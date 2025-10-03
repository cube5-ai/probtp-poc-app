"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.models.base import Base

settings = get_settings()

database_url = settings.get_database_url()

# Use dynamic engine configuration so we can talk to either SQLite (local) or
# Cloud SQL/Postgres (via DATABASE_URL) without editing this module again.
engine_kwargs = {
    "echo": settings.debug,
}

if database_url.startswith("sqlite"):
    engine_kwargs["poolclass"] = StaticPool
    engine_kwargs["connect_args"] = {"check_same_thread": False}

# Create database engine
engine = create_engine(database_url, **engine_kwargs)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """
    Dependency function to get database session
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
