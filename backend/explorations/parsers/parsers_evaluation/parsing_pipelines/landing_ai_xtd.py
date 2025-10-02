"""
Enhanced Landing AI parsing pipeline with PyMuPDF correction and LLM validation.

Implements 4-phase pipeline:
1. Parse with both Landing AI and PyMuPDF
2. Match tables using TF-IDF
3. Correct with LLM using PyMuPDF reference
4. Sanity check and visual correction
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from landing_ai_pipeline_utils.debug_utils import (
    save_debug_artifacts,
    save_html_versions,
)
from landing_ai_pipeline_utils.phase1_parsers import (
    get_landing_tables,
    get_pymupdf_tables,
)
from landing_ai_pipeline_utils.phase2_matching import match_tables_on_page
from landing_ai_pipeline_utils.phase3_correction import correct_table_with_llm
from landing_ai_pipeline_utils.phase4_sanity_check import (
    SanityCheck,
    apply_header_correction,
    apply_visual_correction,
    generate_table_screenshot,
    run_sanity_checks,
)
from langfuse import Langfuse
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

load_dotenv()


# Langfuse setup
langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)


# Async Gemini client manager
class AsyncGeminiClientManager:
    """Async context manager for Gemini client lifecycle."""

    def __init__(self):
        self.client = None

    async def __aenter__(self):
        GoogleGenAIInstrumentor().instrument()
        self.client = genai.Client(
            vertexai=True,
            project="probtp-poc-prod",
            location="global",
        )
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client and hasattr(self.client, "close"):
            try:
                if asyncio.iscoroutinefunction(self.client.close):
                    await self.client.close()
                else:
                    self.client.close()
            except Exception as e:
                print(f"Error closing client: {e}")
        self.client = None


# Define mandatory sanity checks (always run)
MANDATORY_SANITY_CHECKS = [
    SanityCheck(
        check_id="no_header",
        description=(
            "The table should have a descriptive header row with meaningful column names. "
            "Check if the first row serves as a proper header by verifying: \n"
            "(1) Headers should be descriptive text (e.g., 'Category', 'Level', 'Amount' or codes), not numerical values; \n"
            "(2) Headers should be unique - repeated cell content in first row indicates missing headers; \n"
            "(3) Partially empty header cells are acceptable; \n"
            "(4) The first row content should clearly differ from data rows below it. \n"
            "(5) Overall the table should be interpretable as is, not being able to interpret data cells is a sign of missing headers.\n"
            "If any of the above conditions are not met, the table is missing a proper header row."
        ),
        applies_to="all",
    ),
]

# Define additional optional sanity checks
OPTIONAL_SANITY_CHECKS = [
    SanityCheck(
        check_id="too_empty_row",
        description=(
            "A row should not contain an excessive number of consecutive empty cells that deviates from the table's expected pattern. "
            "Specifically: "
            "(1) Identify if there's a continuous sequence of 3+ empty cells in a row where other rows have data; "
            "(2) This pattern should deviate from the rest of the table structure; "
            "(3) Occasional empty cells are acceptable, but a long empty sequence suggests parsing errors, merged cells, "
            "or structural issues. "
            "Consider the table's overall pattern - if most rows have similar empty patterns, it may be intentional structure."
        ),
        applies_to="all",
    ),
    # SanityCheck(
    #     check_id="monotonic_progression",
    #     description=(
    #         "For tables with contract or coverage levels (e.g., 'Basic', 'Standard', 'Premium' or 'Level 1', 'Level 2', 'Level 3'), "
    #         "verify that benefit values show logical progression across adjacent levels. "
    #         "Specifically: "
    #         "(1) Numerical values (amounts, percentages, coverage limits) should generally increase as contract levels increase; "
    #         "(2) Check cells in the same row across level columns - values should follow expected progression (e.g., 100€, 150€, 200€); "
    #         "(3) Exceptions are acceptable for: fixed values that don't vary by level, 'included' vs. numeric amounts, or inverse relationships "
    #         "that make business sense (e.g., deductibles decreasing); "
    #         "(4) Flag cases where higher levels have significantly lower values without clear reason, as this may indicate parsing errors or data misalignment."
    #     ),
    #     applies_to="all"
    # ),
]

# Combine all sanity checks
SANITY_CHECKS = MANDATORY_SANITY_CHECKS + OPTIONAL_SANITY_CHECKS


# Main pipeline
async def process_document(file_path: str, client: genai.Client) -> dict:
    """
    Process a document through the 4-phase pipeline.

    Returns:
        Dict with corrected tables and statistics
    """
    print(f"\n{'=' * 80}")
    print(f"Processing: {Path(file_path).name}")
    print(f"{'=' * 80}")

    # Phase 1: Parse and Get Tables
    print("\n[Phase 1] Parsing document with both parsers...")
    landing_tables_by_page = get_landing_tables(file_path)
    pymupdf_tables_by_page = get_pymupdf_tables(file_path)

    total_landing_tables = sum(
        len(tables) for tables in landing_tables_by_page.values()
    )
    total_pymupdf_tables = sum(
        len(tables) for tables in pymupdf_tables_by_page.values()
    )
    print(
        f"  Landing AI: {total_landing_tables} tables across {len(landing_tables_by_page)} pages"
    )
    print(
        f"  PyMuPDF: {total_pymupdf_tables} tables across {len(pymupdf_tables_by_page)} pages"
    )

    # Phase 2: Match Tables
    print("\n[Phase 2] Matching tables...")
    matches_by_page = {}
    total_matches = 0

    for page_num in landing_tables_by_page:
        landing_tables = landing_tables_by_page[page_num]
        pymupdf_tables = pymupdf_tables_by_page.get(page_num, [])

        matches = match_tables_on_page(landing_tables, pymupdf_tables)
        matches_by_page[page_num] = matches

        page_matches = sum(1 for m in matches.values() if m)
        total_matches += page_matches
        print(f"  Page {page_num}: {page_matches}/{len(landing_tables)} tables matched")

    # Phase 3: LLM Correction
    print("\n[Phase 3] Applying LLM corrections...")
    corrected_tables_by_page = {}
    total_corrections = 0

    for page_num in landing_tables_by_page:
        landing_tables = landing_tables_by_page[page_num]
        pymupdf_tables = pymupdf_tables_by_page.get(page_num, [])
        matches = matches_by_page.get(page_num, {})

        corrected_tables = []

        for table in landing_tables:
            # Use position_in_page to get matches (matches are keyed by position index)
            position_idx = table["position_in_page"]
            matched_indices = matches.get(position_idx, [])
            matched_pymupdf = [
                pymupdf_tables[i] for i in matched_indices if i < len(pymupdf_tables)
            ]

            corrected_table = await correct_table_with_llm(
                client, table, matched_pymupdf, pdf_path=file_path, page_num=page_num
            )
            corrected_tables.append(corrected_table)

            corrections_count = corrected_table.get("corrections_applied", 0)
            total_corrections += corrections_count

        corrected_tables_by_page[page_num] = corrected_tables
        # Tables already in order by position_in_page from phase1

    print(f"  Applied {total_corrections} corrections total")

    # Phase 4: Sanity Check and Visual Correction
    print("\n[Phase 4] Running sanity checks...")
    final_tables_by_page = {}
    total_violations = 0
    total_visual_corrections = 0

    # First pass: run mandatory header check on all tables and store in table dict
    print("  Running mandatory header checks...")
    for page_num in corrected_tables_by_page:
        for table in corrected_tables_by_page[page_num]:
            # Use chunk_id for identification
            table_id = table.get("chunk_id", "unknown")
            header_result = await run_sanity_checks(
                client, table, MANDATORY_SANITY_CHECKS
            )

            # Store violations directly in table dict
            table["sanity_violations"] = list(header_result.violations)
            table["has_valid_headers"] = len(header_result.violations) == 0

            if table["has_valid_headers"]:
                print(f"    ✓ Page {page_num}, Table {table_id[:8]}: Valid headers")
            else:
                print(
                    f"    ✗ Page {page_num}, Table {table_id[:8]}: Missing/invalid headers"
                )

    # Second pass: process violations and apply corrections
    print("\n  Processing violations and applying corrections...")
    for page_num in corrected_tables_by_page:
        final_tables = []

        for table in corrected_tables_by_page[page_num]:
            # Get violations from table dict (stored in first pass)
            violations = table.get("sanity_violations", [])
            has_valid_headers = table.get("has_valid_headers", True)

            # Extract table ID for debug (use both chunk_id and HTML table id)
            import re

            chunk_id = table.get("chunk_id", "unknown")
            table_id_match = re.search(
                r'<table id="([^"]+)"', table.get("html_content", "")
            )
            html_table_id = table_id_match.group(1) if table_id_match else "unknown"
            pdf_name = Path(file_path).stem

            # Get matched PyMuPDF tables for debug artifacts
            position_idx = table["position_in_page"]
            matched_indices = matches_by_page.get(page_num, {}).get(position_idx, [])
            matched_pymupdf = [
                pymupdf_tables_by_page.get(page_num, [])[i]
                for i in matched_indices
                if i < len(pymupdf_tables_by_page.get(page_num, []))
            ]

            # Save debug artifacts after phase 3 (regardless of violations)
            save_debug_artifacts(
                table,
                matched_pymupdf,
                table.get("corrections_applied", 0),
                violations,
                html_table_id,
                page_num,
                pdf_name,
                "phase3_completed",
            )

            # Start with current table for corrections
            corrected_table = table

            if violations:
                total_violations += len(violations)
                print(
                    f"    Page {page_num}, Table {chunk_id[:8]}: {len(violations)} violations found"
                )

                # Step 1: Handle header violations (no image needed)
                if not has_valid_headers:
                    print("      → Applying header correction...")

                    # Find previous table with valid headers
                    previous_table = None

                    # Look through all tables before current one (same page)
                    current_position = table["position_in_page"]
                    for prev_table_candidate in corrected_tables_by_page[page_num]:
                        if prev_table_candidate["position_in_page"] >= current_position:
                            break
                        if prev_table_candidate.get("has_valid_headers", False):
                            previous_table = prev_table_candidate

                    # If not found on same page, look at previous pages
                    if not previous_table:
                        for prev_page in range(page_num - 1, -1, -1):
                            if prev_page not in corrected_tables_by_page:
                                continue
                            for prev_table_candidate in reversed(
                                corrected_tables_by_page[prev_page]
                            ):
                                if prev_table_candidate.get("has_valid_headers", False):
                                    previous_table = prev_table_candidate
                                    break
                            if previous_table:
                                break

                    if previous_table:
                        ref_table_id_match = re.search(
                            r'<table id="([^"]+)"',
                            previous_table.get("html_content", ""),
                        )
                        ref_table_id = (
                            ref_table_id_match.group(1)
                            if ref_table_id_match
                            else "unknown"
                        )
                        print(f"        Using reference table {ref_table_id}")

                        try:
                            corrected_table = await apply_header_correction(
                                client, corrected_table, previous_table=previous_table
                            )
                            if corrected_table.get("header_row_added", False):
                                print("        ✓ Header row added")
                        except Exception as e:
                            print(f"        Error in header correction: {e}")
                    else:
                        print("        No reference table with valid headers found")

                # Step 2: Handle other violations (image needed)
                non_header_violations = [
                    v for v in violations if v.check_id != "no_header"
                ]
                if non_header_violations:
                    print(
                        f"      → Applying visual corrections for {len(non_header_violations)} issues..."
                    )

                    try:
                        screenshot_bytes = generate_table_screenshot(
                            file_path,
                            page_num,
                            corrected_table["grounding"],
                            save_to_tmp=True,
                            table_id=f"{html_table_id}_phase4",
                        )

                        corrected_table = await apply_visual_correction(
                            client, corrected_table, screenshot_bytes
                        )

                        visual_corrections = corrected_table.get(
                            "visual_corrections_applied", 0
                        )
                        total_visual_corrections += visual_corrections

                        if visual_corrections > 0:
                            print(
                                f"        ✓ Applied {visual_corrections} cell corrections"
                            )

                    except Exception as e:
                        print(f"        Error in visual correction: {e}")

                # Save debug artifacts after phase 4
                save_debug_artifacts(
                    corrected_table,
                    matched_pymupdf,
                    table.get("corrections_applied", 0),
                    violations,
                    html_table_id,
                    page_num,
                    pdf_name,
                    "phase4_completed",
                )
            else:
                # Save HTML versions even if no violations
                save_html_versions(corrected_table, html_table_id, page_num, pdf_name)

            final_tables.append(corrected_table)

        final_tables_by_page[page_num] = final_tables

    print(f"  Found {total_violations} violations")
    print(f"  Applied {total_visual_corrections} visual corrections")

    # Build result
    result = {
        "file_path": file_path,
        "tables_by_page": final_tables_by_page,
        "statistics": {
            "total_landing_tables": total_landing_tables,
            "total_pymupdf_tables": total_pymupdf_tables,
            "total_matches": total_matches,
            "total_corrections": total_corrections,
            "total_violations": total_violations,
            "total_visual_corrections": total_visual_corrections,
        },
    }

    return result


# Generate markdown output
def generate_markdown_output(result: dict) -> str:
    """Generate markdown output from processed tables."""
    lines = [f"# {Path(result['file_path']).name}\n"]

    for page_num in sorted(result["tables_by_page"].keys()):
        lines.append(f"\n## Page {page_num + 1}\n")

        for table_idx, table in enumerate(result["tables_by_page"][page_num]):
            lines.append(f"\n### Table {table_idx + 1}\n")
            lines.append(table["html_content"])
            lines.append("\n")

    return "\n".join(lines)


# Main execution
async def main():
    """Main execution function."""
    # Test on same file as landing_ai_enhanced_old.py
    document_name = "File #2 - Laurent M - tableau garantie fm 2025 word.pdf"
    base_dir = Path(__file__).parent.parent
    file_path = base_dir / "documents" / document_name

    print("Landing AI Enhanced Pipeline")
    print("=" * 80)

    async with AsyncGeminiClientManager() as client:
        result = await process_document(str(file_path), client)

        # Print statistics
        print(f"\n{'=' * 80}")
        print("PIPELINE STATISTICS")
        print(f"{'=' * 80}")
        for key, value in result["statistics"].items():
            print(f"{key}: {value}")

        # Generate and save markdown output
        output_dir = base_dir / "output" / "landing_ai_xtd"
        output_dir.mkdir(parents=True, exist_ok=True)

        markdown_output = generate_markdown_output(result)
        output_file = output_dir / f"{Path(file_path).stem}.md"
        output_file.write_text(markdown_output, encoding="utf-8")
        print(f"\nOutput saved to: {output_file}")

        # Save full result as JSON
        json_file = output_dir / f"{Path(file_path).stem}.json"
        # Remove non-serializable objects
        serializable_result = {
            "file_path": result["file_path"],
            "statistics": result["statistics"],
        }
        json_file.write_text(
            json.dumps(serializable_result, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    asyncio.run(main())
