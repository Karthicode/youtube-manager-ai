"""add chat sessions and messages

Revision ID: 4f3c2e19b7aa
Revises: b80597d81f11
Create Date: 2026-03-03 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "4f3c2e19b7aa"
down_revision: Union[str, Sequence[str], None] = "b80597d81f11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("previous_response_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_sessions_id"), "chat_sessions", ["id"], unique=False)
    op.create_index(
        op.f("ix_chat_sessions_last_message_at"),
        "chat_sessions",
        ["last_message_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_sessions_user_id"), "chat_sessions", ["user_id"], unique=False
    )
    op.create_index(
        "idx_chat_sessions_user_last_message",
        "chat_sessions",
        ["user_id", "last_message_at"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls_json", sa.Text(), nullable=True),
        sa.Column("tool_results_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_messages_created_at"),
        "chat_messages",
        ["created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_chat_messages_id"), "chat_messages", ["id"], unique=False)
    op.create_index(
        op.f("ix_chat_messages_role"), "chat_messages", ["role"], unique=False
    )
    op.create_index(
        op.f("ix_chat_messages_session_id"),
        "chat_messages",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "idx_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_chat_messages_session_created", table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_session_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_role"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_created_at"), table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("idx_chat_sessions_user_last_message", table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_user_id"), table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_last_message_at"), table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_id"), table_name="chat_sessions")
    op.drop_table("chat_sessions")
