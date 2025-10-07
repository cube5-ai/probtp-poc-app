"""Utilities for converting JSON structures to human-readable formats (HTML, Markdown)."""


def comparison_table_to_html(table_data: dict) -> str:
    """
    Convert ComparisonTable JSON to HTML table.

    Args:
        table_data: ComparisonTable dict with metadata and rows

    Returns:
        HTML table string
    """
    metadata = table_data.get("metadata", {})
    rows = table_data.get("rows", [])

    html_lines = ['<table class="comparison-table">']

    # Add table header with metadata as caption
    category = metadata.get("category", "")
    if category:
        html_lines.append(f'  <caption>{category}</caption>')

    html_lines.append('  <tbody>')

    for row in rows:
        html_lines.append('    <tr>')
        cells = row.get("cells", [])

        for cell in cells:
            value = cell.get("value", "")
            cell_type = cell.get("type", "data")
            colspan = cell.get("colspan")
            rowspan = cell.get("rowspan")
            is_best = cell.get("is_best")
            metadata_obj = cell.get("metadata") or {}

            # Build cell attributes
            attrs = []
            if colspan and colspan > 1:
                attrs.append(f'colspan="{colspan}"')
            if rowspan and rowspan > 1:
                attrs.append(f'rowspan="{rowspan}"')

            # Add CSS class based on type and is_best
            classes = [f'cell-{cell_type}']
            if is_best is True:
                classes.append('cell-best')
            elif is_best is False:
                classes.append('cell-worse')

            attrs.append(f'class="{" ".join(classes)}"')

            # Build cell tag
            tag = "th" if cell_type == "dimension" else "td"
            attrs_str = " " + " ".join(attrs) if attrs else ""

            # Add footnotes if present
            footnotes = metadata_obj.get("footnotes") or []
            display_value = value
            if footnotes:
                display_value += " " + "".join(footnotes)

            html_lines.append(f'      <{tag}{attrs_str}>{display_value}</{tag}>')

        html_lines.append('    </tr>')

    html_lines.append('  </tbody>')
    html_lines.append('</table>')

    return "\n".join(html_lines)


def comparison_table_to_markdown(table_data: dict, include_row_comparison: bool = True) -> str:
    """
    Convert ComparisonTable JSON to Markdown table.

    Args:
        table_data: ComparisonTable dict with metadata and rows
        include_row_comparison: Whether to add row comparison as a note after each row

    Returns:
        Markdown table string
    """
    metadata = table_data.get("metadata", {})
    rows = table_data.get("rows", [])

    lines = []

    # Add category as header
    category = metadata.get("category", "")
    if category:
        lines.append(f"### {category}\n")

    # Build markdown table
    # Note: Markdown tables don't support colspan/rowspan natively
    # We'll use HTML table format instead for better rendering

    lines.append('<table>')

    for row_idx, row in enumerate(rows):
        cells = row.get("cells", [])

        # Determine if this is a header row (first row or dimension-only row)
        is_header = row_idx == 0

        lines.append('  <tr>')

        for cell in cells:
            # Skip virtual cells (they have ref instead of value)
            if cell.get("ref"):
                continue

            value = cell.get("value", "").strip() if cell.get("value") else ""
            cell_type = cell.get("type")
            colspan = cell.get("colspan")
            rowspan = cell.get("rowspan")
            is_best = cell.get("is_best")
            metadata_obj = cell.get("metadata") or {}

            # Add footnotes
            footnotes = metadata_obj.get("footnotes") or []
            if footnotes:
                value += " " + "".join(footnotes)

            # Add indicator for best coverage
            if is_best is True:
                value = f"<strong>{value}</strong> ✓"
            elif is_best is False and value:
                value = f"{value}"

            # Handle empty cells
            if not value:
                value = " "

            # Build cell tag
            tag = "th" if (is_header or cell_type != "data") else "td"
            attrs = []

            if colspan and colspan > 1:
                attrs.append(f'colspan="{colspan}"')
            if rowspan and rowspan > 1:
                attrs.append(f'rowspan="{rowspan}"')

            attrs_str = " " + " ".join(attrs) if attrs else ""

            lines.append(f'    <{tag}{attrs_str}>{value}</{tag}>')

        lines.append('  </tr>')

        # Add row comparison note if available and requested
        if include_row_comparison and not is_header:
            comparison = row.get("comparison")
            if comparison:
                winner = comparison.get("winner", "")
                reasoning = comparison.get("reasoning", "")

                # Format winner as emoji + text
                winner_display = {
                    "probtp_much_better": "🟢🟢 ProBTP beaucoup mieux",
                    "probtp_better": "🟢 ProBTP mieux",
                    "equivalent": "🟡 Équivalent",
                    "axa_better": "🔴 AXA mieux",
                    "axa_much_better": "🔴🔴 AXA beaucoup mieux"
                }.get(winner, winner)

                # Add comparison as a note row
                num_cols = len(cells)
                lines.append('  <tr class="comparison-note">')
                lines.append(f'    <td colspan="{num_cols}"><em>{winner_display}</em> — {reasoning}</td>')
                lines.append('  </tr>')

    lines.append('</table>')

    return "\n".join(lines)


def analysis_to_markdown(analysis_data: dict) -> str:
    """
    Convert AnalysisOutput JSON to readable Markdown.

    Args:
        analysis_data: AnalysisOutput dict from analysis phase

    Returns:
        Markdown formatted analysis
    """
    lines = []

    category = analysis_data.get("category", "Unknown")
    lines.append(f"## {category}\n")

    # Annotated comparison table
    annotated_table = analysis_data.get("annotated_table", {})
    if annotated_table:
        lines.append("### Tableau de Comparaison\n")
        lines.append(comparison_table_to_markdown(annotated_table))
        lines.append("")

    # Key differences
    key_differences = analysis_data.get("key_differences", "")
    if key_differences:
        lines.append("### Différences Clés\n")
        lines.append(key_differences)
        lines.append("")

    # Concrete examples
    concrete_examples = analysis_data.get("concrete_examples", [])
    if concrete_examples:
        lines.append("### Exemples Concrets\n")
        for example in concrete_examples:
            lines.append(f"- {example}")
        lines.append("")

    # Critical thinking
    critical_thinking = analysis_data.get("critical_thinking", "")
    if critical_thinking:
        lines.append("### Analyse de Valeur\n")
        lines.append(critical_thinking)
        lines.append("")

    # Best coverage (ProBTP perspective)
    best_coverage = analysis_data.get("best_coverage", "")
    if best_coverage:
        lines.append("### Meilleure Couverture (Perspective ProBTP)\n")
        lines.append(best_coverage)
        lines.append("")

    # Salesperson talking points
    talking_points = analysis_data.get("salesperson_talking_points", [])
    if talking_points:
        lines.append("### Points de Vente\n")
        for point in talking_points:
            lines.append(f"- {point}")
        lines.append("")

    # Objective assessment
    objective = analysis_data.get("objective_assessment", {})
    if objective:
        lines.append("### Évaluation Objective\n")
        lines.append(f"**Gagnant:** {objective.get('overall_winner', 'N/A').upper()}")
        lines.append(f"**Confiance:** {objective.get('confidence', 'N/A')}")
        lines.append(f"\n**Raisonnement:** {objective.get('reasoning', 'N/A')}\n")

        probtp_weak = objective.get("probtp_weaknesses", [])
        if probtp_weak:
            lines.append("**Faiblesses ProBTP:**")
            for weakness in probtp_weak:
                lines.append(f"- {weakness}")
            lines.append("")

        axa_weak = objective.get("axa_weaknesses", [])
        if axa_weak:
            lines.append("**Faiblesses AXA:**")
            for weakness in axa_weak:
                lines.append(f"- {weakness}")
            lines.append("")

    return "\n".join(lines)


def summary_to_markdown(summary_data: dict) -> str:
    """
    Convert ComparisonSummary JSON to readable Markdown.

    Args:
        summary_data: ComparisonSummary dict from summary phase

    Returns:
        Markdown formatted summary
    """
    lines = []

    lines.append("# Synthèse Générale de la Comparaison\n")

    # Key differences
    key_differences = summary_data.get("key_differences", "")
    if key_differences:
        lines.append("## Différences Stratégiques\n")
        lines.append(key_differences)
        lines.append("")



    # Overall strengths
    probtp_overall = summary_data.get("probtp_overall_strengths", [])
    axa_overall = summary_data.get("axa_overall_strengths", [])

    if probtp_overall or axa_overall:
        lines.append("## Forces Globales\n")

        if probtp_overall:
            lines.append("### ProBTP\n")
            for strength in probtp_overall:
                lines.append(f"- {strength}")
            lines.append("")

        if axa_overall:
            lines.append("### AXA\n")
            for strength in axa_overall:
                lines.append(f"- {strength}")
            lines.append("")

    # Objective evaluation
    objective_eval = summary_data.get("objective_evaluation", {})
    if objective_eval:
        lines.append("## Évaluation Objective Globale\n")
        lines.append(f"**Gagnant Global:** {objective_eval.get('overall_winner', 'N/A').upper()}")
        lines.append(f"**Confiance:** {objective_eval.get('confidence', 'N/A')}")
        lines.append(f"\n{objective_eval.get('reasoning', 'N/A')}\n")


    # Category strengths
    category_strengths = summary_data.get("category_strengths", [])
    if category_strengths:
        lines.append("## Forces par Catégorie\n")
        for cat_strength in category_strengths:
            category = cat_strength.get("category", "")
            probtp_strengths = cat_strength.get("probtp_strengths", [])
            axa_strengths = cat_strength.get("axa_strengths", [])

            lines.append(f"### {category}\n")

            if probtp_strengths:
                lines.append("**ProBTP:**")
                for strength in probtp_strengths:
                    lines.append(f"- {strength}")
                lines.append("")

            if axa_strengths:
                lines.append("**AXA:**")
                for strength in axa_strengths:
                    lines.append(f"- {strength}")
                lines.append("")


    # # Category winners
    # category_winners = summary_data.get("category_winners", [])
    # if category_winners:
    #     lines.append("### Gagnants par Catégorie\n")
    #     for cat_winner in category_winners:
    #         category = cat_winner.get("category", "")
    #         winner = cat_winner.get("winner", "").upper()
    #         confidence = cat_winner.get("confidence", "")
    #         reason = cat_winner.get("key_reason", "")

    #         lines.append(f"**{category}:** {winner} (confiance: {confidence})")
    #         lines.append(f"  ↳ {reason}\n")

    # Selling points
    selling_points = summary_data.get("selling_points", [])
    if selling_points:
        lines.append("## Points de Vente ProBTP\n")
        for point in selling_points:
            lines.append(f"- {point}")
        lines.append("")

    # Target customer fit
    target_fit = summary_data.get("target_customer_fit", "")
    if target_fit:
        lines.append("## Adéquation Client\n")
        lines.append(target_fit)
        lines.append("")

    return "\n".join(lines)


def detailed_leaf_comparisons_to_markdown(
    comparison_document: dict,
    leaf_analyses: dict,
    comparison_table: dict,
) -> str:
    """
    Convert leaf-based comparisons to detailed hierarchical markdown.

    Creates nested bullet list organized by taxonomy hierarchy, with exhaustive
    mini comparison tables for each leaf showing all available data fields.

    Args:
        comparison_document: ComparisonDocument dict with leaves and paths
        leaf_analyses: TaxonomyFirstAnalysisOutput dict with leaf_comparisons
        comparison_table: ComparisonTable dict with annotated rows

    Returns:
        Markdown string with hierarchical leaf comparisons
    """
    lines = []

    # Get leaves from comparison document
    leaves = comparison_document.get("leaves", [])
    if not leaves:
        return ""

    # Build leaf analysis lookup by leaf_id
    leaf_analysis_map = {}
    for leaf_comp in leaf_analyses.get("leaf_comparisons", []):
        leaf_analysis_map[leaf_comp["leaf_id"]] = leaf_comp

    # Build row lookup by leaf_id from comparison table
    row_map = {}
    for row in comparison_table.get("rows", [])[1:]:  # Skip header row
        leaf_id = row.get("leaf_id")
        if leaf_id:
            row_map[leaf_id] = row

    # Build hierarchical structure from paths
    hierarchy = _build_hierarchy_from_paths(leaves)

    # Render hierarchy as nested markdown
    _render_hierarchy_markdown(
        hierarchy, leaf_analysis_map, row_map, comparison_table, lines, level=0
    )

    return "\n".join(lines)


def _build_hierarchy_from_paths(leaves: list[dict]) -> dict:
    """
    Build hierarchical tree structure from leaf paths.

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
        for i, segment in enumerate(path[:-1]):  # All but last element
            if segment not in current["children"]:
                current["children"][segment] = {"children": {}, "leaves": []}
            current = current["children"][segment]

        # Add leaf to final parent node
        current["leaves"].append(leaf)

    return root


def _render_hierarchy_markdown(
    node: dict,
    leaf_analysis_map: dict,
    row_map: dict,
    comparison_table: dict,
    lines: list[str],
    level: int = 0,
    parent_name: str | None = None,
) -> None:
    """
    Recursively render hierarchical tree as nested markdown.

    Args:
        node: Tree node with 'children' and 'leaves'
        leaf_analysis_map: Leaf ID -> LeafAnalysis dict
        row_map: Leaf ID -> comparison table row dict
        comparison_table: Full comparison table for metadata
        lines: Output lines list (modified in place)
        level: Current nesting level
        parent_name: Parent category name for display
    """
    indent = "  " * level

    # Render child nodes recursively
    for child_name, child_node in node.get("children", {}).items():
        lines.append(f"{indent}- **{child_name}**")
        _render_hierarchy_markdown(
            child_node,
            leaf_analysis_map,
            row_map,
            comparison_table,
            lines,
            level + 1,
            parent_name=child_name,
        )

    # Render leaves at this level
    for leaf in node.get("leaves", []):
        leaf_id = leaf.get("leaf_id", "")
        path = leaf.get("path", [])
        leaf_name = path[-1] if path else "Unknown"

        # Get analysis rationale
        analysis = leaf_analysis_map.get(leaf_id, {})
        rationale = analysis.get("rationale", "Aucune analyse disponible")

        # Add leaf bullet with rationale
        lines.append(f"{indent}- **{leaf_name}**: {rationale}")
        lines.append("")

        # Build exhaustive mini comparison table
        row = row_map.get(leaf_id)
        if row:
            table_md = _build_exhaustive_mini_table(row, comparison_table)
            for table_line in table_md.split("\n"):
                lines.append(f"{indent}  {table_line}")
            lines.append("")


def _build_exhaustive_mini_table(row: dict, comparison_table: dict) -> str:
    """
    Build natural language comparison sentences for a single leaf row.

    Args:
        row: Comparison table row dict with cells
        comparison_table: Full comparison table for metadata

    Returns:
        Markdown formatted sentences describing ProBTP and AXA coverage
    """
    # Get policy levels from metadata
    metadata = comparison_table.get("metadata", {})
    policy_levels = metadata.get("policy_levels", {})
    probtp_level = policy_levels.get("probtp", ["ProBTP"])[0]
    axa_level = policy_levels.get("axa", ["AXA"])[0]

    # Extract ProBTP and AXA cells (last two data cells)
    cells = row.get("cells", [])
    if len(cells) < 2:
        return "*(Données insuffisantes)*"

    probtp_cell = None
    axa_cell = None
    for cell in cells:
        if cell.get("vendor") == "probtp":
            probtp_cell = cell
        elif cell.get("vendor") == "axa":
            axa_cell = cell

    if not probtp_cell or not axa_cell:
        return "*(Données manquantes)*"

    # Build sentences for both vendors
    probtp_sentence = _build_coverage_sentence(probtp_level, probtp_cell)
    axa_sentence = _build_coverage_sentence(axa_level, axa_cell)

    lines = []
    lines.append(f"- **{probtp_level}**: {probtp_sentence}")
    lines.append(f"- **{axa_level}**: {axa_sentence}")

    return "\n".join(lines)


def _build_coverage_sentence(vendor_name: str, cell: dict) -> str:
    """
    Build natural language sentence for a single vendor cell.

    Args:
        vendor_name: Vendor display name (e.g., "ProBTP S2")
        cell: Cell dict with coverage fields

    Returns:
        Natural language sentence describing coverage
    """
    # Extract fields
    coverage = cell.get("coverage", cell.get("value", "Non couvert"))
    frequency = cell.get("frequency")
    cap = cell.get("cap")
    age_restriction = cell.get("age_restriction")
    other_universal_conditions = cell.get("other_universal_conditions")
    vendor_conditions = cell.get("vendor_conditions", [])
    notes = cell.get("notes")

    # Handle "Non couvert" case
    if coverage == "Non couvert":
        return "Non couvert"

    # Build sentence parts
    parts = []

    # Start with coverage
    parts.append(coverage)

    # Add frequency
    if frequency:
        # Convert frequency to natural language
        freq_text = frequency.lower()
        if freq_text.startswith("/"):
            freq_text = freq_text[1:]  # Remove leading /
        if "an" in freq_text:
            parts.append(f"par {freq_text}")
        elif "mois" in freq_text:
            parts.append(f"par {freq_text}")
        elif freq_text:
            parts.append(f"par période de {freq_text}")

    # Add cap if it starts with a number
    if cap and cap[0].isdigit():
        parts.append(f"plafonné à {cap}")

    # Add age restrictions
    if age_restriction:
        parts.append(age_restriction)

    # Add vendor-specific conditions
    if vendor_conditions:
        cond_parts = []
        for vc in vendor_conditions:
            desc = vc.get("description", "")
            modifier = vc.get("coverage_modifier", "")
            if desc and modifier:
                cond_parts.append(f"{desc}: {modifier}")
            elif desc:
                cond_parts.append(desc)
        if cond_parts:
            parts.extend(cond_parts)

    # Add universal conditions at the end
    if other_universal_conditions:
        parts.append(other_universal_conditions)

    # Add notes at the very end
    if notes:
        parts.append(notes)

    # Join with proper punctuation
    if not parts:
        return "Non couvert"

    # First part is the base, rest are comma-separated
    if len(parts) == 1:
        return parts[0]

    # Join parts with commas, except insert proper connectors
    sentence = parts[0]
    for i, part in enumerate(parts[1:], 1):
        if i == len(parts) - 1 and len(parts) > 2:
            # Last item - no comma needed if it's a condition
            sentence += f", {part}"
        else:
            sentence += f", {part}"

    return sentence
