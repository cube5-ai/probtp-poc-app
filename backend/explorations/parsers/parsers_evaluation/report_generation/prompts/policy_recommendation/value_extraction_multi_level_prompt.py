"""Multi-level value extraction prompt for policy recommendation pipeline.

This prompt extracts coverage values for ALL vendor A levels at once, mapping them to taxonomy leaves
with a simplified schema (base_value + detailed_value).
"""

from typing import Any

from pydantic import BaseModel, Field


class ValueAtLevel(BaseModel):
    """Coverage value for a policy level of a vendor."""
    level: str = Field(..., description="Policy level name")
    base_value: str = Field(..., description="Base coverage value under default conditions and modalities (e.g., '100€', '150% BR', 'Non couvert')")
    detailed_value: str = Field(..., description="Complete value description that includes the base value PLUS all conditions, modulations, footnotes, age restrictions, frequency limits, caps, network bonuses, etc. This field should be self-contained and contain everything needed to understand the coverage. Must not repeat the prestation name and description from the taxonomy leaf.")
    source_cell_ids: list[str] | None = Field(None, description="Cell IDs from source document where values were extracted. Can span multiple cells if value is distributed.")
    notes: str | None = Field(None, description="Extraction notes or ambiguities. Omit if straightforward.")

class MultiLevelValue(BaseModel):
    """Coverage value for multiple policy levels of a vendor."""

    leaf_id: str = Field(..., description="ID of taxonomy leaf this value corresponds to")
    values: list[ValueAtLevel] = Field(..., description="Array of values for all policy levels of the vendor")



class UnmappableItemMultiLevel(BaseModel):
    """A benefit found in vendor document that doesn't map to existing taxonomy."""

    description: str = Field(..., description="Description of the unmapped benefit")
    reasoning: str = Field(..., description="Why this doesn't map to existing taxonomy")
    suggested_category_id: str = Field(..., description="Suggested category ID (snake_case)")
    suggested_path: list[str] = Field(..., description="Suggested taxonomy path for this item")
    suggested_parent_id: str = Field(..., description="Suggested parent ID (snake_case)")
    suggested_leaf_id: str = Field(..., description="Suggested leaf ID (snake_case)")

    values: list[ValueAtLevel] = Field(..., description="Values for all policy levels of the vendor")


class CategoryValueExtractionMultiLevel(BaseModel):
    """Extracted values for ALL policy levels of a vendor for a specific category."""

    vendor: str = Field(..., description="Vendor name (e.g., 'ProBTP', 'AXA')")
    category_id: str = Field(..., description="Category ID being extracted (e.g., 'optique', 'hospitalisation')")
    policy_levels: list[str] = Field(..., description="Policy levels identified in the vendor document")

    extracted_values: list[MultiLevelValue] = Field(..., description="All values extracted for this category across all levels")
    unmappable_items: list[UnmappableItemMultiLevel] | None = Field(None, description="Items that don't map to taxonomy. Omit if none.")

    extraction_notes: str | None = Field(None, description="General notes about extraction. Omit if none.")


def format_taxonomy_tree(nodes: list[dict[str, Any]]) -> str:
    """Format a flat taxonomy into an ASCII tree structure."""
    children_map: dict[str | None, list[dict[str, Any]]] = {}
    node_map: dict[str, dict[str, Any]] = {}

    for node in nodes:
        node_id = node["node_id"]
        parent_id = node.get("parent_id")

        node_map[node_id] = node

        if parent_id not in children_map:
            children_map[parent_id] = []
        children_map[parent_id].append(node)

    def build_tree(node_id: str | None, prefix: str = "", is_last: bool = True) -> list[str]:
        """Build tree recursively with proper ASCII art."""
        lines = []
        children = children_map.get(node_id, [])

        for i, child in enumerate(children):
            is_last_child = i == len(children) - 1
            connector = "└─ " if is_last_child else "├─ "

            name = child["name"]
            description = child.get("description", "")
            child_node_id = child["node_id"]
            parent_id = child.get("parent_id")

            # For top-level categories (parent is _root_), include the category ID
            if parent_id == "_root_":
                line = f"{prefix}{connector}{name} (ID: {child_node_id}) - {description}"
            else:
                line = f"{prefix}{connector}{name} - {description}"

            lines.append(line)

            child_prefix = prefix + "   " if is_last_child else prefix + "│  "

            child_lines = build_tree(child_node_id, child_prefix, is_last_child)
            lines.extend(child_lines)

        return lines

    tree_lines = build_tree("_root_")
    return "\n".join(tree_lines)


def create_value_extraction_multi_level_prompt(
    vendor: str,
    vendor_markdown: str,
    category_id: str,
    category_name: str,
    policy_levels: list[str],
    taxonomy_leaves: list[dict[str, Any]],
    full_taxonomy_nodes: list[dict[str, Any]] | None = None,
    provider_profile: dict[str, Any] | None = None,
    provider_context: str = "",
) -> str:
    """Create value extraction prompt for multiple policy levels.

    Args:
        vendor: Vendor name (e.g., 'ProBTP')
        vendor_markdown: Full markdown of vendor document
        category_id: Category ID (e.g., 'optique')
        category_name: Category name (e.g., 'Optique')
        policy_levels: List of policy levels to extract (e.g., ['S1', 'S2', 'S3', 'S4', 'S5'])
        taxonomy_leaves: Taxonomy leaves for this category
        full_taxonomy_nodes: Full taxonomy for context (optional)
        provider_profile: Provider profile data (optional)
        provider_context: Formatted provider context string (optional)

    Returns:
        Extraction prompt
    """

    # Format taxonomy tree for context
    taxonomy_tree = format_taxonomy_tree(full_taxonomy_nodes) if full_taxonomy_nodes else ""

    # Format leaves as simple list
    leaves_texts: list[str] = []
    for leaf in taxonomy_leaves:
        leaf_text = f"- {leaf['leaf_id']}: {leaf['path'][-1]} - {leaf['description']}"
        leaf_text += f" - Conditions : {leaf.get('conditions', '')}" if leaf.get('conditions') else ""
        leaves_texts.append(leaf_text)

    leaves_list = "\n".join(leaves_texts)

    policy_levels_str = ", ".join(policy_levels)

    # Get vendor-specific guidance about bundled benefits relevant to this category
    bundled_benefits_guidance = ""
    if provider_profile and provider_profile.get("typical_bundled_benefits"):
        bundled_benefits = provider_profile["typical_bundled_benefits"]
        # Filter for benefits that might appear in this category
        relevant_benefits = [
            b for b in bundled_benefits
            if category_name.lower() in b["category"].lower() or
               category_id.lower() in b.get("notes", "").lower() or
               "prestations" in category_id.lower()  # Catch prevoyance benefits in Prestations Complémentaires
        ]

        if relevant_benefits:
            bundled_benefits_guidance = "\n\n**Bundled Benefits Context for This Category:**\n"
            for benefit in relevant_benefits:
                bundled_benefits_guidance += f"- **{benefit['name']}**: {benefit['description']}\n"
                if benefit.get("notes"):
                    bundled_benefits_guidance += f"  Note: {benefit['notes']}\n"
            bundled_benefits_guidance += "\n**Important**: These bundled benefits may appear in the coverage tables. Extract them accurately as they are key selling points.\n"

    # Build provider context section conditionally
    provider_section = ""
    if provider_context or bundled_benefits_guidance:
        provider_section = "\n**Provider Context:**\n"
        if provider_context:
            provider_section += f"{provider_context}\n"
        if bundled_benefits_guidance:
            provider_section += f"{bundled_benefits_guidance}"
        provider_section += "\n"

    prompt = f"""Extract coverage values for {vendor} across multiple policy levels for the category: {category_name}.
{provider_section}
**Task**: Map {vendor}'s coverage to the taxonomy leaves below, extracting values for ALL levels: {policy_levels_str}.

**Output Schema**:
```
CategoryValueExtractionMultiLevel {{
  vendor: string
  category_id: string
  policy_levels: string[]
  extracted_values: MultiLevelValue[] {{
    leaf_id: string
    values: ValueAtLevel[] {{
      level: string
      base_value: string
      detailed_value: string
      source_cell_ids: string[] | null
      notes: string | null
    }}
  }}
  unmappable_items: UnmappableItemMultiLevel[] | null
  extraction_notes: string | null
}}
```

**Key Instructions**:
1. Identify the actual policy levels present in the document and return them in `policy_levels`
2. For each taxonomy leaf, create a values array with ONE ValueAtLevel object per policy level:
  a. `level`: Exact policy level name
  b. `base_value`: Default coverage amount/percentage/status under default conditions and modalities. The value to be applied in general for this level.
  c. `detailed_value`: Complete description with ALL conditions and value specific modalities (frequency limits, annual caps, age restrictions, network bonuses, renewal periods). Inline a summary of potential footnote content directly. Must not repeat the prestation name and description from the taxonomy leaf or the level.
  d. `source_cell_ids`: Array of cell IDs from the markdown where values were extracted. Generally will be a single cell ID but can be a list of cell IDs if the value spans multiple cells.
  e. If coverage doesn't exist for a leaf at a level: `base_value: "Non couvert"`, `detailed_value: "Aucune couverture pour ce niveau"`
3. For each value that does not map to a taxonomy leaf, create an UnmappableItemMultiLevel object:
  a. `description`: Description of the unmapped benefit
  b. `reasoning`: Why this doesn't map to existing taxonomy
  c. `suggested_category_id`: Suggested category ID (snake_case). IMPORTANT: Use one of the category IDs shown in the Taxonomy Context section (marked with "ID: ..."). If the benefit belongs to the current category being extracted, use that category ID.
  d. `suggested_path`: Suggested taxonomy path for this item
  e. `suggested_parent_id`: Suggested parent ID (snake_case)
  f. `suggested_leaf_id`: Suggested leaf ID (snake_case)
  g. `values`: Values for all policy levels of the vendor, same as 2.a-e


**Source Document**:
<policy_document>
{vendor_markdown}
</policy_document>

**Taxonomy Context**:
<taxonomy_tree>
{taxonomy_tree if taxonomy_tree else "Not provided"}
</taxonomy_tree>

**Category Context**:
Here we focus on the category: {category_name}, the rest of taxonomy was provided to help judge if the unmapped benefit is related to the category {category_name}.

**Taxonomy Leaves to Extract**:
<taxonomy_leaves>
{leaves_list}
</taxonomy_leaves>

Extract all mapable and unmapable values for levels: {policy_levels_str}, and category: {category_name}. Format the output as a JSON object conforming to CategoryValueExtractionMultiLevel schema."""

    return prompt
