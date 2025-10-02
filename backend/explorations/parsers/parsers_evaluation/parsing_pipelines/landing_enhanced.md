# Enhanced Pipeline for Landing AI Document Extraction

## Project Setup

**Package Management**: Use `uv` for all Python package management
**Required Dependencies**: 
- pymupdf (for deterministic PDF parsing, use with `import fitz`)
- pandas (for data manipulation)
- scikit-learn (for TF-IDF vectorization)
- rapidfuzz (for fuzzy string matching - experimental phase only)
- google genai (`from google import genai`)
- langfuse for observability.

## Context

Landing AI is the best Agentic Document Extraction provider investigated. As an OCR/visual-based system, it can make character-level mistakes or imprecisions. Tables are the most critical and complex part of the current project. PyMuPDF is a deterministic PDF parsing pipeline with good table identification ability, though it struggles with table layouts and merged cells. However, its cell content, even if wrongly placed spatially, is correct and doesn't suffer from OCR limitations on small fonts. Medium LLMs (like Gemini 2.5 Flash, GPT 5 Mini) are good at copy-pasting and identifying mistakes, and can be instructed to identify in-cell corrections to apply. LLMs with vision abilities can understand discrepancies between parsing results and visual reality when provided focused images.

## Goals

1. Improve the quality and accuracy of cell content in Landing AI output by leveraging PyMuPDF's accurate text without changing the layout
2. Identify suspicious patterns in data and ask LLMs to check the parsing output (sanity check patterns provided by user)
3. Recover from wrong parsing

## Implementation Instructions

---

### Phase 1 — Parse and Get Tables List

**Objective**: Parse document with both parsers and extract table structures per page

**Landing AI Parser**:
- Parse the document using Landing AI's API
- Store the complete response structure preserving all metadata
- Extract tables from the response - Landing AI likely returns tables with HTML or structured format
- Create a function `get_landing_tables(landing_response)` that returns a dictionary:
  - Key: page number (integer)
  - Value: list of table objects, where each table contains:
    - `content`: HTML or markdown representation of the table
    - `bbox`: bounding box coordinates if available
    - `metadata`: any additional metadata from Landing AI

**PyMuPDF Parser**:
- Open the PDF document using `pymupdf.open(pdf_path)`
- Iterate through pages using zero-based indexing
- For each page, call `page.find_tables()` which returns a TableFinder object
- Access the tables list via the `.tables` attribute of the TableFinder object
- Create a function `get_pymupdf_tables(pdf_path)` that returns a dictionary:
  - Key: page number (integer)
  - Value: list of Table objects with the following structure:
    - Each Table object has these attributes:
      - `.extract()`: method returning list of lists (rows, then cells)
      - `.to_markdown()`: method returning markdown string
      - `.bbox`: tuple (x0, y0, x1, y1) - bounding box coordinates
      - `.cells`: list of cell bounding boxes (may contain None for merged cells)
      - `.row_count` and `.col_count`: integers for dimensions
      - `.header`: TableHeader object with `.names` (list), `.external` (boolean)
- Store both the Table object and its extracted content

**Alternative approach using pymupdf4llm**:
- Can use `pymupdf4llm.to_markdown(pdf_path, page_chunks=True)` which returns list of dictionaries
- Each dictionary contains `text`, `tables`, `metadata` for a page
- The `tables` key contains a list with `bbox`, `row_count`, `col_count` for each table
- Use the standard pymupdf approach with `page.find_tables()` to get actual Table objects with full functionality

**Output**: Two dictionaries mapping page numbers to lists of tables

---

### Phase 2 — Match Tables

**Objective**: Match Landing AI tables to corresponding PyMuPDF tables per page

**Text Extraction and Cleaning for TF-IDF**:
- Create a function `clean_cell_content(text)` that applies cleaning in this order:
  1. Strip HTML tags (e.g., `<br>`, `<b>`, etc.)
  2. Strip markdown formatting (e.g., `|`, `**`, `##`)
  3. Convert `\n` and other line break characters to single space
  4. Convert HTML `<br>` tags to space
  5. Remove LaTeX location markers in markdown (patterns like `{#...}` or similar)
  6. Add space after percentage signs followed by letters: `%[a-zA-Z]` → `% [a-zA-Z]`
  7. Collapse multiple whitespace characters to single space
  8. Trim leading and trailing whitespace
  9. Map empty cells or cells with only single non-alphanumeric characters to empty string
  10. Keep currency symbols, units, periods, and commas as-is
  11. Keep scientific notation as-is (data is string anyway)
  12. Apply lowercase transformation ONLY for comparison purposes (preserve original)
- For PyMuPDF, also extract text from text blocks on the page (using `page.get_text("blocks")`) as they could have been wrongly interpreted as tables

**TF-IDF Vectorization**:
- For each page, build two collections:
  - Landing AI tables: clean all cell contents, create bag of words per table
  - PyMuPDF tables: clean all cell contents, create bag of words per table (include text blocks as potential table candidates)
- Construct TF-IDF vectors treating each table (or text block) as a document
- Use scikit-learn's TfidfVectorizer with appropriate parameters

**Matching Algorithm**:
- For each Landing AI table on a page:
  - Calculate cosine similarity with all PyMuPDF tables and text blocks on that page
  - Filter matches by:
    - Minimum similarity threshold (permissive, e.g., 0.3-0.5)
    - Word count constraint: PyMuPDF table(s) total word count ≤ 3 × Landing AI table word count
  - Select top N matches (where N can be 0 to multiple matches)
  - If multiple PyMuPDF tables match, preserve them as a list (handles table splitting)
- Create a matching structure:
  - Dictionary with Landing AI table as key
  - Value: list of PyMuPDF Table objects (empty list if no match)
- Preserve this matching structure for Phase 3

**Edge Cases**:
- Landing AI table with 0 PyMuPDF matches: preserve as-is, mark for Phase 4 verification only
- PyMuPDF table with 0 Landing AI matches: ignore (not used)
- If best match exceeds 3× word count: skip to next best match, or if none suitable, use empty list

**Output**: Dictionary mapping each Landing AI table to a list of 0-N matched PyMuPDF tables

---

### Phase 3 — LLM-Based Correction (Default) + Fuzzy Matching (Experimental)

**Primary Path: LLM Correction**

**For each matched table pair** (Landing AI table + list of PyMuPDF tables):

**Skip conditions**:
- If PyMuPDF match list is empty, skip to Phase 4

**LLM Prompt Construction**:
- System message should explain:
  - Landing AI is OCR-based and may have character-level errors
  - PyMuPDF preserves text accurately but layout may be incorrect
  - Task is to identify cell content corrections needed in Landing AI table
  - Must NOT alter layout unless very confident
  - Focus on correcting OCR errors, not restructuring
- Provide to LLM:
  - Landing AI table in HTML format
  - All matched PyMuPDF tables in markdown format
  - Request structured JSON output with format:
    ```json
    {
      "corrections": [
        {
          "cell_id": "id of the cell",
          "old_content": "original text",
          "new_content": "corrected text",
          "confidence": "high|medium|low",
          "reason": "brief explanation"
        }
      ]
    }
    ```
- Use Gemini 2.5 Flash or GPT 4o Mini for this task

**Apply Corrections**:
- Before applying any correction, duplicate the original content in Landing AI response object:
  - Add a new field `_raw_<fieldname>` to preserve original value
  - Example: if field is `html_content`, create `_raw_html_content`
- Apply each correction from LLM response:
  - Locate the cell by row and column index
  - Replace the content while preserving HTML structure and formatting
  - Track which corrections were applied
- Do NOT alter table layout (row/column structure, merged cells, etc.)

**Fallback: Experimental Fuzzy Matching Path**

**Note**: This path is experimental and should be optional via configuration flag

**Build Cell Content Sets**:
- Extract all cell contents from Landing AI table, apply `clean_cell_content()` function
- Create a mapping structure that preserves:
  - `cleaned_content`: cleaned version for matching
  - `original_content`: original content from Landing AI
  - `cell_positions`: list of (row_index, col_index) tuples where this content appears
- Do the same for all matched PyMuPDF tables

**Fuzzy Matching Process**:
- Create a set of cleaned PyMuPDF cell contents
- For each cleaned Landing AI cell content:
  - Check if it exists in PyMuPDF set (exact match after cleaning)
  - If NO exact match:
    - Use rapidfuzz to find closest match in PyMuPDF set
    - Set reasonable threshold (e.g., score > 80)
    - If match found, create replacement mapping
- Build replacement map with structure:
  ```python
  {
    cell_position: {
      "old_content": original_landing_ai_content,
      "new_content": matched_pymupdf_content,
      "confidence_score": fuzzy_match_score
    }
  }
  ```

**Apply Fuzzy Replacements**:
- Before applying, duplicate original content to `_raw_<fieldname>` field
- For each cell_position in replacement map:
  - Replace content at that specific position only
  - Do NOT replace all occurrences globally
  - Preserve HTML structure and formatting
- Track fuzzy matching statistics (number of replacements, average confidence)

**Output**: Modified Landing AI tables with corrections applied and original content preserved in `_raw_*` fields

---

### Phase 4 — Sanity Check Verification and Visual Correction

**Sanity Check Definition**:
- User provides sanity checks as a list in a configuration file (YAML or JSON)
- Each sanity check should contain:
  - `check_id`: unique identifier
  - `description`: human and LLM-readable description


**Example sanity check configuration**:
```yaml
sanity_checks:
  - check_id: "revenue_numeric"
    description: "Revenue column must contain only numeric values"
  - check_id: "too_empty_row"
    description: "Value cells can not be all empty for a given row"
    applies_to: "all"
  - check_id: "monotonic_progression"
    description: "For value cell with contract level, there should be a progression on adjacent cells' values for increasing contract level."
```

**Run Sanity Checks**:
- For each corrected Landing AI table:
  - Load applicable sanity checks from config
  - Evaluate each check with a LLM call on the table and collect violations
  - Track which checks passed and which failed
  - Store violation details (check_id, description, affected cell ids)

**Screenshot Generation for Failed Tables**:
- For tables violating sanity checks:
  - Use PyMuPDF to get page as pixmap: `page.get_pixmap(dpi=300)`
  - Crop pixmap to table bounding box (with margin for context)
  - If sanity check involves missing/incorrect headers:
    - Expand crop to include previous table on page for context
    - Identify "previous table" as the one immediately before in page order
  - Save screenshot as high-quality image (PNG format)

**LLM Visual Correction**:
- For each table with violations:
  - Prepare LLM prompt with:
    - The screenshot image
    - The current Landing AI HTML table
    - Previous Landing AI table HTML (if header-related violation)
    - List of violated sanity checks with definitions
    - Instructions:
      - "Analyze the screenshot and identify errors in the HTML table"
      - "Correct cell content to match the visual reality"
      - "Only alter layout (add/remove rows/columns, merge/unmerge cells) if you are highly confident"
      - "Provide structured output with corrections"
  - Use vision-capable LLM (Gemini 2.5 Flash recommended)
  - Request structured JSON output with:
    ```json
    {
      "layout_changes_needed": true/false,
      "confidence_in_layout_changes": "high|medium|low",
      "corrections": [
        {
          "row_index": 0,
          "col_index": 0,
          "old_content": "text",
          "new_content": "corrected text",
          "reason": "explanation"
        }
      ],
      "structural_changes": [
        {
          "action": "merge_cells|split_cell|add_row|remove_row",
          "parameters": {},
          "confidence": "high|medium|low"
        }
      ]
    }
    ```

**Apply LLM Corrections**:
- Move current content to `_error_<fieldname>` field (preserving the already corrected content)
- Apply cell content corrections
- If LLM indicates `layout_changes_needed: true` and `confidence_in_layout_changes: "high"`:
  - Apply structural changes cautiously
  - Validate result against sanity checks again
- Otherwise, only apply cell content corrections
- Update the main content field with corrected version

**Verification Loop**:
- After applying LLM corrections, re-run sanity checks
- If still failing and haven't exceeded maximum retry attempts (e.g., 2):
  - Generate new screenshot
  - Call LLM again with additional context about previous failure
- If still failing after max retries:
  - Flag table for manual review
  - Preserve best attempt in main field
  - Keep error history in `_error_*` fields

**Output**: Final corrected Landing AI parsing structure with:
- Main content fields containing best available corrected content
- `_raw_*` fields with original Phase 3 input
- `_error_*` fields with Phase 4 pre-correction content (if corrections were applied)
- Metadata about which sanity checks passed/failed
- Flags for tables requiring manual review

---

## Additional Implementation Notes

**Error Handling**:
- All phases should have try-catch blocks with informative error messages
- If Landing AI parsing completely fails, document should still be processed with PyMuPDF alone
- If PyMuPDF parsing fails, preserve Landing AI output as-is
- LLM API failures should fall back gracefully (preserve previous version)

**Logging and Tracking**:
- Log each phase's execution time
- Track statistics:
  - Number of tables processed
  - Number of matches in Phase 2
  - Number of corrections in Phase 3
  - Number of sanity check violations
  - Number of visual corrections in Phase 4
- Create audit trail showing transformation of each table through pipeline

**Configuration**:
- Make all thresholds configurable:
  - TF-IDF similarity threshold (Phase 2)
  - Word count multiplier (Phase 2)
  - Fuzzy matching threshold (Phase 3 experimental)
  - Maximum LLM retry attempts (Phase 4)
- Allow enabling/disabling experimental fuzzy matching path
- Support different LLM providers (Gemini, OpenAI, etc.)

**Performance Optimization**:
- Process pages in parallel where possible
- Cache TF-IDF vectors if processing multiple similar documents
- Batch LLM API calls where the provider supports it
- Reuse PyMuPDF page objects efficiently (they're expensive to create)

**Data Structures**:
- Use dataclasses or Pydantic models for table structures
- Maintain clear separation between Landing AI format and PyMuPDF format
- Document the schema for the final output structure

**Testing Strategy**:
- Create unit tests for cleaning function with edge cases
- Test TF-IDF matching with synthetic table pairs
- Test LLM prompts with sample tables before full pipeline
- Validate sanity checks work correctly with test cases



---

### Helper

Python Function for Normalized Clipping
This function takes a fitz.Page object and a normalized rectangle (as a tuple of four floats) and returns the clipped fitz.Pixmap.

```Python

import fitz
from typing import Tuple

def get_clipped_pixmap_normalized(
    page: fitz.Page, 
    normalized_rect: Tuple[float, float, float, float],
    dpi: int = 150
) -> fitz.Pixmap:
    """
    Renders a specific area of a PDF page defined by normalized coordinates (0.0 to 1.0).

    Args:
        page: The fitz.Page object to render.
        normalized_rect: A tuple (x0, y0, x1, y1) defining the clip area, 
                         where all values are between 0.0 and 1.0.
        dpi: The desired resolution (dots per inch) for the resulting pixmap.

    Returns:
        A fitz.Pixmap object containing the clipped area.
    """
    
    # Unpack the normalized coordinates
    nx0, ny0, nx1, ny1 = normalized_rect
    
    # Get the page's bounding box in points (the size reference)
    page_rect = page.rect
    
    # Calculate the clip rectangle coordinates in points
    x0 = nx0 * page_rect.width
    y0 = ny0 * page_rect.height
    x1 = nx1 * page_rect.width
    y1 = ny1 * page_rect.height
    
    # Create the PyMuPDF Rect object for clipping
    clip_rect_points = fitz.Rect(x0, y0, x1, y1)
    
    # Generate and return the pixmap
    pix = page.get_pixmap(clip=clip_rect_points, dpi=dpi)
    
    return pix
```