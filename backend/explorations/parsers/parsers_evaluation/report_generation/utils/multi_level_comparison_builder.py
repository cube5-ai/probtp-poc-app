"""Build multi-level comparison documents for policy recommendation pipeline.

This module creates comparison documents where:
- Multiple vendor A levels are compared against a single vendor B level
- Values use simplified schema (base_value + detailed_value)
"""

from typing import Any

from pydantic import BaseModel, Field


class MultiLevelLeafComparison(BaseModel):
    """Comparison of multiple vendor A levels vs single vendor B level for one taxonomy leaf."""

    leaf_id: str = Field(..., description="Taxonomy leaf ID")
    path: list[str] = Field(..., description="Taxonomy path")
    description: str = Field(..., description="Leaf description")
    securite_sociale_coverage: str | None = Field(None, description="Social Security coverage")

    # Multi-level vendor A values (one entry per level)
    vendor_a_ref_values: dict[str, dict[str, Any]] = Field(
        ...,
        description="Vendor A values by level (key: level like 'S1', value: {base_value, detailed_value, source_cell_ids, notes})"
    )

    # Single vendor B value
    vendor_b_value: dict[str, Any] | None = Field(
        None,
        description="Vendor B value: {base_value, detailed_value, source_cell_ids, notes}"
    )

    # Flags
    is_unmappable_vendor_a_ref_only: bool = Field(default=False)
    is_unmappable_vendor_b_only: bool = Field(default=False)


class MultiLevelComparisonDocument(BaseModel):
    """Multi-level comparison document for a category."""

    category_id: str = Field(..., description="Category ID")
    category_name: str = Field(..., description="Category name")
    vendor_a_ref_policy_levels: list[str] = Field(..., description="Vendor A policy levels (e.g., ['S1', 'S2', 'S3', 'S4', 'S5'])")
    vendor_b_policy_level: str = Field(..., description="Vendor B policy level")
    vendor_a_ref_name: str = Field(..., description="Vendor A name")
    vendor_b_name: str = Field(..., description="Vendor B name")

    leaves: list[MultiLevelLeafComparison] = Field(..., description="Leaf-based comparisons")


def build_multi_level_comparison_document(
    category_taxonomy: dict[str, Any],
    vendor_a_ref_multi_level_extraction: dict[str, Any],
    vendor_b_multi_level_extraction: dict[str, Any],
    vendor_b_target_level: str,
    vendor_a_ref_name: str,
    vendor_b_name: str,
) -> MultiLevelComparisonDocument:
    """Build multi-level comparison document from taxonomy and extractions.

    Args:
        category_taxonomy: Taxonomy category dict with leaves
        vendor_a_ref_multi_level_extraction: Multi-level extraction for vendor A (contains values for ALL levels)
        vendor_b_multi_level_extraction: Multi-level extraction for vendor B (contains values for ALL levels)
        vendor_b_target_level: The specific vendor B level to use in comparison
        vendor_a_ref_name: Vendor A name
        vendor_b_name: Vendor B name

    Returns:
        Multi-level comparison document
    """
    category_id = category_taxonomy["node_id"]
    category_name = category_taxonomy.get("category_name") or category_taxonomy["name"]
    category_leaves = category_taxonomy.get("leaves", [])

    # Extract policy levels
    vendor_a_ref_levels = vendor_a_ref_multi_level_extraction.get("policy_levels", [])
    vendor_b_all_levels = vendor_b_multi_level_extraction.get("policy_levels", [])

    # Build lookup maps
    # New structure: extracted_values contains {leaf_id, values: [{level, base_value, detailed_value, ...}]}
    vendor_a_ref_values_by_leaf = {}
    for extracted_value in vendor_a_ref_multi_level_extraction.get("extracted_values", []):
        leaf_id = extracted_value["leaf_id"]
        values = extracted_value.get("values", [])

        # Convert list of Value objects to dict keyed by level
        values_dict = {}
        for value_obj in values:
            level = value_obj.get("level")
            if level:
                values_dict[level] = {
                    "base_value": value_obj.get("base_value", ""),
                    "detailed_value": value_obj.get("detailed_value", ""),
                    "source_cell_ids": value_obj.get("source_cell_ids"),
                    "notes": value_obj.get("notes"),
                }

        vendor_a_ref_values_by_leaf[leaf_id] = values_dict

    vendor_b_values_by_leaf = {}
    for extracted_value in vendor_b_multi_level_extraction.get("extracted_values", []):
        leaf_id = extracted_value["leaf_id"]
        values = extracted_value.get("values", [])

        # For vendor B, extract only the target level from all extracted levels
        # Use fuzzy matching: exact match first, then substring match
        matched_value = None
        for value_obj in values:
            level = value_obj.get("level", "")
            if level == vendor_b_target_level:
                # Exact match (preferred)
                matched_value = value_obj
                break
            elif vendor_b_target_level.lower() in level.lower():
                # Fuzzy match (fallback)
                matched_value = value_obj

        if matched_value:
            vendor_b_values_by_leaf[leaf_id] = {
                "base_value": matched_value.get("base_value", ""),
                "detailed_value": matched_value.get("detailed_value", ""),
                "source_cell_ids": matched_value.get("source_cell_ids"),
                "notes": matched_value.get("notes"),
            }

    # Build leaf comparisons
    leaf_comparisons = []
    for leaf in category_leaves:
        leaf_id = leaf["leaf_id"]

        # Get values dict for vendor A (already structured by level)
        vendor_a_ref_values_dict = vendor_a_ref_values_by_leaf.get(leaf_id, {})
        vendor_b_value_data = vendor_b_values_by_leaf.get(leaf_id)

        leaf_comparison = MultiLevelLeafComparison(
            leaf_id=leaf_id,
            path=leaf["path"],
            description=leaf["description"],
            securite_sociale_coverage=leaf.get("securite_sociale_coverage"),
            vendor_a_ref_values=vendor_a_ref_values_dict,
            vendor_b_value=vendor_b_value_data,
            is_unmappable_vendor_a_ref_only=False,
            is_unmappable_vendor_b_only=False,
        )

        leaf_comparisons.append(leaf_comparison)

    # Handle unmappable items from vendor A
    for unmappable in vendor_a_ref_multi_level_extraction.get("unmappable_items", []) or []:
        leaf_id = unmappable["suggested_leaf_id"]
        values = unmappable.get("values", [])

        # Convert list of Value objects to dict keyed by level
        vendor_a_ref_values_dict = {}
        for value_obj in values:
            level = value_obj.get("level")
            if level:
                vendor_a_ref_values_dict[level] = {
                    "base_value": value_obj.get("base_value", ""),
                    "detailed_value": value_obj.get("detailed_value", ""),
                    "source_cell_ids": value_obj.get("source_cell_ids"),
                    "notes": value_obj.get("notes"),
                }

        leaf_comparison = MultiLevelLeafComparison(
            leaf_id=leaf_id,
            path=unmappable["suggested_path"],
            description=unmappable["description"],
            securite_sociale_coverage=None,
            vendor_a_ref_values=vendor_a_ref_values_dict,
            vendor_b_value=None,
            is_unmappable_vendor_a_ref_only=True,
            is_unmappable_vendor_b_only=False,
        )
        leaf_comparisons.append(leaf_comparison)

    # Handle unmappable items from vendor B
    for unmappable in vendor_b_multi_level_extraction.get("unmappable_items", []) or []:
        leaf_id = unmappable["suggested_leaf_id"]
        values = unmappable.get("values", [])

        # For vendor B, extract only the target level (use fuzzy matching)
        vendor_b_value_data = None
        matched_value = None
        for value_obj in values:
            level = value_obj.get("level", "")
            if level == vendor_b_target_level:
                # Exact match (preferred)
                matched_value = value_obj
                break
            elif vendor_b_target_level.lower() in level.lower():
                # Fuzzy match (fallback)
                matched_value = value_obj

        if matched_value:
            vendor_b_value_data = {
                "base_value": matched_value.get("base_value", ""),
                "detailed_value": matched_value.get("detailed_value", ""),
                "source_cell_ids": matched_value.get("source_cell_ids"),
                "notes": matched_value.get("notes"),
            }

        leaf_comparison = MultiLevelLeafComparison(
            leaf_id=leaf_id,
            path=unmappable["suggested_path"],
            description=unmappable["description"],
            securite_sociale_coverage=None,
            vendor_a_ref_values={},
            vendor_b_value=vendor_b_value_data,
            is_unmappable_vendor_a_ref_only=False,
            is_unmappable_vendor_b_only=True,
        )
        leaf_comparisons.append(leaf_comparison)

    return MultiLevelComparisonDocument(
        category_id=category_id,
        category_name=category_name,
        vendor_a_ref_policy_levels=vendor_a_ref_levels,
        vendor_b_policy_level=vendor_b_target_level,
        vendor_a_ref_name=vendor_a_ref_name,
        vendor_b_name=vendor_b_name,
        leaves=leaf_comparisons,
    )
