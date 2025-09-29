#!/usr/bin/env python3
"""
PyMuPDF Document Parser for MacOS M4
=====================================

Dependencies are already in pyproject.toml:
    pymupdf>=1.26.4

Usage:
    uv run python parse_document_pymupdf.py

This script will:
1. Scan the 'documents' folder for PDF, DOCX, PPTX, HTML, and image files
2. Parse each document using PyMuPDF
3. Export results as HTML to the 'output' folder

Note: PyMuPDF provides fast and efficient document parsing with excellent
text extraction and formatting preservation capabilities.
"""

import os
import sys
import warnings
from pathlib import Path
from typing import Optional
import logging
import pymupdf  # PyMuPDF

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DocumentParser:
    """Document parser using PyMuPDF library"""

    SUPPORTED_EXTENSIONS = {
        '.pdf', '.epub', '.mobi', '.xps', '.fb2', '.cbz',
        '.svg', '.txt', '.html', '.htm', '.xml',
        '.png', '.jpg', '.jpeg', '.tiff', '.bmp'
    }

    def __init__(self, input_dir: str = "documents", output_dir: str = "output"):
        """
        Initialize the document parser.

        Args:
            input_dir: Directory containing documents to parse
            output_dir: Directory to save HTML outputs
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

        # Create directories if they don't exist
        self.input_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

        # Log PyMuPDF version
        logger.info(f"Initializing PyMuPDF parser (version {pymupdf.version[0]})")

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
        Parse a single document and return its HTML content.

        Args:
            file_path: Path to the document

        Returns:
            HTML content or None if parsing fails
        """
        try:
            logger.info(f"Parsing: {file_path.name}")

            # Open document with PyMuPDF
            doc = pymupdf.open(str(file_path))

            # Create HTML document structure
            html_parts = []
            html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document: {}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .document-header {{
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .document-header h1 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .metadata {{
            color: #666;
            font-size: 0.9em;
        }}
        .metadata dt {{
            font-weight: bold;
            display: inline;
        }}
        .metadata dd {{
            display: inline;
            margin-left: 5px;
            margin-right: 20px;
        }}
        .page {{
            background-color: #fff;
            padding: 40px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .page-header {{
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 10px;
            margin-bottom: 20px;
            color: #666;
            font-size: 0.9em;
        }}
        .page-content {{
            min-height: 300px;
        }}
        .page-content p {{
            margin: 0.5em 0;
        }}
        .page-content h1, .page-content h2, .page-content h3 {{
            color: #2c3e50;
            margin-top: 1em;
        }}
        .page-content table {{
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
        }}
        .page-content th, .page-content td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        .page-content th {{
            background-color: #f8f9fa;
            font-weight: bold;
        }}
        .text-block {{
            margin: 0.5em 0;
        }}
        .image-container {{
            margin: 1em 0;
            text-align: center;
        }}
        .image-container img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
        }}
    </style>
</head>
<body>
""".format(file_path.name))

            # Add document header with metadata
            metadata = doc.metadata
            html_parts.append("""
    <div class="document-header">
        <h1>Document: {}</h1>
        <dl class="metadata">
            <dt>Source:</dt><dd>{}</dd>
            <dt>Pages:</dt><dd>{}</dd>
            <dt>Parsed with:</dt><dd>PyMuPDF {}</dd>
""".format(file_path.name, file_path, len(doc), pymupdf.version[0]))

            # Add available metadata
            if metadata.get('title'):
                html_parts.append(f"            <dt>Title:</dt><dd>{metadata['title']}</dd>\n")
            if metadata.get('author'):
                html_parts.append(f"            <dt>Author:</dt><dd>{metadata['author']}</dd>\n")
            if metadata.get('subject'):
                html_parts.append(f"            <dt>Subject:</dt><dd>{metadata['subject']}</dd>\n")
            if metadata.get('keywords'):
                html_parts.append(f"            <dt>Keywords:</dt><dd>{metadata['keywords']}</dd>\n")

            html_parts.append("        </dl>\n    </div>\n")

            # Process each page
            for page_num, page in enumerate(doc, 1):
                html_parts.append(f"""
    <div class="page" id="page{page_num}">
        <div class="page-header">Page {page_num} of {len(doc)}</div>
        <div class="page-content">
""")

                # Extract structured text blocks
                blocks = page.get_text("dict")

                for block in blocks.get("blocks", []):
                    if block.get("type") == 0:  # Text block
                        # Process lines in the block
                        block_html = []
                        for line in block.get("lines", []):
                            line_text = ""
                            for span in line.get("spans", []):
                                text = span.get("text", "")
                                font = span.get("font", "")
                                size = span.get("size", 12)
                                flags = span.get("flags", 0)

                                # Apply formatting based on font properties
                                formatted_text = text
                                if flags & 2**4:  # Bold
                                    formatted_text = f"<strong>{formatted_text}</strong>"
                                if flags & 2**1:  # Italic
                                    formatted_text = f"<em>{formatted_text}</em>"

                                # Detect headers based on font size
                                if size > 16:
                                    formatted_text = f"<h2>{formatted_text}</h2>"
                                elif size > 14:
                                    formatted_text = f"<h3>{formatted_text}</h3>"

                                line_text += formatted_text

                            if line_text.strip():
                                block_html.append(line_text)

                        # Join lines into paragraphs
                        if block_html:
                            html_parts.append("            <div class=\"text-block\">\n")
                            for line in block_html:
                                # Wrap non-header text in paragraphs
                                if not line.strip().startswith("<h"):
                                    html_parts.append(f"                <p>{line}</p>\n")
                                else:
                                    html_parts.append(f"                {line}\n")
                            html_parts.append("            </div>\n")

                    elif block.get("type") == 1:  # Image block
                        # Extract and embed images (optional, could save separately)
                        html_parts.append("""            <div class="image-container">
                <p><em>[Image detected - position {}x{}]</em></p>
            </div>\n""".format(
                            int(block.get("bbox", [0])[0]),
                            int(block.get("bbox", [0])[1])
                        ))

                # Try to extract tables using HTML format for better structure
                try:
                    page_html = page.get_text("html")
                    # Extract tables from the HTML if present
                    if "<table" in page_html:
                        import re
                        tables = re.findall(r'<table.*?</table>', page_html, re.DOTALL)
                        for table in tables:
                            html_parts.append("            " + table + "\n")
                except:
                    pass

                html_parts.append("""        </div>
    </div>
""")

            # Close HTML document
            html_parts.append("""
</body>
</html>
""")

            doc.close()

            return "".join(html_parts)

        except Exception as e:
            logger.error(f"Error parsing {file_path.name}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def save_html(self, content: str, original_filename: str) -> Path:
        """
        Save HTML content to the output directory.

        Args:
            content: HTML content to save
            original_filename: Original document filename

        Returns:
            Path to the saved HTML file
        """
        # Create HTML filename based on original
        base_name = Path(original_filename).stem
        html_filename = f"{base_name}.html"
        output_path = self.output_dir / html_filename

        # Save the HTML file
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
            html_content = self.parse_document(doc_path)

            if html_content:
                # Save to output folder
                self.save_html(html_content, doc_path.name)
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
    logger.info("Starting PyMuPDF Document Parser")
    logger.info("Running on MacOS with optimized performance")

    # Create parser instance
    parser = DocumentParser(
        input_dir="documents",
        output_dir="output"
    )

    # Process all documents
    parser.process_all_documents()


if __name__ == "__main__":
    main()