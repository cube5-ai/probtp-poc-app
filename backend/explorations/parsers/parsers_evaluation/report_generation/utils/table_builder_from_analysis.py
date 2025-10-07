"""Build comparison table from analysis results and comparison document.

This module creates the final ComparisonTable structure from taxonomy-first analysis,
using leaf comparisons to add is_best annotations to cells.
"""

from typing import Any

from prompts.taxonomy_first.analysis_prompt import TaxonomyFirstAnalysisOutput


def build_table_from_analysis(
    comparison_document: dict[str, Any],
    analysis: TaxonomyFirstAnalysisOutput,
) -> dict[str, Any]:
    """
    Build ComparisonTable from comparison document and analysis results.

    Args:
        comparison_document: ComparisonDocument dict with full leaf data
        analysis: TaxonomyFirstAnalysisOutput with leaf comparisons

    Returns:
        ComparisonTable dict with Excel-style IDs, rowspan/colspan, and is_best annotations
    """
    category_name = comparison_document.get("category_name", "")
    probtp_level = comparison_document.get("probtp_policy_level", "")
    axa_level = comparison_document.get("axa_policy_level", "")
    leaves = comparison_document.get("leaves", [])

    # Build leaf analysis lookup by leaf_id
    leaf_analysis_map = {
        la.leaf_id: la for la in analysis.leaf_comparisons
    }

    # Determine column structure
    max_depth = max(len(leaf["path"]) for leaf in leaves) if leaves else 1

    # Build template_row
    template_row = _build_template_row(max_depth, probtp_level, axa_level)

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
        leaf_analysis = leaf_analysis_map.get(leaf["leaf_id"])

        row = _build_data_row(
            leaf,
            leaf_analysis,
            row_number,
            max_depth,
            total_columns,
            column_labels,
        )
        rows.append(row)

    # Apply rowspan merging for hierarchical display
    rows = _apply_rowspan_merging(rows, max_depth, total_columns, column_labels)

    # Assemble comparison table
    comparison_table = {
        "template_row": template_row,
        "metadata": metadata,
        "rows": rows,
    }

    return comparison_table


def _build_template_row(max_depth: int, probtp_level: str, axa_level: str) -> list[str]:
    """Build template row based on taxonomy depth."""
    template_row = []

    # Dimension columns (based on max depth)
    if max_depth == 1:
        template_row = ["Prestation"]
    elif max_depth == 2:
        template_row = ["Catégorie", "Prestation"]
    elif max_depth == 3:
        template_row = ["Catégorie", "Sous-catégorie", "Prestation"]
    elif max_depth == 4:
        template_row = ["Catégorie", "Sous-catégorie", "Sous-sous-catégorie", "Prestation"]
    else:
        # General case: use generic labels
        template_row = [f"Niveau {i+1}" for i in range(max_depth)]

    # Add data columns
    template_row.extend(["Part S.S.", probtp_level, axa_level])

    return template_row


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
    leaf_analysis: Any,  # LeafAnalysis or None
    row_number: int,
    max_depth: int,
    total_columns: int,
    column_labels: list[str],
) -> dict[str, Any]:
    """Build a data row for a single leaf with is_best annotations and full metadata."""
    path = leaf["path"]
    probtp_value = leaf.get("probtp")
    axa_value = leaf.get("axa")

    cells = []

    # Dimension columns: fill path elements
    for i in range(max_depth):
        cell_id = f"{column_labels[i]}{row_number}"
        cell_value = path[i] if i < len(path) else ""
        cell = {
            "id": cell_id,
            "value": cell_value,
            "type": "dimension",
        }
        cells.append(cell)

    # Part S.S. column
    ss_col_idx = max_depth
    cells.append({
        "id": f"{column_labels[ss_col_idx]}{row_number}",
        "value": leaf.get("securite_sociale_coverage") or "",
        "type": "ss_coverage",
    })

    # ProBTP data column
    probtp_col_idx = max_depth + 1
    probtp_cell = _build_data_cell(
        probtp_value,
        f"{column_labels[probtp_col_idx]}{row_number}",
        "probtp",
        leaf_analysis,
    )
    cells.append(probtp_cell)

    # AXA data column
    axa_col_idx = max_depth + 2
    axa_cell = _build_data_cell(
        axa_value,
        f"{column_labels[axa_col_idx]}{row_number}",
        "axa",
        leaf_analysis,
    )
    cells.append(axa_cell)

    # Build row with enriched metadata
    row = {
        "row_number": row_number,
        # Leaf metadata
        "leaf_id": leaf["leaf_id"],
        "leaf_path": path,
        "leaf_description": leaf["description"],
        "securite_sociale_coverage": leaf.get("securite_sociale_coverage"),
        "is_unmappable_probtp_only": leaf.get("is_unmappable_probtp_only", False),
        "is_unmappable_axa_only": leaf.get("is_unmappable_axa_only", False),
        "inherited_from_above": [None] * total_columns,
        "cells": cells,
    }

    # Add analysis metadata if available
    if leaf_analysis:
        row["probtp_advantage"] = leaf_analysis.probtp_advantage
        row["rationale"] = leaf_analysis.rationale

    return row


def _build_data_cell(
    extracted_value: dict[str, Any] | None,
    cell_id: str,
    vendor: str,
    leaf_analysis: Any,  # LeafAnalysis or None
) -> dict[str, Any]:
    """Build a data cell from extracted value with is_best annotation and full metadata."""
    if not extracted_value:
        # No value found - mark as non couvert
        return {
            "id": cell_id,
            "value": "Non couvert",
            "type": "data",
            "is_best": False,  # Not covered is never best
            "vendor": vendor,
        }

    coverage = extracted_value.get("coverage", "Non couvert")

    # Build display value with modifiers
    display_parts = [coverage]

    # Add frequency if present
    if extracted_value.get("frequency"):
        display_parts.append(f"({extracted_value['frequency']})")

    # Add cap if present
    if extracted_value.get("cap"):
        display_parts.append(f"[{extracted_value['cap']}]")

    computed_display_value = " ".join(display_parts)

    # Build cell with enriched metadata
    cell = {
        "id": cell_id,
        "value": computed_display_value,  # Computed display value
        "type": "data",
        "vendor": vendor,
        # Structured ExtractedValue fields
        "coverage": coverage,
        "frequency": extracted_value.get("frequency"),
        "cap": extracted_value.get("cap"),
        "age_restriction": extracted_value.get("age_restriction"),
        "other_universal_conditions": extracted_value.get("other_universal_conditions"),
        "vendor_conditions": extracted_value.get("vendor_conditions"),
        "notes": extracted_value.get("notes"),
    }

    # Add analysis display value if available
    if leaf_analysis:
        if vendor == "probtp":
            cell["display_value"] = leaf_analysis.probtp_display_value
        else:  # vendor == "axa"
            cell["display_value"] = leaf_analysis.axa_display_value

    # Add is_best annotation from analysis using probtp_advantage
    if leaf_analysis:
        probtp_advantage = leaf_analysis.probtp_advantage

        # Determine is_best based on vendor and ProBTP advantage
        if probtp_advantage == "equal":
            cell["is_best"] = True  # Both are best if equal
        elif vendor == "probtp":
            # ProBTP cell is best if probtp_advantage is better
            cell["is_best"] = probtp_advantage in ["probtp_much_better", "probtp_better"]
        else:  # vendor == "axa"
            # AXA cell is best if ProBTP advantage is worse
            cell["is_best"] = probtp_advantage in ["probtp_worse", "probtp_much_worse"]
    else:
        # No analysis - default to null
        cell["is_best"] = None

    # Add metadata if conditions/restrictions exist (for backward compatibility)
    metadata_parts = []

    if extracted_value.get("age_restriction"):
        metadata_parts.append(extracted_value["age_restriction"])

    if extracted_value.get("other_universal_conditions"):
        metadata_parts.append(extracted_value["other_universal_conditions"])

    if extracted_value.get("vendor_conditions"):
        for vc in extracted_value["vendor_conditions"]:
            cond_str = vc["description"]
            if vc.get("coverage_modifier"):
                cond_str += f": {vc['coverage_modifier']}"
            metadata_parts.append(cond_str)

    if metadata_parts:
        cell["metadata"] = {
            "document": vendor,
            "conditions": " | ".join(metadata_parts)
        }

    # Add source tracking if present (for backward compatibility)
    # Collect all source cell IDs including modified coverage sources from vendor conditions
    all_source_ids = []
    if extracted_value.get("source_cell_ids"):
        all_source_ids.extend(extracted_value["source_cell_ids"])

    # Add modified coverage source cell IDs from vendor conditions
    if extracted_value.get("vendor_conditions"):
        for vc in extracted_value["vendor_conditions"]:
            if vc.get("modified_coverage_source_cell_ids"):
                all_source_ids.extend(vc["modified_coverage_source_cell_ids"])

    # Deduplicate while preserving order
    if all_source_ids:
        seen = set()
        deduplicated_ids = []
        for source_id in all_source_ids:
            if source_id not in seen:
                seen.add(source_id)
                deduplicated_ids.append(source_id)

        cell["sources"] = {
            vendor: deduplicated_ids
        }

    return cell


def _apply_rowspan_merging(
    rows: list[dict[str, Any]],
    max_depth: int,
    total_columns: int,
    column_labels: list[str],
) -> list[dict[str, Any]]:
    """
    Apply rowspan merging to dimension columns for hierarchical display.

    When consecutive rows have the same value in a dimension column,
    merge them into a single cell with rowspan.

    Args:
        rows: List of row dicts
        max_depth: Number of dimension columns
        total_columns: Total columns in table
        column_labels: Excel-style column labels

    Returns:
        Updated rows with rowspan applied and virtual cells added
    """
    if len(rows) <= 1:  # Only header row
        return rows

    # Track merged cells: {(col_idx, start_row): span_count}
    merged_cells: dict[tuple[int, int], int] = {}

    # Process dimension columns only (not data columns)
    for col_idx in range(max_depth):
        # Scan rows starting from row 2 (index 1, after header)
        current_value = None
        span_start_row = None
        span_count = 0

        for row_idx in range(1, len(rows)):
            row = rows[row_idx]
            cell = row["cells"][col_idx]
            cell_value = cell.get("value", "")

            if cell_value == current_value and cell_value != "":
                # Continue span
                span_count += 1
            else:
                # End previous span if it exists
                if span_count > 1 and span_start_row is not None:
                    merged_cells[(col_idx, span_start_row)] = span_count

                # Start new potential span
                current_value = cell_value
                span_start_row = row_idx
                span_count = 1

        # Handle last span
        if span_count > 1 and span_start_row is not None:
            merged_cells[(col_idx, span_start_row)] = span_count

    # Apply rowspan to cells and create virtual cells
    for (col_idx, start_row_idx), span_count in merged_cells.items():
        start_row = rows[start_row_idx]
        start_cell = start_row["cells"][col_idx]
        row_number = start_row["row_number"]

        # Add rowspan and occupies to start cell
        start_cell["rowspan"] = span_count
        occupies = [f"{column_labels[col_idx]}{row_number + i}" for i in range(span_count)]
        start_cell["occupies"] = occupies

        # Convert subsequent cells to virtual cells
        for i in range(1, span_count):
            virtual_row_idx = start_row_idx + i
            virtual_row = rows[virtual_row_idx]
            virtual_cell_id = f"{column_labels[col_idx]}{virtual_row['row_number']}"

            # Replace cell with virtual cell
            virtual_row["cells"][col_idx] = {
                "id": virtual_cell_id,
                "ref": start_cell["id"],
            }

            # Update inherited_from_above
            virtual_row["inherited_from_above"][col_idx] = start_cell["id"]

    return rows
