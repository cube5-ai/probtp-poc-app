"""
Regenerate report from tmp JSON files.

This script reads the intermediate JSON outputs from tmp directory
and regenerates the markdown report without re-running the LLM calls.
"""
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.json_formatters import analysis_to_markdown, summary_to_markdown
from utils.report_formatter import create_report_metadata, save_report


def regenerate_report_from_tmp(tmp_dir: Path, output_path: Path):
    """
    Regenerate report from tmp JSON files.

    Args:
        tmp_dir: Path to tmp directory containing JSON files
        output_path: Path to save the regenerated report
    """
    print("=" * 80)
    print("Regenerating Report from Tmp Files")
    print("=" * 80)

    # Find all analysis files
    analysis_files = sorted(tmp_dir.glob("*_analysis.json"))

    if not analysis_files:
        print(f"  ✗ No analysis files found in {tmp_dir}")
        return

    print(f"\n  ✓ Found {len(analysis_files)} analysis files")

    # Load all analyses
    all_analyses = []
    categories = []

    for analysis_file in analysis_files:
        print(f"  Loading: {analysis_file.name}")
        with open(analysis_file, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
            all_analyses.append(analysis)
            categories.append(analysis.get("category", "Unknown"))

    # Load general summary
    summary_file = tmp_dir / "general_summary.json"
    if summary_file.exists():
        print(f"\n  Loading: {summary_file.name}")
        with open(summary_file, 'r', encoding='utf-8') as f:
            general_summary = json.load(f)
    else:
        print(f"  ⚠ No general_summary.json found, skipping summary section")
        general_summary = None

    # Assemble report
    print("\n[Assembly] Assembling report sections...")

    report_sections = []

    # Summary section
    if general_summary:
        report_sections.append(summary_to_markdown(general_summary))
        report_sections.append("\n---\n")

    # Category sections
    for analysis in all_analyses:
        report_sections.append(analysis_to_markdown(analysis))
        report_sections.append("\n---\n")

    # Create metadata
    metadata = {
        "Generated": "Regenerated from tmp files",
        "Model": "N/A (using cached outputs)",
        "Categories": ", ".join(categories)
    }

    # Build full report
    full_report = "---\n"
    for key, value in metadata.items():
        full_report += f"{key}: {value}\n"
    full_report += "---\n\n"
    full_report += "\n".join(report_sections)

    # Save report
    print(f"\n[Save] Saving report to {output_path}...")
    save_report(full_report, output_path)
    print(f"  ✓ Report saved successfully")

    print("\n" + "=" * 80)
    print("Regeneration Complete!")
    print("=" * 80)
    print(f"Report length: {len(full_report)} characters")
    print(f"Categories: {len(categories)}")


def main():
    """Main function."""
    # Define paths
    tmp_dir = Path(__file__).parent.parent / "output" / "two_phase" / "tmp"
    output_dir = Path(__file__).parent.parent / "output" / "two_phase"
    output_path = output_dir / "comparison_report_REGENERATED.md"

    # Check if tmp directory exists
    if not tmp_dir.exists():
        print(f"Error: tmp directory not found: {tmp_dir}")
        return

    # Regenerate report
    regenerate_report_from_tmp(tmp_dir, output_path)


if __name__ == "__main__":
    main()
