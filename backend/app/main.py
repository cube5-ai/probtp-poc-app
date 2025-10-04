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

# Create FastAPI application instance
app = FastAPI(
    title="ProBTP POC API",
    description="FastAPI backend for ProBTP proof of concept",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.warning("🚀 ProBTP POC API Starting...")
    
    # Initialize Firebase Admin SDK
    try:
        firebase_admin.get_app()
    except ValueError:
        # App not initialized yet
        if settings.environment == "development":
            # Use Application Default Credentials for development
            if not firebase_admin._apps:
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred, {
                    'projectId': settings.firebase_project_id,
                    'storageBucket': f"{settings.firebase_project_id}.firebasestorage.app"
                })
        else:
            # Production: use service account key
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {
                'projectId': settings.firebase_project_id,
                'storageBucket': f"{settings.firebase_project_id}.firebasestorage.app"
            })

    # Create database tables
    create_tables()
    
    # Test database connection
    try:
        db_manager = get_session_manager()
        # Access the engine property which will trigger connection test
        _ = db_manager.engine
        logger.warning("✅ Application startup complete!")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        # Don't raise - let the app start but log the error