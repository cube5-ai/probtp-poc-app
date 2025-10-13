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

    # Build markdown
    lines = [f"## {section_title}\n"]

    # Summary paragraph
    if summary:
        lines.append(f"{summary}\n")

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
    overall_justification = recommendation.get("overall_justification", "")

    lines = [
        "# Recommandation Globale\n",
        f"## Niveaux Recommandés: {s_level} + {p_level}\n",
        f"{overall_justification}\n",
    ]

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

    # Target customer profile
    target_profile = recommendation.get("target_customer_profile", "")
    if target_profile:
        lines.append("### Profil Client Idéal\n")
        lines.append(f"{target_profile}\n")

    # Key talking points
    talking_points = recommendation.get("key_talking_points", [])
    if talking_points:
        lines.append("### Points Clés pour le Commercial\n")
        for point in talking_points:
            lines.append(f"- {point}")
        lines.append("\n")

    # Category justifications
    category_justifications = recommendation.get("category_justifications", [])
    if category_justifications:
        lines.append("### Justification par Catégorie\n")
        for item in category_justifications:
            if isinstance(item, dict):
                category_name = item.get("category_name", "Unknown")
                justification = item.get("justification", "")
                lines.append(f"**{category_name}**: {justification}\n")
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
