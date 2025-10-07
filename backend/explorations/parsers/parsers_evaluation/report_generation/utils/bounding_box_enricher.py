"""
Bounding box enrichment utilities for comparison tables.

Adds visual grounding information (bounding boxes) from source documents
to cells in the comparison table output.
"""

import json
from pathlib import Path
from typing import Any

from .bounding_box_converter import convert_bounding_box_entry


def boxes_are_adjacent(box1: dict, box2: dict, tolerance: float = 0.05) -> bool:
    """
    Check if two bounding boxes are adjacent (share an edge within tolerance).

    Boxes are considered adjacent if they share a horizontal or vertical edge,
    allowing for a tolerance based on their dimensions.

    Args:
        box1: First bounding box with left, right, top, bottom (0-1 normalized)
        box2: Second bounding box with left, right, top, bottom (0-1 normalized)
        tolerance: Relative tolerance (default 5% = 0.05)

    Returns:
        True if boxes are adjacent within tolerance
    """
    # Extract coordinates (normalized 0-1)
    left1, right1, top1, bottom1 = box1['left'], box1['right'], box1['top'], box1['bottom']
    left2, right2, top2, bottom2 = box2['left'], box2['right'], box2['top'], box2['bottom']

    # Calculate dimensions
    w1, h1 = right1 - left1, bottom1 - top1
    w2, h2 = right2 - left2, bottom2 - top2

    # Calculate tolerance in normalized coordinates (based on average dimensions)
    avg_width = (w1 + w2) / 2
    avg_height = (h1 + h2) / 2
    x_tolerance = avg_width * tolerance
    y_tolerance = avg_height * tolerance

    # Check if boxes share a vertical edge (left-right adjacency)
    # Box1 is to the left of Box2 or vice versa
    vertical_overlap = not (bottom1 < top2 or bottom2 < top1)
    horizontal_adjacent = (
        abs(right1 - left2) <= x_tolerance or  # box1 left of box2
        abs(right2 - left1) <= x_tolerance     # box2 left of box1
    )

    # Check if boxes share a horizontal edge (top-bottom adjacency)
    # Box1 is above Box2 or vice versa
    horizontal_overlap = not (right1 < left2 or right2 < left1)
    vertical_adjacent = (
        abs(bottom1 - top2) <= y_tolerance or  # box1 above box2
        abs(bottom2 - top1) <= y_tolerance     # box2 above box1
    )

    return (vertical_overlap and horizontal_adjacent) or (horizontal_overlap and vertical_adjacent)


def merge_two_boxes(box1: dict, box2: dict) -> dict:
    """
    Merge two bounding boxes into their bounding rectangle.

    Args:
        box1: First bounding box with left, right, top, bottom (0-1 normalized)
        box2: Second bounding box with left, right, top, bottom (0-1 normalized)

    Returns:
        Merged bounding box encompassing both boxes
    """
    left1, right1, top1, bottom1 = box1['left'], box1['right'], box1['top'], box1['bottom']
    left2, right2, top2, bottom2 = box2['left'], box2['right'], box2['top'], box2['bottom']

    # Calculate bounding rectangle
    min_left = min(left1, left2)
    min_top = min(top1, top2)
    max_right = max(right1, right2)
    max_bottom = max(bottom1, bottom2)

    return {
        'left': min_left,
        'right': max_right,
        'top': min_top,
        'bottom': max_bottom
    }


def bbox_contains(outer: dict, inner: dict) -> bool:
    """
    Check if outer bounding box completely contains inner bounding box.

    Args:
        outer: Bounding box {left, right, top, bottom}
        inner: Bounding box {left, right, top, bottom}

    Returns:
        True if outer contains inner
    """
    return (
        outer['left'] <= inner['left'] and
        outer['right'] >= inner['right'] and
        outer['top'] <= inner['top'] and
        outer['bottom'] >= inner['bottom']
    )


def filter_redundant_boxes(boxes: list[dict], size_threshold: float = 0.35) -> list[dict]:
    """
    Remove redundant bounding boxes:
    1. Remove boxes that are too large (width OR height > threshold)
    2. Remove boxes that contain other smaller boxes

    Args:
        boxes: List of bounding boxes with left, right, top, bottom (0-1 normalized)
        size_threshold: Maximum relative size (default 35% = 0.35)

    Returns:
        Filtered list of bounding boxes
    """
    if len(boxes) <= 1:
        return boxes

    filtered = []

    for i, bbox in enumerate(boxes):
        # Calculate dimensions
        width = bbox['right'] - bbox['left']
        height = bbox['bottom'] - bbox['top']

        # Skip if too large (> 35% of page in either dimension)
        if width > size_threshold or height > size_threshold:
            continue

        # Check if this box contains any other box
        is_redundant = False
        for j, other_bbox in enumerate(boxes):
            if i == j:
                continue

            # If this box contains another, it's redundant
            if bbox_contains(bbox, other_bbox):
                is_redundant = True
                break

        if not is_redundant:
            filtered.append(bbox)

    return filtered


def merge_adjacent_boxes(boxes: list[dict], tolerance: float = 0.05) -> list[dict]:
    """
    Recursively merge adjacent bounding boxes within a list.

    Continues merging until no more adjacent boxes can be merged.

    Args:
        boxes: List of bounding boxes with left, right, top, bottom (0-1 normalized)
        tolerance: Relative tolerance for adjacency (default 5% = 0.05)

    Returns:
        List of merged bounding boxes
    """
    if len(boxes) <= 1:
        return boxes

    # Try to find a pair of adjacent boxes to merge
    merged = False
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes_are_adjacent(boxes[i], boxes[j], tolerance):
                # Merge these two boxes
                merged_box = merge_two_boxes(boxes[i], boxes[j])

                # Create new list without boxes[i] and boxes[j], but with merged_box
                new_boxes = [boxes[k] for k in range(len(boxes)) if k != i and k != j]
                new_boxes.append(merged_box)

                # Recursively merge the new list
                merged = True
                return merge_adjacent_boxes(new_boxes, tolerance)

    # No more merges possible
    return boxes


def load_document_grounding(doc_path: str | Path) -> dict[str, dict]:
    """
    Load grounding information from a parsed document.

    Extracts grounding info at the most granular level (tableCell when available).
    Uses Landing AI's grounding structure which maps cell IDs to bounding boxes.

    Args:
        doc_path: Path to parsed document JSON file

    Returns:
        Dictionary mapping cell_id -> grounding_info (filtered for tableCell type only)
    """
    import re

    with open(doc_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    grounding_map = {}

    # Check if document has Landing AI grounding structure
    if 'grounding' in data:
        # Landing AI format: top-level grounding dict with cell_id -> {box, page, type}
        for cell_id, grounding_info in data['grounding'].items():
            # Only include tableCell types (skip table-level grounding)
            if grounding_info.get('type') == 'tableCell':
                grounding_map[cell_id] = grounding_info

    # Fallback to legacy chunk-based grounding (for backward compatibility)
    else:
        for chunk in data.get('chunks', []):
            chunk_id = chunk.get('id')
            grounding = chunk.get('grounding')
            chunk_type = chunk.get('type')
            markdown = chunk.get('markdown', '')

            # For table chunks, extract cell IDs from HTML and map them to table grounding
            if chunk_type == 'table' and grounding and 'id=' in markdown:
                # Extract all cell IDs from the HTML table
                cell_ids = re.findall(r'id="([^"]+)"', markdown)

                # Map each cell ID to the table's grounding
                for cell_id in cell_ids:
                    grounding_map[cell_id] = grounding

            # For non-table chunks, use chunk ID directly
            elif chunk_id and grounding:
                grounding_map[chunk_id] = grounding

    return grounding_map


def enrich_cell_with_bounding_boxes(
    cell: dict,
    probtp_grounding: dict[str, dict],
    axa_grounding: dict[str, dict],
    probtp_file_name: str,
    axa_file_name: str,
    page_dimensions_cache: dict[str, dict[int, dict[str, float]]] | None = None,
    merge_adjacent: bool = True,
    merge_tolerance: float = 0.05
) -> tuple[dict, dict]:
    """
    Enrich a single cell with bounding boxes from source documents.

    Merges adjacent bounding boxes (same file_id and page) to create unified
    bounding boxes at the comparison table cell level.

    Args:
        cell: Table cell dict
        probtp_grounding: ProBTP grounding map (cell_id -> grounding)
        axa_grounding: AXA grounding map (cell_id -> grounding)
        probtp_file_name: ProBTP document file name
        axa_file_name: AXA document file name
        page_dimensions_cache: Optional cache for converting to absolute coordinates
        merge_adjacent: Whether to merge adjacent bounding boxes (default True)
        merge_tolerance: Relative tolerance for adjacency detection (default 5%)

    Returns:
        Tuple of (enriched_cell, resolution_info):
        - enriched_cell: Cell dict with added bounding_boxes array (if sources exist)
        - resolution_info: Dict with 'probtp_resolved', 'axa_resolved', 'probtp_unresolved', 'axa_unresolved' source IDs
        If page_dimensions_cache is provided, bounding boxes will be in absolute coordinates
    """
    sources = cell.get('sources')
    if not sources:
        return cell, {
            'probtp_resolved': [],
            'axa_resolved': [],
            'probtp_unresolved': [],
            'axa_unresolved': []
        }

    bounding_boxes = []
    probtp_sources_with_grounding = []
    axa_sources_with_grounding = []

    # Add ProBTP bounding boxes
    probtp_sources = sources.get('probtp', [])
    if probtp_sources:
        for source_id in probtp_sources:
            grounding = probtp_grounding.get(source_id)
            if grounding:
                probtp_sources_with_grounding.append(source_id)
                bounding_boxes.append({
                    'file_id': probtp_file_name,
                    'bounding_box': grounding.get('box', {}),
                    'page': grounding.get('page', 0)
                })

    # Add AXA bounding boxes
    axa_sources = sources.get('axa', [])
    if axa_sources:
        for source_id in axa_sources:
            grounding = axa_grounding.get(source_id)
            if grounding:
                axa_sources_with_grounding.append(source_id)
                bounding_boxes.append({
                    'file_id': axa_file_name,
                    'bounding_box': grounding.get('box', {}),
                    'page': grounding.get('page', 0)
                })

    # Filter and merge boxes if requested
    if merge_adjacent and bounding_boxes:
        # Group by (file_id, page)
        groups: dict[tuple[str, int], list[dict]] = {}
        for bbox_entry in bounding_boxes:
            key = (bbox_entry['file_id'], bbox_entry['page'])
            if key not in groups:
                groups[key] = []
            groups[key].append(bbox_entry['bounding_box'])

        # Process each group: filter first, then merge
        processed_bounding_boxes = []
        for (file_id, page), boxes in groups.items():
            # 1. Filter redundant boxes (too large or containing others) FIRST
            filtered_boxes = filter_redundant_boxes(boxes, size_threshold=0.35)
            # 2. Then merge adjacent boxes
            merged_boxes = merge_adjacent_boxes(filtered_boxes, tolerance=merge_tolerance)
            for merged_box in merged_boxes:
                processed_bounding_boxes.append({
                    'file_id': file_id,
                    'bounding_box': merged_box,
                    'page': page
                })

        bounding_boxes = processed_bounding_boxes

    # Deduplicate identical bounding boxes (same file_id, page, and bbox coordinates)
    if bounding_boxes:
        seen = set()
        deduplicated_boxes = []
        for bbox_entry in bounding_boxes:
            # Create a hashable key from the bounding box entry
            bbox = bbox_entry['bounding_box']
            key = (
                bbox_entry['file_id'],
                bbox_entry['page'],
                bbox.get('left'),
                bbox.get('right'),
                bbox.get('top'),
                bbox.get('bottom')
            )
            if key not in seen:
                seen.add(key)
                deduplicated_boxes.append(bbox_entry)

        bounding_boxes = deduplicated_boxes

    # Convert to absolute coordinates if cache is provided
    if page_dimensions_cache and bounding_boxes:
        try:
            bounding_boxes = [
                convert_bounding_box_entry(bbox_entry, page_dimensions_cache)
                for bbox_entry in bounding_boxes
            ]
        except (ValueError, KeyError) as e:
            # If conversion fails, log warning but keep relative coordinates
            print(f"      ⚠️  Warning: Could not convert bounding boxes to absolute coordinates: {e}")

    # Determine which sources were resolved (have final bounding boxes after filtering)
    final_probtp_has_bbox = any(probtp_file_name in bbox['file_id'] for bbox in bounding_boxes)
    final_axa_has_bbox = any(axa_file_name in bbox['file_id'] for bbox in bounding_boxes)

    # Create resolution info
    resolution_info = {
        'probtp_resolved': probtp_sources_with_grounding if final_probtp_has_bbox else [],
        'axa_resolved': axa_sources_with_grounding if final_axa_has_bbox else [],
        'probtp_unresolved': [sid for sid in probtp_sources if sid not in probtp_sources_with_grounding] +
                            (probtp_sources_with_grounding if not final_probtp_has_bbox else []),
        'axa_unresolved': [sid for sid in axa_sources if sid not in axa_sources_with_grounding] +
                         (axa_sources_with_grounding if not final_axa_has_bbox else [])
    }

    # Add bounding_boxes array if we found any
    if bounding_boxes:
        enriched_cell = {**cell, 'bounding_boxes': bounding_boxes}
        return enriched_cell, resolution_info

    return cell, resolution_info


def enrich_comparison_table_with_bounding_boxes(
    comparison_table: dict,
    probtp_doc_path: str | Path,
    axa_doc_path: str | Path,
    page_dimensions_cache: dict[str, dict[int, dict[str, float]]] | None = None,
    print_stats: bool = True
) -> tuple[dict, dict]:
    """
    Enrich all cells in comparison table with bounding boxes from source documents.

    Args:
        comparison_table: ComparisonTable dict from alignment/analysis phase
        probtp_doc_path: Path to ProBTP parsed document JSON
        axa_doc_path: Path to AXA parsed document JSON
        page_dimensions_cache: Optional cache for converting to absolute coordinates
        print_stats: Whether to print resolution statistics

    Returns:
        Tuple of (enriched_table, stats_dict):
        - enriched_table: Enriched comparison table with bounding_boxes in cells that have sources
        - stats_dict: Dictionary with grounding statistics
        If page_dimensions_cache is provided, bounding boxes will be in absolute coordinates
    """
    # Load grounding maps
    probtp_grounding = load_document_grounding(probtp_doc_path)
    axa_grounding = load_document_grounding(axa_doc_path)

    # Get file names
    probtp_file_name = Path(probtp_doc_path).stem
    axa_file_name = Path(axa_doc_path).stem

    # Statistics tracking
    stats = {
        'probtp_total_source_ids': 0,
        'probtp_resolved': 0,
        'probtp_unresolved': [],  # List of dicts with {source_id, cell_key, cell_value, row_index, cell_index}
        'axa_total_source_ids': 0,
        'axa_resolved': 0,
        'axa_unresolved': [],  # List of dicts with {source_id, cell_key, cell_value, row_index, cell_index}
    }

    # Enrich each cell
    enriched_rows = []
    for row_idx, row in enumerate(comparison_table.get('rows', [])):
        enriched_cells = []
        for cell_idx, cell in enumerate(row.get('cells', [])):
            # Track source IDs before enrichment
            sources = cell.get('sources', {})
            probtp_sources = sources.get('probtp', [])
            axa_sources = sources.get('axa', [])

            stats['probtp_total_source_ids'] += len(probtp_sources)
            stats['axa_total_source_ids'] += len(axa_sources)

            # Enrich cell
            enriched_cell, resolution_info = enrich_cell_with_bounding_boxes(
                cell,
                probtp_grounding,
                axa_grounding,
                probtp_file_name,
                axa_file_name,
                page_dimensions_cache
            )

            # Track resolved count (number of source IDs that made it through)
            stats['probtp_resolved'] += len(resolution_info['probtp_resolved'])
            stats['axa_resolved'] += len(resolution_info['axa_resolved'])

            # Track unresolved source IDs with metadata
            cell_key = cell.get('key', '')
            cell_value = cell.get('value', '')

            for source_id in resolution_info['probtp_unresolved']:
                # Determine reason
                if source_id not in probtp_grounding:
                    reason = 'not_in_grounding_map'
                else:
                    reason = 'filtered_out_during_processing'

                stats['probtp_unresolved'].append({
                    'source_id': source_id,
                    'cell_key': cell_key,
                    'cell_value': cell_value,
                    'row_index': row_idx,
                    'cell_index': cell_idx,
                    'reason': reason
                })

            for source_id in resolution_info['axa_unresolved']:
                if source_id not in axa_grounding:
                    reason = 'not_in_grounding_map'
                else:
                    reason = 'filtered_out_during_processing'

                stats['axa_unresolved'].append({
                    'source_id': source_id,
                    'cell_key': cell_key,
                    'cell_value': cell_value,
                    'row_index': row_idx,
                    'cell_index': cell_idx,
                    'reason': reason
                })

            enriched_cells.append(enriched_cell)

        enriched_row = {**row, 'cells': enriched_cells}
        enriched_rows.append(enriched_row)

    # Print statistics
    category = comparison_table.get('metadata', {}).get('category', 'Unknown')
    if print_stats:
        print(f"      Grounding statistics for {category}:")
        print(f"         ProBTP: {stats['probtp_resolved']}/{stats['probtp_total_source_ids']} source IDs resolved " +
              f"({stats['probtp_resolved']/stats['probtp_total_source_ids']*100:.1f}%)" if stats['probtp_total_source_ids'] > 0 else "         ProBTP: No source IDs")
        print(f"         AXA:    {stats['axa_resolved']}/{stats['axa_total_source_ids']} source IDs resolved " +
              f"({stats['axa_resolved']/stats['axa_total_source_ids']*100:.1f}%)" if stats['axa_total_source_ids'] > 0 else "         AXA:    No source IDs")

        # Show sample of unresolved IDs
        if stats['probtp_unresolved']:
            print(f"         ProBTP unresolved (sample): {[item['source_id'] for item in stats['probtp_unresolved'][:5]]}")
        if stats['axa_unresolved']:
            print(f"         AXA unresolved (sample): {[item['source_id'] for item in stats['axa_unresolved'][:5]]}")

    # Add category to stats for easier identification
    stats['category'] = category

    # Return enriched table and statistics
    enriched_table = {**comparison_table, 'rows': enriched_rows}
    return enriched_table, stats


def enrich_report_with_bounding_boxes(
    report_data: dict,
    probtp_doc_path: str | Path,
    axa_doc_path: str | Path,
    page_dimensions_cache: dict[str, dict[int, dict[str, float]]] | None = None
) -> dict:
    """
    Enrich entire report with bounding boxes for all category tables.

    Args:
        report_data: Complete report JSON with category_analyses
        probtp_doc_path: Path to ProBTP parsed document JSON
        axa_doc_path: Path to AXA parsed document JSON
        page_dimensions_cache: Optional cache for converting to absolute coordinates

    Returns:
        Enriched report with bounding_boxes in all cells
        If page_dimensions_cache is provided, bounding boxes will be in absolute coordinates
    """
    enriched_categories = {}

    for category, analysis in report_data.get('category_analyses', {}).items():
        # Enrich annotated_table (from analysis phase)
        annotated_table = analysis.get('annotated_table')
        if annotated_table:
            enriched_table = enrich_comparison_table_with_bounding_boxes(
                annotated_table,
                probtp_doc_path,
                axa_doc_path,
                page_dimensions_cache
            )
            enriched_analysis = {**analysis, 'annotated_table': enriched_table}
            enriched_categories[category] = enriched_analysis
        else:
            enriched_categories[category] = analysis

    enriched_report = {**report_data, 'category_analyses': enriched_categories}
    return enriched_report
