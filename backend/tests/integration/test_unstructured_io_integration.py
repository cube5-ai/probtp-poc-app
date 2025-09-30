"""
Integration test for Unstructured.io service parsing
This test MUST fail before implementation exists
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.services.parsing.adapters.unstructured_io import UnstructuredIOAdapter

from app.models.parsing_configuration import ParsingConfiguration
from app.models.parsing_request import ParsingRequest


@pytest.fixture
def unstructured_config():
    """Mock Unstructured.io configuration"""
    return ParsingConfiguration(
        service_name="unstructured",
        endpoint_url="https://api.unstructured.io/general/v0",
        auth_type="api_key",
        credentials={"api_key": "test_key"},
        default_timeout=45,
        max_file_size=52428800,  # 50MB
        supported_formats=[".pdf", ".docx", ".txt", ".html"]
    )


@pytest.fixture
def parsing_request():
    """Mock parsing request"""
    return ParsingRequest(
        file_path="gs://test-bucket/documents/sample.pdf",
        service_name="unstructured",
        timeout_seconds=45,
        options={}
    )


@pytest.mark.asyncio
async def test_unstructured_adapter_initialization(unstructured_config):
    """Test that UnstructuredIOAdapter can be initialized with config"""
    # This test will fail until adapter is implemented
    adapter = UnstructuredIOAdapter(unstructured_config)
    assert adapter is not None
    assert adapter.config == unstructured_config


@pytest.mark.asyncio
async def test_unstructured_parse_document(unstructured_config, parsing_request):
    """Test Unstructured.io document parsing"""
    adapter = UnstructuredIOAdapter(unstructured_config)

    # Mock the HTTP response (Unstructured.io format)
    mock_response = [
        {
            "element_id": "block_1",
            "type": "Title",
            "text": "Document Title",
            "metadata": {
                "page_number": 1,
                "coordinates": {"points": [(100, 100), (500, 100), (500, 150), (100, 150)]}
            }
        },
        {
            "element_id": "block_2",
            "type": "NarrativeText",
            "text": "This is the main content of the document.",
            "metadata": {
                "page_number": 1,
                "coordinates": {"points": [(100, 200), (500, 200), (500, 400), (100, 400)]}
            }
        }
    ]

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value=mock_response)
        mock_post.return_value.status_code = 200

        result = await adapter.parse_document(parsing_request)

        assert result is not None
        assert result.status == "completed"
        assert len(result.content_blocks) == 2
        assert result.content_blocks[0].content == "Document Title"
        assert result.content_blocks[0].block_type == "heading"
        assert result.content_blocks[1].content == "This is the main content of the document."
        assert result.content_blocks[1].block_type == "text"


@pytest.mark.asyncio
async def test_unstructured_timeout_handling(unstructured_config, parsing_request):
    """Test Unstructured.io timeout handling"""
    adapter = UnstructuredIOAdapter(unstructured_config)

    with patch('httpx.AsyncClient.post') as mock_post:
        # Simulate timeout
        mock_post.side_effect = TimeoutError("Request timeout")

        result = await adapter.parse_document(parsing_request)

        assert result.status == "timeout"
        assert "timeout" in result.error_message.lower()


@pytest.mark.asyncio
async def test_unstructured_error_handling(unstructured_config, parsing_request):
    """Test Unstructured.io error handling"""
    adapter = UnstructuredIOAdapter(unstructured_config)

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.status_code = 422
        mock_post.return_value.json = AsyncMock(return_value={"detail": "File format not supported"})

        result = await adapter.parse_document(parsing_request)

        assert result.status == "failed"
        assert "File format not supported" in result.error_message


@pytest.mark.asyncio
async def test_unstructured_coordinate_conversion(unstructured_config, parsing_request):
    """Test coordinate conversion from Unstructured.io format to normalized bounding boxes"""
    adapter = UnstructuredIOAdapter(unstructured_config)

    # Mock response with coordinates
    mock_response = [
        {
            "element_id": "block_1",
            "type": "NarrativeText",
            "text": "Test content",
            "metadata": {
                "page_number": 1,
                "coordinates": {"points": [(0, 0), (612, 0), (612, 100), (0, 100)]}  # PDF points
            }
        }
    ]

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value=mock_response)
        mock_post.return_value.status_code = 200

        result = await adapter.parse_document(parsing_request)

        assert len(result.content_blocks) == 1
        block = result.content_blocks[0]

        # Should have bounding box with normalized coordinates (0.0-1.0)
        assert block.bounding_box is not None
        assert 0.0 <= block.bounding_box.x <= 1.0
        assert 0.0 <= block.bounding_box.y <= 1.0
        assert 0.0 <= block.bounding_box.width <= 1.0
        assert 0.0 <= block.bounding_box.height <= 1.0


@pytest.mark.asyncio
async def test_unstructured_element_type_mapping(unstructured_config, parsing_request):
    """Test mapping of Unstructured.io element types to standardized block types"""
    adapter = UnstructuredIOAdapter(unstructured_config)

    # Mock response with various element types
    mock_response = [
        {"element_id": "1", "type": "Title", "text": "Title text"},
        {"element_id": "2", "type": "Header", "text": "Header text"},
        {"element_id": "3", "type": "NarrativeText", "text": "Narrative text"},
        {"element_id": "4", "type": "Table", "text": "Table content"},
        {"element_id": "5", "type": "ListItem", "text": "List item"},
        {"element_id": "6", "type": "Image", "text": "Image description"}
    ]

    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = Mock()
        mock_post.return_value.json = AsyncMock(return_value=mock_response)
        mock_post.return_value.status_code = 200

        result = await adapter.parse_document(parsing_request)

        assert len(result.content_blocks) == 6

        # Verify type mappings
        block_types = [block.block_type for block in result.content_blocks]
        expected_types = ["heading", "heading", "text", "table", "list", "image"]
        assert block_types == expected_types