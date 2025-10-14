"""Format recommendation reports for policy recommendation pipeline.

This module generates markdown reports from recommendation data.
"""

from typing import Any


def format_category_recommendation(
    recommendation: dict[str, Any],
    comparison_table_markdown: str | None = None,
) -> str:
    """Format a single category recommendation as markdown.

    Args:
        recommendation: Category recommendation dict
        comparison_table_markdown: Optional comparison table in markdown

    Returns:
        Formatted markdown section
    """
    category_name = recommendation.get("category_name", "Unknown")
    section_title = recommendation.get("section_title", category_name)
    summary = recommendation.get("summary_paragraph", "")
    recommended_level = recommendation.get("recommended_vendor_a_ref_level", "")

    # Build markdown - ensure category name is at the start
    # Remove category name from section_title if it's already there to avoid duplication
    title_without_category = section_title
    if section_title.lower().startswith(category_name.lower()):
        title_without_category = section_title[len(category_name):].lstrip(" :-–—")

    # Format: "Category: Brief newspaper-style title"
    if title_without_category and title_without_category != category_name:
        formatted_title = f"{category_name}: {title_without_category}"
    else:
        formatted_title = category_name

    lines = [f"## {formatted_title}\n"]

    # Summary paragraph
    if summary:
        lines.append(f"{summary}\n")

    # Level selection process
    eliminated = recommendation.get("eliminated_levels", [])
    shortlisted = recommendation.get("shortlisted_levels", [])
    other_candidates = recommendation.get("other_candidates", [])

    if eliminated or shortlisted or other_candidates:
        lines.append("### Processus de Sélection\n")

        if eliminated:
            lines.append(f"**Niveaux éliminés:** {', '.join(eliminated)}\n")

        if shortlisted:
            lines.append(f"**Niveaux présélectionnés:** {', '.join(shortlisted)}\n")

        if other_candidates:
            lines.append("\n**Autres candidats analysés:**\n")
            for candidate in other_candidates:
                level = candidate.get("level", "")
                reason = candidate.get("reason_not_selected", "")
                lines.append(f"- **{level}**: {reason}")
            lines.append("\n")

    # Comparison table (if provided)
    if comparison_table_markdown:
        lines.append(f"### Tableau Comparatif - {category_name}\n")
        lines.append(comparison_table_markdown)
        lines.append("\n")

    # Equivalent coverage examples
    equivalent_examples = recommendation.get("equivalent_coverage_examples", [])
    if equivalent_examples:
        lines.append("### Couvertures Équivalentes\n")
        for example in equivalent_examples:
            lines.append(f"- {example}")
        lines.append("\n")

    # Vendor A wins
    vendor_a_wins = recommendation.get("vendor_a_ref_wins", [])
    if vendor_a_wins:
        lines.append(f"### Points Forts (Niveau {recommended_level})\n")
        for win in vendor_a_wins:
            lines.append(f"- {win}")
        lines.append("\n")

    # Selling arguments
    selling_args = recommendation.get("selling_arguments", [])
    if selling_args:
        lines.append("### Arguments de Vente\n")
        for arg in selling_args:
            lines.append(f"- {arg}")
        lines.append("\n")

    # Vendor B wins (acknowledged gaps)
    vendor_b_wins = recommendation.get("vendor_b_wins", [])
    counter_args = recommendation.get("counter_arguments", [])

    if vendor_b_wins or counter_args:
        lines.append("### Points à Relativiser\n")

        if vendor_b_wins:
            lines.append("**Avantages du concurrent:**\n")
            for win in vendor_b_wins:
                lines.append(f"- {win}")
            lines.append("\n")

        if counter_args:
            lines.append("**Pourquoi ce n'est pas critique:**\n")
            for arg in counter_args:
                lines.append(f"- {arg}")
            lines.append("\n")

    return "\n".join(lines)


def format_global_recommendation(recommendation: dict[str, Any]) -> str:
    """Format global recommendation as markdown.

    Args:
        recommendation: Global recommendation dict

    Returns:
        Formatted markdown section
    """
    s_level = recommendation.get("recommended_s_level", "")
    p_level = recommendation.get("recommended_p_level", "")
    s_candidates = recommendation.get("s_level_candidates", [])
    p_candidates = recommendation.get("p_level_candidates", [])
    overall_justification = recommendation.get("overall_justification", "")

    lines = [
        "# Recommandation Globale\n",
        f"## Résumé de l'étude: {s_level} & {p_level}\n",
    ]

    # Justification
    lines.append("### Recommandation\n")
    lines.append(f"{overall_justification}\n")

    # Alternatives rejected rationale
    alternatives_rationale = recommendation.get("alternatives_rejected_rationale", "")
    if alternatives_rationale:
        lines.append("### Alternatives Considérées et Rejetées\n")
        lines.append(f"{alternatives_rationale}\n")

    # Key competitive advantages
    advantages = recommendation.get("key_competitive_advantages", [])
    if advantages:
        lines.append("### Avantages Compétitifs Clés\n")
        for advantage in advantages:
            lines.append(f"- {advantage}")
        lines.append("\n")

    # Acknowledged gaps
    gaps = recommendation.get("acknowledged_gaps", [])
    if gaps:
        lines.append("### Points de Vigilance\n")
        for gap in gaps:
            lines.append(f"- {gap}")
        lines.append("\n")

    # Key talking points
    key_selling_arguments_points = recommendation.get("key_selling_arguments_points", [])
    if key_selling_arguments_points:
        lines.append("### Arguments de Vente Clés\n")
        for point in key_selling_arguments_points:
            lines.append(f"- {point}")
        lines.append("\n")

    return "\n".join(lines)


def build_recommendation_report(
    global_recommendation: dict[str, Any],
    category_recommendations: list[dict[str, Any]],
    metadata: dict[str, Any],
    comparison_tables: dict[str, str] | None = None,
) -> str:
    """Build complete recommendation report.

    Args:
        global_recommendation: Global recommendation dict
        category_recommendations: List of category recommendation dicts
        metadata: Report metadata
        comparison_tables: Optional dict mapping category_id to markdown table

    Returns:
        Complete markdown report
    """
    comparison_tables = comparison_tables or {}

    # Build report sections
    sections = []

    # Metadata header
    metadata_lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            metadata_lines.append(f"{key}: {', '.join(value)}")
        else:
            metadata_lines.append(f"{key}: {value}")
    metadata_lines.append("---\n")
    sections.append("\n".join(metadata_lines))

    # Global recommendation
    sections.append(format_global_recommendation(global_recommendation))
    sections.append("\n---\n")

    # Category recommendations
    sections.append("# Recommandations par Catégorie\n")

    for rec in category_recommendations:
        category_id = rec.get("category_name", "").lower().replace(" ", "_")
        table_markdown = comparison_tables.get(category_id)

        category_section = format_category_recommendation(rec, table_markdown)
        sections.append(category_section)
        sections.append("\n---\n")

    return "\n".join(sections)
