"""Category extraction prompt for single-vendor focused table extraction."""

from pydantic import BaseModel, Field


class CellMetadata(BaseModel):
    """Metadata for a table cell."""
    footnotes: list[str] | None = Field(None, description="Footnote references (e.g., ['*', '(1)']). Omit if empty.")
    conditions: str | None = Field(None, description="Special conditions or modifiers. Omit if none.")


class CategoryTableCell(BaseModel):
    """A single cell in a category-focused table."""
    id: str = Field(..., description="Excel-style cell ID (e.g., 'A1', 'B15', 'C2')")

    # Real cells
    value: str | None = Field(None, description="Cell content. Required for real cells, omit for virtual cells.")
    type: str | None = Field(None, description="'data' for data cells. Omit for dimension cells (headers/labels).")
    colspan: int | None = Field(None, description="Column span. Omit if 1.")
    rowspan: int | None = Field(None, description="Row span. Omit if 1.")
    occupies: list[str] | None = Field(None, description="List of all cell IDs occupied by this span. Omit if no span.")

    # Virtual cells
    ref: str | None = Field(None, description="For virtual cells: ID of the cell that occupies this position. Omit for real cells.")

    # Source tracking (single vendor)
    source_cell_ids: list[str] | None = Field(None, description="Cell IDs from source document. Omit for dimension cells.")
    metadata: CellMetadata | None = Field(None, description="Cell metadata (footnotes, conditions). Omit if empty.")


class CategoryTableRow(BaseModel):
    """A single row in the category table."""
    row_number: int = Field(..., description="1-indexed row number")
    inherited_from_above: list[str | None] = Field(..., description="Array showing rowspan inheritance. Length must equal table_structure.total_columns.")
    cells: list[CategoryTableCell] = Field(..., description="Exactly table_structure.total_columns cells (real + virtual)")


class CategoryTableMetadata(BaseModel):
    """Metadata for a category-focused table."""
    vendor: str = Field(..., description="Vendor name (e.g., 'ProBTP', 'AXA')")
    category: str = Field(..., description="Healthcare category")
    policy_levels: list[str] = Field(..., description="Policy level(s) to extract for this vendor (e.g., ['P2', 'P3', 'P3+'] or just ['Option 1'])")


class TableStructureMetadata(BaseModel):
    """Table structure metadata derived from extraction."""
    template_row: list[str] = Field(..., description="Template showing column structure")
    total_columns: int = Field(..., description="Total number of columns")
    column_labels: list[str] = Field(..., description="Excel-style column labels (e.g., ['A', 'B', 'C'])")


class AmbiguousCase(BaseModel):
    """An ambiguous item that could belong to this category or another."""
    item_description: str = Field(..., description="Description of the benefit/item")
    reasoning: str = Field(..., description="Why this is ambiguous (could be this category or out of scope)")
    candidate_categories: list[str] = Field(..., description="Possible categories this could belong to")
    source_cell_ids: list[str] | None = Field(None, description="Cell IDs from source document")


class CategoryTaxonomy(BaseModel):
    """ASCII art taxonomy tree for the vendor's category organization."""
    ascii_tree: list[str] = Field(..., description="ASCII art folder tree showing category hierarchy as an Array of strings for readability.")
    description: str = Field(..., description="Brief explanation of the taxonomy structure")


class CategoryTable(BaseModel):
    """Single-vendor category-focused table with taxonomy and ambiguous cases."""
    metadata: CategoryTableMetadata = Field(..., description="Table metadata (vendor, category to extract, policy level(s) to extract)")
    taxonomy: CategoryTaxonomy = Field(..., description="Category taxonomy for this vendor")
    table_structure: TableStructureMetadata = Field(..., description="Table structure metadata (template_row, total_columns, column_labels)")
    rows: list[CategoryTableRow] = Field(..., description="Table rows")
    footnotes: list[str] | None = Field(None, description="List of footnote texts from the document. Omit if none.")
    ambiguous_cases: list[AmbiguousCase] | None = Field(None, description="Items that could belong to this or other categories. Omit if none.")
    contextual_information: str | None = Field(None, description="Other conditions, notes, or context from the document. Omit if none.")


def create_category_extraction_prompt(
    vendor: str,
    markdown: str,
    category: str,
    policy_levels: list[str] | None = None,
    other_categories: list[str] | None = None,
    language: str = "French (France)"
) -> str:
    """
    Create a prompt for extracting a single-vendor category-focused table.

    Args:
        vendor: Vendor name (e.g., "ProBTP", "AXA")
        markdown: Full markdown of the contract document
        category: Healthcare category to extract
        policy_levels: Policy level(s) to extract for this vendor
        other_categories: List of other categories (for boundary guidance)
        language: Output language

    Returns:
        Formatted prompt string
    """
    levels_context = ""
    if policy_levels:
        levels_str = "/".join(policy_levels)
        levels_context = f"\n**Policy Level(s) to Extract (ONLY these):** {levels_str}\n"

    boundaries_context = ""
    if other_categories:
        boundaries_context = "\n**Other Categories (DO NOT extract - handled separately):**\n"
        boundaries_context += "\n".join(f"- {cat}" for cat in other_categories)

    prompt = f"""You are an expert insurance analyst specializing in French health insurance (mutuelle) contracts. Your task is to extract a COMPLETE and ACCURATE category-focused table for the from the {vendor} contract.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SOURCE DOCUMENT (Read carefully first!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**{vendor} Insurance Contract (with source cell IDs for bounding boxes):**

<document>
{markdown}
</document>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL: CATEGORY-FOCUSED EXTRACTION WITH TAXONOMY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**PRIMARY OBJECTIVE:**

Extract ALL information covering the **"{category}"** category from the {vendor} contract, including:
1. Main category table with all benefits and coverage levels
2. Footnotes and contextual information (conditions, age limits, caps, etc.)
3. Ambiguous cases that could belong to this category or fall out of scope
4. Category taxonomy (ASCII art folder tree showing how {vendor} organizes this category)

**Critical Success Factors:**
1. ✓ **Completeness**: Extract EVERY benefit in this category
2. ✓ **Accuracy**: Correct coverage values, conditions, and source tracking
3. ✓ **Taxonomy**: Clear ASCII art showing category hierarchy
4. ✓ **Ambiguity Tracking**: Identify edge cases that could belong elsewhere
5. ✓ **Context Preservation**: All footnotes, conditions, and contextual notes
6. ✓ **Structural Integrity**: Correct column counts and cell tracking
7. ✓ **Header Row**: ALWAYS include header row (row 1) even if mostly empty except policy level(s): {policy_levels or "ALL"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLE STRUCTURE (Excel-Style with Spans)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Key Concepts:**

1. **Excel-Style Cell IDs**: Every cell has an ID like "A1", "B15", "C2"
2. **Every Row Has Exactly total_columns Cells**: Real cells + Virtual cells (for spans)
3. **inherited_from_above Array**: Tracks rowspan inheritance (length = total_columns)
4. **Real vs Virtual Cells**:
   - Real cells: Have `value` field, optional spans
   - Virtual cells: Have `ref` field pointing to the cell occupying this position
5. **occupies List**: For spans, lists ALL cell IDs occupied

**Structure Requirements:**
✓ `inherited_from_above.length === table_structure.total_columns`
✓ `cells.length === table_structure.total_columns`
✓ All cell IDs sequential: `table_structure.column_labels[i] + row_number`
✓ Every cell has EITHER value OR ref (never both, never neither)
✓ All `ref` values point to earlier cells
✓ **HEADER ROW IS MANDATORY**: Row 1 must exist with column headers (even if some are empty strings)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROWSPAN AND COLSPAN EXAMPLES (Important!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Example 1: Rowspan Only**

Visual table (3 columns: A, B, C):
┌──────────┬────────┬──────┐
│ Soins    │ Consul │ 100% │  Row 1 (A1 rowspan=2)
│ Courants │  tati  │      │
│          │   on   │      │
├──────────┼────────┼──────┤
│ (cont.)  │ Radio  │ 80%  │  Row 2 (A2 is continuation of A1)
└──────────┴────────┴──────┘

Column layout:
- Column A: "Soins Courants" spans rows 1-2
- Column B: "Consultation" (row 1), "Radio" (row 2)
- Column C: "100%" (row 1), "80%" (row 2)

JSON representation:
{{
  "rows": [
    {{
      "row_number": 1,
      "inherited_from_above": [null, null, null],
      "cells": [
        {{"id": "A1", "value": "Soins Courants", "rowspan": 2, "occupies": ["A1", "A2"]}},
        {{"id": "B1", "value": "Consultation"}},
        {{"id": "C1", "value": "100%", "type": "data"}}
      ]
    }},
    {{
      "row_number": 2,
      "inherited_from_above": ["A1", null, null],
      "cells": [
        {{"id": "A2", "ref": "A1"}},  // Virtual cell pointing to A1
        {{"id": "B2", "value": "Radio"}},
        {{"id": "C2", "value": "80%", "type": "data"}}
      ]
    }}
  ]
}}

**Example 2: Colspan Only**

Visual table (3 columns: A, B, C):
┌───────────────────┬──────┐
│ Header spanning   │ S2   │  Row 1 (A1 colspan=2, spans A1 and B1)
│ two columns       │      │
└───────────────────┴──────┘

Column layout:
- Columns A and B: Merged into "Header spanning two columns"
- Column C: "S2"

JSON representation:
{{
  "rows": [
    {{
      "row_number": 1,
      "inherited_from_above": [null, null, null],
      "cells": [
        {{"id": "A1", "value": "Header spanning two columns", "colspan": 2, "occupies": ["A1", "B1"]}},
        {{"id": "B1", "ref": "A1"}},  // Virtual cell for colspan continuation
        {{"id": "C1", "value": "S2"}}
      ]
    }}
  ]
}}

**Example 3: Both Rowspan AND Colspan**

Visual table (3 columns: A, B, C):
┌──────────────────┬──────┐
│ Complex cell     │      │  Row 1: A1 spans cols A-B (colspan=2)
│ spans 2x2        │ 60%  │         and rows 1-2 (rowspan=2)
│                  │      │  Row 2: C1 spans rows 1-2 (rowspan=2)
├─────────┬────────┼──────┤
│ Cat A   │ Cat Aa │ 35€  │  Row 3: Normal cells
└─────────┴────────┴──────┘

Column layout:
- A1 occupies: A1 (row 1, col A), B1 (row 1, col B), A2 (row 2, col A), B2 (row 2, col B)
- C1 occupies: C1 (row 1, col C), C2 (row 2, col C)
- Row 3: Three independent cells (A3, B3, C3)

JSON representation:
{{
  "rows": [
    {{
      "row_number": 1,
      "inherited_from_above": [null, null, null],
      "cells": [
        {{"id": "A1", "value": "Complex cell spans 2x2", "rowspan": 2, "colspan": 2, "occupies": ["A1", "B1", "A2", "B2"]}},
        {{"id": "B1", "ref": "A1"}},  // Virtual cell (colspan continuation)
        {{"id": "C1", "value": "60%", "type": "data", "rowspan": 2, "occupies": ["C1", "C2"]}}
      ]
    }},
    {{
      "row_number": 2,
      "inherited_from_above": ["A1", "A1", "C1"],
      "cells": [
        {{"id": "A2", "ref": "A1"}},  // Virtual cell (rowspan+colspan continuation)
        {{"id": "B2", "ref": "A1"}},  // Virtual cell (rowspan+colspan continuation)
        {{"id": "C2", "ref": "C1"}}   // Virtual cell (rowspan continuation)
      ]
    }},
    {{
      "row_number": 3,
      "inherited_from_above": [null, null, null],
      "cells": [
        {{"id": "A3", "value": "Cat A"}},
        {{"id": "B3", "value": "Cat Aa"}},
        {{"id": "C3", "value": "35€", "type": "data"}}
      ]
    }}
  ]
}}

**Key Insight for occupies**:
- Rowspan=2, colspan=1: occupies = [current, same_col_next_row]
  Example: A1 with rowspan=2 → occupies ["A1", "A2"]

- Rowspan=1, colspan=2: occupies = [current, next_col_same_row]
  Example: A1 with colspan=2 → occupies ["A1", "B1"]

- Rowspan=2, colspan=2: occupies = [current, next_col_same_row, same_col_next_row, diagonal_cell]
  Example: A1 with rowspan=2, colspan=2 → occupies ["A1", "B1", "A2", "B2"]

- General formula: List ALL cells in the rectangular grid defined by the span
  - For rowspan=R, colspan=C starting at cell XY:
  - occupies = [all cells in the rectangle from XY to (X+C-1)(Y+R-1)]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TAXONOMY EXTRACTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Task**: Create an ASCII art folder tree showing how {vendor} organizes the "{category}" category.

**Example Taxonomy (for reference):**

```
{category}/
├── Sous-catégorie A/
│   ├── Sous-Sous-catégorie Aa
│       ├── Prestation Aa1
│       └── Prestation Aa2
│   ├── Prestation A2
│   └── Prestation A3
├── Sous-catégorie B/
│   ├── Prestation B1
│   └── Prestation B2
└── Sous-catégorie C/
    └── Prestation C1
```

**Guidelines:**
- Use folder notation (/) for categories/subcategories
- Use plain text for specific benefits/prestations
- Reflect the ACTUAL structure from the {vendor} document
- Include all levels of hierarchy present in the source table
- Keep it concise but complete

**Output Field**: `taxonomy.ascii_tree` (list of strings)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AMBIGUOUS CASE TRACKING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Task**: Identify benefits that could belong to "{category}" OR another category.

**When to Flag as Ambiguous:**
- Benefit appears in multiple category tables in the source
- Benefit name suggests it could fit in multiple categories
- Unclear if it's in scope or out of scope for this category
- Edge cases where categorization is debatable

**For Each Ambiguous Case, Provide:**
1. `item_description`: What is the benefit?
2. `reasoning`: Why is it ambiguous?
3. `candidate_categories`: Which categories could it belong to?
4. `source_cell_ids`: Cell IDs from source document

**Example**:
{{
  "item_description": "Ostéopathie (3 séances/an)",
  "reasoning": "Could be classified as 'Soins Courants' OR 'Médecines Douces' depending on contract structure",
  "candidate_categories": ["Soins Courants", "Médecines Douces"],
  "source_cell_ids": ["5-c", "5-d"]
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION PROCESS (Natural Flow)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**STEP 1: Extract Metadata (Understand Context)**

1.1: Identify vendor: "{vendor}"
1.2: Identify category: "{category}"
1.3: Identify policy level: {policy_levels or "ALL"}

**STEP 2: Extract Taxonomy (Understand Structure)**

2.1: Locate the "{category}" section in the {vendor} document
2.2: Identify how {vendor} organizes this category hierarchically
2.3: Create ASCII art folder tree showing:
   - Main category as root
   - Subcategories as folders (/)
   - Specific benefits as items (no /)
2.4: Write brief description of the taxonomy structure

**STEP 3: Extract Main Table (Capture Data)**

3.1: Locate the "{category}" table in the source
3.2: Extract ALL benefit rows with coverage values
3.3: Track source cell IDs for every data cell
3.4: Extract footnote markers (*, (1), (2), etc.)
3.5: Build rows with proper structure:
   - Row 1 (MANDATORY): Header row with column names
   - Remaining rows: Benefit data with correct spans
   - Track inherited_from_above for rowspan inheritance
   - Create virtual cells (with ref) for span continuations

**STEP 4: Derive Table Structure (From Extracted Data)**

4.1: Based on extracted rows, determine:
   - template_row: Column headers from row 1
   - total_columns: Count of columns
   - column_labels: Excel-style labels (A, B, C, ...)

4.2: This structure should naturally emerge from the taxonomy and table content

**STEP 5: Extract Contextual Information**

5.1: Locate all footnotes at bottom of table
5.2: Extract conditions, age limits, caps from inline text
5.3: Combine into `contextual_information` and `footnotes` fields

**STEP 6: Identify Ambiguous Cases**

6.1: Review extracted benefits for potential ambiguity
6.2: Check if any items appear in multiple tables
6.3: Flag edge cases with reasoning
6.4: **IMPORTANT**: If you encounter benefits that clearly belong to OTHER categories, do NOT extract them
   - Mark them as ambiguous ONLY if there's genuine uncertainty
   - If a benefit clearly belongs to a different category (e.g., "Lunettes" in "Soins Courants" extraction when "Optique" category exists), SKIP it entirely
   - The other category extraction will handle it

**STEP 7: Validate Before Returning**

✓ All benefits from "{category}" table extracted
✓ Row counts match source table (plus header row)
✓ All cells have correct IDs
✓ Taxonomy reflects actual document structure
✓ Table structure (template_row, total_columns, column_labels) is consistent
✓ Footnotes captured completely
✓ Header row (row 1) exists


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK PARAMETERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Vendor:** {vendor}
**Category to Extract:** {category}
{levels_context}{boundaries_context}

**CRITICAL LEVEL FILTERING:**
- ONLY extract columns for the specified policy level(s): {policy_levels or "ALL levels"}
- If source table has levels not in the list, SKIP those columns entirely
- This ensures focused extraction without irrelevant data

**CRITICAL CATEGORY BOUNDARIES:**
- ONLY extract benefits that belong to "{category}"
- If a benefit clearly belongs to one of the other categories listed above, SKIP it entirely (do NOT extract, do NOT mark as ambiguous)
- Mark as ambiguous ONLY if there's genuine uncertainty about which category it belongs to
- Examples:
  ✓ Extracting "Soins Courants": Include general consultations, exclude dental/optical care
  ✓ Extracting "Optique": Include glasses/lenses, exclude hearing aids (that's "Audiologie")
  ✓ Extracting "Soins Dentaires": Include dental care, exclude orthodontics if it appears in "Prestations Complémentaires"

**Output Language:** {language}

**Return**: ONLY the JSON object conforming to CategoryTable schema.

**Example Output Structure**:

{{
  "metadata": {{
    "vendor": "{vendor}",
    "category": "{category}",
    "policy_levels": {policy_levels or []}
  }},
  "taxonomy": {{
    "ascii_tree": [
      "{category}/",
      "├── Sous-catégorie A",
      "│   ├── Sous-Sous-catégorie Aa",
      "│   │   ├── Prestation Aa1",
      "│   │   └── Prestation Aa2",
      "│   ├── Prestation A2",
      "│   └── Prestation A3",
      "├── Sous-catégorie B",
      "│   ├── Prestation B1",
      "│   └── Prestation B2",
      "└── Sous-catégorie C",
      "    └── Prestation C1"
    ],
    "description": "The {vendor} contract organizes {category} into X subcategories..."
  }},
  "table_structure": {{
    "template_row": ["Sous-catégorie name", "Sous-Sous-catégorie name", "Prestation name", "Value for Part S.S.", "Value for S3+"],
    "total_columns": 5,
    "column_labels": ["A", "B", "C", "D", "E"]
  }},
  "rows": [
    {{
      "row_number": 1,
      "inherited_from_above": [null, null, null, null, null],
      "cells": [
        {{"id": "A1", "value": ""}},
        {{"id": "B1", "value": ""}},
        {{"id": "C1", "value": ""}},
        {{"id": "D1", "value": "Part S.S."}},
        {{"id": "E1", "value": "S3+"}}
      ]
    }},
    {{
      "row_number": 2,
      "inherited_from_above": [null, null, null, null, null],
      "cells": [
        {{"id": "A2", "value": "Honoraires médicaux", "rowspan": 4, "occupies": ["A2", "A3", "A4", "A5"]}},
        {{"id": "B2", "value": "Consultations", "rowspan": 1, "occupies": ["B2", "B3"]}},
        {{"id": "C2", "value": "Médecin généraliste"}},
        {{"id": "D2", "value": "70%"}},
        {{"id": "E2", "value": "100% BR", "type": "data", "source_cell_ids": ["2-h"]}}
      ]
    }},
    {{
      "row_number": 3,
      "inherited_from_above": ["A2", "B2", null, null, null],
      "cells": [
        {{"id": "A3", "ref": "A2"}},
        {{"id": "B3", "ref": "B2"}},
        {{"id": "C3", "value": "Médecin spécialiste"}},
        {{"id": "D3", "value": "70%"}},
        {{"id": "E3", "value": "100% BR", "type": "data", "source_cell_ids": ["3-i"]}}
      ]
    }},
    {{
        ...
    }},
    {{
        ...
    }},
    ...
  ],
  "footnotes": ["* BR = Base de Remboursement", "(1) Plafond annuel applicable"],
  "contextual_information": "Age limits apply for certain benefits. See footnotes for details.",
  "ambiguous_cases": [
    {{
      "item_description": "Ostéopathie",
      "reasoning": "Could be Soins Courants or Médecines Douces",
      "candidate_categories": ["Soins Courants", "Médecines Douces"],
      "source_cell_ids": ["5-c"]
    }}
  ]
}}

Output the JSON now:"""

    return prompt
