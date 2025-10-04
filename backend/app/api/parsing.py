"""
Parsing API endpoints
Provides HTTP endpoints for document parsing operations
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.models.parsed_document import ParsedDocument
from app.models.parsing_request import ParsingRequest
from app.services.parsing.service import ParsingService
from app.services.parsing.validation import FileValidationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/parsing", tags=["parsing"])


# Global service instances (initialized by dependency injection)
_parsing_service: ParsingService = None
_validation_service: FileValidationService = None


def get_parsing_service() -> ParsingService:
    """Dependency injection for parsing service."""
    global _parsing_service
    if _parsing_service is None:
        settings = get_settings()
        configs = settings.get_parsing_service_configs()

        # For testing: if no configs (no API keys), create mock configs
        if not configs and settings.environment == "development":
            from app.models.parsing_configuration import ParsingConfiguration
            configs = {
                "mistral_ocr": ParsingConfiguration(
                    service_name="mistral_ocr",
                    endpoint_url="https://api.mistral-ocr.com/v1",
                    auth_type="api_key",
                    credentials={"api_key": "test_key"},
                    default_timeout=60,
                    max_file_size=104857600,
                    supported_formats=[".pdf", ".png", ".jpg", ".jpeg"]
                ),
                "unstructured": ParsingConfiguration(
                    service_name="unstructured",
                    endpoint_url="https://api.unstructured.io/general/v0",
                    auth_type="api_key",
                    credentials={"api_key": "test_key"},
                    default_timeout=45,
                    max_file_size=52428800,
                    supported_formats=[".pdf", ".docx", ".txt", ".html"]
                ),
                "llamaparse": ParsingConfiguration(
                    service_name="llamaparse",
                    endpoint_url="https://api.llamaindex.ai/v1/parse",
                    auth_type="api_key",
                    credentials={"api_key": "test_key"},
                    default_timeout=120,
                    max_file_size=209715200,
                    supported_formats=[".pdf", ".docx", ".pptx", ".xlsx"]
                )
            }

        _parsing_service = ParsingService(configs)
    return _parsing_service


def get_validation_service() -> FileValidationService:
    """Dependency injection for validation service."""
    global _validation_service
    if _validation_service is None:
        _validation_service = FileValidationService()
    return _validation_service


# Request/Response models for API endpoints
class ParseRequest(ParsedDocument):
    """Request model for parse endpoint (inherits from ParsingRequest)"""
    pass


class ValidateRequest(ParsingRequest):
    """Request model for validate endpoint (inherits from ParsingRequest)"""
    pass


class ParseResponse(ParsedDocument):
    """Response model for parse endpoint (inherits from ParsedDocument)"""
    pass


class ValidateResponse:
    """Response model for validate endpoint"""
    def __init__(self, **data):
        self.valid = data.get("valid", False)
        self.file_size = data.get("file_size", 0)
        self.format = data.get("format", "")
        self.estimated_pages = data.get("estimated_pages", 1)
        self.errors = data.get("errors", [])


class ServicesResponse:
    """Response model for services endpoint"""
    def __init__(self, services: list[dict[str, Any]]):
        self.services = services


# API Endpoints


@router.post(
    "/parse",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Parse a document",
    description="Parse a document using the specified parsing service and return structured content blocks"
)
async def parse_document(
    request: dict[str, Any],
    parsing_service: ParsingService = Depends(get_parsing_service)
) -> JSONResponse:
    """
    Parse a document using the specified parsing service.

    Args:
        request: Parsing request with file_path, service_name, and options
        parsing_service: Injected parsing service instance

    Returns:
        JSONResponse: Parsed document with content blocks and metadata

    Raises:
        HTTPException: For invalid requests or service errors
    """
    try:
        # Validate and create parsing request
        parsing_request = ParsingRequest(**request)

        # logger.info("Received parse request", extra={
        #     "file_path": parsing_request.file_path,
        #     "service": parsing_request.service_name,
        #     "timeout": parsing_request.timeout_seconds
        # })

        # Parse the document
        result = await parsing_service.parse_document(parsing_request)

        # Convert to dictionary for JSON response
        response_data = {
            "document_id": result.document_id,
            "source_file_path": result.source_file_path,
            "parsing_service": result.parsing_service,
            "status": result.status,
            "created_at": result.created_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "content_blocks": [
                {
                    "block_id": block.block_id,
                    "block_type": block.block_type,
                    "content": block.content,
                    "page_number": block.page_number,
                    "bounding_box": {
                        "x": block.bounding_box.x,
                        "y": block.bounding_box.y,
                        "width": block.bounding_box.width,
                        "height": block.bounding_box.height
                    } if block.bounding_box else None,
                    "confidence_score": block.confidence_score,
                    "metadata": block.metadata
                }
                for block in result.content_blocks
            ],
            "metadata": result.metadata,
            "error_message": result.error_message
        }

        # logger.info("Parse request completed", extra={
        #     "document_id": result.document_id,
        #     "status": result.status,
        #     "blocks_count": len(result.content_blocks)
        # })

        return JSONResponse(content=response_data, status_code=status.HTTP_200_OK)

    except ValueError as e:
        logger.error(f"Invalid parse request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Parse request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parsing failed: {str(e)}"
        )


@router.post(
    "/validate",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Validate a file for parsing",
    description="Validate if a file can be processed by the specified parsing service"
)
async def validate_file(
    request: dict[str, Any],
    parsing_service: ParsingService = Depends(get_parsing_service),
    validation_service: FileValidationService = Depends(get_validation_service)
) -> JSONResponse:
    """
    Validate if a file can be processed by the specified parsing service.

    Args:
        request: Validation request with file_path and service_name
        parsing_service: Injected parsing service instance
        validation_service: Injected validation service instance

    Returns:
        JSONResponse: Validation results with file info and errors

    Raises:
        HTTPException: For invalid service names or validation errors
    """
    try:
        # Validate and create parsing request
        parsing_request = ParsingRequest(**request)

        # logger.info("Received validate request", extra={
        #     "file_path": parsing_request.file_path,
        #     "service": parsing_request.service_name
        # })

        # Check if service exists
        service_config = parsing_service.get_service_config(parsing_request.service_name)
        if not service_config:
            available_services = list(parsing_service.adapters.keys())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid service",
                    "message": f"Service '{parsing_request.service_name}' not supported. Available services: {available_services}"
                }
            )

        # Perform comprehensive validation
        result = await validation_service.validate_file(parsing_request, service_config)

        # logger.info("Validate request completed", extra={
        #     "file_path": parsing_request.file_path,
        #     "service": parsing_request.service_name,
        #     "valid": result["valid"]
        # })

        return JSONResponse(content=result, status_code=status.HTTP_200_OK)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except ValueError as e:
        logger.error(f"Invalid validate request: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid request format: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Validate request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        )


@router.get(
    "/services",
    response_model=dict[str, list[dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="Get available parsing services",
    description="Get list of available parsing services with their status and capabilities"
)
async def get_parsing_services(
    parsing_service: ParsingService = Depends(get_parsing_service)
) -> JSONResponse:
    """
    Get list of available parsing services with their status and capabilities.

    Args:
        parsing_service: Injected parsing service instance

    Returns:
        JSONResponse: List of services with status and capabilities

    Raises:
        HTTPException: For service errors
    """
    try:
        # logger.info("Received get services request")

        # Get service availability
        services = await parsing_service.get_available_services()

        response_data = {"services": services}

        # logger.info("Get services request completed", extra={
        #     "services_count": len(services),
        #     "available_count": sum(1 for s in services if s["status"] == "available")
        # })

        return JSONResponse(content=response_data, status_code=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Get services request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get services: {str(e)}"
        )


# Health check endpoint for the parsing service itself
@router.get(
    "/health",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Check parsing service health",
    description="Check the health status of the parsing service and its dependencies"
)
async def check_parsing_health(
    parsing_service: ParsingService = Depends(get_parsing_service)
) -> JSONResponse:
    """
    Check the health status of the parsing service and its dependencies.

    Args:
        parsing_service: Injected parsing service instance

    Returns:
        JSONResponse: Health status information
    """
    try:
        # logger.info("Received health check request")

        health_data = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",  # Would use datetime.now() in real implementation
            "services": {},
            "summary": {
                "total_services": 0,
                "available_services": 0,
                "unavailable_services": 0
            }
        }

        # Check each service health
        for service_name in parsing_service.adapters.keys():
            try:
                service_health = await parsing_service.check_service_health(service_name)
                health_data["services"][service_name] = service_health

                if service_health.get("status") == "available":
                    health_data["summary"]["available_services"] += 1
                else:
                    health_data["summary"]["unavailable_services"] += 1

            except Exception as e:
                logger.warning(f"Health check failed for {service_name}: {e}")
                health_data["services"][service_name] = {
                    "status": "unavailable",
                    "error": str(e)
                }
                health_data["summary"]["unavailable_services"] += 1

        health_data["summary"]["total_services"] = len(parsing_service.adapters)

        # Overall status based on available services
        if health_data["summary"]["available_services"] == 0:
            health_data["status"] = "unhealthy"
        elif health_data["summary"]["unavailable_services"] > 0:
            health_data["status"] = "degraded"

        # logger.info("Health check completed", extra={
        #     "status": health_data["status"],
        #     "available_services": health_data["summary"]["available_services"],
        #     "total_services": health_data["summary"]["total_services"]
        # })

        return JSONResponse(content=health_data, status_code=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "2024-01-01T00:00:00Z"
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
