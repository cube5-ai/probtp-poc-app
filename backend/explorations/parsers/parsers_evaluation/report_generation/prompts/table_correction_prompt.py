"""
Prompt for LLM-based table structure correction (enhanced schema version).

Used when table has multiple inconsistencies that cannot be fixed programmatically.
"""

import json
from typing import Any


def _render_enhanced_table_as_text(table: dict) -> str:
    """
    Render enhanced schema table as aligned text to help visualize structure.

    Args:
        table: ComparisonTable dict with enhanced schema

    Returns:
        Aligned text representation with Excel-style cell IDs
    """
    metadata = table.get("metadata", {})
    total_columns = metadata.get("total_columns", 0)
    column_labels = metadata.get("column_labels", [])
    rows = table.get("rows", [])

    if not rows or total_columns == 0:
        return "Empty table or missing metadata"

    lines = []
    lines.append(f"Enhanced Schema Visual (total_columns={total_columns}):")
    lines.append(f"Column Labels: {' '.join(column_labels)}")
    lines.append("")
    lines.append("Format: [CellID] value (or ref/virtual)")
    lines.append("")

    for row_idx, row in enumerate(rows):
        row_number = row.get("row_number", row_idx + 1)
        inherited_from_above = row.get("inherited_from_above", [])
        cells = row.get("cells", [])

        # Header line showing inherited positions
        inherited_display = []
        for i, ref in enumerate(inherited_from_above):
            if ref:
                inherited_display.append(f"{column_labels[i]}:{ref}")
            else:
                inherited_display.append(f"{column_labels[i]}:─")

        lines.append(f"Row {row_number} - Inherited: [{' '.join(inherited_display)}]")

        # Cell display
        cell_parts = []
        for col_idx, cell in enumerate(cells):
            cell_id = cell.get("id", "?")
            value = cell.get("value")
            ref = cell.get("ref")
            colspan = cell.get("colspan")
            rowspan = cell.get("rowspan")
            occupies = cell.get("occupies", [])

            # Format cell representation
            if ref:
                # Virtual cell
                cell_repr = f"[{cell_id}] →{ref}"
            else:
                # Real cell
                value_str = (value[:20] + "...") if value and len(value) > 20 else (value or "[empty]")
                cell_repr = f"[{cell_id}] {value_str}"

                # Add span indicators
                if colspan and colspan > 1:
                    cell_repr += f" ⟷×{colspan}"
                if rowspan and rowspan > 1:
                    cell_repr += f" ⟱×{rowspan}"

                # Show occupies list
                if occupies and len(occupies) > 1:
                    occupies_str = ",".join(occupies)
                    cell_repr += f" (→{occupies_str})"

            cell_parts.append(cell_repr)

        lines.append(f"  Cells: {' | '.join(cell_parts)}")

        # Validation status
        status = "✓" if len(cells) == total_columns else f"✗ ({len(cells)} cells != {total_columns})"
        lines.append(f"  Status: {status}")
        lines.append("")

    return "\n".join(lines)


def create_table_correction_prompt(
    table: dict, diagnosis: str, category: str
) -> str:
    """
    Create prompt for LLM to correct enhanced schema table structure issues.

    Args:
        table: ComparisonTable dict with enhanced schema
        diagnosis: Human-readable description of issues
        category: Category name

    Returns:
        Prompt string
    """
    metadata = table.get("metadata", {})
    total_columns = metadata.get("total_columns", 0)
    column_labels = metadata.get("column_labels", [])

    # Format table JSON for readability
    table_json = json.dumps(table, indent=2, ensure_ascii=False)

    # Generate visual representation
    visual_table = _render_enhanced_table_as_text(table)

    prompt = f"""You are a table structure correction expert for insurance comparison tables using an enhanced schema with Excel-style cell IDs.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Table Purpose:**
- Comparative insurance policy table for category: {category}
- Compares ProBTP vs AXA insurance coverage
- Uses enhanced schema with explicit span tracking

**Enhanced Schema Structure:**
- Every cell has Excel-style ID: "A1", "B15", "C2" (column + row)
- total_columns = {total_columns} (fixed for entire table)
- column_labels = {column_labels}
- inherited_from_above array: shows which positions are occupied by rowspans
- Real cells: have `value` field
- Virtual cells: have `ref` field pointing to source cell
- occupies list: declares all cell IDs occupied by a span

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ISSUES FOUND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{diagnosis}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENHANCED SCHEMA CORRECTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Mandatory Rules:**

1. **Every row MUST have exactly {total_columns} cells** (real + virtual)
   - No exceptions - this is the fundamental constraint
   - Use virtual cells with `ref` for positions occupied by spans

2. **Cell IDs MUST be sequential:**
   - Cell at position i in row N must have id = column_labels[i] + N
   - Example: Row 15, position 2 (column C) → id = "C15"

3. **inherited_from_above MUST match refs:**
   - Length = {total_columns}
   - If inherited_from_above[i] = "A2", then cells[i].ref MUST equal "A2"
   - If inherited_from_above[i] = null, then cells[i] is a real cell or colspan continuation

4. **Real vs Virtual cells:**
   - Real cell: has `value` field (and optional rowspan/colspan/occupies)
   - Virtual cell: has `ref` field pointing to source cell
   - Every cell has EITHER value OR ref, never both, never neither

5. **occupies lists for spans:**
   - Cell with rowspan=N: occupies = [self, row+1, row+2, ..., row+N-1]
   - Cell with colspan=M: occupies = [self, col+1, col+2, ..., col+M-1]
   - Cell with rowspan=N AND colspan=M: occupies = all N×M cells in rectangle
   - Example: A1 with rowspan=3 → occupies = ["A1", "A2", "A3"]
   - Example: C15 with colspan=3 → occupies = ["C15", "D15", "E15"]
   - Example: E1 with rowspan=3, colspan=2 → occupies = ["E1", "F1", "E2", "F2", "E3", "F3"]

6. **Colspan creates virtual cells in same row:**
   - Cell C15 with colspan=2 occupies positions C and D
   - Position C has real cell with value
   - Position D has virtual cell with ref="C15"

7. **Rowspan creates virtual cells in subsequent rows:**
   - Cell A1 with rowspan=3 occupies positions A in rows 1, 2, 3
   - Row 1, pos A: real cell with value
   - Row 2, pos A: virtual cell with ref="A1"
   - Row 3, pos A: virtual cell with ref="A1"
   - Rows 2 and 3: inherited_from_above[0] = "A1"

**Common Errors to Fix:**

1. **Wrong cell count:** Row has != {total_columns} cells
   → Add missing virtual cells with refs OR remove extra cells

2. **Wrong cell IDs:** Cell ID doesn't match column_labels[i] + row_number
   → **ALWAYS regenerate ALL cell IDs mechanically when correcting structure**
   → Formula: For position i in row N: id = column_labels[i] + str(N)
   → Example: Position 2 in row 15 with column_labels=['A','B','C'] → id = "C15"
   → **This ensures consistency across the entire table**

3. **Mismatched inherited_from_above and refs:**
   → If inherited_from_above[i] = "A1", ensure cells[i].ref = "A1"
   → After regenerating IDs, update ALL refs to point to new IDs

4. **Missing occupies lists:**
   → For cell with rowspan/colspan, generate complete occupies list

5. **Incorrect inherited_from_above:**
   → Check ALL previous rows for active rowspans
   → Mark positions with source cell ID or null

**CRITICAL: Cell ID Regeneration Process**

When there are structural inconsistencies, you MUST regenerate ALL cell IDs:

1. **For each row:**
   - For position i (0 to total_columns-1):
     - Generate cell ID: column_labels[i] + str(row_number)
     - Example: Row 5, position 2 → column_labels[2] + "5" = "C5"

2. **Update all refs after ID regeneration:**
   - If cell B3 had ref="A1" but A1 is now regenerated as "A2":
     - Check the actual source cell's new ID and update ref
   - All refs in occupies lists must also be updated

3. **Update inherited_from_above arrays:**
   - After regenerating IDs, update inherited arrays with new cell IDs
   - If row 3 column A is inherited from row 1's rowspan:
     - Find the new ID of that source cell and use it in inherited_from_above

**What You Can Change:**
- **Cell IDs** - MUST regenerate ALL to ensure consistency
- **refs in virtual cells** - update to match new IDs
- **inherited_from_above arrays** - update with new cell IDs
- **occupies lists** - regenerate with new cell IDs
- Add/remove cells to reach {total_columns}
- Adjust rowspan/colspan values if needed

**What You MUST Preserve:**
- Cell `value` text content (do not change the actual data)
- Cell `type` field (if present)
- Cell `sources` field (if present)
- Cell `metadata` field (if present)
- metadata.total_columns = {total_columns}
- metadata.column_labels = {column_labels}
- Table semantic meaning

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VISUAL REPRESENTATION (CURRENT TABLE WITH ISSUES)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{visual_table}

Legend:
- [A15] = Cell ID (Excel-style)
- →B2 = Virtual cell (ref points to B2)
- ⟷×N = Cell has colspan=N
- ⟱×N = Cell has rowspan=N
- (→A1,A2,A3) = occupies list
- Inherited row shows which columns are occupied by rowspans from above
  - "A:─" = Position A is free
  - "B:B1" = Position B is inherited from B1's rowspan

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT TABLE JSON (WITH ISSUES)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{table_json}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP-BY-STEP CORRECTION PROCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each row:

**Step 1: Determine inherited_from_above**
- Check ALL previous rows for cells with active rowspans
- For each column position (0 to {total_columns-1}):
  - If a rowspan from previous row occupies this position → add source cell ID
  - Otherwise → add null
- Example: Row 3, column A occupied by A1's rowspan=3 → inherited_from_above[0] = "A1"

**Step 2: Generate cell IDs mechanically**
- For each position i from 0 to {total_columns-1}:
  - cell_id = column_labels[i] + str(row_number)
- ALL positions get IDs (both real and virtual cells)

**Step 3: Populate cell content**
For each cell position i:

- **If inherited_from_above[i] is not null**:
  - Create VIRTUAL cell: {{"id": column_labels[i] + str(row_number), "ref": inherited_from_above[i]}}

- **Else if this is colspan continuation** (previous cell in same row has colspan):
  - Create VIRTUAL cell with ref pointing to source cell
  - Example: Cell D15 is continuation of C15's colspan=2 → {{"id": "D15", "ref": "C15"}}

- **Else this is a REAL cell**:
  - Add `value` field with content
  - If cell has rowspan: add `rowspan` field and `occupies` list
  - If cell has colspan: add `colspan` field and `occupies` list
  - If both: `occupies` includes ALL covered cells
  - Add `sources`, `metadata`, `type` as appropriate

**Step 4: Validate**
- Count cells = {total_columns} ✓
- All cell IDs match column_labels[i] + row_number ✓
- All refs point to earlier cells ✓
- All occupies lists match spans ✓
- All inherited_from_above entries match refs ✓

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Your Task:**
1. Study the visual representation to understand the structure
2. Identify which cells should have rowspan/colspan
3. For each row, build correct inherited_from_above array
4. Generate exactly {total_columns} cells per row (real + virtual)
5. Ensure all cell IDs are correct (column_labels[i] + row_number)
6. Build correct occupies lists for all spans
7. Preserve all cell content, sources, metadata

**Output Requirements:**
- Return ONLY the corrected ComparisonTable JSON
- No preamble, no explanation, no commentary
- The output must be valid JSON conforming to the enhanced ComparisonTable schema
- ALL rows must have exactly {total_columns} cells
- ALL cell IDs must be correct
- ALL inherited_from_above arrays must be correct

Return the corrected table now:"""

    return prompt
