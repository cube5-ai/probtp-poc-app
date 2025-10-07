"""
Visualize comparison results by annotating the ProBTP PDF with color-coded rectangles.

Colors indicate how ProBTP compares to AXA:
- Dark Red: ProBTP much worse
- Light Red: ProBTP worse
- Yellow: Equivalent
- Light Green: ProBTP better
- Dark Green: ProBTP much better

Hover over annotations to see AXA values and comparison rationale.
"""

import json
from pathlib import Path
import pymupdf


# Color mapping based on probtp_advantage
COLORS = {
    "probtp_much_worse": (0.545, 0, 0),      # Dark Red
    "probtp_worse": (1, 0.42, 0.42),         # Light Red
    "probtp_equivalent": (1, 0.84, 0),       # Yellow
    "probtp_better": (0.565, 0.933, 0.565),  # Light Green
    "probtp_much_better": (0, 0.392, 0),     # Dark Green
}


def load_comparison_report(json_path: Path) -> dict:
    """Load the comparison report JSON."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_leaf_analysis_map(report: dict) -> dict:
    """
    Build a mapping from leaf_id to analysis information.

    Returns:
        dict: {leaf_id: {advantage, probtp_value, axa_value, rationale}}
    """
    leaf_map = {}

    for category, analysis in report.get('analyses', {}).items():
        for leaf_comp in analysis.get('leaf_comparisons', []):
            leaf_id = leaf_comp['leaf_id']
            leaf_map[leaf_id] = {
                'advantage': leaf_comp['probtp_advantage'],
                'probtp_display_value': leaf_comp.get('probtp_display_value', 'N/A'),
                'axa_value': leaf_comp.get('axa_display_value', 'N/A'),
                'rationale': leaf_comp.get('rationale', '')
            }

    return leaf_map


def build_source_to_leaf_map(report: dict) -> dict:
    """
    Build a mapping from source_cell_id to leaf_id for both ProBTP and AXA.

    Returns:
        dict: {source_cell_id: leaf_id}
    """
    source_map = {}

    for category, extractions in report.get('extractions', {}).items():
        # Add ProBTP sources
        probtp_data = extractions.get('probtp', {})
        probtp_values = probtp_data.get('extracted_values', [])

        for item in probtp_values:
            leaf_id = item.get('leaf_id')
            source_cell_ids = item.get('source_cell_ids') or []

            for source_id in source_cell_ids:
                source_map[source_id] = leaf_id

        # Add AXA sources
        axa_data = extractions.get('axa', {})
        axa_values = axa_data.get('extracted_values', [])

        for item in axa_values:
            leaf_id = item.get('leaf_id')
            source_cell_ids = item.get('source_cell_ids') or []

            for source_id in source_cell_ids:
                source_map[source_id] = leaf_id

    return source_map


def bbox_contains(outer: dict, inner: dict) -> bool:
    """
    Check if outer bounding box completely contains inner bounding box.

    Args:
        outer: Bounding box {top, left, bottom, right}
        inner: Bounding box {top, left, bottom, right}

    Returns:
        True if outer contains inner
    """
    return (
        outer['left'] <= inner['left'] and
        outer['right'] >= inner['right'] and
        outer['top'] <= inner['top'] and
        outer['bottom'] >= inner['bottom']
    )


def are_vertically_aligned(bbox1: dict, bbox2: dict, tolerance: float = 0.02) -> bool:
    """
    Check if two bounding boxes are vertically aligned (centered on same vertical line).

    Args:
        bbox1: First bounding box {top, left, bottom, right}
        bbox2: Second bounding box {top, left, bottom, right}
        tolerance: Maximum allowed difference in center x-coordinate (normalized 0-1)

    Returns:
        True if the bboxes are vertically aligned
    """
    # Calculate center x-coordinates
    center1_x = (bbox1['left'] + bbox1['right']) / 2
    center2_x = (bbox2['left'] + bbox2['right']) / 2

    # Check if centers are within tolerance
    return abs(center1_x - center2_x) < tolerance


def are_vertical_neighbors(bbox1: dict, bbox2: dict, gap_tolerance: float = 0.01) -> bool:
    """
    Check if two bounding boxes are vertical neighbors (one above/below the other with small gap).

    Args:
        bbox1: First bounding box {top, left, bottom, right}
        bbox2: Second bounding box {top, left, bottom, right}
        gap_tolerance: Maximum allowed gap between boxes (normalized 0-1)

    Returns:
        True if the bboxes are vertical neighbors
    """
    # Check if bbox1 is above bbox2
    gap_below = bbox2['top'] - bbox1['bottom']
    # Check if bbox2 is above bbox1
    gap_above = bbox1['top'] - bbox2['bottom']

    # They are neighbors if the gap is small (touching or very close)
    return (0 <= gap_below <= gap_tolerance) or (0 <= gap_above <= gap_tolerance)


def remove_redundant_bboxes(bboxes: list) -> list:
    """
    Remove bounding boxes that contain other bounding boxes from the same cell.
    Also removes bboxes that are too large (width OR height > 20% of page).
    Keeps the most specific (smallest) bounding boxes.
    Only merges cells if they are BOTH vertical neighbors AND vertically aligned.

    Args:
        bboxes: List of bbox_info dicts with 'bounding_box' and 'page'

    Returns:
        Filtered list with redundant (larger) bboxes removed
    """
    if len(bboxes) <= 1:
        return bboxes

    # Group by page
    by_page = {}
    for bbox_info in bboxes:
        page = bbox_info.get('page', 0)
        if page not in by_page:
            by_page[page] = []
        by_page[page].append(bbox_info)

    result = []

    # For each page, remove bboxes that contain others or are too large
    for page, page_bboxes in by_page.items():
        filtered = []

        for i, bbox_info in enumerate(page_bboxes):
            bbox = bbox_info.get('bounding_box', {})

            # Calculate bbox dimensions (normalized 0-1)
            width = abs(bbox.get('right', 0) - bbox.get('left', 0))
            height = abs(bbox.get('bottom', 0) - bbox.get('top', 0))

            # Skip bboxes that are too large (> 20% of page in either dimension)
            if width > 0.2 or height > 0.2:
                continue

            is_redundant = False

            # Check if this bbox contains any other bbox
            for j, other_info in enumerate(page_bboxes):
                if i == j:
                    continue

                other_bbox = other_info.get('bounding_box', {})

                # Only consider it redundant if:
                # 1. This bbox contains another
                # 2. They are vertical neighbors (one above/below the other)
                # 3. They are vertically aligned (centered on same vertical line)
                if (bbox_contains(bbox, other_bbox) and
                    are_vertical_neighbors(bbox, other_bbox) and
                    are_vertically_aligned(bbox, other_bbox)):
                    is_redundant = True
                    break

            if not is_redundant:
                filtered.append(bbox_info)

        result.extend(filtered)

    return result


def reverse_perspective(rationale: str, advantage: str) -> str:
    """
    Reverse the rationale to be from AXA's perspective instead of ProBTP's.

    Args:
        rationale: Original rationale from ProBTP perspective
        advantage: probtp_advantage value

    Returns:
        Reversed rationale from AXA perspective
    """
    # Map ProBTP advantage to AXA advantage description
    perspective_map = {
        'probtp_much_worse': 'AXA offre une couverture beaucoup plus avantageuse',
        'probtp_worse': 'AXA offre une couverture plus avantageuse',
        'probtp_equivalent': 'Couverture équivalente',
        'probtp_better': 'ProBTP offre une couverture plus avantageuse',
        'probtp_much_better': 'ProBTP offre une couverture beaucoup plus avantageuse',
    }

    prefix = perspective_map.get(advantage, '')

    # Return the reversed perspective with original rationale
    if advantage in ['probtp_much_worse', 'probtp_worse']:
        return f"{prefix}. {rationale}"
    elif advantage == 'probtp_equivalent':
        return rationale
    else:  # probtp_better or probtp_much_better
        return f"{prefix}. {rationale}"


def extract_annotations(report: dict, leaf_map: dict, document_filter: str) -> list:
    """
    Extract annotation data for cells from a specific document.

    Args:
        report: Comparison report data
        leaf_map: Mapping of leaf_id to analysis info
        document_filter: Document name to filter for ('Panorama FMC' or 'SAE')

    Returns:
        list: [{page, bbox, color, hover_text, document}, ...]
    """
    annotations = []

    # Build source_cell_id to leaf_id mapping
    source_to_leaf = build_source_to_leaf_map(report)

    # Iterate through comparison tables
    for category, table in report.get('comparison_tables', {}).items():
        template_row = table.get('template_row', [])

        # Find ProBTP and AXA column indices
        probtp_col_idx = None
        axa_col_idx = None
        for idx, header in enumerate(template_row):
            # ProBTP columns: S2, S3, S3+, S4, P3, P4, P5, etc.
            if header in ['S2', 'S3', 'S3+', 'S4', 'P3', 'P4', 'P5']:
                probtp_col_idx = idx
            # AXA columns: various formulations
            elif 'Base Obligatoire' in header or 'Surcomplémentaire' in header or 'Complémentaire responsable' in header or 'Option' in header:
                axa_col_idx = idx

        # Process each row
        for row in table.get('rows', []):
            cells = row.get('cells', [])

            # Get both ProBTP and AXA cells to extract leaf_id
            probtp_cell = cells[probtp_col_idx] if probtp_col_idx is not None and probtp_col_idx < len(cells) else None
            axa_cell = cells[axa_col_idx] if axa_col_idx is not None and axa_col_idx < len(cells) else None

            # Determine which cell to process based on document filter
            if document_filter == 'Panorama FMC':
                target_cell = probtp_cell
                source_key = 'probtp'
            else:  # AXA document
                target_cell = axa_cell
                source_key = 'axa'

            if not target_cell or not target_cell.get('bounding_boxes'):
                continue

            # Get source_cell_ids from the cell
            sources = target_cell.get('sources', {})
            target_sources = sources.get(source_key, [])

            if not target_sources:
                continue

            # Map source_cell_id to leaf_id
            leaf_id = None
            for source_id in target_sources:
                if source_id in source_to_leaf:
                    leaf_id = source_to_leaf[source_id]
                    break

            if not leaf_id:
                continue

            # Get analysis info for this leaf
            if leaf_id not in leaf_map:
                continue

            analysis_info = leaf_map[leaf_id]
            advantage = analysis_info['advantage']

            # Get color for this advantage level (from ProBTP perspective)
            color = COLORS.get(advantage, (0.5, 0.5, 0.5))  # Default gray

            # Get policy levels from metadata
            metadata = report.get('metadata', {})
            probtp_levels = metadata.get('Probtp Levels', '')
            axa_levels = metadata.get('Axa Levels', '')

            # Build hover text (show both values with policy levels)
            probtp_value = analysis_info.get('probtp_display_value', 'N/A')
            axa_value = analysis_info['axa_value']
            rationale = analysis_info['rationale']

            # For ProBTP document: show from ProBTP perspective
            # For AXA document: show from AXA perspective (reversed)
            if document_filter == 'Panorama FMC':
                # ProBTP perspective
                hover_text = (
                    f"ProBTP ({probtp_levels}): {probtp_value}\n"
                    f"AXA ({axa_levels}): {axa_value}\n\n"
                    f"{rationale}"
                )
            else:
                # AXA perspective - reverse the rationale interpretation
                axa_rationale = reverse_perspective(rationale, advantage)
                hover_text = (
                    f"AXA ({axa_levels}): {axa_value}\n"
                    f"ProBTP ({probtp_levels}): {probtp_value}\n\n"
                    f"{axa_rationale}"
                )

            # Extract bounding boxes and filter for target document
            target_bboxes = []
            for bbox_info in target_cell['bounding_boxes']:
                file_id = bbox_info.get('file_id', '')

                # Only process target document
                if document_filter not in file_id:
                    continue

                target_bboxes.append(bbox_info)

            # Remove redundant (containing) bounding boxes
            filtered_bboxes = remove_redundant_bboxes(target_bboxes)

            # Create annotations from filtered bboxes
            for bbox_info in filtered_bboxes:
                bbox = bbox_info.get('bounding_box', {})
                page = bbox_info.get('page', 0)

                annotations.append({
                    'page': page,
                    'bbox': bbox,  # {top, left, bottom, right} in 0-1 range
                    'color': color,
                    'hover_text': hover_text,
                    'leaf_id': leaf_id,
                    'document': document_filter
                })

    return annotations


def convert_bbox_to_rect(bbox: dict, page_width: float, page_height: float) -> pymupdf.Rect:
    """
    Convert normalized bounding box to PyMuPDF Rect.

    Args:
        bbox: {top, left, bottom, right} in 0-1 range
        page_width: Page width in points
        page_height: Page height in points

    Returns:
        pymupdf.Rect object
    """
    left = bbox['left'] * page_width
    top = bbox['top'] * page_height
    right = bbox['right'] * page_width
    bottom = bbox['bottom'] * page_height

    return pymupdf.Rect(left, top, right, bottom)


def annotate_pdf(pdf_path: Path, annotations: list, output_path: Path):
    """
    Add color-coded annotations to the PDF.

    Args:
        pdf_path: Path to source PDF
        annotations: List of annotation data
        output_path: Path to save annotated PDF
    """
    doc = pymupdf.open(pdf_path)

    for annot_data in annotations:
        page_num = annot_data['page']

        if page_num >= len(doc):
            print(f"Warning: Page {page_num} not found in PDF (total pages: {len(doc)})")
            continue

        page = doc[page_num]
        page_width = page.rect.width
        page_height = page.rect.height

        # Convert normalized bbox to PyMuPDF Rect
        rect = convert_bbox_to_rect(annot_data['bbox'], page_width, page_height)

        # Add square annotation
        annot = page.add_rect_annot(rect)

        # Set hover text
        annot.set_info(
            content=annot_data['hover_text'],
            title="Comparison with AXA"
        )

        # Set color and opacity
        annot.set_colors(stroke=annot_data['color'], fill=annot_data['color'])
        annot.set_opacity(0.3)
        annot.update()

    # Save annotated PDF
    doc.save(output_path)
    doc.close()

    print(f"Annotated PDF saved to: {output_path}")
    print(f"Total annotations added: {len(annotations)}")


def main():
    """Main function to run the visualization."""
    # Paths
    base_dir = Path(__file__).parent
    output_dir = base_dir / "output" / "taxonomy_first"
    documents_dir = base_dir.parent / "documents"

    # Input files
    report_json = output_dir / "comparison_report_ProBTP_S4_P5_vs_AXA_Base_obligatoire.json"
    probtp_pdf = documents_dir / "File #3 - Panorama FMC 2025.pdf"
    axa_pdf = documents_dir / "File #1 - Laurent M - Conditions particulières - Socle AXA - SAE.pdf"

    # Output files - derive from report name
    report_base = report_json.stem.replace('comparison_report_', 'annotated_')
    probtp_output = output_dir / f"{report_base}_ProBTP.pdf"
    axa_output = output_dir / f"{report_base}_AXA.pdf"

    # Check if files exist
    if not report_json.exists():
        print(f"Error: Report JSON not found: {report_json}")
        return

    if not probtp_pdf.exists():
        print(f"Error: ProBTP PDF not found: {probtp_pdf}")
        return

    if not axa_pdf.exists():
        print(f"Error: AXA PDF not found: {axa_pdf}")
        return

    # Load comparison report
    print(f"Loading comparison report: {report_json.name}")
    report = load_comparison_report(report_json)

    # Build leaf analysis map
    print("Building leaf analysis map...")
    leaf_map = build_leaf_analysis_map(report)
    print(f"Found {len(leaf_map)} leaf analyses")

    # Extract and annotate ProBTP document
    print("\n--- Annotating ProBTP Document ---")
    print("Extracting ProBTP annotations...")
    probtp_annotations = extract_annotations(report, leaf_map, 'Panorama FMC')
    print(f"Found {len(probtp_annotations)} annotations")

    if probtp_annotations:
        print(f"Annotating PDF: {probtp_pdf.name}")
        annotate_pdf(probtp_pdf, probtp_annotations, probtp_output)
    else:
        print("Warning: No ProBTP annotations found.")

    # Extract and annotate AXA document
    print("\n--- Annotating AXA Document ---")
    print("Extracting AXA annotations...")
    axa_annotations = extract_annotations(report, leaf_map, 'Laurent M - Conditions')
    print(f"Found {len(axa_annotations)} annotations")

    if axa_annotations:
        print(f"Annotating PDF: {axa_pdf.name}")
        annotate_pdf(axa_pdf, axa_annotations, axa_output)
    else:
        print("Warning: No AXA annotations found.")

    print("\n" + "="*80)
    print("VISUALIZATION COMPLETE")
    print("="*80)
    if probtp_annotations:
        print(f"ProBTP: {probtp_output}")
    if axa_annotations:
        print(f"AXA:    {axa_output}")
    print("\nColor Legend (from ProBTP perspective):")
    print("  🟢 Dark Green:  ProBTP much better")
    print("  🟢 Light Green: ProBTP better")
    print("  🟡 Yellow:      Equivalent")
    print("  🔴 Light Red:   ProBTP worse")
    print("  🔴 Dark Red:    ProBTP much worse")


if __name__ == "__main__":
    main()
