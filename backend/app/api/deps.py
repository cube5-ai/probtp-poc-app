"""
FastAPI dependencies for authentication and database access
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.auth_service import FirebaseAuthService

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict[str, any]:
    """
    FastAPI dependency to get current authenticated user

    Args:
        credentials: HTTP Bearer credentials from request

    Returns:
        Dictionary with user information

    Raises:
        HTTPException: If token is invalid or expired
    """
    from app.core.config import get_settings
    settings = get_settings()

    # If token is provided, always try to verify it first
    if credentials:
        try:
            # Extract token from Bearer credentials
            token = credentials.credentials

            # Verify Firebase token and get user info
            user_info = FirebaseAuthService.verify_id_token(token)
            return user_info

        except Exception as e:
            # In development mode, allow fallback if token verification fails
            if settings.environment == "development" and settings.debug:
                print(f"⚠️  Token verification failed in dev mode: {e}")
                print(f"⚠️  Falling back to dev user")
                return {
                    'user_id': 'dev-user-123',
                    'email': 'dev@example.com',
                    'email_verified': True,
                    'name': 'Development User',
                    'roles': ['admin'],
                    'firebase_claims': {}
                }
            else:
                # In production, fail on invalid token
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid authentication credentials: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
    
    # No credentials provided
    if settings.environment == "development" and settings.debug:
        # Return mock user for development when no token
        return {
            'user_id': 'dev-user-123',
            'email': 'dev@example.com',
            'email_verified': True,
            'name': 'Development User',
            'roles': ['admin'],
            'firebase_claims': {}
        }
    else:
        # Production mode: require authentication
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(
    current_user: dict[str, any] = Depends(get_current_user)
) -> str:
    """
    FastAPI dependency to get current user ID
    
    Args:
        current_user: Current user information from get_current_user
    
    Returns:
        Firebase user ID string
    """
    return current_user['user_id']


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False))
) -> dict[str, any] | None:
    """
    FastAPI dependency to get optional user (for endpoints that work with or without auth)
    
    Args:
        credentials: Optional HTTP Bearer credentials
    
    Returns:
        User information dictionary or None if no valid credentials
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        user_info = FirebaseAuthService.verify_id_token(token)
        return user_info
    except Exception:
        # Return None instead of raising exception for optional auth
        return None


def require_roles(required_roles: list):
    """
    Factory function to create role-based access dependency
    
    Args:
        required_roles: List of roles that are allowed access
    
    Returns:
        FastAPI dependency function
    """
    async def check_roles(
        current_user: dict[str, any] = Depends(get_current_user)
    ) -> dict[str, any]:
        """
        Check if current user has required roles
        
        Args:
            current_user: Current user information
        
        Returns:
            User information if authorized
        
        Raises:
            HTTPException: If user doesn't have required roles
        """
        user_roles = current_user.get('roles', [])

        # Check if user has any of the required roles
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {required_roles}"
            )

        return current_user

    return check_roles


# Common role dependencies for convenience
require_admin = require_roles(['admin'])
require_commercial = require_roles(['admin', 'commercial'])
require_any_role = require_roles(['admin', 'commercial', 'viewer'])


class DatabaseDependency:
    """Database session dependency with automatic cleanup"""

    def __init__(self):
        self.db = None

    async def __call__(self, db: Session = Depends(get_db)) -> Session:
        """Get database session"""
        self.db = db
        return db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()


# Database dependency instance
get_database = DatabaseDependency()
