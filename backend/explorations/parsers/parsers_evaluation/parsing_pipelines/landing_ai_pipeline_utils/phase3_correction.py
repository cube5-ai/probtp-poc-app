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
    pdf_path: str | None = None,
    page_num: int | None = None
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

    # Build prompt with focused correction approach
    prompt = f"""You are a table extraction correction specialist.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  CRITICAL FIRST PRINCIPLE ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Only correct text errors that affect MEANING or prevent READABILITY.
Do NOT correct cosmetic spacing/punctuation that doesn't impair comprehension.

READABILITY ERRORS - DO CORRECT:
✓ "65%30%15%" → "65% 30% 15%" (run-together values are unreadable)
✓ "FraisréelsOPTAM" → "Frais réels OPTAM" (missing word boundaries)
✓ "1OO€" → "100€" (OCR misread character: "O" instead of "0")
✓ "anti-grppe" → "anti-grippe" (missing letter makes word unreadable)
✓ "Premium" → "Premium benefits" (missing content changes meaning)

COSMETIC VARIATIONS - DO NOT CORRECT:
✗ "100 %" vs "100%" (both equally readable)
✗ "Verres: frais" vs "Verres : frais" (both equally readable)
✗ "15€" vs "15 €" (both equally readable)
✗ "Item1, Item2" vs "Item1,Item2" (both equally readable)
✗ "-" vs "—" vs "*" (all mean "empty/not covered")
✗ "✓ Text" vs "Text" (Landing AI saw a visual element, keep it)

THE TEST: Would a human reader struggle to parse or misunderstand the current text?
→ If YES: Correct it (readability/meaning issue)
→ If NO: Leave it (cosmetic variation)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You have two imperfect extractions of the same table:

LANDING AI (OCR-based):
  ✓ Excellent cell boundaries and table structure
  ✓ Can detect images, logos, icons in cells
  ✗ Prone to OCR errors (misread characters, missing text, run-together words)

PYMUPDF (Text extraction):
  ✓ Accurate text with high character fidelity
  ✗ May misunderstand cell boundaries
  ✗ Text-only - cannot see images, logos, or icons

YOUR JOB: Fix text errors in Landing AI cells using PyMuPDF as reference.

OUTPUT: JSON list of corrections with:
- cell_id: Landing AI cell ID
- old_content: Current (incorrect) content
- new_content: Corrected content
- confidence: "high" | "medium"
- reason: Brief explanation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LANDING AI TABLE (HTML - Structure Reference)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{landing_html_formatted}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PYMUPDF TABLE (Markdown - Text Reference)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{pymupdf_markdowns}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CORRECTION GUIDELINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Identify the type of differences

A) OCR CHARACTER ERRORS - Wrong characters that change meaning
   Example: "1OO€" should be "100€" (letter O instead of digit 0)
   → Correct: YES (high confidence if PyMuPDF confirms)

B) NOT READABLE ERRORS - Missing spaces that prevent parsing
   Example: "65%30%15%" should be "65% 30% 15%" (can't tell where values separate)
   → Correct: YES (high confidence - values are run together)

   Example: "FraisréelsOPTAM" should be "Frais réels OPTAM" (words glued together)
   → Correct: YES (high confidence - word boundaries missing)

C) MISSING CONTENT - Text present in PyMuPDF but absent from Landing AI
   Example: Landing AI has "Premium" but PyMuPDF has "Premium benefits"
   → Check: Is "benefits" found in other Landing AI cells nearby?
     - If NO: Correct (likely missing)
     - If YES: Don't correct (PyMuPDF merged cells)

D) VISUAL CONTENT - Images, logos, icons that only Landing AI can see
   Example: Landing AI has "✓ Premium" but PyMuPDF has only "Premium"
   → Correct: NO (Landing AI has extra visual information, keep it)

   Example: Landing AI has "[logo] Company" but PyMuPDF has "Company"
   → Correct: NO (Landing AI captured visual element, this is valuable)

E) COSMETIC SPACING - Spacing that doesn't affect parsing
   Example: "100 %" vs "100%" (both equally clear)
   → Correct: NO (forbidden - just a style difference)

STEP 2: Trust Landing AI structure

- DON'T merge cells even if PyMuPDF concatenates them
- DON'T split cells even if PyMuPDF separates content
- If content appears in DIFFERENT Landing AI cells, PyMuPDF likely merged them incorrectly

STEP 3: Apply confidence levels

"high" = Obvious OCR error or missing text, PyMuPDF clearly shows the correct version
"medium" = Likely error but some ambiguity
"low" = Uncertain → DO NOT include

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS PROCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each Landing AI cell:

1. Does it have OCR character errors?
   - Wrong letters/digits (1 vs l, O vs 0, etc.)
   - Garbled text
   - Misspelled words (check against PyMuPDF)

2. Does it have errors completely preventing readability?
   - Run-together values that look like one item ("65%30%15%")
   - Missing spaces between words ("FraisréelsOPTAM")
   - Would a human need to guess where breaks occur?

3. Is content missing?
   - Compare with PyMuPDF content
   - Search for "missing" content in adjacent Landing AI cells
   - Only correct if truly absent (not just in another cell)

4. Is this just cosmetic?
   - Does the spacing/punctuation difference affect comprehension?
   - If both versions are equally readable → SKIP IT

5. Create correction entry only if:
   - Confidence is "high" or "medium"
   - old_content ≠ new_content
   - It fixes a readability or meaning issue

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FINAL VALIDATION CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before adding ANY correction, verify:

□ Is this fixing wrong characters, missing text, or unreadable run-together text?
  → If NO, DELETE this correction

□ Would a human reader understand the content differently after the fix?
  → If NO, DELETE this correction

□ Does old_content exactly match the Landing AI cell content?
  → If NO, fix the match

□ Is new_content actually different from old_content?
  → If NO, DELETE this correction

□ Is confidence "high" or "medium" (not "low")?
  → If NO, DELETE this correction

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return corrections as JSON. If no corrections needed: {{"corrections": []}}

Begin your analysis."""

    # Call LLM with focused thinking budget
    response = await client.aio.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CorrectionsResponse.model_json_schema(),
            thinking_config=ThinkingConfig(thinking_budget=500),
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
    applied_count = 0

    for correction in corrections_obj.corrections:
        # Skip if old_content == new_content (no actual change)
        if correction.old_content == correction.new_content:
            continue

        # Skip if not high/medium confidence
        if correction.confidence not in ['high', 'medium']:
            continue

        corrected_html = corrected_html.replace(
            correction.old_content,
            correction.new_content,
            1  # Replace only first occurrence
        )
        applied_count += 1

    corrected_table['html_content'] = corrected_html
    corrected_table['corrections_applied'] = applied_count

    return corrected_table

