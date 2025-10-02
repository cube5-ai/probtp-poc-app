"""Phase 2: Match Tables using TF-IDF."""
import html
import re

import numpy as np
from langfuse import observe
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Clean cell content for TF-IDF matching
def clean_cell_content(text: str) -> str:
    """
    Clean cell content for matching.
    Returns "-" for empty cells to ensure consistent representation.
    """
    if not text or not isinstance(text, str):
        return "-"

    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Convert line breaks to space
    text = text.replace('\n', ' ').replace('\r', ' ')
    # Remove LaTeX markers
    text = re.sub(r'\{#[^}]*\}', '', text)
    # Add space after % followed by letters
    text = re.sub(r'%([a-zA-Z])', r'% \1', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    # Trim
    text = text.strip()
    # Unescape HTML entities
    text = html.unescape(text)
    # Empty cells get "-" as default character
    if len(text) <= 1 and not text.isalnum():
        return "-"

    return text


# Extract bag of words from table
def extract_bag_of_words(table_content: str) -> str:
    """
    Extract all text from table content (HTML or markdown) as bag of words.
    Filters out empty cell placeholders ("-") to avoid affecting TF-IDF matching.
    """
    # Parse HTML/markdown to extract all text
    if '<tr' in table_content:
        # HTML table
        cells = re.findall(r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>', table_content, re.DOTALL)
        cleaned_cells = [clean_cell_content(cell) for cell in cells]
    else:
        # Markdown table
        lines = table_content.split('\n')
        cleaned_cells = []
        for line in lines:
            if '|' in line:
                cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                cleaned_cells.extend([clean_cell_content(cell) for cell in cells])

    # Filter out empty cell placeholders and truly empty cells
    return ' '.join(cell for cell in cleaned_cells if cell and cell != "-")


# Match tables using TF-IDF
@observe()
def match_tables_on_page(
    landing_tables: list[dict],
    pymupdf_tables: list[dict],
    similarity_threshold: float = 0.3,
    word_count_multiplier: float = 3.0
) -> dict[int, list[int]]:
    """
    Match Landing AI tables to PyMuPDF tables using TF-IDF.

    Returns:
        Dict mapping Landing AI table index to list of matched PyMuPDF table indices
    """
    if not landing_tables or not pymupdf_tables:
        return {}

    # Extract bag of words for all tables
    landing_bow = [extract_bag_of_words(t['html_content']) for t in landing_tables]
    pymupdf_bow = [extract_bag_of_words(t['markdown']) for t in pymupdf_tables]

    # Build TF-IDF vectors
    all_texts = landing_bow + pymupdf_bow
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), lowercase=True)

    try:
        tfidf_matrix = vectorizer.fit_transform(all_texts)
    except ValueError:
        # No valid text to vectorize
        return {}

    # Split back into landing and pymupdf matrices
    landing_vectors = tfidf_matrix[:len(landing_tables)]
    pymupdf_vectors = tfidf_matrix[len(landing_tables):]

    # Calculate cosine similarities
    similarities = cosine_similarity(landing_vectors, pymupdf_vectors)

    # Match each Landing AI table
    matches: dict[int, list[int]] = {}

    for landing_idx in range(len(landing_tables)):
        landing_word_count = len(landing_bow[landing_idx].split())
        candidate_matches = []

        for pymupdf_idx in range(len(pymupdf_tables)):
            sim = similarities[landing_idx, pymupdf_idx]

            if sim < similarity_threshold:
                continue

            pymupdf_word_count = len(pymupdf_bow[pymupdf_idx].split())

            # Check word count constraint
            if pymupdf_word_count > word_count_multiplier * landing_word_count:
                continue

            candidate_matches.append((pymupdf_idx, sim))

        # Sort by similarity and take matches
        candidate_matches.sort(key=lambda x: x[1], reverse=True)
        matches[landing_idx] = [idx for idx, _ in candidate_matches]

    return matches

