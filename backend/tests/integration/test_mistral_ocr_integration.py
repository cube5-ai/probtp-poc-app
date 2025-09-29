"""
Integration test for Mistral OCR service parsing
This test MUST fail before implementation exists
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.parsing_configuration import ParsingConfiguration
from app.models.parsing_request import ParsingRequest
from app.services.parsing.adapters.mistral_ocr import MistralOCRAdapter


@pytest.fixture
def mistral_config():
    """Mock Mistral OCR configuration"""
    return ParsingConfiguration(
        service_name="mistral_ocr",
        endpoint_url="https://api.mistral-ocr.com/v1",
        auth_type="api_key",
        credentials={"api_key": "test_key"},
        default_timeout=60,
        max_file_size=104857600,  # 100MB
        supported_formats=[".pdf", ".png", ".jpg", ".jpeg"]
    )


@pytest.fixture
def parsing_request():
    """Mock parsing request"""
    return ParsingRequest(
        file_path="gs://test-bucket/documents/sample.pdf",
        service_name="mistral_ocr",
        timeout_seconds=60,
        options={}
    )


@pytest.mark.asyncio
async def test_mistral_ocr_adapter_initialization(mistral_config):
    """Test that MistralOCRAdapter can be initialized with config"""
    # This test will fail until adapter is implemented
    adapter = MistralOCRAdapter(mistral_config)
    assert adapter is not None
    assert adapter.config == mistral_config


@pytest.mark.asyncio
async def test_mistral_ocr_parse_document(mistral_config, parsing_request):
    """Test Mistral OCR document parsing"""
    adapter = MistralOCRAdapter(mistral_config)

    # Mock the HTTP response
    mock_response = {
        "document_id": "test_doc_123",
        "status": "completed",
        "content_blocks": [
            {
                "block_id": "block_1",
                "block_type": "text",
                "content": "Sample text content",
                "page_number": 1,
                "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.1},
                "confidence_score": 0.95
            }
        ]
    }

    with patch('httpx.AsyncClient') as mock_client:
        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.status_code = 200

        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post = AsyncMock(return_value=mock_response_obj)

        result = await adapter.parse_document(parsing_request)

        assert result is not None
        assert result.document_id == "test_doc_123"
        assert result.status == "completed"
        assert len(result.content_blocks) == 1
        assert result.content_blocks[0].content == "Sample text content"


@pytest.mark.asyncio
async def test_mistral_ocr_timeout_handling(mistral_config, parsing_request):
    """Test Mistral OCR timeout handling"""
    adapter = MistralOCRAdapter(mistral_config)

    # Set short timeout for test
    parsing_request.timeout_seconds = 1

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post = AsyncMock(side_effect=TimeoutError("Request timeout"))

        result = await adapter.parse_document(parsing_request)

        assert result.status == "timeout"
        assert "timeout" in result.error_message.lower() or "timed out" in result.error_message.lower()


@pytest.mark.asyncio
async def test_mistral_ocr_error_handling(mistral_config, parsing_request):
    """Test Mistral OCR error handling"""
    adapter = MistralOCRAdapter(mistral_config)

    with patch('httpx.AsyncClient') as mock_client:
        mock_response_obj = Mock()
        mock_response_obj.status_code = 400
        mock_response_obj.json.return_value = {"error": "Invalid file format"}

        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post = AsyncMock(return_value=mock_response_obj)

        result = await adapter.parse_document(parsing_request)

        assert result.status == "failed"
        assert "Invalid file format" in result.error_message


@pytest.mark.asyncio
async def test_mistral_ocr_file_validation(mistral_config):
    """Test Mistral OCR file validation"""
    adapter = MistralOCRAdapter(mistral_config)

    # Valid file
    valid_request = ParsingRequest(
        file_path="gs://test-bucket/documents/sample.pdf",
        service_name="mistral_ocr"
    )

    is_valid = await adapter.validate_file(valid_request)
    assert is_valid is True

    # Invalid file format (supported by system but not by mistral_ocr)
    invalid_request = ParsingRequest(
        file_path="gs://test-bucket/documents/sample.webp",
        service_name="mistral_ocr"
    )

    is_valid = await adapter.validate_file(invalid_request)
    assert is_valid is False


@pytest.mark.asyncio
async def test_mistral_ocr_authentication(mistral_config, parsing_request):
    """Test Mistral OCR authentication header"""
    adapter = MistralOCRAdapter(mistral_config)

    with patch('httpx.AsyncClient') as mock_client:
        mock_response_obj = Mock()
        mock_response_obj.json.return_value = {"status": "completed"}
        mock_response_obj.status_code = 200

        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post = AsyncMock(return_value=mock_response_obj)

        await adapter.parse_document(parsing_request)

        # Verify authentication header was included
        call_args = mock_instance.post.call_args
        headers = call_args[1].get('headers', {})
        assert 'Authorization' in headers or 'X-API-Key' in headers