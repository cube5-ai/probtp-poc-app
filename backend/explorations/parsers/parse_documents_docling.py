#!/usr/bin/env python3
"""
Docling + Granite Document Parser for MacOS M4
==============================================

Dependencies are already in pyproject.toml:
    docling>=2.7.0
    torch>=2.8.0
    transformers>=4.56.2
    docling-core>=2.4.0

Usage:
    uv run python parse_documents_docling.py

This script will:
1. Scan the 'documents' folder for PDF, DOCX, PPTX, HTML, and image files
2. Parse each document using Granite Docling
3. Export results as markdown to the 'output' folder

Note: You may see NumPy compatibility warnings. These can be safely ignored
as the script will still function correctly.
"""

import os
import sys
import warnings
from pathlib import Path
from typing import Optional
import logging

# Suppress NumPy version warnings that don't affect functionality
warnings.filterwarnings("ignore", message=".*NumPy.*")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
except ImportError as e:
    logger.error(f"Failed to import required libraries: {e}")
    logger.error("Please ensure docling is installed:")
    logger.error('  uv sync')
    sys.exit(1)


class DocumentParser:
    """Document parser using Granite Docling model"""

    SUPPORTED_EXTENSIONS = {
        '.pdf', '.docx', '.pptx', '.html', '.htm',
        '.png', '.jpg', '.jpeg', '.tiff', '.bmp'
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

        # Initialize the document converter with Granite Docling
        logger.info("Initializing Granite Docling converter...")

        # Configure pipeline options
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True  # Enable OCR for scanned PDFs
        pipeline_options.do_table_structure = True  # Enable table structure detection

        try:
            # Initialize converter with pipeline options
            self.converter = DocumentConverter(
                pdf_pipeline_options=pipeline_options
            )
            logger.info("Converter initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize with custom options: {e}")
            logger.info("Falling back to standard converter...")
            self.converter = DocumentConverter()

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

            # Convert document
            result = self.converter.convert(source=str(file_path))

            if result and result.document:
                # Export to markdown
                markdown_content = result.document.export_to_markdown()

                # Add document metadata header
                header = f"# Document: {file_path.name}\n\n"
                header += f"**Source**: `{file_path}`\n"
                header += "**Parsed with**: Granite Docling 258M\n"
                header += "---\n\n"

                return header + markdown_content
            else:
                logger.warning(f"No content extracted from {file_path.name}")
                return None

        except Exception as e:
            logger.error(f"Error parsing {file_path.name}: {e}")
            return None

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
        markdown_filename = f"{base_name}.md"
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
            logger.info(f"Supported formats: {', '.join(self.SUPPORTED_EXTENSIONS)}")
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


def main():
    """Main function to run the document parser."""
    logger.info("Starting Granite Docling Document Parser")
    logger.info("Running on MacOS with Apple Silicon optimization")

    # Create parser instance
    parser = DocumentParser(
        input_dir="documents",
        output_dir="output"
    )

    # Process all documents
    parser.process_all_documents()




if __name__ == "__main__":
    main()