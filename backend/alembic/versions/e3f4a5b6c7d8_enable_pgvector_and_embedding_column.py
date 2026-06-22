"""enable pgvector extension and add embedding column

Revision ID: e3f4a5b6c7d8
Revises: d1e2f3a4b5c6
Create Date: 2026-05-15 00:00:00.000000

The previous migration (d1e2f3a4b5c6) silently swallowed the pgvector
CREATE EXTENSION failure when running against a postgres:15-alpine image
that has no pgvector. This migration re-attempts with the correct image
(pgvector/pgvector:pg15) now in place.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Install pgvector — idempotent, safe to re-run.
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Add embedding column if still missing (the previous migration may have
    # skipped it silently when pgvector wasn't available).
    has_embedding = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='videos' AND column_name='embedding'"
        )
    ).fetchone()

    if not has_embedding:
        op.add_column(
            "videos",
            sa.Column("embedding", sa.Text(), nullable=True),
        )


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
