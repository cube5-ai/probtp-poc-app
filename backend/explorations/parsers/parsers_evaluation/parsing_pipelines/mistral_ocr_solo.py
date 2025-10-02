"""
Mistral OCR parsing functions for document processing
Provides simple functions similar to extend_solo.py but adapted for Mistral OCR via Vertex AI
"""
import base64
import json
import os
import re
from typing import Any, Optional

import requests
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2 import service_account

load_dotenv()

# Environment variables for GCP configuration
REGION = os.getenv("REGION", "us-central1")
PROJECT_ID = os.getenv("PROJECT_ID", "probtp-poc-prod")
MODEL_ID = os.getenv("MODEL_ID", "mistral-ocr-2505")
SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "backend-sa-key.json")

print(f"REGION: {REGION}")
print(f"PROJECT_ID: {PROJECT_ID}")
print(f"MODEL_ID: {MODEL_ID}")
print(f"SERVICE_ACCOUNT_PATH: {SERVICE_ACCOUNT_PATH}")


def get_gcp_access_token() -> str:
    """
    Get GCP access token using service account credentials
    """
    try:
        # Load service account credentials
        if not os.path.exists(SERVICE_ACCOUNT_PATH):
            raise Exception(f"Service account file not found: {SERVICE_ACCOUNT_PATH}")

        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_PATH,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )

        # Get access token
        request = Request()
        credentials.refresh(request)

        if not credentials.token:
            raise Exception("Failed to obtain access token from service account")

        return credentials.token

    except Exception as e:
        raise Exception(f"Error getting GCP access token: {str(e)}") from e


def encode_file_to_base64(file_path: str) -> str:
    """
    Encode a file to base64 string
    """
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            base64_string = base64.b64encode(file_bytes).decode('utf-8')
            return base64_string
    except Exception as e:
        raise Exception(f"Error encoding file to base64: {str(e)}") from e


def upload_file_as_base64(file_path: str) -> str:
    """
    Convert file to base64 data URL for Mistral OCR
    Returns a data URL that can be used directly with Mistral OCR
    """
    try:
        # Determine MIME type based on file extension
        file_extension = os.path.splitext(file_path)[1].lower()
        mime_type_map = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg'
        }

        mime_type = mime_type_map.get(file_extension, 'application/octet-stream')

        # Encode file to base64
        base64_content = encode_file_to_base64(file_path)

        # Create data URL
        data_url = f"data:{mime_type};base64,{base64_content}"

        return data_url
    except Exception as e:
        print(f"Error creating base64 data URL: {str(e)}")
        return ""

def parse_document(file_path: str, include_image_base64: bool = True, pages: str | None = None) -> dict[str, Any]:
    """
    Parse a document using Mistral OCR via Vertex AI

    Args:
        file_path: Path to the document file
        include_image_base64: Whether to include base64 encoded images in response
        pages: Specific pages to process (e.g., "0", "0-2", "1,3,5")

    Returns:
        Dict containing the Mistral OCR response
    """
    try:
        # Validate required configuration
        if not PROJECT_ID:
            raise Exception("PROJECT_ID is required")

        # Get access token
        access_token = get_gcp_access_token()

        # Convert file to base64 data URL
        document_data_url = upload_file_as_base64(file_path)

        # Construct Vertex AI endpoint URL
        url = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/publishers/mistralai/models/{MODEL_ID}:rawPredict"

        # Prepare payload
        payload = {
            "model": MODEL_ID,
            "document": {
                "type": "document_url",
                "document_url": document_data_url
            },
            "include_image_base64": include_image_base64
        }

        # Add pages parameter if specified
        if pages is not None:
            payload["pages"] = pages

        # Prepare headers
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Make the request
        response = requests.post(
            url=url,
            headers=headers,
            json=payload,
            timeout=120  # 2 minute timeout for large documents
        )
        # Handle response

        if response.status_code == 200:
            try:
                response_dict = response.json()
                return response_dict
            except json.JSONDecodeError as e:
                raise Exception(f"Error decoding JSON response: {e}") from e
        else:
            error_msg = f"Request failed with status code: {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f", Details: {error_detail}"
            except Exception:
                error_msg += f", Response: {response.text}"
            raise Exception(error_msg)

    except Exception as e:
        raise Exception(f"Error parsing document with Mistral OCR: {str(e)}") from e


def parse_document_from_url(document_url: str, include_image_base64: bool = True, pages: str | None = None) -> dict[str, Any]:
    """
    Parse a document from URL using Mistral OCR via Vertex AI

    Args:
        document_url: HTTP(S) URL to the document
        include_image_base64: Whether to include base64 encoded images in response
        pages: Specific pages to process (e.g., "0", "0-2", "1,3,5")

    Returns:
        Dict containing the Mistral OCR response
    """
    try:
        # Validate required configuration
        if not PROJECT_ID:
            raise Exception("PROJECT_ID is required")

        # Get access token
        access_token = get_gcp_access_token()

        # Construct Vertex AI endpoint URL
        url = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/publishers/mistralai/models/{MODEL_ID}:rawPredict"

        # Prepare payload
        payload = {
            "model": MODEL_ID,
            "document": {
                "type": "document_url",
                "document_url": document_url
            },
            "include_image_base64": include_image_base64
        }

        # Add pages parameter if specified
        if pages is not None:
            payload["pages"] = pages

        # Prepare headers
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Make the request
        response = requests.post(
            url=url,
            headers=headers,
            json=payload,
            timeout=120  # 2 minute timeout for large documents
        )

        # Handle response
        if response.status_code == 200:
            try:
                response_dict = response.json()
                return response_dict
            except json.JSONDecodeError as e:
                raise Exception(f"Error decoding JSON response: {e}") from e
        else:
            error_msg = f"Request failed with status code: {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f", Details: {error_detail}"
            except Exception:
                error_msg += f", Response: {response.text}"
            raise Exception(error_msg)

    except Exception as e:
        raise Exception(f"Error parsing document from URL with Mistral OCR: {str(e)}") from e


def clean_empty_markdown_tables(content: str) -> str:
    """
    Remove empty markdown table patterns with 3 or more consecutive rows of only empty cells.

    Args:
        content: Raw markdown content

    Returns:
        Cleaned markdown content with empty table patterns removed
    """
    # Pattern to match empty markdown table rows: |   |  |  |  |   |
    # This regex matches:
    # - Line starts with |
    # - Contains only spaces, | characters, and optional whitespace
    # - Ends with | and optional whitespace
    empty_row_pattern = r'^\|\s*(?:\|\s*)*\|\s*$'

    lines = content.split('\n')
    cleaned_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if current line matches empty table row pattern
        if re.match(empty_row_pattern, line.strip()):
            # Count consecutive empty table rows
            empty_row_count = 0
            j = i

            # Count how many consecutive empty rows we have
            while j < len(lines) and re.match(empty_row_pattern, lines[j].strip()):
                empty_row_count += 1
                j += 1

            # If we have 3 or more consecutive empty rows, skip them
            if empty_row_count >= 3:
                i = j  # Skip all the empty rows
                continue

        # Keep the line if it's not part of a long empty table sequence
        cleaned_lines.append(line)
        i += 1

    return '\n'.join(cleaned_lines)


def write_to_markdown(response: dict[str, Any], file_path: str) -> None:
    """
    Convert the Mistral OCR response to markdown file

    Args:
        response: Mistral OCR API response dictionary
        file_path: Output path for the markdown file
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            # Write header with document metadata
            model = response.get("model", "mistral-ocr-2505")
            usage_info = response.get("usage_info", {})
            pages_processed = usage_info.get("pages_processed", 0)
            doc_size = usage_info.get("doc_size_bytes")

            f.write(f"# Document Parsed with {model}\n\n")
            f.write(f"**Pages processed:** {pages_processed}\n")
            if doc_size:
                f.write(f"**Document size:** {doc_size:,} bytes\n")
            f.write("\n---\n\n")

            # Process each page
            pages = response.get("pages", [])
            for page_data in pages:
                page_index = page_data.get("index", 0)
                page_number = page_index + 1  # Convert 0-based to 1-based

                # Write page header
                f.write(f"## Page {page_number}\n\n")

                # Add page dimensions if available
                dimensions = page_data.get("dimensions", {})
                if dimensions:
                    dpi = dimensions.get("dpi", "unknown")
                    height = dimensions.get("height", "unknown")
                    width = dimensions.get("width", "unknown")
                    f.write(f"*Page dimensions: {width}x{height} pixels @ {dpi} DPI*\n\n")

                # Write markdown content (cleaned of empty table patterns)
                markdown_content = page_data.get("markdown", "")
                if markdown_content:
                    # Clean up empty markdown table patterns before writing
                    cleaned_content = clean_empty_markdown_tables(markdown_content)
                    f.write(cleaned_content)

                    # Ensure proper spacing after content
                    if not cleaned_content.endswith("\n\n"):
                        if cleaned_content.endswith("\n"):
                            f.write("\n")
                        else:
                            f.write("\n\n")

                # Add image information if present
                images = page_data.get("images", [])
                if images:
                    f.write(f"\n### Images on Page {page_number}\n\n")
                    for i, img in enumerate(images, 1):
                        img_id = img.get("id", f"image_{i}")
                        coords = f"({img.get('top_left_x', 0)}, {img.get('top_left_y', 0)}) to ({img.get('bottom_right_x', 0)}, {img.get('bottom_right_y', 0)})"
                        has_base64 = "✅" if img.get("image_base64") else "❌"
                        f.write(f"- **{img_id}**: {coords} - Base64 data: {has_base64}\n")
                    f.write("\n")

                # Add page separator
                f.write("---\n\n")

    except Exception as e:
        raise Exception(f"Error writing markdown file: {str(e)}") from e


def get_document_info(response: dict[str, Any]) -> dict[str, Any]:
    """
    Extract summary information from Mistral OCR response

    Args:
        response: Mistral OCR API response dictionary

    Returns:
        Dict with document information summary
    """
    try:
        pages = response.get("pages", [])
        usage_info = response.get("usage_info", {})

        total_characters = 0
        total_images = 0
        page_count = len(pages)

        for page_data in pages:
            markdown_content = page_data.get("markdown", "")
            total_characters += len(markdown_content)

            images = page_data.get("images", [])
            total_images += len(images)

        return {
            "model": response.get("model", "mistral-ocr-2505"),
            "pages_processed": usage_info.get("pages_processed", page_count),
            "doc_size_bytes": usage_info.get("doc_size_bytes"),
            "total_pages": page_count,
            "total_characters": total_characters,
            "total_images": total_images,
            "pages_with_images": len([p for p in pages if p.get("images")]),
            "average_chars_per_page": total_characters / page_count if page_count > 0 else 0
        }

    except Exception as e:
        raise Exception(f"Error extracting document info: {str(e)}") from e


# Example usage and testing function
def test_mistral_ocr_parsing(file_path: str, output_dir: str = "./output") -> None:
    """
    Test function to demonstrate Mistral OCR parsing workflow

    Args:
        file_path: Path to the document to parse
        output_dir: Directory to save output files
    """
    try:
        import os
        os.makedirs(output_dir, exist_ok=True)

        print(f"🔍 Parsing document: {file_path}")

        # Parse the document
        response = parse_document(file_path, include_image_base64=True)

        # Get document info
        doc_info = get_document_info(response)
        print("✅ Parsing completed!")
        print(f"   Model: {doc_info['model']}")
        print(f"   Pages: {doc_info['total_pages']}")
        print(f"   Characters: {doc_info['total_characters']:,}")
        print(f"   Images: {doc_info['total_images']}")

        # Save raw response
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        json_output = os.path.join(output_dir, f"{base_name}_response.json")
        with open(json_output, "w", encoding="utf-8") as f:
            json.dump(response, f, indent=2, ensure_ascii=False)
        print(f"💾 Raw response saved: {json_output}")

        # Save markdown
        md_output = os.path.join(output_dir, f"{base_name}.md")
        write_to_markdown(response, md_output)
        print(f"📝 Markdown saved: {md_output}")


    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        raise


def test_empty_table_cleaning() -> None:
    """Test the empty markdown table cleaning functionality"""
    test_content = """# Test Document

Some regular content here.

|   |  |  |  |   |
|   |  |  |  |   |
|   |  |  |  |   |
|   |  |  |  |   |
|   |  |  |  |   |

More content here.

| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |

Final content.

|   |  |  |  |  |  |   |
|   |  |  |  |  |  |   |

Only 2 empty rows above - should be kept.
"""

    print("🧪 Testing empty table cleaning...")
    print("Original content:")
    print("-" * 40)
    print(test_content)

    cleaned = clean_empty_markdown_tables(test_content)
    print("\nCleaned content:")
    print("-" * 40)
    print(cleaned)

    # Count removed lines
    original_lines = len(test_content.split('\n'))
    cleaned_lines = len(cleaned.split('\n'))
    removed_lines = original_lines - cleaned_lines

    print(f"\n📊 Results:")
    print(f"   Original lines: {original_lines}")
    print(f"   Cleaned lines: {cleaned_lines}")
    print(f"   Removed lines: {removed_lines}")


if __name__ == "__main__":
    # Example usage
    print("Mistral OCR Solo - Document Parsing Functions")
    print("=" * 50)

    # Test empty table cleaning
    test_empty_table_cleaning()
    print("\n" + "=" * 50)

    # Test with a sample file (replace with your file path)
    sample_file = "sample_document.pdf"
    if os.path.exists(sample_file):
        test_mistral_ocr_parsing(sample_file)
    else:
        print(f"Sample file {sample_file!r} not found.")
        print("Update the file path in the script to test with your own document.")
