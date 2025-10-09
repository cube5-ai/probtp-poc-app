"""Phase 1: Parse and Get Tables List."""
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

import fitz
from langfuse import observe

# Thread lock for PyMuPDF operations to avoid concurrent access issues
_pymupdf_lock = threading.Lock()


def standardize_empty_cells_html(html_content: str) -> str:
    """
    Standardize empty cell representation in HTML tables.
    Replaces empty <td></td> cells with <td>-</td> for non-first-row cells.

    Args:
        html_content: HTML content containing table(s)

    Returns:
        HTML with standardized empty cell representation
    """
    # Split into rows
    rows = re.findall(r'<tr[^>]*>.*?</tr>', html_content, re.DOTALL)

    if not rows:
        return html_content

    # Keep first row as-is (may contain empty header cells)
    standardized_rows = [rows[0]]

    # Process remaining rows: replace empty cells with "-"
    for row in rows[1:]:
        # Replace empty td cells with "-"
        # Pattern: <td ...></td> or <td ...> </td> (whitespace only)
        standardized_row = re.sub(
            r'(<td[^>]*>)\s*(</td>)',
            r'\1-\2',
            row
        )
        standardized_rows.append(standardized_row)

    # Reconstruct the HTML
    # Find the part before first <tr> and after last </tr>
    table_start = html_content[:html_content.find('<tr')]
    table_end_pos = html_content.rfind('</tr>') + len('</tr>')
    table_end = html_content[table_end_pos:]

    return table_start + ''.join(standardized_rows) + table_end


def standardize_empty_cells_markdown(markdown: str) -> str:
    """
    Standardize empty cell representation in markdown tables.
    Replaces empty cells with "-" for non-first-row cells.

    Args:
        markdown: Markdown content containing table(s)

    Returns:
        Markdown with standardized empty cell representation
    """
    lines = markdown.split('\n')
    result_lines = []

    in_table = False
    row_count = 0

    for line in lines:
        if '|' in line and line.strip():
            if not in_table:
                in_table = True
                row_count = 0

            row_count += 1

            # Skip separator rows (like |---|---|)
            if re.match(r'^\s*\|[\s\-:]+\|\s*$', line):
                result_lines.append(line)
                continue

            # For first row (header), keep as-is
            if row_count == 1:
                result_lines.append(line)
                continue

            # For data rows, replace empty cells with "-"
            cells = line.split('|')
            standardized_cells = []
            for cell in cells:
                stripped = cell.strip()
                if not stripped or stripped == '':
                    standardized_cells.append(' - ')
                else:
                    standardized_cells.append(cell)
            result_lines.append('|'.join(standardized_cells))
        else:
            in_table = False
            row_count = 0
            result_lines.append(line)

    return '\n'.join(result_lines)


# Load Landing AI parsed document
@observe()
def get_landing_tables(file_path: str) -> dict[int, list[dict]]:
    """
    Parse document with Landing AI and extract tables per page.

    Returns:
        Dict mapping page number to list of table objects
    """
    tables_by_page, _ = get_landing_tables_with_response(file_path)
    return tables_by_page


@observe()
def get_landing_tables_with_response(file_path: str) -> tuple[dict[int, list[dict]], dict]:
    """
    Parse document with Landing AI and extract tables per page.

    Returns:
        Tuple of (tables_by_page dict, original Landing AI response dict)
    """
    document_name = os.path.basename(file_path).replace(".pdf", "")
    cache_path = Path(__file__).parent.parent.parent / "output" / "landing_ai_solo" / f"{document_name}.json"

    with open(cache_path, encoding="utf-8") as f:
        landing_response = json.load(f)

    tables_by_page: dict[int, list[dict]] = {}

    for chunk_idx, chunk in enumerate(landing_response.get('chunks', [])):
        if chunk.get('type') != 'table':
            continue

        page = chunk.get('grounding', {}).get('page')
        if page is None:
            continue

        if page not in tables_by_page:
            tables_by_page[page] = []

        # Calculate position in page for this table
        position_in_page = len(tables_by_page[page])

        # Standardize empty cells in HTML content
        raw_html = chunk.get('markdown', '')
        standardized_html = standardize_empty_cells_html(raw_html)

        tables_by_page[page].append({
            'content': standardized_html,
            'html_content': standardized_html,
            'grounding': chunk.get('grounding', {}),
            'metadata': chunk.get('metadata', {}),
            'chunk_index': chunk_idx,
            'chunk': chunk,
            # Stable metadata for tracking throughout pipeline
            'chunk_id': chunk.get('id'),
            'chunk_type': chunk.get('type'),
            'page_num': page,
            'position_in_page': position_in_page,
        })

    return tables_by_page, landing_response


# Parse with PyMuPDF and extract tables
@observe()
def get_pymupdf_tables(pdf_path: str) -> dict[int, list[dict]]:
    """
    Parse document with PyMuPDF and extract tables per page.

    Returns:
        Dict mapping page number to list of Table objects with extracted content
    """
    # Use lock to prevent concurrent PyMuPDF operations that can cause textpage conflicts
    with _pymupdf_lock:
        doc = fitz.open(pdf_path)
        tables_by_page: dict[int, list[dict]] = {}

        try:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                table_finder = page.find_tables()

                if not table_finder.tables:
                    continue

                tables_by_page[page_num] = []

                for table in table_finder.tables:
                    # Standardize empty cells in markdown
                    raw_markdown = table.to_markdown()
                    standardized_markdown = standardize_empty_cells_markdown(raw_markdown)

                    tables_by_page[page_num].append({
                        'table_object': table,
                        'extracted_content': table.extract(),
                        'markdown': standardized_markdown,
                        'bbox': table.bbox,
                        'row_count': table.row_count,
                        'col_count': table.col_count
                    })
        finally:
            doc.close()

        return tables_by_page

