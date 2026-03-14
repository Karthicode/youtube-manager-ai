"""add performance indexes for slow queries

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-03-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing performance indexes identified from slow query analysis."""

    # Composite index for the common pattern:
    #   WHERE user_id = ? ORDER BY liked_at DESC
    # Used by: video list, categorization queues, embedding generation, agent queries
    op.create_index(
        "idx_videos_user_liked_at",
        "videos",
        ["user_id", "liked_at"],
        postgresql_ops={"liked_at": "DESC NULLS LAST"},
    )

    # HNSW index for approximate nearest-neighbour vector search.
    # Dramatically speeds up the <=> cosine distance operator.
    # m=16 and ef_construction=64 are safe defaults for 1536-dim embeddings.
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_embedding_hnsw
        ON videos
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_videos_embedding_hnsw")
    op.drop_index("idx_videos_user_liked_at", table_name="videos")
