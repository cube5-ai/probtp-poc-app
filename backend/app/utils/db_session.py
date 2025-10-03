"""
Database session management utility
Handles database connection lifecycle and session creation
"""
from contextlib import contextmanager
from typing import Generator
import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from app.core.config import get_settings

# Configure logger
logger = logging.getLogger(__name__)


# Base class for SQLAlchemy models
Base = declarative_base()


class DatabaseSessionManager:
    """Manages database engine and session creation"""
    
    def __init__(self, database_url: str = None):
        """Initialize database session manager with connection URL"""
        settings = get_settings()
        
        # Use provided URL or get from settings
        if database_url:
            self.database_url = database_url
            logger.info(f"Using provided database URL")
        else:
            # Get the appropriate database URL (handles Cloud Run vs local)
            self.database_url = settings.get_database_url()
            logger.info(f"Environment: {settings.ENVIRONMENT}")
            # Log connection string without password
            safe_url = self.database_url.split('@')[0].split(':')[0] + ':****@' + self.database_url.split('@')[1] if '@' in self.database_url else 'invalid_url'
            logger.info(f"Database URL configured: {safe_url}")
        
        self._engine: Engine = None
        self._session_factory = None
    
    @property
    def engine(self) -> Engine:
        """Get or create database engine"""
        if self._engine is None:
            try:
                logger.info("Creating database engine...")
                
                # Configure connection args based on database type
                connect_args = {}
                if self.database_url.startswith('postgresql'):
                    connect_args = {"connect_timeout": 10}
                elif self.database_url.startswith('sqlite'):
                    connect_args = {"timeout": 10}
                
                self._engine = create_engine(
                    self.database_url,
                    pool_pre_ping=True,
                    pool_size=10,
                    max_overflow=20,
                    connect_args=connect_args
                )
                # Test the connection
                with self._engine.connect() as conn:
                    logger.info("✅ Database connection successful!")
            except Exception as e:
                logger.error(f"❌ Database connection failed: {type(e).__name__}: {str(e)}")
                raise
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
            logger.debug("Database session started")
            yield session
            session.commit()
            logger.debug("Database session committed")
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {type(e).__name__}: {str(e)}")
            raise
        finally:
            session.close()
            logger.debug("Database session closed")
    
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
