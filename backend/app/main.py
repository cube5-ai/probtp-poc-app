"""
Main FastAPI application module
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.schemas import router as schemas_router
from app.core.config import get_settings
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
    """Log application startup information"""
    logger.info("=" * 60)
    logger.info("🚀 ProBTP POC API Starting...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info("=" * 60)
    
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
