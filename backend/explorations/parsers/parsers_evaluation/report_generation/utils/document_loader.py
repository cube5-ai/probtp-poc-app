"""Document loader utilities for parsed insurance contracts."""
import json
import re
from pathlib import Path
from typing import Any
from bs4 import BeautifulSoup


class ParsedDocument:
    """Represents a parsed insurance contract document."""

    def __init__(self, file_path: str | Path):
        """
        Load a parsed document from landing_ai_xtd output.

        Args:
            file_path: Path to the JSON file (from landing_ai_xtd parser)
        """
        self.file_path = Path(file_path)
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.chunks = self.data.get('chunks', [])
        self.markdown = self.data.get('markdown', '')
        self.metadata = self.data.get('metadata', {})

    @property
    def name(self) -> str:
        """Get document name from file path."""
        return self.file_path.stem

    def get_full_markdown(self) -> str:
        """Get the full markdown representation of the document."""
        return self.markdown

    def get_tables(self) -> list[dict[str, Any]]:
        """
        Extract all table chunks from the document.

        Returns:
            List of table chunks with html_content, markdown, and metadata
        """
        tables = []
        for chunk in self.chunks:
            chunk_type = chunk.get('chunk_type', '')
            if chunk_type == 'Table':
                tables.append({
                    'html_content': chunk.get('html_content', ''),
                    'markdown': chunk.get('markdown', ''),
                    'chunk_id': chunk.get('chunk_id', ''),
                    'page_number': chunk.get('page_number', 0),
                    'grounding': chunk.get('grounding', {}),
                })
        return tables

    def get_text_chunks(self) -> list[dict[str, Any]]:
        """
        Extract all text chunks from the document.

        Returns:
            List of text chunks with content and metadata
        """
        texts = []
        for chunk in self.chunks:
            chunk_type = chunk.get('chunk_type', '')
            if chunk_type in ['Text', 'NarrativeText']:
                texts.append({
                    'content': chunk.get('text', ''),
                    'markdown': chunk.get('markdown', ''),
                    'chunk_id': chunk.get('chunk_id', ''),
                    'page_number': chunk.get('page_number', 0),
                })
        return texts

    def get_chunks_by_type(self, chunk_type: str) -> list[dict[str, Any]]:
        """
        Get chunks filtered by type.

        Args:
            chunk_type: Type of chunk (e.g., 'Table', 'Text', 'Image')

        Returns:
            List of matching chunks
        """
        return [c for c in self.chunks if c.get('chunk_type') == chunk_type]

    def get_markdown_with_expanded_tables(self) -> str:
        """
        Get markdown with tables expanded (rowspan/colspan duplicated).

        This helps LLMs understand table structure by showing the actual grid
        with duplicated cell values for spans, no metadata.

        Returns:
            Modified markdown with expanded tables injected below original tables
        """
        modified_markdown = self.markdown

        # Find all <table> tags in markdown and expand them
        table_pattern = r'(<table[^>]*>.*?</table>)'

        def expand_table(match):
            html_table = match.group(1)
            # Convert HTML to expanded markdown
            expanded_md = _html_table_to_expanded_markdown(html_table)
            # Return original + expanded view
            return f"{html_table}\n\n**Expanded view (for structure analysis):**\n\n{expanded_md}\n"

        modified_markdown = re.sub(
            table_pattern,
            expand_table,
            modified_markdown,
            flags=re.DOTALL | re.IGNORECASE
        )

        return modified_markdown


def _html_table_to_expanded_markdown(html: str) -> str:
    """
    Convert HTML table to markdown with rowspan/colspan expanded.

    Duplicates cell content for spans to show the actual grid structure.
    Only includes cell values, no metadata (no cell IDs, no grounding).

    Args:
        html: HTML table string

    Returns:
        Markdown table with expanded cells
    """
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')

    if not table:
        return "(No table found)"

    # Build a grid representation
    rows = []
    max_cols = 0

    for tr in table.find_all('tr'):
        row_cells = []
        for cell in tr.find_all(['td', 'th']):
            # Get cell value (text only, no attributes)
            value = cell.get_text(strip=True)

            # Get span values
            colspan = int(cell.get('colspan', 1))
            rowspan = int(cell.get('rowspan', 1))

            # Add cell with span info
            row_cells.append({
                'value': value,
                'colspan': colspan,
                'rowspan': rowspan
            })

        rows.append(row_cells)
        max_cols = max(max_cols, sum(c['colspan'] for c in row_cells))

    # Expand spans into a grid
    grid = []

    for row_idx, row in enumerate(rows):
        # Initialize row in grid
        if row_idx >= len(grid):
            grid.append([None] * max_cols)

        col_idx = 0
        for cell in row:
            # Find next available column
            while col_idx < len(grid[row_idx]) and grid[row_idx][col_idx] is not None:
                col_idx += 1

            if col_idx >= len(grid[row_idx]):
                break

            value = cell['value']
            colspan = cell['colspan']
            rowspan = cell['rowspan']

            # Fill the grid with duplicated values
            for r in range(rowspan):
                row_target = row_idx + r
                # Ensure row exists
                while row_target >= len(grid):
                    grid.append([None] * max_cols)

                for c in range(colspan):
                    col_target = col_idx + c
                    if col_target < len(grid[row_target]):
                        grid[row_target][col_target] = value

            col_idx += colspan

    # Convert grid to markdown
    if not grid:
        return "(Empty table)"

    md_lines = []

    # Header row
    header = grid[0] if grid else []
    md_lines.append('| ' + ' | '.join(str(c or '') for c in header) + ' |')

    # Separator
    md_lines.append('| ' + ' | '.join(['---'] * len(header)) + ' |')

    # Data rows
    for row in grid[1:]:
        md_lines.append('| ' + ' | '.join(str(c or '') for c in row) + ' |')

    return '\n'.join(md_lines)


def load_document_pair(
    probtp_path: str | Path,
    axa_path: str | Path
) -> tuple[ParsedDocument, ParsedDocument]:
    """
    Load a pair of ProBTP and AXA documents for comparison.

    Args:
        probtp_path: Path to ProBTP document JSON
        axa_path: Path to AXA document JSON

    Returns:
        Tuple of (probtp_doc, axa_doc)
    """
    probtp = ParsedDocument(probtp_path)
    axa = ParsedDocument(axa_path)
    return probtp, axa


def get_available_documents(output_dir: str | Path) -> list[Path]:
    """
    Get list of available parsed documents in the output directory.

    Args:
        output_dir: Path to landing_ai_xtd output directory

    Returns:
        List of JSON file paths
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        return []
    return list(output_path.glob('*.json'))
