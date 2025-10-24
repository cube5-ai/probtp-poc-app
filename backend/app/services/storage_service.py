"""
Firebase Storage service for file operations
"""
import json
import os
import time
from datetime import timedelta

from google.cloud import storage as gcs_storage
from google.cloud.exceptions import NotFound
from google.oauth2 import service_account

from app.core.config import get_settings
from app.core.storage import StorageConfig


class StorageService:
    """Service for handling Firebase Storage operations"""

    def __init__(self):
        """Initialize storage service with Firebase Storage"""
        self.settings = get_settings()
        
        # For signed URLs, we need service account credentials with a private key
        # Try to get from environment variable (for runtime) or settings (from .env file)
        service_account_key = os.getenv("FIREBASE_STORAGE_SERVICE_ACCOUNT_KEY") or \
                             getattr(self.settings, 'firebase_storage_service_account_key', None)
        
        if service_account_key:
            # Check if it's a file path
            if os.path.exists(service_account_key):
                # Load from file
                credentials = service_account.Credentials.from_service_account_file(service_account_key)
            else:
                # Try as JSON string
                try:
                    credentials_info = json.loads(service_account_key)
                    credentials = service_account.Credentials.from_service_account_info(credentials_info)
                except (json.JSONDecodeError, Exception) as e:
                    print(f"⚠️  Failed to parse FIREBASE_STORAGE_SERVICE_ACCOUNT_KEY: {e}")
                    # Fallback: use default Firebase Storage (won't support signed URLs)
                    from firebase_admin import storage
                    self.bucket = storage.bucket()
                    return
            
            # Create GCS client with service account credentials for signed URLs
            client = gcs_storage.Client(
                credentials=credentials,
                project=credentials.project_id if hasattr(credentials, 'project_id') else self.settings.firebase_project_id
            )
            self.bucket = client.bucket(f"{self.settings.firebase_project_id}.firebasestorage.app")
        else:
            print("⚠️  FIREBASE_STORAGE_SERVICE_ACCOUNT_KEY not set - signed URLs will not work")
            # Fallback: use default Firebase Storage (won't support signed URLs)
            from firebase_admin import storage
            self.bucket = storage.bucket()

    def generate_upload_url(
        self,
        project_id: str,
        file_id: str,
        content_type: str = 'application/pdf',
        expiration_minutes: int = None
    ) -> tuple[str, str]:
        """
        Generate a signed URL for direct upload to Cloud Storage

        Args:
            project_id: Project ID for file organization
            file_id: Unique file identifier
            content_type: MIME type of the file
            expiration_minutes: URL expiration time (defaults to config)

        Returns:
            Tuple of (signed_url, storage_path)
        """
        if expiration_minutes is None:
            expiration_minutes = self.settings.upload_url_expiration_minutes

        timestamp = int(time.time())
        blob_name = StorageConfig.get_file_path(project_id, file_id, timestamp)
        blob = self.bucket.blob(blob_name)
        
        # Generate signed URL - Note: Content-Type must match exactly on upload
        # We use application/octet-stream to be more flexible with file types
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="PUT",
            content_type="application/octet-stream"
        )

        return url, blob_name

    def generate_download_url(
        self,
        storage_path: str,
        expiration_minutes: int | None = None,
        filename: str | None = None
    ) -> str:
        """
        Generate a signed URL for file download

        Args:
            storage_path: Path to file in cloud storage
            expiration_minutes: URL expiration time (defaults to config)
            filename: Optional filename to use for download

        Returns:
            Signed download URL

        Raises:
            FileNotFoundError: If file doesn't exist in storage
        """
        if expiration_minutes is None:
            expiration_minutes = self.settings.download_url_expiration_minutes

        blob = self.bucket.blob(storage_path)

        # Check if file exists
        if not blob.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")

        # Reload to get metadata
        blob.reload()

        # Generate signed download URL with attachment disposition
        query_params = {}
        
        # Force download with attachment disposition
        if filename:
            query_params["response-content-disposition"] = f'attachment; filename="{filename}"'
        else:
            query_params["response-content-disposition"] = "attachment"
        
        # Set content-type to match the file
        if blob.content_type:
            query_params["response-content-type"] = blob.content_type

        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
            query_parameters=query_params
        )

        return url

    def generate_view_url(
        self,
        storage_path: str,
        expiration_minutes: int | None = None
    ) -> str:
        """
        Generate a signed URL for file viewing (inline display)

        Args:
            storage_path: Path to file in cloud storage
            expiration_minutes: URL expiration time (defaults to config)

        Returns:
            Signed view URL for inline display

        Raises:
            FileNotFoundError: If file doesn't exist in storage
        """
        if expiration_minutes is None:
            expiration_minutes = self.settings.download_url_expiration_minutes

        blob = self.bucket.blob(storage_path)

        # Check if file exists
        if not blob.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")

        # Reload blob to get current metadata
        blob.reload()
        
        # Generate signed URL for inline viewing with proper content-type
        query_params = {
            "response-content-disposition": "inline"
        }
        
        # Add content-type to response parameters to ensure proper display
        if blob.content_type:
            query_params["response-content-type"] = blob.content_type
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
            query_parameters=query_params
        )

        return url

    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from cloud storage
        
        Args:
            storage_path: Path to file in cloud storage
        
        Returns:
            True if file was deleted, False if file didn't exist
        """
        try:
            blob = self.bucket.blob(storage_path)
            blob.delete()
            return True
        except NotFound:
            return False

    def file_exists(self, storage_path: str) -> bool:
        """
        Check if a file exists in cloud storage
        
        Args:
            storage_path: Path to file in cloud storage
        
        Returns:
            True if file exists, False otherwise
        """
        blob = self.bucket.blob(storage_path)
        return blob.exists()

    def update_content_type(self, storage_path: str, content_type: str) -> None:
        """
        Update the content-type metadata of an uploaded file
        
        Args:
            storage_path: Path to file in cloud storage
            content_type: MIME type to set
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        blob = self.bucket.blob(storage_path)
        
        if not blob.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")
        
        # Update content-type and content-disposition for inline viewing
        blob.content_type = content_type
        blob.content_disposition = "inline"
        blob.patch()

    def get_file_info(self, storage_path: str) -> dict:
        """
        Get metadata information about a file

        Args:
            storage_path: Path to file in cloud storage

        Returns:
            Dictionary with file metadata

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        blob = self.bucket.blob(storage_path)

        if not blob.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")

        # Reload to get updated metadata
        blob.reload()

        return {
            "name": blob.name,
            "size": blob.size,
            "created": blob.time_created,
            "updated": blob.updated,
            "content_type": blob.content_type,
            "md5_hash": blob.md5_hash,
        }
