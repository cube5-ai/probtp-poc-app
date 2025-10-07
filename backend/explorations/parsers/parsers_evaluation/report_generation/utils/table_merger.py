"""Utility for programmatically merging projection alignment into ComparisonTable format."""

import copy


def merge_projection_to_comparison_table(
    projection_alignment: dict,
    probtp_table: dict,
    axa_table: dict,
    category: str
) -> dict:
    """
    Programmatically merge two CategoryTables (ProBTP + AXA projected) into ComparisonTable format.

    Args:
        projection_alignment: ProjectionAlignment dict with axa_projected_table
        probtp_table: Original ProBTP CategoryTable
        axa_table: Not used (kept for API compatibility)
        category: Category name

    Returns:
        ComparisonTable dict (using the schema from alignment_prompt.py)
    """
    # Extract the AXA projected table from projection_alignment
    axa_projected = projection_alignment.get("axa_projected_table", {})

    # Get metadata from both tables
    probtp_metadata = probtp_table.get("metadata", {})
    axa_metadata = axa_projected.get("metadata", {})

    probtp_levels = probtp_metadata.get("policy_levels", [])
    axa_levels = axa_metadata.get("policy_levels", [])

    # Get table structure from both tables
    probtp_structure = probtp_table.get("table_structure", {})
    axa_structure = axa_projected.get("table_structure", {})

    # Get rows from both tables
    probtp_rows = probtp_table.get("rows", [])
    axa_rows = axa_projected.get("rows", [])

    # Sanity check: both should have same number of rows (except possibly AXA-only additions)
    if len(probtp_rows) > len(axa_rows):
        print(f"⚠ Warning: ProBTP has more rows ({len(probtp_rows)}) than AXA projected ({len(axa_rows)})")

    # Build template_row for ComparisonTable
    # Structure: [Dimension cols..., Part S.S., ProBTP levels..., AXA levels...]
    probtp_template = probtp_structure.get("template_row", [])

    # Find where data columns start (after dimension columns and Part S.S.)
    # Typically: ["Catégorie", "Sous-catégorie", "Prestation", "Part S.S.", ...]
    template_row = []
    data_col_start_idx = None

    for i, col_name in enumerate(probtp_template):
        if any(level in col_name for level in probtp_levels):
            # Found first ProBTP level column
            data_col_start_idx = i
            break
        template_row.append(col_name)

    # If we didn't find data columns, assume they start after Part S.S.
    if data_col_start_idx is None:
        # Add ProBTP and AXA levels
        template_row.extend(probtp_levels)
        template_row.extend(axa_levels)
        data_col_start_idx = len(template_row) - len(probtp_levels) - len(axa_levels)
    else:
        # Add ProBTP and AXA levels
        template_row.extend(probtp_levels)
        template_row.extend(axa_levels)

    total_columns = len(template_row)
    column_labels = [chr(65 + i) for i in range(total_columns)]

    # Build ComparisonTable metadata
    metadata = {
        "category": category,
        "policy_levels": {
            "probtp": probtp_levels,
            "axa": axa_levels,
        },
        "total_columns": total_columns,
        "column_labels": column_labels,
    }

    # Build rows for ComparisonTable
    comparison_rows = []
    max_rows = max(len(probtp_rows), len(axa_rows))

    for row_idx in range(max_rows):
        row_number = row_idx + 1

        # Get corresponding rows from both tables (if they exist)
        probtp_row = probtp_rows[row_idx] if row_idx < len(probtp_rows) else None
        axa_row = axa_rows[row_idx] if row_idx < len(axa_rows) else None

        # Initialize row structure
        inherited_from_above = [None] * total_columns
        cells = []

        # If we have a ProBTP row, use its structure
        if probtp_row:
            probtp_cells = probtp_row.get("cells", [])
            probtp_inherited = probtp_row.get("inherited_from_above", [])
            axa_cells = axa_row.get("cells", []) if axa_row else []

            # Process dimension columns (copy from ProBTP)
            for col_idx in range(data_col_start_idx):
                if col_idx < len(probtp_cells):
                    cell = copy.deepcopy(probtp_cells[col_idx])
                    cells.append(cell)
                    if col_idx < len(probtp_inherited):
                        inherited_from_above[col_idx] = probtp_inherited[col_idx]
                else:
                    # Missing cell - create empty
                    cells.append({
                        "id": f"{column_labels[col_idx]}{row_number}",
                        "value": ""
                    })

            # Process ProBTP data columns
            probtp_data_start = data_col_start_idx
            for i, level in enumerate(probtp_levels):
                col_idx = data_col_start_idx + i
                source_col_idx = probtp_data_start + i

                if source_col_idx < len(probtp_cells):
                    cell = copy.deepcopy(probtp_cells[source_col_idx])
                    # Update cell ID to match new column position
                    cell["id"] = f"{column_labels[col_idx]}{row_number}"
                    cells.append(cell)
                else:
                    cells.append({
                        "id": f"{column_labels[col_idx]}{row_number}",
                        "value": "",
                        "type": "data"
                    })

            # Process AXA data columns
            axa_data_start = data_col_start_idx  # AXA data columns start at same position in axa_projected
            for i, level in enumerate(axa_levels):
                col_idx = data_col_start_idx + len(probtp_levels) + i
                source_col_idx = axa_data_start + i

                if axa_row and source_col_idx < len(axa_cells):
                    cell = copy.deepcopy(axa_cells[source_col_idx])
                    # Update cell ID to match new column position
                    cell["id"] = f"{column_labels[col_idx]}{row_number}"
                    # Update sources to use 'axa' key instead of 'source_cell_ids'
                    if "source_cell_ids" in cell:
                        cell["sources"] = {"axa": cell.pop("source_cell_ids")}
                    cells.append(cell)
                else:
                    cells.append({
                        "id": f"{column_labels[col_idx]}{row_number}",
                        "value": "Non couvert",
                        "type": "data"
                    })

        elif axa_row:
            # AXA-only row (no ProBTP equivalent)
            axa_cells = axa_row.get("cells", [])

            # Process dimension columns
            for col_idx in range(data_col_start_idx):
                if col_idx < len(axa_cells):
                    cell = copy.deepcopy(axa_cells[col_idx])
                    cells.append(cell)
                else:
                    cells.append({
                        "id": f"{column_labels[col_idx]}{row_number}",
                        "value": ""
                    })

            # ProBTP data columns (not covered)
            for i, level in enumerate(probtp_levels):
                col_idx = data_col_start_idx + i
                cells.append({
                    "id": f"{column_labels[col_idx]}{row_number}",
                    "value": "Non couvert",
                    "type": "data"
                })

            # AXA data columns
            axa_data_start = data_col_start_idx
            for i, level in enumerate(axa_levels):
                col_idx = data_col_start_idx + len(probtp_levels) + i
                source_col_idx = axa_data_start + i

                if source_col_idx < len(axa_cells):
                    cell = copy.deepcopy(axa_cells[source_col_idx])
                    cell["id"] = f"{column_labels[col_idx]}{row_number}"
                    if "source_cell_ids" in cell:
                        cell["sources"] = {"axa": cell.pop("source_cell_ids")}
                    cells.append(cell)
                else:
                    cells.append({
                        "id": f"{column_labels[col_idx]}{row_number}",
                        "value": "",
                        "type": "data"
                    })

        # Create comparison row
        comparison_row = {
            "row_number": row_number,
            "inherited_from_above": inherited_from_above,
            "cells": cells
        }

        comparison_rows.append(comparison_row)

    # Assemble ComparisonTable
    comparison_table = {
        "template_row": template_row,
        "metadata": metadata,
        "rows": comparison_rows
    }

    return comparison_table


def validate_comparison_table_structure(comparison_table: dict) -> tuple[bool, list[str]]:
    """
    Validate the structure of a ComparisonTable.

    Args:
        comparison_table: ComparisonTable dict

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check metadata
    metadata = comparison_table.get("metadata")
    if not metadata:
        errors.append("Missing metadata")
        return False, errors

    total_columns = metadata.get("total_columns")
    column_labels = metadata.get("column_labels", [])

    if not total_columns:
        errors.append("Missing total_columns in metadata")

    if len(column_labels) != total_columns:
        errors.append(f"column_labels length ({len(column_labels)}) != total_columns ({total_columns})")

    # Check template_row
    template_row = comparison_table.get("template_row", [])
    if len(template_row) != total_columns:
        errors.append(f"template_row length ({len(template_row)}) != total_columns ({total_columns})")

    # Check rows
    rows = comparison_table.get("rows", [])
    for i, row in enumerate(rows):
        row_number = row.get("row_number")
        if row_number != i + 1:
            errors.append(f"Row {i}: row_number ({row_number}) doesn't match expected ({i + 1})")

        inherited = row.get("inherited_from_above", [])
        if len(inherited) != total_columns:
            errors.append(f"Row {row_number}: inherited_from_above length ({len(inherited)}) != total_columns ({total_columns})")

        cells = row.get("cells", [])
        if len(cells) != total_columns:
            errors.append(f"Row {row_number}: cells length ({len(cells)}) != total_columns ({total_columns})")

        # Check cell IDs
        for j, cell in enumerate(cells):
            expected_id = f"{column_labels[j]}{row_number}"
            actual_id = cell.get("id")
            if actual_id != expected_id:
                errors.append(f"Row {row_number}, Cell {j}: ID mismatch (expected {expected_id}, got {actual_id})")

            # Check that cell has either value or ref
            has_value = "value" in cell
            has_ref = "ref" in cell
            if not has_value and not has_ref:
                errors.append(f"Cell {actual_id}: missing both 'value' and 'ref'")
            if has_value and has_ref:
                errors.append(f"Cell {actual_id}: has both 'value' and 'ref' (should have only one)")

    is_valid = len(errors) == 0
    return is_valid, errors
