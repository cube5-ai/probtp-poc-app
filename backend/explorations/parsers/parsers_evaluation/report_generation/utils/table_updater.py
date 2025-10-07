"""Utility for updating CategoryTable with classified ambiguous cases."""

import copy


def append_classified_cases_to_table(
    category_table: dict,
    classified_cases: list[dict],
    category: str
) -> dict:
    """
    Append classified ambiguous cases to the main category table.

    Args:
        category_table: CategoryTable dict
        classified_cases: List of ClassifiedCase dicts
        category: The category this table represents

    Returns:
        Updated CategoryTable dict with new rows appended
    """
    # Filter cases that belong to this category
    relevant_cases = [
        case for case in classified_cases
        if case.get("assigned_category") == category
    ]

    if not relevant_cases:
        # No cases to add for this category
        return category_table

    # Make a copy to avoid mutating original
    updated_table = copy.deepcopy(category_table)

    # Get table structure
    table_structure = updated_table.get("table_structure", {})
    total_columns = table_structure.get("total_columns", 0)
    column_labels = table_structure.get("column_labels", [])
    template_row = table_structure.get("template_row", [])

    # Get current row count
    rows = updated_table.get("rows", [])
    last_row_number = rows[-1].get("row_number", 0) if rows else 0

    # Append new rows for each classified case
    for case in relevant_cases:
        # Increment row number
        last_row_number += 1

        # Create a new row for this case
        # Structure: Dimension cells + Data cells
        # We'll create a simple row with the benefit description in the "Prestation" column
        # and mark it as coming from ambiguous cases

        # Find indices for key columns
        prestation_idx = None
        for i, col_name in enumerate(template_row):
            if "prestation" in col_name.lower() or "bénéfice" in col_name.lower():
                prestation_idx = i
                break

        if prestation_idx is None:
            # Default to last dimension column before data columns
            prestation_idx = 0

        # Build cells array
        cells = []
        for i in range(total_columns):
            cell_id = f"{column_labels[i]}{last_row_number}"

            if i == prestation_idx:
                # Prestation column - add the benefit description
                cells.append({
                    "id": cell_id,
                    "value": f"{case.get('original_description', 'Unknown')} [Ambiguous - classified]"
                })
            elif i < prestation_idx:
                # Other dimension columns - empty
                cells.append({
                    "id": cell_id,
                    "value": ""
                })
            else:
                # Data columns - mark as "To be filled" or empty
                # In step 1.4, an LLM would fill these with actual coverage values
                # For now, we just create placeholders
                cells.append({
                    "id": cell_id,
                    "value": "À compléter",
                    "type": "data"
                })

        # Create row
        new_row = {
            "row_number": last_row_number,
            "inherited_from_above": [None] * total_columns,
            "cells": cells
        }

        rows.append(new_row)

    updated_table["rows"] = rows

    return updated_table


def generate_table_update_prompt(
    category_table: dict,
    source_markdown: str,
    vendor: str,
    category: str,
    language: str = "French (France)"
) -> str:
    """
    Generate a prompt to fill in coverage values for newly added ambiguous case rows.

    Args:
        category_table: CategoryTable with placeholder rows from ambiguous cases
        source_markdown: Original contract markdown
        vendor: Vendor name
        category: Category name
        language: Output language

    Returns:
        Formatted prompt string
    """
    # Find rows that need completion (those with "À compléter" values)
    rows_to_complete = []
    for row in category_table.get("rows", []):
        cells = row.get("cells", [])
        if any("À compléter" in cell.get("value", "") for cell in cells):
            rows_to_complete.append(row)

    if not rows_to_complete:
        return ""

    # Format rows for prompt
    rows_text = ""
    for row in rows_to_complete:
        row_num = row.get("row_number")
        cells = row.get("cells", [])
        prestation = next((c.get("value") for c in cells if "Ambiguous" in c.get("value", "")), "Unknown")
        rows_text += f"\n- Row {row_num}: {prestation}\n"

    prompt = f"""You are an expert insurance analyst. Your task is to complete the coverage values for newly classified benefits in the {vendor} {category} table.

**Context:**

The following benefits were classified as belonging to the "{category}" category and have been added to the table. However, their coverage values are missing and marked as "À compléter".

**Rows to Complete:**
{rows_text}

**Task:**

For each row:
1. Find the benefit description in the source document
2. Extract all coverage values for the policy levels in this table
3. Update the cells with correct values
4. Track source cell IDs

**Source Document:**

{source_markdown}

**Current Table (JSON):**

```json
{category_table}
```

**Output Language:** {language}

**Return**: The COMPLETE updated CategoryTable JSON with all "À compléter" cells filled with actual coverage values.

Output the JSON now:"""

    return prompt
