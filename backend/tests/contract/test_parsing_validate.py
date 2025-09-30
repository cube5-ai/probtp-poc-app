"""
Contract test for POST /api/v1/parsing/validate endpoint
This test MUST fail before implementation exists
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_validate_file_contract():
    """Test POST /api/v1/parsing/validate contract"""
    request_payload = {
        "file_path": "gs://test-bucket/documents/sample.pdf",
        "service_name": "mistral_ocr"
    }

    response = client.post("/api/v1/parsing/validate", json=request_payload)

    # This test should fail initially since endpoint doesn't exist yet
    assert response.status_code == 200

    response_data = response.json()

    # Validate response schema
    assert "valid" in response_data
    assert "file_size" in response_data
    assert "format" in response_data
    assert "estimated_pages" in response_data
    assert "errors" in response_data

    # Validate data types
    assert isinstance(response_data["valid"], bool)
    assert isinstance(response_data["file_size"], int)
    assert isinstance(response_data["format"], str)
    assert isinstance(response_data["estimated_pages"], int)
    assert isinstance(response_data["errors"], list)


def test_validate_file_invalid_path():
    """Test POST /api/v1/parsing/validate with invalid file path"""
    request_payload = {
        "file_path": "invalid://path/to/file.pdf",
        "service_name": "mistral_ocr"
    }

    response = client.post("/api/v1/parsing/validate", json=request_payload)

    assert response.status_code == 200

    response_data = response.json()
    assert response_data["valid"] is False
    assert len(response_data["errors"]) > 0
    assert "path" in response_data["errors"][0].lower() or "file" in response_data["errors"][0].lower()


def test_validate_file_unsupported_service():
    """Test POST /api/v1/parsing/validate with unsupported service"""
    request_payload = {
        "file_path": "gs://test-bucket/documents/sample.pdf",
        "service_name": "nonexistent_service"
    }

    response = client.post("/api/v1/parsing/validate", json=request_payload)

    # Should return 400 for invalid service
    assert response.status_code == 400

    response_data = response.json()
    assert "error" in response_data
    assert "service" in response_data["message"].lower()


def test_validate_file_large_size():
    """Test POST /api/v1/parsing/validate with oversized file"""
    request_payload = {
        "file_path": "gs://test-bucket/documents/huge_file.pdf",  # Assume this is >100MB
        "service_name": "mistral_ocr"
    }

    response = client.post("/api/v1/parsing/validate", json=request_payload)

    assert response.status_code == 200

    response_data = response.json()
    # Should be invalid due to size limit
    if response_data["file_size"] > 104857600:  # 100MB
        assert response_data["valid"] is False
        assert any("size" in error.lower() for error in response_data["errors"])


def test_validate_file_missing_fields():
    """Test POST /api/v1/parsing/validate with missing required fields"""
    request_payload = {
        "file_path": "gs://test-bucket/documents/sample.pdf"
        # Missing service_name
    }

    response = client.post("/api/v1/parsing/validate", json=request_payload)

    # Should return 422 for missing required field
    assert response.status_code == 422