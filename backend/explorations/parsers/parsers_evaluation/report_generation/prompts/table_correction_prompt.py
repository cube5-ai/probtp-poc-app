"""
Prompt for LLM-based table structure correction.

Used when table has multiple inconsistencies that cannot be fixed programmatically.
"""

import json
from typing import Any


def _render_table_as_aligned_text(table: dict, expected_columns: int) -> str:
    """
    Render table as aligned text to help visualize structure issues.

    Args:
        table: ComparisonTable dict
        expected_columns: Target logical column count

    Returns:
        Aligned text representation
    """
    rows = table.get("rows", [])
    if not rows:
        return "Empty table"

    lines = []
    lines.append(
        f"Visual representation (target: {expected_columns} logical columns per row):"
    )
    lines.append("")

    # Track active rowspans: list of (starting_row_idx, starting_col_position, colspan, rows_remaining)
    active_rowspans: list[tuple[int, int, int, int]] = []

    for row_idx, row in enumerate(rows):
        cells = row.get("cells", [])

        # Build row representation
        row_parts = []
        col_position = 0  # Tracks current logical column position
        cell_idx = 0
        new_rowspans = []  # Collect new rowspans from this row

        while col_position < expected_columns:
            # Check if this column position is occupied by an active rowspan
            occupied_by_rowspan = False
            for (start_row, start_col, span_cols, remaining) in active_rowspans:
                if start_col <= col_position < start_col + span_cols:
                    occupied_by_rowspan = True
                    break

            if occupied_by_rowspan:
                # This column is spanned from above
                row_parts.append("↓↓↓")
                col_position += 1
            elif cell_idx < len(cells):
                # Place the next cell
                cell = cells[cell_idx]
                value = cell.get("value", "")[:30]  # Truncate long values
                colspan = cell.get("colspan", 1) or 1
                rowspan = cell.get("rowspan", 1) or 1

                # Format cell with span indicators
                cell_text = value if value else "[empty]"
                if colspan > 1:
                    cell_text += f" [⟷×{colspan}]"
                if rowspan > 1:
                    cell_text += f" [⟱×{rowspan}]"

                row_parts.append(cell_text)

                # For colspan > 1, add placeholders for the extra columns
                for _ in range(1, colspan):
                    row_parts.append("⟷⟷⟷")

                # Track this cell's rowspan for future rows
                if rowspan > 1:
                    new_rowspans.append(
                        (row_idx, col_position, colspan, rowspan - 1)
                    )

                col_position += colspan
                cell_idx += 1
            else:
                # No more cells, but column is expected
                row_parts.append("[MISSING]")
                col_position += 1

        # Calculate actual logical columns
        actual_columns_from_cells = sum(
            cell.get("colspan", 1) or 1 for cell in cells
        )
        # Count columns from active rowspans (all rowspans that were started in previous rows)
        columns_from_rowspans = sum(
            span_cols
            for (start_row, start_col, span_cols, remaining) in active_rowspans
        )
        actual_columns = actual_columns_from_cells + columns_from_rowspans

        status = "✓" if actual_columns == expected_columns else "✗"
        lines.append(
            f"Row {row_idx + 1:2d} ({len(cells)} cells, {actual_columns} cols) {status}: {' | '.join(row_parts)}"
        )

        # Update active rowspans for next row
        # 1. Decrement existing rowspans
        # 2. Add new rowspans from current row
        updated_rowspans = []
        for (start_row, start_col, span_cols, remaining) in active_rowspans:
            new_remaining = remaining - 1
            if new_remaining > 0:
                updated_rowspans.append((start_row, start_col, span_cols, new_remaining))

        # Add new rowspans from this row (they will be active starting next row)
        updated_rowspans.extend(new_rowspans)
        active_rowspans = updated_rowspans

    return "\n".join(lines)


def create_table_correction_prompt(
    table: dict, diagnosis: str, category: str, expected_columns: int
) -> str:
    """
    Create prompt for LLM to correct table structure issues.

    Args:
        table: ComparisonTable dict with inconsistencies
        diagnosis: Human-readable description of issues
        category: Category name
        expected_columns: Target logical column count

    Returns:
        Prompt string
    """
    # Format table JSON for readability
    table_json = json.dumps(table, indent=2, ensure_ascii=False)

    # Generate visual representation
    visual_table = _render_table_as_aligned_text(table, expected_columns)

    prompt = f"""You are a table structure correction expert. Your task is to fix rowspan/colspan issues in an insurance comparison table.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Table Purpose:**
- This is a comparative insurance policy table for category: {category}
- It compares ProBTP vs AXA insurance coverage
- Columns represent: dimension labels, policy levels from both insurers

**Target Structure:**
- Each row must occupy exactly **{expected_columns} logical columns**
- Row 1 is the header row (policy level names)
- Subsequent rows contain benefit comparisons

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ISSUES FOUND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{diagnosis}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY RULES FOR CORRECTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Logical Column Calculation:**
1. Each cell occupies `colspan` logical columns (default: 1)
2. Cells with `rowspan=N` occupy columns in the next N-1 rows
3. Those subsequent rows must have FEWER cells (they skip the spanned columns)

**Example of correct rowspan usage:**
```
Row 1: [A, B, C, D, E] → 5 columns
Row 2: [F (rowspan=3), G, H, I, J] → 5 columns (F will span down)
Row 3: [K, L, M, N] → 4 cells + 1 occupied by F's rowspan = 5 columns ✓
Row 4: [O, P, Q, R] → 4 cells + 1 occupied by F's rowspan = 5 columns ✓
Row 5: [S, T, U, V, W] → 5 columns (F's rowspan ended)
```

**CRITICAL - Track ALL Active Rowspans:**
- If row 3 has cell A with `rowspan=7` AND cell B with `rowspan=5`
- Then rows 4-7 must skip BOTH columns A and B (2 fewer cells)
- And rows 8-9 must skip only column A (1 fewer cell)

**Common Mistakes to Fix:**
1. **Too many cells in nested rowspan rows** - When a cell has rowspan, subsequent rows should have fewer cells
2. **Incorrect rowspan values** - Rowspan may be too large or too small
3. **Missing cells** - Some rows may be missing cells needed to reach {expected_columns} columns
4. **Incorrect colspan** - Colspan values may be wrong, especially in header row

**What You Can Change:**
- Add/remove cells from rows
- Adjust `rowspan` values (or remove field if value is 1)
- Adjust `colspan` values (or remove field if value is 1)
- Add empty cells where needed: `{{"value": ""}}`

**What You MUST Preserve:**
- Cell `value` text (do not change the content)
- Cell `type` field (if present)
- Cell `sources` field (if present)
- Cell `metadata` field (if present)
- Table metadata (category, policy_levels)
- Overall table structure and meaning

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VISUAL REPRESENTATION (CURRENT TABLE WITH ISSUES)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{visual_table}

Legend:
- ↓↓↓ = Column occupied by rowspan from previous row
- ⟷⟷⟷ = Column occupied by colspan from same row
- [⟷×N] = Cell has colspan=N (occupies N columns)
- [⟱×N] = Cell has rowspan=N (spans N rows)
- [empty] = Cell with no value
- [MISSING] = Expected cell is missing
- ✓ = Row has correct column count
- ✗ = Row has incorrect column count

**Semantic Analysis Guidance:**
When correcting the table, analyze the MEANING and semantic relationships:

1. **Header row (row 1):** Should contain policy level names or labels
   - Check if column labels align with data in subsequent rows
   - Data cells in lower rows should correspond to their header column

2. **Data alignment:** Each data cell should be under the correct policy level
   - ProBTP data should be under ProBTP policy levels
   - AXA data should be under AXA policy levels
   - Verify cell `sources` field matches the column (probtp vs axa)

3. **Dimension hierarchy:** Look for hierarchical benefit labels
   - Parent categories (e.g., "Hospitalisation") often have large rowspan
   - Sub-categories (e.g., "Honoraires", "Chambre particulière") are nested
   - Ensure hierarchy makes semantic sense

4. **Pattern consistency:** Similar benefits should have similar structures
   - If one benefit row has 3 dimension columns + 2 data columns, others likely do too
   - Look for patterns in how rows are structured

**Common semantic errors to fix:**
- Data cell appears under wrong policy level (check sources field)
- Rowspan creates misalignment between labels and data
- Colspan in header doesn't match the number of related columns below
- Dimension labels and data values don't correspond

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT TABLE JSON (WITH ISSUES)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{table_json}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Your Task:**
1. **Study the visual representation** to identify patterns and inconsistencies
2. **Analyze semantic relationships** between headers, dimension labels, and data cells
3. **Verify column correspondence** - ensure data cells align with correct policy levels using `sources` field
4. **Fix rowspan/colspan values** so ALL rows occupy exactly {expected_columns} logical columns
5. **Maintain semantic meaning** - the corrected table must preserve the insurance benefit comparison structure

**Output Requirements:**
- Return ONLY the corrected ComparisonTable JSON
- No preamble, no explanation, no commentary
- The output must be valid JSON conforming to the ComparisonTable schema
- All rows must have exactly {expected_columns} logical columns when accounting for colspan and active rowspans

**Verification Before Output:**
For each row, verify:
- Count cells in row
- Multiply each cell's colspan (default 1)
- Add columns occupied by active rowspans from previous rows
- Total must equal {expected_columns}

Return the corrected table now:"""

    return prompt
