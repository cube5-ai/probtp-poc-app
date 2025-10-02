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

    # Build prompt with flexible semantic synthesis approach
    prompt = f"""You are a document parsing expert specializing in table extraction synthesis.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK: Synthesize Two Imperfect Table Extractions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You have two different extraction attempts of the same table, each with different strengths:

LANDING AI (OCR-based):
  ✓ Strengths: Excellent at detecting cell boundaries and table structure
  ✗ Weaknesses: Prone to character-level OCR errors (misreading characters, missing text)

PYMUPDF (Text extraction):
  ✓ Strengths: Accurate text extraction with high character fidelity
  ✗ Weaknesses: May misunderstand cell boundaries (merge cells that should be separate,
               or split content that belongs together)

YOUR GOAL: Identify specific cell-level edits needed in the Landing AI table to improve
           text accuracy by synthesizing evidence from both extraction sources.

OUTPUT: A list of cell corrections in JSON format, where each correction specifies:
        - cell_id: The ID of the Landing AI cell to edit
        - old_content: The current (incorrect/incomplete) content
        - new_content: The corrected/completed content
        - confidence: "high" | "medium" | "low"
        - reason: Brief explanation of why this correction improves accuracy

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LANDING AI TABLE (HTML - Structure Reference)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Note: Empty cells in non-header rows are represented as <td>-</td>

{landing_html_formatted}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PYMUPDF TABLES (Markdown - Text Reference)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Note: Empty cells in non-header rows are represented as "-"

{pymupdf_markdowns}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEMANTIC SYNTHESIS FRAMEWORK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 1: UNDERSTAND THE TABLE HOLISTICALLY
└─ What does this table represent? (e.g., pricing, benefits, specifications, schedule)
└─ What are the semantic columns? (e.g., category, tier, value, description)
└─ What data types should each column contain? (text, numbers, dates, codes)
└─ What patterns should repeat? (units, formatting, terminology)

PHASE 2: ANALYZE BOTH SOURCES AS EVIDENCE
└─ Treat both as imperfect witnesses to the same underlying table

A. For each Landing AI cell, examine:
   ├─ Does the content make semantic sense for this column type?
   ├─ Are there obvious OCR errors? (garbled text, wrong characters, missing content)
   ├─ Does it match expected patterns? (e.g., numeric column should have numbers)
   └─ Is it complete? (does it feel like something is missing?)

B. For PyMuPDF content, examine:
   ├─ How is the text grouped? (what appears together in PyMuPDF?)
   ├─ Are there spacing/formatting cues? (line breaks, whitespace, punctuation)
   ├─ Does PyMuPDF's grouping suggest semantic unity or separation?
   └─ Does PyMuPDF contain content absent from Landing AI?

C. Cross-reference patterns:
   ├─ Where do they agree? (high confidence - likely correct)
   ├─ Where do they disagree? (needs interpretation)
   ├─ Is PyMuPDF content found distributed across multiple Landing AI cells?
      └─ This suggests Landing AI correctly split cells, PyMuPDF concatenated
   ├─ Is PyMuPDF content completely absent from all Landing AI cells?
      └─ This suggests Landing AI OCR missed it entirely
   ├─ Does PyMuPDF show natural breaks (spacing, punctuation) within its text?
      └─ This provides clues about whether content should be split or unified

PHASE 3: SEMANTIC ARBITRATION
└─ Use contextual reasoning to decide corrections:

SCENARIO A: OCR Character Errors
├─ Landing AI: "1OO€" (O instead of 0)
├─ PyMuPDF: "100€"
├─ Decision: Correct - clear OCR misread, PyMuPDF has accurate text
└─ Confidence: High (if semantic and pattern match)

SCENARIO B: OCR Missing Content
├─ Landing AI cell: "Premium"
├─ PyMuPDF: "Premium benefits include coverage"
├─ Check: Is "benefits include coverage" found in other Landing AI cells?
│  └─ No → Landing AI likely truncated/missed content
├─ Decision: Augment Landing AI cell with missing content
└─ Confidence: High if content is semantically coherent for this cell

SCENARIO C: Layout Disagreement - Trust OCR Structure
├─ Landing AI: Cell A="Value 1" | Cell B="Value 2"
├─ PyMuPDF: "Value 1 Value 2" (concatenated)
├─ Check: Do "Value 1" and "Value 2" appear separately in Landing AI?
│  └─ Yes → Landing AI correctly identified cell boundaries
├─ Decision: Do NOT merge - OCR structure is correct
└─ Confidence: High if Landing AI structure is semantically logical

SCENARIO D: PyMuPDF Layout Hints
├─ Landing AI: One cell with "Plan A Plan B"
├─ PyMuPDF markdown shows: "Plan A\n\nPlan B" (clear separation)
├─ Semantic check: Should these be separate based on table meaning?
│  └─ If yes: Consider flagging (but DON'T change structure - outside scope)
│  └─ If no: Trust Landing AI structure
├─ Decision: Preserve Landing AI structure (we correct content, not layout)

SCENARIO E: Image-Based Content Fusion
├─ Landing AI: "[icon] Premium" (captured icon description from OCR)
├─ PyMuPDF: "Premium" (no icon, text extraction only)
├─ Decision: Keep Landing AI content (it has extra visual information)
└─ Note: Don't "correct" away image-derived content

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CORRECTION PRINCIPLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ DO correct: Character-level OCR errors that alter meaning
✓ DO augment: Landing AI cells missing content that PyMuPDF has (and isn't elsewhere)
✓ DO preserve: Landing AI cell structure (don't merge/split cells)
✓ DO consider: PyMuPDF spacing/grouping as evidence for semantic relationships
✓ DO validate: Corrections against semantic patterns (data types, units, terminology)

✗ DON'T correct: ANY spacing, punctuation, or formatting variations that don't alter MEANING
   STRICTLY FORBIDDEN to correct:
   • "Revenue: increase" vs "Revenue : increase"(spacing around colons) - FORBIDDEN
   • "100%" vs "100 %" (spacing around percent symbols) - FORBIDDEN
   • "20€" vs "20 €" (spacing before currency) - FORBIDDEN
   • "Item1, Item2" vs "Item1,Item2" (spacing around punctuation) - FORBIDDEN
   • "Section A" vs "Section  A" (extra whitespace) - FORBIDDEN
   • Line breaks or paragraph formatting differences - FORBIDDEN
   • "-" (empty cell placeholder) - this is standardized and intentional - FORBIDDEN

   ONLY correct if text content is WRONG or MISSING, NOT for "standardization" or "consistency"
✗ DON'T merge: Landing AI cells even if PyMuPDF concatenates them
✗ DON'T split: Landing AI cells even if PyMuPDF separates content
✗ DON'T overwrite: Image-derived content from Landing AI with PyMuPDF text-only version
✗ DON'T force: Corrections when confidence is low or semantic fit is unclear

CONFIDENCE LEVELS:
├─ "high": Clear OCR error or missing content that changes meaning, strong semantic/pattern evidence
├─ "medium": Likely OCR error/missing content but some ambiguity exists
└─ "low": Uncertain - DO NOT include in corrections

NOTE: "Standardizing spacing/punctuation" is NEVER high or medium confidence - it's FORBIDDEN.
      Only actual text errors (wrong characters, missing words) qualify as corrections.

CRITICAL: Only suggest corrections that improve text accuracy while respecting
          Landing AI's structural interpretation. When in doubt, don't correct.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  CRITICAL RULE: DO NOT "standardize" or "normalize" spacing/punctuation/formatting.
    Only correct ACTUAL ERRORS where text content is wrong, missing, or unreadable.

    Examples of what to IGNORE (these are NOT errors):
    - "Revenue: increase" vs "Revenue : increase" - IGNORE (just spacing)
    - "100€" vs "100 €" - IGNORE (just spacing)
    - "$100" vs "100$" - IGNORE (just formatting)
    - "Item1,Item2" vs "Item1, Item2" - IGNORE (just spacing)

    Examples of what to CORRECT (these ARE errors):
    - "1OO€" vs "100€" - CORRECT (OCR misread "0" as "O")
    - "Premium" vs "Premium benefits" - CORRECT (missing text)
    - "xyz@gmial.com" vs "xyz@gmail.com" - CORRECT (typo/OCR error)
    - "GoldSilverBronze" vs "Gold Silver Bronze" - CORRECT (typo/OCR glued wordserror)

1. Examine the Landing AI table and understand its semantic structure
2. Compare each cell's content with the corresponding PyMuPDF content
3. For each Landing AI cell where you identify an improvement opportunity:

   a) Determine the type of issue:
      • OCR character error (misread characters)
      • OCR missing content (text PyMuPDF has but Landing AI doesn't)
      • Other text accuracy issue

   b) Validate the correction using semantic reasoning:
      • FIRST: Is this ONLY a spacing/punctuation/formatting change? → REJECT IT IMMEDIATELY
      • Does the correction change the MEANING or fix a comprehension issue?
      • Would a human reader understand the content differently? (if not, DON'T correct)
      • Is actual TEXT wrong, missing, or garbled? (not just formatted differently)
      • Does the PyMuPDF content make semantic sense for this cell?
      • Does it match the expected pattern (data type, units, format)?
      • If augmenting: Is this content genuinely missing, or just in another cell?
      • Is the correction high enough confidence to apply?

      REMEMBER: "Verres: frais" vs "Verres : frais" = SAME MEANING = DO NOT CORRECT

   c) If valid, add a correction specifying:
      • cell_id: The exact cell ID from the Landing AI HTML
      • old_content: The exact current content (must match precisely)
      • new_content: The corrected/completed content (MUST be different from old_content)
      • confidence: "high" or "medium" only (don't include "low")
      • reason: Concise explanation (e.g., "OCR misread '0' as 'O'",
                "Landing AI missing 'coverage' text present in PyMuPDF")

4. Return the list of corrections as a JSON object

IMPORTANT:
- Each correction will be applied as a direct text replacement in the Landing AI HTML
- old_content must match the current cell content exactly
- new_content MUST be DIFFERENT from old_content (if they're the same, DON'T include it)
- DO NOT include entries where "no correction needed" - just skip them entirely

If no corrections are needed, return an empty corrections array: {{"corrections": []}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Begin your analysis and provide the corrections in JSON format."""

    # Call LLM with increased thinking budget for semantic synthesis
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CorrectionsResponse.model_json_schema(),
            thinking_config=ThinkingConfig(thinking_budget=1000),
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

