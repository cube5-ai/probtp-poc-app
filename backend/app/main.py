"""
Main FastAPI application module
"""
import logging

# Configure logging FIRST, before any other imports
logging.basicConfig(
    level=logging.WARNING,  # Reduced from INFO to WARNING
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Completely disable SQLAlchemy's verbose logging BEFORE importing SQLAlchemy
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.orm').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.engine.Engine').setLevel(logging.ERROR)

import firebase_admin
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import credentials

from app.api.files import router as files_router
from app.api.health import router as health_router
from app.api.parsing import router as parsing_router
from app.api.projects import router as projects_router
from app.api.schemas import router as schemas_router
from app.core.config import get_settings
from app.core.database import create_tables
from app.utils.db_session import get_session_manager

logger = logging.getLogger(__name__)

# Load application settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application on startup and cleanup on shutdown"""
    logger.warning("🚀 ProBTP POC API Starting...")
    
    # Initialize Firebase Admin SDK
    try:
        firebase_admin.get_app()
        logger.warning("✅ Firebase already initialized")
    except ValueError:
        # App not initialized yet
        try:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {
                'projectId': settings.firebase_project_id,
                'storageBucket': f"{settings.firebase_project_id}.firebasestorage.app"
            })
            logger.warning("✅ Firebase initialized successfully")
        except Exception as e:
            logger.error(f"❌ Firebase initialization failed: {e}")
            # Continue startup - Firebase may not be critical for all endpoints

    # Create database tables
    try:
        create_tables()
        logger.warning("✅ Database tables created/verified")
    except Exception as e:
        logger.error(f"❌ Database table creation failed: {e}")
        # Continue startup - some endpoints may still work
    
    # Test database connection
    try:
        db_manager = get_session_manager()
        _ = db_manager.engine
        logger.warning("✅ Database connection verified")
    except Exception as e:
        logger.error(f"⚠️ Database connection test failed: {e}")
        # Continue startup - health endpoint will show status
    
    logger.warning("✅ Application startup complete!")
    
    yield
    
    # Cleanup on shutdown
    logger.warning("👋 Application shutting down...")


# Create FastAPI application instance
app = FastAPI(
    title="ProBTP POC API",
    description="FastAPI backend for ProBTP proof of concept",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://probtp-poc-prod.web.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(files_router, prefix="/api/v1", tags=["files"])
app.include_router(projects_router, prefix="/api/v1")
app.include_router(parsing_router, tags=["parsing"])
app.include_router(schemas_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint returning API information"""
    return {
        "message": "ProBTP POC API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/debug/cors")
async def debug_cors():
    """Debug endpoint to check CORS configuration"""
    return {
        "allowed_origins": [
            "http://localhost:3000",
            "http://localhost:3001",
            "https://probtp-poc-prod.web.app",
        ],
        "environment": settings.ENVIRONMENT,
    }