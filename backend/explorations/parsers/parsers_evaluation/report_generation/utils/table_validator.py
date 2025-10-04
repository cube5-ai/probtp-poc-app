"""
Table structure validation and correction utilities.

Validates that comparison tables have consistent logical column counts across all rows,
accounting for both colspan and rowspan. Provides automatic correction for common issues.
"""

import json
from enum import Enum
from typing import Any


class ConsistencyState(Enum):
    """Table consistency states."""

    CONSISTENT = "CONSISTENT"
    HEADER_MISSING_COLUMNS = "HEADER_MISSING_COLUMNS"
    MULTIPLE_INCONSISTENCIES = "MULTIPLE_INCONSISTENCIES"


def calculate_logical_columns_per_row(table: dict) -> list[int]:
    """
    Calculate the logical column count for each row.

    Logical columns = actual columns occupied by cells + columns occupied by active rowspans.

    Args:
        table: ComparisonTable dict

    Returns:
        List of logical column counts, one per row
    """
    rows = table.get("rows", [])
    if not rows:
        return []

    logical_columns = []
    active_rowspans = (
        []
    )  # List of (row_idx_started, columns_occupied, remaining_rows)

    for row_idx, row in enumerate(rows):
        cells = row.get("cells", [])

        # Calculate columns from current row's cells
        current_row_columns = 0
        new_rowspans = []

        for cell in cells:
            colspan = cell.get("colspan", 1) or 1
            rowspan = cell.get("rowspan", 1) or 1

            current_row_columns += colspan

            # Track if this cell spans multiple rows
            if rowspan > 1:
                new_rowspans.append((row_idx, colspan, rowspan - 1))

        # Add columns occupied by active rowspans from previous rows
        columns_from_active_rowspans = sum(
            cols for (_, cols, _) in active_rowspans if row_idx > 0
        )

        total_logical_columns = current_row_columns + columns_from_active_rowspans
        logical_columns.append(total_logical_columns)

        # Update active rowspans for next iteration
        # Decrement remaining rows and filter out completed spans
        active_rowspans = [
            (start_row, cols, remaining - 1)
            for (start_row, cols, remaining) in active_rowspans
            if remaining > 1
        ]

        # Add new rowspans from current row
        active_rowspans.extend(new_rowspans)

    return logical_columns


def remove_category_column(table: dict) -> tuple[dict, bool]:
    """
    Remove category column if present.

    Detects if row 2, cell 1 has rowspan = (total_rows - 1), indicating a category label
    that spans all data rows. If found, removes this cell and adjusts row 1 accordingly.

    Args:
        table: ComparisonTable dict

    Returns:
        Tuple of (modified_table, was_removed)
    """
    rows = table.get("rows", [])
    if len(rows) < 2:
        return table, False

    row1 = rows[0]
    row2 = rows[1]

    row1_cells = row1.get("cells", [])
    row2_cells = row2.get("cells", [])

    if not row1_cells or not row2_cells:
        return table, False

    # Check if row2, cell1 has rowspan = total_rows - 1
    category_cell = row2_cells[0]
    rowspan = category_cell.get("rowspan", 1) or 1
    expected_rowspan = len(rows) - 1

    if rowspan != expected_rowspan:
        # Not a category column
        return table, False

    # Category column detected - remove it
    # Remove cell from row 2
    row2_cells_new = row2_cells[1:]

    # Adjust row 1
    row1_cell = row1_cells[0]
    row1_colspan = row1_cell.get("colspan", 1) or 1

    if row1_colspan > 1:
        # Reduce colspan by 1
        row1_cell_new = {**row1_cell, "colspan": row1_colspan - 1}
        if row1_cell_new["colspan"] == 1:
            # Remove colspan field if now 1
            row1_cell_new = {
                k: v for k, v in row1_cell_new.items() if k != "colspan"
            }
        row1_cells_new = [row1_cell_new] + row1_cells[1:]
    else:
        # Remove first cell from row 1
        row1_cells_new = row1_cells[1:]

        # Edge case: if removed cell had content, log warning
        if row1_cell.get("value", "").strip():
            print(
                f"  ⚠ Warning: Removed header cell had content: '{row1_cell.get('value')}'"
            )

    # Create modified table
    modified_table = {**table}
    modified_rows = []

    for idx, row in enumerate(rows):
        if idx == 0:
            modified_rows.append({"cells": row1_cells_new})
        elif idx == 1:
            modified_rows.append({"cells": row2_cells_new})
        else:
            modified_rows.append(row)

    modified_table["rows"] = modified_rows

    return modified_table, True


def validate_table_consistency(table: dict) -> tuple[ConsistencyState, dict]:
    """
    Validate table structure consistency.

    Args:
        table: ComparisonTable dict

    Returns:
        Tuple of (ConsistencyState, diagnosis_dict)
    """
    columns_per_row = calculate_logical_columns_per_row(table)

    if not columns_per_row:
        return ConsistencyState.CONSISTENT, {"expected_columns": 0}

    # Find the mode (most common column count) - this is the expected value
    from collections import Counter

    counter = Counter(columns_per_row)
    expected_columns = counter.most_common(1)[0][0]

    # Find inconsistent rows
    inconsistent_rows = [
        idx
        for idx, count in enumerate(columns_per_row)
        if count != expected_columns
    ]

    if not inconsistent_rows:
        return ConsistencyState.CONSISTENT, {
            "expected_columns": expected_columns,
            "actual_columns_per_row": columns_per_row,
        }

    # Check if only row 1 (header) is inconsistent
    if inconsistent_rows == [0]:
        return ConsistencyState.HEADER_MISSING_COLUMNS, {
            "expected_columns": expected_columns,
            "actual_columns_per_row": columns_per_row,
            "inconsistent_rows": inconsistent_rows,
            "differences": {0: columns_per_row[0] - expected_columns},
        }

    # Multiple inconsistencies
    differences = {
        idx: columns_per_row[idx] - expected_columns for idx in inconsistent_rows
    }

    return ConsistencyState.MULTIPLE_INCONSISTENCIES, {
        "expected_columns": expected_columns,
        "actual_columns_per_row": columns_per_row,
        "inconsistent_rows": inconsistent_rows,
        "differences": differences,
    }


def diagnose_inconsistencies(table: dict, diagnosis: dict) -> str:
    """
    Generate human-readable diagnosis of table inconsistencies.

    Args:
        table: ComparisonTable dict
        diagnosis: Diagnosis dict from validate_table_consistency

    Returns:
        Human-readable diagnosis string
    """
    rows = table.get("rows", [])
    expected = diagnosis.get("expected_columns", 0)
    actual_per_row = diagnosis.get("actual_columns_per_row", [])
    inconsistent = diagnosis.get("inconsistent_rows", [])
    differences = diagnosis.get("differences", {})

    lines = [
        f"Table has {len(rows)} rows. Expected logical columns: {expected}",
        "",
        "Issues found:",
    ]

    for row_idx in inconsistent:
        actual = actual_per_row[row_idx]
        diff = differences[row_idx]

        if row_idx == 0:
            row_label = "Row 1 (header)"
        else:
            row_label = f"Row {row_idx + 1}"

        if diff < 0:
            lines.append(
                f"- {row_label}: has {actual} columns, expected {expected} (missing {abs(diff)} column(s))"
            )
        else:
            lines.append(
                f"- {row_label}: has {actual} columns, expected {expected} ({diff} extra column(s))"
            )

    lines.append("")
    lines.append("Possible causes:")

    # Analyze possible causes
    for row_idx in inconsistent:
        if row_idx > 0:
            # Check if previous rows have rowspan cells
            prev_rows_with_rowspan = []
            for prev_idx in range(row_idx):
                cells = rows[prev_idx].get("cells", [])
                for cell_idx, cell in enumerate(cells):
                    rowspan = cell.get("rowspan", 1) or 1
                    if rowspan > 1 and prev_idx + rowspan > row_idx:
                        prev_rows_with_rowspan.append((prev_idx, cell_idx, rowspan))

            if prev_rows_with_rowspan:
                lines.append(
                    f"- Row {row_idx + 1} has active rowspan cells from previous rows not properly accounted for"
                )

    return "\n".join(lines)


def fix_header_missing_columns(table: dict, diagnosis: dict) -> dict:
    """
    Fix header row column count mismatch.

    Handles two cases:
    - Header has too few columns: add empty cells
    - Header has too many columns: remove empty cells or reduce colspan

    Args:
        table: ComparisonTable dict
        diagnosis: Diagnosis dict

    Returns:
        Corrected table dict
    """
    rows = table.get("rows", [])
    if not rows:
        return table

    difference = diagnosis["differences"].get(0, 0)

    if difference == 0:
        # No difference
        return table

    row1_cells = rows[0].get("cells", [])

    if difference > 0:
        # Header has TOO MANY columns - remove extras
        columns_to_remove = difference

        # Strategy: Remove empty cells from the beginning, or reduce colspan of first empty cell
        new_row1_cells = []
        columns_removed = 0

        for cell in row1_cells:
            if columns_removed >= columns_to_remove:
                # Already removed enough, keep rest
                new_row1_cells.append(cell)
            elif not cell.get("value", "").strip():
                # Empty cell - can remove or reduce colspan
                colspan = cell.get("colspan", 1) or 1

                if colspan > columns_to_remove - columns_removed:
                    # Reduce colspan
                    new_colspan = colspan - (columns_to_remove - columns_removed)
                    columns_removed = columns_to_remove

                    if new_colspan == 1:
                        # Remove colspan field
                        new_cell = {k: v for k, v in cell.items() if k != "colspan"}
                        new_row1_cells.append(new_cell)
                    else:
                        new_row1_cells.append({**cell, "colspan": new_colspan})
                else:
                    # Remove entire cell
                    columns_removed += colspan
            else:
                # Non-empty cell - keep it
                new_row1_cells.append(cell)
    else:
        # Header has TOO FEW columns - add empty cells
        columns_to_add = abs(difference)
        empty_cells = [{"value": ""} for _ in range(columns_to_add)]
        new_row1_cells = empty_cells + row1_cells

    # Create modified table
    modified_table = {**table}
    modified_rows = [{"cells": new_row1_cells}] + rows[1:]
    modified_table["rows"] = modified_rows

    return modified_table


async def fix_with_llm_correction(
    table: dict, diagnosis: dict, category: str
) -> dict:
    """
    Fix table inconsistencies using LLM.

    Args:
        table: ComparisonTable dict
        diagnosis: Diagnosis dict
        category: Category name

    Returns:
        Corrected table dict
    """
    from prompts.table_correction_prompt import create_table_correction_prompt
    from utils.gemini_client import generate_with_reasoning
    from prompts.alignment_prompt import ComparisonTable

    diagnosis_text = diagnose_inconsistencies(table, diagnosis)
    expected_columns = diagnosis.get("expected_columns", 0)

    prompt = create_table_correction_prompt(
        table=table,
        diagnosis=diagnosis_text,
        category=category,
        expected_columns=expected_columns,
    )

    response = await generate_with_reasoning(
        prompt=prompt,
        model="gemini-2.5-flash",
        thinking_budget=4096,
        temperature=0.2,
        response_mime_type="application/json",
        response_schema=ComparisonTable.model_json_schema(),
    )

    try:
        corrected_table = json.loads(response)
        return corrected_table
    except json.JSONDecodeError as e:
        print(f"    ✗ Failed to parse LLM correction response: {e}")
        return table


async def validate_and_fix_table(
    table: dict, category: str, max_iterations: int = 3
) -> tuple[dict, dict]:
    """
    Validate and fix table structure.

    Main orchestration function that:
    1. Removes category column if present
    2. Validates consistency
    3. Applies appropriate fixes
    4. Loops until consistent or max iterations reached

    Args:
        table: ComparisonTable dict
        category: Category name
        max_iterations: Maximum correction iterations

    Returns:
        Tuple of (corrected_table, validation_log)
    """
    from pathlib import Path

    log: dict[str, Any] = {"iterations": 0, "fixes_applied": []}

    # Save the original table before any corrections
    tmp_dir = Path(__file__).parent.parent / "output" / "two_phase" / "tmp"
    original_table_path = tmp_dir / f"{category}_table_before_correction.json"
    with open(original_table_path, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=2)

    for iteration in range(max_iterations):
        log["iterations"] = iteration + 1

        # Step 1: Remove category column
        table, removed = remove_category_column(table)
        if removed and iteration == 0:
            log["category_column_removed"] = True
            log["fixes_applied"].append("remove_category")
            print(f"  ✓ Removed category column from table")

        # Step 2: Calculate logical columns
        columns_per_row = calculate_logical_columns_per_row(table)

        # Step 3: Validate
        state, diagnosis = validate_table_consistency(table)

        if iteration == 0:
            log["initial_state"] = state.value
            log["initial_columns_per_row"] = columns_per_row
            if state != ConsistencyState.CONSISTENT:
                log["initial_diagnosis"] = diagnose_inconsistencies(table, diagnosis)
                print(f"  ⚠ Table validation: {state.value}")
                print(f"    Columns per row: {columns_per_row}")

        # Step 4: Check if done
        if state == ConsistencyState.CONSISTENT:
            log["final_state"] = "CONSISTENT"
            log["final_column_count"] = columns_per_row[0] if columns_per_row else 0

            # Save the corrected table
            corrected_table_path = tmp_dir / f"{category}_table_after_correction.json"
            with open(corrected_table_path, "w", encoding="utf-8") as f:
                json.dump(table, f, ensure_ascii=False, indent=2)

            if iteration > 0:
                print(
                    f"  ✓ Table validated and corrected after {iteration + 1} iteration(s)"
                )
            return table, log

        # Step 5: Apply fixes
        if state == ConsistencyState.HEADER_MISSING_COLUMNS:
            print(f"  → Fixing header row (iteration {iteration + 1})")
            table = fix_header_missing_columns(table, diagnosis)
            log["fixes_applied"].append(f"fix_header_iter_{iteration + 1}")

        elif state == ConsistencyState.MULTIPLE_INCONSISTENCIES:
            print(
                f"  → Applying LLM correction for multiple issues (iteration {iteration + 1})"
            )
            table = await fix_with_llm_correction(table, diagnosis, category)
            log["fixes_applied"].append(f"llm_correction_iter_{iteration + 1}")

    # Max iterations reached
    final_state, final_diagnosis = validate_table_consistency(table)
    log["final_state"] = final_state.value
    log["final_columns_per_row"] = calculate_logical_columns_per_row(table)

    # Save the final table (even if not fully corrected)
    corrected_table_path = tmp_dir / f"{category}_table_after_correction.json"
    with open(corrected_table_path, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=2)

    if final_state != ConsistencyState.CONSISTENT:
        log["warning"] = "Max iterations reached, table may still have issues"
        print(
            f"  ⚠ Warning: Table still inconsistent after {max_iterations} iterations"
        )
        print(f"    Final state: {final_state.value}")
        print(f"    Final columns: {log['final_columns_per_row']}")

    return table, log
