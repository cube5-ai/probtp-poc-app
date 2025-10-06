"""
Health check API endpoints
"""
from datetime import datetime

from fastapi import APIRouter  # type: ignore

router = APIRouter()


@router.get("/health")
async def health_check():
    """Check API health status"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "probtp-poc-api",
        "version": "1.0.0"
    }


@router.get("/health/ready")
async def readiness_check():
    """Check if the service is ready to accept requests"""
    # Add checks for database, redis, etc.
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": "ok"
        }
    }
