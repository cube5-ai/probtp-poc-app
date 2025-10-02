"""Phase 4: Sanity Check Verification and Visual Correction."""
import re
from pathlib import Path
from typing import Any

import fitz
from google import genai
from google.genai.types import GenerateContentConfig, Part, ThinkingConfig
from langfuse import observe
from pydantic import BaseModel

from .html_formatter import format_html_for_llm


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
    reason: str


class VisualCorrectionResponse(BaseModel):
    """Response from vision LLM."""
    layout_changes_needed: bool
    confidence_in_layout_changes: str
    new_header_row: str | None = None
    corrections: list[VisualCorrection]


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


# Apply visual corrections
@observe()
async def apply_visual_correction(
    client: genai.Client,
    table: dict,
    violations: list[SanityViolation],
    screenshot_bytes: bytes,
    previous_table: dict | None = None
) -> dict:
    """
    Use vision LLM to correct table based on screenshot.
    
    Returns:
        Corrected table dict
    """
    if not violations:
        return table
    
    violations_text = '\n'.join([
        f"- {v.check_id}: {v.description}" for v in violations
    ])
    
    # Check if missing header violation exists
    has_header_violation = any('header' in v.check_id.lower() or 'header' in v.description.lower() 
                                for v in violations)
    
    previous_table_context = ""
    if has_header_violation and previous_table:
        # Format previous table HTML
        prev_html_formatted = format_html_for_llm(previous_table.get('html_content', ''))
        
        previous_table_context = f"""

IMPORTANT: The current table appears to be missing headers. Here is a PREVIOUS table that PASSED header validation:

Previous Table (HTML):
{prev_html_formatted}

INSTRUCTIONS FOR HEADERS:
- Carefully examine if the previous table's first row contains headers that should apply to the current table
- If the headers are relevant, provide them in the 'new_header_row' field as a complete <tr> element
- The header row should contain only <td> tags WITHOUT any id attributes (since they weren't in the original)
- Example: "<tr><td>Column1</td><td>Column2</td><td>Column3</td></tr>"
- Match the number of columns in the current table
- Be cautious: only provide headers if you're confident they belong to the current table
- The previous table is provided for REFERENCE ONLY - it may or may not be related
"""
    
    # Format current table HTML
    current_html_formatted = format_html_for_llm(table['html_content'])
    
    prompt = f"""You are a document correction expert with vision capabilities.

Violated sanity checks:
{violations_text}
{previous_table_context}

Current table (HTML):
{current_html_formatted}

Analyze the screenshot and correct errors in the table.

CORRECTION INSTRUCTIONS:
1. For cell content corrections:
   - Use the 'corrections' array
   - Provide 'cell_id' (e.g., "0-2k" - the id attribute of the <td> or <th> tag)
   - Provide 'old_content' (exact current text) and 'new_content' (corrected text)
   
2. For missing headers:
   - If the table needs headers, provide a complete header row in 'new_header_row'
   - Format: "<tr><td>Header1</td><td>Header2</td></tr>" (WITHOUT id attributes)
   - This will be prepended to the table

3. Layout changes:
   - Set 'layout_changes_needed' to true only if confident
   - Avoid structural changes unless absolutely necessary

Provide corrections in JSON format."""
    
    # Create image part
    image_part = Part.from_bytes(data=screenshot_bytes, mime_type="image/png")
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, image_part],
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=VisualCorrectionResponse.model_json_schema(),
            thinking_config=ThinkingConfig(thinking_budget=800),
            temperature=0.0,
            max_output_tokens=3000
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
    corrected_table['_error_html_content'] = table['html_content']
    
    corrected_html = table['html_content']
    
    # Apply cell content corrections using cell_id
    for correction in corrections_obj.corrections:
        # Find and replace content within the specific cell
        cell_id = correction.cell_id
        # Match the cell with this ID and replace its content
        cell_pattern = rf'(<t[dh][^>]*\bid="{re.escape(cell_id)}"[^>]*>)(.*?)(</t[dh]>)'
        
        def replace_cell_content(match):
            opening_tag = match.group(1)
            current_content = match.group(2)
            closing_tag = match.group(3)
            
            # Only replace if current content matches old_content (case-insensitive, whitespace-normalized)
            if current_content.strip() == correction.old_content.strip():
                return opening_tag + correction.new_content + closing_tag
            return match.group(0)  # No change if content doesn't match
        
        corrected_html = re.sub(cell_pattern, replace_cell_content, corrected_html, flags=re.DOTALL)
    
    # Prepend header row if provided
    if corrections_obj.new_header_row:
        corrected_html = prepend_header_row(corrected_html, corrections_obj.new_header_row)
    
    corrected_table['html_content'] = corrected_html
    corrected_table['visual_corrections_applied'] = len(corrections_obj.corrections)
    if corrections_obj.new_header_row:
        corrected_table['header_row_added'] = True
    
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

