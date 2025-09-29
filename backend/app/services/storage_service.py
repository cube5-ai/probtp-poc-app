"""
Google Cloud Storage service for file operations
"""
import time
from datetime import timedelta

from google.cloud import storage
from google.cloud.exceptions import NotFound

from app.core.config import get_settings
from app.core.storage import StorageConfig


class StorageService:
    """Service for handling Google Cloud Storage operations"""

    def __init__(self):
        """Initialize storage service with GCS client"""
        self.settings = get_settings()

        # Use Application Default Credentials (ADC)
        self.client = storage.Client()
        self.bucket_name = StorageConfig.get_bucket_name()
        self.bucket = self.client.bucket(self.bucket_name)

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

        # Generate signed URL with content restrictions
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="PUT",
            content_type=content_type
        )

        return url, blob_name

    def generate_download_url(
        self,
        storage_path: str,
        expiration_minutes: int | None = None
    ) -> str:
        """
        Generate a signed URL for file download

        Args:
            storage_path: Path to file in cloud storage
            expiration_minutes: URL expiration time (defaults to config)

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

        # Generate signed download URL
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
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
