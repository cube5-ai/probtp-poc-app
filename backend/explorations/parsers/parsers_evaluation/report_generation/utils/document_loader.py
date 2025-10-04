"""Document loader utilities for parsed insurance contracts."""
import json
from pathlib import Path
from typing import Any


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
