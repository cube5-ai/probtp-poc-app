"""
Main FastAPI application module
"""
import firebase_admin
import logging
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
app.include_router(projects_router, prefix="/api/v1", tags=["projects"])
app.include_router(parsing_router, tags=["parsing"])
app.include_router(schemas_router, prefix="/api/v1", tags=["schemas"])


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
    logger.info("=" * 60)
    logger.info("🚀 ProBTP POC API Starting...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info("=" * 60)
    
    # Initialize Firebase Admin SDK
    try:
        firebase_admin.get_app()
    except ValueError:
        # App not initialized yet
        if settings.environment == "development":
            # Use emulator or default credentials for development
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
        else:
            # Production: use service account key
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {
                'projectId': settings.firebase_project_id
            })

    # Create database tables
    create_tables()
    
    # Test database connection
    try:
        db_manager = get_session_manager()
        # Access the engine property which will trigger connection test
        _ = db_manager.engine
        logger.info("✅ Application startup complete - Database ready!")
    except Exception as e:
        logger.error(f"❌ Database connection failed during startup: {e}")
        # Don't raise - let the app start but log the error
    
    logger.info("=" * 60)