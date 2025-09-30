import pymupdf4llm
import pymupdf
from pathlib import Path

from .pymupdf_lock import pymupdf_lock



def parse_document(file_path: str) -> dict:
    """
    Parse a document using pymupdf4llm
    Returns a dict with parsed content and metadata
    Thread-safe: uses shared global lock to prevent concurrent calls to pymupdf4llm.
    """
    try:

        # Use pymupdf4llm to extract markdown-formatted text (thread-safe)
        with pymupdf_lock:
            markdown_result = pymupdf4llm.to_markdown(
                file_path,
                page_chunks=True,  # Preserve page boundaries
                write_images=False,  # Don't extract images to disk
                image_size_limit=0,  # Skip image extraction
                table_strategy="lines_strict",  # Better table detection
            )

        # Process the result based on return type
        chunks = []
        if isinstance(markdown_result, list):
            # When page_chunks=True, returns list of dicts with metadata
            for i, chunk in enumerate(markdown_result, 1):
                if isinstance(chunk, dict):
                    chunks.append({
                        "type": "page",
                        "content": chunk.get('text', ''),
                        "metadata": {
                            "pageRange": {
                                "start": i
                            }
                        }
                    })
                else:
                    chunks.append({
                        "type": "page", 
                        "content": str(chunk),
                        "metadata": {
                            "pageRange": {
                                "start": i
                            }
                        }
                    })
        else:
            # Single document without page chunks
            chunks.append({
                "type": "document",
                "content": str(markdown_result),
                "metadata": {}
            })

        return {
            "chunks": chunks,
            "metadata": {
                "source": file_path,
                "parser": "pymupdf4llm",
                "pymupdf_version": pymupdf.version[0]
            }
        }

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return {
            "chunks": [],
            "metadata": {
                "source": file_path,
                "parser": "pymupdf4llm",
                "error": str(e)
            }
        }


def write_to_markdown(response: dict, file_path: str):
    """
    Convert the pymupdf4llm response to markdown file
    """
    try:
        with open(file_path, "w", encoding='utf-8') as f:
            # Write chunks
            for chunk in response.get("chunks", []):
                if chunk.get("type") == "page":
                    page_num = chunk.get('metadata', {}).get('pageRange', {}).get('start', 1)
                    f.write(f"---\n*Page {page_num}*\n---\n\n")

                content = chunk.get("content", "")
                if content:
                    f.write(content)
                    f.write("\n\n")

    except Exception as e:
        print(f"Error writing markdown to {file_path}: {e}")
