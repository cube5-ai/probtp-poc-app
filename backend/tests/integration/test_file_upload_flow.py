"""
Integration tests for file upload flow
"""
import uuid
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestFileUploadFlow:
    """Integration tests for complete file upload workflow"""
    
    @pytest.fixture
    def mock_firebase_auth(self):
        """Mock Firebase authentication"""
        with patch('app.api.deps.FirebaseAuthService.verify_id_token') as mock_verify:
            mock_verify.return_value = {
                'user_id': 'test-user-123',
                'email': 'test@example.com',
                'email_verified': True,
                'name': 'Test User',
                'roles': ['editor'],
                'firebase_claims': {}
            }
            yield mock_verify
    
    @pytest.fixture
    def mock_storage_service(self):
        """Mock storage service"""
        with patch('app.services.storage_service.StorageService') as mock_service:
            mock_instance = Mock()
            mock_service.return_value = mock_instance
            
            # Mock generate_upload_url
            mock_instance.generate_upload_url.return_value = (
                "https://storage.googleapis.com/test-bucket/signed-url",
                "dev/projects/test-project/files/test-file_123456.pdf"
            )
            
            # Mock generate_download_url
            mock_instance.generate_download_url.return_value = (
                "https://storage.googleapis.com/test-bucket/download-url"
            )
            
            # Mock file operations
            mock_instance.file_exists.return_value = True
            mock_instance.delete_file.return_value = True
            
            yield mock_instance
    
    @pytest.fixture
    def mock_database(self):
        """Mock database operations"""
        with patch('app.api.deps.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            # Mock authorization check
            with patch('app.services.auth_service.AuthorizationService.can_upload_file') as mock_can_upload:
                mock_can_upload.return_value = True
                
                # Mock project query
                mock_project = Mock()
                mock_project.id = "test-project-123"
                mock_db.query.return_value.filter.return_value.first.return_value = mock_project
                
                yield mock_db
    
    def test_file_upload_initialization(self, mock_firebase_auth, mock_storage_service, mock_database):
        """Test file upload initialization endpoint"""
        headers = {"Authorization": "Bearer fake-token"}
        payload = {
            "filename": "test-document.pdf",
            "file_size": 1024000  # 1MB
        }
        
        with patch('app.services.auth_service.AuthorizationService.can_upload_file', return_value=True):
            response = client.post(
                "/api/v1/projects/test-project-123/files/upload",
                json=payload,
                headers=headers
            )
        
        # Should succeed with mocked auth and storage
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "upload_id" in data
        assert "upload_url" in data
        assert "upload_method" in data
        assert "expires_at" in data
        assert "max_file_size" in data
        
        assert data["upload_method"] == "PUT"
        assert data["max_file_size"] == 104857600  # 100MB
    
    def test_file_upload_invalid_file_type(self, mock_firebase_auth):
        """Test file upload with invalid file type"""
        headers = {"Authorization": "Bearer fake-token"}
        payload = {
            "filename": "test-document.txt",  # Not a PDF
            "file_size": 1024000
        }
        
        response = client.post(
            "/api/v1/projects/test-project-123/files/upload",
            json=payload,
            headers=headers
        )
        
        # Should fail validation
        assert response.status_code == 422
    
    def test_file_upload_too_large(self, mock_firebase_auth):
        """Test file upload with file too large"""
        headers = {"Authorization": "Bearer fake-token"}
        payload = {
            "filename": "test-document.pdf",
            "file_size": 200 * 1024 * 1024  # 200MB, exceeds 100MB limit
        }
        
        response = client.post(
            "/api/v1/projects/test-project-123/files/upload",
            json=payload,
            headers=headers
        )
        
        # Should fail validation
        assert response.status_code == 422
    
    def test_unauthorized_access(self):
        """Test access without authentication"""
        payload = {
            "filename": "test-document.pdf",
            "file_size": 1024000
        }
        
        response = client.post(
            "/api/v1/projects/test-project-123/files/upload",
            json=payload
            # No Authorization header
        )
        
        # Should fail authentication
        assert response.status_code == 403
    
    def test_file_status_endpoint(self, mock_firebase_auth, mock_database):
        """Test file status endpoint"""
        headers = {"Authorization": "Bearer fake-token"}
        
        # Mock file record
        mock_file = Mock()
        mock_file.id = str(uuid.uuid4())
        mock_file.status = 'ready'
        mock_file.updated_at = "2024-01-01T00:00:00Z"
        mock_file.error_message = None
        
        with patch('app.services.auth_service.AuthorizationService.can_view_file', return_value=True):
            mock_database.query.return_value.filter.return_value.first.return_value = mock_file
            
            response = client.get(
                f"/api/v1/files/{mock_file.id}/status",
                headers=headers
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ready"
        assert data["progress"] == 100
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "probtp-poc-api"
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "ProBTP POC API"
        assert data["version"] == "1.0.0"
        assert data["docs"] == "/docs"
