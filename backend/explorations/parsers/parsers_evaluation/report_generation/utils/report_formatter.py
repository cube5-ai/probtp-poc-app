"""Report formatting utilities for insurance comparison reports."""
from datetime import datetime
from pathlib import Path
from typing import Any


def format_markdown_report(
    executive_summary: str,
    category_sections: list[dict[str, str]],
    overall_recommendation: str,
    metadata: dict[str, Any] | None = None
) -> str:
    """
    Format a complete comparison report in Markdown.

    Args:
        executive_summary: Executive summary section
        category_sections: List of dicts with 'category', 'table', 'insights'
        overall_recommendation: Final recommendation section
        metadata: Optional metadata (generation time, model, etc.)

    Returns:
        Formatted markdown report
    """
    sections = []

    # Header
    sections.append("# Insurance Policy Comparison Report")
    sections.append("")

    # Metadata
    if metadata:
        sections.append("**Report Metadata:**")
        for key, value in metadata.items():
            sections.append(f"- {key}: {value}")
        sections.append("")

    sections.append("---")
    sections.append("")

    # Executive Summary
    sections.append("## Executive Summary")
    sections.append("")
    sections.append(executive_summary)
    sections.append("")
    sections.append("---")
    sections.append("")

    # Category Comparisons
    sections.append("## Category Comparisons")
    sections.append("")

    for cat in category_sections:
        category_name = cat.get('category', 'Unknown Category')
        table = cat.get('table', '')
        insights = cat.get('insights', '')

        sections.append(f"### {category_name}")
        sections.append("")

        # Comparison table
        if table:
            sections.append(table)
            sections.append("")

        # Insights
        if insights:
            sections.append("**Key Insights:**")
            sections.append("")
            sections.append(insights)
            sections.append("")

        sections.append("---")
        sections.append("")

    # Overall Recommendation
    sections.append("## Overall Recommendation")
    sections.append("")
    sections.append(overall_recommendation)
    sections.append("")

    return "\n".join(sections)


def save_report(
    report_content: str,
    output_path: str | Path,
    metadata: dict[str, Any] | None = None
) -> None:
    """
    Save report to file with optional metadata.

    Args:
        report_content: The report content (markdown)
        output_path: Path to save the report
        metadata: Optional metadata to prepend as YAML frontmatter
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        # Optional: Add YAML frontmatter for metadata
        if metadata:
            f.write("---\n")
            for key, value in metadata.items():
                f.write(f"{key}: {value}\n")
            f.write("---\n\n")

        f.write(report_content)


def format_comparison_table_markdown(
    rows: list[dict[str, str]],
    columns: list[str] = None
) -> str:
    """
    Format a comparison table in Markdown.

    Args:
        rows: List of dicts representing table rows
        columns: Optional list of column names (if not in rows)

    Returns:
        Markdown table string

    Example:
        rows = [
            {'Benefit': 'Dental checkup', 'ProBTP': 'BR + 300%', 'AXA': 'BR + 200%', 'Advantage': 'ProBTP +50€'},
            {'Benefit': 'Orthodontics', 'ProBTP': 'Unlimited', 'AXA': '€500/year', 'Advantage': 'ProBTP'}
        ]
    """
    if not rows:
        return ""

    # Determine columns
    if columns is None:
        columns = list(rows[0].keys())

    # Header
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join(["---" for _ in columns]) + "|"

    # Rows
    table_rows = []
    for row in rows:
        row_values = [str(row.get(col, '-')) for col in columns]
        table_rows.append("| " + " | ".join(row_values) + " |")

    return "\n".join([header, separator] + table_rows)


def create_report_metadata(
    vendor_a_ref_doc_name: str,
    vendor_b_doc_name: str,
    vendor_a_ref_name: str,
    vendor_b_name: str,
    vendor_a_ref_levels: list[str] | None = None,
    vendor_b_levels: list[str] | None = None,
    model: str = "gemini-2.5-pro",
    generation_time_seconds: float | None = None,
    **extra_metadata: Any
) -> dict[str, Any]:
    """
    Create metadata dict for report.

    Args:
        vendor_a_ref_doc_name: Vendor A (reference) document name
        vendor_b_doc_name: Vendor B document name
        vendor_a_ref_name: Vendor A name (e.g., "ProBTP")
        vendor_b_name: Vendor B name (e.g., "Generali")
        vendor_a_ref_levels: Vendor A policy levels
        vendor_b_levels: Vendor B policy levels
        model: Model used for generation
        generation_time_seconds: Time taken to generate report
        **extra_metadata: Additional metadata fields (e.g., categories)

    Returns:
        Metadata dictionary
    """
    metadata = {
        "Generated": datetime.now().isoformat(),
        "Model": model,
        "Vendor A (Reference)": f"{vendor_a_ref_name} ({vendor_a_ref_doc_name})",
        "Vendor B": f"{vendor_b_name} ({vendor_b_doc_name})",
    }

    if vendor_a_ref_levels:
        metadata["Vendor A Levels"] = ", ".join(vendor_a_ref_levels)

    if vendor_b_levels:
        metadata["Vendor B Levels"] = ", ".join(vendor_b_levels)

    if generation_time_seconds is not None:
        metadata["Generation Time"] = f"{generation_time_seconds:.2f}s"

    # Add any extra metadata fields
    for key, value in extra_metadata.items():
        # Format lists nicely
        if isinstance(value, list):
            metadata[key.replace("_", " ").title()] = ", ".join(str(v) for v in value)
        else:
            metadata[key.replace("_", " ").title()] = value

    return metadata
