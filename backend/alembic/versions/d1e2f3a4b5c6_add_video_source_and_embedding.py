"""add video_source and embedding columns to videos

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-05-14 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Add video_source column if missing
    has_video_source = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='videos' AND column_name='video_source'"
        )
    ).fetchone()
    if not has_video_source:
        op.add_column(
            "videos",
            sa.Column(
                "video_source",
                sa.String(20),
                nullable=False,
                server_default="liked",
            ),
        )
        op.create_index(
            "idx_user_source",
            "videos",
            ["user_id", "video_source"],
            if_not_exists=True,
        )

    # Add pgvector extension + embedding column if pgvector is available
    has_embedding = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='videos' AND column_name='embedding'"
        )
    ).fetchone()
    if not has_embedding:
        try:
            op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
            op.add_column(
                "videos",
                sa.Column("embedding", sa.Text(), nullable=True),
            )
        except Exception:
            # pgvector not installed — embedding column skipped
            pass


def downgrade() -> None:
    conn = op.get_bind()

    has_embedding = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='videos' AND column_name='embedding'"
        )
    ).fetchone()
    if has_embedding:
        op.drop_column("videos", "embedding")

    has_video_source = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='videos' AND column_name='video_source'"
        )
    ).fetchone()
    if has_video_source:
        op.drop_index("idx_user_source", table_name="videos")
        op.drop_column("videos", "video_source")
