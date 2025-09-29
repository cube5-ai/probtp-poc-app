"""
Contract test for GET /api/v1/parsing/services endpoint
This test MUST fail before implementation exists
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_services_contract():
    """Test GET /api/v1/parsing/services contract"""
    response = client.get("/api/v1/parsing/services")

    # This test should fail initially since endpoint doesn't exist yet
    assert response.status_code == 200

    response_data = response.json()

    # Validate response schema
    assert "services" in response_data
    assert isinstance(response_data["services"], list)

    # Validate each service has required fields
    for service in response_data["services"]:
        assert "name" in service
        assert "status" in service
        assert "supported_formats" in service
        assert "max_file_size" in service
        assert "default_timeout" in service

        # Validate data types
        assert isinstance(service["name"], str)
        assert service["status"] in ["available", "unavailable"]
        assert isinstance(service["supported_formats"], list)
        assert isinstance(service["max_file_size"], int)
        assert isinstance(service["default_timeout"], int)

    # Should have at least the 3 configured services
    service_names = [s["name"] for s in response_data["services"]]
    expected_services = ["mistral_ocr", "unstructured", "llamaparse"]

    for expected_service in expected_services:
        assert expected_service in service_names


def test_get_services_includes_availability():
    """Test GET /api/v1/parsing/services includes service availability"""
    response = client.get("/api/v1/parsing/services")

    assert response.status_code == 200

    response_data = response.json()
    services = response_data["services"]

    # Each service should have a status
    for service in services:
        assert service["status"] in ["available", "unavailable"]


def test_get_services_includes_supported_formats():
    """Test GET /api/v1/parsing/services includes supported formats"""
    response = client.get("/api/v1/parsing/services")

    assert response.status_code == 200

    response_data = response.json()
    services = response_data["services"]

    # Each service should list supported formats
    for service in services:
        assert len(service["supported_formats"]) > 0
        # Common formats should be supported
        supported_formats = service["supported_formats"]
        assert isinstance(supported_formats, list)
        assert all(isinstance(fmt, str) for fmt in supported_formats)


def test_get_services_includes_limits():
    """Test GET /api/v1/parsing/services includes service limits"""
    response = client.get("/api/v1/parsing/services")

    assert response.status_code == 200

    response_data = response.json()
    services = response_data["services"]

    # Each service should have limits defined
    for service in services:
        assert service["max_file_size"] > 0
        assert service["default_timeout"] > 0
        # File size should be reasonable (not more than 500MB)
        assert service["max_file_size"] <= 524288000  # 500MB
        # Timeout should be reasonable (not more than 300 seconds)
        assert service["default_timeout"] <= 300


def test_get_services_no_auth_required():
    """Test GET /api/v1/parsing/services doesn't require authentication"""
    # This test verifies internal service can be accessed without auth
    response = client.get("/api/v1/parsing/services")

    # Should not return 401 or 403
    assert response.status_code != 401
    assert response.status_code != 403
    assert response.status_code == 200