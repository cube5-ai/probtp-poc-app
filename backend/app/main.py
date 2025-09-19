"""
Main FastAPI application module
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import get_settings

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


@app.get("/")
async def root():
    """Root endpoint returning API information"""
    return {
        "message": "ProBTP POC API",
        "version": "1.0.0",
        "docs": "/docs",
    }
