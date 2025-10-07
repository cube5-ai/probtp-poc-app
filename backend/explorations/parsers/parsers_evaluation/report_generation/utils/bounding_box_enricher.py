"""
Bounding box enrichment utilities for comparison tables.

Adds visual grounding information (bounding boxes) from source documents
to cells in the comparison table output.
"""

import json
from pathlib import Path
from typing import Any


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
    merge_adjacent: bool = True,
    merge_tolerance: float = 0.05
) -> dict:
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
        merge_adjacent: Whether to merge adjacent bounding boxes (default True)
        merge_tolerance: Relative tolerance for adjacency detection (default 5%)

    Returns:
        Cell dict with added bounding_boxes array (if sources exist)
    """
    sources = cell.get('sources')
    if not sources:
        return cell

    bounding_boxes = []

    # Add ProBTP bounding boxes
    probtp_sources = sources.get('probtp', [])
    if probtp_sources:
        for source_id in probtp_sources:
            grounding = probtp_grounding.get(source_id)
            if grounding:
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
                bounding_boxes.append({
                    'file_id': axa_file_name,
                    'bounding_box': grounding.get('box', {}),
                    'page': grounding.get('page', 0)
                })

    # Merge adjacent boxes if requested
    if merge_adjacent and bounding_boxes:
        # Group by (file_id, page)
        groups: dict[tuple[str, int], list[dict]] = {}
        for bbox_entry in bounding_boxes:
            key = (bbox_entry['file_id'], bbox_entry['page'])
            if key not in groups:
                groups[key] = []
            groups[key].append(bbox_entry['bounding_box'])

        # Merge boxes within each group and rebuild bounding_boxes list
        merged_bounding_boxes = []
        for (file_id, page), boxes in groups.items():
            merged_boxes = merge_adjacent_boxes(boxes, tolerance=merge_tolerance)
            for merged_box in merged_boxes:
                merged_bounding_boxes.append({
                    'file_id': file_id,
                    'bounding_box': merged_box,
                    'page': page
                })

        bounding_boxes = merged_bounding_boxes

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

    # Add bounding_boxes array if we found any
    if bounding_boxes:
        enriched_cell = {**cell, 'bounding_boxes': bounding_boxes}
        return enriched_cell

    return cell


def enrich_comparison_table_with_bounding_boxes(
    comparison_table: dict,
    probtp_doc_path: str | Path,
    axa_doc_path: str | Path,
    print_stats: bool = True
) -> dict:
    """
    Enrich all cells in comparison table with bounding boxes from source documents.

    Args:
        comparison_table: ComparisonTable dict from alignment/analysis phase
        probtp_doc_path: Path to ProBTP parsed document JSON
        axa_doc_path: Path to AXA parsed document JSON
        print_stats: Whether to print resolution statistics

    Returns:
        Enriched comparison table with bounding_boxes in cells that have sources
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
        'probtp_unresolved': [],
        'axa_total_source_ids': 0,
        'axa_resolved': 0,
        'axa_unresolved': [],
    }

    # Enrich each cell
    enriched_rows = []
    for row in comparison_table.get('rows', []):
        enriched_cells = []
        for cell in row.get('cells', []):
            # Track source IDs before enrichment
            sources = cell.get('sources', {})
            probtp_sources = sources.get('probtp', [])
            axa_sources = sources.get('axa', [])

            stats['probtp_total_source_ids'] += len(probtp_sources)
            stats['axa_total_source_ids'] += len(axa_sources)

            # Enrich cell
            enriched_cell = enrich_cell_with_bounding_boxes(
                cell,
                probtp_grounding,
                axa_grounding,
                probtp_file_name,
                axa_file_name
            )

            # Track resolved bounding boxes
            bboxes = enriched_cell.get('bounding_boxes', [])
            for bbox in bboxes:
                if probtp_file_name in bbox['file_id']:
                    stats['probtp_resolved'] += 1
                elif axa_file_name in bbox['file_id']:
                    stats['axa_resolved'] += 1

            # Track unresolved source IDs
            for source_id in probtp_sources:
                if source_id not in probtp_grounding:
                    stats['probtp_unresolved'].append(source_id)

            for source_id in axa_sources:
                if source_id not in axa_grounding:
                    stats['axa_unresolved'].append(source_id)

            enriched_cells.append(enriched_cell)

        enriched_row = {**row, 'cells': enriched_cells}
        enriched_rows.append(enriched_row)

    # Print statistics
    if print_stats:
        category = comparison_table.get('metadata', {}).get('category', 'Unknown')
        print(f"      Grounding statistics for {category}:")
        print(f"         ProBTP: {stats['probtp_resolved']}/{stats['probtp_total_source_ids']} source IDs resolved " +
              f"({stats['probtp_resolved']/stats['probtp_total_source_ids']*100:.1f}%)" if stats['probtp_total_source_ids'] > 0 else "         ProBTP: No source IDs")
        print(f"         AXA:    {stats['axa_resolved']}/{stats['axa_total_source_ids']} source IDs resolved " +
              f"({stats['axa_resolved']/stats['axa_total_source_ids']*100:.1f}%)" if stats['axa_total_source_ids'] > 0 else "         AXA:    No source IDs")

        # Show sample of unresolved IDs
        if stats['probtp_unresolved']:
            print(f"         ProBTP unresolved (sample): {stats['probtp_unresolved'][:5]}")
        if stats['axa_unresolved']:
            print(f"         AXA unresolved (sample): {stats['axa_unresolved'][:5]}")

    # Return enriched table
    enriched_table = {**comparison_table, 'rows': enriched_rows}
    return enriched_table


def enrich_report_with_bounding_boxes(
    report_data: dict,
    probtp_doc_path: str | Path,
    axa_doc_path: str | Path
) -> dict:
    """
    Enrich entire report with bounding boxes for all category tables.

    Args:
        report_data: Complete report JSON with category_analyses
        probtp_doc_path: Path to ProBTP parsed document JSON
        axa_doc_path: Path to AXA parsed document JSON

    Returns:
        Enriched report with bounding_boxes in all cells
    """
    enriched_categories = {}

    for category, analysis in report_data.get('category_analyses', {}).items():
        # Enrich annotated_table (from analysis phase)
        annotated_table = analysis.get('annotated_table')
        if annotated_table:
            enriched_table = enrich_comparison_table_with_bounding_boxes(
                annotated_table,
                probtp_doc_path,
                axa_doc_path
            )
            enriched_analysis = {**analysis, 'annotated_table': enriched_table}
            enriched_categories[category] = enriched_analysis
        else:
            enriched_categories[category] = analysis

    enriched_report = {**report_data, 'category_analyses': enriched_categories}
    return enriched_report
