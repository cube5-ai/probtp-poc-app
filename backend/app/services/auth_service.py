"""
Authentication and authorization service using Firebase
"""

from firebase_admin import auth
from firebase_admin.auth import UserRecord
from sqlalchemy.orm import Session

from app.models.file import File
from app.models.project_member import ProjectMember


class AuthorizationService:
    """Service for handling authorization logic"""

    @staticmethod
    async def check_project_permission(
        db: Session,
        user_id: str,
        project_id: str,
        required_roles: list[str] | None = None
    ) -> bool:
        """
        Check if user has access to project with required role
        
        Args:
            db: Database session
            user_id: Firebase user ID
            project_id: Project UUID
            required_roles: List of acceptable roles (defaults to all)
        
        Returns:
            True if user has permission, False otherwise
        """
        if required_roles is None:
            required_roles = ['owner', 'editor', 'viewer']

        member = db.query(ProjectMember).filter(
            ProjectMember.user_id == user_id,
            ProjectMember.project_id == project_id,
            ProjectMember.role.in_(required_roles)
        ).first()

        return member is not None

    @staticmethod
    async def get_user_project_role(
        db: Session,
        user_id: str,
        project_id: str
    ) -> str | None:
        """
        Get user's role in a specific project
        
        Args:
            db: Database session
            user_id: Firebase user ID
            project_id: Project UUID
        
        Returns:
            Role string or None if user is not a member
        """
        member = db.query(ProjectMember).filter(
            ProjectMember.user_id == user_id,
            ProjectMember.project_id == project_id
        ).first()

        return member.role if member else None

    @staticmethod
    async def can_upload_file(
        db: Session,
        user_id: str,
        project_id: str
    ) -> bool:
        """
        Check if user can upload files to project
        
        Args:
            db: Database session
            user_id: Firebase user ID
            project_id: Project UUID
        
        Returns:
            True if user can upload, False otherwise
        """
        return await AuthorizationService.check_project_permission(
            db, user_id, project_id, ['owner', 'editor']
        )

    @staticmethod
    async def can_delete_file(
        db: Session,
        user_id: str,
        file_id: str
    ) -> bool:
        """
        Check if user can delete a file
        
        Args:
            db: Database session
            user_id: Firebase user ID
            file_id: File UUID
        
        Returns:
            True if user can delete, False otherwise
        """
        file = db.query(File).filter(
            File.id == file_id,
            File.deleted_at.is_(None)
        ).first()

        if not file:
            return False

        # File owner can always delete their own files
        if file.uploaded_by == user_id:
            return True

        # Project owners can delete any file in their project
        return await AuthorizationService.check_project_permission(
            db, user_id, file.project_id, ['owner']
        )

    @staticmethod
    async def can_view_file(
        db: Session,
        user_id: str,
        file_id: str
    ) -> bool:
        """
        Check if user can view/download a file
        
        Args:
            db: Database session
            user_id: Firebase user ID
            file_id: File UUID
        
        Returns:
            True if user can view, False otherwise
        """
        file = db.query(File).filter(
            File.id == file_id,
            File.deleted_at.is_(None)
        ).first()

        if not file:
            return False

        # Check if user has any access to the project
        return await AuthorizationService.check_project_permission(
            db, user_id, file.project_id, ['owner', 'editor', 'viewer']
        )


class FirebaseAuthService:
    """Service for Firebase authentication operations"""

    @staticmethod
    def verify_id_token(id_token: str) -> dict:
        """
        Verify Firebase ID token and extract user information
        
        Args:
            id_token: Firebase ID token from client
        
        Returns:
            Dictionary with user information
        
        Raises:
            firebase_admin.auth.InvalidIdTokenError: If token is invalid
            firebase_admin.auth.ExpiredIdTokenError: If token is expired
        """
        try:
            # Verify the ID token
            decoded_token = auth.verify_id_token(id_token)

            return {
                'user_id': decoded_token['uid'],
                'email': decoded_token.get('email'),
                'email_verified': decoded_token.get('email_verified', False),
                'name': decoded_token.get('name'),
                'roles': decoded_token.get('roles', []),  # Custom claims
                'firebase_claims': decoded_token
            }
        except Exception as e:
            raise e

    @staticmethod
    def get_user_by_uid(uid: str) -> UserRecord:
        """
        Get user record by Firebase UID
        
        Args:
            uid: Firebase user UID
        
        Returns:
            Firebase UserRecord
        
        Raises:
            firebase_admin.auth.UserNotFoundError: If user doesn't exist
        """
        return auth.get_user(uid)

    @staticmethod
    def set_custom_user_claims(uid: str, claims: dict) -> None:
        """
        Set custom claims for a user (for role management)
        
        Args:
            uid: Firebase user UID
            claims: Dictionary of custom claims to set
        """
        auth.set_custom_user_claims(uid, claims)
