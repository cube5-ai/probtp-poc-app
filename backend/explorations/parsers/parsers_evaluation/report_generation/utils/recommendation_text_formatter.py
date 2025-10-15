"""Utilities for formatting category recommendations to text for prompt context."""

from typing import Any


def format_category_recommendation_to_text(recommendation: dict[str, Any]) -> str:
    """Format a single category recommendation to readable text.

    Excludes coverage tables (which are shown separately) and focuses on
    the analysis, conclusions, and arguments.

    Args:
        recommendation: CategoryRecommendation dict

    Returns:
        Formatted text representation
    """
    category_name = recommendation.get("category_name", "Unknown")
    recommended_level = recommendation.get("recommended_vendor_a_ref_level", "")

    # Screening results
    too_weak = recommendation.get("too_weak_levels", [])
    excessive = recommendation.get("excessive_levels", [])
    shortlisted = recommendation.get("shortlisted_levels", [])

    # Analysis
    other_candidates = recommendation.get("other_candidates", [])
    equivalent_coverage = recommendation.get("equivalent_coverage_examples", [])
    vendor_a_wins = recommendation.get("vendor_a_ref_wins", [])
    selling_args = recommendation.get("selling_arguments", [])
    vendor_b_wins = recommendation.get("vendor_b_wins", [])
    counter_args = recommendation.get("counter_arguments", [])

    # Summary
    section_title = recommendation.get("section_title", "")
    summary = recommendation.get("summary_paragraph", "")

    lines = []
    lines.append(f"## {category_name}")
    lines.append("")

    # Recommendation
    lines.append(f"**Recommended Level**: {recommended_level}")
    lines.append("")

    # Screening summary
    lines.append("**Level Screening**:")
    if shortlisted:
        lines.append(f"- Shortlisted: {', '.join(shortlisted)}")
    if too_weak:
        lines.append(f"- Too weak: {', '.join(too_weak)}")
    if excessive:
        lines.append(f"- Excessive: {', '.join(excessive)}")
    lines.append("")

    # Other candidates (why not selected)
    if other_candidates:
        lines.append("**Other Candidates Considered**:")
        for candidate in other_candidates:
            level = candidate.get("level", "")
            reason = candidate.get("reason_not_selected", "")
            lines.append(f"- **{level}**: {reason}")
        lines.append("")

    # Analysis of recommended level
    if equivalent_coverage:
        lines.append("**Equivalent Coverage**:")
        for item in equivalent_coverage:
            lines.append(f"- {item}")
        lines.append("")

    if vendor_a_wins:
        lines.append("**Vendor A Wins**:")
        for item in vendor_a_wins:
            lines.append(f"- {item}")
        if selling_args:
            lines.append("")
            lines.append("*Selling Arguments*:")
            for arg in selling_args:
                lines.append(f"  - {arg}")
        lines.append("")

    if vendor_b_wins:
        lines.append("**Vendor B Wins**:")
        for item in vendor_b_wins:
            lines.append(f"- {item}")
        if counter_args:
            lines.append("")
            lines.append("*Counter Arguments*:")
            for arg in counter_args:
                lines.append(f"  - {arg}")
        lines.append("")

    # Summary
    if summary:
        lines.append("**Summary**:")
        lines.append(summary)
        lines.append("")

    return "\n".join(lines)


def format_category_recommendations_to_text(
    recommendations: list[dict[str, Any]],
    include_tables: bool = False,
) -> str:
    """Format multiple category recommendations to readable text.

    Args:
        recommendations: List of CategoryRecommendation dicts
        include_tables: If True, include coverage_table_markdown. If False (default), exclude tables.

    Returns:
        Formatted text with all recommendations
    """
    sections = []

    for rec in recommendations:
        # Add the textual analysis
        text = format_category_recommendation_to_text(rec)
        sections.append(text)

        # Optionally add the coverage table
        if include_tables:
            table = rec.get("coverage_table_markdown", "")
            if table:
                sections.append("**Coverage Table**:")
                sections.append(table)
                sections.append("")

    return "\n".join(sections)
