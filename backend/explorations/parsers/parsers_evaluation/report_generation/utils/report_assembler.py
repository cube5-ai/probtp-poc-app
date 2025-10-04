"""Report assembler utilities for two-phase pipeline."""
from typing import Any


def format_comparison_table_from_data(
    category: str,
    benefits: list[dict[str, str]],
    probtp_levels: list[str] | None = None,
    axa_levels: list[str] | None = None
) -> str:
    """
    Format a comparison table in Markdown from structured data.

    Args:
        category: Category name
        benefits: List of benefit dicts with coverage data
        probtp_levels: ProBTP levels for column headers
        axa_levels: AXA levels for column headers

    Returns:
        Markdown table string
    """
    # Build column headers
    probtp_label = f"ProBTP {'/'.join(probtp_levels)}" if probtp_levels else "ProBTP"
    axa_label = f"AXA {'/'.join(axa_levels)}" if axa_levels else "AXA"

    header = f"| Prestation | {probtp_label} | Conditions | {axa_label} | Conditions | Avantage |"
    separator = "|" + "|".join(["---" for _ in range(6)]) + "|"

    rows = []
    for benefit in benefits:
        benefit_name = benefit.get("benefit_name", "")
        probtp_cov = benefit.get("probtp_coverage", "-")
        probtp_cond = benefit.get("probtp_conditions", "-")
        axa_cov = benefit.get("axa_coverage", "-")
        axa_cond = benefit.get("axa_conditions", "-")

        # Determine advantage
        advantage = _determine_advantage(
            benefit_name, probtp_cov, axa_cov, probtp_cond, axa_cond
        )

        row = f"| {benefit_name} | {probtp_cov} | {probtp_cond} | {axa_cov} | {axa_cond} | {advantage} |"
        rows.append(row)

    return "\n".join([header, separator] + rows)


def _determine_advantage(
    benefit_name: str,
    probtp_cov: str,
    axa_cov: str,
    probtp_cond: str,
    axa_cond: str
) -> str:
    """
    Simple heuristic to determine advantage (can be enhanced with LLM call).

    Args:
        benefit_name: Name of the benefit
        probtp_cov: ProBTP coverage
        axa_cov: AXA coverage
        probtp_cond: ProBTP conditions
        axa_cond: AXA conditions

    Returns:
        Advantage string
    """
    # Simple rules - can be replaced with LLM-based comparison
    if probtp_cov in ["Non couvert", "-"] and axa_cov not in ["Non couvert", "-"]:
        return "**AXA uniquement**"
    elif axa_cov in ["Non couvert", "-"] and probtp_cov not in ["Non couvert", "-"]:
        return "**ProBTP uniquement**"
    elif probtp_cov == axa_cov and probtp_cond == axa_cond:
        return "Équivalent"
    else:
        return "À analyser"


def assemble_category_section(
    category: str,
    table_markdown: str,
    analysis_data: dict,
    probtp_levels: list[str] | None = None,
    axa_levels: list[str] | None = None
) -> str:
    """
    Assemble a complete category section with table and insights.

    Args:
        category: Category name
        table_markdown: Markdown table from Phase 1 (raw aligned data)
        analysis_data: Analysis and insights data from Phase 2
        probtp_levels: ProBTP levels
        axa_levels: AXA levels

    Returns:
        Markdown section string
    """
    sections = []

    # Category header
    sections.append(f"### {category}")
    sections.append("")

    # Raw comparison table (for salespeople to verify and analyze)
    sections.append("#### Tableau Comparatif Aligné")
    sections.append("")
    sections.append("*Données brutes alignées pour analyse manuelle*")
    sections.append("")
    sections.append(table_markdown)
    sections.append("")

    # AI-generated analysis sections
    sections.append(f"#### Analyse IA - {category}")
    sections.append("")
    sections.append("*Insights générés par IA pour compléter votre analyse*")
    sections.append("")

    # Key differences
    if "key_differences" in analysis_data:
        sections.append("**Principales Différences:**")
        sections.append(analysis_data["key_differences"])
        sections.append("")

    # Concrete examples
    if "concrete_examples" in analysis_data:
        sections.append("**Exemples Concrets:**")
        for example in analysis_data["concrete_examples"]:
            sections.append(f"- {example}")
        sections.append("")

    # Critical thinking
    if "critical_thinking" in analysis_data:
        sections.append("**Analyse Critique:**")
        sections.append(analysis_data["critical_thinking"])
        sections.append("")

    # Best coverage
    if "best_coverage" in analysis_data:
        sections.append("**Meilleure Couverture:**")
        sections.append(analysis_data["best_coverage"])
        sections.append("")

    sections.append("---")
    sections.append("")

    return "\n".join(sections)


def assemble_full_report(
    executive_summary: str,
    category_sections: list[str],
    overall_recommendation: str,
    metadata: dict[str, Any] | None = None
) -> str:
    """
    Assemble the complete report from all components.

    Args:
        executive_summary: Executive summary section
        category_sections: List of formatted category sections
        overall_recommendation: Overall recommendation section
        metadata: Optional report metadata

    Returns:
        Complete Markdown report
    """
    sections = []

    # Title
    sections.append("# Rapport Comparatif des Contrats de Santé")
    sections.append("")

    # Metadata (optional)
    if metadata:
        sections.append("**Métadonnées du Rapport:**")
        for key, value in metadata.items():
            sections.append(f"- **{key}:** {value}")
        sections.append("")

    sections.append("---")
    sections.append("")

    # Executive Summary
    sections.append("## 1. Synthèse Exécutive")
    sections.append("")
    sections.append(executive_summary)
    sections.append("")
    sections.append("---")
    sections.append("")

    # Category Sections
    sections.append("## 2. Comparaisons par Catégorie")
    sections.append("")
    for category_section in category_sections:
        sections.append(category_section)

    # Overall Recommendation
    sections.append("## 3. Recommandation Globale")
    sections.append("")
    sections.append(overall_recommendation)
    sections.append("")

    return "\n".join(sections)
