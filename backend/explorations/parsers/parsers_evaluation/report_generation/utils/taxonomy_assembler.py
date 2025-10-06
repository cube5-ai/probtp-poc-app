"""Utility for assembling comparison tables from taxonomy and extracted values.

This module provides programmatic table assembly:
1. Takes taxonomy structure + extracted values from both vendors
2. Builds ComparisonTable with proper rowspan/colspan based on hierarchy
3. No LLM involvement - purely mechanical transformation
"""

from typing import Any


def assemble_comparison_table(
    taxonomy_category: dict[str, Any],
    probtp_extraction: dict[str, Any],
    axa_extraction: dict[str, Any],
) -> dict[str, Any]:
    """
    Assemble a comparison table from taxonomy and extracted values.

    Args:
        taxonomy_category: Single category from ProBTPTaxonomy
        probtp_extraction: CategoryValueExtraction for ProBTP
        axa_extraction: CategoryValueExtraction for AXA

    Returns:
        ComparisonTable dict matching alignment_prompt.py schema
    """
    category_name = taxonomy_category["category_name"]
    category_id = taxonomy_category["category_id"]
    leaves = taxonomy_category["leaves"]

    probtp_level = probtp_extraction["policy_level"]
    axa_level = axa_extraction["policy_level"]

    # Build value lookup dicts for fast access
    probtp_values = {v["leaf_id"]: v for v in probtp_extraction["extracted_values"]}
    axa_values = {v["leaf_id"]: v for v in axa_extraction["extracted_values"]}

    # Determine column structure
    # Structure: [Catégorie, Sous-catégorie(s)..., Prestation, Part S.S., ProBTP Level, AXA Level]

    # Analyze taxonomy depth to determine dimension columns needed
    max_depth = max(len(leaf["path"]) for leaf in leaves)

    # Build template_row
    template_row = []

    # Dimension columns (based on max depth)
    # First element is category, last is prestation, middle are subcategories
    if max_depth == 1:
        # Just prestation
        template_row = ["Prestation"]
    elif max_depth == 2:
        # Category + Prestation
        template_row = ["Catégorie", "Prestation"]
    elif max_depth == 3:
        # Category + Subcategory + Prestation
        template_row = ["Catégorie", "Sous-catégorie", "Prestation"]
    elif max_depth == 4:
        # Category + Subcategory + Sub-subcategory + Prestation
        template_row = ["Catégorie", "Sous-catégorie", "Sous-sous-catégorie", "Prestation"]
    else:
        # General case: use generic labels
        template_row = [f"Niveau {i+1}" for i in range(max_depth)]

    # Add data columns
    template_row.extend(["Part S.S.", probtp_level, axa_level])

    total_columns = len(template_row)
    column_labels = [chr(65 + i) for i in range(total_columns)]  # A, B, C, ...

    # Build metadata
    metadata = {
        "category": category_name,
        "policy_levels": {
            "probtp": [probtp_level],
            "axa": [axa_level],
        },
        "total_columns": total_columns,
        "column_labels": column_labels,
    }

    # Build rows
    rows = []

    # Row 1: Header row
    header_row = _build_header_row(template_row, column_labels)
    rows.append(header_row)

    # Data rows: one per leaf
    for row_idx, leaf in enumerate(leaves):
        row_number = row_idx + 2  # row 1 is header, data starts at 2
        row = _build_data_row(
            leaf,
            probtp_values,
            axa_values,
            row_number,
            max_depth,
            total_columns,
            column_labels,
        )
        rows.append(row)

    # Assemble comparison table
    comparison_table = {
        "template_row": template_row,
        "metadata": metadata,
        "rows": rows,
    }

    return comparison_table


def _build_header_row(template_row: list[str], column_labels: list[str]) -> dict[str, Any]:
    """Build header row (row 1)."""
    total_columns = len(template_row)

    cells = []
    for i, col_name in enumerate(template_row):
        cell = {
            "id": f"{column_labels[i]}1",
            "value": col_name,
        }
        cells.append(cell)

    return {
        "row_number": 1,
        "inherited_from_above": [None] * total_columns,
        "cells": cells,
    }


def _build_data_row(
    leaf: dict[str, Any],
    probtp_values: dict[str, dict],
    axa_values: dict[str, dict],
    row_number: int,
    max_depth: int,
    total_columns: int,
    column_labels: list[str],
) -> dict[str, Any]:
    """
    Build a data row for a single leaf.

    Note: This is a simplified version that doesn't handle rowspan merging yet.
    Each leaf gets its own row with full path displayed.

    TODO: Add rowspan logic to merge cells with same category/subcategory values.
    """
    path = leaf["path"]
    leaf_id = leaf["leaf_id"]

    cells = []

    # Dimension columns: fill path elements
    for i in range(max_depth):
        cell_id = f"{column_labels[i]}{row_number}"
        if i < len(path):
            cell_value = path[i]
        else:
            cell_value = ""

        cell = {
            "id": cell_id,
            "value": cell_value,
        }
        cells.append(cell)

    # Part S.S. column (empty for now - could be extracted)
    ss_col_idx = max_depth
    cells.append({
        "id": f"{column_labels[ss_col_idx]}{row_number}",
        "value": "",
    })

    # ProBTP data column
    probtp_col_idx = max_depth + 1
    probtp_value = probtp_values.get(leaf_id)
    probtp_cell = _build_data_cell(
        probtp_value,
        f"{column_labels[probtp_col_idx]}{row_number}",
        "probtp"
    )
    cells.append(probtp_cell)

    # AXA data column
    axa_col_idx = max_depth + 2
    axa_value = axa_values.get(leaf_id)
    axa_cell = _build_data_cell(
        axa_value,
        f"{column_labels[axa_col_idx]}{row_number}",
        "axa"
    )
    cells.append(axa_cell)

    return {
        "row_number": row_number,
        "inherited_from_above": [None] * total_columns,
        "cells": cells,
    }


def _build_data_cell(
    value_data: dict[str, Any] | None,
    cell_id: str,
    vendor: str,
) -> dict[str, Any]:
    """Build a data cell from extracted value."""
    if not value_data:
        # No value found - mark as non couvert
        return {
            "id": cell_id,
            "value": "Non couvert",
            "type": "data",
        }

    coverage = value_data.get("coverage", "Non couvert")

    # Build display value with modifiers
    display_parts = [coverage]

    # Add frequency if present
    if value_data.get("frequency"):
        display_parts.append(f"({value_data['frequency']})")

    # Add cap if present
    if value_data.get("cap"):
        display_parts.append(f"[{value_data['cap']}]")

    display_value = " ".join(display_parts)

    # Build cell
    cell = {
        "id": cell_id,
        "value": display_value,
        "type": "data",
    }

    # Add metadata if conditions/restrictions exist
    metadata_parts = []

    if value_data.get("age_restriction"):
        metadata_parts.append(value_data["age_restriction"])

    if value_data.get("other_universal_conditions"):
        metadata_parts.append(value_data["other_universal_conditions"])

    if value_data.get("vendor_conditions"):
        for vc in value_data["vendor_conditions"]:
            cond_str = vc["description"]
            if vc.get("coverage_modifier"):
                cond_str += f": {vc['coverage_modifier']}"
            metadata_parts.append(cond_str)

    if metadata_parts:
        cell["metadata"] = {
            "conditions": " | ".join(metadata_parts)
        }

    # Add source tracking if present
    if value_data.get("source_cell_ids"):
        cell["sources"] = {
            vendor: value_data["source_cell_ids"]
        }

    return cell


def apply_rowspan_merging(comparison_table: dict[str, Any]) -> dict[str, Any]:
    """
    Apply rowspan merging to comparison table based on hierarchy.

    This function takes a comparison table where each row is independent
    and merges cells vertically when the same category/subcategory appears
    in consecutive rows.

    TODO: Implement this logic to reduce visual redundancy.
    For now, returns table unchanged.

    Args:
        comparison_table: ComparisonTable dict

    Returns:
        ComparisonTable dict with rowspan applied to dimension columns
    """
    # TODO: Implement rowspan merging logic
    # Algorithm:
    # 1. For each dimension column (left-most columns before data)
    # 2. Scan consecutive rows looking for identical values
    # 3. When found, merge into rowspan cell + virtual cells
    # 4. Update inherited_from_above arrays

    # For MVP, return unchanged
    return comparison_table


def validate_assembled_table(comparison_table: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate assembled comparison table structure.

    Args:
        comparison_table: ComparisonTable dict

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check basic structure
    if "metadata" not in comparison_table:
        errors.append("Missing metadata")
        return False, errors

    if "rows" not in comparison_table:
        errors.append("Missing rows")
        return False, errors

    metadata = comparison_table["metadata"]
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
    rows = comparison_table["rows"]
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

    is_valid = len(errors) == 0
    return is_valid, errors
