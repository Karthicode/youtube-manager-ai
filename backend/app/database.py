from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Configure engine parameters based on environment
# Supabase and production environments need different pool settings
if settings.is_production:
    # Production (Supabase) - Use connection pooler for serverless
    # DATABASE_URL should be the Supabase connection pooling URL (port 6543)
    # Format: postgresql://postgres.[project]:password@aws-0-[region].pooler.supabase.com:6543/postgres
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,  # allow parallel requests
        max_overflow=10,  # allow spike load briefly
        pool_timeout=30,  # timeout before erroring
        pool_recycle=1800,  # recycle every 30min to avoid stale connections
        echo=False,
    )
else:
    # Local development - Larger pool
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=settings.debug,
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
