from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Configure engine parameters based on environment
# Supabase and production environments need different pool settings
if settings.is_production:
    # Production (Supabase) - Use connection pooler for serverless
    # Supabase pooler uses port 6543 for transaction mode
    # This is essential for Vercel serverless functions
    pooler_url = settings.database_url.replace(":5432/", ":6543/")

    engine = create_engine(
        pooler_url,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=1,  # Very small pool for serverless (1 connection per instance)
        max_overflow=0,  # No overflow - use pooler for scaling
        pool_recycle=300,  # Recycle connections after 5 minutes
        pool_timeout=30,  # Wait up to 30s for a connection
        echo=False,  # Don't log SQL queries in production
        connect_args={
            "connect_timeout": 10,  # Connection timeout
            "options": "-c timezone=utc",  # Set timezone
        },
    )
else:
    # Local development - Larger pool
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=settings.debug,  # Log SQL queries in debug mode
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
