"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.models.base import Base

settings = get_settings()

# Create database engine
engine = create_engine(
    settings.database_url,
    poolclass=StaticPool,
    connect_args={
        "check_same_thread": False
    } if "sqlite" in settings.database_url else {},
    echo=settings.debug,  # Log SQL queries in debug mode
)

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
