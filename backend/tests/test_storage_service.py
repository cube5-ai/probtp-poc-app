"""
Tests for storage service functionality
"""
import time
from unittest.mock import Mock, patch

import pytest

from app.core.storage import StorageConfig
from app.services.storage_service import StorageService


class TestStorageService:
    """Test cases for StorageService"""
    
    def test_storage_config_get_bucket_name(self):
        """Test bucket name retrieval based on environment"""
        # Test default environment
        bucket_name = StorageConfig.get_bucket_name()
        assert bucket_name == 'probtp-poc-prod'
    
    def test_storage_config_get_file_path(self):
        """Test file path generation"""
        project_id = "test-project-123"
        file_id = "test-file-456"
        timestamp = 1640995200  # 2022-01-01 00:00:00 UTC
        
        # Test file path format
        path = StorageConfig.get_file_path(project_id, file_id, timestamp)
        expected_path = f"dev/projects/{project_id}/files/{file_id}_{timestamp}.pdf"
        
        assert path == expected_path
        assert "projects" in path
        assert project_id in path
        assert file_id in path
        assert str(timestamp) in path
        assert path.endswith('.pdf')
    
    @patch.dict('os.environ', {'ENVIRONMENT': 'production'})
    def test_storage_config_production_env(self):
        """Test path generation for production environment"""
        project_id = "prod-project"
        file_id = "prod-file"
        timestamp = int(time.time())
        
        path = StorageConfig.get_file_path(project_id, file_id, timestamp)
        assert path.startswith('prod/')
    
    @patch.dict('os.environ', {'ENVIRONMENT': 'test'})
    def test_storage_config_test_env(self):
        """Test path generation for test environment"""
        project_id = "test-project"
        file_id = "test-file"
        timestamp = int(time.time())
        
        path = StorageConfig.get_file_path(project_id, file_id, timestamp)
        assert path.startswith('test/')
    
    @patch('app.services.storage_service.storage.Client')
    def test_storage_service_init(self, mock_client):
        """Test StorageService initialization"""
        mock_client_instance = Mock()
        mock_bucket = Mock()
        mock_client_instance.bucket.return_value = mock_bucket
        mock_client.return_value = mock_client_instance
        
        service = StorageService()
        
        assert service.client == mock_client_instance
        assert service.bucket == mock_bucket
        mock_client_instance.bucket.assert_called_once_with('probtp-poc-prod')
    
    @patch('app.services.storage_service.storage.Client')
    def test_generate_upload_url(self, mock_client):
        """Test signed upload URL generation"""
        # Setup mocks
        mock_client_instance = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()
        
        mock_client.return_value = mock_client_instance
        mock_client_instance.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        expected_url = "https://storage.googleapis.com/test-bucket/test-file?signed=true"
        mock_blob.generate_signed_url.return_value = expected_url
        
        # Test the service
        service = StorageService()
        url, path = service.generate_upload_url(
            project_id="test-project",
            file_id="test-file"
        )
        
        # Assertions
        assert url == expected_url
        assert "test-project" in path
        assert "test-file" in path
        assert path.endswith('.pdf')
        
        # Check that signed URL was called with correct parameters
        mock_blob.generate_signed_url.assert_called_once()
        call_args = mock_blob.generate_signed_url.call_args
        assert call_args[1]['method'] == 'PUT'
        assert call_args[1]['content_type'] == 'application/pdf'
    
    @patch('app.services.storage_service.storage.Client')
    def test_generate_download_url_file_exists(self, mock_client):
        """Test signed download URL generation for existing file"""
        # Setup mocks
        mock_client_instance = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()
        
        mock_client.return_value = mock_client_instance
        mock_client_instance.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        
        expected_url = "https://storage.googleapis.com/test-bucket/test-file?download=true"
        mock_blob.generate_signed_url.return_value = expected_url
        
        # Test the service
        service = StorageService()
        url = service.generate_download_url("test/path/file.pdf")
        
        # Assertions
        assert url == expected_url
        mock_blob.exists.assert_called_once()
        mock_blob.generate_signed_url.assert_called_once()
        call_args = mock_blob.generate_signed_url.call_args
        assert call_args[1]['method'] == 'GET'
    
    @patch('app.services.storage_service.storage.Client')
    def test_generate_download_url_file_not_exists(self, mock_client):
        """Test download URL generation for non-existent file"""
        # Setup mocks
        mock_client_instance = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()
        
        mock_client.return_value = mock_client_instance
        mock_client_instance.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = False
        
        # Test the service
        service = StorageService()
        
        with pytest.raises(FileNotFoundError) as exc_info:
            service.generate_download_url("test/path/nonexistent.pdf")
        
        assert "File not found" in str(exc_info.value)
        mock_blob.exists.assert_called_once()
    
    @patch('app.services.storage_service.storage.Client')
    def test_file_exists(self, mock_client):
        """Test file existence check"""
        # Setup mocks
        mock_client_instance = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()
        
        mock_client.return_value = mock_client_instance
        mock_client_instance.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService()
        
        # Test existing file
        mock_blob.exists.return_value = True
        assert service.file_exists("test/path/file.pdf") is True
        
        # Test non-existing file
        mock_blob.exists.return_value = False
        assert service.file_exists("test/path/nonexistent.pdf") is False
    
    @patch('app.services.storage_service.storage.Client')
    def test_delete_file_success(self, mock_client):
        """Test successful file deletion"""
        # Setup mocks
        mock_client_instance = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()
        
        mock_client.return_value = mock_client_instance
        mock_client_instance.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService()
        result = service.delete_file("test/path/file.pdf")
        
        assert result is True
        mock_blob.delete.assert_called_once()
    
    @patch('app.services.storage_service.storage.Client')
    def test_delete_file_not_found(self, mock_client):
        """Test file deletion when file doesn't exist"""
        from google.cloud.exceptions import NotFound
        
        # Setup mocks
        mock_client_instance = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()
        
        mock_client.return_value = mock_client_instance
        mock_client_instance.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.delete.side_effect = NotFound("File not found")
        
        service = StorageService()
        result = service.delete_file("test/path/nonexistent.pdf")
        
        assert result is False
        mock_blob.delete.assert_called_once()
