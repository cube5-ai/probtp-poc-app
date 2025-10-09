"""
Enhanced Landing AI parsing pipeline with PyMuPDF correction and LLM validation.

Implements 5-phase pipeline:
1. Parse with both Landing AI and PyMuPDF
2. Match tables using TF-IDF
3. Correct with LLM using PyMuPDF reference
4. Sanity check and visual correction
5. Map corrected tables back to Landing AI response structure
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from langfuse import Langfuse
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

# Handle both relative imports (when used as module) and direct imports (when run standalone)
try:
    from .landing_ai_pipeline_utils.debug_utils import (
        save_debug_artifacts,
        save_html_versions,
    )
    from .landing_ai_pipeline_utils.phase1_parsers import (
        get_landing_tables,
        get_landing_tables_with_response,
        get_pymupdf_tables,
    )
    from .landing_ai_pipeline_utils.phase2_matching import match_tables_on_page
    from .landing_ai_pipeline_utils.phase3_correction import correct_table_with_llm
    from .landing_ai_pipeline_utils.phase4_sanity_check import (
        SanityCheck,
        apply_header_correction,
        apply_visual_correction,
        generate_table_screenshot,
        run_sanity_checks,
        validate_table_headers,
    )
    from .landing_ai_pipeline_utils.phase5_output_mapping import map_to_landing_ai_response
except ImportError:
    from landing_ai_pipeline_utils.debug_utils import (
        save_debug_artifacts,
        save_html_versions,
    )
    from landing_ai_pipeline_utils.phase1_parsers import (
        get_landing_tables,
        get_landing_tables_with_response,
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
        validate_table_headers,
    )
    from landing_ai_pipeline_utils.phase5_output_mapping import map_to_landing_ai_response

load_dotenv()


# Langfuse setup
langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)


# Global client instance (reused across calls)
_client_instance = None


def _get_client() -> genai.Client:
    """Get or create Gemini client instance."""
    global _client_instance
    if _client_instance is None:
        GoogleGenAIInstrumentor().instrument()
        _client_instance = genai.Client(
            vertexai=True,
            project="probtp-poc-prod",
            location="global",
        )
    return _client_instance


# Define optional sanity checks (run for data quality issues)
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


async def _process_document_with_client(file_path: str, client: genai.Client) -> dict:
    """
    Process a document through the 5-phase pipeline with given client.

    Returns:
        Dict with corrected tables, statistics, and landing_ai_response
    """
    print(f"\n{'=' * 80}")
    print(f"Processing: {Path(file_path).name}")
    print(f"{'=' * 80}")

    # Phase 1: Parse and Get Tables
    print("\n[Phase 1] Parsing document with both parsers...")
    landing_tables_by_page, original_landing_response = get_landing_tables_with_response(file_path)
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

    # First pass: validate headers on all tables using dedicated function
    print("  Running header validation...")
    for page_num in corrected_tables_by_page:
        for table in corrected_tables_by_page[page_num]:
            # Use chunk_id for identification
            table_id = table.get("chunk_id", "unknown")

            # Use dedicated header validation function
            header_validation = await validate_table_headers(client, table)

            # Store validation results in table dict
            table["has_valid_headers"] = header_validation.has_valid_headers
            table["header_validation_confidence"] = header_validation.confidence
            table["header_validation_reason"] = header_validation.reason

            # Initialize sanity_violations list (will be populated with non-header issues later)
            table["sanity_violations"] = []

            # Add a violation for missing headers if needed (for backward compatibility)
            if not header_validation.has_valid_headers:
                try:
                    from .landing_ai_pipeline_utils.phase4_sanity_check import SanityViolation
                except ImportError:
                    from landing_ai_pipeline_utils.phase4_sanity_check import SanityViolation

                table["sanity_violations"].append(
                    SanityViolation(
                        check_id="no_header",
                        description=header_validation.reason,
                        affected_cells=[]
                    )
                )

            if table["has_valid_headers"]:
                print(f"    ✓ Page {page_num}, Table {table_id[:8]}: Valid headers ({header_validation.confidence} confidence)")
            else:
                print(f"    ✗ Page {page_num}, Table {table_id[:8]}: Missing/invalid headers ({header_validation.confidence} confidence)")

    # Second pass: run optional data quality checks and process violations
    print("\n  Running optional data quality checks...")
    if OPTIONAL_SANITY_CHECKS:
        for page_num in corrected_tables_by_page:
            for table in corrected_tables_by_page[page_num]:
                table_id = table.get("chunk_id", "unknown")

                # Run optional sanity checks for data quality issues
                optional_result = await run_sanity_checks(
                    client, table, OPTIONAL_SANITY_CHECKS
                )

                # Append to existing violations (header violations from first pass)
                existing_violations = table.get("sanity_violations", [])
                table["sanity_violations"] = existing_violations + list(optional_result.violations)

                if optional_result.violations:
                    print(f"    Page {page_num}, Table {table_id[:8]}: {len(optional_result.violations)} data quality issues found")

    # Third pass: process all violations and apply corrections
    print("\n  Processing violations and applying corrections...")
    for page_num in corrected_tables_by_page:
        final_tables = []

        for table in corrected_tables_by_page[page_num]:
            # Get all violations from table dict (header + optional checks)
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

    # Phase 5: Map Corrected Tables Back to Landing AI Response
    print("\n[Phase 5] Mapping corrected tables back to Landing AI response...")
    final_landing_response = map_to_landing_ai_response(
        original_landing_response=original_landing_response,
        corrected_tables_by_page=final_tables_by_page,
        phase3_tables_by_page=corrected_tables_by_page,
        matches_by_page=matches_by_page,
        pymupdf_tables_by_page=pymupdf_tables_by_page,
    )

    # Count tables with metadata
    tables_with_metadata = sum(
        1 for chunk in final_landing_response.get("chunks", [])
        if "post_processing_metadata" in chunk
    )
    print(f"  Updated {tables_with_metadata} table chunks with post_processing_metadata")

    # Build result
    result = {
        "file_path": file_path,
        "tables_by_page": final_tables_by_page,
        "landing_ai_response": final_landing_response,  # Add final response
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


# ============================================================================
# Public API (called by parse_documents.py)
# ============================================================================

def parse_document(file_path: str) -> dict[str, Any]:
    """
    Parse a document using the enhanced Landing AI + PyMuPDF pipeline.

    This is the main entry point called by parse_documents.py.
    Runs the full 5-phase pipeline synchronously (from a thread pool).

    Args:
        file_path: Absolute path to the PDF file

    Returns:
        Dict containing the Landing AI response with corrected tables and metadata
    """
    # This function is called from ThreadPoolExecutor in parse_documents.py
    # We're in a worker thread, not the main event loop thread

    async def _run():
        # Create client inside event loop to ensure proper binding
        GoogleGenAIInstrumentor().instrument()
        client = genai.Client(
            vertexai=True,
            project="probtp-poc-prod",
            location="global",
        )
        return await _process_document_with_client(file_path, client)

    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run())
        return result["landing_ai_response"]
    finally:
        loop.close()


def write_to_markdown(response: dict[str, Any], file_path: str) -> None:
    """
    Convert the enhanced Landing AI response to markdown.

    This is called by parse_documents.py to generate the markdown output.

    Args:
        response: The Landing AI response dict (from parse_document)
        file_path: Output markdown file path
    """
    with open(file_path, "w", encoding="utf-8") as f:
        # Write all chunks in order (text, tables, etc.)
        for chunk in response.get("chunks", []):
            f.write(chunk.get("markdown", ""))
            f.write("\n")




# ============================================================================
# Test/Debug main (for standalone execution)
# ============================================================================

def main():
    """Test function for standalone execution."""
    # Test on sample file
    document_name = "File #2 - Laurent M - tableau garantie fm 2025 word.pdf"

    base_dir = Path(__file__).parent.parent
    file_path = base_dir / "documents" / document_name

    print("Landing AI Enhanced Pipeline (Test Mode)")
    print("=" * 80)

    # Use the public API (synchronous)
    response = parse_document(str(file_path))

    # Save outputs
    output_dir = base_dir / "output" / "landing_ai_xtd"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON
    json_file = output_dir / f"{Path(file_path).stem}.json"
    json_file.write_text(json.dumps(response, indent=2), encoding="utf-8")
    print(f"\nJSON saved to: {json_file}")

    # Save markdown
    md_file = output_dir / f"{Path(file_path).stem}.md"
    write_to_markdown(response, str(md_file))
    print(f"Markdown saved to: {md_file}")


if __name__ == "__main__":
    main()
