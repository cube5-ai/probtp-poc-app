"""
Test script for sanity checks functionality using REAL data from debug JSON files.
Tests the LLM-based sanity check validation on actual tables from the pipeline.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from google import genai
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

from phase4_sanity_check import SanityCheck, run_sanity_checks
from landing_ai_pipeline_utils.html_formatter import format_html_for_llm

load_dotenv()


# Define actual sanity checks from landing_ai_xtd.py
MANDATORY_CHECKS = [
    SanityCheck(
        check_id="no_header",
        description=(
            "The table should have a descriptive header row with meaningful column names. "
            "Check if the first row serves as a proper header by verifying: "
            "(1) Headers should be descriptive text (e.g., 'Category', 'Level', 'Amount' or codes), not numerical values; "
            "(2) Headers should be unique - repeated header names indicate missing or misaligned headers; "
            "(3) Partially empty header cells are acceptable; "
            "(4) The first row content should clearly differ from data rows below it. "
            "Strong indicators of a missing header: numerical values in the first row, inability to interpret data cells "
            "because the meaning of columns is unclear, or the first row appearing to be data rather than labels."
        ),
        applies_to="all"
    ),
]

OPTIONAL_CHECKS = [
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
        applies_to="all"
    ),
    SanityCheck(
        check_id="monotonic_progression",
        description=(
            "For tables with contract or coverage levels (e.g., 'Basic', 'Standard', 'Premium' or 'Level 1', 'Level 2', 'Level 3'), "
            "verify that benefit values show logical progression across adjacent levels. "
            "Specifically: "
            "(1) Numerical values (amounts, percentages, coverage limits) should generally increase as contract levels increase; "
            "(2) Check cells in the same row across level columns - values should follow expected progression (e.g., 100€, 150€, 200€); "
            "(3) Exceptions are acceptable for: fixed values that don't vary by level, 'included' vs. numeric amounts, or inverse relationships "
            "that make business sense (e.g., deductibles decreasing); "
            "(4) Flag cases where higher levels have significantly lower values without clear reason, as this may indicate parsing errors or data misalignment."
        ),
        applies_to="all"
    ),
]

ALL_CHECKS = MANDATORY_CHECKS + OPTIONAL_CHECKS


# Load real tables from JSON files
def load_test_tables():
    """Load real tables from debug JSON files."""
    tmp_dir = Path(__file__).parent

    tables = {}

    # Table with headers (0-1)
    json_file_1 = tmp_dir / "File #2 - Laurent M - tableau garantie fm 2025 word_page0_table0-1_phase3_completed_debug.json"
    if json_file_1.exists():
        with open(json_file_1) as f:
            data = json.load(f)
            tables["table_with_headers"] = {
                "html_content": data["landing_ai_html"],
                "table_id": data["table_id"]
            }

    # Table with monotonic progression issue (0-2k)
    json_file_2k = tmp_dir / "File #2 - Laurent M - tableau garantie fm 2025 word_page0_table0-2k_phase3_completed_debug.json"
    if json_file_2k.exists():
        with open(json_file_2k) as f:
            data = json.load(f)
            tables["table_monotonic_issue"] = {
                "html_content": data["landing_ai_html"],
                "table_id": data["table_id"],
                "expected_violations": data["violations"]
            }

    # Table missing headers (0-5v)
    json_file_5v = tmp_dir / "File #2 - Laurent M - tableau garantie fm 2025 word_page0_table0-5v_phase3_completed_debug.json"
    if json_file_5v.exists():
        with open(json_file_5v) as f:
            data = json.load(f)
            tables["table_no_headers"] = {
                "html_content": data["landing_ai_html"],
                "table_id": data["table_id"],
                "expected_violations": data["violations"]
            }

    return tables


async def test_sanity_checks():
    """Test sanity checks on real tables from the pipeline."""
    print("="*80)
    print("SANITY CHECKS TEST SUITE - REAL DATA")
    print("="*80)

    # Load real tables
    tables = load_test_tables()

    if not tables:
        print("❌ No test tables found in /tmp folder")
        print("Run the main pipeline first to generate debug JSON files")
        return

    print(f"\n✓ Loaded {len(tables)} real tables from debug JSON files\n")

    # Initialize Gemini client
    GoogleGenAIInstrumentor().instrument()
    client = genai.Client(
        vertexai=True,
        project="probtp-poc-prod",
        location="global",
    )

    try:
        # Test 1: Table with headers (should pass header check)
        if "table_with_headers" in tables:
            print("="*80)
            print("Test 1: Table WITH Headers (Table 0-1)")
            print("="*80)
            table = tables["table_with_headers"]
            print(f"Table ID: {table['table_id']}")
            print("Formatted HTML (first 300 chars):")
            formatted = format_html_for_llm(table['html_content'])
            print(formatted[:300] + "...")
            print("\nRunning mandatory header check...")

            result1 = await run_sanity_checks(
                client,
                table,
                MANDATORY_CHECKS
            )

            if result1.violations:
                print(f"❌ FAILED - {len(result1.violations)} violations found:")
                for v in result1.violations:
                    print(f"  - {v.check_id}: {v.description}")
            else:
                print("✅ PASSED - No violations found")

        # Test 2: Table with monotonic progression issue
        if "table_monotonic_issue" in tables:
            print("\n" + "="*80)
            print("Test 2: Table with Monotonic Progression Issue (Table 0-2k)")
            print("="*80)
            table = tables["table_monotonic_issue"]
            print(f"Table ID: {table['table_id']}")
            print(f"Expected violations: {len(table['expected_violations'])}")
            for v in table['expected_violations']:
                print(f"  - {v['check_id']}: {v['description'][:100]}...")

            print("\nRunning all sanity checks...")

            result2 = await run_sanity_checks(
                client,
                table,
                ALL_CHECKS
            )

            if result2.violations:
                print(f"Results - {len(result2.violations)} violations found:")
                for v in result2.violations:
                    print(f"  - {v.check_id}: {v.description[:150]}...")
                    if v.affected_cells:
                        print(f"    Affected cells: {', '.join(v.affected_cells)}")
            else:
                print("No violations found")

        # Test 3: Table without headers
        if "table_no_headers" in tables:
            print("\n" + "="*80)
            print("Test 3: Table WITHOUT Headers (Table 0-5v)")
            print("="*80)
            table = tables["table_no_headers"]
            print(f"Table ID: {table['table_id']}")
            print(f"Expected violations: {len(table['expected_violations'])}")
            for v in table['expected_violations']:
                print(f"  - {v['check_id']}: {v['description'][:100]}...")

            print("\nRunning mandatory header check...")

            result3 = await run_sanity_checks(
                client,
                table,
                MANDATORY_CHECKS
            )

            if result3.violations:
                print(f"✅ EXPECTED FAILURE - {len(result3.violations)} violations found:")
                for v in result3.violations:
                    print(f"  - {v.check_id}: {v.description[:150]}...")
            else:
                print("❌ UNEXPECTED PASS - No violations found (expected missing headers)")

        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        if "table_with_headers" in tables:
            print(f"Test 1 (With Headers): {'PASSED' if not result1.violations else 'FAILED'}")
        if "table_monotonic_issue" in tables:
            print(f"Test 2 (Monotonic): Completed - {len(result2.violations)} violations")
        if "table_no_headers" in tables:
            print(f"Test 3 (Without Headers): {'PASSED' if result3.violations else 'FAILED'}")

        print(f"\nNote: Tests use REAL tables from the pipeline with actual check descriptions")

    finally:
        if hasattr(client, "close"):
            try:
                if asyncio.iscoroutinefunction(client.close):
                    await client.close()
                else:
                    client.close()
            except Exception as e:
                print(f"Error closing client: {e}")


if __name__ == "__main__":
    asyncio.run(test_sanity_checks())
