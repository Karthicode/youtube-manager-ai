"""add deleted_at to playlists

Revision ID: b80597d81f11
Revises: ef08f4e09821
Create Date: 2025-10-26 10:11:06.010695

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b80597d81f11'
down_revision: Union[str, Sequence[str], None] = 'ef08f4e09821'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('playlists', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('playlists', 'deleted_at')
