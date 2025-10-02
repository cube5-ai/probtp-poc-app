"""
Enhanced parsing pipeline combining LandingAI (OCR) with PyMuPDF4LLM (deterministic text extraction).

Uses TF-IDF + fuzzy matching to:
1. Find potential matches for each table line using TF-IDF (fast semantic search)
2. Refine matches with fuzzy matching (character-level accuracy)
3. Correct OCR errors in LandingAI output using PyMuPDF text
"""
import html
import json
import os
import re

import numpy as np
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

from landing_ai_solo import parse_document as parse_document_solo  # type: ignore
from pymupdf4llm_solo import parse_document as parse_document_pymupdf4llm  # type: ignore

# Load parsed documents from cache or parse fresh
def load_landing_ai_document(file_path: str) -> dict:
    """Load LandingAI parsed document from cache."""
    document_name = os.path.basename(file_path).replace(".pdf", "")
    cache_path = f"../output/landing_ai_solo/{document_name}.json"

    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    # Parse fresh if not cached
    parse_response = parse_document_solo(file_path)
    parse_response_dict = json.loads(parse_response.model_dump_json())
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(parse_response_dict, f, indent=2, ensure_ascii=False)
    return parse_response_dict


def load_pymupdf_document(file_path: str) -> dict:
    """Load PyMuPDF parsed document."""
    return parse_document_pymupdf4llm(file_path)


# Extract table lines from both parsers
def extract_table_lines_from_landing_ai(chunk: dict) -> list[str]:
    """
    Extract individual table lines from LandingAI table chunks.
    Handles merged cells (colspan/rowspan) by duplicating content.
    
    Example:
        HTML: <td colspan="2">A</td><td>B</td>
        Output: "A A B"
        
        HTML: <td rowspan="2">X</td><td>Y</td>
        Row 1: "X Y"
        Row 2: "X <cells from row 2>"
    """
    if chunk.get('type') != 'table':
        return []

    markdown = chunk.get('markdown', '')

    # Parse HTML table to handle merged cells
    # Extract table rows
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', markdown, re.DOTALL)

    table_lines = []
    pending_rowspans: list[list[str]] = []  # Each element is cells to add to that future row

    for _row_idx, row_html in enumerate(rows):
        # Find all cells (td or th) with their attributes
        cells = re.findall(r'<(td|th)([^>]*)>(.*?)</\1>', row_html, re.DOTALL)

        row_cells = []

        # Add cells from previous rowspans first
        if pending_rowspans:
            row_cells.extend(pending_rowspans[0])
            pending_rowspans.pop(0)

        for _cell_type, attributes, content in cells:
            # Extract text content
            cell_text = re.sub(r'<[^>]+>', ' ', content)
            cell_text = html.unescape(cell_text).strip()

            # Check for colspan
            colspan_match = re.search(r'colspan["\s]*=["\s]*["\']?(\d+)', attributes)
            colspan = int(colspan_match.group(1)) if colspan_match else 1

            # Check for rowspan
            rowspan_match = re.search(r'rowspan["\s]*=["\s]*["\']?(\d+)', attributes)
            rowspan = int(rowspan_match.group(1)) if rowspan_match else 1

            # Duplicate cell content for colspan
            for _ in range(colspan):
                row_cells.append(cell_text)

            # If rowspan > 1, schedule content for future rows
            if rowspan > 1:
                for future_offset in range(1, rowspan):
                    # Ensure buffer has enough slots
                    while len(pending_rowspans) < future_offset:
                        pending_rowspans.append([])
                    # Add content for each colspan position
                    for _ in range(colspan):
                        pending_rowspans[future_offset - 1].append(cell_text)

        # Join cells with space and add to lines
        if row_cells:
            table_lines.append(' '.join(row_cells))

    return table_lines


def extract_table_lines_from_pymupdf(chunk: dict) -> list[str]:
    """Extract individual table lines from PyMuPDF output."""
    content = chunk.get('content', '')

    # Look for table markers (markdown tables use |)
    lines = content.split('\n')
    table_lines = []

    for line in lines:
        line = line.strip()
        if '|' in line:  # Table row
            # Extract cell content
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            if cells:
                table_lines.append(' '.join(cells))

    return table_lines


def extract_all_table_lines_by_page(response: dict, parser_type: str) -> dict[int, list[dict]]:
    """
    Extract all table lines grouped by page.

    Returns:
        Dict mapping page number to list of dicts with structure:
        {
            'line': str,
            'chunk_index': int,
            'line_index': int,
            'chunk': dict (original chunk)
        }
    """
    extractor = (extract_table_lines_from_landing_ai
                 if parser_type == 'landing_ai'
                 else extract_table_lines_from_pymupdf)

    pages: dict[int, list[dict]] = {}

    for chunk_idx, chunk in enumerate(response.get('chunks', [])):
        # Get page number
        if parser_type == 'landing_ai':
            page = chunk.get('grounding', {}).get('page')
            if page is None or chunk.get('type') != 'table':
                continue
        else:  # pymupdf
            page = chunk.get('metadata', {}).get('pageRange', {}).get('start')
            if page is None:
                continue
            page -= 1  # Convert to 0-indexed to match LandingAI

        # Extract lines
        lines = extractor(chunk)

        if page not in pages:
            pages[page] = []

        for line_idx, line in enumerate(lines):
            pages[page].append({
                'line': line,
                'chunk_index': chunk_idx,
                'line_index': line_idx,
                'chunk': chunk
            })

    return pages


class TableLineMatcher:
    """Two-step table line matcher using TF-IDF + fuzzy matching."""

    def __init__(self, min_ngram: int = 1, max_ngram: int = 2):
        self.vectorizer = TfidfVectorizer(
            ngram_range=(min_ngram, max_ngram),
            lowercase=True,
            analyzer='word',
            token_pattern=r'\b\w+\b'
        )
        self.tfidf_matrix = None
        self.reference_lines: list[str] = []

    def fit(self, reference_lines: list[str]):
        """Fit TF-IDF vectorizer on reference lines (PyMuPDF)."""
        self.reference_lines = reference_lines
        if not reference_lines:
            return
        self.tfidf_matrix = self.vectorizer.fit_transform(reference_lines)

    def find_matches(
        self,
        query_line: str,
        top_k: int = 5,
        tfidf_threshold: float = 0.1,
        fuzzy_threshold: float = 70.0
    ) -> list[dict]:
        """
        Find matching lines using TF-IDF + fuzzy matching.

        Args:
            query_line: LandingAI table line to match
            top_k: Number of TF-IDF candidates to consider
            tfidf_threshold: Minimum TF-IDF cosine similarity
            fuzzy_threshold: Minimum fuzzy matching score

        Returns:
            List of matches with scores, sorted by fuzzy score
        """
        if not self.reference_lines or self.tfidf_matrix is None:
            return []

        # Step 1: TF-IDF to find top-k candidates
        query_vec = self.vectorizer.transform([query_line])
        cosine_similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        # Get top-k candidates above threshold
        candidate_indices = np.argsort(cosine_similarities)[::-1][:top_k]
        candidates = [
            (idx, cosine_similarities[idx])
            for idx in candidate_indices
            if cosine_similarities[idx] >= tfidf_threshold
        ]

        if not candidates:
            return []

        # Step 2: Fuzzy matching refinement
        matches = []
        for idx, tfidf_score in candidates:
            reference_line = self.reference_lines[idx]
            fuzzy_score = fuzz.token_set_ratio(query_line, reference_line)

            if fuzzy_score >= fuzzy_threshold:
                matches.append({
                    'reference_index': idx,
                    'reference_line': reference_line,
                    'tfidf_score': float(tfidf_score),
                    'fuzzy_score': float(fuzzy_score),
                    'combined_score': float(tfidf_score * 0.3 + fuzzy_score * 0.7)  # Weighted
                })

        # Sort by fuzzy score (more reliable for final ranking)
        matches.sort(key=lambda x: x['fuzzy_score'], reverse=True)
        return matches


def match_table_lines_by_page(
    landing_ai_response: dict,
    pymupdf_response: dict,
    top_k: int = 5,
    tfidf_threshold: float = 0.1,
    fuzzy_threshold: float = 70.0
) -> dict[int, list[dict]]:
    """
    Match table lines between LandingAI and PyMuPDF page by page.

    Returns:
        Dict mapping page number to list of matches:
        {
            'landing_ai_line': dict,
            'matches': list[dict],
            'best_match': dict or None
        }
    """
    # Extract lines by page
    landing_pages = extract_all_table_lines_by_page(landing_ai_response, 'landing_ai')
    pymupdf_pages = extract_all_table_lines_by_page(pymupdf_response, 'pymupdf')

    results = {}

    for page_num in landing_pages:
        landing_lines = landing_pages[page_num]
        pymupdf_lines = pymupdf_pages.get(page_num, [])

        if not pymupdf_lines:
            # No PyMuPDF reference for this page
            results[page_num] = [
                {
                    'landing_ai_line': la_line,
                    'matches': [],
                    'best_match': None
                }
                for la_line in landing_lines
            ]
            continue

        # Build TF-IDF index for this page's PyMuPDF lines
        matcher = TableLineMatcher()
        pymupdf_line_texts = [line['line'] for line in pymupdf_lines]
        matcher.fit(pymupdf_line_texts)

        # Match each LandingAI line
        page_matches = []
        for la_line in landing_lines:
            matches = matcher.find_matches(
                la_line['line'],
                top_k=top_k,
                tfidf_threshold=tfidf_threshold,
                fuzzy_threshold=fuzzy_threshold
            )

            # Enrich matches with full PyMuPDF line info
            enriched_matches = []
            for match in matches:
                pymupdf_line = pymupdf_lines[match['reference_index']]
                enriched_matches.append({
                    **match,
                    'pymupdf_line': pymupdf_line
                })

            page_matches.append({
                'landing_ai_line': la_line,
                'matches': enriched_matches,
                'best_match': enriched_matches[0] if enriched_matches else None
            })

        results[page_num] = page_matches

    return results

# %%
# Example usage and testing

# if __name__ == "__main__":
# Load test document
document_name = "File #2 - Laurent M - tableau garantie fm 2025 word.pdf"
file_path = "../documents/" + document_name

print("Loading documents...")
landing_ai_response = load_landing_ai_document(file_path)
pymupdf_response = load_pymupdf_document(file_path)
print(f"✓ Loaded {len(landing_ai_response.get('chunks', []))} LandingAI chunks")
print(f"✓ Loaded {len(pymupdf_response.get('chunks', []))} PyMuPDF chunks")

# %%
# Match table lines using TF-IDF + fuzzy matching
table_matches = match_table_lines_by_page(
    landing_ai_response,
    pymupdf_response,
    top_k=3,
    tfidf_threshold=0.05,
    fuzzy_threshold=65.0
)

# %%
# Print summary statistics
total_landing_lines = sum(len(matches) for matches in table_matches.values())
matched_lines = sum(
    sum(1 for m in matches if m['best_match'] is not None)
    for matches in table_matches.values()
)

print("\n" + "="*100)
print("TABLE LINE MATCHING RESULTS (TF-IDF + Fuzzy)")
print("="*100)
print(f"Total LandingAI table lines: {total_landing_lines}")
print(f"Lines with matches: {matched_lines}")
print(f"Match rate: {matched_lines/total_landing_lines*100:.1f}%" if total_landing_lines > 0 else "N/A")

# %%
# Show detailed examples from first page with tables
for page_num in sorted(table_matches.keys())[:2]:
    print(f"\n{'='*100}")
    print(f"PAGE {page_num} - Sample Matches")
    print(f"{'='*100}")

    for i, match_info in enumerate(table_matches[page_num][:5]):
        la_line = match_info['landing_ai_line']['line']
        best_match = match_info['best_match']

        print(f"\n--- LandingAI Line {i+1} ---")
        print(f"Text: {la_line[:100]}...")

        if best_match:
            print(f"  ✓ Match (TF-IDF: {best_match['tfidf_score']:.3f}, Fuzzy: {best_match['fuzzy_score']:.1f})")
            print(f"  PyMuPDF: {best_match['reference_line'][:100]}...")

            # Highlight potential OCR corrections
            if best_match['fuzzy_score'] < 100:
                print(f"  → Potential OCR correction (confidence: {best_match['fuzzy_score']:.1f}%)")
        else:
            print("  ✗ No match found")

# %%
