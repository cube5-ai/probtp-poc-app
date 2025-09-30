"""
Integration test for LlamaParse service parsing
This test MUST fail before implementation exists
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.services.parsing.adapters.llamaparse import LlamaParseAdapter

from app.models.parsing_configuration import ParsingConfiguration
from app.models.parsing_request import ParsingRequest


@pytest.fixture
def llamaparse_config():
    """Mock LlamaParse configuration"""
    return ParsingConfiguration(
        service_name="llamaparse",
        endpoint_url="https://api.llamaindex.ai/v1/parse",
        auth_type="api_key",
        credentials={"api_key": "test_key"},
        default_timeout=120,
        max_file_size=209715200,  # 200MB
        supported_formats=[".pdf", ".docx", ".pptx", ".xlsx"]
    )


@pytest.fixture
def parsing_request():
    """Mock parsing request"""
    return ParsingRequest(
        file_path="gs://test-bucket/documents/sample.pdf",
        service_name="llamaparse",
        timeout_seconds=120,
        options={}
    )


@pytest.mark.asyncio
async def test_llamaparse_adapter_initialization(llamaparse_config):
    """Test that LlamaParseAdapter can be initialized with config"""
    # This test will fail until adapter is implemented
    adapter = LlamaParseAdapter(llamaparse_config)
    assert adapter is not None
    assert adapter.config == llamaparse_config


@pytest.mark.asyncio
async def test_llamaparse_parse_document(llamaparse_config, parsing_request):
    """Test LlamaParse document parsing"""
    adapter = LlamaParseAdapter(llamaparse_config)

    # Mock the HTTP response (LlamaParse format)
    mock_response = {
        "job_id": "job_123456",
        "status": "completed",
        "pages": [
            {
                "page": 1,
                "text": "Document Title\n\nThis is the main content of the document.",
                "markdown": "# Document Title\n\nThis is the main content of the document.",
                "bbox": [0, 0, 612, 792]
            }
        ]
    }

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value=mock_response)
        mock_post.return_value.status_code = 200

        result = await adapter.parse_document(parsing_request)

        assert result is not None
        assert result.status == "completed"
        assert len(result.content_blocks) > 0
        assert result.content_blocks[0].content in mock_response["pages"][0]["text"]


@pytest.mark.asyncio
async def test_llamaparse_job_polling(llamaparse_config, parsing_request):
    """Test LlamaParse job polling mechanism"""
    adapter = LlamaParseAdapter(llamaparse_config)

    # Mock initial job submission
    initial_response = {
        "job_id": "job_123456",
        "status": "processing"
    }

    # Mock job completion
    completed_response = {
        "job_id": "job_123456",
        "status": "completed",
        "pages": [
            {
                "page": 1,
                "text": "Test content",
                "markdown": "Test content",
                "bbox": [0, 0, 612, 792]
            }
        ]
    }

    with patch('httpx.AsyncClient.post') as mock_post, \
         patch('httpx.AsyncClient.get') as mock_get:

        # Mock job submission
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value=initial_response)
        mock_post.return_value.status_code = 200

        # Mock job status check (first processing, then completed)
        mock_get.return_value = Mock()
        mock_get.return_value.json = AsyncMock(side_effect=[
            {"job_id": "job_123456", "status": "processing"},
            completed_response
        ])
        mock_get.return_value.status_code = 200

        result = await adapter.parse_document(parsing_request)

        assert result.status == "completed"
        assert len(result.content_blocks) > 0


@pytest.mark.asyncio
async def test_llamaparse_timeout_handling(llamaparse_config, parsing_request):
    """Test LlamaParse timeout handling"""
    adapter = LlamaParseAdapter(llamaparse_config)

    with patch('httpx.AsyncClient.post') as mock_post:
        # Simulate timeout
        mock_post.side_effect = TimeoutError("Request timeout")

        result = await adapter.parse_document(parsing_request)

        assert result.status == "timeout"
        assert "timeout" in result.error_message.lower()


@pytest.mark.asyncio
async def test_llamaparse_error_handling(llamaparse_config, parsing_request):
    """Test LlamaParse error handling"""
    adapter = LlamaParseAdapter(llamaparse_config)

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.status_code = 400
        mock_post.return_value.json = AsyncMock(return_value={"error": "Invalid API key"})

        result = await adapter.parse_document(parsing_request)

        assert result.status == "failed"
        assert "Invalid API key" in result.error_message


@pytest.mark.asyncio
async def test_llamaparse_markdown_to_blocks(llamaparse_config, parsing_request):
    """Test conversion from LlamaParse markdown to content blocks"""
    adapter = LlamaParseAdapter(llamaparse_config)

    # Mock response with structured markdown
    mock_response = {
        "job_id": "job_123456",
        "status": "completed",
        "pages": [
            {
                "page": 1,
                "text": "Document Title\nParagraph text\n• List item 1\n• List item 2",
                "markdown": "# Document Title\n\nParagraph text\n\n- List item 1\n- List item 2",
                "bbox": [0, 0, 612, 792]
            }
        ]
    }

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value=mock_response)
        mock_post.return_value.status_code = 200

        result = await adapter.parse_document(parsing_request)

        assert len(result.content_blocks) >= 3  # Title, paragraph, list

        # Should have different block types
        block_types = [block.block_type for block in result.content_blocks]
        assert "heading" in block_types
        assert "text" in block_types
        assert "list" in block_types


@pytest.mark.asyncio
async def test_llamaparse_large_document_handling(llamaparse_config, parsing_request):
    """Test LlamaParse handling of multi-page documents"""
    adapter = LlamaParseAdapter(llamaparse_config)

    # Mock response with multiple pages
    mock_response = {
        "job_id": "job_123456",
        "status": "completed",
        "pages": [
            {
                "page": 1,
                "text": "Page 1 content",
                "markdown": "# Page 1\n\nPage 1 content",
                "bbox": [0, 0, 612, 792]
            },
            {
                "page": 2,
                "text": "Page 2 content",
                "markdown": "# Page 2\n\nPage 2 content",
                "bbox": [0, 0, 612, 792]
            }
        ]
    }

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value=mock_response)
        mock_post.return_value.status_code = 200

        result = await adapter.parse_document(parsing_request)

        assert result.status == "completed"
        assert len(result.content_blocks) >= 2  # At least one block per page

        # Verify page numbers are set correctly
        page_numbers = [block.page_number for block in result.content_blocks]
        assert 1 in page_numbers
        assert 2 in page_numbers


@pytest.mark.asyncio
async def test_llamaparse_job_failure_handling(llamaparse_config, parsing_request):
    """Test LlamaParse job failure scenarios"""
    adapter = LlamaParseAdapter(llamaparse_config)

    # Mock job failure response
    failure_response = {
        "job_id": "job_123456",
        "status": "failed",
        "error": "Document parsing failed - unsupported format"
    }

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value=failure_response)
        mock_post.return_value.status_code = 200

        result = await adapter.parse_document(parsing_request)

        assert result.status == "failed"
        assert "unsupported format" in result.error_message.lower()