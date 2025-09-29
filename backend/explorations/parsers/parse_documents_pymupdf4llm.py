#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyMuPDF4LLM Document Parser with Markdown Output
================================================

Dependencies are already in pyproject.toml:
    pymupdf4llm>=0.0.27

Usage:
    uv run python parse_documents_pymupdf4llm.py

This script will:
1. Scan the 'documents' folder for PDF and other supported files
2. Parse each document using pymupdf4llm (optimized for LLM consumption)
3. Export results as Markdown to the 'output' folder

Note: pymupdf4llm is specifically designed to extract text in a format
optimized for Large Language Models, with excellent structure preservation
and markdown formatting.
"""

import os
import sys
import warnings
from pathlib import Path
from typing import Optional, Dict, Any
import logging
import pymupdf4llm
import pymupdf

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DocumentParser:
    """Document parser using pymupdf4llm library optimized for LLM consumption"""

    SUPPORTED_EXTENSIONS = {
        '.pdf', '.epub', '.mobi', '.xps', '.fb2', '.cbz',
        '.svg', '.txt', '.html', '.htm', '.xml'
    }

    def __init__(self, input_dir: str = "documents", output_dir: str = "output"):
        """
        Initialize the document parser.

        Args:
            input_dir: Directory containing documents to parse
            output_dir: Directory to save markdown outputs
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

        # Create directories if they don't exist
        self.input_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

        # Log pymupdf4llm version
        logger.info(f"Initializing pymupdf4llm parser (PyMuPDF version {pymupdf.version[0]})")
        logger.info("Optimized for Large Language Model consumption")

    def find_documents(self) -> list[Path]:
        """
        Find all supported documents in the input directory.

        Returns:
            List of document paths
        """
        documents = []

        if not self.input_dir.exists():
            logger.warning(f"Input directory '{self.input_dir}' does not exist")
            return documents

        for file_path in self.input_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                documents.append(file_path)

        logger.info(f"Found {len(documents)} documents to process")
        return documents

    def parse_document(self, file_path: Path) -> str | None:
        """
        Parse a single document and return its markdown content.

        Args:
            file_path: Path to the document

        Returns:
            Markdown content or None if parsing fails
        """
        try:
            logger.info(f"Parsing: {file_path.name}")

            # Use pymupdf4llm to extract markdown-formatted text
            # This provides better structure preservation for LLM consumption
            markdown_result = pymupdf4llm.to_markdown(
                str(file_path),
                page_chunks=True,  # Preserve page boundaries
                write_images=False,  # Don't extract images to disk
                image_size_limit=0,  # Skip image extraction
                table_strategy="lines_strict",  # Better table detection
            )

            # Handle different return types
            if isinstance(markdown_result, list):
                # When page_chunks=True, returns list of dicts with metadata
                markdown_parts = []
                for i, chunk in enumerate(markdown_result, 1):
                    if isinstance(chunk, dict):
                        # Add page separator
                        markdown_parts.append(f"\n\n---\n*Page {i}*\n---\n\n")
                        # Add the text content
                        markdown_parts.append(chunk.get('text', ''))
                    else:
                        markdown_parts.append(str(chunk))
                markdown_text = ''.join(markdown_parts)
            else:
                markdown_text = str(markdown_result)

            # Add document header with metadata
            header = f"# Document: {file_path.name}\n\n"
            header += f"**Source**: `{file_path}`\n"
            header += f"**Parsed with**: pymupdf4llm (Optimized for LLM)\n"
            header += f"**PyMuPDF Version**: {pymupdf.version[0]}\n"
            header += "---\n\n"

            # Add table of contents if document is long
            lines = markdown_text.split('\n')
            if len(lines) > 100:
                headers = []
                for line in lines:
                    if line.startswith('#'):
                        level = len(line) - len(line.lstrip('#'))
                        if level <= 3:  # Only include h1, h2, h3
                            title = line.lstrip('#').strip()
                            indent = "  " * (level - 1)
                            headers.append(f"{indent}- {title}")

                if headers:
                    header += "## Table of Contents\n\n"
                    header += "\n".join(headers[:20])  # Limit to first 20 headers
                    if len(headers) > 20:
                        header += f"\n  - ... and {len(headers) - 20} more sections"
                    header += "\n\n---\n\n"

            # Process the markdown to enhance formatting
            enhanced_markdown = self.enhance_markdown(markdown_text)

            return header + enhanced_markdown

        except Exception as e:
            logger.error(f"Error parsing {file_path.name}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def enhance_markdown(self, markdown_text: str) -> str:
        """
        Enhance the markdown formatting for better readability.

        Args:
            markdown_text: Original markdown text

        Returns:
            Enhanced markdown text
        """
        lines = markdown_text.split('\n')
        enhanced_lines = []
        prev_was_header = False

        for i, line in enumerate(lines):
            # Add spacing around headers
            if line.startswith('#'):
                if i > 0 and not prev_was_header:
                    enhanced_lines.append('')  # Add blank line before header
                enhanced_lines.append(line)
                if i < len(lines) - 1:
                    enhanced_lines.append('')  # Add blank line after header
                prev_was_header = True

            # Enhance page breaks
            elif 'page' in line.lower() and '---' in line:
                enhanced_lines.append('')
                enhanced_lines.append('---')
                enhanced_lines.append(f'*{line.strip()}*')
                enhanced_lines.append('---')
                enhanced_lines.append('')
                prev_was_header = False

            # Enhance table formatting
            elif '|' in line:
                # Ensure tables have proper spacing
                if i > 0 and not enhanced_lines[-1].strip().startswith('|'):
                    enhanced_lines.append('')  # Add blank line before table
                enhanced_lines.append(line)
                # Check if next line is not part of table
                if i < len(lines) - 1 and '|' not in lines[i + 1]:
                    enhanced_lines.append('')  # Add blank line after table
                prev_was_header = False

            else:
                enhanced_lines.append(line)
                prev_was_header = False

        # Join lines and clean up excessive blank lines
        result = '\n'.join(enhanced_lines)
        # Replace multiple blank lines with maximum of two
        while '\n\n\n' in result:
            result = result.replace('\n\n\n', '\n\n')

        return result

    def save_markdown(self, content: str, original_filename: str) -> Path:
        """
        Save markdown content to the output directory.

        Args:
            content: Markdown content to save
            original_filename: Original document filename

        Returns:
            Path to the saved markdown file
        """
        # Create markdown filename based on original
        base_name = Path(original_filename).stem
        markdown_filename = f"{base_name}_llm.md"
        output_path = self.output_dir / markdown_filename

        # Save the markdown file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Saved: {output_path}")
        return output_path

    def process_all_documents(self):
        """Process all documents in the input directory."""
        documents = self.find_documents()

        if not documents:
            logger.warning("No documents found to process")
            logger.info(f"Place documents in the '{self.input_dir}' directory")
            logger.info(f"Supported formats: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}")
            return

        successful = 0
        failed = 0

        for doc_path in documents:
            logger.info(f"\nProcessing {doc_path.name}...")

            # Parse document
            markdown_content = self.parse_document(doc_path)

            if markdown_content:
                # Save to output folder
                self.save_markdown(markdown_content, doc_path.name)
                successful += 1
            else:
                failed += 1

        # Print summary
        logger.info("\n" + "="*50)
        logger.info("PROCESSING COMPLETE")
        logger.info(f"Successfully parsed: {successful} documents")
        if failed > 0:
            logger.info(f"Failed to parse: {failed} documents")
        logger.info(f"Output saved to: {self.output_dir.absolute()}")
        logger.info("="*50)

        # Show optimization tips
        if successful > 0:
            logger.info("\n💡 Tips for LLM consumption:")
            logger.info("- Documents are optimized with structured markdown")
            logger.info("- Tables and lists are preserved for better context")
            logger.info("- Page boundaries are marked for reference")
            logger.info("- Headers are hierarchically organized")


def main():
    """Main function to run the document parser."""
    logger.info("Starting pymupdf4llm Document Parser")
    logger.info("Extracting to Markdown format optimized for LLMs")

    # Create parser instance
    parser = DocumentParser(
        input_dir="documents",
        output_dir="output"
    )

    # Process all documents
    parser.process_all_documents()


if __name__ == "__main__":
    main()