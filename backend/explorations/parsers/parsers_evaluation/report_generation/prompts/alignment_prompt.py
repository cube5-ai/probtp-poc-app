"""Alignment prompt template for extracting structured comparison tables with enhanced span support."""

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
    """A single cell in the comparison table with Excel-style ID."""
    id: str = Field(..., description="Excel-style cell ID (e.g., 'A1', 'B15', 'C2')")

    # Real cells (first occurrence of a span or simple cells)
    value: str | None = Field(None, description="Cell content (coverage amount, benefit name, etc.). Required for real cells, omit for virtual cells.")
    type: str | None = Field(None, description="'data' for data cells. Omit for dimension cells (headers/labels).")
    colspan: int | None = Field(None, description="Column span. Omit if 1.")
    rowspan: int | None = Field(None, description="Row span. Omit if 1.")
    occupies: list[str] | None = Field(None, description="List of all cell IDs occupied by this span (e.g., ['C15', 'D15', 'E15'] for colspan=3). Omit if no span.")

    # Virtual cells (continuations of rowspan/colspan)
    ref: str | None = Field(None, description="For virtual cells: ID of the cell that occupies this position (e.g., 'A1' or 'C15'). Omit for real cells.")

    # Metadata (optional)
    sources: CellSources | None = Field(None, description="Source cell IDs. Omit for dimension cells.")
    metadata: CellMetadata | None = Field(None, description="Cell metadata (footnotes, conditions). Omit if empty.")


class TableRow(BaseModel):
    """A single row in the comparison table with rowspan tracking."""
    row_number: int = Field(..., description="1-indexed row number matching Excel notation")
    inherited_from_above: list[str | None] = Field(..., description="Array showing rowspan inheritance. Length must equal total_columns. Cell ID (e.g., 'A1') = inherited position, null = free position for new cells.")
    cells: list[TableCell] = Field(..., description="Exactly total_columns cells (real + virtual)")


class PolicyLevels(BaseModel):
    """Policy levels for each insurer."""
    probtp: list[str] = Field(..., description="ProBTP policy levels (e.g., ['S1', 'S2', 'S3'])")
    axa: list[str] = Field(..., description="AXA policy levels (e.g., ['Option 1', 'Option 2'])")


class ComparisonTableMetadata(BaseModel):
    """Metadata for the comparison table."""
    category: str = Field(..., description="Healthcare category (e.g., 'Soins courants', 'Dentaire')")
    policy_levels: PolicyLevels = Field(..., description="Policy levels being compared")
    total_columns: int = Field(..., description="Total number of columns in the table")
    column_labels: list[str] = Field(..., description="Excel-style column labels (e.g., ['A', 'B', 'C', 'D', 'E', 'F'])")


class ComparisonTable(BaseModel):
    """Structured comparison table with enhanced span support and cell-level grounding."""
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
    Create a prompt for extracting structured comparison tables with enhanced span support.

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
6. ✓ **Structural Integrity**: Every row must have exactly total_columns cells (no missing cells!)

**What Success Looks Like:**
- ProBTP column has NO unexplained empty cells
- Every ProBTP benefit row in source table appears in output
- AXA benefits align to ProBTP equivalents OR clearly marked as "Non couvert"
- All rows have correct cell counts (exactly total_columns cells per row)
- No missing cells due to rowspan/colspan tracking errors

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENHANCED TABLE STRUCTURE WITH SPAN SUPPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Problem This Schema Solves:**
LLMs struggle with rowspan/colspan tracking, often forgetting cells (like the "Prévention" row issue where columns were omitted). This schema provides **cognitive scaffolding** to make it mechanically difficult to generate incorrect structures.

**Key Concepts:**

1. **Excel-Style Cell IDs**: Every cell has an ID like "A1", "B15", "C2"
   - Column letter (A, B, C...) + Row number (1, 2, 3...)
   - Makes position explicit and unambiguous
   - Easy to validate and debug

2. **Every Row Has Exactly total_columns Cells** (MANDATORY):
   - Real cells (with value content)
   - Virtual cells (placeholders for spans with ref pointing to source)
   - No exceptions - this prevents the "missing cells" problem
   - Example: If total_columns=6, every row MUST have 6 cells

3. **inherited_from_above Array**:
   - Length = total_columns
   - Shows which positions are occupied by rowspans from previous rows
   - Cell ID (e.g., "A1") = this position inherited from that cell's rowspan
   - null = free position available for new cells
   - This makes rowspan tracking explicit and visible

4. **Real vs Virtual Cells**:
   - **Real cells**: Have `value` field and optional `rowspan`/`colspan`
   - **Virtual cells**: Have `ref` field pointing to the cell that occupies this position
   - Both types have `id` fields (Excel-style)
   - Every cell is either real (has value) OR virtual (has ref), never both

5. **occupies List**:
   - For cells with rowspan/colspan
   - Lists ALL cell IDs occupied by the span
   - Example: Cell C15 with colspan=3 occupies ["C15", "D15", "E15"]
   - Example: Cell A1 with rowspan=3 occupies ["A1", "A2", "A3"]
   - Example: Cell E1 with rowspan=3 AND colspan=2 occupies ["E1", "F1", "E2", "F2", "E3", "F3"]

**Structure Benefits:**
- ✅ Prevents missing cells (must have exactly total_columns)
- ✅ Makes rowspan tracking explicit (inherited_from_above array)
- ✅ Self-validating (multiple redundant fields must agree)
- ✅ Mirrors HTML table structure naturally
- ✅ Easy to debug (scan for inconsistencies visually)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCHEMA DEFINITION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
class ComparisonTable(BaseModel):
    metadata: ComparisonTableMetadata  # category, policy_levels, total_columns, column_labels
    rows: list[TableRow]

class ComparisonTableMetadata(BaseModel):
    category: str  # e.g., "Soins courants"
    policy_levels: PolicyLevels
    total_columns: int  # Fixed number of columns in table
    column_labels: list[str]  # ["A", "B", "C", "D", "E", "F"]

class TableRow(BaseModel):
    row_number: int  # 1-indexed (matches Excel)
    inherited_from_above: list[str | None]  # Length = total_columns
    cells: list[TableCell]  # Length = total_columns (real + virtual)

class TableCell(BaseModel):
    id: str  # Excel-style: "A1", "B15", "C2"

    # Real cells (has value)
    value: str | None  # Cell content (required for real cells)
    type: str | None  # "data" for data cells, OMIT for dimension cells
    colspan: int | None  # OMIT if 1
    rowspan: int | None  # OMIT if 1
    occupies: list[str] | None  # Cell IDs occupied by span, OMIT if no span
    sources: CellSources | None  # OMIT for dimension cells
    metadata: CellMetadata | None  # OMIT if empty

    # Virtual cells (has ref)
    ref: str | None  # For virtual cells only: ID of source cell, OMIT for real cells
```

**Token Optimization - OMIT these fields:**
- `type`: Omit for dimension cells (only include for data cells)
- `colspan`/`rowspan`: Omit if value is 1
- `occupies`: Omit if no span (colspan=1 and rowspan=1)
- `ref`: Omit for real cells (only for virtual cells)
- `sources`: Omit for dimension cells entirely
- `metadata`: Omit if no footnotes or conditions
- `sources.probtp`/`sources.axa`: Omit if not applicable

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP-BY-STEP GENERATION PROCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**STEP 0: Determine Table Structure**

Before extracting any content, analyze the ProBTP table to determine:

1. **Count total_columns**: Look at the ProBTP table header
   - Count dimension columns (benefit categories, names, etc.)
   - Count "Part S.S.*" column (if present)
   - Count policy level columns (S1, S2, S3, P3+, etc.)
   - Count AXA policy level columns
   - **CRITICAL**: Think carefully about the grid structure needed
   - Example: If you have 3 dimension columns, 1 Part SS column, 1 ProBTP level column, 1 AXA level column → total_columns = 6

2. **Generate column_labels**: Create Excel-style labels
   - ["A", "B", "C", "D", "E", "F"] for 6 columns
   - ["A", "B", "C", "D", "E"] for 5 columns
   - etc.

3. **Double-check your column count**: This is critical for the entire structure!

**STEP 1: Two-Pass Semantic Extraction** (ProBTP First!)

**PASS 1 - Extract ALL ProBTP Benefits:**
1. Locate ProBTP table for the category
2. Extract EVERY benefit row (complete count from source table)
3. Use ProBTP's structure, terminology, and organization
4. Extract: benefit names, coverage values, Part S.S., cell IDs, footnotes, conditions

**PASS 2 - Align AXA Benefits:**
5. For each ProBTP benefit row, search AXA for equivalent
6. Extract AXA coverage OR mark "Non couvert"
7. Track AXA cell IDs in sources
8. Handle granularity differences (detailed ProBTP vs broad AXA)

**PASS 3 - AXA-Only Benefits (if applicable):**
9. Identify AXA benefits not in ProBTP category table
10. Add as separate section at end with clear labeling ("Garanties supplémentaires AXA")
11. Use category rowspan cell for label, ProBTP columns show "-"

**STEP 2: Generate Table Structure Row by Row**

For each row (starting with row_number=1 for header):

**2.1: Determine inherited_from_above**
- Check ALL previous rows for cells with active rowspans
- For each column position (0 to total_columns-1):
  - If a rowspan from previous row occupies this position → add source cell ID (e.g., "A1")
  - Otherwise → add null
- Example: Row 2 with column A occupied by A1's rowspan=3 → inherited_from_above = ["A1", null, null, null, null, null]

**2.2: Generate cell IDs mechanically**
- For each position i from 0 to total_columns-1:
  - cell_id = column_labels[i] + str(row_number)
  - Example: Row 15, position 2 (column C) → id = "C15"
- ALL positions get IDs (both real and virtual cells)

**2.3: Populate cell content**
For each cell position i:

- **If inherited_from_above[i] is not null**:
  - This position is occupied by a rowspan from above
  - Create VIRTUAL cell: `{{"id": "column_labels[i] + row_number", "ref": "inherited_from_above[i]"}}`

- **Else if this is a colspan continuation** (previous cell in same row has colspan):
  - Create VIRTUAL cell with ref pointing to source cell
  - Example: Cell D15 is continuation of C15's colspan=2 → `{{"id": "D15", "ref": "C15"}}`

- **Else this is a REAL cell**:
  - Add `value` field with content (use empty string `""` for visually empty cells, NEVER use null/None)
  - **IMPORTANT**: Empty-looking cells in merged headers should use `value=""`, not `value=null`
  - If cell has rowspan: add `rowspan` field and `occupies` list
  - If cell has colspan: add `colspan` field and `occupies` list
  - If both: `occupies` includes ALL covered cells (current row + future rows)
  - Add `sources`, `metadata`, `type` as appropriate

**2.4: Build occupies list** (for cells with spans)

For rowspan only:
- `occupies = [cell_id, same_col_next_row, same_col_next_row+1, ...]`
- Example: A1 with rowspan=3 → occupies = ["A1", "A2", "A3"]

For colspan only:
- `occupies = [cell_id, next_col_same_row, next_col+1_same_row, ...]`
- Example: C15 with colspan=3 → occupies = ["C15", "D15", "E15"]

For BOTH rowspan and colspan:
- `occupies = [all cells in the rectangle]`
- Example: E1 with rowspan=3, colspan=2 → occupies = ["E1", "F1", "E2", "F2", "E3", "F3"]

**STEP 3: Validate Before Returning**

Check these MANDATORY rules:

✓ `inherited_from_above.length === total_columns`
✓ `cells.length === total_columns`
✓ All cell IDs are sequential: `column_labels[i] + row_number`
✓ **Every cell has EITHER value OR ref** (never both, never neither, never null)
  - Real cells: `{{"id": "A1", "value": "text"}}` or `{{"id": "B5", "value": ""}}`
  - Virtual cells: `{{"id": "C2", "ref": "C1"}}`
  - NEVER: `{{"id": "D1", "value": null}}` - use `"value": ""` instead
✓ All ref values point to earlier cells (earlier row OR same row but earlier column)
✓ All occupies lists match the actual rowspan/colspan values
✓ No ProBTP cells with empty value (should be data, "Non couvert", or "-")

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Semantic Quality (Priority 1):**
1. **Completeness**: Extract EVERY ProBTP benefit from category table
2. **Accuracy**: Align equivalent benefits correctly (check benefit names, coverage types)
3. **Explicit missing data**: Mark "Non couvert" when AXA doesn't cover a ProBTP benefit
4. **Granularity matching**: Match ProBTP's level of detail (don't merge detailed rows)
5. **Condition extraction**: Capture ALL conditions, footnotes, caps, age limits

**Structural Quality (Priority 2):**
6. **Correct column count**: Think carefully about total_columns before starting
7. **Every row has exactly total_columns cells**: Real + virtual cells
8. **inherited_from_above tracking**: Accurately track rowspans from previous rows
9. **Source tracking**: Every real cell must reference source cell IDs from parsed markdown

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION GUIDELINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1. ProBTP as Reference (CRITICAL)**

This report helps **ProBTP's sales team** win customers by understanding the differences between ProBTP and AXA. Therefore:

- ✓ **ProBTP is the REFERENCE** - Use ProBTP's structure, terminology, organization
- ✓ **Extract ProBTP completely** - Locate category table, extract ALL rows, preserve exact benefit names
- ✓ **AXA aligns to ProBTP** - Find AXA equivalents and map to ProBTP structure
- ✓ **Show ProBTP advantages** - If ProBTP covers it and AXA doesn't → mark "Non couvert"
- ✓ **Show AXA advantages** - If AXA covers it and ProBTP doesn't → mark "Non couvert"
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

**3. Handling Asymmetry Between Contracts**

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

**4. Footnote and Condition Extraction**

**CRITICAL**: Conditions come from TWO sources:

**Source 1: Direct conditions in cell/dimension text**
- Age limits inline (e.g., "Orthodontie jusqu'à 16 ans")
- Frequency limits (e.g., "1 séance/an")
- Caps in cell (e.g., "100% BR (plafond €300)")

**Source 2: Footnotes**
- Identify markers (*, (1), (2), †)
- Find footnote text at bottom of table
- Translate to conditions

**Combine both sources** in `metadata.conditions`:
- Keep markers in `metadata.footnotes` array
- Store combined text in `metadata.conditions`

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

**STEP 0**: Determine total_columns and column_labels (think about grid structure!)
**STEP 1**: ProBTP First - Extract ALL benefits, then align AXA
**STEP 2**: Generate rows with proper structure:
  - inherited_from_above (track rowspans)
  - Exactly total_columns cells (real + virtual)
  - Excel-style cell IDs (A1, B15, C2)
  - occupies lists for spans
**STEP 3**: Validate before returning (check rules above)

**Return**: ONLY the JSON object conforming to ComparisonTable schema.

**Example output structure** (showing enhanced schema):

{{
  "metadata": {{
    "category": "{category}",
    "policy_levels": {{
      "probtp": {probtp_levels},
      "axa": {axa_levels}
    }},
    "total_columns": 6,  // Example: 3 dimension + 1 Part SS + 1 ProBTP + 1 AXA
    "column_labels": ["A", "B", "C", "D", "E", "F"]
  }},
  "rows": [
    {{
      "row_number": 1,
      "inherited_from_above": [null, null, null, null, null, null],
      "cells": [
        {{"id": "A1", "value": ""}},
        {{"id": "B1", "value": "", "colspan": 2, "occupies": ["B1", "C1"]}},
        {{"id": "C1", "ref": "B1"}},
        {{"id": "D1", "value": "Part S.S.*"}},
        {{"id": "E1", "value": "S2"}},
        {{"id": "F1", "value": "Base Obligatoire"}}
      ]
    }},
    {{
      "row_number": 2,
      "inherited_from_above": [null, null, null, null, null, null],
      "cells": [
        {{"id": "A2", "value": "Soins courants", "rowspan": 3, "occupies": ["A2", "A3", "A4"]}},
        {{"id": "B2", "value": "Consultations"}},
        {{"id": "C2", "value": "70%"}},
        {{"id": "D2", "value": ""}},
        {{"id": "E2", "value": "100%", "type": "data", "sources": {{"probtp": ["2-h"]}}}},
        {{"id": "F2", "value": "170% BR-MR", "type": "data", "sources": {{"axa": ["4-f"]}}}}
      ]
    }},
    {{
      "row_number": 3,
      "inherited_from_above": ["A2", null, null, null, null, null],  // A2's rowspan still active
      "cells": [
        {{"id": "A3", "ref": "A2"}},  // Virtual cell for A2's rowspan
        {{"id": "B3", "value": "Radiologie"}},
        {{"id": "C3", "value": "70%"}},
        {{"id": "D3", "value": ""}},
        {{"id": "E3", "value": "100%", "type": "data"}},
        {{"id": "F3", "value": "Non couvert", "type": "data"}}  // ProBTP advantage!
      ]
    }}
  ]
}}

Output the JSON now:"""

    return prompt
