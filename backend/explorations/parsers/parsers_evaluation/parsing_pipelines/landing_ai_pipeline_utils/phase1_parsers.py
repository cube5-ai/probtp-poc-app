"""Phase 1: Parse and Get Tables List."""
import json
import os
from pathlib import Path
from typing import Any

import fitz
from langfuse import observe


# Load Landing AI parsed document
@observe()
def get_landing_tables(file_path: str) -> dict[int, list[dict]]:
    """
    Parse document with Landing AI and extract tables per page.
    
    Returns:
        Dict mapping page number to list of table objects
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
            
        tables_by_page[page].append({
            'content': chunk.get('markdown', ''),
            'html_content': chunk.get('markdown', ''),
            'grounding': chunk.get('grounding', {}),
            'metadata': chunk.get('metadata', {}),
            'chunk_index': chunk_idx,
            'chunk': chunk
        })
    
    return tables_by_page


# Parse with PyMuPDF and extract tables
@observe()
def get_pymupdf_tables(pdf_path: str) -> dict[int, list[dict]]:
    """
    Parse document with PyMuPDF and extract tables per page.
    
    Returns:
        Dict mapping page number to list of Table objects with extracted content
    """
    doc = fitz.open(pdf_path)
    tables_by_page: dict[int, list[dict]] = {}
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        table_finder = page.find_tables()
        
        if not table_finder.tables:
            continue
            
        tables_by_page[page_num] = []
        
        for table in table_finder.tables:
            tables_by_page[page_num].append({
                'table_object': table,
                'extracted_content': table.extract(),
                'markdown': table.to_markdown(),
                'bbox': table.bbox,
                'row_count': table.row_count,
                'col_count': table.col_count
            })
    
    doc.close()
    return tables_by_page

