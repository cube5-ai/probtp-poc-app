"""Utilities for formatting multi-level comparison documents to markdown tables."""

from typing import Any


def format_multi_level_comparison_to_markdown(
    comparison_document: dict[str, Any],
    vendor_a_levels_to_include: list[str] | None = None,
) -> str:
    """Convert multi-level comparison document to markdown table.

    Creates a hierarchical table with:
    - Column headers: Taxonomy path (hierarchical), then vendor A levels, then vendor B level
    - Rows: One per leaf prestation
    - Values: detailed_value from the comparison document

    Args:
        comparison_document: MultiLevelComparisonDocument dict
        vendor_a_levels_to_include: Specific vendor A levels to include in table.
            If None, includes all levels from the document.

    Returns:
        Markdown formatted table string
    """
    category_name = comparison_document.get("category_name", "Unknown")
    vendor_a_ref_name = comparison_document.get("vendor_a_ref_name", "Vendor A")
    vendor_b_name = comparison_document.get("vendor_b_name", "Vendor B")
    vendor_b_level = comparison_document.get("vendor_b_policy_level", "")
    all_vendor_a_levels = comparison_document.get("vendor_a_ref_policy_levels", [])
    leaves = comparison_document.get("leaves", [])

    # Determine which vendor A levels to include
    if vendor_a_levels_to_include:
        # Filter to only requested levels, maintain order from document
        vendor_a_levels = [
            level for level in all_vendor_a_levels
            if level in vendor_a_levels_to_include
        ]
    else:
        vendor_a_levels = all_vendor_a_levels

    if not leaves or not vendor_a_levels:
        return f"### {category_name}\n\n*(Aucune donnée disponible)*\n"

    lines = []
    lines.append(f"### {category_name}\n")

    # Build hierarchical table using HTML for better control
    lines.append('<table>')

    # Build header row
    lines.append('  <tr>')
    lines.append('    <th>Prestation</th>')
    for level in vendor_a_levels:
        lines.append(f'    <th>{vendor_a_ref_name}<br/>{level}</th>')
    lines.append(f'    <th>{vendor_b_name}<br/>{vendor_b_level}</th>')
    lines.append('  </tr>')

    # Build hierarchy from paths
    hierarchy = _build_hierarchy_from_paths(leaves)

    # Render rows recursively
    _render_comparison_rows(
        hierarchy,
        vendor_a_levels,
        vendor_a_ref_name,
        vendor_b_name,
        lines,
        level=0,
    )

    lines.append('</table>\n')

    return "\n".join(lines)


def _build_hierarchy_from_paths(leaves: list[dict]) -> dict:
    """Build hierarchical tree structure from leaf paths.

    Args:
        leaves: List of leaf dicts with 'path' field

    Returns:
        Nested dict representing tree structure
    """
    root = {"children": {}, "leaves": []}

    for leaf in leaves:
        path = leaf.get("path", [])
        if not path:
            continue

        # Navigate/create tree nodes for path
        current = root
        for segment in path[:-1]:  # All but last element (leaf name)
            if segment not in current["children"]:
                current["children"][segment] = {"children": {}, "leaves": []}
            current = current["children"][segment]

        # Add leaf to final parent node
        current["leaves"].append(leaf)

    return root


def _render_comparison_rows(
    node: dict,
    vendor_a_levels: list[str],
    vendor_a_ref_name: str,
    vendor_b_name: str,
    lines: list[str],
    level: int = 0,
    parent_path: list[str] | None = None,
) -> None:
    """Recursively render hierarchical tree as table rows.

    Args:
        node: Tree node with 'children' and 'leaves'
        vendor_a_levels: List of vendor A levels to include
        vendor_a_ref_name: Vendor A name
        vendor_b_name: Vendor B name
        lines: Output lines list (modified in place)
        level: Current nesting level
        parent_path: Parent path segments for context
    """
    if parent_path is None:
        parent_path = []

    # Render child categories as section headers
    for child_name, child_node in node.get("children", {}).items():
        # Add a section header row for this subcategory
        num_cols = len(vendor_a_levels) + 2  # +2 for prestation column and vendor B column
        indent = "&nbsp;" * (level * 4)
        lines.append('  <tr>')
        lines.append(f'    <td colspan="{num_cols}" style="background-color: #f0f0f0; font-weight: bold;">{indent}{child_name}</td>')
        lines.append('  </tr>')

        # Recursively render children
        _render_comparison_rows(
            child_node,
            vendor_a_levels,
            vendor_a_ref_name,
            vendor_b_name,
            lines,
            level + 1,
            parent_path + [child_name],
        )

    # Render leaves at this level
    for leaf in node.get("leaves", []):
        leaf_id = leaf.get("leaf_id", "")
        path = leaf.get("path", [])
        leaf_name = path[-1] if path else "Unknown"
        description = leaf.get("description", "")

        # Get vendor A values (by level)
        vendor_a_values = leaf.get("vendor_a_ref_values", {})

        # Get vendor B value
        vendor_b_value = leaf.get("vendor_b_value", {})

        # Build row
        indent = "&nbsp;" * (level * 4)
        lines.append('  <tr>')

        # Prestation name with description as tooltip
        prestation_display = f'{indent}{leaf_name}'
        if description and description != leaf_name:
            prestation_display = f'{indent}<span title="{description}">{leaf_name}</span>'
        lines.append(f'    <td>{prestation_display}</td>')

        # Vendor A level values
        for vendor_level in vendor_a_levels:
            value_data = vendor_a_values.get(vendor_level, {})
            detailed_value = value_data.get("detailed_value", "")
            base_value = value_data.get("base_value", "")

            # Use detailed_value if available, fallback to base_value
            display_value = detailed_value or base_value or "—"

            # Truncate very long values
            if len(display_value) > 150:
                display_value = display_value[:147] + "..."

            lines.append(f'    <td>{display_value}</td>')

        # Vendor B value
        vendor_b_detailed = vendor_b_value.get("detailed_value", "")
        vendor_b_base = vendor_b_value.get("base_value", "")
        vendor_b_display = vendor_b_detailed or vendor_b_base or "—"

        if len(vendor_b_display) > 150:
            vendor_b_display = vendor_b_display[:147] + "..."

        lines.append(f'    <td>{vendor_b_display}</td>')

        lines.append('  </tr>')
