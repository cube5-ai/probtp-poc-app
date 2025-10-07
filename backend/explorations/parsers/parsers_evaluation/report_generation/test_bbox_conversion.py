"""
Test script for bounding box conversion to react-pdf-highlighter format.
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.page_dimensions_generator import (
    extract_page_dimensions,
)
from utils.bounding_box_converter import (
    convert_bbox_to_absolute,
    convert_bounding_box_entry,
)


def test_page_dimensions_extraction():
    """Test extracting page dimensions from PDF."""
    print("=" * 80)
    print("TEST 1: Extract Page Dimensions")
    print("=" * 80)

    # Test with ProBTP document
    pdf_path = Path(__file__).parent.parent / "documents" / "File #3 - Panorama FMC 2025.pdf"

    if not pdf_path.exists():
        print(f"✗ PDF not found: {pdf_path}")
        return False

    try:
        dimensions = extract_page_dimensions(pdf_path)
        print(f"✓ Extracted dimensions for {len(dimensions)} pages")

        # Show first 3 pages
        for page_num in range(min(3, len(dimensions))):
            dims = dimensions[page_num]
            print(f"  Page {page_num}: {dims['width']:.2f} x {dims['height']:.2f} points")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_bbox_conversion():
    """Test converting bounding box from relative to absolute coordinates."""
    print("\n" + "=" * 80)
    print("TEST 2: Convert Bounding Box Coordinates")
    print("=" * 80)

    # Sample relative bounding box (from Landing AI)
    relative_bbox = {
        "left": 0.556,
        "right": 0.746,
        "top": 0.198,
        "bottom": 0.354
    }

    # Sample page dimensions (typical A4 page in points)
    page_width = 612.0  # 8.5 inches * 72 points/inch
    page_height = 792.0  # 11 inches * 72 points/inch

    print(f"Input (relative):")
    print(f"  left={relative_bbox['left']}, right={relative_bbox['right']}")
    print(f"  top={relative_bbox['top']}, bottom={relative_bbox['bottom']}")
    print(f"\nPage dimensions: {page_width} x {page_height} points")

    try:
        absolute_bbox = convert_bbox_to_absolute(relative_bbox, page_width, page_height)

        print(f"\nOutput (absolute, react-pdf-highlighter format):")
        print(f"  x1={absolute_bbox['x1']:.2f}, y1={absolute_bbox['y1']:.2f}")
        print(f"  x2={absolute_bbox['x2']:.2f}, y2={absolute_bbox['y2']:.2f}")
        print(f"  width={absolute_bbox['width']:.2f}, height={absolute_bbox['height']:.2f}")

        # Verify conversion
        assert absolute_bbox['x1'] == relative_bbox['left'] * page_width
        assert absolute_bbox['y1'] == relative_bbox['top'] * page_height
        assert absolute_bbox['x2'] == relative_bbox['right'] * page_width
        assert absolute_bbox['y2'] == relative_bbox['bottom'] * page_height
        assert absolute_bbox['width'] == page_width
        assert absolute_bbox['height'] == page_height

        print("✓ Conversion verified")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_full_conversion():
    """Test converting full bounding box entry."""
    print("\n" + "=" * 80)
    print("TEST 3: Convert Full Bounding Box Entry")
    print("=" * 80)

    # Create mock cache
    cache = {
        "File #1 - Test": {
            4: {"width": 612.0, "height": 792.0}
        }
    }

    # Sample bounding box entry
    bbox_entry = {
        "file_id": "File #1 - Test",
        "bounding_box": {
            "left": 0.556,
            "right": 0.746,
            "top": 0.198,
            "bottom": 0.354
        },
        "page": 4
    }

    print("Input:")
    print(f"  file_id: {bbox_entry['file_id']}")
    print(f"  page: {bbox_entry['page']}")
    print(f"  bounding_box (relative): {bbox_entry['bounding_box']}")

    try:
        converted_entry = convert_bounding_box_entry(bbox_entry, cache)

        print("\nOutput:")
        print(f"  file_id: {converted_entry['file_id']}")
        print(f"  page: {converted_entry['page']}")
        print(f"  bounding_box (absolute):")
        for key, value in converted_entry['bounding_box'].items():
            print(f"    {key}: {value:.2f}")

        print("✓ Full conversion successful")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    print("\nBounding Box Conversion Tests\n")

    results = []
    results.append(("Page Dimensions Extraction", test_page_dimensions_extraction()))
    results.append(("Bounding Box Conversion", test_bbox_conversion()))
    results.append(("Full Entry Conversion", test_full_conversion()))

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result for _, result in results)
    print("\n" + ("All tests passed! ✓" if all_passed else "Some tests failed ✗"))

    sys.exit(0 if all_passed else 1)
