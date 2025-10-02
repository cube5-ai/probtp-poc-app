"""Phase 5: Map Corrected Tables Back to Landing AI Response Structure."""


def map_to_landing_ai_response(
    original_landing_response: dict,
    corrected_tables_by_page: dict[int, list[dict]],
    phase3_tables_by_page: dict[int, list[dict]] | None = None,
    matches_by_page: dict[int, dict[int, list[int]]] | None = None,
    pymupdf_tables_by_page: dict[int, list[dict]] | None = None,
) -> dict:
    """
    Map corrected tables back to Landing AI response structure.

    Updates table chunks' markdown with corrected HTML and adds post_processing_metadata
    to track the correction history. Non-table chunks are preserved as-is.

    Args:
        original_landing_response: Original Landing AI API response with chunks
        corrected_tables_by_page: Final corrected tables after phase 4 (by page number)
        phase3_tables_by_page: Tables after phase 3 corrections (optional)
        matches_by_page: Matching info from phase 2 (optional)
        pymupdf_tables_by_page: PyMuPDF tables by page (optional, for matched content)

    Returns:
        Modified Landing AI response with updated markdown and metadata
    """
    # Create lookup: chunk_id -> corrected table
    corrected_by_chunk_id = {}
    phase3_by_chunk_id = {}

    for page_num, tables in corrected_tables_by_page.items():
        for table in tables:
            chunk_id = table.get("chunk_id")
            if chunk_id:
                corrected_by_chunk_id[chunk_id] = table

    # Build phase3 lookup if provided
    if phase3_tables_by_page:
        for page_num, tables in phase3_tables_by_page.items():
            for table in tables:
                chunk_id = table.get("chunk_id")
                if chunk_id:
                    phase3_by_chunk_id[chunk_id] = table

    # Create a deep copy to avoid modifying original
    import copy
    updated_response = copy.deepcopy(original_landing_response)

    # Process each chunk
    for chunk in updated_response.get("chunks", []):
        chunk_id = chunk.get("id")
        chunk_type = chunk.get("type")

        # Only process table chunks that were corrected
        if chunk_type != "table" or chunk_id not in corrected_by_chunk_id:
            continue

        corrected_table = corrected_by_chunk_id[chunk_id]
        phase3_table = phase3_by_chunk_id.get(chunk_id)

        # Store original markdown
        original_markdown = chunk.get("markdown", "")

        # Update markdown with corrected version
        chunk["markdown"] = corrected_table.get("html_content", original_markdown)

        # Build post_processing_metadata
        # Convert SanityViolation objects to dicts if needed
        sanity_violations = corrected_table.get("sanity_violations", [])
        violations_as_dicts = []
        for violation in sanity_violations:
            if hasattr(violation, "model_dump"):
                # Pydantic v2
                violations_as_dicts.append(violation.model_dump())
            elif hasattr(violation, "dict"):
                # Pydantic v1
                violations_as_dicts.append(violation.dict())
            elif isinstance(violation, dict):
                violations_as_dicts.append(violation)
            else:
                # Fallback: convert to dict manually
                violations_as_dicts.append({
                    "check_id": getattr(violation, "check_id", ""),
                    "description": getattr(violation, "description", ""),
                    "affected_cells": getattr(violation, "affected_cells", []),
                })

        metadata = {
            "original_markdown": original_markdown,
            "corrections_applied": corrected_table.get("corrections_applied", 0),
            "header_row_added": corrected_table.get("header_row_added", False),
            "visual_corrections_applied": corrected_table.get("visual_corrections_applied", False),
            "sanity_violations": violations_as_dicts,
        }

        # Add intermediate markdown versions with descriptive names
        if phase3_table:
            metadata["after_llm_corrections_markdown"] = phase3_table.get("html_content", "")

        # Add final version reference
        metadata["after_sanity_check_corrections_markdown"] = corrected_table.get("html_content", "")

        # Add matched PyMuPDF content if available
        if matches_by_page and pymupdf_tables_by_page:
            # Get page number from grounding
            page_num = chunk.get("grounding", {}).get("page")
            position_idx = corrected_table.get("position_in_page")

            if page_num is not None and position_idx is not None:
                matched_indices = matches_by_page.get(page_num, {}).get(position_idx, [])

                # Get matched PyMuPDF markdown content
                matched_pymupdf_content = []
                for idx in matched_indices:
                    pymupdf_tables = pymupdf_tables_by_page.get(page_num, [])
                    if idx < len(pymupdf_tables):
                        pymupdf_table = pymupdf_tables[idx]
                        matched_pymupdf_content.append({
                            "markdown": pymupdf_table.get("markdown", ""),
                            "table_index": idx,
                            "bbox": pymupdf_table.get("bbox"),
                        })

                metadata["matched_pymupdf_tables"] = matched_pymupdf_content

        # Add metadata to chunk
        chunk["post_processing_metadata"] = metadata

    return updated_response
