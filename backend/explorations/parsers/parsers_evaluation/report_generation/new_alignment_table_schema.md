
# Table Structure Schema with Enhanced Span Support

## Context

When parsing complex tables from documents (HTML, PDFs, etc.) into JSON, LLMs struggle with correctly handling `rowspan` and `colspan` attributes. The main challenges are:

1. **Rowspan tracking**: Remembering which cells from previous rows still occupy space in the current row
2. **Cell counting**: Ensuring every row has the correct number of cell positions
3. **Colspan handling**: Properly accounting for cells that span multiple columns
4. **Missing cells**: LLMs often forget to add cells, especially in complex scenarios like the "Prévention" row where columns were omitted

The goal is to create a schema that provides **cognitive scaffolding** for LLMs, making it mechanically difficult to generate incorrect structures.

## Rationale

### Key Design Decisions

1. **Explicit cell IDs using Excel notation** (A1, B2, C15, etc.)
   - Universally understood
   - Encodes both column and row information
   - Easy to validate

2. **Every row has exactly `total_columns` cells**
   - No ambiguity about structure
   - Simple validation: `cells.length === total_columns`
   - Forces accounting for all positions

3. **Separation of concerns**:
   - `inherited_from_above`: Handles inter-row complexity (rowspans)
   - `cells` array with `colspan` and `occupies`: Handles intra-row complexity
   - Mirrors HTML table structure naturally

4. **Triple redundancy for validation**:
   - `inherited_from_above`: Shows which positions are inherited
   - `rowspan`/`colspan` attributes: Declare spanning intent
   - `occupies` list: Explicitly names all occupied cells
   - `ref` in virtual cells: Points back to source cell

5. **Virtual cells with `ref`**:
   - Positions occupied by spans have explicit placeholder cells
   - All cells (real and virtual) have IDs
   - Creates multiple validation checkpoints

## Schema Definition

```typescript
interface TableStructure {
  metadata: {
    total_columns: number;           // Fixed number of columns in table
    column_labels: string[];          // ["A", "B", "C", ...] for reference
  };
  rows: Row[];
}

interface Row {
  row_number: number;                 // 1-indexed, matches Excel notation
  
  // Array of length total_columns showing rowspan inheritance
  // - Cell ID (e.g., "A1", "B5"): Position inherited from previous row's rowspan
  // - null: Free position available for new cells
  inherited_from_above: (string | null)[];
  
  // Array of exactly total_columns cells (real + virtual)
  cells: Cell[];
}

interface Cell {
  id: string;                         // Excel-style ID (e.g., "A15", "C2")
  
  // Real cells (first occurrence of a span or simple cells)
  value?: string;                     // Cell content
  rowspan?: number;                   // Number of rows this cell spans
  colspan?: number;                   // Number of columns this cell spans
  occupies?: string[];                // IDs of all cells occupied by this span
  
  // Virtual cells (continuations of rowspan/colspan)
  ref?: string;                       // ID of the cell that occupies this position
  
  // Metadata (optional)
  sources?: object;
  metadata?: object;
  type?: string;
}
```

### Validation Rules

```javascript
// Rule 1: Structure consistency
assert(inherited_from_above.length === total_columns);
assert(cells.length === total_columns);

// Rule 2: Cell IDs must be sequential
for (let i = 0; i < cells.length; i++) {
  let expectedId = column_labels[i] + row_number;
  assert(cells[i].id === expectedId);
}

// Rule 3: inherited_from_above consistency
for (let i = 0; i < inherited_from_above.length; i++) {
  if (inherited_from_above[i] !== null) {
    // This position is inherited
    assert(cells[i].ref === inherited_from_above[i]);
    
    // Ref must point to a previous row
    let refRow = extractRowNumber(cells[i].ref);
    assert(refRow < row_number);
  }
}

// Rule 4: Rowspan occupies list
for (let cell of cells) {
  if (cell.rowspan) {
    assert(cell.occupies.length === cell.rowspan);
    assert(cell.occupies[0] === cell.id);
  }
}

// Rule 5: Colspan occupies list and refs
for (let cell of cells) {
  if (cell.colspan) {
    assert(cell.occupies.length === cell.colspan);
    assert(cell.occupies[0] === cell.id);
    
    // Next (colspan-1) cells should ref back to this cell
    let colIndex = getColumnIndex(cell.id);
    for (let j = 1; j < cell.colspan; j++) {
      assert(cells[colIndex + j].ref === cell.id);
    }
  }
}

// Rule 6: Every cell is either real (has value) or virtual (has ref)
for (let cell of cells) {
  assert((cell.value !== undefined) !== (cell.ref !== undefined));
}
```

## Complete Example with Complex Spans

This example shows a table with:
- Simple cells
- A cell with rowspan=3
- A cell with colspan=2
- A cell with both rowspan=3 AND colspan=2

```json
{
  "metadata": {
    "total_columns": 6,
    "column_labels": ["A", "B", "C", "D", "E", "F"]
  },
  "rows": [
    {
      "row_number": 1,
      "inherited_from_above": [null, null, null, null, null, null],
      "cells": [
        {
          "id": "A1",
          "value": "Category A",
          "rowspan": 3,
          "occupies": ["A1", "A2", "A3"]
        },
        {
          "id": "B1",
          "value": "Category B"
        },
        {
          "id": "C1",
          "value": "Header C",
          "colspan": 2,
          "occupies": ["C1", "D1"]
        },
        {
          "id": "D1",
          "ref": "C1"
        },
        {
          "id": "E1",
          "value": "Multi-span Cell",
          "rowspan": 3,
          "colspan": 2,
          "occupies": ["E1", "F1", "E2", "F2", "E3", "F3"]
        },
        {
          "id": "F1",
          "ref": "E1"
        }
      ]
    },
    {
      "row_number": 2,
      "inherited_from_above": ["A1", null, null, null, "E1", "E1"],
      "cells": [
        {
          "id": "A2",
          "ref": "A1"
        },
        {
          "id": "B2",
          "value": "Item 1"
        },
        {
          "id": "C2",
          "value": "Data C2"
        },
        {
          "id": "D2",
          "value": "Data D2"
        },
        {
          "id": "E2",
          "ref": "E1"
        },
        {
          "id": "F2",
          "ref": "E1"
        }
      ]
    },
    {
      "row_number": 3,
      "inherited_from_above": ["A1", null, null, null, "E1", "E1"],
      "cells": [
        {
          "id": "A3",
          "ref": "A1"
        },
        {
          "id": "B3",
          "value": "Item 2"
        },
        {
          "id": "C3",
          "value": "Data C3"
        },
        {
          "id": "D3",
          "value": "Data D3"
        },
        {
          "id": "E3",
          "ref": "E1"
        },
        {
          "id": "F3",
          "ref": "E1"
        }
      ]
    },
    {
      "row_number": 4,
      "inherited_from_above": [null, null, null, null, null, null],
      "cells": [
        {
          "id": "A4",
          "value": "New Section"
        },
        {
          "id": "B4",
          "value": "Item 3"
        },
        {
          "id": "C4",
          "value": "Data C4"
        },
        {
          "id": "D4",
          "value": "Data D4"
        },
        {
          "id": "E4",
          "value": "Data E4"
        },
        {
          "id": "F4",
          "value": "Data F4"
        }
      ]
    }
  ]
}
```

### Visual Representation

```
┌─────────────┬──────────┬──────────┬──────────┬─────────────────────┐
│ Category A  │Category B│ Header C (colspan=2) │ Multi-span Cell     │
│ (rowspan=3) │          ├──────────┼──────────┤ (rowspan=3,         │
│             │  Item 1  │ Data C2  │ Data D2  │  colspan=2)         │
│             ├──────────┼──────────┼──────────┤                     │
│             │  Item 2  │ Data C3  │ Data D3  │                     │
├─────────────┼──────────┼──────────┼──────────┼──────────┬──────────┤
│ New Section │  Item 3  │ Data C4  │ Data D4  │ Data E4  │ Data F4  │
└─────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

## Benefits of This Schema

1. **Prevents missing cells**: Every row must have exactly `total_columns` cells
2. **Clear inheritance tracking**: `inherited_from_above` makes rowspan explicit
3. **Self-validating**: Multiple redundant fields that must agree
4. **Natural for LLMs**: Mirrors HTML table structure (source format)
5. **Debuggable**: Easy to spot inconsistencies visually
6. **Comprehensive**: Handles all span combinations (rowspan only, colspan only, both)

## Generation Guidelines for LLMs

**Step 1**: Determine `inherited_from_above`
- Check all previous cells with active rowspans
- Mark positions with cell IDs or null

**Step 2**: Generate cell IDs mechanically
- Always: `column_label + row_number`
- All positions get IDs (real and virtual)

**Step 3**: Populate cell content
- If `inherited_from_above[i]` is not null → add `ref`
- If free position and first of a span → add `value`, `rowspan`/`colspan`, `occupies`
- If continuation of same-row colspan → add `ref`
- Otherwise → add `value` (simple cell)

**Step 4**: Validate
- Count cells = `total_columns`
- All `ref` values point to valid cells
- All `occupies` lists match actual spans



----------------------------------------
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
    value: str = Field(..., description="Cell content (coverage amount, benefit name, etc.)")
    type: str | None = Field(None, description="'data' for data cells. Omit for dimension cells (headers/labels).")
    colspan: int | None = Field(None, description="Column span. Omit if 1.")
    rowspan: int | None = Field(None, description="Row span. Omit if 1.")
    occupies: list[str] | None = Field(None, description="List of all cell IDs occupied by this span (e.g., ['C15', 'D15', 'E15'] for colspan=3). Omit if no span.")
    ref: str | None = Field(None, description="For virtual cells: ID of the cell that occupies this position (e.g., 'A1' or 'C15'). Omit for real cells.")
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
6. ✓ **Structural Integrity**: Every row must have exactly total_columns cells

**What Success Looks Like:**
- ProBTP column has NO unexplained empty cells
- Every ProBTP benefit row in source table appears in output
- AXA benefits align to ProBTP equivalents OR clearly marked as "Non couvert"
- All rows have correct cell counts accounting for rowspan/colspan
- No missing cells due to span tracking errors

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENHANCED TABLE STRUCTURE WITH SPAN SUPPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Context:**
This schema solves the rowspan/colspan tracking problem by using Excel-style cell IDs and explicit span tracking. It provides cognitive scaffolding to prevent missing cells.

**Key Concepts:**

1. **Excel-Style Cell IDs**: Every cell has an ID like "A1", "B15", "C2"
   - Column letter (A, B, C...) + Row number (1, 2, 3...)
   - Makes position explicit and unambiguous

2. **Every Row Has Exactly total_columns Cells**:
   - Real cells (with value content)
   - Virtual cells (placeholders for spans)
   - No exceptions - this is mandatory

3. **inherited_from_above Array**:
   - Length = total_columns
   - Shows which positions are occupied by rowspans from previous rows
   - Cell ID (e.g., "A1") = this position inherited from that cell's rowspan
   - null = free position available for new cells

4. **Real vs Virtual Cells**:
   - **Real cells**: Have `value` and optional `rowspan`/`colspan`
   - **Virtual cells**: Have `ref` pointing to the cell that occupies them
   - Both types have `id` fields

5. **occupies List**:
   - For cells with rowspan/colspan
   - Lists ALL cell IDs occupied by the span
   - Example: Cell C15 with colspan=3 has occupies=["C15", "D15", "E15"]

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

class TableRow(BaseModel):
    row_number: int  # 1-indexed (matches Excel)
    inherited_from_above: list[str | None]  # Length = total_columns
    cells: list[TableCell]  # Length = total_columns (real + virtual)

class TableCell(BaseModel):
    id: str  # Excel-style: "A1", "B15", "C2"
    value: str  # Cell content
    type: str | None  # "data" for data cells, OMIT for dimension cells
    colspan: int | None  # OMIT if 1
    rowspan: int | None  # OMIT if 1
    occupies: list[str] | None  # Cell IDs occupied by span, OMIT if no span
    ref: str | None  # For virtual cells only, OMIT for real cells
    sources: CellSources | None  # OMIT for dimension cells
    metadata: CellMetadata | None  # OMIT if empty