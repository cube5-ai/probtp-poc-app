"""Build comparison table from analysis results and comparison document.

This module creates the final ComparisonTable structure from taxonomy-first analysis,
using leaf comparisons to add is_best annotations to cells.
"""

from typing import Any

from prompts.taxonomy_first.analysis_prompt import TaxonomyFirstAnalysisOutput


def _sort_leaves_by_hierarchy(
    leaves: list[dict[str, Any]],
    taxonomy_nodes: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """
    Sort leaves hierarchically preserving original taxonomy order.

    The taxonomy nodes are in depth-first order matching the source document structure.
    We preserve this order and append unmappable items (taxonomy extensions) after their
    parent's existing children.

    Args:
        leaves: List of leaf dicts from comparison document
        taxonomy_nodes: Optional full taxonomy nodes for preserving original order

    Returns:
        Sorted list of leaves preserving taxonomy order
    """
    if not taxonomy_nodes:
        # Fallback: simple alphabetical sorting by path
        return sorted(leaves, key=lambda leaf: leaf.get("path", []))

    # Build taxonomy order lookup: {leaf_id: order_index}
    taxonomy_order = {}
    for idx, node in enumerate(taxonomy_nodes):
        if node.get("is_leaf", False):
            taxonomy_order[node["node_id"]] = idx

    # Split leaves into taxonomy leaves and unmappable extensions
    taxonomy_leaves = []
    unmappable_leaves = []

    for leaf in leaves:
        leaf_id = leaf.get("leaf_id", "")
        is_unmappable = leaf.get("is_unmappable_probtp_only", False) or leaf.get("is_unmappable_axa_only", False)

        if is_unmappable or leaf_id not in taxonomy_order:
            unmappable_leaves.append(leaf)
        else:
            taxonomy_leaves.append(leaf)

    # Sort taxonomy leaves by their original order
    taxonomy_leaves.sort(key=lambda leaf: taxonomy_order.get(leaf.get("leaf_id", ""), float('inf')))

    # Group unmappable leaves by parent path for insertion
    unmappable_by_parent: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for leaf in unmappable_leaves:
        path = leaf.get("path", [])
        parent_path = tuple(path[:-1]) if len(path) > 1 else ()
        if parent_path not in unmappable_by_parent:
            unmappable_by_parent[parent_path] = []
        unmappable_by_parent[parent_path].append(leaf)

    # Sort unmappable leaves within each parent group alphabetically
    for parent_path in unmappable_by_parent:
        unmappable_by_parent[parent_path].sort(key=lambda leaf: leaf.get("path", [])[-1] if leaf.get("path") else "")

    # Merge: insert unmappable leaves after their parent's last taxonomy child
    result = []
    i = 0
    while i < len(taxonomy_leaves):
        current_leaf = taxonomy_leaves[i]
        current_path = current_leaf.get("path", [])
        current_parent_path = tuple(current_path[:-1]) if len(current_path) > 1 else ()

        # Add current taxonomy leaf
        result.append(current_leaf)

        # Check if next leaf has different parent
        next_has_different_parent = (
            i + 1 >= len(taxonomy_leaves) or
            tuple(taxonomy_leaves[i + 1].get("path", [])[:-1] if len(taxonomy_leaves[i + 1].get("path", [])) > 1 else ()) != current_parent_path
        )

        # If this is the last child of current parent, insert unmappable children
        if next_has_different_parent and current_parent_path in unmappable_by_parent:
            result.extend(unmappable_by_parent[current_parent_path])
            del unmappable_by_parent[current_parent_path]  # Mark as inserted

        i += 1

    # Append any remaining unmappable leaves that didn't match a parent (root-level extensions)
    for parent_path in sorted(unmappable_by_parent.keys()):
        result.extend(unmappable_by_parent[parent_path])

    return result


def build_table_from_analysis(
    comparison_document: dict[str, Any],
    analysis: TaxonomyFirstAnalysisOutput,
    taxonomy_nodes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Build ComparisonTable from comparison document and analysis results.

    Args:
        comparison_document: ComparisonDocument dict with full leaf data
        analysis: TaxonomyFirstAnalysisOutput with leaf comparisons
        taxonomy_nodes: Optional full taxonomy nodes for enhanced hierarchy visualization

    Returns:
        ComparisonTable dict with Excel-style IDs, rowspan/colspan, and is_best annotations
    """
    category_name = comparison_document.get("category_name", "")
    probtp_level = comparison_document.get("probtp_policy_level", "")
    axa_level = comparison_document.get("axa_policy_level", "")
    leaves = comparison_document.get("leaves", [])

    # Sort leaves hierarchically preserving original taxonomy order
    leaves = _sort_leaves_by_hierarchy(leaves, taxonomy_nodes)

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
            "vendor_a_ref": [probtp_level],
            "vendor_b": [axa_level],
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
    rows = _apply_rowspan_merging(rows, max_depth, total_columns, column_labels, taxonomy_nodes)

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
    vendor_a_ref_value = leaf.get("vendor_a_ref")
    vendor_b_value = leaf.get("vendor_b")

    cells = []

    # Dimension columns: fill path elements with hierarchy depth metadata
    for i in range(max_depth):
        cell_id = f"{column_labels[i]}{row_number}"
        cell_value = path[i] if i < len(path) else ""
        cell = {
            "id": cell_id,
            "value": cell_value,
            "type": "dimension",
            "hierarchy_level": i,  # 0 = top category, 1 = subcategory, etc.
            "is_deepest_level": (i == len(path) - 1) if path else False,  # Marks leaf level
        }
        cells.append(cell)

    # Part S.S. column
    ss_col_idx = max_depth
    cells.append({
        "id": f"{column_labels[ss_col_idx]}{row_number}",
        "value": leaf.get("securite_sociale_coverage") or "",
        "type": "ss_coverage",
    })

    # Vendor A data column
    vendor_a_ref_col_idx = max_depth + 1
    vendor_a_ref_cell = _build_data_cell(
        vendor_a_ref_value,
        f"{column_labels[vendor_a_ref_col_idx]}{row_number}",
        "vendor_a_ref",
        leaf_analysis,
    )
    cells.append(vendor_a_ref_cell)

    # Vendor B data column
    vendor_b_col_idx = max_depth + 2
    vendor_b_cell = _build_data_cell(
        vendor_b_value,
        f"{column_labels[vendor_b_col_idx]}{row_number}",
        "vendor_b",
        leaf_analysis,
    )
    cells.append(vendor_b_cell)

    # Check if this is a new taxonomy leaf (discovered during extraction)
    is_new_leaf = leaf.get("is_unmappable_vendor_a_ref_only", False) or leaf.get("is_unmappable_vendor_b_only", False)

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
        "is_taxonomy_extension": is_new_leaf,  # Flag for visual styling
        "inherited_from_above": [None] * total_columns,
        "cells": cells,
    }

    # Add analysis metadata if available
    if leaf_analysis:
        row["vendor_a_ref_advantage"] = leaf_analysis.vendor_a_ref_advantage
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
        if vendor == "vendor_a_ref":
            cell["display_value"] = leaf_analysis.vendor_a_ref_display_value
        else:  # vendor == "vendor_b"
            cell["display_value"] = leaf_analysis.vendor_b_display_value

    # Add is_best annotation from analysis using vendor_a_ref_advantage
    if leaf_analysis:
        vendor_a_ref_advantage = leaf_analysis.vendor_a_ref_advantage

        # Determine is_best based on vendor and vendor A advantage
        if vendor_a_ref_advantage == "equal":
            cell["is_best"] = True  # Both are best if equal
        elif vendor == "vendor_a_ref":
            # Vendor A cell is best if vendor_a_ref_advantage is better
            cell["is_best"] = vendor_a_ref_advantage in ["vendor_a_ref_much_better", "vendor_a_ref_better"]
        else:  # vendor == "vendor_b"
            # Vendor B cell is best if vendor A advantage is worse
            cell["is_best"] = vendor_a_ref_advantage in ["vendor_a_ref_worse", "vendor_a_ref_much_worse"]
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
    taxonomy_nodes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Apply rowspan merging to dimension columns for hierarchical display.

    When consecutive rows have the same value in a dimension column,
    merge them into a single cell with rowspan. Uses taxonomy structure
    for smarter hierarchical merging.

    Args:
        rows: List of row dicts
        max_depth: Number of dimension columns
        total_columns: Total columns in table
        column_labels: Excel-style column labels
        taxonomy_nodes: Optional full taxonomy nodes for hierarchy-aware merging

    Returns:
        Updated rows with rowspan applied and virtual cells added
    """
    if len(rows) <= 1:  # Only header row
        return rows

    # Track merged cells: {(col_idx, start_row): span_count}
    merged_cells: dict[tuple[int, int], int] = {}

    # Build taxonomy node lookup if available (for smarter merging)
    taxonomy_lookup = {}
    if taxonomy_nodes:
        for node in taxonomy_nodes:
            node_id = node.get("node_id")
            if node_id:
                taxonomy_lookup[node_id] = node

    # Process dimension columns from left to right (respects hierarchy)
    # Only merge cells when ALL ancestor columns are also merged
    for col_idx in range(max_depth):
        # Scan rows starting from row 2 (index 1, after header)
        current_value = None
        current_path_prefix = None  # Track full path prefix for this column
        span_start_row = None
        span_count = 0

        for row_idx in range(1, len(rows)):
            row = rows[row_idx]
            cell = row["cells"][col_idx]
            cell_value = cell.get("value", "")

            # Get full path for taxonomy-aware comparison
            leaf_path = row.get("leaf_path", [])
            path_prefix = tuple(leaf_path[:col_idx + 1]) if col_idx < len(leaf_path) else ()

            # Check if ancestors are merged (only merge if parent columns are also merged)
            can_merge = True
            if col_idx > 0:
                # Check if all ancestor columns (0 to col_idx-1) are merged
                for ancestor_col_idx in range(col_idx):
                    ancestor_cell = row["cells"][ancestor_col_idx]
                    # If ancestor is virtual (has ref), it's merged - good
                    # If ancestor has no ref and has same value as previous row, continue checking
                    if "ref" not in ancestor_cell:
                        # Not merged yet, so we can't merge this level either
                        if row_idx > 1:
                            prev_row = rows[row_idx - 1]
                            prev_ancestor_cell = prev_row["cells"][ancestor_col_idx]
                            if prev_ancestor_cell.get("value", "") != ancestor_cell.get("value", ""):
                                can_merge = False
                                break

            # Merge logic: same value AND same path prefix (taxonomy-aware)
            if (cell_value == current_value and
                path_prefix == current_path_prefix and
                cell_value != "" and
                can_merge):
                # Continue span
                span_count += 1
            else:
                # End previous span if it exists
                if span_count > 1 and span_start_row is not None:
                    merged_cells[(col_idx, span_start_row)] = span_count

                # Start new potential span
                current_value = cell_value
                current_path_prefix = path_prefix
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
