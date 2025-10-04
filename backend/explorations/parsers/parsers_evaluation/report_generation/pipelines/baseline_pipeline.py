"""
Baseline single-shot pipeline for insurance policy comparison report generation.

This pipeline uses a single LLM call to generate a complete comparison report
between ProBTP and AXA insurance contracts.
"""
import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from prompts.baseline_prompt import create_baseline_prompt
from utils.document_loader import ParsedDocument, load_document_pair
from utils.gemini_client import generate_with_reasoning
from utils.report_formatter import create_report_metadata, save_report



# Default categories to analyze
DEFAULT_CATEGORIES = [
    "Soins Courants",
    "Hospitalisation",
    "Optique",
    "Soins Dentaires",
    "Audiologie",
    "Médecines Douces"
]

async def generate_baseline_report(
    probtp_path: str | Path,
    axa_path: str | Path,
    output_path: str | Path,
    probtp_levels: list[str] | None = None,
    axa_levels: list[str] | None = None,
    categories: list[str] | None = None,
    language: str = "French (France)",
    model: str = "gemini-2.5-pro",
    thinking_budget: int = 8192,
    temperature: float = 0.1
) -> dict:
    """
    Generate a complete comparison report using single-shot LLM generation.

    Args:
        probtp_path: Path to ProBTP document JSON
        axa_path: Path to AXA document JSON
        output_path: Path to save the generated report
        probtp_levels: Optional ProBTP contract levels
        axa_levels: Optional AXA contract levels
        categories: Optional list of categories to compare
        language: Language for the report (default: "French (France)")
        model: Gemini model to use (default: gemini-2.5-pro)
        thinking_budget: Reasoning budget (default: 8192)
        temperature: Generation temperature (default: 0.1)

    Returns:
        Dictionary with generation metadata (time, model, etc.)
    """
    print("=" * 80)
    print("Baseline Pipeline: Single-Shot Report Generation")
    print("=" * 80)

    # No categories specified, use default
    if categories is None:
        categories = DEFAULT_CATEGORIES
        print(f"  ✓ Using default categories: {categories}")

    # Load documents
    print("\n[1/3] Loading documents...")
    probtp_doc, axa_doc = load_document_pair(probtp_path, axa_path)
    print(f"  ✓ ProBTP: {probtp_doc.name}")
    print(f"  ✓ AXA: {axa_doc.name}")

    # Extract markdown content
    probtp_markdown = probtp_doc.get_full_markdown()
    axa_markdown = axa_doc.get_full_markdown()

    print(f"\n  ProBTP content: {len(probtp_markdown)} characters")
    print(f"  AXA content: {len(axa_markdown)} characters")

    # Create prompt
    print("\n[2/3] Creating prompt...")
    prompt = create_baseline_prompt(
        probtp_markdown=probtp_markdown,
        axa_markdown=axa_markdown,
        probtp_levels=probtp_levels,
        axa_levels=axa_levels,
        categories=categories,
        language=language
    )

    prompt_length = len(prompt)
    print(f"  ✓ Prompt length: {prompt_length} characters (~{prompt_length // 4} tokens)")

    # Generate report
    print(f"\n[3/3] Generating report with {model}...")
    print(f"  - Thinking budget: {thinking_budget}")
    print(f"  - Temperature: {temperature}")

    start_time = time.time()

    report_content = await generate_with_reasoning(
        prompt=prompt,
        model=model,
        thinking_budget=thinking_budget,
        temperature=temperature,
        max_output_tokens=16000,  # Increased for comprehensive report
    )

    generation_time = time.time() - start_time

    print(f"  ✓ Report generated in {generation_time:.2f}s")
    print(f"  ✓ Report length: {len(report_content)} characters")

    # Save report
    print(f"\n[4/4] Saving report to {output_path}...")

    # Add metadata for levels and categories
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
        model=model,
        generation_time_seconds=generation_time,
        **metadata_extra
    )

    save_report(report_content, output_path, metadata=metadata)
    print(f"  ✓ Report saved successfully")

    print("\n" + "=" * 80)
    print("Pipeline Complete!")
    print("=" * 80)

    return {
        "generation_time_seconds": generation_time,
        "model": model,
        "prompt_length_chars": prompt_length,
        "report_length_chars": len(report_content),
        "probtp_document": probtp_doc.name,
        "axa_document": axa_doc.name,
        "output_path": str(output_path),
    }


def main():
    """
    Main function for testing the baseline pipeline.

    Uses default ProBTP and AXA documents from the landing_ai_xtd output.
    """
    # Define paths
    base_dir = Path(__file__).parent.parent.parent
    output_base = base_dir / "output" / "landing_ai_xtd"

    # Use available documents (adjust as needed)
    probtp_path = output_base / "File #2 - Laurent M - tableau garantie fm 2025 word.json"
    axa_path = output_base / "File #1 - Laurent M - Conditions particulières - Socle AXA - SAE.json"

    # Output path with levels in filename
    output_dir = Path(__file__).parent.parent / "output" / "baseline"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build filename with levels
    probtp_levels = ["S2", "P3+"]
    axa_levels = ["Base Obligatoire"]
    probtp_level_str = "_".join(probtp_levels).replace("+", "plus")
    axa_level_str = "_".join(axa_levels).replace(" ", "_")
    output_path = output_dir / f"comparison_report_ProBTP_{probtp_level_str}_vs_AXA_{axa_level_str}.md"

    # Check if documents exist
    if not probtp_path.exists():
        print(f"Error: ProBTP document not found: {probtp_path}")
        print("\nAvailable documents:")
        for doc in output_base.glob("*.json"):
            print(f"  - {doc.name}")
        return

    if not axa_path.exists():
        print(f"Error: AXA document not found: {axa_path}")
        print("\nAvailable documents:")
        for doc in output_base.glob("*.json"):
            print(f"  - {doc.name}")
        return

    # Run pipeline
    print("\nStarting baseline report generation...")
    print(f"ProBTP document: {probtp_path.name}")
    print(f"AXA document: {axa_path.name}")
    print(f"Output: {output_path}")
    print()

    # Generate report
    result = asyncio.run(generate_baseline_report(
        probtp_path=probtp_path,
        axa_path=axa_path,
        output_path=output_path,
        # Optional: specify levels and categories
        probtp_levels=probtp_levels,
        axa_levels=axa_levels,
    ))

    # Print summary
    print("\n" + "=" * 80)
    print("GENERATION SUMMARY")
    print("=" * 80)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
