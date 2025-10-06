"""
Two-phase pipeline for insurance policy comparison report generation.

Phase 1: Extract aligned comparison tables per category (structured JSON)
Phase 2: Generate insights and analysis from tables (structured JSON)
Phase 3: Generate overall summary across all categories (structured JSON)
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from langfuse import Langfuse, observe

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from prompts.alignment_prompt import ComparisonTable, create_alignment_prompt
from prompts.analysis_prompt import AnalysisOutput, create_analysis_prompt
from prompts.summary_prompt import ComparisonSummary, create_summary_prompt
from utils.document_loader import load_document_pair
from utils.gemini_client import generate_with_reasoning
from utils.json_formatters import analysis_to_markdown, summary_to_markdown
from utils.report_formatter import create_report_metadata, save_report

load_dotenv()


langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)

# Default categories to analyze
DEFAULT_CATEGORIES = [
    "Soins Courants",
    "Hospitalisation",
    "Optique",
    "Soins Dentaires",
    "Audiologie",
    "Médecines Douces",
]

# Category to ProBTP level type mapping
# "S" levels = Soins (care) categories
# "P" levels = Prévoyance (prevention/specialized) categories
CATEGORY_LEVEL_MAPPING = {
    "Soins Courants": "S",
    "Hospitalisation": "S",
    "Optique": "P",
    "Soins Dentaires": "P",
    "Audiologie": "P",
    "Médecines Douces": "P",
}


def filter_probtp_levels_for_category(
    category: str, all_probtp_levels: list[str] | None
) -> list[str] | None:
    """
    Filter ProBTP levels appropriate for a given category.

    Args:
        category: Category name
        all_probtp_levels: All ProBTP levels provided

    Returns:
        Filtered list of levels appropriate for the category, or None if no levels provided
    """
    if not all_probtp_levels:
        return None

    # Get the level type for this category (S or P)
    level_type = CATEGORY_LEVEL_MAPPING.get(category)

    if not level_type:
        # Category not in mapping, return all levels
        return all_probtp_levels

    # Filter levels that start with the appropriate type
    filtered_levels = [
        level for level in all_probtp_levels if level.startswith(level_type)
    ]

    return filtered_levels if filtered_levels else None


@observe(name="phase_1_alignment")
async def extract_comparison_table(
    probtp_markdown: str,
    axa_markdown: str,
    category: str,
    probtp_levels: list[str] | None = None,
    axa_levels: list[str] | None = None,
    language: str = "French (France)",
) -> dict:
    """
    Phase 1: Extract structured comparison table for a category.

    Args:
        probtp_markdown: ProBTP document markdown
        axa_markdown: AXA document markdown
        category: Category to extract
        probtp_levels: ProBTP levels
        axa_levels: AXA levels
        language: Output language

    Returns:
        ComparisonTable dict (JSON)
    """
    print(f"  [Phase 1] Extracting table for: {category}")

    # Add Langfuse metadata
    langfuse.update_current_trace(
        metadata={
            "category": category,
            "probtp_levels": probtp_levels,
            "axa_levels": axa_levels,
            "language": language,
            "phase": "alignment",
        }
    )

    prompt = create_alignment_prompt(
        probtp_markdown=probtp_markdown,
        axa_markdown=axa_markdown,
        category=category,
        probtp_levels=probtp_levels,
        axa_levels=axa_levels,
        language=language,
    )

    response = await generate_with_reasoning(
        prompt=prompt,
        model="gemini-2.5-flash",
        thinking_budget=4096,
        temperature=0.2,
        response_mime_type="application/json",
        response_schema=ComparisonTable.model_json_schema(),
    )

    try:
        comparison_table = json.loads(response)

        # Post-processing: Validate and fix table structure
        from utils.table_validator import validate_and_fix_table

        comparison_table, validation_log = await validate_and_fix_table(
            table=comparison_table, category=category, max_iterations=3
        )

        # Track output metrics including validation
        langfuse.update_current_trace(
            output={"row_count": len(comparison_table.get("rows", []))},
            metadata={"success": True, "validation": validation_log},
        )

        return comparison_table
    except json.JSONDecodeError as e:
        print(f"    ✗ Failed to parse JSON for {category}: {e}")

        # Track error
        langfuse.update_current_trace(metadata={"success": False, "error": str(e)})

        return {
            "metadata": {
                "category": category,
                "policy_levels": {
                    "probtp": probtp_levels or [],
                    "axa": axa_levels or [],
                },
            },
            "rows": [],
        }


@observe(name="phase_2_analysis")
async def generate_category_analysis(
    comparison_table: dict, language: str = "French (France)"
) -> dict:
    """
    Phase 2: Generate insights and analysis from comparison table.

    Args:
        comparison_table: ComparisonTable dict from Phase 1
        language: Output language

    Returns:
        AnalysisOutput dict (JSON)
    """
    category = comparison_table.get("metadata", {}).get("category", "Unknown")
    print(f"  [Phase 2] Generating analysis for: {category}")

    # Add Langfuse metadata
    langfuse.update_current_trace(
        metadata={
            "category": category,
            "language": language,
            "phase": "analysis",
            "input_row_count": len(comparison_table.get("rows", [])),
        }
    )

    prompt = create_analysis_prompt(
        comparison_table=comparison_table, language=language
    )

    response = await generate_with_reasoning(
        prompt=prompt,
        model="gemini-2.5-flash",
        thinking_budget=4096,
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=AnalysisOutput.model_json_schema(),
    )

    try:
        analysis_data = json.loads(response)

        # Post-processing: Validate analysis preserves alignment structure
        from utils.analysis_validator import validate_and_fix_analysis_table

        annotated_table = analysis_data.get("annotated_table", {})
        corrected_table, validation_log = await validate_and_fix_analysis_table(
            alignment_table=comparison_table,
            analysis_table=annotated_table,
            category=category,
        )
        analysis_data["annotated_table"] = corrected_table

        # Track output metrics
        objective_assessment = analysis_data.get("objective_assessment", {})
        langfuse.update_current_trace(
            output={
                "winner": objective_assessment.get("overall_winner"),
                "talking_points_count": len(
                    analysis_data.get("salesperson_talking_points", [])
                ),
            },
            metadata={"success": True, "analysis_validation": validation_log},
        )

        return analysis_data
    except json.JSONDecodeError as e:
        print(f"    ✗ Failed to parse JSON for {category}: {e}")

        # Track error
        langfuse.update_current_trace(metadata={"success": False, "error": str(e)})

        return {
            "category": category,
            "annotated_table": comparison_table,
            "key_differences": "",
            "concrete_examples": [],
            "critical_thinking": "",
            "best_coverage": "",
            "salesperson_talking_points": [],
            "objective_assessment": {
                "overall_winner": "unknown",
                "confidence": "low",
                "reasoning": "Failed to generate analysis",
                "probtp_weaknesses": [],
                "axa_weaknesses": [],
            },
        }


@observe(name="phase_3_summary")
async def generate_general_summary(
    all_analyses: list[dict], language: str = "French (France)"
) -> dict:
    """
    Phase 3: Generate general summary from all category analyses.

    Args:
        all_analyses: List of AnalysisOutput dicts for all categories
        language: Output language

    Returns:
        ComparisonSummary dict (JSON)
    """
    print("  [Phase 3] Generating general summary...")

    # Add Langfuse metadata
    langfuse.update_current_trace(
        metadata={
            "language": language,
            "phase": "summary",
            "category_count": len(all_analyses),
        }
    )

    # Extract relevant fields from each analysis
    category_analyses = []
    for analysis in all_analyses:
        category_analyses.append(
            {
                "category": analysis.get("category", "Unknown"),
                "key_differences": analysis.get("key_differences", ""),
                "critical_thinking": analysis.get("critical_thinking", ""),
                "best_coverage": analysis.get("best_coverage", ""),
                "salesperson_talking_points": analysis.get(
                    "salesperson_talking_points", []
                ),
                "objective_assessment": analysis.get("objective_assessment", {}),
            }
        )

    prompt = create_summary_prompt(
        category_analyses=category_analyses, language=language
    )

    response = await generate_with_reasoning(
        prompt=prompt,
        model="gemini-2.5-flash",
        thinking_budget=4096,
        temperature=0.4,
        response_mime_type="application/json",
        response_schema=ComparisonSummary.model_json_schema(),
    )

    try:
        summary_data = json.loads(response)

        # Track output metrics
        objective_eval = summary_data.get("objective_evaluation", {})
        langfuse.update_current_trace(
            output={
                "overall_winner": objective_eval.get("overall_winner"),
                "selling_points_count": len(summary_data.get("selling_points", [])),
            },
            metadata={"success": True},
        )

        return summary_data
    except json.JSONDecodeError as e:
        print(f"    ✗ Failed to parse summary JSON: {e}")

        # Track error
        langfuse.update_current_trace(metadata={"success": False, "error": str(e)})

        return {
            "key_differences": "",
            "category_strengths": [],
            "probtp_overall_strengths": [],
            "axa_overall_strengths": [],
            "objective_evaluation": {
                "overall_winner": "unknown",
                "confidence": "low",
                "reasoning": "Failed to generate summary",
            },
            "category_winners": [],
            "selling_points": [],
            "target_customer_fit": "",
        }


async def generate_overall_recommendation(
    all_analyses: list[dict], language: str = "French (France)"
) -> str:
    """
    Generate overall recommendation from all category analyses.

    Args:
        all_analyses: List of analysis data for all categories
        language: Output language

    Returns:
        Overall recommendation text
    """
    print("  [Recommendation] Generating overall recommendation...")

    talking_points = []
    for analysis in all_analyses:
        if "salesperson_talking_points" in analysis:
            talking_points.extend(analysis["salesperson_talking_points"])

    talking_points_text = "\n".join([f"- {tp}" for tp in talking_points])

    prompt = f"""You are an expert insurance analyst. Based on the category analyses, write an overall recommendation section.

**Language:** Write in {language}.

**Structure:**
1. Strengths & Weaknesses Summary (bullet points for each contract)
2. Decision Factors (key questions a salesperson should ask the customer)
3. Final Guidance (2-3 paragraphs)

**Talking Points from Analyses:**

{talking_points_text}

**Output:** Return ONLY the recommendation section in {language}. No JSON, no preamble."""

    response = await generate_with_reasoning(
        prompt=prompt,
        model="gemini-2.5-flash",
        thinking_budget=2048,
        temperature=0.4,
        response_mime_type="text/plain",
    )

    return response


async def process_single_category(
    category: str,
    index: int,
    total: int,
    probtp_markdown: str,
    axa_markdown: str,
    probtp_levels: list[str] | None,
    axa_levels: list[str] | None,
    language: str,
) -> tuple[str, dict, dict]:
    """
    Process a single category: extract table and generate analysis.

    Args:
        category: Category name
        index: Category index (for logging)
        total: Total number of categories (for logging)
        probtp_markdown: ProBTP document markdown
        axa_markdown: AXA document markdown
        probtp_levels: ProBTP levels
        axa_levels: AXA levels
        language: Output language

    Returns:
        Tuple of (category, comparison_table, analysis_data)
    """
    print(f"\n[{index}/{total}] Processing: {category}")

    # Filter ProBTP levels for this category
    category_probtp_levels = filter_probtp_levels_for_category(category, probtp_levels)

    if category_probtp_levels and category_probtp_levels != probtp_levels:
        print(f"  → Filtered ProBTP levels for {category}: {category_probtp_levels}")

    # Phase 1: Extract comparison table (structured JSON)
    comparison_table = await extract_comparison_table(
        probtp_markdown=probtp_markdown,
        axa_markdown=axa_markdown,
        category=category,
        probtp_levels=category_probtp_levels,
        axa_levels=axa_levels,
        language=language,
    )

    # Phase 2: Generate analysis from structured table (structured JSON)
    analysis_data = await generate_category_analysis(
        comparison_table=comparison_table, language=language
    )

    return (category, comparison_table, analysis_data)


@observe(name="two_phase_report_generation")
async def generate_two_phase_report(
    probtp_path: str | Path,
    axa_path: str | Path,
    output_path: str | Path,
    probtp_levels: list[str] | None = None,
    axa_levels: list[str] | None = None,
    categories: list[str] | None = None,
    language: str = "French (France)",
) -> dict:
    """
    Generate a complete comparison report using two-phase pipeline.

    Args:
        probtp_path: Path to ProBTP document JSON
        axa_path: Path to AXA document JSON
        output_path: Path to save the generated report
        probtp_levels: Optional ProBTP contract levels
        axa_levels: Optional AXA contract levels
        categories: Optional list of categories to compare
        language: Language for the report (default: "French (France)")

    Returns:
        Dictionary with generation metadata
    """
    print("=" * 80)
    print("Two-Phase Pipeline: Structured Report Generation")
    print("=" * 80)

    start_time = time.time()

    # Add top-level Langfuse metadata
    langfuse.update_current_trace(
        name="insurance_comparison_report",
        user_id=os.getenv("USER", "unknown"),
        metadata={
            "probtp_document": str(probtp_path),
            "axa_document": str(axa_path),
            "probtp_levels": probtp_levels,
            "axa_levels": axa_levels,
            "language": language,
            "output_path": str(output_path),
        },
        tags=["insurance", "comparison", "report", "two-phase"],
    )

    # Load documents
    print("\n[Setup] Loading documents...")
    probtp_doc, axa_doc = load_document_pair(probtp_path, axa_path)
    print(f"  ✓ ProBTP: {probtp_doc.name}")
    print(f"  ✓ AXA: {axa_doc.name}")

    # Use expanded markdown with tables showing duplicated cell values for spans
    # This helps the LLM understand the table structure better
    probtp_markdown = probtp_doc.get_markdown_with_expanded_tables()
    axa_markdown = axa_doc.get_markdown_with_expanded_tables()

    # Use default categories if not specified
    if categories is None:
        categories = DEFAULT_CATEGORIES

    print(f"\n[Setup] Processing {len(categories)} categories...")

    # Create tmp directory for intermediate outputs
    tmp_dir = Path(__file__).parent.parent / "output" / "two_phase" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ Intermediate outputs will be saved to: {tmp_dir}")

    all_comparison_tables = []
    all_analyses = []

    if len(categories) > 0:
        # Process first category alone to warm up prompt cache
        print(f"\n[1/{len(categories)}] Processing (cache warming): {categories[0]}")
        first_category, first_table, first_analysis = await process_single_category(
            category=categories[0],
            index=1,
            total=len(categories),
            probtp_markdown=probtp_markdown,
            axa_markdown=axa_markdown,
            probtp_levels=probtp_levels,
            axa_levels=axa_levels,
            language=language,
        )

        all_comparison_tables.append(first_table)
        all_analyses.append(first_analysis)

        # Save intermediate outputs
        with open(tmp_dir / f"{first_category}_table.json", 'w', encoding='utf-8') as f:
            json.dump(first_table, f, ensure_ascii=False, indent=2)
        with open(tmp_dir / f"{first_category}_analysis.json", 'w', encoding='utf-8') as f:
            json.dump(first_analysis, f, ensure_ascii=False, indent=2)

    # Process remaining categories in parallel (cache is now warmed)
    if len(categories) > 1:
        print(
            f"\n[Parallel] Processing remaining {len(categories) - 1} categories with cached prompts..."
        )

        tasks = [
            process_single_category(
                category=category,
                index=i,
                total=len(categories),
                probtp_markdown=probtp_markdown,
                axa_markdown=axa_markdown,
                probtp_levels=probtp_levels,
                axa_levels=axa_levels,
                language=language,
            )
            for i, category in enumerate(categories[1:], 2)
        ]

        # Gather results - order is preserved!
        results = await asyncio.gather(*tasks)

        # Process results in order
        for category, comparison_table, analysis_data in results:
            all_comparison_tables.append(comparison_table)
            all_analyses.append(analysis_data)

            # Save intermediate outputs
            with open(tmp_dir / f"{category}_table.json", 'w', encoding='utf-8') as f:
                json.dump(comparison_table, f, ensure_ascii=False, indent=2)
            with open(tmp_dir / f"{category}_analysis.json", 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)

    # Phase 3: Generate general summary
    print("\n[Phase 3] Generating general summary...")
    general_summary = await generate_general_summary(all_analyses, language)

    # Save general summary intermediate output
    with open(tmp_dir / "general_summary.json", 'w', encoding='utf-8') as f:
        json.dump(general_summary, f, ensure_ascii=False, indent=2)

    # Generate recommendation
    print("\n[Final] Generating overall recommendation...")
    overall_recommendation = await generate_overall_recommendation(
        all_analyses, language
    )

    # Assemble full report
    print("\n[Assembly] Assembling final report...")

    # Convert structured data to markdown
    report_sections = []

    # Summary section
    report_sections.append(summary_to_markdown(general_summary))
    report_sections.append("\n---\n")

    # Category sections
    for analysis in all_analyses:
        report_sections.append(analysis_to_markdown(analysis))
        report_sections.append("\n---\n")

    # Recommendation section
    report_sections.append("## Recommandations Globales\n")
    report_sections.append(overall_recommendation)
    report_sections.append("\n")

    # Metadata
    metadata_extra = {}
    if probtp_levels:
        metadata_extra["probtp_levels"] = probtp_levels
    if axa_levels:
        metadata_extra["axa_levels"] = axa_levels
    if categories:
        metadata_extra["categories"] = categories

    metadata = create_report_metadata(
        probtp_doc_name=probtp_doc.name,
        axa_doc_name=axa_doc.name,
        model="gemini-2.5-flash",
        **metadata_extra,
    )

    # Build full report
    full_report = "---\n"
    for key, value in metadata.items():
        if isinstance(value, list):
            full_report += f"{key}: {', '.join(value)}\n"
        else:
            full_report += f"{key}: {value}\n"
    full_report += "---\n\n"
    full_report += "\n".join(report_sections)

    # Save report
    generation_time = time.time() - start_time
    print(f"\n[Save] Saving report to {output_path}...")
    save_report(full_report, output_path)
    print("  ✓ Report saved successfully")

    # Save JSON outputs for debugging
    json_output_path = Path(output_path).with_suffix(".json")
    json_data = {
        "metadata": metadata,
        "comparison_tables": all_comparison_tables,
        "analyses": all_analyses,
        "general_summary": general_summary,
        "overall_recommendation": overall_recommendation,
    }
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ JSON data saved to {json_output_path}")

    print("\n" + "=" * 80)
    print("Pipeline Complete!")
    print("=" * 80)
    print(f"Generation time: {generation_time:.2f}s")
    print(f"Categories processed: {len(categories)}")
    print(f"Report length: {len(full_report)} characters")

    # Final trace update
    result = {
        "generation_time_seconds": generation_time,
        "model": "gemini-2.5-flash (two-phase)",
        "categories_processed": len(categories),
        "report_length_chars": len(full_report),
        "probtp_document": probtp_doc.name,
        "axa_document": axa_doc.name,
        "output_path": str(output_path),
        "json_output_path": str(json_output_path),
    }

    # Update trace with final results
    langfuse.update_current_trace(
        output=result,
        metadata={
            "generation_time_seconds": generation_time,
            "categories_processed": len(categories),
            "report_length_chars": len(full_report),
            "pipeline_complete": True,
        },
    )

    return result


def main():
    """Main function for testing the two-phase pipeline."""
    # Define paths
    base_dir = Path(__file__).parent.parent.parent
    output_base = base_dir / "output" / "landing_ai_xtd"

    # Use available documents
    probtp_path = output_base / "File #3 - Panorama FMC 2025.json"
    axa_path = (
        output_base
        / "File #1 - Laurent M - Conditions particulières - Socle AXA - SAE.json"
    )

    # Output path with levels in filename
    output_dir = Path(__file__).parent.parent / "output" / "two_phase"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build filename with levels
    probtp_levels = ["S2", "P4"]
    axa_levels = ["Base Obligatoire"]
    probtp_level_str = "_".join(probtp_levels).replace("+", "plus")
    axa_level_str = "_".join(axa_levels).replace(" ", "_")
    output_path = (
        output_dir
        / f"comparison_report_ProBTP_{probtp_level_str}_vs_AXA_{axa_level_str}.md"
    )

    # Check if documents exist
    if not probtp_path.exists():
        print(f"Error: ProBTP document not found: {probtp_path}")
        return

    if not axa_path.exists():
        print(f"Error: AXA document not found: {axa_path}")
        return

    # Run pipeline
    print("\nStarting two-phase report generation...")
    print(f"ProBTP document: {probtp_path.name}")
    print(f"AXA document: {axa_path.name}")
    print(f"Output: {output_path}")
    print()

    # Generate report
    result = asyncio.run(
        generate_two_phase_report(
            probtp_path=probtp_path,
            axa_path=axa_path,
            output_path=output_path,
            probtp_levels=probtp_levels,
            axa_levels=axa_levels,
        )
    )

    # Print summary
    print("\n" + "=" * 80)
    print("GENERATION SUMMARY")
    print("=" * 80)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
