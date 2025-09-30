"""
Integration test for parsing service switching
This test MUST fail before implementation exists
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.parsing_configuration import ParsingConfiguration
from app.models.parsing_request import ParsingRequest
from app.services.parsing.service import ParsingService


@pytest.fixture
def mock_configs():
    """Mock configurations for all services"""
    return {
        "mistral_ocr": ParsingConfiguration(
            service_name="mistral_ocr",
            endpoint_url="https://api.mistral-ocr.com/v1",
            auth_type="api_key",
            credentials={"api_key": "mistral_key"},
            default_timeout=60,
            max_file_size=104857600,
            supported_formats=["pdf", "png", "jpg", "jpeg"]
        ),
        "unstructured": ParsingConfiguration(
            service_name="unstructured",
            endpoint_url="https://api.unstructured.io/general/v0",
            auth_type="api_key",
            credentials={"api_key": "unstructured_key"},
            default_timeout=45,
            max_file_size=52428800,
            supported_formats=["pdf", "docx", "txt", "html"]
        ),
        "llamaparse": ParsingConfiguration(
            service_name="llamaparse",
            endpoint_url="https://api.llamaindex.ai/v1/parse",
            auth_type="api_key",
            credentials={"api_key": "llama_key"},
            default_timeout=120,
            max_file_size=209715200,
            supported_formats=["pdf", "docx", "pptx", "xlsx"]
        )
    }


@pytest.fixture
def parsing_service(mock_configs):
    """Mock parsing service with all adapters configured"""
    return ParsingService(mock_configs)


@pytest.mark.asyncio
async def test_parsing_service_initialization(mock_configs):
    """Test that ParsingService can be initialized with multiple adapters"""
    # This test will fail until service is implemented
    service = ParsingService(mock_configs)
    assert service is not None
    assert len(service.adapters) == 3
    assert "mistral_ocr" in service.adapters
    assert "unstructured" in service.adapters
    assert "llamaparse" in service.adapters


@pytest.mark.asyncio
async def test_service_switching_mistral_ocr(parsing_service):
    """Test switching to Mistral OCR service"""
    request = ParsingRequest(
        file_path="gs://test-bucket/documents/sample.pdf",
        service_name="mistral_ocr",
        timeout_seconds=60,
        options={}
    )

    # Mock Mistral OCR response
    mock_response = {
        "document_id": "mistral_doc_123",
        "status": "completed",
        "content_blocks": [
            {
                "block_id": "block_1",
                "block_type": "text",
                "content": "Mistral OCR parsed content",
                "page_number": 1,
                "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.1},
                "confidence_score": 0.95
            }
        ]
    }

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value=mock_response)
        mock_post.return_value.status_code = 200

        result = await parsing_service.parse_document(request)

        assert result is not None
        assert result.document_id == "mistral_doc_123"
        assert result.status == "completed"
        assert len(result.content_blocks) == 1
        assert "Mistral OCR" in result.content_blocks[0].content


@pytest.mark.asyncio
async def test_service_switching_unstructured(parsing_service):
    """Test switching to Unstructured.io service"""
    request = ParsingRequest(
        file_path="gs://test-bucket/documents/sample.pdf",
        service_name="unstructured",
        timeout_seconds=45,
        options={}
    )

    # Mock Unstructured.io response
    mock_response = [
        {
            "element_id": "unstructured_block_1",
            "type": "NarrativeText",
            "text": "Unstructured.io parsed content",
            "metadata": {
                "page_number": 1,
                "coordinates": {"points": [(100, 100), (500, 100), (500, 150), (100, 150)]}
            }
        }
    ]

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value=mock_response)
        mock_post.return_value.status_code = 200

        result = await parsing_service.parse_document(request)

        assert result is not None
        assert result.status == "completed"
        assert len(result.content_blocks) == 1
        assert "Unstructured.io" in result.content_blocks[0].content
        assert result.content_blocks[0].block_type == "text"


@pytest.mark.asyncio
async def test_service_switching_llamaparse(parsing_service):
    """Test switching to LlamaParse service"""
    request = ParsingRequest(
        file_path="gs://test-bucket/documents/sample.pdf",
        service_name="llamaparse",
        timeout_seconds=120,
        options={}
    )

    # Mock LlamaParse response
    mock_response = {
        "job_id": "llama_job_123",
        "status": "completed",
        "pages": [
            {
                "page": 1,
                "text": "LlamaParse parsed content",
                "markdown": "# LlamaParse parsed content",
                "bbox": [0, 0, 612, 792]
            }
        ]
    }

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value=mock_response)
        mock_post.return_value.status_code = 200

        result = await parsing_service.parse_document(request)

        assert result is not None
        assert result.status == "completed"
        assert len(result.content_blocks) > 0
        assert any("LlamaParse" in block.content for block in result.content_blocks)


@pytest.mark.asyncio
async def test_invalid_service_name(parsing_service):
    """Test handling of invalid service name"""
    request = ParsingRequest(
        file_path="gs://test-bucket/documents/sample.pdf",
        service_name="nonexistent_service",
        timeout_seconds=60,
        options={}
    )

    with pytest.raises(ValueError) as exc_info:
        await parsing_service.parse_document(request)

    assert "nonexistent_service" in str(exc_info.value)
    assert "not supported" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_service_fallback_on_failure(parsing_service):
    """Test automatic fallback when primary service fails"""
    request = ParsingRequest(
        file_path="gs://test-bucket/documents/sample.pdf",
        service_name="mistral_ocr",
        timeout_seconds=60,
        options={"enable_fallback": True, "fallback_services": ["unstructured"]}
    )

    # Mock Mistral OCR failure
    mistral_error_response = {"error": "Service unavailable"}

    # Mock Unstructured.io success
    unstructured_success_response = [
        {
            "element_id": "fallback_block_1",
            "type": "NarrativeText",
            "text": "Fallback service parsed content",
            "metadata": {"page_number": 1}
        }
    ]

    with patch('httpx.AsyncClient.post') as mock_post:
        # First call (Mistral) fails, second call (Unstructured) succeeds
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(side_effect=[
            mistral_error_response,
            unstructured_success_response
        ])
        mock_post.return_value.status_code = Mock(side_effect=[500, 200])

        result = await parsing_service.parse_document(request)

        assert result is not None
        assert result.status == "completed"
        assert len(result.content_blocks) == 1
        assert "Fallback service" in result.content_blocks[0].content


@pytest.mark.asyncio
async def test_service_availability_check(parsing_service):
    """Test checking service availability before parsing"""
    # Mock health check responses
    health_responses = {
        "mistral_ocr": {"status": "available", "response_time": 150},
        "unstructured": {"status": "unavailable", "error": "Rate limit exceeded"},
        "llamaparse": {"status": "available", "response_time": 300}
    }

    with patch.object(parsing_service, 'check_service_health') as mock_health:
        mock_health.return_value = AsyncMock(side_effect=lambda service: health_responses[service])

        available_services = await parsing_service.get_available_services()

        assert "mistral_ocr" in available_services
        assert "llamaparse" in available_services
        assert "unstructured" not in available_services


@pytest.mark.asyncio
async def test_concurrent_parsing_requests(parsing_service):
    """Test handling multiple concurrent parsing requests"""
    requests = [
        ParsingRequest(
            file_path=f"gs://test-bucket/documents/sample{i}.pdf",
            service_name="mistral_ocr" if i % 2 == 0 else "unstructured",
            timeout_seconds=60,
            options={}
        )
        for i in range(5)
    ]

    # Mock responses for both services
    mistral_response = {
        "document_id": "concurrent_mistral",
        "status": "completed",
        "content_blocks": [{"block_id": "b1", "block_type": "text", "content": "Mistral content"}]
    }

    unstructured_response = [{
        "element_id": "concurrent_unstructured",
        "type": "NarrativeText",
        "text": "Unstructured content"
    }]

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(side_effect=[
            mistral_response, unstructured_response, mistral_response,
            unstructured_response, mistral_response
        ])
        mock_post.return_value.status_code = 200

        import asyncio
        results = await asyncio.gather(*[
            parsing_service.parse_document(req) for req in requests
        ])

        assert len(results) == 5
        assert all(result.status == "completed" for result in results)


@pytest.mark.asyncio
async def test_service_configuration_validation(mock_configs):
    """Test validation of service configurations"""
    # Test with invalid configuration
    invalid_config = mock_configs.copy()
    invalid_config["mistral_ocr"].endpoint_url = ""

    with pytest.raises(ValueError) as exc_info:
        ParsingService(invalid_config)

    assert "endpoint_url" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_service_timeout_differences(parsing_service):
    """Test that different services respect their timeout settings"""
    # Short timeout request
    short_timeout_request = ParsingRequest(
        file_path="gs://test-bucket/documents/sample.pdf",
        service_name="unstructured",  # 45s default
        timeout_seconds=30,
        options={}
    )

    # Long timeout request
    long_timeout_request = ParsingRequest(
        file_path="gs://test-bucket/documents/sample.pdf",
        service_name="llamaparse",  # 120s default
        timeout_seconds=150,
        options={}
    )

    with patch('httpx.AsyncClient.post') as mock_post:
        # Simulate timeout for short request
        mock_post.side_effect = [TimeoutError("Request timeout"), Mock()]

        # Short timeout should fail
        result1 = await parsing_service.parse_document(short_timeout_request)
        assert result1.status == "timeout"

        # Reset mock for long timeout test
        mock_post.side_effect = None
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value={"job_id": "test", "status": "completed", "pages": []})
        mock_post.return_value.status_code = 200

        result2 = await parsing_service.parse_document(long_timeout_request)
        assert result2.status == "completed"