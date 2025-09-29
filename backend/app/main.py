"""
Main FastAPI application module
"""
import firebase_admin
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import credentials

from app.api.files import router as files_router
from app.api.health import router as health_router
from app.api.parsing import router as parsing_router
from app.api.projects import router as projects_router
from app.core.config import get_settings
from app.core.database import create_tables

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
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(files_router, prefix="/api/v1", tags=["files"])
app.include_router(projects_router, prefix="/api/v1", tags=["projects"])
app.include_router(parsing_router, tags=["parsing"])

# Create database tables on startup
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
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

    create_tables()


@app.get("/")
async def root():
    """Root endpoint returning API information"""
    return {
        "message": "ProBTP POC API",
        "version": "1.0.0",
        "docs": "/docs",
    }
