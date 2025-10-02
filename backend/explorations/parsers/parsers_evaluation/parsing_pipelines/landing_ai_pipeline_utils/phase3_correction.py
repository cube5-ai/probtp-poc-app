"""Phase 3: LLM-Based Correction."""
import copy
import re
from pathlib import Path
from typing import Any

import fitz
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig
from langfuse import observe
from pydantic import BaseModel

from .html_formatter import format_html_for_llm


# Correction structure
class CellCorrection(BaseModel):
    """Structure for a single cell correction."""
    cell_id: str
    old_content: str
    new_content: str
    confidence: str
    reason: str


class CorrectionsResponse(BaseModel):
    """Response from LLM with corrections."""
    corrections: list[CellCorrection]


# Generate screenshot for debugging
def save_table_screenshot_phase3(
    pdf_path: str,
    page_num: int,
    grounding: dict,
    table_id: str = "unknown",
    dpi: int = 300
) -> None:
    """Save table screenshot to tmp folder for Phase 3 debugging."""
    try:
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
        margin = 5
        clip_rect = fitz.Rect(
            max(0, x0 - margin),
            max(0, y0 - margin),
            min(page_rect.width, x1 + margin),
            min(page_rect.height, y1 + margin)
        )

        # Generate pixmap
        pix = page.get_pixmap(clip=clip_rect, dpi=dpi)

        # Save to tmp folder
        tmp_dir = Path(__file__).parent / "tmp"
        tmp_dir.mkdir(exist_ok=True)

        pdf_name = Path(pdf_path).stem
        screenshot_path = tmp_dir / f"{pdf_name}_page{page_num}_table{table_id}_phase3.png"
        pix.save(str(screenshot_path))

        doc.close()
    except Exception as e:
        print(f"Failed to save screenshot for table {table_id}: {e}")


# Apply LLM corrections to Landing AI table
@observe()
async def correct_table_with_llm(
    client: genai.Client,
    landing_table: dict,
    matched_pymupdf_tables: list[dict],
    pdf_path: str = None,
    page_num: int = None
) -> dict:
    """
    Use LLM to identify and apply corrections to Landing AI table.
    
    Returns:
        Updated table dict with corrections applied
    """
    if not matched_pymupdf_tables:
        return landing_table
    
    # Save screenshot for debugging if pdf_path provided
    if pdf_path and page_num is not None:
        table_id_match = re.search(r'<table id="([^"]+)"', landing_table.get('html_content', ''))
        table_id = table_id_match.group(1) if table_id_match else 'unknown'
        # Use the grounding from the chunk, not bbox
        grounding = landing_table.get('chunk', {}).get('grounding', {})
        save_table_screenshot_phase3(pdf_path, page_num, grounding, table_id)
    
    # Format HTML for better readability
    landing_html_formatted = format_html_for_llm(landing_table['html_content'])
    pymupdf_markdowns = '\n\n---\n\n'.join([t['markdown'] for t in matched_pymupdf_tables])
    
    # Build prompt
    system_message = """You are a document parsing expert.

Landing AI is OCR-based and may have character-level errors but is very good at table layout.
PyMuPDF preserves text accurately but layout may be incorrect.

Task: Identify cell content corrections needed in the Landing AI table using the following rules:

Instructions:
- IF a cell in Landing AI contains a major OCR error that alters meaning or comprehension, THEN suggest a correction using PyMuPDF content.
- IF a cell difference is minor (minor spelling variations, formatting differences, or layout variations), THEN do NOT suggest a correction.
- IF a cell difference could result from an image present in the Landing AI cell but not captured by PyMuPDF, THEN fuse the Landing AI cell content with the PyMuPDF content.
- IF you are not confident about whether a correction is needed, THEN do NOT suggest a correction.
- IF the correction would alter the table layout or structure, THEN do NOT suggest it.

Provide corrections in JSON format."""
    
    user_message = f"""Landing AI Table (HTML):
{landing_html_formatted}

PyMuPDF Tables (Markdown):
{pymupdf_markdowns}

Identify corrections needed."""
    
    prompt = f"{system_message}\n\n{user_message}"
    
    # Call LLM
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CorrectionsResponse.model_json_schema(),
            thinking_config=ThinkingConfig(thinking_budget=600),
            temperature=0.0,
            max_output_tokens=6000
        )
    )
    
    raw_json = getattr(response, "text", "").strip()
    
    try:
        corrections_obj = CorrectionsResponse.model_validate_json(raw_json)
    except Exception:
        print(f"No valid corrections found for table {landing_table}")
        # No valid corrections
        return landing_table
    
    # Preserve original content
    corrected_table = copy.deepcopy(landing_table)
    corrected_table['_raw_html_content'] = landing_table['html_content']
    
    # Apply corrections (simple string replacement for now)
    corrected_html = landing_table['html_content']
    
    for correction in corrections_obj.corrections:
        if correction.confidence in ['high', 'medium']:
            corrected_html = corrected_html.replace(
                correction.old_content,
                correction.new_content,
                1  # Replace only first occurrence
            )
    
    corrected_table['html_content'] = corrected_html
    corrected_table['corrections_applied'] = len(corrections_obj.corrections)
    
    return corrected_table

