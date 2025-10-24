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
        pool_pre_ping=True,  # Verify connections before using
        pool_size=1,  # Single connection per serverless instance
        max_overflow=0,  # No overflow - Supabase pooler handles scaling
        pool_recycle=300,  # Recycle connections after 5 minutes
        echo=False,  # Don't log SQL queries in production
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
