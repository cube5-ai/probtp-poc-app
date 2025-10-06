"""
Analysis table validation and correction utilities for enhanced schema.

Validates that analysis tables preserve the exact enhanced structure from alignment tables,
only adding the is_best annotation field.
"""

import json
from pathlib import Path
from typing import Any


def validate_table_structure_preserved(
    alignment_table: dict, analysis_table: dict
) -> tuple[bool, list[str]]:
    """
    Validate that analysis table preserves alignment table's enhanced structure.

    Checks that ALL enhanced schema fields are preserved:
    - Metadata: total_columns, column_labels
    - Rows: row_number, inherited_from_above
    - Cells: id, value, type, rowspan, colspan, occupies, ref, sources, metadata

    Args:
        alignment_table: Table from alignment phase (after correction)
        analysis_table: Annotated table from analysis phase

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    # Check template_row preservation
    align_template = alignment_table.get("template_row", [])
    analysis_template = analysis_table.get("template_row", [])

    if align_template != analysis_template:
        issues.append(
            f"template_row changed: {align_template} → {analysis_template}"
        )

    # Check metadata preservation
    align_meta = alignment_table.get("metadata", {})
    analysis_meta = analysis_table.get("metadata", {})

    if align_meta.get("total_columns") != analysis_meta.get("total_columns"):
        issues.append(
            f"total_columns changed: {align_meta.get('total_columns')} → {analysis_meta.get('total_columns')}"
        )

    if align_meta.get("column_labels") != analysis_meta.get("column_labels"):
        issues.append(
            f"column_labels changed: {align_meta.get('column_labels')} → {analysis_meta.get('column_labels')}"
        )

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
        # Check row_number
        if align_row.get("row_number") != analysis_row.get("row_number"):
            issues.append(
                f"Row {row_idx}: row_number changed ({align_row.get('row_number')} → {analysis_row.get('row_number')})"
            )

        # Check inherited_from_above
        if align_row.get("inherited_from_above") != analysis_row.get(
            "inherited_from_above"
        ):
            issues.append(
                f"Row {row_idx + 1}: inherited_from_above changed"
            )

        # Check cells
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
            cell_id = align_cell.get("id", f"Row{row_idx+1}Cell{cell_idx}")

            # Check id
            if align_cell.get("id") != analysis_cell.get("id"):
                issues.append(
                    f"{cell_id}: id changed ({align_cell.get('id')} → {analysis_cell.get('id')})"
                )

            # Check value
            if align_cell.get("value") != analysis_cell.get("value"):
                issues.append(f"{cell_id}: value changed")

            # Check type field preservation
            align_type = align_cell.get("type")
            analysis_type = analysis_cell.get("type")

            # If alignment omitted type, analysis should too
            if align_type is None and analysis_type is not None:
                issues.append(
                    f"{cell_id}: type field added where it was omitted ('{analysis_type}')"
                )

            # If alignment had type, analysis should preserve it
            if align_type is not None and analysis_type != align_type:
                issues.append(
                    f"{cell_id}: type changed ('{align_type}' → '{analysis_type}')"
                )

            # Check rowspan/colspan/occupies
            if align_cell.get("rowspan") != analysis_cell.get("rowspan"):
                issues.append(
                    f"{cell_id}: rowspan changed ({align_cell.get('rowspan')} → {analysis_cell.get('rowspan')})"
                )

            if align_cell.get("colspan") != analysis_cell.get("colspan"):
                issues.append(
                    f"{cell_id}: colspan changed ({align_cell.get('colspan')} → {analysis_cell.get('colspan')})"
                )

            if align_cell.get("occupies") != analysis_cell.get("occupies"):
                issues.append(
                    f"{cell_id}: occupies changed"
                )

            # Check ref (virtual cells)
            if align_cell.get("ref") != analysis_cell.get("ref"):
                issues.append(
                    f"{cell_id}: ref changed ({align_cell.get('ref')} → {analysis_cell.get('ref')})"
                )

            # Check sources preservation (exact structure)
            align_sources = align_cell.get("sources")
            analysis_sources = analysis_cell.get("sources")

            if align_sources != analysis_sources:
                issues.append(
                    f"{cell_id}: sources structure changed"
                )

            # Check metadata preservation
            align_metadata = align_cell.get("metadata")
            analysis_metadata = analysis_cell.get("metadata")

            if align_metadata != analysis_metadata:
                issues.append(
                    f"{cell_id}: metadata changed"
                )

    is_valid = len(issues) == 0
    return is_valid, issues


def fix_analysis_table_structure(
    alignment_table: dict, analysis_table: dict
) -> dict:
    """
    Programmatically fix analysis table to match alignment's enhanced structure.

    Restores all enhanced schema fields from alignment while keeping is_best from analysis.

    Args:
        alignment_table: Table from alignment phase (reference)
        analysis_table: Annotated table from analysis phase (to fix)

    Returns:
        Corrected analysis table
    """
    align_rows = alignment_table.get("rows", [])
    analysis_rows = analysis_table.get("rows", [])
    align_meta = alignment_table.get("metadata", {})

    if len(align_rows) != len(analysis_rows):
        print(
            f"  ⚠ Cannot fix: row count mismatch ({len(align_rows)} vs {len(analysis_rows)})"
        )
        return analysis_table

    # Fix metadata
    corrected_metadata = {
        **analysis_table.get("metadata", {}),
        "total_columns": align_meta.get("total_columns"),
        "column_labels": align_meta.get("column_labels"),
    }

    # Preserve template_row from alignment
    corrected_template_row = alignment_table.get("template_row", [])

    corrected_rows = []

    for row_idx, (align_row, analysis_row) in enumerate(zip(align_rows, analysis_rows)):
        align_cells = align_row.get("cells", [])
        analysis_cells = analysis_row.get("cells", [])

        if len(align_cells) != len(analysis_cells):
            print(f"  ⚠ Row {row_idx + 1}: Cannot fix cell count mismatch")
            corrected_rows.append(analysis_row)
            continue

        corrected_cells = []

        for cell_idx, (align_cell, analysis_cell) in enumerate(
            zip(align_cells, analysis_cells)
        ):
            # Start with alignment cell (correct structure)
            corrected_cell = {**align_cell}

            # Add is_best from analysis (the only field analysis should add)
            if "is_best" in analysis_cell:
                corrected_cell["is_best"] = analysis_cell["is_best"]

            corrected_cells.append(corrected_cell)

        corrected_row = {
            "row_number": align_row.get("row_number"),
            "inherited_from_above": align_row.get("inherited_from_above"),
            "cells": corrected_cells,
        }
        corrected_rows.append(corrected_row)

    corrected_table = {
        **analysis_table,
        "template_row": corrected_template_row,
        "metadata": corrected_metadata,
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
            cell_id = cell.get("id", f"Row{row_idx+1}Cell{cell_idx}")
            cell_type = cell.get("type")
            is_best = cell.get("is_best")
            has_value = cell.get("value") is not None

            # Only check real cells (not virtual cells with ref)
            if not has_value:
                continue

            # Data cells should have is_best = true or false
            if cell_type == "data":
                if "is_best" not in cell:
                    data_cells_without_is_best += 1
                    if data_cells_without_is_best <= 3:  # Limit logging
                        issues.append(
                            f"{cell_id}: data cell missing is_best field"
                        )

            # Dimension cells should have is_best = null or omitted
            elif cell_type is None:  # Dimension cell (type omitted)
                if is_best is not None and is_best is not False:
                    dimension_cells_with_non_null_is_best += 1
                    if dimension_cells_with_non_null_is_best <= 3:
                        issues.append(
                            f"{cell_id}: dimension cell has is_best={is_best} (should be null or false)"
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
    Validate and fix analysis table to preserve alignment's enhanced structure.

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
    tmp_dir.mkdir(parents=True, exist_ok=True)

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
