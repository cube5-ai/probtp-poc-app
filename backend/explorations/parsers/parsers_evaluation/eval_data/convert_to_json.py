"""
Read the data from the markdown files, identify the tables and convert them to json
"""

import json
import os
import sys
import re
import uuid
from pathlib import Path

def list_markdown_files(directory: Path) -> list[Path]:
    """
    List all the markdown files in the directory
    """
    return list(directory.glob("*.md"))


def is_table_continuation(lines: list[str], current_index: int) -> bool:
    """
    Check if the current line is likely a continuation of a table cell
    """
    if current_index >= len(lines):
        return False
    
    current_line = lines[current_index].strip()
    
    # If current line is empty, check if next few lines contain table content
    if not current_line:
        for i in range(current_index + 1, min(current_index + 3, len(lines))):
            if lines[i].strip().startswith('|'):
                return True
        return False
    
    # Check if this looks like a continuation of table content
    # (doesn't start with |, but could be part of a multiline cell)
    if not current_line.startswith('|'):
        # Look ahead to see if there are more table rows
        for i in range(current_index + 1, min(current_index + 5, len(lines))):
            if lines[i].strip().startswith('|'):
                return True
    
    return False


def find_tables_and_convert_to_json(markdown_file: Path) -> list[dict]:
    """
    Read the data from the markdown files, identify the tables and convert them to json
    """
    with open(markdown_file, "r", encoding='utf-8') as file:
        data = file.read()

    # Find tables by identifying header and separator patterns
    # Then collect all subsequent lines until we hit a non-table line
    lines = data.split('\n')
    all_json_objects = []

    i = 0
    while i < len(lines):
        # Look for table header pattern
        if lines[i].strip().startswith('|') and '|' in lines[i]:
            # Check if next line is separator
            if i + 1 < len(lines) and re.match(r'^\|\s*[-\s\|]+\|\s*$', lines[i + 1]):
                # Found a table, extract it
                table_lines = [lines[i], lines[i + 1]]  # Header and separator
                j = i + 2

                # Collect all table rows (including multiline cells)
                while j < len(lines):
                    line = lines[j].strip()

                    # Check if this is clearly the end of the table
                    if (line
                        and not line.startswith('|')
                        and not is_table_continuation(lines, j)
                        and (line.startswith('#') or
                             line.startswith('---') or
                             line.startswith('Question'))
                    ):
                            break

                    # Add the line to the table
                    table_lines.append(lines[j])
                    j += 1

                # Parse the collected table
                table_text = '\n'.join(table_lines)
                json_objects = parse_table_to_json(table_text)
                all_json_objects.extend(json_objects)

                i = j
            else:
                i += 1
        else:
            i += 1

    return all_json_objects


def parse_table_to_json(table_text: str) -> list[dict]:
    """
    Parse a single markdown table and convert each row to a JSON object
    Handles multiline cells by reconstructing rows properly
    """
    lines = table_text.split('\n')

    # Extract header row and clean it
    header_line = lines[0].strip()
    headers = [col.strip() for col in header_line.split('|')[1:-1]]  # Remove first and last empty elements

    # Skip separator row (lines[1])
    data_lines = lines[2:]

    json_objects = []

    # Reconstruct rows that might span multiple lines
    current_row_parts = []

    for line in data_lines:
        line_stripped = line.strip()

        # Skip empty lines that are not part of multiline cells
        if not line_stripped:
            continue

        # Check if this line starts a new row (starts with |)
        if line_stripped.startswith('|'):
            # If we have accumulated parts from previous lines, process them first
            if current_row_parts:
                process_row(current_row_parts, headers, json_objects)
                current_row_parts = []

            # Start accumulating new row
            current_row_parts.append(line)
        else:
            # This is continuation of a multiline cell
            if current_row_parts:
                current_row_parts.append(line)

    # Process the last row if any
    if current_row_parts:
        process_row(current_row_parts, headers, json_objects)

    return json_objects


def process_row(row_lines: list[str], headers: list[str], json_objects: list[dict]) -> None:
    """
    Process accumulated row lines and create a JSON object
    """
    # Combine all lines and split by |
    combined_line = ' '.join(line.strip() for line in row_lines)

    # Handle the case where cells contain | characters within them
    # We need to be smarter about splitting
    cells = split_table_row(combined_line)

    if len(cells) >= len(headers):
        # Create JSON object with header as keys
        json_obj = {}
        for i, header in enumerate(headers):
            # Get cell content, default to empty if not enough cells
            cell_value = cells[i] if i < len(cells) else ""

            # Clean cell content and handle special cases
            cell_value = re.sub(r'\s+', ' ', cell_value).strip()

            # Convert specific values
            if cell_value.lower() in ['none', '`none`', '']:
                cell_value = None
            elif cell_value.lower() in ['`null`', 'null']:
                cell_value = "Non pris en charge"


            json_obj[header] = cell_value.strip() if cell_value else None

        # Add unique identifier to each object
        json_obj["id"] = str(uuid.uuid4())[:8]

        json_objects.append(json_obj)


def split_table_row(row: str) -> list[str]:
    """
    Split a table row by | while handling escaped pipes and complex content
    """
    # Remove leading/trailing |
    row = row.strip()
    if row.startswith('|'):
        row = row[1:]
    if row.endswith('|'):
        row = row[:-1]

    # Split by | and clean each cell
    cells = [cell.strip() for cell in row.split('|')]

    return cells



def write_to_json(data: list[dict], json_file: Path) -> None:
    """
    Write the data to a json file
    """
    with open(json_file, "w", encoding='utf-8') as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def write_to_jsonl(data: list[dict], jsonl_file: Path) -> None:
    """
    Write the data to a JSONL file (one JSON object per line)
    """
    with open(jsonl_file, "w", encoding='utf-8') as file:
        for obj in data:
            json.dump(obj, file, ensure_ascii=False)
            file.write('\n')


if __name__ == "__main__":
    markdown_files = list_markdown_files(Path("."))
    for i, markdown_file in enumerate(markdown_files):
        print(f"Processing {markdown_file}...")
        data = find_tables_and_convert_to_json(markdown_file)

        # Write to JSON file
        write_to_json(data, Path(f"./data_{i}.json"))
        # Write to JSONL file (one object per line)
        write_to_jsonl(data, Path(f"./data_{i}.jsonl"))
        print(f"Written `data_{i}.json` and `data_{i}.jsonl` for {markdown_file} ({len(data)} objects)")