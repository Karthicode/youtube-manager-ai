"""cleanup unused indexes and add fk indexes

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-03-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop redundant PK indexes (PostgreSQL auto-indexes primary keys)
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_playlists_id"), table_name="playlists")

    # Drop unused single-column index (composite idx_user_youtube_playlist covers this)
    op.drop_index(op.f("ix_playlists_youtube_id"), table_name="playlists")

    # Drop index on chat_messages.role (never filtered in any query)
    op.drop_index(op.f("ix_chat_messages_role"), table_name="chat_messages")

    # Add missing FK covering indexes on junction tables
    op.create_index(
        "idx_video_categories_category_id",
        "video_categories",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        "idx_video_tags_tag_id",
        "video_tags",
        ["tag_id"],
        unique=False,
    )


def downgrade() -> None:
    # Remove FK indexes
    op.drop_index("idx_video_tags_tag_id", table_name="video_tags")
    op.drop_index("idx_video_categories_category_id", table_name="video_categories")

    # Restore dropped indexes
    op.create_index(
        op.f("ix_chat_messages_role"), "chat_messages", ["role"], unique=False
    )
    op.create_index(
        op.f("ix_playlists_youtube_id"), "playlists", ["youtube_id"], unique=False
    )
    op.create_index(op.f("ix_playlists_id"), "playlists", ["id"], unique=False)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
