"""
Analysis table validation and correction utilities.

Validates that analysis tables preserve the exact structure from alignment tables,
only adding the is_best annotation field.
"""

import json
from pathlib import Path
from typing import Any


def validate_table_structure_preserved(
    alignment_table: dict, analysis_table: dict
) -> tuple[bool, list[str]]:
    """
    Validate that analysis table preserves alignment table structure.

    Args:
        alignment_table: Table from alignment phase (after correction)
        analysis_table: Annotated table from analysis phase

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    # Check row count
    align_rows = alignment_table.get("rows", [])
    analysis_rows = analysis_table.get("rows", [])

    if len(align_rows) != len(analysis_rows):
        issues.append(
            f"Row count mismatch: alignment has {len(align_rows)}, analysis has {len(analysis_rows)}"
        )
        return False, issues

    # Check each row
    for row_idx, (align_row, analysis_row) in enumerate(zip(align_rows, analysis_rows)):
        align_cells = align_row.get("cells", [])
        analysis_cells = analysis_row.get("cells", [])

        # Check cell count
        if len(align_cells) != len(analysis_cells):
            issues.append(
                f"Row {row_idx + 1}: cell count mismatch ({len(align_cells)} → {len(analysis_cells)})"
            )
            continue

        # Check each cell
        for cell_idx, (align_cell, analysis_cell) in enumerate(
            zip(align_cells, analysis_cells)
        ):
            cell_loc = f"Row {row_idx + 1}, Cell {cell_idx + 1}"

            # Check value
            if align_cell.get("value") != analysis_cell.get("value"):
                issues.append(f"{cell_loc}: value changed")

            # Check rowspan/colspan
            if align_cell.get("rowspan") != analysis_cell.get("rowspan"):
                issues.append(
                    f"{cell_loc}: rowspan changed ({align_cell.get('rowspan')} → {analysis_cell.get('rowspan')})"
                )

            if align_cell.get("colspan") != analysis_cell.get("colspan"):
                issues.append(
                    f"{cell_loc}: colspan changed ({align_cell.get('colspan')} → {analysis_cell.get('colspan')})"
                )

            # Check type field preservation
            align_type = align_cell.get("type")
            analysis_type = analysis_cell.get("type")

            # If alignment omitted type, analysis should too
            if align_type is None and analysis_type is not None:
                issues.append(
                    f"{cell_loc}: type field added where it was omitted ('{analysis_type}')"
                )

            # If alignment had type, analysis should preserve it
            if align_type is not None and analysis_type != align_type:
                issues.append(
                    f"{cell_loc}: type changed ('{align_type}' → '{analysis_type}')"
                )

    is_valid = len(issues) == 0
    return is_valid, issues


def fix_analysis_table_structure(
    alignment_table: dict, analysis_table: dict
) -> dict:
    """
    Programmatically fix analysis table to match alignment structure.

    Args:
        alignment_table: Table from alignment phase (reference)
        analysis_table: Annotated table from analysis phase (to fix)

    Returns:
        Corrected analysis table
    """
    align_rows = alignment_table.get("rows", [])
    analysis_rows = analysis_table.get("rows", [])

    if len(align_rows) != len(analysis_rows):
        print(
            f"  ⚠ Cannot fix: row count mismatch ({len(align_rows)} vs {len(analysis_rows)})"
        )
        return analysis_table

    corrected_rows = []

    for row_idx, (align_row, analysis_row) in enumerate(zip(align_rows, analysis_rows)):
        align_cells = align_row.get("cells", [])
        analysis_cells = analysis_row.get("cells", [])

        if len(align_cells) != len(analysis_cells):
            print(
                f"  ⚠ Row {row_idx + 1}: Cannot fix cell count mismatch"
            )
            corrected_rows.append(analysis_row)
            continue

        corrected_cells = []

        for cell_idx, (align_cell, analysis_cell) in enumerate(
            zip(align_cells, analysis_cells)
        ):
            # Start with analysis cell (has is_best annotation)
            corrected_cell = {**analysis_cell}

            # Restore exact fields from alignment
            corrected_cell["value"] = align_cell.get("value")

            # Restore type field (or omit it)
            align_type = align_cell.get("type")
            if align_type is None:
                # Alignment omitted type - remove it from analysis
                corrected_cell.pop("type", None)
            else:
                # Alignment had type - preserve it
                corrected_cell["type"] = align_type

            # Restore rowspan/colspan
            align_rowspan = align_cell.get("rowspan")
            if align_rowspan is None:
                corrected_cell.pop("rowspan", None)
            else:
                corrected_cell["rowspan"] = align_rowspan

            align_colspan = align_cell.get("colspan")
            if align_colspan is None:
                corrected_cell.pop("colspan", None)
            else:
                corrected_cell["colspan"] = align_colspan

            # Restore sources structure
            align_sources = align_cell.get("sources")
            if align_sources is None:
                corrected_cell.pop("sources", None)
            else:
                # Deep copy sources to avoid reference issues
                corrected_cell["sources"] = {**align_sources}

            # Restore metadata
            align_metadata = align_cell.get("metadata")
            if align_metadata is None:
                corrected_cell.pop("metadata", None)
            else:
                corrected_cell["metadata"] = {**align_metadata}

            # Keep is_best from analysis (that's the whole point!)
            # It should already be in corrected_cell from the copy above

            corrected_cells.append(corrected_cell)

        corrected_rows.append({"cells": corrected_cells})

    corrected_table = {
        **analysis_table,
        "rows": corrected_rows,
    }

    return corrected_table


def verify_is_best_added(analysis_table: dict) -> tuple[bool, list[str]]:
    """
    Verify that is_best field was properly added to analysis table.

    Args:
        analysis_table: Annotated table from analysis phase

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    rows = analysis_table.get("rows", [])

    data_cells_without_is_best = 0
    dimension_cells_with_non_null_is_best = 0

    for row_idx, row in enumerate(rows):
        for cell_idx, cell in enumerate(row.get("cells", [])):
            cell_type = cell.get("type")
            is_best = cell.get("is_best")

            # Data cells should have is_best = true or false
            if cell_type == "data":
                if "is_best" not in cell:
                    data_cells_without_is_best += 1
                    if data_cells_without_is_best <= 3:  # Limit logging
                        issues.append(
                            f"Row {row_idx + 1}, Cell {cell_idx + 1}: data cell missing is_best field"
                        )

            # Dimension cells should have is_best = null or omitted
            elif cell_type is None:  # Dimension cell (type omitted)
                if is_best is not None and is_best is not False:
                    dimension_cells_with_non_null_is_best += 1
                    if dimension_cells_with_non_null_is_best <= 3:
                        issues.append(
                            f"Row {row_idx + 1}, Cell {cell_idx + 1}: dimension cell has is_best={is_best} (should be null)"
                        )

    if data_cells_without_is_best > 0:
        issues.append(
            f"Total: {data_cells_without_is_best} data cells missing is_best field"
        )

    if dimension_cells_with_non_null_is_best > 0:
        issues.append(
            f"Total: {dimension_cells_with_non_null_is_best} dimension cells with non-null is_best"
        )

    is_valid = len(issues) == 0
    return is_valid, issues


async def validate_and_fix_analysis_table(
    alignment_table: dict, analysis_table: dict, category: str
) -> tuple[dict, dict]:
    """
    Validate and fix analysis table to preserve alignment structure.

    Args:
        alignment_table: Table from alignment phase (reference)
        analysis_table: Annotated table from analysis phase
        category: Category name

    Returns:
        Tuple of (corrected_analysis_table, validation_log)
    """
    log: dict[str, Any] = {}

    # Save original analysis table
    tmp_dir = Path(__file__).parent.parent / "output" / "two_phase" / "tmp"
    original_path = tmp_dir / f"{category}_analysis_before_validation.json"
    with open(original_path, "w", encoding="utf-8") as f:
        json.dump(analysis_table, f, ensure_ascii=False, indent=2)

    # Step 1: Validate structure
    is_valid, structure_issues = validate_table_structure_preserved(
        alignment_table, analysis_table
    )

    log["initial_structure_valid"] = is_valid
    if structure_issues:
        log["initial_structure_issues"] = structure_issues
        print(f"  ⚠ Analysis table structure issues: {len(structure_issues)} found")
        for issue in structure_issues[:5]:  # Show first 5
            print(f"    - {issue}")

    # Step 2: Apply programmatic fixes
    if not is_valid:
        print(f"  → Applying programmatic fixes to analysis table")
        analysis_table = fix_analysis_table_structure(alignment_table, analysis_table)
        log["fixes_applied"] = ["programmatic_fix"]

        # Re-validate
        is_valid_after_fix, issues_after_fix = validate_table_structure_preserved(
            alignment_table, analysis_table
        )

        log["structure_valid_after_fix"] = is_valid_after_fix

        if not is_valid_after_fix and issues_after_fix:
            log["remaining_issues"] = issues_after_fix
            print(
                f"  ⚠ Warning: {len(issues_after_fix)} issues remain after programmatic fix"
            )
        elif is_valid_after_fix:
            print(f"  ✓ Structure corrected programmatically")

    # Step 3: Verify is_best annotations
    is_best_valid, is_best_issues = verify_is_best_added(analysis_table)
    log["is_best_valid"] = is_best_valid

    if not is_best_valid:
        log["is_best_issues"] = is_best_issues
        print(f"  ⚠ is_best annotation issues: {len(is_best_issues)} found")

    # Save final analysis table
    final_path = tmp_dir / f"{category}_analysis_after_validation.json"
    with open(final_path, "w", encoding="utf-8") as f:
        json.dump(analysis_table, f, ensure_ascii=False, indent=2)

    log["final_structure_valid"] = is_valid_after_fix if not is_valid else True
    log["final_is_best_valid"] = is_best_valid

    return analysis_table, log
