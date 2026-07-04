"""SQLAlchemy session factory for the isolated eval database."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  # registers all model tables on Base.metadata
from app.database import Base

EVALS_DATABASE_URL = os.environ.get(
    "EVALS_DATABASE_URL", "postgresql://evals:evals@localhost:55432/evals"
)

_engine = None


def get_eval_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(EVALS_DATABASE_URL)
    return _engine


def create_schema() -> None:
    """Create pgvector extension and all app tables in the eval DB."""
    engine = get_eval_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)


def get_eval_session() -> Session:
    return sessionmaker(bind=get_eval_engine())()
