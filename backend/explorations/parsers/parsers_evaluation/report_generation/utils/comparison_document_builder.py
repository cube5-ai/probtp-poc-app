"""Build comparison document from taxonomy and value extractions.

This module creates a leaf-based comparison document that pairs vendor A and vendor B values
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
    """Comparison of vendor A and vendor B values for a single taxonomy leaf."""

    leaf_id: str = Field(..., description="Taxonomy leaf ID (e.g., 'optique_lunettes_monture')")
    path: list[str] = Field(..., description="Taxonomy path (e.g., ['Optique', 'Lunettes', 'Monture'])")
    description: str = Field(..., description="Leaf description")
    securite_sociale_coverage: str | None = Field(None, description="Social Security coverage (e.g., '0€', '70% BRSS')")

    # Full ExtractedValue objects with all fields
    vendor_a_ref: ExtractedValue | None = Field(None, description="Vendor A (reference) extracted value (None if not covered or unmappable)")
    vendor_b: ExtractedValue | None = Field(None, description="Vendor B extracted value (None if not covered or unmappable)")

    # Flags for unmappable items
    is_unmappable_vendor_a_ref_only: bool = Field(
        default=False, description="True if this leaf is from vendor A unmappable items"
    )
    is_unmappable_vendor_b_only: bool = Field(
        default=False, description="True if this leaf is from vendor B unmappable items"
    )


class ComparisonDocument(BaseModel):
    """Leaf-based comparison document for a category."""

    category_id: str = Field(..., description="Category ID (e.g., 'optique', 'hospitalisation')")
    category_name: str = Field(..., description="Category display name (e.g., 'Optique')")
    vendor_a_ref_policy_level: str = Field(..., description="Vendor A (reference) policy level (e.g., 'S2')")
    vendor_b_policy_level: str = Field(..., description="Vendor B policy level (e.g., 'Base Obligatoire')")
    vendor_a_ref_name: str = Field(..., description="Vendor A (reference) name (e.g., 'ProBTP')")
    vendor_b_name: str = Field(..., description="Vendor B name (e.g., 'Generali')")

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
    vendor_a_ref_extraction: CategoryValueExtraction | dict,
    vendor_b_extraction: CategoryValueExtraction | dict,
    vendor_a_ref_name: str,
    vendor_b_name: str,
) -> ComparisonDocument:
    """
    Build comparison document from taxonomy and extractions.

    Args:
        category_taxonomy: Taxonomy category dict with leaves
        vendor_a_ref_extraction: Vendor A (reference) CategoryValueExtraction (or dict)
        vendor_b_extraction: Vendor B CategoryValueExtraction (or dict)
        vendor_a_ref_name: Vendor A name (e.g., "ProBTP")
        vendor_b_name: Vendor B name (e.g., "Generali")

    Returns:
        ComparisonDocument with leaf-based comparisons
    """
    # Validate inputs if they're dicts (with backward compatibility fixes)
    if isinstance(vendor_a_ref_extraction, dict):
        vendor_a_ref_extraction = _fix_extraction_dict(vendor_a_ref_extraction)
        vendor_a_ref_extraction = CategoryValueExtraction.model_validate(vendor_a_ref_extraction)
    if isinstance(vendor_b_extraction, dict):
        vendor_b_extraction = _fix_extraction_dict(vendor_b_extraction)
        vendor_b_extraction = CategoryValueExtraction.model_validate(vendor_b_extraction)

    # Create lookup maps for extracted values by leaf_id
    vendor_a_ref_map: dict[str, ExtractedValue] = {
        ev.leaf_id: ev for ev in vendor_a_ref_extraction.extracted_values
    }
    vendor_b_map: dict[str, ExtractedValue] = {
        ev.leaf_id: ev for ev in vendor_b_extraction.extracted_values
    }

    # Build leaf comparisons from taxonomy
    leaf_comparisons: list[LeafComparison] = []

    # Process taxonomy leaves
    for leaf in category_taxonomy.get("leaves", []):
        leaf_id = leaf["leaf_id"]
        vendor_a_ref_value = vendor_a_ref_map.get(leaf_id)
        vendor_b_value = vendor_b_map.get(leaf_id)

        # Skip if neither vendor has this leaf (shouldn't happen in taxonomy)
        if not vendor_a_ref_value and not vendor_b_value:
            continue

        leaf_comparisons.append(
            LeafComparison(
                leaf_id=leaf_id,
                path=leaf["path"],
                description=leaf["description"],
                securite_sociale_coverage=leaf.get("securite_sociale_coverage"),
                vendor_a_ref=vendor_a_ref_value,
                vendor_b=vendor_b_value,
                is_unmappable_vendor_a_ref_only=False,
                is_unmappable_vendor_b_only=False,
            )
        )

    # Process vendor A unmappable items (only those matching current category)
    category_id = vendor_a_ref_extraction.category_id
    if vendor_a_ref_extraction.unmappable_items:
        for unmappable in vendor_a_ref_extraction.unmappable_items:
            # Filter: only include unmappable items that belong to current category
            unmappable_dict = unmappable if isinstance(unmappable, dict) else unmappable.model_dump()
            if unmappable_dict.get("suggested_category_id") == category_id:
                leaf_comparisons.append(_unmappable_to_leaf_comparison(unmappable, vendor="vendor_a_ref"))

    # Process vendor B unmappable items (only those matching current category)
    if vendor_b_extraction.unmappable_items:
        for unmappable in vendor_b_extraction.unmappable_items:
            # Filter: only include unmappable items that belong to current category
            unmappable_dict = unmappable if isinstance(unmappable, dict) else unmappable.model_dump()
            if unmappable_dict.get("suggested_category_id") == category_id:
                leaf_comparisons.append(_unmappable_to_leaf_comparison(unmappable, vendor="vendor_b"))

    return ComparisonDocument(
        category_id=vendor_a_ref_extraction.category_id,
        category_name=category_taxonomy.get("category_name", vendor_a_ref_extraction.category_id),
        vendor_a_ref_policy_level=vendor_a_ref_extraction.policy_level,
        vendor_b_policy_level=vendor_b_extraction.policy_level,
        vendor_a_ref_name=vendor_a_ref_name,
        vendor_b_name=vendor_b_name,
        leaves=leaf_comparisons,
    )


def _unmappable_to_leaf_comparison(unmappable: UnmappableItem | dict, vendor: str) -> LeafComparison:
    """
    Convert unmappable item to a LeafComparison with appropriate flags.

    Args:
        unmappable: UnmappableItem from extraction (or dict)
        vendor: "vendor_a_ref" or "vendor_b"

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
        frequency=unmappable.frequency,
        cap=unmappable.cap,
        age_restriction=unmappable.age_restriction,
        other_universal_conditions=unmappable.other_universal_conditions,
        vendor_conditions=unmappable.vendor_conditions,
        notes=f"Unmappable: {unmappable.reasoning}",
        display_text=unmappable.display_text,
    )

    return LeafComparison(
        leaf_id=unmappable.suggested_leaf_id,
        path=unmappable.suggested_path,
        description=unmappable.description,
        securite_sociale_coverage=None,
        vendor_a_ref=extracted_value if vendor == "vendor_a_ref" else None,
        vendor_b=extracted_value if vendor == "vendor_b" else None,
        is_unmappable_vendor_a_ref_only=(vendor == "vendor_a_ref"),
        is_unmappable_vendor_b_only=(vendor == "vendor_b"),
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
            "is_unmappable_vendor_a_ref_only": leaf.is_unmappable_vendor_a_ref_only,
            "is_unmappable_vendor_b_only": leaf.is_unmappable_vendor_b_only,
        }

        # Strip source_cell_ids from extracted values
        if leaf.vendor_a_ref:
            vendor_a_ref_dict = leaf.vendor_a_ref.model_dump(exclude={"source_cell_ids"}, exclude_none=True)
            leaf_dict["vendor_a_ref"] = vendor_a_ref_dict

        if leaf.vendor_b:
            vendor_b_dict = leaf.vendor_b.model_dump(exclude={"source_cell_ids"}, exclude_none=True)
            leaf_dict["vendor_b"] = vendor_b_dict

        leaves_simplified.append(leaf_dict)

    return {
        "category_id": comparison_doc.category_id,
        "category_name": comparison_doc.category_name,
        "vendor_a_ref_policy_level": comparison_doc.vendor_a_ref_policy_level,
        "vendor_b_policy_level": comparison_doc.vendor_b_policy_level,
        "vendor_a_ref_name": comparison_doc.vendor_a_ref_name,
        "vendor_b_name": comparison_doc.vendor_b_name,
        "leaves": leaves_simplified,
    }
