"""Value extraction prompt for extracting coverage values mapped to taxonomy leaves.

This prompt extracts actual coverage values from vendor documents, mapping them to
the pre-defined taxonomy structure while separating vendor-specific conditions.
"""

from typing import Any

from pydantic import BaseModel, Field


class VendorCondition(BaseModel):
    """A vendor-specific modifier that affects coverage."""
    condition_type: str = Field(..., description="Type: 'network_bonus', 'administrative_requirement', 'geographic_restriction', 'timing_restriction', etc.")
    description: str = Field(..., description="Human-readable description (e.g., 'Si partenaire xyz')")
    coverage_modifier: str | None = Field(None, description="How this changes coverage (e.g., '+20€', 'remboursement majoré'). Omit if not quantified.")
    modified_coverage_source_cell_ids: list[str] | None = Field(None, description="Cell ID from source document that contains the modified coverage value. Or the modifier itself.")





class ExtractedValue(BaseModel):
    """A coverage value extracted from vendor document for a specific taxonomy leaf."""
    leaf_id: str = Field(..., description="ID of taxonomy leaf this value corresponds to")

    # Core coverage information
    coverage: str = Field(..., description="Base (unmodified) coverage amount/percentage/yes-no (e.g., '100€', '150% BR', '100% BR - MR', 'Non couvert', 'Oui') Can be a composite if the coverage is more granular than a leaf.")
    # Traceability
    source_cell_ids: list[str] | None = Field(None, description="Cell ID from source document markdown where the value was extracted from. Generally will be a single cell ID but can be a list of cell IDs if the value spans multiple cells.")

    # Universal modifiers (apply to any insurer)
    frequency: str | None = Field(None, description="Frequency limit (e.g., 'par an', 'par œil', 'tous les 2 ans'). Omit if none.")
    cap: str | None = Field(None, description="Coverage cap/plafond (e.g., 'plafond 300€', 'maximum 500€/an'). Omit if none.")
    age_restriction: str | None = Field(None, description="Age limits (e.g., 'jusqu'à 16 ans', 'adultes uniquement'). Omit if none.")
    other_universal_conditions: str | None = Field(None, description="Other universal conditions (e.g., 'sur prescription médicale', 'avec accord préalable SS'). Omit if none.")

    # Vendor-specific modifiers (DO NOT belong in taxonomy)
    vendor_conditions: list[VendorCondition] | None = Field(None, description="Vendor-specific modifiers. Omit if none.")

    # Traceability
    notes: str | None = Field(None, description="Extraction notes or ambiguities. Omit if straightforward.")

    # Human-readable summary
    display_text: str = Field(..., description="Concise 1-2 sentence human-readable summary synthesizing the coverage for user understanding. Include: base value, universal modifiers (frequency, cap, age restrictions, other universal conditions), vendor-specific conditions, and inline the content of vendor-specific footnotes that apply directly to this leaf/value (not just the footnote reference). Examples: '150€ tous les 2 ans (200€ si partenaire Sévéane)', '100% BR - MR, plafond 300€/an, sur prescription', '120€ par an, uniquement dans le réseau de partenaires agréés', 'Non couvert'.")


class UnmappableItem(BaseModel):
    """A benefit found in vendor document that doesn't map to existing taxonomy."""
    description: str = Field(..., description="Description of the unmapped benefit")
    reasoning: str = Field(..., description="Why this doesn't map to existing taxonomy and should be added")
    suggested_category_id:   str = Field(..., description="Suggested category ID (snake_case)")
    suggested_path: list[str] = Field(..., description="Suggested taxonomy path for this item")
    suggested_parent_id: str = Field(..., description="Suggested parent ID (snake_case)")
    suggested_leaf_id: str = Field(..., description="Suggested leaf ID (snake_case)")
    coverage: str = Field(..., description="Coverage value for this item")
    # Traceability
    source_cell_ids: list[str] | None = Field(None, description="Cell ID from source document markdown where the value was extracted from. Generally will be a single cell ID but can be a list of cell IDs if the value spans multiple cells.")

    # Universal modifiers (apply to any insurer)
    frequency: str | None = Field(None, description="Frequency limit (e.g., 'par an', 'par œil', 'tous les 2 ans'). Omit if none.")
    cap: str | None = Field(None, description="Coverage cap/plafond (e.g., 'plafond 300€', 'maximum 500€/an'). Omit if none.")
    age_restriction: str | None = Field(None, description="Age limits (e.g., 'jusqu'à 16 ans', 'adultes uniquement'). Omit if none.")
    other_universal_conditions: str | None = Field(None, description="Other universal conditions (e.g., 'sur prescription médicale', 'avec accord préalable SS'). Omit if none.")

    # Vendor-specific modifiers (DO NOT belong in taxonomy)
    vendor_conditions: list[VendorCondition] | None = Field(None, description="Vendor-specific modifiers. Omit if none.")

    # Traceability
    notes: str | None = Field(None, description="Extraction notes or ambiguities. Omit if straightforward.")

    # Human-readable summary
    display_text: str = Field(..., description="Concise 1-2 sentence human-readable summary synthesizing the coverage for user understanding. Include: base value, universal modifiers (frequency, cap, age restrictions, other universal conditions), vendor-specific conditions. Examples: '150€ tous les 2 ans', '100% BR - MR, plafond 300€/an, sur prescription', '120€ par an'.")


class CategoryValueExtraction(BaseModel):
    """Extracted values for a specific category from a vendor document."""
    vendor: str = Field(..., description="Vendor name (e.g., 'ProBTP', 'AXA')")
    category_id: str = Field(..., description="Category ID being extracted (e.g., 'optique', 'hospitalisation')")
    policy_level: str = Field(..., description="Policy level extracted (e.g., 'S2', 'P4', 'Base Obligatoire')")

    extracted_values: list[ExtractedValue] = Field(..., description="All values extracted for this category")
    unmappable_items: list[UnmappableItem] | None = Field(None, description="Items that don't map to taxonomy. Omit if none.")

    extraction_notes: str | None = Field(None, description="General notes about extraction (coverage gaps, ambiguities, etc.). Omit if none.")


def format_taxonomy_tree(nodes: list[dict[str, Any]]) -> str:
    """
    Format a flat taxonomy into an ASCII tree structure with names and descriptions.

    Args:
        nodes: Flat list of taxonomy nodes with node_id, parent_id, name, description, is_leaf

    Returns:
        Formatted ASCII tree string
    """
    # Build parent-child mapping
    children_map: dict[str | None, list[dict[str, Any]]] = {}
    node_map: dict[str, dict[str, Any]] = {}

    for node in nodes:
        node_id = node["node_id"]
        parent_id = node.get("parent_id")

        node_map[node_id] = node

        if parent_id not in children_map:
            children_map[parent_id] = []
        children_map[parent_id].append(node)

    # Recursive function to build tree
    def build_tree(node_id: str | None, prefix: str = "", is_last: bool = True) -> list[str]:
        """Build tree recursively with proper ASCII art."""
        lines = []

        # Get children of this node
        children = children_map.get(node_id, [])

        for i, child in enumerate(children):
            is_last_child = i == len(children) - 1

            # Prepare connector
            connector = "└─ " if is_last_child else "├─ "

            # Prepare description
            name = child["name"]
            description = child.get("description", "")
            is_leaf = child.get("is_leaf", False)

            # Format line
            if is_leaf:
                line = f"{prefix}{connector}{name} - {description}"
            else:
                line = f"{prefix}{connector}{name} - {description}"

            lines.append(line)

            # Prepare prefix for children
            if is_last_child:
                child_prefix = prefix + "   "
            else:
                child_prefix = prefix + "│  "

            # Recursively add children
            child_lines = build_tree(child["node_id"], child_prefix, is_last_child)
            lines.extend(child_lines)

        return lines

    # Start from root (parent_id = "_root_" or None)
    # Try "_root_" first (ProBTP convention), fallback to None
    if "_root_" in children_map:
        tree_lines = build_tree("_root_")
    else:
        tree_lines = build_tree(None)
    return "\n".join(tree_lines)


def create_value_extraction_prompt(
    vendor: str,
    vendor_markdown: str,
    category_id: str,
    category_name: str,
    policy_level: str,
    taxonomy_leaves: list[dict],
    full_taxonomy_nodes: list[dict[str, Any]] | None = None,
    language: str = "French (France)"
) -> str:
    """
    Create prompt for extracting values from vendor document mapped to taxonomy.

    Args:
        vendor: Vendor name ("ProBTP" or "AXA")
        vendor_markdown: Full markdown of vendor contract
        category_id: Category ID to extract (e.g., "optique")
        category_name: Category display name (e.g., "Optique")
        policy_level: Policy level to extract (e.g., "S2", "Base Obligatoire")
        taxonomy_leaves: List of taxonomy leaf dicts for this category
        full_taxonomy_nodes: Full flat taxonomy structure (for cross-category awareness)
        language: Output language

    Returns:
        Formatted prompt string
    """

    # Format taxonomy leaves for prompt
    leaves_formatted = "\n".join([
        f"  - leaf_id: {leaf['leaf_id']}\n"
        f"    path: {' → '.join(leaf['path'])}\n"
        f"    description: {leaf['description']}"
        for leaf in taxonomy_leaves
    ])

    # Format full taxonomy tree if provided
    full_taxonomy_section = ""
    if full_taxonomy_nodes:
        full_taxonomy_tree = format_taxonomy_tree(full_taxonomy_nodes)
        full_taxonomy_section = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FULL TAXONOMY REFERENCE (All Categories)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The complete taxonomy structure is shown below for reference. This helps you identify when a benefit found in the document clearly belongs to a DIFFERENT category:

{full_taxonomy_tree}

"""

    prompt = f"""You are an expert insurance analyst specializing in French health insurance (mutuelle) contracts. Your task is to extract COVERAGE VALUES from the {vendor} contract for the "{category_name}" category, mapping them to a pre-defined taxonomy.
{full_taxonomy_section}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL: EXTRACT VALUES MAPPED TO TAXONOMY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**What You're Extracting:**

For the **{vendor} {policy_level}** policy levels, extract coverage values for the **"{category_name}"** category.

**Current Category Taxonomy Leaves:**

The leaves below define what to extract for THIS category. Each leaf represents a specific benefit that should have a coverage value:

{leaves_formatted}

**Critical Success Factors:**

1. ✓ **Completeness**: Extract values for EVERY taxonomy leaf (or mark "Non couvert" if not covered)
2. ✓ **Accuracy**: Correct coverage amounts, frequencies, caps, conditions
3. ✓ **Separation**: Split universal conditions from vendor-specific modifiers
4. ✓ **Mapping**: Map values to correct leaf_id from taxonomy
5. ✓ **Unmappable Items**: Flag benefits in {vendor} doc that don't map to taxonomy

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION GUIDELINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1. Mapping to Taxonomy Leaves**

For each leaf in the taxonomy:
- Search {vendor} document for corresponding benefit
- Extract coverage value for **{policy_level}** column/level only
- If benefit exists → extract coverage
- If benefit doesn't exist → create entry with `coverage: "Non couvert"`

**Example:**
- Taxonomy leaf: `optique_lunettes_monture` (path: Optique → Lunettes → Monture)
- {vendor} has: "Monture: 150€/2 ans"
- Extract:
  - coverage: "150€"
  - frequency: "tous les 2 ans"
  - leaf_id: "optique_lunettes_monture"

**2. Separating Universal vs. Vendor-Specific Conditions**

**Universal Conditions** (apply to any insurer):
- ✓ Frequency limits: "par an", "par œil", "tous les 2 ans"
- ✓ Caps/plafonds: "plafond 300€", "maximum 500€/an"
- ✓ Age restrictions: "jusqu'à 16 ans", "adultes uniquement"
- ✓ Medical requirements: "sur prescription", "avec accord préalable SS"

→ Extract these as: `frequency`, `cap`, `age_restriction`, `other_universal_conditions`

**Vendor-Specific Conditions** (specific to {vendor}):
- ✗ Network bonuses: "Si partenaire opticien Sévéane: +20€"
- ✗ Geographic: "Dans le réseau {vendor}"
- ✗ Administrative: "Sur présentation facture {vendor}"
- ✗ Timing: "Offre 2024"

→ Extract these as: `vendor_conditions` array

**Example:**

{vendor} document shows:
```
Monture: 100€/2 ans
Si partenaire Sévéane: 150€/2 ans
```

Extract as:
```json
{{
  "leaf_id": "optique_lunettes_monture",
  "coverage": "100€",
  "source_cell_ids": ["0-2v", "0-4E"],
  "frequency": "tous les 2 ans",
  "vendor_conditions": [
    {{
      "condition_type": "network_bonus",
      "description": "Si partenaire opticien Sévéane",
      "coverage_modifier": "+50€ (150€ total)",
      "modified_coverage_source_cell_ids": ["0-2v"]
    }}
  ],
  "display_text": "100€ tous les 2 ans (150€ si partenaire opticien Sévéane)"
}}
```

**3. Handling Complex Coverage Strings**

**"100% BR - MR"** → Extract as-is: `"100% BR - MR"`
**"170% BR (base de remboursement)"** → Extract: `"170% BR"`
**"50€ + 60€"** → Extract: `"110€"` (or keep as `"50€ + 60€"` if semantic meaning matters)
**"Jusqu'à 100€"** → coverage: `"100€"`, cap: `"maximum 100€"`

**4. Handling Unmappable Items & Cross-Category Awareness**

When you find a benefit in the {vendor} document, follow this decision tree:

**Step 1: Does it match a leaf in the CURRENT category ({category_name})?**
- Check all leaves carefully - might be worded differently
- Example: Taxonomy has "Verres simples", {vendor} has "Verres unifocaux" → SAME (map it)
- If YES → Extract the value to that leaf

**Step 2: Does it clearly belong to a DIFFERENT category?**
- Use the full taxonomy reference above to check other categories
- Example: Processing "Optique" but found "Chambre particulière" → clearly "Hospitalisation" → SKIP IT
- If YES → SKIP this benefit (it will be processed when that category runs)

**Step 3: Does it belong to CURRENT category but no leaf matches?**
- The benefit semantically belongs to {category_name}
- But none of the leaves match it
- If YES → Flag as `unmappable_items` with suggested leaf

**Example of Step 3:**
Processing "Optique" category. {vendor} has "Chirurgie réfractive (LASIK)" but taxonomy has no such leaf under Optique.

```json
{{
  "description": "Chirurgie réfractive (LASIK)",
  "suggested_path": ["Optique", "Chirurgie réfractive"],
  "suggested_parent_id": "optique",
  "suggested_leaf_id": "optique_chirurgie_refractive",
  "reasoning": "Clearly belongs to Optique category but no matching leaf exists. AXA covers laser eye surgery but ProBTP taxonomy doesn't include it.",
  "coverage": "300€"
}}
```

**Important:** Only flag items as unmappable if they belong to the CURRENT category. Don't flag items that belong to other categories.

**5. Handling Multiple Values for Same Leaf**

If {vendor} splits a taxonomy leaf into multiple scenarios (e.g., "Lentilles journalières: X€" and "Lentilles mensuelles: Y€"), but taxonomy only has one leaf "Lentilles":

**Option A: Use notes field**
```json
{{
  "leaf_id": "optique_lentilles_non_remboursees_ss",
  "coverage": "60€",
  "notes": "AXA distingue journalières (60€) et mensuelles (80€). Valeur principale: 60€."
}}
```

**Option B: Flag as unmappable extension**
If the distinction is significant, suggest splitting the taxonomy leaf.

**6. Handling Vendor-Specific Footnotes in Display Text**

When a coverage value has associated footnotes in the vendor document:

**Determine Footnote Type:**
- **Universal footnote**: Applies to any insurer (e.g., "*Sur prescription médicale", "*Accord préalable SS requis") → Extract to appropriate universal field (other_universal_conditions), include in display_text
- **Vendor-specific footnote**: Specific to {vendor} (e.g., "*Uniquement réseau partenaire {vendor}", "*Offre 2024") → Extract to vendor_conditions, inline the footnote CONTENT (not reference) in display_text

**Key Point**: The display_text should integrate the footnote content inline for easy human understanding, not just reference it as "voir note *".

**7. Policy Level Filtering**

**CRITICAL**: Only extract values for **{policy_level}**.

If {vendor} table shows multiple policy levels (e.g., "Base", "Option 1", "Option 2"), ONLY extract the **{policy_level}** column.

Ignore other policy levels - they will be extracted in separate calls.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VENDOR DOCUMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**{vendor} Insurance Contract:**

{vendor_markdown}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION PROCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**STEP 1: Locate {category_name} Section**

Find the "{category_name}" section/table in the {vendor} document.

**STEP 2: Identify {policy_level} Column**

Locate the column for **{policy_level}** policy level.

**STEP 3: Extract Values for Each Taxonomy Leaf**

For each leaf in the taxonomy:

3.1: Search for corresponding benefit in {vendor} table
3.2: Extract coverage value from **{policy_level}** column
3.3: Extract universal conditions (frequency, cap, age, etc.)
3.4: Extract vendor-specific conditions separately
3.5: Check for footnotes that apply to this leaf/value:
     - If universal footnote → add to appropriate universal field
     - If vendor-specific footnote → add to vendor_conditions and inline content in display_text
3.6: Synthesize display_text with all elements (coverage, universal modifiers, vendor conditions, footnote content)
3.7: If benefit not found → coverage: "Non couvert"

**STEP 4: Identify Unmappable Items (Current Category Only)**

Scan {vendor} "{category_name}" section for benefits that:
- Clearly belong to {category_name} category (not other categories)
- Don't match any existing leaf in this category
- Should be flagged as unmappable with suggested taxonomy extension

Skip any benefits that clearly belong to other categories - they will be processed later.

**STEP 5: Validate**

✓ All taxonomy leaves have extracted values (or "Non couvert")?
✓ Coverage values accurate?
✓ Universal conditions separated from vendor conditions?
✓ Vendor-specific footnotes inlined in display_text (content, not just references)?
✓ Display text synthesizes all importante elements for human understanding?
✓ Only **{policy_level}** extracted (not other levels)?
✓ Unmappable items flagged appropriately?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Output Language:** {language}

**Return:** ONLY the JSON object conforming to CategoryValueExtraction schema.

**Example Output:**

{{
  "vendor": "{vendor}",
  "category_id": "{category_id}",
  "policy_level": "{policy_level}",
  "extracted_values": [
    {{
      "leaf_id": "optique_lunettes_monture",
      "coverage": "150€",
      "source_cell_ids": ["3-5v", "2-2e"],
      "frequency": "tous les 2 ans",
      "cap": null,
      "age_restriction": null,
      "other_universal_conditions": null,
      "vendor_conditions": [
        {{
          "condition_type": "network_bonus",
          "description": "Si partenaire opticien Sévéane",
          "coverage_modifier": "+50€ (200€ total)",
          "modified_coverage_source_cell_ids": ["0-2v"]
        }}
      ],
      "notes": null,
      "display_text": "150€ tous les 2 ans (200€ si partenaire opticien Sévéane)"
    }},
    {{
      "leaf_id": "optique_lunettes_verres_simples",
      "coverage": "100€",
      "source_cell_ids": ["3-6C"],
      "frequency": "par an",
      "cap": "plafond 150€",
      "age_restriction": null,
      "other_universal_conditions": null,
      "vendor_conditions": null,
      "notes": null,
      "display_text": "100€/an, plafond 150€"
    }},
    {{
      "leaf_id": "optique_lentilles_remboursees_ss",
      "coverage": "Non couvert",
      "source_cell_ids": null,
      "frequency": null,
      "cap": null,
      "age_restriction": null,
      "other_universal_conditions": null,
      "vendor_conditions": null,
      "notes": "AXA ne couvre pas les lentilles remboursées SS mais couvre les lentilles non remboursées SS (voir optique_lentilles_non_remboursees_ss)",
      "display_text": "Non couvert (voir lentilles non remboursées SS)"
    }}
  ],
  "unmappable_items": [
    {{
      "description": "Chirurgie réfractive (LASIK)",
      "suggested_category_id": "{category_id}",
      "suggested_path": ["Optique", "Chirurgie réfractive"],
      "suggested_parent_id": "optique",
      "suggested_leaf_id": "optique_chirurgie_refractive",
      "reasoning": "AXA couvre la chirurgie réfractive au laser mais ce n'est pas présent dans la taxonomie ProBTP. Avantage légitime propre à AXA.",
      "coverage": "300€",
      "source_cell_ids": ["7-5L"],
      "frequency": "/an",
      "cap": "par an par beneficiaire",
      "age_restriction": null,
      "other_universal_conditions": null,
      "vendor_conditions": null,
      "notes": null
    }}
  ],
  "extraction_notes": "Extraction complete for {category_name}. 1 unmappable item flagged."
}}

Output the JSON now:"""

    return prompt
