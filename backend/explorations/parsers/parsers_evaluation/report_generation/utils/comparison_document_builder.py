"""Build comparison document from taxonomy and value extractions.

This module creates a leaf-based comparison document that pairs ProBTP and AXA values
for each taxonomy leaf, making it suitable for LLM-based analysis.
"""

from pydantic import BaseModel, Field

from prompts.taxonomy_first.value_extraction_prompt import (
    CategoryValueExtraction,
    ExtractedValue,
    UnmappableItem,
    VendorCondition,
)


class LeafComparison(BaseModel):
    """Comparison of ProBTP and AXA values for a single taxonomy leaf."""

    leaf_id: str = Field(..., description="Taxonomy leaf ID (e.g., 'optique_lunettes_monture')")
    path: list[str] = Field(..., description="Taxonomy path (e.g., ['Optique', 'Lunettes', 'Monture'])")
    description: str = Field(..., description="Leaf description")
    securite_sociale_coverage: str | None = Field(None, description="Social Security coverage (e.g., '0€', '70% BRSS')")

    # Full ExtractedValue objects with all fields
    probtp: ExtractedValue | None = Field(None, description="ProBTP extracted value (None if not covered or unmappable)")
    axa: ExtractedValue | None = Field(None, description="AXA extracted value (None if not covered or unmappable)")

    # Flags for unmappable items
    is_unmappable_probtp_only: bool = Field(
        default=False, description="True if this leaf is from ProBTP unmappable items"
    )
    is_unmappable_axa_only: bool = Field(
        default=False, description="True if this leaf is from AXA unmappable items"
    )


class ComparisonDocument(BaseModel):
    """Leaf-based comparison document for a category."""

    category_id: str = Field(..., description="Category ID (e.g., 'optique', 'hospitalisation')")
    category_name: str = Field(..., description="Category display name (e.g., 'Optique')")
    probtp_policy_level: str = Field(..., description="ProBTP policy level (e.g., 'S2')")
    axa_policy_level: str = Field(..., description="AXA policy level (e.g., 'Base Obligatoire')")

    leaves: list[LeafComparison] = Field(..., description="Leaf-based comparisons")


def _fix_extraction_dict(extraction: dict) -> dict:
    """
    Fix extraction dict for backward compatibility with old checkpoints.

    Adds missing suggested_parent_id to unmappable items.
    """
    if "unmappable_items" in extraction and extraction["unmappable_items"]:
        for item in extraction["unmappable_items"]:
            if "suggested_parent_id" not in item and "suggested_path" in item:
                path = item["suggested_path"]
                if len(path) > 1:
                    parent_name = path[-2]
                    item["suggested_parent_id"] = parent_name.lower().replace(" ", "_").replace("é", "e")
                else:
                    item["suggested_parent_id"] = "_root_"
    return extraction


def build_comparison_document(
    category_taxonomy: dict,
    probtp_extraction: CategoryValueExtraction | dict,
    axa_extraction: CategoryValueExtraction | dict,
) -> ComparisonDocument:
    """
    Build comparison document from taxonomy and extractions.

    Args:
        category_taxonomy: Taxonomy category dict with leaves
        probtp_extraction: ProBTP CategoryValueExtraction (or dict)
        axa_extraction: AXA CategoryValueExtraction (or dict)

    Returns:
        ComparisonDocument with leaf-based comparisons
    """
    # Validate inputs if they're dicts (with backward compatibility fixes)
    if isinstance(probtp_extraction, dict):
        probtp_extraction = _fix_extraction_dict(probtp_extraction)
        probtp_extraction = CategoryValueExtraction.model_validate(probtp_extraction)
    if isinstance(axa_extraction, dict):
        axa_extraction = _fix_extraction_dict(axa_extraction)
        axa_extraction = CategoryValueExtraction.model_validate(axa_extraction)

    # Create lookup maps for extracted values by leaf_id
    probtp_map: dict[str, ExtractedValue] = {
        ev.leaf_id: ev for ev in probtp_extraction.extracted_values
    }
    axa_map: dict[str, ExtractedValue] = {
        ev.leaf_id: ev for ev in axa_extraction.extracted_values
    }

    # Build leaf comparisons from taxonomy
    leaf_comparisons: list[LeafComparison] = []

    # Process taxonomy leaves
    for leaf in category_taxonomy.get("leaves", []):
        leaf_id = leaf["leaf_id"]
        probtp_value = probtp_map.get(leaf_id)
        axa_value = axa_map.get(leaf_id)

        # Skip if neither vendor has this leaf (shouldn't happen in taxonomy)
        if not probtp_value and not axa_value:
            continue

        leaf_comparisons.append(
            LeafComparison(
                leaf_id=leaf_id,
                path=leaf["path"],
                description=leaf["description"],
                securite_sociale_coverage=leaf.get("securite_sociale_coverage"),
                probtp=probtp_value,
                axa=axa_value,
                is_unmappable_probtp_only=False,
                is_unmappable_axa_only=False,
            )
        )

    # Process ProBTP unmappable items
    if probtp_extraction.unmappable_items:
        for unmappable in probtp_extraction.unmappable_items:
            leaf_comparisons.append(_unmappable_to_leaf_comparison(unmappable, vendor="probtp"))

    # Process AXA unmappable items
    if axa_extraction.unmappable_items:
        for unmappable in axa_extraction.unmappable_items:
            leaf_comparisons.append(_unmappable_to_leaf_comparison(unmappable, vendor="axa"))

    return ComparisonDocument(
        category_id=probtp_extraction.category_id,
        category_name=category_taxonomy.get("category_name", probtp_extraction.category_id),
        probtp_policy_level=probtp_extraction.policy_level,
        axa_policy_level=axa_extraction.policy_level,
        leaves=leaf_comparisons,
    )


def _unmappable_to_leaf_comparison(unmappable: UnmappableItem | dict, vendor: str) -> LeafComparison:
    """
    Convert unmappable item to a LeafComparison with appropriate flags.

    Args:
        unmappable: UnmappableItem from extraction (or dict)
        vendor: "probtp" or "axa"

    Returns:
        LeafComparison with unmappable flags set
    """
    # Handle dict input (for backward compatibility with old checkpoints)
    if isinstance(unmappable, dict):
        # Infer suggested_parent_id from path if missing
        if "suggested_parent_id" not in unmappable and "suggested_path" in unmappable:
            path = unmappable["suggested_path"]
            # Parent is second-to-last element converted to snake_case
            if len(path) > 1:
                parent_name = path[-2]
                unmappable["suggested_parent_id"] = parent_name.lower().replace(" ", "_").replace("é", "e")
            else:
                unmappable["suggested_parent_id"] = "_root_"
        unmappable = UnmappableItem.model_validate(unmappable)

    # Create synthetic ExtractedValue from unmappable item
    extracted_value = ExtractedValue(
        leaf_id=unmappable.suggested_leaf_id,
        coverage=unmappable.coverage,
        source_cell_ids=unmappable.source_cell_ids,
        notes=f"Unmappable: {unmappable.reasoning}",
    )

    return LeafComparison(
        leaf_id=unmappable.suggested_leaf_id,
        path=unmappable.suggested_path,
        description=unmappable.description,
        securite_sociale_coverage=None,
        probtp=extracted_value if vendor == "probtp" else None,
        axa=extracted_value if vendor == "axa" else None,
        is_unmappable_probtp_only=(vendor == "probtp"),
        is_unmappable_axa_only=(vendor == "axa"),
    )


def prepare_for_llm(comparison_doc: ComparisonDocument) -> dict:
    """
    Prepare comparison document for LLM consumption by stripping unnecessary fields.

    Args:
        comparison_doc: Full ComparisonDocument

    Returns:
        Simplified dict suitable for LLM prompt
    """
    leaves_simplified = []

    for leaf in comparison_doc.leaves:
        leaf_dict = {
            "leaf_id": leaf.leaf_id,
            "path": leaf.path,
            "description": leaf.description,
            "securite_sociale_coverage": leaf.securite_sociale_coverage,
            "is_unmappable_probtp_only": leaf.is_unmappable_probtp_only,
            "is_unmappable_axa_only": leaf.is_unmappable_axa_only,
        }

        # Strip source_cell_ids from extracted values
        if leaf.probtp:
            probtp_dict = leaf.probtp.model_dump(exclude={"source_cell_ids"}, exclude_none=True)
            leaf_dict["probtp"] = probtp_dict

        if leaf.axa:
            axa_dict = leaf.axa.model_dump(exclude={"source_cell_ids"}, exclude_none=True)
            leaf_dict["axa"] = axa_dict

        leaves_simplified.append(leaf_dict)

    return {
        "category_id": comparison_doc.category_id,
        "category_name": comparison_doc.category_name,
        "probtp_policy_level": comparison_doc.probtp_policy_level,
        "axa_policy_level": comparison_doc.axa_policy_level,
        "leaves": leaves_simplified,
    }
