"""
Bounding box coordinate converter.

Converts Landing AI's relative bounding boxes (0-1 normalized)
to absolute coordinates compatible with react-pdf-highlighter.
"""


def convert_bbox_to_absolute(
    bbox: dict,
    page_width: float,
    page_height: float
) -> dict:
    """
    Convert relative bounding box to absolute coordinates.

    Landing AI format (input):
        {
            "left": 0.556,   # 0-1 normalized
            "right": 0.746,
            "top": 0.198,
            "bottom": 0.354
        }

    react-pdf-highlighter format (output):
        {
            "x1": 450.14,    # absolute points
            "y1": 237.85,
            "x2": 603.87,
            "y2": 425.76,
            "width": 809.99,
            "height": 1200
        }

    Coordinate system: top-left origin, y-axis goes top to bottom

    Args:
        bbox: Relative bounding box with left, right, top, bottom (0-1 normalized)
        page_width: Page width in points
        page_height: Page height in points

    Returns:
        Absolute bounding box with x1, y1, x2, y2, width, height
    """
    return {
        "x1": bbox["left"] * page_width,
        "y1": bbox["top"] * page_height,
        "x2": bbox["right"] * page_width,
        "y2": bbox["bottom"] * page_height,
        "width": page_width,
        "height": page_height
    }


def convert_bounding_box_entry(
    bbox_entry: dict,
    page_dimensions_cache: dict[str, dict[int, dict[str, float]]]
) -> dict:
    """
    Convert a bounding box entry from relative to absolute coordinates.

    Input format:
        {
            "file_id": "File #1 - ...",
            "bounding_box": {
                "left": 0.556,
                "right": 0.746,
                "top": 0.198,
                "bottom": 0.354
            },
            "page": 4
        }

    Output format:
        {
            "file_id": "File #1 - ...",
            "bounding_box": {
                "x1": 450.14,
                "y1": 237.85,
                "x2": 603.87,
                "y2": 425.76,
                "width": 809.99,
                "height": 1200
            },
            "page": 4
        }

    Args:
        bbox_entry: Bounding box entry with relative coordinates
        page_dimensions_cache: Cache mapping file_id -> page -> dimensions

    Returns:
        Bounding box entry with absolute coordinates
    """
    file_id = bbox_entry["file_id"]
    page = bbox_entry["page"]
    relative_bbox = bbox_entry["bounding_box"]

    # Get page dimensions from cache
    if file_id not in page_dimensions_cache:
        raise ValueError(f"File ID not found in cache: {file_id}")

    if page not in page_dimensions_cache[file_id]:
        raise ValueError(f"Page {page} not found for file: {file_id}")

    page_dims = page_dimensions_cache[file_id][page]
    page_width = page_dims["width"]
    page_height = page_dims["height"]

    # Convert bounding box
    absolute_bbox = convert_bbox_to_absolute(
        relative_bbox,
        page_width,
        page_height
    )

    # Return new entry with absolute coordinates
    return {
        "file_id": file_id,
        "bounding_box": absolute_bbox,
        "page": page
    }
