"""Debug utilities for saving pipeline artifacts."""
import json
from pathlib import Path


# Save debug artifacts to tmp folder
def save_debug_artifacts(
    landing_table: dict,
    matched_pymupdf_tables: list[dict],
    corrections_applied: int,
    violations: list[dict],
    table_id: str,
    page_num: int,
    pdf_name: str,
    phase: str
) -> None:
    """Save debug information about table processing."""
    tmp_dir = Path(__file__).parent / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    
    # Create debug dict
    debug_info = {
        "table_id": table_id,
        "page_num": page_num,
        "phase": phase,
        "landing_ai_html": landing_table.get('html_content', ''),
        "landing_ai_raw_html": landing_table.get('_raw_html_content', ''),
        "landing_ai_error_html": landing_table.get('_error_html_content', ''),
        "pymupdf_matched_tables": [
            {
                "markdown": t.get('markdown', ''),
                "row_count": t.get('row_count', 0),
                "col_count": t.get('col_count', 0)
            }
            for t in matched_pymupdf_tables
        ],
        "corrections_applied": corrections_applied,
        "violations": [
            {
                "check_id": v.check_id if hasattr(v, 'check_id') else v.get('check_id', ''),
                "description": v.description if hasattr(v, 'description') else v.get('description', '')
            }
            for v in violations
        ] if violations else []
    }
    
    # Save to JSON
    debug_file = tmp_dir / f"{pdf_name}_page{page_num}_table{table_id}_{phase}_debug.json"
    with open(debug_file, 'w', encoding='utf-8') as f:
        json.dump(debug_info, f, indent=2, ensure_ascii=False)


# Save HTML versions for comparison
def save_html_versions(
    landing_table: dict,
    table_id: str,
    page_num: int,
    pdf_name: str
) -> None:
    """Save different HTML versions of the table for visual comparison."""
    tmp_dir = Path(__file__).parent / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    
    base_name = f"{pdf_name}_page{page_num}_table{table_id}"
    
    # Save original if exists
    if '_raw_html_content' in landing_table:
        html_file = tmp_dir / f"{base_name}_original.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(f"<html><body>{landing_table['_raw_html_content']}</body></html>")
    
    # Save current version
    html_file = tmp_dir / f"{base_name}_current.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(f"<html><body>{landing_table.get('html_content', '')}</body></html>")
    
    # Save error version if exists
    if '_error_html_content' in landing_table:
        html_file = tmp_dir / f"{base_name}_error.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(f"<html><body>{landing_table['_error_html_content']}</body></html>")

