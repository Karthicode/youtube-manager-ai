"""deduplicate videos and add unique constraint on (user_id, youtube_id)

Revision ID: f1g2h3i4j5k6
Revises: e3f4a5b6c7d8
Create Date: 2026-05-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f1g2h3i4j5k6"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: For each (user_id, youtube_id) group with duplicates, pick a winner.
    # Prefer is_categorized=True; on tie keep lowest id.
    # Build a mapping: loser_id -> winner_id for all duplicates.
    duplicates = conn.execute(
        sa.text(
            """
            SELECT
                user_id,
                youtube_id,
                array_agg(id ORDER BY is_categorized DESC, id ASC) AS ids
            FROM videos
            GROUP BY user_id, youtube_id
            HAVING count(*) > 1
            """
        )
    ).fetchall()

    for row in duplicates:
        ids = row[2]  # sorted: winner first, losers after
        winner_id = ids[0]
        loser_ids = ids[1:]

        # Step 2: Re-point FK references from losers to winner
        for table, col in [
            ("playlist_videos", "video_id"),
            ("video_categories", "video_id"),
            ("video_tags", "video_id"),
            ("watch_history", "video_id"),
        ]:
            # For playlist_videos we must avoid creating duplicate (playlist_id, video_id)
            # rows — delete conflicting rows before updating
            if table == "playlist_videos":
                # Find playlist_id values that the winner already covers
                existing_playlist_ids = conn.execute(
                    sa.text(
                        "SELECT playlist_id FROM playlist_videos WHERE video_id = :winner_id"
                    ),
                    {"winner_id": winner_id},
                ).fetchall()
                existing_pids = {r[0] for r in existing_playlist_ids}

                for loser_id in loser_ids:
                    if existing_pids:
                        # Delete loser rows whose playlist_id would conflict with winner
                        conn.execute(
                            # table/col come from the fixed CHILD_TABLES list
                            # above, never user input; values use bind params.
                            # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
                            sa.text(
                                f"DELETE FROM {table} WHERE {col} = :loser_id "  # noqa: S608
                                "AND playlist_id = ANY(:pids)"
                            ),
                            {"loser_id": loser_id, "pids": list(existing_pids)},
                        )
                    # Update remaining loser rows to point at winner
                    conn.execute(
                        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
                        sa.text(
                            f"UPDATE {table} SET {col} = :winner_id WHERE {col} = :loser_id"  # noqa: S608
                        ),
                        {"winner_id": winner_id, "loser_id": loser_id},
                    )
            elif table == "video_categories":
                existing_cat_ids = conn.execute(
                    sa.text(
                        "SELECT category_id FROM video_categories WHERE video_id = :winner_id"
                    ),
                    {"winner_id": winner_id},
                ).fetchall()
                existing_cids = {r[0] for r in existing_cat_ids}

                for loser_id in loser_ids:
                    if existing_cids:
                        conn.execute(
                            sa.text(
                                "DELETE FROM video_categories WHERE video_id = :loser_id "
                                "AND category_id = ANY(:cids)"
                            ),
                            {"loser_id": loser_id, "cids": list(existing_cids)},
                        )
                    conn.execute(
                        sa.text(
                            "UPDATE video_categories SET video_id = :winner_id WHERE video_id = :loser_id"
                        ),
                        {"winner_id": winner_id, "loser_id": loser_id},
                    )
            elif table == "video_tags":
                existing_tag_ids = conn.execute(
                    sa.text(
                        "SELECT tag_id FROM video_tags WHERE video_id = :winner_id"
                    ),
                    {"winner_id": winner_id},
                ).fetchall()
                existing_tids = {r[0] for r in existing_tag_ids}

                for loser_id in loser_ids:
                    if existing_tids:
                        conn.execute(
                            sa.text(
                                "DELETE FROM video_tags WHERE video_id = :loser_id "
                                "AND tag_id = ANY(:tids)"
                            ),
                            {"loser_id": loser_id, "tids": list(existing_tids)},
                        )
                    conn.execute(
                        sa.text(
                            "UPDATE video_tags SET video_id = :winner_id WHERE video_id = :loser_id"
                        ),
                        {"winner_id": winner_id, "loser_id": loser_id},
                    )
            else:
                for loser_id in loser_ids:
                    conn.execute(
                        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
                        sa.text(
                            f"UPDATE {table} SET {col} = :winner_id WHERE {col} = :loser_id"  # noqa: S608
                        ),
                        {"winner_id": winner_id, "loser_id": loser_id},
                    )

        # Step 3: Delete the loser rows
        conn.execute(
            sa.text("DELETE FROM videos WHERE id = ANY(:loser_ids)"),
            {"loser_ids": loser_ids},
        )

    # Step 4: Drop the old phantom index if it exists (was never actually created,
    # but drop defensively in case it somehow exists)
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_user_youtube_id_source"))

    # Step 5: Create the new unique index on (user_id, youtube_id)
    conn.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_youtube_id "
            "ON videos (user_id, youtube_id)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_user_youtube_id"))
    # Note: we cannot restore deleted duplicate rows, so downgrade only removes the index.
