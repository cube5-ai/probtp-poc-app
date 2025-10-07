"""
Auto-fix table structure by leveraging schema redundancy.

This utility performs bidirectional validation:
1. PHASE 1: Real cells with rowspan/colspan → Generate missing virtual cells and inherited_from_above
2. PHASE 2: Virtual cells with ref → Infer missing rowspan/colspan on real cells
"""

import re
from typing import Any
import copy


def fix_table_structure(table: dict) -> tuple[dict, list[str]]:
    """
    Auto-fix table structure using bidirectional validation.

    The schema has redundancy that we leverage:
    - Real cells with rowspan/colspan should list all occupied cell IDs in `occupies`
    - Virtual cells should have `ref` pointing to the real cell that occupies their position
    - inherited_from_above tracks active rowspans

    This function performs two phases:
    1. PHASE 1 (Priority): Real cells with spans → Add missing virtual cells
    2. PHASE 2 (Fallback): Virtual cells → Infer missing spans on real cells

    Args:
        table: ComparisonTable or CategoryTable dict

    Returns:
        Tuple of (fixed_table, list_of_fixes_applied)
    """
    fixed_table = copy.deepcopy(table)
    fixes = []

    rows = fixed_table.get("rows", [])
    if not rows:
        return fixed_table, fixes

    # Get table structure metadata
    metadata = fixed_table.get("metadata", {})
    table_structure = fixed_table.get("table_structure", {})

    # Try both locations for total_columns and column_labels
    total_columns = table_structure.get("total_columns") or metadata.get("total_columns", 0)
    column_labels = table_structure.get("column_labels") or metadata.get("column_labels", [])

    if not total_columns or not column_labels:
        fixes.append("⚠ Cannot fix: missing total_columns or column_labels")
        return fixed_table, fixes

    # PHASE 1: Real cells with rowspan/colspan → Generate missing virtual cells
    phase1_fixes = _fix_from_real_cells_to_virtual(rows, total_columns, column_labels)
    fixes.extend(phase1_fixes)

    # PHASE 2: Virtual cells → Infer missing rowspan/colspan on real cells
    phase2_fixes = _fix_from_virtual_cells_to_real(rows)
    fixes.extend(phase2_fixes)

    # PHASE 3: Update inherited_from_above arrays based on rowspans
    phase3_fixes = _fix_inherited_from_above(rows, total_columns, column_labels)
    fixes.extend(phase3_fixes)

    return fixed_table, fixes


def _fix_from_real_cells_to_virtual(
    rows: list[dict],
    total_columns: int,
    column_labels: list[str]
) -> list[str]:
    """
    PHASE 1: For cells with rowspan/colspan, ensure virtual cells exist.

    If a cell has rowspan=3, there should be virtual cells in the next 2 rows
    with ref pointing back to the original cell.
    """
    fixes = []

    # Build index: row_number -> {cell_id -> cell}
    row_index = {}
    for row in rows:
        row_num = row.get("row_number")
        row_index[row_num] = {}
        for cell in row.get("cells", []):
            cell_id = cell.get("id")
            row_index[row_num][cell_id] = cell

    # Find all cells with spans
    for row in rows:
        row_num = row.get("row_number")
        cells = row.get("cells", [])

        for cell in cells:
            # Skip virtual cells
            if cell.get("ref"):
                continue

            cell_id = cell.get("id")
            rowspan = cell.get("rowspan", 1)
            colspan = cell.get("colspan", 1)

            # Calculate expected occupies list
            expected_occupies = _calculate_occupies_from_span(
                cell_id, rowspan, colspan, column_labels
            )

            # Fix occupies if missing or incorrect
            current_occupies = cell.get("occupies")
            if rowspan > 1 or colspan > 1:
                if not current_occupies or sorted(current_occupies, key=_sort_cell_id) != sorted(expected_occupies, key=_sort_cell_id):
                    cell["occupies"] = expected_occupies
                    fixes.append(f"[Phase1] Fixed occupies for {cell_id}: {expected_occupies}")

            # For each cell in occupies (except the original), ensure virtual cell exists
            for occupied_id in expected_occupies:
                if occupied_id == cell_id:
                    continue  # Skip the original cell

                # Parse occupied cell
                occupied_row_num = _parse_row_number(occupied_id)

                if occupied_row_num not in row_index:
                    fixes.append(f"[Phase1] ⚠ Warning: Row {occupied_row_num} doesn't exist for occupied cell {occupied_id}")
                    continue

                occupied_cell = row_index[occupied_row_num].get(occupied_id)

                if not occupied_cell:
                    # Cell doesn't exist at all - this shouldn't happen, but skip
                    fixes.append(f"[Phase1] ⚠ Warning: Cell {occupied_id} doesn't exist in row {occupied_row_num}")
                    continue

                # Check if it's already a virtual cell pointing to the right place
                current_ref = occupied_cell.get("ref")

                if current_ref != cell_id:
                    # Need to make it virtual or fix the ref
                    if current_ref:
                        fixes.append(f"[Phase1] Fixed ref for {occupied_id}: {current_ref} -> {cell_id}")
                    else:
                        fixes.append(f"[Phase1] Added ref for {occupied_id} -> {cell_id}")

                    # Convert to virtual cell
                    occupied_cell["ref"] = cell_id

                    # Remove value from virtual cells (keep only ref)
                    if "value" in occupied_cell:
                        del occupied_cell["value"]
                    if "type" in occupied_cell:
                        del occupied_cell["type"]
                    if "rowspan" in occupied_cell:
                        del occupied_cell["rowspan"]
                    if "colspan" in occupied_cell:
                        del occupied_cell["colspan"]
                    if "occupies" in occupied_cell:
                        del occupied_cell["occupies"]

    return fixes


def _fix_from_virtual_cells_to_real(rows: list[dict]) -> list[str]:
    """
    PHASE 2: For virtual cells with ref, ensure real cell has correct rowspan/colspan.

    This is the fallback: if the LLM created virtual cells but forgot the rowspan,
    we infer it from the virtual cells.
    """
    fixes = []

    # Build a map of which cells are referenced by virtual cells
    # Format: {cell_id: [list of cell_ids that reference it]}
    ref_map: dict[str, list[str]] = {}

    for row in rows:
        for cell in row.get("cells", []):
            ref = cell.get("ref")
            if ref:
                # This is a virtual cell
                virtual_id = cell.get("id")
                if ref not in ref_map:
                    ref_map[ref] = []
                ref_map[ref].append(virtual_id)

    # Now fix real cells based on ref_map
    for row in rows:
        for cell in row.get("cells", []):
            cell_id = cell.get("id")

            # Skip virtual cells
            if cell.get("ref"):
                continue

            # Check if this cell is referenced by virtual cells
            if cell_id in ref_map:
                referenced_by = ref_map[cell_id]

                # Calculate what occupies list should be
                expected_occupies = sorted([cell_id] + referenced_by, key=_sort_cell_id)

                # Calculate rowspan and colspan from occupies
                expected_rowspan, expected_colspan = _calculate_span_from_occupies(
                    cell_id, expected_occupies
                )

                # Fix occupies if missing or incorrect
                current_occupies = cell.get("occupies")
                if current_occupies is None or sorted(current_occupies, key=_sort_cell_id) != expected_occupies:
                    cell["occupies"] = expected_occupies
                    fixes.append(f"[Phase2] Fixed occupies for {cell_id}: {expected_occupies}")

                # Fix rowspan if missing or incorrect
                current_rowspan = cell.get("rowspan")
                if expected_rowspan > 1:
                    if current_rowspan != expected_rowspan:
                        cell["rowspan"] = expected_rowspan
                        fixes.append(f"[Phase2] Fixed rowspan for {cell_id}: {current_rowspan} -> {expected_rowspan}")

                # Fix colspan if missing or incorrect
                current_colspan = cell.get("colspan")
                if expected_colspan > 1:
                    if current_colspan != expected_colspan:
                        cell["colspan"] = expected_colspan
                        fixes.append(f"[Phase2] Fixed colspan for {cell_id}: {current_colspan} -> {expected_colspan}")

    return fixes


def _fix_inherited_from_above(
    rows: list[dict],
    total_columns: int,
    column_labels: list[str]
) -> list[str]:
    """
    PHASE 3: Update inherited_from_above arrays based on active rowspans.

    For each row, check which cells from previous rows are still active
    (have rowspan extending into this row).
    """
    fixes = []

    # Track active rowspans: {column_index: cell_id_that_spans_here}
    active_spans = {}

    for row in rows:
        row_num = row.get("row_number")
        cells = row.get("cells", [])

        # Build expected inherited_from_above
        expected_inherited = [None] * total_columns

        # First, carry over active spans from previous rows
        for col_idx in range(total_columns):
            if col_idx in active_spans:
                # Check if span is still active for this row
                spanning_cell_id = active_spans[col_idx]
                # We'll update this after processing current row's cells
                expected_inherited[col_idx] = spanning_cell_id

        # Now process this row's cells
        for col_idx, cell in enumerate(cells):
            if col_idx >= total_columns:
                break

            cell_id = cell.get("id")
            ref = cell.get("ref")

            if ref:
                # Virtual cell - should inherit from the ref
                expected_inherited[col_idx] = ref
            else:
                # Real cell - starts a new span
                rowspan = cell.get("rowspan", 1)

                if rowspan > 1:
                    # This cell spans multiple rows
                    # Mark it as active for the next (rowspan-1) rows
                    end_row = row_num + rowspan - 1
                    active_spans[col_idx] = (cell_id, end_row)
                else:
                    # Clear any active span at this column
                    if col_idx in active_spans:
                        del active_spans[col_idx]

                # Current row doesn't inherit at this position
                expected_inherited[col_idx] = None

        # Clean up expired spans
        expired_cols = []
        for col_idx, (spanning_id, end_row) in list(active_spans.items()):
            if row_num > end_row:
                expired_cols.append(col_idx)

        for col_idx in expired_cols:
            del active_spans[col_idx]

        # Update active spans for next iteration
        new_active_spans = {}
        for col_idx, value in active_spans.items():
            if isinstance(value, tuple):
                spanning_id, end_row = value
                if row_num < end_row:
                    new_active_spans[col_idx] = (spanning_id, end_row)
        active_spans = new_active_spans

        # Compare with current inherited_from_above
        current_inherited = row.get("inherited_from_above", [])

        if current_inherited != expected_inherited:
            row["inherited_from_above"] = expected_inherited
            # Only log if there's a meaningful difference
            if current_inherited and any(a != b for a, b in zip(current_inherited, expected_inherited)):
                fixes.append(f"[Phase3] Fixed inherited_from_above for row {row_num}")

    return fixes


def _calculate_occupies_from_span(
    cell_id: str,
    rowspan: int,
    colspan: int,
    column_labels: list[str]
) -> list[str]:
    """
    Calculate the occupies list from rowspan and colspan.

    Args:
        cell_id: Starting cell ID (e.g., "E2")
        rowspan: Number of rows spanned
        colspan: Number of columns spanned
        column_labels: List of column labels (e.g., ["A", "B", "C", ...])

    Returns:
        List of all cell IDs occupied
    """
    match = re.match(r"([A-Z]+)(\d+)", cell_id)
    if not match:
        return [cell_id]

    start_col, start_row = match.groups()
    start_row = int(start_row)
    start_col_idx = column_labels.index(start_col) if start_col in column_labels else 0

    occupies = []
    for row_offset in range(rowspan):
        for col_offset in range(colspan):
            row_num = start_row + row_offset
            col_idx = start_col_idx + col_offset

            if col_idx < len(column_labels):
                col_label = column_labels[col_idx]
                occupies.append(f"{col_label}{row_num}")

    return sorted(occupies, key=_sort_cell_id)


def _calculate_span_from_occupies(cell_id: str, occupies: list[str]) -> tuple[int, int]:
    """
    Calculate rowspan and colspan from the occupies list.

    Args:
        cell_id: The cell ID (e.g., "E2")
        occupies: List of all cell IDs occupied (e.g., ["E2", "E3", "E4", "E5"])

    Returns:
        Tuple of (rowspan, colspan)
    """
    # Parse cell_id
    match = re.match(r"([A-Z]+)(\d+)", cell_id)
    if not match:
        return 1, 1

    start_col, start_row = match.groups()
    start_row = int(start_row)

    # Find the range of rows and columns in occupies
    rows = set()
    cols = set()

    for occupied_id in occupies:
        match = re.match(r"([A-Z]+)(\d+)", occupied_id)
        if match:
            col, row = match.groups()
            rows.add(int(row))
            cols.add(col)

    # Calculate span
    rowspan = max(rows) - min(rows) + 1 if rows else 1
    colspan = len(cols)

    return rowspan, colspan


def _parse_row_number(cell_id: str) -> int:
    """Extract row number from cell ID (e.g., "E2" -> 2)."""
    match = re.match(r"[A-Z]+(\d+)", cell_id)
    if match:
        return int(match.group(1))
    return 0


def _sort_cell_id(cell_id: str) -> tuple[int, str]:
    """
    Sort key for cell IDs (e.g., "A1", "B2", "AA10").
    Returns (row_number, column_letter) for sorting.
    """
    match = re.match(r"([A-Z]+)(\d+)", cell_id)
    if match:
        col, row = match.groups()
        return (int(row), col)
    return (0, cell_id)


def validate_and_fix_all_tables(data: dict) -> tuple[dict, dict[str, list[str]]]:
    """
    Validate and fix all tables in a report data structure.

    This works on the full report JSON structure, fixing:
    - annotated_table in each analysis
    - comparison_table in alignments (if present)

    Args:
        data: Full report data (e.g., comparison_report JSON)

    Returns:
        Tuple of (fixed_data, dict mapping table_name to list_of_fixes)
    """
    fixed_data = copy.deepcopy(data)
    all_fixes = {}

    # Fix annotated tables in analyses
    analyses = fixed_data.get("analyses", [])
    for analysis in analyses:
        category = analysis.get("category", "unknown")
        annotated_table = analysis.get("annotated_table")

        if annotated_table:
            fixed_table, fixes = fix_table_structure(annotated_table)
            if fixes:
                all_fixes[f"{category}_annotated_table"] = fixes
                analysis["annotated_table"] = fixed_table

    # Fix alignment tables if present
    alignments = fixed_data.get("alignments", [])
    for alignment in alignments:
        category = alignment.get("category", "unknown")
        comparison_table = alignment.get("comparison_table")

        if comparison_table:
            fixed_table, fixes = fix_table_structure(comparison_table)
            if fixes:
                all_fixes[f"{category}_comparison_table"] = fixes
                alignment["comparison_table"] = fixed_table

    return fixed_data, all_fixes
