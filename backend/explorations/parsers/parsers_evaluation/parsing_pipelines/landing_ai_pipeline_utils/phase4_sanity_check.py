"""Phase 4: Sanity Check Verification and Visual Correction."""
import re
from pathlib import Path
from typing import Any

import fitz
from google import genai
from google.genai.types import GenerateContentConfig, Part, ThinkingConfig
from langfuse import observe
from pydantic import BaseModel, Field

from .html_formatter import format_html_for_llm
from .phase1_parsers import standardize_empty_cells_html


# Sanity check definition
class SanityCheck(BaseModel):
    """Definition of a sanity check."""
    check_id: str
    description: str
    applies_to: str = "all"  # Can be "all", "headers", etc.


# Violation structure
class SanityViolation(BaseModel):
    """A sanity check violation."""
    check_id: str
    description: str
    affected_cells: list[str] = []


class SanityCheckResult(BaseModel):
    """Result of sanity checks on a table."""
    violations: list[SanityViolation]


# Run sanity checks with LLM
@observe()
async def run_sanity_checks(
    client: genai.Client,
    table: dict,
    sanity_checks: list[SanityCheck]
) -> SanityCheckResult:
    """
    Run sanity checks on a table using LLM.

    Returns:
        List of violations found
    """
    if not sanity_checks:
        return SanityCheckResult(violations=[])

    checks_text = '\n'.join([f"- {c.check_id}: {c.description}" for c in sanity_checks])

    # Format HTML for better readability
    formatted_html = format_html_for_llm(table['html_content'])

    prompt = f"""You are a data quality expert.

Evaluate this table against the following sanity checks:

{checks_text}

Table (HTML):
{formatted_html}

Identify any violations."""

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SanityCheckResult.model_json_schema(),
            thinking_config=ThinkingConfig(thinking_budget=300),
            temperature=0.0,
            max_output_tokens=1500
        )
    )

    raw_json = getattr(response, "text", "").strip()

    try:
        result = SanityCheckResult.model_validate_json(raw_json)
    except Exception:
        result = SanityCheckResult(violations=[])

    return result


# Generate screenshot for table
def generate_table_screenshot(
    pdf_path: str,
    page_num: int,
    grounding: dict,
    dpi: int = 300,
    save_to_tmp: bool = True,
    table_id: str = "unknown"
) -> bytes:
    """
    Generate a screenshot of a table area from PDF using Landing AI grounding.

    Returns:
        PNG image bytes
    """
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num)

    # Get normalized bbox coordinates from Landing AI grounding.box
    box = grounding.get('box', {})
    left = box.get('left', 0.0)
    right = box.get('right', 1.0)
    top = box.get('top', 0.0)
    bottom = box.get('bottom', 1.0)

    # Convert to absolute coordinates
    page_rect = page.rect
    x0 = left * page_rect.width
    x1 = right * page_rect.width
    y0 = top * page_rect.height
    y1 = bottom * page_rect.height

    # Add margin
    margin = 1
    clip_rect = fitz.Rect(
        max(0, x0 - margin),
        max(0, y0 - margin),
        min(page_rect.width, x1 + margin),
        min(page_rect.height, y1 + margin)
    )

    # Generate pixmap
    pix = page.get_pixmap(clip=clip_rect, dpi=dpi)
    img_bytes = pix.tobytes("png")

    # Save to tmp folder for debugging
    if save_to_tmp:
        tmp_dir = Path(__file__).parent / "tmp"
        tmp_dir.mkdir(exist_ok=True)

        from pathlib import Path as P
        pdf_name = P(pdf_path).stem
        screenshot_path = tmp_dir / f"{pdf_name}_page{page_num}_table{table_id}.png"

        with open(screenshot_path, "wb") as f:
            f.write(img_bytes)

    doc.close()
    return img_bytes


# Visual correction structure
class VisualCorrection(BaseModel):
    """Visual correction from LLM."""
    cell_id: str
    old_content: str
    new_content: str
    reason: str = Field(..., description="Concise explanation of the cell content correction, 200 words max.")


class VisualCorrectionResponse(BaseModel):
    """Response from vision LLM for cell content corrections."""
    layout_changes_needed: bool
    confidence_in_layout_changes: str
    corrections: list[VisualCorrection]



class HeaderCorrectionResponse(BaseModel):
    """Response from LLM for header reconstruction."""
    confidence: str  # "high" | "medium" | "low"
    new_header_row_HTML: str | None = None
    reason: str = Field(..., description="Concise explanation of the header correction, 200 words max.")


# Find previous table that passed header check
def find_previous_table_with_headers(
    current_page: int,
    current_table_idx: int,
    all_tables_by_page: dict,
    tables_header_status: dict
) -> dict | None:
    """
    Find the previous table that passed the header sanity check.

    Args:
        current_page: Current page number
        current_table_idx: Current table index on page
        all_tables_by_page: Dict of all tables by page
        tables_header_status: Dict tracking which tables have valid headers
            Format: {(page_num, table_idx): has_valid_headers}

    Returns:
        Previous table with valid headers, or None
    """
    # Check previous tables on same page
    if current_page in all_tables_by_page:
        for idx in range(current_table_idx - 1, -1, -1):
            # Check if this table has valid headers
            if tables_header_status.get((current_page, idx), False):
                return all_tables_by_page[current_page][idx]

    # Check previous page(s)
    for page in range(current_page - 1, -1, -1):
        if page in all_tables_by_page:
            # Check tables in reverse order (last to first)
            tables_on_page = all_tables_by_page[page]
            for idx in range(len(tables_on_page) - 1, -1, -1):
                if tables_header_status.get((page, idx), False):
                    return tables_on_page[idx]

    return None


# Helper function to count columns in a table row
def count_columns_in_row(row_html: str) -> int:
    """
    Count the total number of columns in an HTML table row, accounting for colspan.

    Args:
        row_html: HTML string of a table row (<tr>...</tr>)

    Returns:
        Total column count
    """
    import re

    # Find all td/th tags with their attributes
    cell_pattern = r'<t[dh](?:\s+[^>]*)?>'
    cells = re.findall(cell_pattern, row_html, re.IGNORECASE)

    total_cols = 0
    for cell in cells:
        # Check if cell has colspan attribute
        colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', cell, re.IGNORECASE)
        if colspan_match:
            total_cols += int(colspan_match.group(1))
        else:
            total_cols += 1

    return total_cols


# Helper function to get column count from table body
def get_table_column_count(html_content: str) -> int:
    """
    Get the column count from the first data row of a table.

    Args:
        html_content: HTML content containing the table

    Returns:
        Column count, or 0 if unable to determine
    """
    import re

    # Find the first <tr> tag after <table>
    table_match = re.search(r'<table[^>]*>(.*?)</table>', html_content, re.DOTALL | re.IGNORECASE)
    if not table_match:
        return 0

    table_body = table_match.group(1)

    # Find first row
    row_match = re.search(r'<tr[^>]*>(.*?)</tr>', table_body, re.DOTALL | re.IGNORECASE)
    if not row_match:
        return 0

    row_html = row_match.group(0)
    return count_columns_in_row(row_html)


# Apply header correction (no image needed)
@observe()
async def apply_header_correction(
    client: genai.Client,
    table: dict,
    previous_table: dict | None = None
) -> dict:
    """
    Use LLM to reconstruct missing headers based on previous table context.
    Does not require image - purely analytical based on table structure.

    Returns:
        Table dict with header row added if appropriate
    """
    if not previous_table:
        return table

    # Format previous table HTML with id removal and table truncation
    prev_html_formatted = format_html_for_llm(
        previous_table.get('html_content', ''),
        remove_ids=True,
        truncate_tables=True,
        max_rows=5
    )

    # Format current table HTML
    current_html_formatted = format_html_for_llm(table['html_content'])

    prompt = f"""You are a data quality expert specializing in structured document analysis.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK: Semantic Header Reconstruction
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The current table is missing headers. A reference table from the same document
with valid headers is provided. Your task is to determine if the reference headers
are semantically applicable to the current table, and if so, reconstruct them.

CRITICAL: Focus on SEMANTIC MEANING, not mechanical structure copying.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REFERENCE TABLE (with valid headers)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{prev_html_formatted}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT TABLE (missing headers)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{current_html_formatted}

━━━━━━━���━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS FRAMEWORK: Semantic-First Approach
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 1: SEMANTIC UNDERSTANDING (most important)
└─ For EACH table independently, determine:

   A. What information does this table convey?
      └─ Examples: "Product pricing tiers", "Employee benefits by plan level",
         "Financial metrics by quarter", "Technical specifications by model"

   B. What are the semantic dimensions/axes?
      └─ Most tables organize data along 1-2 dimensions:
         • Dimension 1 (rows): What categories? (e.g., benefit types, products, metrics)
         • Dimension 2 (columns): What groupings? (e.g., plan tiers, time periods, locations)
      └─ Example: A benefits table might be "Benefit Category × Plan Tier"

   C. Examine ALL rows holistically (not just one row):
      └─ Look at the entire data pattern across all rows
      └─ Identify data types in each column position (text, numbers, dates, codes, etc.)
      └─ Recognize repeating patterns or structures
      └─ Don't fixate on individual rows with special formatting

PHASE 2: SEMANTIC COMPATIBILITY CHECK
└─ Compare the two tables conceptually:

   A. Do they represent the same TYPE of information?
      ├─ Same domain? (e.g., both about benefits, or pricing, or schedules)
      ├─ Same purpose? (e.g., both comparing options across tiers)
      └─ Same conceptual structure? (e.g., both are "category × tier" matrices)

   B. Do the semantic dimensions align?
      ├─ If reference is "Benefit × Plan Level", is current also "Benefit × Plan Level"?
      ├─ Column count may differ (merged cells, parser variations, subset of tiers)
      ├─ What matters: Do columns serve the SAME SEMANTIC ROLE?
      └─ Example: Reference has P1-P6 columns, Current has P1-P4 → COMPATIBLE
                  Both use columns for "plan tiers", just different quantities

   C. Cross-validate with data patterns:
      ├─ Do data types align? (reference col 3 is numeric, current col 3 is numeric)
      ├─ Do value patterns match? (similar ranges, formats, units)
      └─ Do label patterns match? (similar terminology, abbreviations)

PHASE 3: HEADER MAPPING (only if Phase 2 confirms compatibility)
└─ Map reference header semantics to current table structure:

   A. Identify semantic roles of reference headers:
      └─ Which headers label categories? Which label groupings/tiers?
      └─ Are there grouping headers (colspan) vs. leaf headers?
      └─ What is the PURPOSE of empty cells? (structural spacing? aesthetic? data alignment?)

   B. Map to current table columns:
      └─ For each current column, determine its semantic role
      └─ Find corresponding reference header that matches that role
      └─ Adapt structure (colspan, positioning) to match current column count
      └─ DO NOT blindly copy empty cells - only include if semantically necessary

   C. Construct header row:
      └─ Total column span MUST match current table's column count
      └─ Preserve semantic meaning, not mechanical structure

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMMON PITFALLS TO AVOID
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ DON'T mechanically copy reference header structure
❌ DON'T fixate on empty cells in reference without understanding their purpose
❌ DON'T analyze only one row - examine ALL rows holistically
❌ DON'T force headers if semantic compatibility is unclear
❌ DON'T assume same column count means same structure

✓ DO understand what each table is ABOUT
✓ DO identify semantic dimensions/axes
✓ DO validate semantic compatibility before mapping
✓ DO adapt structure to current table's actual column count
✓ DO preserve semantic meaning over structural similarity

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TECHNICAL RULES (apply only after semantic validation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If headers ARE semantically appropriate:
├─ Format: <tr><td>Header1</td><td>Header2</td><td colspan="2">Grouped</td></tr>
├─ Requirements:
│  ├─ Use <td> tags ONLY (not <th>)
│  ├─ NO id attributes in any tags
│  ├─ Include empty cells ONLY if semantically meaningful: <td></td>
│  ├─ Use colspan for grouped concepts: <td colspan="N">Text</td>
│  └─ Total column span MUST match current table exactly
└─ Example (current table has 5 columns):
   <tr><td>Category</td><td colspan="2">Premium Tier</td><td colspan="2">Basic Tier</td></tr>
   └─ Breakdown: 1 + 2 (colspan) + 2 (colspan) = 5 columns ✓

If headers are NOT semantically appropriate (set new_header_row_HTML to null):
├─ Tables represent different types of information
├─ Semantic dimensions don't align
├─ Data patterns are inconsistent
├─ Any uncertainty about semantic compatibility
└─ REMEMBER: Better to omit headers than provide semantically wrong ones

CONFIDENCE LEVELS:
├─ "high": Clear semantic match, confident in header applicability
├─ "medium": Likely compatible but some ambiguity exists
└─ "low": Uncertain semantic compatibility → set new_header_row_HTML to null

CRITICAL: When in doubt about SEMANTIC compatibility, set new_header_row_HTML to null.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Provide your analysis and header reconstruction."""

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=HeaderCorrectionResponse.model_json_schema(),
            thinking_config=ThinkingConfig(thinking_budget=600),
            temperature=0.0,
            max_output_tokens=2000
        )
    )

    raw_json = getattr(response, "text", "").strip()

    try:
        correction_obj = HeaderCorrectionResponse.model_validate_json(raw_json)
    except Exception:
        return table

    # Only proceed if header row provided and confidence is acceptable
    if not correction_obj.new_header_row_HTML or correction_obj.confidence not in ["high", "medium"]:
        return table

    # Step 1: Validate column count matches
    original_col_count = get_table_column_count(table['html_content'])
    proposed_header_col_count = count_columns_in_row(correction_obj.new_header_row_HTML)

    final_header_row_html = correction_obj.new_header_row_HTML

    # Step 2: If column counts don't match, trigger corrective LLM call
    if original_col_count != proposed_header_col_count and original_col_count > 0:
        # Create partially corrected table for context
        partially_corrected_html = prepend_header_row(table['html_content'], correction_obj.new_header_row_HTML)
        formatted_partial = format_html_for_llm(partially_corrected_html)

        # Re-include reference table for semantic context
        prev_html_formatted_for_correction = format_html_for_llm(
            previous_table.get('html_content', ''),
            remove_ids=True,
            truncate_tables=True,
            max_rows=5
        ) if previous_table else "No reference table available"

        correction_prompt = f"""You are a data quality expert. A header row was proposed but has a column count mismatch.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROBLEM DETECTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Expected column count: {original_col_count}
Proposed header column count: {proposed_header_col_count}

This mismatch must be corrected while maintaining semantic alignment with the reference table.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REFERENCE TABLE (for semantic context)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{prev_html_formatted_for_correction}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT TABLE WITH INCORRECT HEADER (needs {original_col_count} columns)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{formatted_partial}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Correct the header row to have EXACTLY {original_col_count} columns (accounting for colspan).

CRITICAL REQUIREMENTS:
1. SEMANTIC ALIGNMENT: Review the reference table to understand the semantic meaning of each header
2. PATTERN MATCHING: For small tables, the reference table patterns are especially important
3. COLUMN MAPPING: Ensure each header semantically matches its corresponding data column
4. STRUCTURAL CONSISTENCY: Maintain the same semantic relationships as the reference table

TECHNICAL RULES:
1. Use <td> tags ONLY (never <th>)
2. NO id attributes in any tags
3. Include empty cells where needed: <td></td>
4. Use colspan for merged headers: <td colspan="N">Text</td>
5. CRITICAL: Total column span MUST equal {original_col_count}

CALCULATION EXAMPLE:
If target is 5 columns:
<tr><td>Col1</td><td></td><td colspan="2">Grouped</td><td>Last</td></tr>
└─ Count: 1 + 1 (empty) + 2 (colspan) + 1 = 5 ✓

DECISION CRITERIA:
- If you can adjust the header structure while maintaining semantic alignment → Provide corrected header
- If the semantic mismatch is too significant to resolve → Set new_header_row_HTML to null
- When in doubt about semantic correctness → Set new_header_row_HTML to null

Better to omit headers than provide semantically incorrect ones.

Provide the corrected header row HTML or null if unable to fix in the expected JSON format."""

        try:
            correction_response = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=correction_prompt,
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=HeaderCorrectionResponse.model_json_schema(),
                    thinking_config=ThinkingConfig(thinking_budget=1200),
                    temperature=0.0,
                    max_output_tokens=2000
                )
            )

            correction_raw_json = getattr(correction_response, "text", "").strip()
            correction_obj_2 = HeaderCorrectionResponse.model_validate_json(correction_raw_json)

            # Validate the corrected header
            if correction_obj_2.new_header_row_HTML:
                corrected_col_count = count_columns_in_row(correction_obj_2.new_header_row_HTML)
                if corrected_col_count == original_col_count:
                    final_header_row_html = correction_obj_2.new_header_row_HTML
                else:
                    # Still doesn't match, abort header correction
                    return table
            else:
                # LLM couldn't fix it, abort
                return table

        except Exception:
            # Error in correction attempt, abort
            return table

    # Step 3: Apply the validated header
    import copy
    corrected_table = copy.deepcopy(table)
    corrected_table['_pre_header_html_content'] = table['html_content']

    # Prepend header row
    corrected_html = prepend_header_row(table['html_content'], final_header_row_html)

    # Standardize empty cells in the entire table (including the new header and data rows)
    # This ensures empty cells below the header are represented as "-"
    corrected_html = standardize_empty_cells_html(corrected_html)

    corrected_table['html_content'] = corrected_html
    corrected_table['header_row_added'] = True
    corrected_table['header_correction_confidence'] = correction_obj.confidence
    corrected_table['header_correction_reason'] = correction_obj.reason
    corrected_table['header_column_count_match'] = (original_col_count == proposed_header_col_count)

    return corrected_table


# Apply visual corrections for cell content
@observe()
async def apply_visual_correction(
    client: genai.Client,
    table: dict,
    screenshot_bytes: bytes
) -> dict:
    """
    Use vision LLM to correct cell content based on screenshot.
    Focuses only on cell-level corrections, not structural changes.

    Returns:
        Corrected table dict
    """
    violations = table.get('sanity_violations', [])
    if not violations:
        return table

    # Filter out header violations - those are handled separately
    non_header_violations = [v for v in violations if v.check_id != "no_header"]

    if not non_header_violations:
        return table

    violations_text = '\n'.join([
        f"- {v.check_id}: {v.description}" for v in non_header_violations
    ])

    # Format current table HTML
    current_html_formatted = format_html_for_llm(table['html_content'])

    prompt = f"""You are a data quality expert specializing in structured document analysis.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IDENTIFIED ISSUES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{violations_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT TABLE (HTML)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{current_html_formatted}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CORRECTION INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use the screenshot as your visual reference to analyze and correct the table.

A. CELL CONTENT CORRECTIONS
   ├─ Purpose: Fix individual cell content errors
   ├─ Method: Use the 'corrections' array
   ├─ Required fields:
   │  ├─ 'cell_id': The id attribute from <td> or <th> tag (e.g., "0-2k", "1-5j")
   │  ├─ 'old_content': EXACT current text inside the cell
   │  ├─ 'new_content': Corrected text based on visual evidence
   │  └─ 'reason': Brief explanation (e.g., "OCR misread '0' as 'O'")
   ├─ Guidelines:
   │  ├─ Only correct cells with clear visual evidence of error
   │  ├─ old_content must match EXACTLY (whitespace-normalized)
   │  ├─ Be conservative: accuracy > completeness
   │  └─ If unsure, don't correct
   └─ Example:
      {{
        "cell_id": "2-3k",
        "old_content": "100€",
        "new_content": "10€",
        "reason": "Visual shows '10€' not '100€'"
      }}

B. LAYOUT CHANGES
   ├─ Field: 'layout_changes_needed' (boolean)
   ├─ Set to true ONLY if:
   │  ├─ Structural changes clearly needed (visual evidence)
   │  └─ High confidence in required changes
   ├─ Default: false
   └─ Rationale: Most issues are content errors, not structural

C. CONFIDENCE REPORTING
   ├─ Field: 'confidence_in_layout_changes'
   ├─ Values: "high" | "medium" | "low"
   ├─ Guidance:
   │  ├─ "high": Clear visual evidence, no ambiguity
   │  ├─ "medium": Reasonable evidence, some uncertainty
   │  └─ "low": Uncertain, multiple interpretations possible
   └─ Philosophy: Be conservative - accuracy over completeness

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Provide your response in JSON format following the VisualCorrectionResponse schema.

Example response structure:
{{
  "layout_changes_needed": false,
  "confidence_in_layout_changes": "high",
  "corrections": [
    {{
      "cell_id": "1-2k",
      "old_content": "1OO",
      "new_content": "100",
      "reason": "OCR misread zeros as letter O"
    }}
  ]
}}

Begin your analysis."""

    # Create image part
    image_part = Part.from_bytes(data=screenshot_bytes, mime_type="image/png")

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, image_part],
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=VisualCorrectionResponse.model_json_schema(),
            thinking_config=ThinkingConfig(thinking_budget=600),
            temperature=0.0,
            max_output_tokens=2000
        )
    )

    raw_json = getattr(response, "text", "").strip()

    try:
        corrections_obj = VisualCorrectionResponse.model_validate_json(raw_json)
    except Exception:
        return table

    # Preserve pre-correction content
    import copy
    corrected_table = copy.deepcopy(table)
    corrected_table['_pre_visual_correction_html'] = table['html_content']

    corrected_html = table['html_content']

    # Apply cell content corrections using cell_id
    for correction in corrections_obj.corrections:
        # Find and replace content within the specific cell
        cell_id = correction.cell_id
        # Match the cell with this ID and replace its content
        cell_pattern = rf'(<t[dh][^>]*\bid="{re.escape(cell_id)}"[^>]*>)(.*?)(</t[dh]>)'

        def replace_cell_content(match, corr=correction):
            opening_tag = match.group(1)
            current_content = match.group(2)
            closing_tag = match.group(3)

            # Only replace if current content matches old_content (whitespace-normalized)
            if current_content.strip() == corr.old_content.strip():
                return opening_tag + corr.new_content + closing_tag
            return match.group(0)  # No change if content doesn't match

        corrected_html = re.sub(cell_pattern, replace_cell_content, corrected_html, flags=re.DOTALL)

    corrected_table['html_content'] = corrected_html
    corrected_table['visual_corrections_applied'] = len(corrections_obj.corrections)

    return corrected_table


# Helper function to prepend header row
def prepend_header_row(html_content: str, header_row: str) -> str:
    """
    Prepend a header row to an HTML table.

    Args:
        html_content: Original HTML content containing the table
        header_row: Header row HTML (e.g., "<tr><td>Col1</td><td>Col2</td></tr>")

    Returns:
        HTML content with header row prepended
    """
    # Find the opening <table> tag and insert header row after it
    table_pattern = r'(<table[^>]*>)'

    def insert_header(match):
        opening_tag = match.group(1)
        return f"{opening_tag}\n{header_row}"

    # Insert header row right after <table> tag
    corrected_html = re.sub(table_pattern, insert_header, html_content, count=1)

    return corrected_html
