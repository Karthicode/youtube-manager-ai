"""add watch history table

Revision ID: a1b2c3d4e5f6
Revises: 8d9e7f6a5b4c
Create Date: 2026-03-10 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "8d9e7f6a5b4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create watch_history table."""
    op.create_table(
        "watch_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("youtube_id", sa.String(20), nullable=False),
        sa.Column("position_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("watched_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "video_id", name="uq_watch_history_user_video"),
    )
    op.create_index(op.f("ix_watch_history_id"), "watch_history", ["id"], unique=False)
    op.create_index(
        op.f("ix_watch_history_user_id"), "watch_history", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_watch_history_video_id"), "watch_history", ["video_id"], unique=False
    )
    op.create_index(
        op.f("ix_watch_history_youtube_id"),
        "watch_history",
        ["youtube_id"],
        unique=False,
    )
    op.create_index(
        "idx_wh_user_watched_at",
        "watch_history",
        ["user_id", "watched_at"],
        unique=False,
    )
    op.create_index(
        "idx_wh_user_video",
        "watch_history",
        ["user_id", "video_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop watch_history table."""
    op.drop_index("idx_wh_user_video", table_name="watch_history")
    op.drop_index("idx_wh_user_watched_at", table_name="watch_history")
    op.drop_index(op.f("ix_watch_history_youtube_id"), table_name="watch_history")
    op.drop_index(op.f("ix_watch_history_video_id"), table_name="watch_history")
    op.drop_index(op.f("ix_watch_history_user_id"), table_name="watch_history")
    op.drop_index(op.f("ix_watch_history_id"), table_name="watch_history")
    op.drop_table("watch_history")
