"""
Table structure validation and correction utilities for enhanced schema.

Validates comparison tables with Excel-style cell IDs, inherited_from_above tracking,
and explicit span support. The enhanced schema provides multiple validation checkpoints
through redundant fields that must agree.
"""

import json
import re
from pathlib import Path
from typing import Any


def validate_enhanced_table_structure(table: dict) -> tuple[bool, list[str]]:
    """
    Validate table structure according to enhanced schema rules.

    Validation Rules:
    1. Structure consistency: inherited_from_above.length === total_columns === cells.length
    2. Cell IDs sequential: column_labels[i] + row_number
    3. inherited_from_above consistency: refs match inherited positions
    4. Rowspan occupies lists correct
    5. Colspan occupies lists and refs correct
    6. Every cell is either real (has value) or virtual (has ref)

    Args:
        table: ComparisonTable dict with enhanced schema

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    # Validate template_row
    template_row = table.get("template_row", [])
    if not template_row:
        issues.append("Missing template_row")

    metadata = table.get("metadata", {})
    total_columns = metadata.get("total_columns")
    column_labels = metadata.get("column_labels", [])
    rows = table.get("rows", [])

    if not total_columns:
        issues.append("Missing metadata.total_columns")
        return False, issues

    if len(column_labels) != total_columns:
        issues.append(
            f"column_labels length ({len(column_labels)}) != total_columns ({total_columns})"
        )

    if len(template_row) != total_columns:
        issues.append(
            f"template_row length ({len(template_row)}) != total_columns ({total_columns})"
        )

    # Validate each row
    for row_idx, row in enumerate(rows):
        row_number = row.get("row_number")
        inherited_from_above = row.get("inherited_from_above", [])
        cells = row.get("cells", [])

        # Rule 1: Structure consistency
        if row_number != row_idx + 1:
            issues.append(
                f"Row {row_idx}: row_number ({row_number}) != expected ({row_idx + 1})"
            )

        if len(inherited_from_above) != total_columns:
            issues.append(
                f"Row {row_number}: inherited_from_above length ({len(inherited_from_above)}) != total_columns ({total_columns})"
            )

        if len(cells) != total_columns:
            issues.append(
                f"Row {row_number}: cells length ({len(cells)}) != total_columns ({total_columns})"
            )
            continue  # Can't validate further if cell count is wrong

        # Rule 2 & 3: Cell IDs and inherited_from_above consistency
        for col_idx, cell in enumerate(cells):
            cell_id = cell.get("id")
            expected_id = column_labels[col_idx] + str(row_number)

            if cell_id != expected_id:
                issues.append(
                    f"Row {row_number}, Col {col_idx}: cell ID '{cell_id}' != expected '{expected_id}'"
                )

            # Rule 3: inherited_from_above consistency
            inherited_ref = inherited_from_above[col_idx]
            cell_ref = cell.get("ref")

            if inherited_ref is not None:
                # Position is inherited - cell should be virtual with matching ref
                if cell_ref != inherited_ref:
                    issues.append(
                        f"Cell {cell_id}: ref '{cell_ref}' != inherited_from_above '{inherited_ref}'"
                    )

                # Ref must point to earlier row
                if cell_ref:
                    ref_row_num = extract_row_number(cell_ref)
                    if ref_row_num and ref_row_num >= row_number:
                        issues.append(
                            f"Cell {cell_id}: ref '{cell_ref}' points to same/later row"
                        )

            # Rule 6: Every cell is either real (has value) or virtual (has ref)
            has_value = cell.get("value") is not None
            has_ref = cell.get("ref") is not None

            if has_value == has_ref:  # Both true or both false
                if has_value and has_ref:
                    issues.append(
                        f"Cell {cell_id}: has both value and ref (should have one or the other)"
                    )
                else:
                    issues.append(
                        f"Cell {cell_id}: has neither value nor ref (should have one)"
                    )

    # Rule 4 & 5: Validate spans (rowspan and colspan)
    for row_idx, row in enumerate(rows):
        row_number = row.get("row_number")
        cells = row.get("cells", [])

        for col_idx, cell in enumerate(cells):
            cell_id = cell.get("id")
            rowspan = cell.get("rowspan")
            colspan = cell.get("colspan")
            occupies = cell.get("occupies", [])
            has_value = cell.get("value") is not None

            # Only real cells can have spans
            if not has_value:
                continue

            # Rule 4: Rowspan validation
            if rowspan and rowspan > 1:
                expected_occupies_count = rowspan
                if colspan and colspan > 1:
                    expected_occupies_count = rowspan * colspan

                if len(occupies) != expected_occupies_count:
                    issues.append(
                        f"Cell {cell_id}: rowspan={rowspan}, colspan={colspan or 1}, but occupies has {len(occupies)} items (expected {expected_occupies_count})"
                    )

                if occupies and occupies[0] != cell_id:
                    issues.append(
                        f"Cell {cell_id}: occupies[0] should be '{cell_id}', got '{occupies[0]}'"
                    )

            # Rule 5: Colspan validation
            if colspan and colspan > 1:
                if not rowspan or rowspan == 1:
                    # Colspan only (no rowspan)
                    if len(occupies) != colspan:
                        issues.append(
                            f"Cell {cell_id}: colspan={colspan} but occupies has {len(occupies)} items"
                        )

                # Verify next (colspan-1) cells in same row have ref to this cell
                for offset in range(1, colspan):
                    if col_idx + offset < len(cells):
                        next_cell = cells[col_idx + offset]
                        if next_cell.get("ref") != cell_id:
                            issues.append(
                                f"Cell {cell_id}: colspan continuation cell {next_cell.get('id')} should have ref='{cell_id}'"
                            )

    is_valid = len(issues) == 0
    return is_valid, issues


def extract_row_number(cell_id: str) -> int | None:
    """Extract row number from Excel-style cell ID (e.g., 'A15' -> 15)."""
    if not cell_id:
        return None
    match = re.match(r"[A-Z]+(\d+)", cell_id)
    return int(match.group(1)) if match else None


def extract_column_letter(cell_id: str) -> str | None:
    """Extract column letter from Excel-style cell ID (e.g., 'A15' -> 'A')."""
    if not cell_id:
        return None
    match = re.match(r"([A-Z]+)\d+", cell_id)
    return match.group(1) if match else None


def remove_category_column(table: dict) -> tuple[dict, bool]:
    """
    Remove category column if present (adapted for enhanced schema).

    Detects if first cell in row 2 has rowspan = (total_rows - 1), indicating a category label
    that spans all data rows. If found, removes this cell and adjusts header row.

    Args:
        table: ComparisonTable dict with enhanced schema

    Returns:
        Tuple of (modified_table, was_removed)
    """
    rows = table.get("rows", [])
    metadata = table.get("metadata", {})
    total_columns = metadata.get("total_columns", 0)
    column_labels = metadata.get("column_labels", [])

    if len(rows) < 2 or total_columns == 0:
        return table, False

    row2 = rows[1]
    cells2 = row2.get("cells", [])

    if not cells2:
        return table, False

    # Check if first cell has rowspan covering all data rows
    first_cell = cells2[0]
    rowspan = first_cell.get("rowspan")
    has_value = first_cell.get("value") is not None

    if not has_value or not rowspan or rowspan != (len(rows) - 1):
        return table, False

    print(f"  → Removing category column (rowspan={rowspan})")

    # This is a category column - need to:
    # 1. Remove first column from all rows
    # 2. Update total_columns and column_labels
    # 3. Update all cell IDs to shift left
    # 4. Update inherited_from_above arrays
    # 5. Update occupies lists

    new_total_columns = total_columns - 1
    new_column_labels = column_labels[1:]  # Remove first column (A)

    new_rows = []

    for row_idx, row in enumerate(rows):
        row_number = row.get("row_number")
        old_cells = row.get("cells", [])
        old_inherited = row.get("inherited_from_above", [])

        # Skip first cell, shift rest
        new_cells = []
        for col_idx in range(1, len(old_cells)):
            old_cell = old_cells[col_idx]
            new_cell = {**old_cell}

            # Update cell ID (shift column left)
            old_id = old_cell.get("id")
            new_id = new_column_labels[col_idx - 1] + str(row_number)
            new_cell["id"] = new_id

            # Update ref if present (shift column letter)
            if "ref" in new_cell and new_cell["ref"]:
                old_ref = new_cell["ref"]
                ref_row = extract_row_number(old_ref)
                ref_col_letter = extract_column_letter(old_ref)
                # Shift column: A->skip, B->A, C->B, etc.
                old_col_idx = column_labels.index(ref_col_letter) if ref_col_letter in column_labels else -1
                if old_col_idx > 0:
                    new_ref = new_column_labels[old_col_idx - 1] + str(ref_row)
                    new_cell["ref"] = new_ref

            # Update occupies list (shift column letters)
            if "occupies" in new_cell and new_cell["occupies"]:
                new_occupies = []
                for occupy_id in new_cell["occupies"]:
                    occupy_row = extract_row_number(occupy_id)
                    occupy_col = extract_column_letter(occupy_id)
                    old_col_idx = column_labels.index(occupy_col) if occupy_col in column_labels else -1
                    if old_col_idx > 0:
                        new_occupy_id = new_column_labels[old_col_idx - 1] + str(occupy_row)
                        new_occupies.append(new_occupy_id)
                new_cell["occupies"] = new_occupies if new_occupies else None

            new_cells.append(new_cell)

        # Update inherited_from_above (remove first element, update refs)
        new_inherited = []
        for col_idx in range(1, len(old_inherited)):
            old_ref = old_inherited[col_idx]
            if old_ref:
                ref_row = extract_row_number(old_ref)
                ref_col = extract_column_letter(old_ref)
                old_col_idx = column_labels.index(ref_col) if ref_col in column_labels else -1
                if old_col_idx > 0:
                    new_ref = new_column_labels[old_col_idx - 1] + str(ref_row)
                    new_inherited.append(new_ref)
                else:
                    new_inherited.append(None)
            else:
                new_inherited.append(None)

        new_row = {
            "row_number": row_number,
            "inherited_from_above": new_inherited,
            "cells": new_cells,
        }
        new_rows.append(new_row)

    new_metadata = {
        **metadata,
        "total_columns": new_total_columns,
        "column_labels": new_column_labels,
    }

    new_table = {
        **table,
        "metadata": new_metadata,
        "rows": new_rows,
    }

    return new_table, True


async def validate_and_fix_table(
    table: dict, category: str, max_iterations: int = 3
) -> tuple[dict, dict]:
    """
    Validate and fix table structure with enhanced schema.

    Args:
        table: ComparisonTable dict with enhanced schema
        category: Category name (for file naming)
        max_iterations: Maximum correction iterations

    Returns:
        Tuple of (corrected_table, validation_log)
    """
    from pathlib import Path

    log: dict[str, Any] = {}

    # Save original table
    tmp_dir = Path(__file__).parent.parent / "output" / "two_phase" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    original_path = tmp_dir / f"{category}_table_before_correction.json"
    with open(original_path, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=2)

    print(f"  → Validating table structure for '{category}'")

    # NOTE: Category column removal disabled - it messes up cell IDs
    # The LLM should generate the correct structure from the start
    # table, was_removed = remove_category_column(table)
    # if was_removed:
    #     log["category_column_removed"] = True

    # Validate enhanced schema
    is_valid, issues = validate_enhanced_table_structure(table)

    log["initial_valid"] = is_valid
    if issues:
        log["initial_issues"] = issues
        print(f"  ⚠ Found {len(issues)} structural issues:")
        for issue in issues[:10]:  # Show first 10
            print(f"    - {issue}")

    if not is_valid:
        print(f"  ⚠ Enhanced schema validation failed - table may need LLM re-generation")
        log["recommendation"] = "Re-run alignment with enhanced schema instructions"

    # Save corrected table
    corrected_path = tmp_dir / f"{category}_table_after_correction.json"
    with open(corrected_path, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=2)

    log["final_valid"] = is_valid
    log["final_issue_count"] = len(issues)

    if is_valid:
        print(f"  ✓ Table structure validated successfully")
    else:
        print(
            f"  ⚠ Table structure has {len(issues)} remaining issues (see validation log)"
        )

    return table, log
