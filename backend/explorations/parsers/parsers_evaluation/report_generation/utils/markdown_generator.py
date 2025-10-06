"""Markdown generator for comparison tables and analysis.

Simple wrapper around existing json_formatters utilities.
"""

from typing import Any


def generate_comparison_markdown(
    comparison_table: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> str:
    """
    Generate markdown report from comparison table and analysis.

    Args:
        comparison_table: ComparisonTable dict
        analysis: CategoryAnalysis dict (optional)

    Returns:
        Markdown string
    """
    from utils.json_formatters import (
        comparison_table_to_markdown,
        analysis_to_markdown,
    )

    # Generate table markdown
    table_md = comparison_table_to_markdown(comparison_table)

    # Generate analysis markdown if provided
    if analysis:
        analysis_md = analysis_to_markdown(analysis)
        return f"{table_md}\n\n{analysis_md}"
    else:
        return table_md
