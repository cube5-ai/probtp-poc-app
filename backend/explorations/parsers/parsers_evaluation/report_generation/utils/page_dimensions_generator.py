"""
Page dimensions generator for PDF documents.

Extracts page dimensions from PDF files using PyMuPDF and caches them
for use in bounding box coordinate conversion.
"""

import json
from pathlib import Path
import pymupdf


def extract_page_dimensions(pdf_path: str | Path) -> dict[int, dict[str, float]]:
    """
    Extract page dimensions from a PDF file.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dictionary mapping page numbers to dimensions:
        {
            0: {"width": 612.0, "height": 792.0},
            1: {"width": 612.0, "height": 792.0},
            ...
        }
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    dimensions = {}

    with pymupdf.open(pdf_path) as doc:
        for page_num in range(len(doc)):
            page = doc[page_num]
            dimensions[page_num] = {
                "width": page.rect.width,
                "height": page.rect.height
            }

    return dimensions


def generate_page_dimensions_cache(
    pdf_paths: dict[str, str | Path],
    output_path: str | Path
) -> dict[str, dict[int, dict[str, float]]]:
    """
    Generate page dimensions cache for multiple PDF files.

    Args:
        pdf_paths: Dictionary mapping file_id to PDF path
                  e.g., {"File #1 - ...": "/path/to/file.pdf"}
        output_path: Path to save the cache JSON file

    Returns:
        Dictionary mapping file_id to page dimensions
    """
    cache = {}

    for file_id, pdf_path in pdf_paths.items():
        print(f"Extracting dimensions for: {file_id}")
        try:
            dimensions = extract_page_dimensions(pdf_path)
            cache[file_id] = dimensions
            print(f"  → {len(dimensions)} pages extracted")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue

    # Save cache
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"\nCache saved to: {output_path}")
    return cache


def load_page_dimensions_cache(cache_path: str | Path) -> dict[str, dict[int, dict[str, float]]]:
    """
    Load page dimensions cache from JSON file.

    Args:
        cache_path: Path to cache JSON file

    Returns:
        Dictionary mapping file_id to page dimensions
    """
    with open(cache_path, 'r', encoding='utf-8') as f:
        cache = json.load(f)

    # Convert page numbers back to integers (JSON keys are strings)
    normalized_cache = {}
    for file_id, pages in cache.items():
        normalized_cache[file_id] = {
            int(page_num): dims
            for page_num, dims in pages.items()
        }

    return normalized_cache


def get_page_dimensions(
    cache: dict[str, dict[int, dict[str, float]]],
    file_id: str,
    page: int
) -> dict[str, float] | None:
    """
    Get page dimensions from cache.

    Args:
        cache: Page dimensions cache
        file_id: Document file ID
        page: Page number

    Returns:
        Dictionary with width and height, or None if not found
    """
    if file_id not in cache:
        return None

    if page not in cache[file_id]:
        return None

    return cache[file_id][page]
