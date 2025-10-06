"""
Contract test for POST /api/v1/parsing/parse endpoint
This test MUST fail before implementation exists
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_parse_document_contract():
    """Test POST /api/v1/parsing/parse contract"""
    request_payload = {
        "file_path": "gs://test-bucket/documents/sample.pdf",
        "service_name": "mistral_ocr",
        "timeout_seconds": 60
    }

    response = client.post("/api/v1/parsing/parse", json=request_payload)

    # This test should fail initially since endpoint doesn't exist yet
    assert response.status_code == 200

    response_data = response.json()

    # Validate response schema matches ParsedDocument
    assert "document_id" in response_data
    assert "source_file_path" in response_data
    assert "parsing_service" in response_data
    assert "status" in response_data
    assert "created_at" in response_data
    assert "content_blocks" in response_data
    assert isinstance(response_data["content_blocks"], list)

    # Validate specific fields
    assert response_data["source_file_path"] == request_payload["file_path"]
    assert response_data["parsing_service"] == request_payload["service_name"]
    assert response_data["status"] in ["pending", "completed", "failed", "timeout"]


def test_parse_document_invalid_request():
    """Test POST /api/v1/parsing/parse with invalid request"""
    invalid_payload = {
        "file_path": "",  # Empty file path should be invalid
        "service_name": "invalid_service"
    }

    response = client.post("/api/v1/parsing/parse", json=invalid_payload)

    # Should return 400 for invalid request
    assert response.status_code == 400

    response_data = response.json()
    assert "error" in response_data
    assert "message" in response_data


def test_parse_document_timeout():
    """Test POST /api/v1/parsing/parse timeout behavior"""
    request_payload = {
        "file_path": "gs://test-bucket/documents/large.pdf",
        "service_name": "mistral_ocr",
        "timeout_seconds": 1  # Very short timeout to trigger timeout
    }

    response = client.post("/api/v1/parsing/parse", json=request_payload)

    # Should return 408 for timeout or 200 with timeout status
    assert response.status_code in [200, 408]

    if response.status_code == 200:
        response_data = response.json()
        assert response_data["status"] == "timeout"


def test_parse_document_unsupported_format():
    """Test POST /api/v1/parsing/parse with unsupported file format"""
    request_payload = {
        "file_path": "gs://test-bucket/documents/file.xlsx",  # Unsupported format
        "service_name": "mistral_ocr"
    }

    response = client.post("/api/v1/parsing/parse", json=request_payload)

    # Should return 422 for unsupported format
    assert response.status_code == 422

    response_data = response.json()
    assert "error" in response_data
    assert "message" in response_data
    assert "format" in response_data["message"].lower() or "supported" in response_data["message"].lower()