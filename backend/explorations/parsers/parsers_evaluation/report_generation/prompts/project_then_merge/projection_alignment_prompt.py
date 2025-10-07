"""Projection alignment prompt for projecting AXA values onto ProBTP table structure."""

from pydantic import BaseModel, Field

# Import CategoryTable schema from category_extraction_prompt
from prompts.category_extraction_prompt import CategoryTable


class ProjectionAlignment(BaseModel):
    """Output schema for AXA-to-ProBTP projection alignment."""
    category: str = Field(..., description="Category being aligned")
    axa_projected_table: CategoryTable = Field(..., description="AXA values projected onto ProBTP table structure")
    coverage_gaps: dict[str, list[str]] = Field(..., description="Coverage gaps: {'probtp_only': [...], 'axa_only': [...]}")
    alignment_notes: str | None = Field(None, description="General notes about the alignment process")


def create_projection_alignment_prompt(
    probtp_table: dict,
    axa_table: dict,
    category: str,
    language: str = "French (France)"
) -> str:
    """
    Create a prompt for projecting AXA values onto ProBTP table structure.

    Args:
        probtp_table: CategoryTable dict for ProBTP
        axa_table: CategoryTable dict for AXA
        category: Category name
        language: Output language

    Returns:
        Formatted prompt string
    """
    import json

    probtp_json = json.dumps(probtp_table, ensure_ascii=False, indent=2)
    axa_json = json.dumps(axa_table, ensure_ascii=False, indent=2)

    # Extract AXA levels from the table
    axa_levels = axa_table.get("metadata", {}).get("policy_levels", [])
    axa_levels_str = ", ".join(axa_levels) if axa_levels else "Base Obligatoire"

    prompt = f"""You are an expert insurance analyst specializing in French health insurance (mutuelle) contracts. Your task is to project AXA coverage values onto the ProBTP table structure, essentially swapping the ProBTP level columns with AXA level columns while preserving all table structure.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL: PROJECT AXA VALUES ONTO PROBTP TABLE STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**PRIMARY OBJECTIVE:**

Think of this as **swapping column headers and values**:
- Take the ProBTP table structure (rows, hierarchy, spans, cell IDs)
- Keep dimension columns exactly the same (Catégorie, Sous-catégorie, Prestation, Part S.S.)
- Replace ProBTP level column headers with AXA level headers
- Replace ProBTP coverage values with AXA coverage values (or "Non couvert" if not covered)
- Append new rows at the end for AXA-only benefits not in ProBTP structure

**Visual Analogy:**

ProBTP Table (input):
| Prestation          | Part S.S. | S2      |
|---------------------|-----------|---------|
| Consultation généra | 70%       | 100% BR |

AXA Projected Table (output):
| Prestation          | Part S.S. | Option 1   |
|---------------------|-----------|------------|
| Consultation généra | 70%       | 170% BR-MR |

**Key Points:**
1. Same row structure (same row_number, inherited_from_above, cell IDs)
2. Same dimension columns (Catégorie, Sous-catégorie, Prestation)
3. Same Part S.S. column
4. Different level column headers (AXA instead of ProBTP)
5. Different coverage values (AXA values instead of ProBTP values)
6. Preserve all rowspan/colspan structure exactly

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INPUT TABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Category:** {category}

**ProBTP Table (structure to preserve):**

```json
{probtp_json}
```

**AXA Table (values to project):**

```json
{axa_json}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECTION PROCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**STEP 0: Setup Output Table Structure**

0.1: Copy ProBTP table structure:
   - Copy metadata but update:
     - vendor = "AXA"
     - policy_levels = AXA levels (e.g., ["Base Obligatoire", "Option 1"])
   - Copy taxonomy from ProBTP (same structure)
   - Prepare table_structure (will be filled after rows are built):
     - template_row: Will replace ProBTP level names with AXA level names
     - total_columns and column_labels: Keep same as ProBTP
   - Start with empty rows array

0.2: Initialize coverage_gaps tracking:
   - probtp_only: list of benefits ProBTP covers but AXA doesn't
   - axa_only: list of benefits AXA covers but ProBTP doesn't

**STEP 1: Process ProBTP Rows (Preserve Structure)**

For each row in ProBTP table (starting from row 1 = header):

1.1: Copy row structure exactly:
   - Same row_number
   - Same inherited_from_above array
   - Same cell count (table_structure.total_columns)

1.2: For each cell in the row:

   **If dimension cell (Catégorie, Sous-catégorie, Prestation, Part S.S.):**
   - Copy cell exactly as-is (same id, value, rowspan, colspan, occupies, ref)

   **If ProBTP level data cell:**
   - Keep cell id, rowspan, colspan, occupies, ref structure
   - Find semantically equivalent benefit in AXA table
   - Replace value with AXA coverage value
   - Replace source_cell_ids with AXA source_cell_ids
   - If no AXA equivalent found: value = "Non couvert"
   - Keep type = "data"

**STEP 2: Semantic Mapping (Critical!)**

For each ProBTP benefit (prestation), find AXA equivalent by:

2.1: **Exact match**: Same benefit name → use AXA value directly

2.2: **Semantic match**: Different wording but same coverage
   - "Consultation généraliste" ≈ "Médecin généraliste" ≈ "Visite médecin traitant"
   - "Lunettes" ≈ "Verres optiques"
   - Use your insurance expertise to identify equivalents

2.3: **Granularity differences**:
   - ProBTP detailed (10 specific benefits), AXA broad (3 categories)
     → Repeat AXA category value across all matching ProBTP rows
   - ProBTP broad (1 category), AXA detailed (5 specific benefits)
     → Use most appropriate AXA value or aggregate

2.4: **No match**:
   - value = "Non couvert"
   - Add to coverage_gaps.probtp_only

**STEP 3: Append AXA-Only Benefits**

3.1: Identify benefits in AXA table NOT matched to any ProBTP row

3.2: For each AXA-only benefit:
   - Create new row at end (increment row_number)
   - Build cells:
     - Dimension cells: benefit name, category (if applicable)
       * **Use colspan if needed** to span across dimension columns for category headers
       * Example: Category cell with colspan=3 to span [Catégorie, Sous-catégorie, Prestation]
     - Part S.S. cell: from AXA or empty
     - AXA level cells: AXA coverage values with source_cell_ids
     - ProBTP level cells: ALL "Non couvert" (ProBTP doesn't cover this)
   - Properly track inherited_from_above and occupies lists for any spans
   - Add to coverage_gaps.axa_only

**STEP 4: Validate Structure**

✓ Same number of rows as ProBTP (plus AXA-only rows)
✓ Every row has exactly table_structure.total_columns cells
✓ All cell IDs match pattern: table_structure.column_labels[i] + row_number
✓ All inherited_from_above arrays are correct
✓ All rowspan/colspan preserved from ProBTP structure
✓ Header row (row 1) has AXA level names, not ProBTP
✓ table_structure matches the extracted rows

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORTANT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **Preserve ProBTP Structure Exactly**:
   - Same row counts (before AXA-only additions)
   - Same cell IDs
   - Same rowspan/colspan in dimension columns
   - Same inherited_from_above arrays

2. **Semantic Mapping is Critical**:
   - Focus on benefit NATURE, not exact wording
   - Use insurance domain knowledge
   - Handle terminology variations gracefully

3. **Handle "Non couvert" Correctly**:
   - Only use when benefit is truly not covered by AXA
   - Don't confuse missing data with non-coverage
   - Be conservative: if unsure, map to nearest equivalent

4. **Source Tracking**:
   - Update source_cell_ids to point to AXA document cells
   - Use source_cell_ids from AXA table
   - Omit source_cell_ids for "Non couvert" cells

5. **Column Headers in Row 1**:
   - Must show AXA level names: "{axa_levels_str}"
   - Replace ProBTP level names completely
   - Keep dimension column headers unchanged

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Your Task:**

1. Take ProBTP table structure as scaffold
2. Swap ProBTP level columns with AXA level columns
3. Map ProBTP benefits to AXA equivalents semantically
4. Replace ProBTP values with AXA values (or "Non couvert")
5. Append AXA-only benefits as new rows
6. Track coverage gaps

**Output Language:** {language}

**Return**: ONLY the JSON object conforming to ProjectionAlignment schema.

**Example Output Structure:**

{{
  "category": "{category}",
  "axa_projected_table": {{
    "metadata": {{
      "vendor": "AXA",
      "category": "{category}",
      "policy_levels": ["{axa_levels_str}"]
    }},
    "taxonomy": {{
      "ascii_tree": "Same as ProBTP taxonomy",
      "description": "AXA projected onto ProBTP structure"
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
          {{"id": "E1", "value": "Option 1"}}
        ]
      }},
      {{
        "row_number": 2,
        "inherited_from_above": [null, null, null, null, null],
        "cells": [
          {{"id": "A2", "value": "Soins Courants", "rowspan": 2, "occupies": ["A2", "A3"]}},
          {{"id": "B2", "value": "Consultations"}},
          {{"id": "C2", "value": "Médecin généraliste"}},
          {{"id": "D2", "value": "70%"}},
          {{"id": "E2", "value": "170% BR-MR", "type": "data", "source_cell_ids": ["4-f"]}}
        ]
      }},
      {{
        "row_number": 3,
        "inherited_from_above": ["A2", null, null, null, null],
        "cells": [
          {{"id": "A3", "ref": "A2"}},
          {{"id": "B3", "value": "Consultations"}},
          {{"id": "C3", "value": "Ostéopathie"}},
          {{"id": "D3", "value": ""}},
          {{"id": "E3", "value": "Non couvert", "type": "data"}}
        ]
      }},
      {{
        "row_number": 4,
        "inherited_from_above": [null, null, null, null, null],
        "cells": [
          {{"id": "A4", "value": "Garanties supplémentaires AXA", "colspan": 3, "occupies": ["A4", "B4", "C4"]}},
          {{"id": "B4", "ref": "A4"}},
          {{"id": "C4", "ref": "A4"}},
          {{"id": "D4", "value": ""}},
          {{"id": "E4", "value": "Non couvert", "type": "data"}}
        ]
      }},
      {{
        "row_number": 5,
        "inherited_from_above": [null, null, null, null, null],
        "cells": [
          {{"id": "A5", "value": ""}},
          {{"id": "B5", "value": ""}},
          {{"id": "C5", "value": "Cure thermale"}},
          {{"id": "D5", "value": ""}},
          {{"id": "E5", "value": "Forfait 150€", "type": "data", "source_cell_ids": ["8-k"]}}
        ]
      }}
    ],
    "table_structure": {{
      "template_row": ["Catégorie", "Sous-catégorie", "Prestation", "Part S.S.", "Option 1"],
      "total_columns": 5,
      "column_labels": ["A", "B", "C", "D", "E"]
    }},
    "footnotes": ["Footnotes from AXA table if applicable"],
    "contextual_information": "Context from AXA table if applicable",
    "ambiguous_cases": null
  }},
  "coverage_gaps": {{
    "probtp_only": ["Ostéopathie (row 3)"],
    "axa_only": ["Cure thermale (row 5)"]
  }},
  "alignment_notes": "AXA uses broader categories for consultations. Ostéopathie not covered by AXA. Cure thermale is AXA-only and added with colspan header row."
}}

Output the JSON now:"""

    return prompt
