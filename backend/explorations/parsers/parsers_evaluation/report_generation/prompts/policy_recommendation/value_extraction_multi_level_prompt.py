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
    detailed_value: str = Field(..., description="Detailed value description including all conditions, modulations, footnotes, age restrictions, frequency limits, caps, network bonuses, etc. If coverage varies by level, explicitly state which levels have which conditions. Must not repeat the prestation name and description from the taxonomy leaf.")
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

            line = f"{prefix}{connector}{name} - {description}"
            lines.append(line)

            child_prefix = prefix + "   " if is_last_child else prefix + "│  "

            child_lines = build_tree(child["node_id"], child_prefix, is_last_child)
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

    Returns:
        Extraction prompt
    """
    # Format taxonomy tree for context
    if full_taxonomy_nodes:
        # Filter nodes for this category
        category_nodes = [
            node for node in full_taxonomy_nodes
            if node["node_id"] == category_id or node.get("path", [""])[0] == category_name
        ]
        taxonomy_tree = format_taxonomy_tree(category_nodes) if category_nodes else ""
    else:
        taxonomy_tree = ""

    # Format leaves as simple list
    leaves_list = "\n".join([
        f"- {leaf['leaf_id']}: {leaf['path'][-1]} - {leaf['description']}"
        for leaf in taxonomy_leaves
    ])

    policy_levels_str = ", ".join(policy_levels)

    prompt = f"""Extract coverage values for {vendor} across multiple policy levels for a specific category that is provided below.

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
  c. `suggested_category_id`: Suggested category ID (snake_case)
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
