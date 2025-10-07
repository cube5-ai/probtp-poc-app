"""
Project-then-Merge pipeline for insurance policy comparison report generation.

Phase 1: Category Extraction
  1.1: Extract category-focused tables for each vendor (with taxonomy and ambiguous cases)
  1.2: Validate and correct table structure
  1.3: Classify ambiguous cases using ProBTP taxonomy
  1.4: Update tables with classified cases

Phase 2: Alignment and Merge
  2.1: Project AXA onto ProBTP taxonomy (semantic alignment)
  2.2: Programmatically merge into ComparisonTable format

Phase 3: Analysis and Report (reuse from two_phase_pipeline)
  3: Generate analysis for each category
  4: Generate general summary
  5: Generate final report
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
from prompts.project_then_merge.category_extraction_prompt import CategoryTable, create_category_extraction_prompt
from prompts.project_then_merge.ambiguous_classification_prompt import AmbiguousClassificationOutput, create_ambiguous_classification_prompt
from prompts.project_then_merge.projection_alignment_prompt import ProjectionAlignment, create_projection_alignment_prompt
from prompts.two_phase.analysis_prompt import AnalysisOutput, create_analysis_prompt
from prompts.two_phase.summary_prompt import ComparisonSummary, create_summary_prompt
from utils.document_loader import load_document_pair
from utils.gemini_client import generate_with_reasoning
from utils.table_validator import validate_and_fix_table
from utils.table_updater import append_classified_cases_to_table, generate_table_update_prompt
from utils.table_merger import merge_projection_to_comparison_table, validate_comparison_table_structure
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
    "Prestations Complémentaires",
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
    "Prestations Complémentaires": "P",
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


@observe(name="phase_1_1_category_extraction")
async def extract_category_table(
    vendor: str,
    markdown: str,
    category: str,
    policy_levels: list[str] | None = None,
    other_categories: list[str] | None = None,
    language: str = "French (France)",
) -> dict:
    """
    Phase 1.1: Extract category-focused table for a single vendor.

    Args:
        vendor: Vendor name (ProBTP or AXA)
        markdown: Full markdown of the contract
        category: Category to extract
        policy_levels: Policy levels for this vendor
        other_categories: Other categories (for boundary guidance)
        language: Output language

    Returns:
        CategoryTable dict
    """
    print(f"  [Phase 1.1] Extracting {vendor} table for: {category}")

    langfuse.update_current_trace(
        metadata={
            "vendor": vendor,
            "category": category,
            "policy_levels": policy_levels,
            "other_categories": other_categories,
            "language": language,
            "phase": "category_extraction",
        }
    )

    prompt = create_category_extraction_prompt(
        vendor=vendor,
        markdown=markdown,
        category=category,
        policy_levels=policy_levels,
        other_categories=other_categories,
        language=language,
    )

    response = await generate_with_reasoning(
        prompt=prompt,
        model="gemini-2.5-flash",
        thinking_budget=4096,
        temperature=0.2,
        response_mime_type="application/json",
        response_schema=CategoryTable.model_json_schema(),
    )

    try:
        category_table = json.loads(response)

        # Validate table structure
        category_table, validation_log = await validate_and_fix_table(
            table=category_table, category=category, max_iterations=3
        )

        langfuse.update_current_trace(
            output={"row_count": len(category_table.get("rows", []))},
            metadata={"success": True, "validation": validation_log},
        )

        return category_table
    except json.JSONDecodeError as e:
        print(f"    ✗ Failed to parse JSON for {vendor} {category}: {e}")
        langfuse.update_current_trace(metadata={"success": False, "error": str(e)})
        return {
            "metadata": {
                "vendor": vendor,
                "category": category,
                "policy_levels": policy_levels or [],
                "total_columns": 0,
                "column_labels": [],
            },
            "taxonomy": {"ascii_tree": "", "description": ""},
            "rows": [],
        }


@observe(name="phase_1_3_classify_ambiguous_cases")
async def classify_ambiguous_cases(
    vendor: str,
    category: str,
    ambiguous_cases: list[dict],
    probtp_taxonomy_tree: str,
    language: str = "French (France)",
) -> dict:
    """
    Phase 1.3: Classify ambiguous cases using ProBTP taxonomy.

    Args:
        vendor: Vendor name
        category: Original category
        ambiguous_cases: List of ambiguous case dicts
        probtp_taxonomy_tree: ProBTP taxonomy ASCII art
        language: Output language

    Returns:
        AmbiguousClassificationOutput dict
    """
    print(f"  [Phase 1.3] Classifying {len(ambiguous_cases)} ambiguous cases for {vendor} {category}")

    if not ambiguous_cases:
        return {
            "vendor": vendor,
            "category": category,
            "classified_cases": []
        }

    langfuse.update_current_trace(
        metadata={
            "vendor": vendor,
            "category": category,
            "ambiguous_count": len(ambiguous_cases),
            "phase": "ambiguous_classification",
        }
    )

    prompt = create_ambiguous_classification_prompt(
        vendor=vendor,
        category=category,
        ambiguous_cases=ambiguous_cases,
        probtp_taxonomy_tree=probtp_taxonomy_tree,
        language=language,
    )

    response = await generate_with_reasoning(
        prompt=prompt,
        model="gemini-2.5-flash",
        thinking_budget=2048,
        temperature=0.1,
        response_mime_type="application/json",
        response_schema=AmbiguousClassificationOutput.model_json_schema(),
    )

    try:
        classification = json.loads(response)
        langfuse.update_current_trace(
            output={"classified_count": len(classification.get("classified_cases", []))},
            metadata={"success": True},
        )
        return classification
    except json.JSONDecodeError as e:
        print(f"    ✗ Failed to parse classification JSON: {e}")
        langfuse.update_current_trace(metadata={"success": False, "error": str(e)})
        return {
            "vendor": vendor,
            "category": category,
            "classified_cases": []
        }


@observe(name="phase_1_4_update_table_with_classified_cases")
async def update_table_with_classified_cases(
    category_table: dict,
    classified_cases: list[dict],
    category: str,
    source_markdown: str,
    vendor: str,
    language: str = "French (France)",
) -> dict:
    """
    Phase 1.4: Update category table with classified ambiguous cases.

    Args:
        category_table: CategoryTable dict
        classified_cases: Classified cases from phase 1.3
        category: Category name
        source_markdown: Original contract markdown
        vendor: Vendor name
        language: Output language

    Returns:
        Updated CategoryTable dict
    """
    print(f"  [Phase 1.4] Updating {vendor} {category} table with classified cases")

    # Append placeholder rows for classified cases
    updated_table = append_classified_cases_to_table(
        category_table=category_table,
        classified_cases=classified_cases,
        category=category
    )

    # Check if we added any rows
    original_row_count = len(category_table.get("rows", []))
    updated_row_count = len(updated_table.get("rows", []))
    new_rows_count = updated_row_count - original_row_count

    if new_rows_count == 0:
        print(f"    → No new rows added for {category}")
        return category_table

    print(f"    → Added {new_rows_count} rows, filling coverage values...")

    # Generate prompt to fill in coverage values
    prompt = generate_table_update_prompt(
        category_table=updated_table,
        source_markdown=source_markdown,
        vendor=vendor,
        category=category,
        language=language
    )

    if not prompt:
        print(f"    → No prompt generated (no rows to complete)")
        return updated_table

    # Use LLM to fill in the coverage values
    response = await generate_with_reasoning(
        prompt=prompt,
        model="gemini-2.5-flash",
        thinking_budget=2048,
        temperature=0.1,
        response_mime_type="application/json",
        response_schema=CategoryTable.model_json_schema(),
    )

    try:
        completed_table = json.loads(response)
        langfuse.update_current_trace(
            output={"rows_added": new_rows_count},
            metadata={"success": True},
        )
        return completed_table
    except json.JSONDecodeError as e:
        print(f"    ✗ Failed to parse updated table JSON: {e}")
        langfuse.update_current_trace(metadata={"success": False, "error": str(e)})
        return updated_table


@observe(name="phase_2_1_projection_alignment")
async def perform_projection_alignment(
    probtp_table: dict,
    axa_table: dict,
    category: str,
    language: str = "French (France)",
) -> dict:
    """
    Phase 2.1: Project AXA onto ProBTP taxonomy (semantic alignment).

    Args:
        probtp_table: ProBTP CategoryTable
        axa_table: AXA CategoryTable
        category: Category name
        language: Output language

    Returns:
        ProjectionAlignment dict
    """
    print(f"  [Phase 2.1] Performing projection alignment for: {category}")

    langfuse.update_current_trace(
        metadata={
            "category": category,
            "phase": "projection_alignment",
        }
    )

    prompt = create_projection_alignment_prompt(
        probtp_table=probtp_table,
        axa_table=axa_table,
        category=category,
        language=language,
    )

    response = await generate_with_reasoning(
        prompt=prompt,
        model="gemini-2.5-flash",
        thinking_budget=4096,
        temperature=0.2,
        response_mime_type="application/json",
        response_schema=ProjectionAlignment.model_json_schema(),
    )

    try:
        projection = json.loads(response)
        langfuse.update_current_trace(
            output={"projected_rows_count": len(projection.get("projected_rows", []))},
            metadata={"success": True},
        )
        return projection
    except json.JSONDecodeError as e:
        print(f"    ✗ Failed to parse projection JSON: {e}")
        langfuse.update_current_trace(metadata={"success": False, "error": str(e)})
        return {
            "category": category,
            "probtp_levels": [],
            "axa_levels": [],
            "projected_rows": [],
            "coverage_gaps": {"probtp_only": [], "axa_only": []}
        }


@observe(name="phase_2_2_programmatic_merge")
async def perform_programmatic_merge(
    projection_alignment: dict,
    probtp_table: dict,
    axa_table: dict,
    category: str,
) -> dict:
    """
    Phase 2.2: Programmatically merge projection into ComparisonTable format.

    Args:
        projection_alignment: ProjectionAlignment dict
        probtp_table: ProBTP CategoryTable
        axa_table: AXA CategoryTable
        category: Category name

    Returns:
        ComparisonTable dict
    """
    print(f"  [Phase 2.2] Merging projection into ComparisonTable for: {category}")

    comparison_table = merge_projection_to_comparison_table(
        projection_alignment=projection_alignment,
        probtp_table=probtp_table,
        axa_table=axa_table,
        category=category
    )

    # Fix table structure using redundancy in schema
    from utils.table_structure_fixer import fix_table_structure

    fixed_table, structure_fixes = fix_table_structure(comparison_table)

    if structure_fixes:
        print(f"    ℹ Applied {len(structure_fixes)} structure fixes to merged table")
        for fix in structure_fixes[:3]:  # Show first 3
            print(f"      - {fix}")
        if len(structure_fixes) > 3:
            print(f"      ... and {len(structure_fixes) - 3} more")

    # Validate structure
    is_valid, errors = validate_comparison_table_structure(fixed_table)

    if not is_valid:
        print(f"    ⚠ Validation warnings for {category}:")
        for error in errors[:5]:  # Show first 5 errors
            print(f"      - {error}")

    langfuse.update_current_trace(
        output={
            "row_count": len(fixed_table.get("rows", [])),
            "is_valid": is_valid
        },
        metadata={
            "validation_errors": errors if not is_valid else [],
            "structure_fixes": structure_fixes
        },
    )

    return fixed_table


# Reuse analysis and summary generation from two_phase_pipeline
@observe(name="phase_3_analysis")
async def generate_category_analysis(
    comparison_table: dict,
    other_categories: list[str] | None = None,
    language: str = "French (France)",
) -> dict:
    """Phase 3: Generate analysis from comparison table (reused from two_phase)."""
    category = comparison_table.get("metadata", {}).get("category", "Unknown")
    print(f"  [Phase 3] Generating analysis for: {category}")

    langfuse.update_current_trace(
        metadata={
            "category": category,
            "phase": "analysis",
        }
    )

    prompt = create_analysis_prompt(
        comparison_table=comparison_table,
        other_categories=other_categories,
        language=language,
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

        # Fix table structure using redundancy in schema
        from utils.table_structure_fixer import fix_table_structure

        annotated_table = analysis_data.get("annotated_table", {})
        fixed_table, structure_fixes = fix_table_structure(annotated_table)

        if structure_fixes:
            print(f"    ℹ Applied {len(structure_fixes)} structure fixes to annotated_table")
            for fix in structure_fixes[:3]:  # Show first 3
                print(f"      - {fix}")
            if len(structure_fixes) > 3:
                print(f"      ... and {len(structure_fixes) - 3} more")

        # Validate analysis (reuse from two_phase)
        from utils.analysis_validator import validate_and_fix_analysis_table

        corrected_table, validation_log = await validate_and_fix_analysis_table(
            alignment_table=comparison_table,
            analysis_table=fixed_table,
            category=category,
        )
        analysis_data["annotated_table"] = corrected_table

        langfuse.update_current_trace(
            output={"success": True},
            metadata={"validation": validation_log},
        )

        return analysis_data
    except json.JSONDecodeError as e:
        print(f"    ✗ Failed to parse analysis JSON: {e}")
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


@observe(name="phase_4_summary")
async def generate_general_summary(
    all_analyses: list[dict], language: str = "French (France)"
) -> dict:
    """Phase 4: Generate general summary (reused from two_phase)."""
    print("  [Phase 4] Generating general summary...")

    langfuse.update_current_trace(
        metadata={
            "phase": "summary",
            "category_count": len(all_analyses),
        }
    )

    category_analyses = []
    for analysis in all_analyses:
        category_analyses.append({
            "category": analysis.get("category", "Unknown"),
            "key_differences": analysis.get("key_differences", ""),
            "critical_thinking": analysis.get("critical_thinking", ""),
            "best_coverage": analysis.get("best_coverage", ""),
            "salesperson_talking_points": analysis.get("salesperson_talking_points", []),
            "objective_assessment": analysis.get("objective_assessment", {}),
        })

    prompt = create_summary_prompt(category_analyses=category_analyses, language=language)

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
        langfuse.update_current_trace(output={"success": True})
        return summary_data
    except json.JSONDecodeError as e:
        print(f"    ✗ Failed to parse summary JSON: {e}")
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


async def process_single_category(
    category: str,
    index: int,
    total: int,
    probtp_markdown: str,
    axa_markdown: str,
    probtp_levels: list[str] | None,
    axa_levels: list[str] | None,
    all_categories: list[str],
    probtp_taxonomy_tree: str | None,
    language: str,
) -> tuple[str, dict, dict, dict]:
    """
    Process a single category through all pipeline phases.

    Returns:
        Tuple of (category, probtp_table, axa_table, comparison_table, analysis_data)
    """
    print(f"\n[{index}/{total}] Processing: {category}")

    # Filter ProBTP levels for this category
    category_probtp_levels = filter_probtp_levels_for_category(category, probtp_levels)

    if category_probtp_levels and category_probtp_levels != probtp_levels:
        print(f"  → Filtered ProBTP levels for {category}: {category_probtp_levels}")

    other_categories = [c for c in all_categories if c != category]

    # Phase 1.1: Extract ProBTP and AXA category tables
    probtp_table, axa_table = await asyncio.gather(
        extract_category_table(
            vendor="ProBTP",
            markdown=probtp_markdown,
            category=category,
            policy_levels=category_probtp_levels,
            other_categories=other_categories,
            language=language,
        ),
        extract_category_table(
            vendor="AXA",
            markdown=axa_markdown,
            category=category,
            policy_levels=axa_levels,
            other_categories=other_categories,
            language=language,
        ),
    )

    # Extract taxonomies
    probtp_taxonomy = probtp_table.get("taxonomy", {}).get("ascii_tree", "")
    if probtp_taxonomy and not probtp_taxonomy_tree:
        probtp_taxonomy_tree = probtp_taxonomy

    # Phase 1.3: Classify ambiguous cases (parallel for both vendors)
    probtp_ambiguous = probtp_table.get("ambiguous_cases", [])
    axa_ambiguous = axa_table.get("ambiguous_cases", [])

    probtp_classification, axa_classification = await asyncio.gather(
        classify_ambiguous_cases(
            vendor="ProBTP",
            category=category,
            ambiguous_cases=probtp_ambiguous,
            probtp_taxonomy_tree=probtp_taxonomy_tree or "",
            language=language,
        ) if probtp_ambiguous else asyncio.sleep(0, result={"vendor": "ProBTP", "category": category, "classified_cases": []}),
        classify_ambiguous_cases(
            vendor="AXA",
            category=category,
            ambiguous_cases=axa_ambiguous,
            probtp_taxonomy_tree=probtp_taxonomy_tree or "",
            language=language,
        ) if axa_ambiguous else asyncio.sleep(0, result={"vendor": "AXA", "category": category, "classified_cases": []}),
    )

    # Phase 1.4: Update tables with classified cases (parallel)
    probtp_table, axa_table = await asyncio.gather(
        update_table_with_classified_cases(
            category_table=probtp_table,
            classified_cases=probtp_classification.get("classified_cases", []),
            category=category,
            source_markdown=probtp_markdown,
            vendor="ProBTP",
            language=language,
        ),
        update_table_with_classified_cases(
            category_table=axa_table,
            classified_cases=axa_classification.get("classified_cases", []),
            category=category,
            source_markdown=axa_markdown,
            vendor="AXA",
            language=language,
        ),
    )

    # Phase 2.1: Projection alignment
    projection_alignment = await perform_projection_alignment(
        probtp_table=probtp_table,
        axa_table=axa_table,
        category=category,
        language=language,
    )

    # Phase 2.2: Programmatic merge
    comparison_table = await perform_programmatic_merge(
        projection_alignment=projection_alignment,
        probtp_table=probtp_table,
        axa_table=axa_table,
        category=category,
    )

    # Phase 3: Analysis
    analysis_data = await generate_category_analysis(
        comparison_table=comparison_table,
        other_categories=other_categories,
        language=language,
    )

    return (category, probtp_table, axa_table, comparison_table, analysis_data)


@observe(name="project_then_merge_report_generation")
async def generate_project_then_merge_report(
    probtp_path: str | Path,
    axa_path: str | Path,
    output_path: str | Path,
    probtp_levels: list[str] | None = None,
    axa_levels: list[str] | None = None,
    categories: list[str] | None = None,
    language: str = "French (France)",
) -> dict:
    """
    Generate a complete comparison report using project-then-merge pipeline.

    Args:
        probtp_path: Path to ProBTP document JSON
        axa_path: Path to AXA document JSON
        output_path: Path to save the generated report
        probtp_levels: Optional ProBTP contract levels
        axa_levels: Optional AXA contract levels
        categories: Optional list of categories to compare
        language: Language for the report

    Returns:
        Dictionary with generation metadata
    """
    print("=" * 80)
    print("Project-Then-Merge Pipeline: Structured Report Generation")
    print("=" * 80)

    start_time = time.time()

    langfuse.update_current_trace(
        name="insurance_comparison_report_project_merge",
        user_id=os.getenv("USER", "unknown"),
        metadata={
            "probtp_document": str(probtp_path),
            "axa_document": str(axa_path),
            "probtp_levels": probtp_levels,
            "axa_levels": axa_levels,
            "language": language,
            "output_path": str(output_path),
        },
        tags=["insurance", "comparison", "report", "project-merge"],
    )

    # Load documents
    print("\n[Setup] Loading documents...")
    probtp_doc, axa_doc = load_document_pair(probtp_path, axa_path)
    print(f"  ✓ ProBTP: {probtp_doc.name}")
    print(f"  ✓ AXA: {axa_doc.name}")

    probtp_markdown = probtp_doc.get_markdown_with_expanded_tables()
    axa_markdown = axa_doc.get_markdown_with_expanded_tables()

    if categories is None:
        categories = DEFAULT_CATEGORIES

    print(f"\n[Setup] Processing {len(categories)} categories...")

    # Create tmp directory
    tmp_dir = Path(__file__).parent.parent / "output" / "project_merge" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ Intermediate outputs will be saved to: {tmp_dir}")

    all_probtp_tables = []
    all_axa_tables = []
    all_comparison_tables = []
    all_analyses = []
    probtp_taxonomy_tree = None

    # Process categories sequentially for now (can parallelize later)
    for i, category in enumerate(categories, 1):
        result = await process_single_category(
            category=category,
            index=i,
            total=len(categories),
            probtp_markdown=probtp_markdown,
            axa_markdown=axa_markdown,
            probtp_levels=probtp_levels,
            axa_levels=axa_levels,
            all_categories=categories,
            probtp_taxonomy_tree=probtp_taxonomy_tree,
            language=language,
        )

        cat, probtp_table, axa_table, comparison_table, analysis_data = result

        # Update global taxonomy tree if available
        if not probtp_taxonomy_tree:
            probtp_taxonomy_tree = probtp_table.get("taxonomy", {}).get("ascii_tree", "")

        all_probtp_tables.append(probtp_table)
        all_axa_tables.append(axa_table)
        all_comparison_tables.append(comparison_table)
        all_analyses.append(analysis_data)

        # Save intermediate outputs
        with open(tmp_dir / f"{cat}_probtp_table.json", 'w', encoding='utf-8') as f:
            json.dump(probtp_table, f, ensure_ascii=False, indent=2)
        with open(tmp_dir / f"{cat}_axa_table.json", 'w', encoding='utf-8') as f:
            json.dump(axa_table, f, ensure_ascii=False, indent=2)
        with open(tmp_dir / f"{cat}_comparison_table.json", 'w', encoding='utf-8') as f:
            json.dump(comparison_table, f, ensure_ascii=False, indent=2)
        with open(tmp_dir / f"{cat}_analysis.json", 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2)

    # Phase 4: Generate general summary
    print("\n[Phase 4] Generating general summary...")
    general_summary = await generate_general_summary(all_analyses, language)

    with open(tmp_dir / "general_summary.json", 'w', encoding='utf-8') as f:
        json.dump(general_summary, f, ensure_ascii=False, indent=2)

    # Phase 5: Assemble final report (reuse from two_phase)
    print("\n[Assembly] Assembling final report...")

    # Import from two_phase pipeline
    from pipelines.two_phase_pipeline import generate_overall_recommendation

    overall_recommendation = await generate_overall_recommendation(all_analyses, language)

    # Convert to markdown
    report_sections = []
    report_sections.append(summary_to_markdown(general_summary))
    report_sections.append("\n---\n")

    for analysis in all_analyses:
        report_sections.append(analysis_to_markdown(analysis))
        report_sections.append("\n---\n")

    report_sections.append("## Recommandations Globales\n")
    report_sections.append(overall_recommendation)
    report_sections.append("\n")

    # Metadata
    metadata = create_report_metadata(
        probtp_doc_name=probtp_doc.name,
        axa_doc_name=axa_doc.name,
        model="gemini-2.5-flash",
        probtp_levels=probtp_levels,
        axa_levels=axa_levels,
        categories=categories,
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
        "probtp_tables": all_probtp_tables,
        "axa_tables": all_axa_tables,
        "comparison_tables": all_comparison_tables,
        "analyses": all_analyses,
        "general_summary": general_summary,
        "overall_recommendation": overall_recommendation,
    }

    # Save version without bounding boxes
    json_output_path_before = Path(output_path).with_suffix(".before_bbox.json")
    with open(json_output_path_before, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ JSON data (before bbox) saved to {json_output_path_before}")

    # Enrich with bounding boxes from source documents
    print("  → Adding bounding boxes from source documents...")
    from utils.bounding_box_enricher import enrich_comparison_table_with_bounding_boxes

    # Enrich comparison_tables array
    enriched_comparison_tables = []
    for table in all_comparison_tables:
        enriched_table = enrich_comparison_table_with_bounding_boxes(
            table,
            probtp_path,
            axa_path
        )
        enriched_comparison_tables.append(enriched_table)

    # Enrich analyses (annotated_table inside each analysis)
    enriched_analyses = []
    for analysis in all_analyses:
        annotated_table = analysis.get("annotated_table")
        if annotated_table:
            enriched_table = enrich_comparison_table_with_bounding_boxes(
                annotated_table,
                probtp_path,
                axa_path
            )
            enriched_analysis = {**analysis, "annotated_table": enriched_table}
            enriched_analyses.append(enriched_analysis)
        else:
            enriched_analyses.append(analysis)

    # Update json_data with enriched tables and analyses
    json_data["comparison_tables"] = enriched_comparison_tables
    json_data["analyses"] = enriched_analyses

    # Save enriched version
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ JSON data (with bounding boxes) saved to {json_output_path}")

    print("\n" + "=" * 80)
    print("Pipeline Complete!")
    print("=" * 80)
    print(f"Generation time: {generation_time:.2f}s")
    print(f"Categories processed: {len(categories)}")
    print(f"Report length: {len(full_report)} characters")

    result = {
        "generation_time_seconds": generation_time,
        "model": "gemini-2.5-flash (project-merge)",
        "categories_processed": len(categories),
        "report_length_chars": len(full_report),
        "probtp_document": probtp_doc.name,
        "axa_document": axa_doc.name,
        "output_path": str(output_path),
        "json_output_path": str(json_output_path),
    }

    langfuse.update_current_trace(
        output=result,
        metadata={"pipeline_complete": True},
    )

    return result


def main():
    """Main function for testing the project-then-merge pipeline."""
    base_dir = Path(__file__).parent.parent.parent
    output_base = base_dir / "output" / "landing_ai_xtd"

    probtp_path = output_base / "File #3 - Panorama FMC 2025.json"
    axa_path = output_base / "File #1 - Laurent M - Conditions particulières - Socle AXA - SAE.json"

    output_dir = Path(__file__).parent.parent / "output" / "project_merge"
    output_dir.mkdir(parents=True, exist_ok=True)

    probtp_levels = ["S2", "P4"]
    axa_levels = ["Base Obligatoire"]
    probtp_level_str = "_".join(probtp_levels).replace("+", "plus")
    axa_level_str = "_".join(axa_levels).replace(" ", "_")
    output_path = (
        output_dir
        / f"comparison_report_ProBTP_{probtp_level_str}_vs_AXA_{axa_level_str}.md"
    )

    if not probtp_path.exists():
        print(f"Error: ProBTP document not found: {probtp_path}")
        return

    if not axa_path.exists():
        print(f"Error: AXA document not found: {axa_path}")
        return

    print("\nStarting project-then-merge report generation...")
    print(f"ProBTP document: {probtp_path.name}")
    print(f"AXA document: {axa_path.name}")
    print(f"Output: {output_path}")
    print()

    result = asyncio.run(
        generate_project_then_merge_report(
            probtp_path=probtp_path,
            axa_path=axa_path,
            output_path=output_path,
            probtp_levels=probtp_levels,
            axa_levels=axa_levels,
        )
    )

    print("\n" + "=" * 80)
    print("GENERATION SUMMARY")
    print("=" * 80)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
