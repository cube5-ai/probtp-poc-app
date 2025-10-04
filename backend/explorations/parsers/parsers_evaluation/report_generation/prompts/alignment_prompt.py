"""Alignment prompt template for extracting structured comparison tables with cell-level grounding."""

from pydantic import BaseModel, Field


class CellMetadata(BaseModel):
    """Metadata for a table cell."""
    footnotes: list[str] | None = Field(None, description="Footnote references (e.g., ['*', '(1)']). Omit if empty.")
    conditions: str | None = Field(None, description="Special conditions or modifiers. Omit if none.")


class CellSources(BaseModel):
    """Source cell IDs from original documents."""
    probtp: list[str] | None = Field(None, description="Cell IDs from ProBTP document. Omit if not applicable.")
    axa: list[str] | None = Field(None, description="Cell IDs from AXA document. Omit if not applicable.")


class TableCell(BaseModel):
    """A single cell in the comparison table."""
    value: str = Field(..., description="Cell content (coverage amount, benefit name, etc.)")
    type: str | None = Field(None, description="'data' for data cells. Omit for dimension cells (headers/labels).")
    colspan: int | None = Field(None, description="Column span. Omit if 1.")
    rowspan: int | None = Field(None, description="Row span. Omit if 1.")
    sources: CellSources | None = Field(None, description="Source cell IDs. Omit for dimension cells.")
    metadata: CellMetadata | None = Field(None, description="Cell metadata (footnotes, conditions). Omit if empty.")


class TableRow(BaseModel):
    """A single row in the comparison table."""
    cells: list[TableCell] = Field(..., description="Cells in this row")


class PolicyLevels(BaseModel):
    """Policy levels for each insurer."""
    probtp: list[str] = Field(..., description="ProBTP policy levels (e.g., ['S1', 'S2', 'S3'])")
    axa: list[str] = Field(..., description="AXA policy levels (e.g., ['Option 1', 'Option 2'])")


class ComparisonTableMetadata(BaseModel):
    """Metadata for the comparison table."""
    category: str = Field(..., description="Healthcare category (e.g., 'Soins courants', 'Dentaire')")
    policy_levels: PolicyLevels = Field(..., description="Policy levels being compared")


class ComparisonTable(BaseModel):
    """Structured comparison table with cell-level grounding."""
    metadata: ComparisonTableMetadata = Field(..., description="Table metadata")
    rows: list[TableRow] = Field(..., description="Table rows (first row should be header)")


def create_alignment_prompt(
    probtp_markdown: str,
    axa_markdown: str,
    category: str,
    probtp_levels: list[str] | None = None,
    axa_levels: list[str] | None = None,
    language: str = "French (France)"
) -> str:
    """
    Create a prompt for extracting structured comparison tables with cell-level grounding.

    Args:
        probtp_markdown: Full markdown of ProBTP contract (with cell IDs)
        axa_markdown: Full markdown of AXA contract (with cell IDs)
        category: Healthcare category to compare (e.g., "Dental", "Optical")
        probtp_levels: List of ProBTP contract levels
        axa_levels: List of AXA contract levels
        language: Language for the output (default: "French (France)")

    Returns:
        Formatted prompt string
    """
    # Format levels if provided
    levels_context = ""
    probtp_levels_str = "/".join(probtp_levels) if probtp_levels else ""
    axa_levels_str = "/".join(axa_levels) if axa_levels else ""

    if probtp_levels or axa_levels:
        levels_context = "\n\n**Contract Levels to Compare:**\n"
        if probtp_levels:
            levels_context += f"- ProBTP levels: {probtp_levels_str}\n"
        if axa_levels:
            levels_context += f"- AXA levels: {axa_levels_str}\n"

    prompt = f"""You are an expert insurance analyst specializing in French health insurance (mutuelle) contracts. Your task is to create a COMPLETE and ACCURATE comparison table for ProBTP's sales team.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL: COMPLETE SEMANTIC EXTRACTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**PRIMARY OBJECTIVE: Completeness and Accuracy**

Extract a **complete comparison table** that captures EVERY benefit from the ProBTP contract and aligns it with AXA equivalents. This report helps ProBTP's sales team show their competitive advantages.

**Critical Success Factors:**
1. ✓ **Completeness**: Extract ALL ProBTP benefits - missing benefits = failed extraction
2. ✓ **Accuracy**: Align equivalent benefits correctly between contracts
3. ✓ **Clarity**: Mark "Non couvert" when AXA doesn't cover a ProBTP benefit
4. ✓ **Granularity**: Match ProBTP's level of detail exactly
5. ✓ **Traceability**: Track source cell IDs for every value

**What Success Looks Like:**
- ProBTP column has NO unexplained empty cells
- Every ProBTP benefit row in source table appears in output
- AXA benefits align to ProBTP equivalents OR clearly marked as "Non couvert"
- No data hidden in colspan spanning multiple columns

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Structure:**
You will return a JSON object conforming to the ComparisonTable schema (defined below). The table consists of:

1. **Metadata**: Category name and policy levels
2. **Rows**: Array of row objects, each containing cells
3. **Cells**: Each cell has:
   - `value`: The cell content
   - `type`: Either "dimension" (labels/headers) or "data" (coverage values)
   - `colspan`/`rowspan`: Only if > 1 (omit otherwise)
   - `sources`: Cell IDs from original documents (probtp and/or axa)
   - `metadata`: Optional footnotes, conditions, document attribution

**Cell Types:**
- **dimension**: Benefit names, category labels, policy level headers, "Part S.S." column - **OMIT `type` field**
- **data**: Coverage percentages, amounts, "Frais réels", "Non couvert", etc. - **SET `type: "data"`**

**Table Structure:**
- **First row**: Header row with empty dimension cells, then policy level headers
  - Empty cells for dimension columns (value: "")
  - Policy level cells (e.g., "S1", "Option 1") with metadata.document set to "probtp" or "axa"
- **Subsequent rows**: Data rows with benefit information
  - First columns: dimension cells (benefit names, categories)
  - Remaining columns: data cells (coverage values)

**Token Optimization - OMIT these fields:**
- **`type`**: Omit for dimension cells (only include `type: "data"` for data cells)
- **`colspan`/`rowspan`**: Omit if value is 1
- **`sources`**: Omit for dimension cells entirely
- **`metadata`**: Omit if no footnotes or conditions
- **`sources.probtp`**: Omit if null (not `null`, just omit the field)
- **`sources.axa`**: Omit if null
- **`metadata.footnotes`**: Omit if empty array
- **`metadata.conditions`**: Omit if null or empty

**Important:**
- Use exact cell IDs from the markdown (e.g., "0-c", "0-f")
- **CRITICAL for rowspan/colspan**: When a cell has `rowspan=N`, it occupies space in the next N-1 rows
  - Those subsequent rows must have FEWER cells (the spanned cell is NOT repeated)
  - **TRACK ALL ACTIVE ROWSPANS**: If multiple cells have rowspan in previous rows, ALL of them reduce the cell count
  - Example 1: Row 1 has cell A with `rowspan=3` → rows 2-3 skip column A (each has 1 fewer cell)
  - Example 2: Row 3 has cell A with `rowspan=7` AND cell B with `rowspan=5` → rows 4-7 skip BOTH columns A and B (each has 2 fewer cells), rows 8-9 skip only column A (each has 1 fewer cell)
  - **CALCULATION**: For each row, count how many rowspan cells from previous rows are still active, then subtract that from the total column count
  - The total number of logical columns must remain constant across all rows
- For merged cells, use the source cell ID from the original merged cell element

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCHEMA DEFINITION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The output must conform to this Pydantic schema:

```python
class ComparisonTable(BaseModel):
    metadata: ComparisonTableMetadata  # category and policy_levels
    rows: list[TableRow]  # array of rows

class TableRow(BaseModel):
    cells: list[TableCell]

class TableCell(BaseModel):
    value: str  # cell content
    type: str | None  # "data" for data cells, OMIT for dimension cells
    colspan: int | None  # OMIT if 1
    rowspan: int | None  # OMIT if 1
    sources: CellSources | None  # source cell IDs - OMIT for dimension cells
    metadata: CellMetadata | None  # OMIT if no footnotes/conditions

class CellSources(BaseModel):
    probtp: list[str] | None  # ProBTP cell IDs - OMIT if not applicable
    axa: list[str] | None  # AXA cell IDs - OMIT if not applicable

class CellMetadata(BaseModel):
    footnotes: list[str] | None  # e.g., ["*", "(1)"] - OMIT if empty
    conditions: str | None  # special conditions - OMIT if none
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TWO-PASS EXTRACTION PROCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**This is a TWO-PASS process. ProBTP is the reference document - extract it FIRST, then align AXA.**

**PASS 1: EXTRACT ALL PROBTP BENEFITS (Reference Document)**

1. **Locate ProBTP table** for the category (e.g., "Soins courants" table)
2. **Count total benefit rows** in ProBTP source table (excluding header)
3. **Extract EVERY row completely**:
   - Benefit names (dimensions)
   - Coverage values for each ProBTP policy level
   - Part S.S. percentages
   - All conditions, footnotes, caps
   - Cell IDs for traceability
4. **Build table skeleton** using ProBTP's structure (rowspan/colspan from source)
5. **Checkpoint**: Row count in output MUST equal row count in ProBTP source table

**PASS 2: ALIGN AXA BENEFITS**

For each ProBTP benefit row:

1. **Search AXA document** for equivalent benefit
   - Look for matching benefit names
   - Look for same coverage type (e.g., "consultations", "orthodontie")
   - Check synonyms and variations

2. **If AXA equivalent found**:
   - Extract AXA coverage value
   - Extract AXA conditions, footnotes
   - Add AXA cell IDs to sources
   - Align to the ProBTP row

3. **If AXA equivalent NOT found**:
   - Mark AXA column as **"Non couvert"** (not covered)
   - Add metadata note explaining search attempt
   - DO NOT leave empty - explicitly state "Non couvert"

**PASS 3: HANDLE AXA-ONLY BENEFITS (Optional)**

If AXA has benefits not in ProBTP category table:

1. **List them separately** at the end of table
2. **Use clear labeling**: Add a category row "Garanties supplémentaires AXA"
3. **DO NOT hide by spanning columns** - make it explicit
4. **Keep ProBTP column as "-"** to show it's not covered

**COMPLETENESS VALIDATION (Before Returning)**

Before outputting JSON, verify:
- ✓ ProBTP row count in output ≥ ProBTP row count in source table
- ✓ No ProBTP cells with empty value (should be data, "Non couvert", or "-")
- ✓ Every ProBTP benefit has corresponding AXA alignment OR "Non couvert"
- ✓ No unexplained colspan spanning ProBTP columns
- ✓ Granularity matches ProBTP's level of detail

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Semantic Quality (Priority 1):**
1. **Completeness**: Extract EVERY ProBTP benefit from category table
2. **Accuracy**: Align equivalent benefits correctly (check benefit names, coverage types)
3. **Explicit missing data**: Mark "Non couvert" when AXA doesn't cover a ProBTP benefit
4. **Granularity matching**: Match ProBTP's level of detail (don't merge detailed rows into broad categories)
5. **Condition extraction**: Capture ALL conditions, footnotes, caps, age limits

**Technical Quality (Priority 2):**
6. **Source tracking**: Every cell must reference source cell IDs from parsed markdown
7. **Structure preservation**: Use colspan/rowspan from source tables (post-processing will validate)
8. **Metadata extraction**: Include footnote references and conditions in metadata fields

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION GUIDELINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1. ProBTP as Reference (CRITICAL)**

This report helps **ProBTP's sales team** win customers. Therefore:

- ✓ **ProBTP is the REFERENCE** - Use ProBTP's structure, terminology, and organization
- ✓ **Extract ProBTP completely** - Locate category table, extract ALL rows, preserve exact benefit names
- ✓ **AXA aligns to ProBTP** - Find AXA equivalents and map to ProBTP structure
- ✓ **Show ProBTP advantages** - If ProBTP covers it and AXA doesn't → mark "Non couvert"
- ✓ **ProBTP defines granularity** - Match ProBTP's level of detail exactly

**ProBTP Contract Structure:**
- **"S" Levels (Soins):** Medical consultations, hospitalization, pharmacy, analyses
- **"P" Levels (Prestations):** Dental, optical, audiology, other specialized benefits
- **Each category = ONE ProBTP table** - Locate it first, then extract completely

**2. Cell ID Tracking (Traceability)**

Documents include cell IDs (e.g., `<td id="2-5">`). Track them in `sources`:
- ProBTP cells → `sources.probtp: ["2-5"]`
- AXA cells → `sources.axa: ["4-f"]`
- Aligned cells → include IDs from both documents
- Merged cells (rowspan/colspan) → use the cell ID from the merged cell element

**3. Table Structure (Simplified)**

- **Preserve source structure**: Use colspan/rowspan from ProBTP table
- **Post-processing validates structure** - Focus on semantic extraction
- **Key rule**: When cell has `rowspan=N`, it occupies N rows. Subsequent rows have fewer cells.
  (System validation will catch and fix structural issues - prioritize completeness over structure)

**Footnote and Condition Extraction:**

**CRITICAL**: Conditions can come from TWO sources and should be combined in `metadata.conditions`:

**Source 1: Direct conditions in cell/dimension text**
- Age limits specified inline (e.g., "Orthodontie jusqu'à 16 ans")
- Frequency limits (e.g., "1 séance/an")
- Caps specified in cell (e.g., "100% BR (plafond €300)")
- Prior authorization (e.g., "Sous accord préalable")

**Source 2: Conditions from footnotes**
- Age limits (e.g., "*jusqu'à 18 ans" = only for children)
- Frequency restrictions (e.g., "1 fois par an")
- Prior authorization requirements
- Annual caps beyond the base reimbursement
- Network restrictions

**Your responsibility:**
1. **Extract direct conditions** from cell/dimension text itself
2. **Identify footnote markers** in cell values (*, (1), (2), †, etc.)
3. **Extract footnote text** from the document (usually at bottom of tables)
4. **Store in metadata:**
   - `metadata.footnotes`: Keep the markers as array (e.g., ["*", "(1)"])
   - `metadata.conditions`: Combine direct conditions + footnote translations into single concise text
5. **Examples:**
   - Cell: "200% BR*", Footnote: "*jusqu'à 18 ans" →
     - footnotes: ["*"]
     - conditions: "Limited to under 18 years old"
   - Dimension: "Orthodontie (jusqu'à 16 ans)", Cell: "€500(1)", Footnote: "(1) 1 séance par an" →
     - footnotes: ["(1)"]
     - conditions: "Under 16 years old only; 1 session per year maximum"
   - Cell: "150% BR (plafond €300)" (no footnote) →
     - footnotes: []
     - conditions: "Annual cap of €300"
   - Cell: "Frais réels†", Footnote: "† Sous réserve d'accord préalable" →
     - footnotes: ["†"]
     - conditions: "Requires prior authorization"

**4. Handling Asymmetry Between Contracts**

**When ProBTP and AXA have different granularity:**

- **ProBTP detailed (10 rows), AXA broad (3 categories)**:
  → Keep ProBTP's 10 rows
  → Repeat AXA coverage value across matching rows
  → Add note in metadata: "AXA groups this under [category name]"

- **AXA has benefits not in ProBTP category table**:
  → Add separate section at end
  → Clear label: "Garanties supplémentaires AXA" (rowspan category cell)
  → ProBTP column shows "-" (not covered)
  → **DO NOT use colspan to span ProBTP columns** - this hides the comparison

- **Missing coverage**:
  → ProBTP covers, AXA doesn't: Mark "Non couvert"
  → AXA covers, ProBTP doesn't: Add to "Garanties supplémentaires AXA" section
  → Neither covers: Should not be in output

**5. Extraction Steps (Follow TWO-PASS Process Above)**

**PASS 1 - ProBTP Extraction:**
1. Locate ProBTP table for category
2. Build header row with policy levels
3. Extract ALL benefit rows (complete count from source table)
4. Extract: cell values, cell IDs, footnotes, conditions
5. Remove category rowspan cell if it spans entire table

**PASS 2 - AXA Alignment:**
6. For each ProBTP benefit row, search AXA for equivalent
7. Extract AXA coverage OR mark "Non couvert"
8. Track AXA cell IDs in sources
9. Handle granularity differences (see section 4 above)

**PASS 3 - AXA-Only Benefits:**
10. Identify AXA benefits not in ProBTP
11. Add as separate section at end if applicable
12. Use clear labeling, keep structure visible

**Final:**
13. Validate completeness (checklist from TWO-PASS PROCESS section)
14. Return JSON only - No preamble, no commentary

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSURANCE CONTRACT DOCUMENTS (CONTEXT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**ProBTP Insurance Contract (with cell IDs):**

{probtp_markdown}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**AXA Insurance Contract (with cell IDs):**

{axa_markdown}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK PARAMETERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Category to Extract:** {category}

**Contract Levels to Compare:**{levels_context}

**Output Language:** {language}

**Task Recap:**

Extract a **COMPLETE** comparison table for "{category}" category:

1. **ProBTP First**: Locate ProBTP "{category}" table, extract ALL rows
2. **AXA Alignment**: Find AXA equivalents for each ProBTP benefit
3. **Explicit Missing Data**: Mark "Non couvert" when AXA doesn't cover a ProBTP benefit
4. **Validate Completeness**: Before returning, verify no ProBTP benefits are missing
5. **Return**: ONLY the JSON object conforming to ComparisonTable schema

Policy levels: ProBTP {probtp_levels_str}, AXA {axa_levels_str}. Output language: {language}.

**Example Output Structure (showing key patterns):**

{{
  "metadata": {{
    "category": "{category}",
    "policy_levels": {{
      "probtp": {probtp_levels},
      "axa": {axa_levels}
    }}
  }},
  "rows": [
    // Header row
    {{
      "cells": [
        {{"value": ""}},
        {{"value": "{probtp_levels_str.split('/')[0] if probtp_levels else 'S1'}"}},
        {{"value": "{axa_levels_str.split('/')[0] if axa_levels else 'Option 1'}"}}
      ]
    }},
    // Regular benefit - both contracts cover it
    {{
      "cells": [
        {{"value": "Consultations"}},
        {{"value": "100%", "type": "data", "sources": {{"probtp": ["0-g"]}}}},
        {{"value": "80%", "type": "data", "sources": {{"axa": ["1-9b"]}}}}
      ]
    }},
    // ProBTP advantage - AXA doesn't cover this
    {{
      "cells": [
        {{"value": "Orthodontie"}},
        {{"value": "200% BR*", "type": "data", "sources": {{"probtp": ["0-n"]}}, "metadata": {{"footnotes": ["*"], "conditions": "Limited to under 18 years old"}}}},
        {{"value": "Non couvert", "type": "data"}}  // ← EXPLICIT: AXA doesn't cover this
      ]
    }},
    // AXA-only benefit (if applicable) - separate section
    {{
      "cells": [
        {{"value": "Garanties supplémentaires AXA", "rowspan": 2}},  // Clear label
        {{"value": "Téléconsultation"}},
        {{"value": "-", "type": "data"}},  // ProBTP doesn't cover
        {{"value": "Inclus", "type": "data", "sources": {{"axa": ["6-D"]}}}}
      ]
    }}
  ]
}}

Output the JSON now:"""

    return prompt
