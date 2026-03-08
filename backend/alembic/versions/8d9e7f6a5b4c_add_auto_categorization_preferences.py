"""add auto categorization preferences

Revision ID: 8d9e7f6a5b4c
Revises: 13d1c7fcca16
Create Date: 2026-03-08 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8d9e7f6a5b4c"
down_revision: Union[str, Sequence[str], None] = "13d1c7fcca16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create user_preferences table
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "auto_categorize_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "auto_categorize_max_videos",
            sa.Integer(),
            nullable=False,
            server_default="50",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_preferences_id"), "user_preferences", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_user_preferences_user_id"),
        "user_preferences",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_auto_categorize_enabled",
        "user_preferences",
        ["auto_categorize_enabled"],
        unique=False,
    )

    # Add last_auto_categorize_at to users table
    op.add_column(
        "users", sa.Column("last_auto_categorize_at", sa.DateTime(), nullable=True)
    )

    # Create default preferences for existing users (all disabled by default)
    op.execute(
        """
        INSERT INTO user_preferences (user_id, auto_categorize_enabled, auto_categorize_max_videos, created_at, updated_at)
        SELECT id, false, 50, NOW(), NOW() FROM users
        WHERE NOT EXISTS (SELECT 1 FROM user_preferences WHERE user_preferences.user_id = users.id)
    """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove last_auto_categorize_at from users table
    op.drop_column("users", "last_auto_categorize_at")

    # Drop user_preferences table
    op.drop_index("ix_auto_categorize_enabled", table_name="user_preferences")
    op.drop_index(op.f("ix_user_preferences_user_id"), table_name="user_preferences")
    op.drop_index(op.f("ix_user_preferences_id"), table_name="user_preferences")
    op.drop_table("user_preferences")
