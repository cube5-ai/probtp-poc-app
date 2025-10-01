"""
Database session management utility
Handles database connection lifecycle and session creation
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from app.core.config import get_settings


# Base class for SQLAlchemy models
Base = declarative_base()


class DatabaseSessionManager:
    """Manages database engine and session creation"""
    
    def __init__(self, database_url: str = None):
        """Initialize database session manager with connection URL"""
        # Use provided URL or get from settings, fallback to Cloud SQL proxy
        if database_url:
            self.database_url = database_url
        else:
            database_url = get_settings().DATABASE_URL
            # If using default sqlite, switch to PostgreSQL via proxy
            if "sqlite" in database_url:
                self.database_url = "postgresql://probtp-poc_user:X0i7!W0e3/CIgg@localhost:5432/probtp-poc_prod"
            else:
                self.database_url = database_url
        self._engine: Engine = None
        self._session_factory = None
    
    @property
    def engine(self) -> Engine:
        """Get or create database engine"""
        if self._engine is None:
            self._engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                connect_args={"connect_timeout": 10}
            )
        return self._engine
    
    @property
    def session_factory(self):
        """Get or create session factory"""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
        return self._session_factory
    
    def create_session(self) -> Session:
        """Create a new database session"""
        return self.session_factory()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope for database operations"""
        session = self.create_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def close(self):
        """Close database engine and connections"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None


# Global database session manager instance
_db_manager = DatabaseSessionManager()


def get_db_session() -> Generator[Session, None, None]:
    """Dependency function to get database session for FastAPI routes"""
    with _db_manager.session_scope() as session:
        yield session


def get_session_manager() -> DatabaseSessionManager:
    """Get the global database session manager"""
    return _db_manager
