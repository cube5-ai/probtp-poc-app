"""
Mistral OCR service adapter for document parsing
"""
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

from app.models.bounding_box import BoundingBox
from app.models.content_block import ContentBlock
from app.models.parsed_document import ParsedDocument
from app.models.parsing_configuration import ParsingConfiguration
from app.models.parsing_request import ParsingRequest
from app.services.parsing.adapters.base import (
    AuthenticationError,
    BaseParsingAdapter,
)

logger = logging.getLogger(__name__)


class MistralOCRAdapter(BaseParsingAdapter):
    """
    Mistral OCR service adapter for processing documents.

    Handles document parsing using Mistral's OCR API, converting
    their response format to our standardized ParsedDocument format.
    """

    def __init__(self, config: ParsingConfiguration):
        """Initialize the Mistral OCR adapter with configuration."""
        super().__init__(config)

    async def parse_document(self, request: ParsingRequest) -> ParsedDocument:
        """
        Parse a document using Mistral OCR service.

        Args:
            request: Parsing request containing file path and options

        Returns:
            ParsedDocument: Standardized parsing result
        """
        document_id = f"mistral_{uuid.uuid4().hex[:8]}"
        start_time = datetime.utcnow()

        # logger.info(f"Starting Mistral OCR parsing for {request.file_path}", extra={
        #     "document_id": document_id,
        #     "service": self.service_name,
        #     "file_path": request.file_path
        # })

        try:
            # Validate file format
            if not await self.validate_file(request):
                return self._create_error_document(
                    request,
                    "failed",
                    "Unsupported file format for Mistral OCR"
                )

            # Determine endpoint and payload based on whether we're calling Vertex AI rawPredict
            timeout = self._get_timeout(request)
            headers = self._get_auth_headers()

            endpoint = str(self.config.endpoint_url).rstrip("/")

            model_id = self.config.credentials.get("model_id", "mistral-ocr-2505")

            # Use the file_path directly - it should already be a valid HTTP(S) URL
            # The caller is responsible for providing accessible URLs
            document_url = request.options.get("document_data_url") or request.file_path

            # Validate that we have an HTTP(S) URL for the API
            if not (document_url.startswith("http://") or document_url.startswith("https://")):
                logger.error(f"Mistral OCR requires HTTP(S) URLs, got: {document_url}")
                return self._create_error_document(
                    request,
                    "failed",
                    f"Mistral OCR requires HTTP(S) URLs. Please provide a signed URL instead of: {document_url[:50]}..."
                )

            payload = {
                "model": model_id,
                "document": {
                    "type": "document_url",
                    "document_url": document_url,
                },
            }
            payload["include_image_base64"] = request.options.get("include_image_base64", True) # Default to True
            url = endpoint


            # Make the API request
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers
                )

                if response.status_code == 401:
                    raise AuthenticationError("Invalid API key for Mistral OCR")
                elif response.status_code == 413:
                    return self._create_error_document(
                        request,
                        "failed",
                        "File too large for Mistral OCR service"
                    )
                elif response.status_code not in [200, 201]:
                    error_data = {}
                    try:
                        error_data = response.json()
                    except Exception:
                        pass

                    error_msg = error_data.get("error", f"HTTP {response.status_code}")
                    return self._create_error_document(
                        request,
                        "failed",
                        f"Mistral OCR API error: {error_msg}"
                    )

                # Parse successful response
                response_data = response.json()
                return await self._convert_response_to_document(
                    response_data,
                    request,
                    document_id,
                    start_time
                )

        except (TimeoutError, httpx.TimeoutException):
            logger.warning(f"Mistral OCR timeout for {request.file_path}", extra={
                "document_id": document_id,
                "timeout": timeout
            })
            return self._create_error_document(
                request,
                "timeout",
                f"Mistral OCR request timed out after {timeout} seconds"
            )

        except AuthenticationError:
            logger.error("Mistral OCR authentication failed", extra={
                "document_id": document_id
            })
            return self._create_error_document(
                request,
                "failed",
                "Authentication failed - invalid API key"
            )

        except Exception as e:
            logger.error(f"Mistral OCR parsing error for {request.file_path}: {e}", extra={
                "document_id": document_id,
                "error": str(e)
            })
            return self._create_error_document(
                request,
                "failed",
                f"Mistral OCR parsing failed: {str(e)}"
            )

    async def _convert_response_to_document(
        self,
        response_data: dict[str, Any],
        request: ParsingRequest,
        document_id: str,
        start_time: datetime
    ) -> ParsedDocument:
        """
        Convert Mistral OCR API response to ParsedDocument format.

        Args:
            response_data: Raw API response from Mistral OCR
            request: Original parsing request
            document_id: Generated document ID
            start_time: When parsing started

        Returns:
            ParsedDocument with converted content blocks
        """
        try:
            content_blocks = []
            total_images = 0

            # Handle the actual Mistral OCR response format with pages
            if "pages" in response_data:
                for i, page_data in enumerate(response_data.get("pages", [])):
                    page_index = page_data.get("index", i) # Default to order in the response
                    page_number = page_index + 1  # Mistral OCR uses 0-based indexing

                    # Track block position within the page
                    block_position = 0

                    # Create content blocks for the page markdown content
                    markdown_content = page_data.get("markdown", "")
                    if markdown_content:
                        # Split markdown into logical sections preserving structure
                        sections = self._split_markdown_sections(markdown_content)

                        for section_content in sections:
                            if section_content.strip():
                                # Determine block type based on content
                                block_type = self._determine_block_type(section_content)

                                # For image references in markdown, extract the image info
                                import re
                                image_match = re.match(r'^!\[([^\]]*?)\]\(([^\)]+)\)', section_content)

                                if image_match and block_type == "image":
                                    # This is an image reference - try to match with image data
                                    img_id = image_match.group(2)  # Get the image filename

                                    # Find corresponding image data
                                    image_data = None
                                    for img in page_data.get("images", []):
                                        if img.get("id") == img_id:
                                            image_data = img
                                            break

                                    if image_data:
                                        # Create enhanced image block with actual data
                                        image_block = await self._create_image_block(
                                            image_data,
                                            document_id,
                                            page_number,
                                            block_position
                                        )
                                        if image_block:
                                            # Use neutral block ID based on position
                                            image_block.block_id = f"{document_id}_p{page_number}_b{block_position}"
                                            image_block.position = block_position
                                            content_blocks.append(image_block)
                                            block_position += 1
                                            continue

                                # Regular content block
                                content_blocks.append(ContentBlock(
                                    block_id=f"{document_id}_p{page_number}_b{block_position}",
                                    block_type=block_type,
                                    content=section_content,
                                    page_number=page_number,
                                    position=block_position,
                                    confidence_score=None,  # Mistral OCR doesn't provide confidence scores
                                    metadata={
                                        "dimensions": page_data.get("dimensions", {})
                                    }
                                ))
                                block_position += 1

                    # Count total images (they're already handled above in markdown)
                    images = page_data.get("images", [])
                    total_images += len(images)

            # Extract metadata including usage info
            usage_info = response_data.get("usage_info", {})
            metadata = {
                "service": self.service_name,
                "model": response_data.get("model", "mistral-ocr-2505"),
                "processing_time_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "total_blocks": len(content_blocks),
                "total_pages": usage_info.get("pages_processed", len(response_data.get("pages", []))),
                "total_images": total_images,
                "document_size_bytes": usage_info.get("doc_size_bytes"),
                **request.options.get("metadata", {})
            }

            return ParsedDocument(
                document_id=document_id,
                source_file_path=request.file_path,
                parsing_service=self.service_name,
                status="completed",
                created_at=start_time,
                completed_at=datetime.utcnow(),
                content_blocks=content_blocks,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Error converting Mistral OCR response: {e}")
            return self._create_error_document(
                request,
                "failed",
                f"Failed to convert Mistral OCR response: {str(e)}"
            )

    def _split_markdown_sections(self, markdown: str) -> list[str]:
        """
        Split markdown content into logical sections.

        Splits on:
        - Headers (# ## ### etc.)
        - Images (![...](...))
        - Tables
        - Lists
        - Significant paragraph breaks (2+ newlines)

        Args:
            markdown: Raw markdown text

        Returns:
            List of markdown sections preserving document structure
        """
        import re

        sections = []
        current_section = []

        lines = markdown.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check if this line starts a new logical section
            is_header = re.match(r'^#+\s', line)
            is_image = re.match(r'^!\[.*?\]\(.*?\)', line)
            is_table_start = '|' in line and line.count('|') >= 3
            is_list_start = re.match(r'^[*\-+]\s', line) or re.match(r'^\d+\.\s', line)

            # Decide if we should start a new section
            should_split = False

            if is_header or is_image:
                should_split = True
            elif is_table_start:
                # Look ahead to see if this is really a table
                if i + 1 < len(lines) and '|' in lines[i + 1] and '-' in lines[i + 1]:
                    should_split = True
            elif is_list_start and current_section and not re.match(r'^[*\-+\d]', '\n'.join(current_section)):
                # Start new section for lists unless we're already in a list
                should_split = True
            elif line.strip() == '' and current_section:
                # Check if we have multiple blank lines (paragraph break)
                if i + 1 < len(lines) and lines[i + 1].strip() == '':
                    should_split = True

            if should_split and current_section:
                # Save the current section
                content = '\n'.join(current_section).strip()
                if content:
                    sections.append(content)
                current_section = []

            # Handle special cases
            if is_image:
                # Images get their own section
                if current_section:
                    content = '\n'.join(current_section).strip()
                    if content:
                        sections.append(content)
                    current_section = []
                sections.append(line)
            elif is_table_start:
                # Collect the entire table
                if current_section:
                    content = '\n'.join(current_section).strip()
                    if content:
                        sections.append(content)
                    current_section = []

                table_lines = [line]
                i += 1
                while i < len(lines) and '|' in lines[i]:
                    table_lines.append(lines[i])
                    i += 1
                sections.append('\n'.join(table_lines))
                i -= 1  # Adjust because we'll increment at the end of the loop
            elif is_list_start:
                # Collect the entire list
                if current_section and not re.match(r'^[*\-+\d]', '\n'.join(current_section)):
                    content = '\n'.join(current_section).strip()
                    if content:
                        sections.append(content)
                    current_section = []

                current_section.append(line)
                # Continue collecting list items
                i += 1
                while i < len(lines):
                    if re.match(r'^[*\-+]\s', lines[i]) or re.match(r'^\d+\.\s', lines[i]) or (lines[i].strip() and lines[i].startswith('  ')):
                        current_section.append(lines[i])
                        i += 1
                    elif lines[i].strip() == '':
                        # Allow one blank line within lists
                        current_section.append(lines[i])
                        i += 1
                        if i < len(lines) and lines[i].strip() == '':
                            # Two blank lines end the list
                            break
                    else:
                        break
                i -= 1  # Adjust because we'll increment at the end of the loop
            else:
                # Regular line - add to current section
                if line.strip() or current_section:  # Don't start sections with blank lines
                    current_section.append(line)

            i += 1

        # Don't forget the last section
        if current_section:
            content = '\n'.join(current_section).strip()
            if content:
                sections.append(content)

        # If no sections were created, return the whole content
        if not sections:
            sections = [markdown.strip()] if markdown.strip() else []

        return sections

    def _determine_block_type(self, content: str) -> str:
        """
        Determine the block type based on markdown content.

        Args:
            content: Markdown content

        Returns:
            Block type string
        """
        import re

        content_lower = content.lower().strip()

        # Check for headers
        if re.match(r'^#+\s', content):
            return "heading"

        # Check for tables (markdown tables with |)
        if '|' in content and content.count('|') >= 3:
            lines = content.split('\n')
            table_lines = [l for l in lines if '|' in l]
            if len(table_lines) >= 2:  # At least header and separator
                return "table"

        # Check for lists
        if re.match(r'^[*\-+]\s', content) or re.match(r'^\d+\.\s', content):
            return "list"

        # Check for images
        if re.search(r'!\[.*?\]\(.*?\)', content):
            return "image"

        # Default to text
        return "text"

    async def _create_image_block(
        self,
        image_data: dict[str, Any],
        document_id: str,
        page_number: int,
        block_position: int
    ) -> ContentBlock | None:
        """
        Create an image ContentBlock from Mistral OCR image data.

        Args:
            image_data: Image information from Mistral OCR
            document_id: Document ID
            page_number: Page number
            block_position: Position of this block within the page

        Returns:
            ContentBlock for the image or None if creation fails
        """
        try:
            # Calculate normalized bounding box coordinates
            # Mistral provides absolute pixel coordinates
            bounding_box = None
            if all(k in image_data for k in ["top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y"]):
                # We'd need page dimensions to normalize, but for now store absolute values
                width = image_data["bottom_right_x"] - image_data["top_left_x"]
                height = image_data["bottom_right_y"] - image_data["top_left_y"]

                bounding_box = BoundingBox(
                    x=float(image_data["top_left_x"]),
                    y=float(image_data["top_left_y"]),
                    width=float(width),
                    height=float(height)
                )

            return ContentBlock(
                block_id=f"{document_id}_p{page_number}_b{block_position}",
                block_type="image",
                content=image_data.get("id", f"image_{block_position}"),  # Store image ID as content
                page_number=page_number,
                position=block_position,
                bounding_box=bounding_box,
                confidence_score=None,
                metadata={
                    "image_id": image_data.get("id"),
                    "image_base64": image_data.get("image_base64", "")[:100] + "..." if image_data.get("image_base64") else None,
                    "has_base64": bool(image_data.get("image_base64")),
                    "coordinates": {
                        "top_left_x": image_data.get("top_left_x"),
                        "top_left_y": image_data.get("top_left_y"),
                        "bottom_right_x": image_data.get("bottom_right_x"),
                        "bottom_right_y": image_data.get("bottom_right_y")
                    }
                }
            )

        except Exception as e:
            logger.warning(f"Failed to create image block from Mistral OCR data: {e}")
            return None

    def _get_auth_headers(self) -> dict[str, str]:
        """
        Get authentication headers for Mistral OCR API, delegating to base for
        api_key, bearer, or service account (Vertex AI) modes.

        Returns:
            Dict with authentication headers
        """
        headers = super()._get_auth_headers()
        headers.setdefault("Content-Type", "application/json")
        return headers
