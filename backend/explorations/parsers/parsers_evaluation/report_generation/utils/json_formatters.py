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

    # Category winners
    category_winners = summary_data.get("category_winners", [])
    if category_winners:
        lines.append("### Gagnants par Catégorie\n")
        for cat_winner in category_winners:
            category = cat_winner.get("category", "")
            winner = cat_winner.get("winner", "").upper()
            confidence = cat_winner.get("confidence", "")
            reason = cat_winner.get("key_reason", "")

            lines.append(f"**{category}:** {winner} (confiance: {confidence})")
            lines.append(f"  ↳ {reason}\n")

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
