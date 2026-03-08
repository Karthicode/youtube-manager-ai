"""merge api_key and chat_sessions

Revision ID: 13d1c7fcca16
Revises: c3a1f5e8d201, 4f3c2e19b7aa
Create Date: 2026-03-08 10:13:52.636460

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "13d1c7fcca16"
down_revision: Union[str, Sequence[str], None] = ("c3a1f5e8d201", "4f3c2e19b7aa")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
