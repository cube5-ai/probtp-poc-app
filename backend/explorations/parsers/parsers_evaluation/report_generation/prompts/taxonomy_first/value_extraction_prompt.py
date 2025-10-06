"""Value extraction prompt for extracting coverage values mapped to taxonomy leaves.

This prompt extracts actual coverage values from vendor documents, mapping them to
the pre-defined taxonomy structure while separating vendor-specific conditions.
"""

from pydantic import BaseModel, Field


class VendorCondition(BaseModel):
    """A vendor-specific modifier that affects coverage."""
    condition_type: str = Field(..., description="Type: 'network_bonus', 'administrative_requirement', 'geographic_restriction', 'timing_restriction', etc.")
    description: str = Field(..., description="Human-readable description (e.g., 'Si partenaire opticien Sévéane')")
    coverage_modifier: str | None = Field(None, description="How this changes coverage (e.g., '+20€', 'remboursement majoré'). Omit if not quantified.")


class ExtractedValue(BaseModel):
    """A coverage value extracted from vendor document for a specific taxonomy leaf."""
    leaf_id: str = Field(..., description="ID of taxonomy leaf this value corresponds to")

    # Core coverage information
    coverage: str = Field(..., description="Coverage amount/percentage/yes-no (e.g., '100€', '150% BR', '100% BR - MR', 'Non couvert', 'Oui')")
    # Traceability
    source_cell_ids: list[str] | None = Field(None, description="Cell IDs from source document markdown. Omit for now (grounding deferred).")

    # Universal modifiers (apply to any insurer)
    frequency: str | None = Field(None, description="Frequency limit (e.g., 'par an', 'par œil', 'tous les 2 ans'). Omit if none.")
    cap: str | None = Field(None, description="Coverage cap/plafond (e.g., 'plafond 300€', 'maximum 500€/an'). Omit if none.")
    age_restriction: str | None = Field(None, description="Age limits (e.g., 'jusqu'à 16 ans', 'adultes uniquement'). Omit if none.")
    other_universal_conditions: str | None = Field(None, description="Other universal conditions (e.g., 'sur prescription médicale', 'avec accord préalable SS'). Omit if none.")

    # Vendor-specific modifiers (DO NOT belong in taxonomy)
    vendor_conditions: list[VendorCondition] | None = Field(None, description="Vendor-specific modifiers. Omit if none.")

    # Traceability
    notes: str | None = Field(None, description="Extraction notes or ambiguities. Omit if straightforward.")


class UnmappableItem(BaseModel):
    """A benefit found in vendor document that doesn't map to existing taxonomy."""
    description: str = Field(..., description="Description of the unmapped benefit")
    suggested_path: list[str] = Field(..., description="Suggested taxonomy path for this item")
    suggested_parent_id: str = Field(..., description="Suggested parent ID (snake_case)")
    suggested_leaf_id: str = Field(..., description="Suggested leaf ID (snake_case)")
    reasoning: str = Field(..., description="Why this doesn't map to existing taxonomy and should be added")
    coverage: str = Field(..., description="Coverage value for this item")
    # Traceability
    source_cell_ids: list[str] | None = Field(None, description="Cell IDs from source. Omit for now.")


class CategoryValueExtraction(BaseModel):
    """Extracted values for a specific category from a vendor document."""
    vendor: str = Field(..., description="Vendor name (e.g., 'ProBTP', 'AXA')")
    category_id: str = Field(..., description="Category ID being extracted (e.g., 'optique', 'hospitalisation')")
    policy_level: str = Field(..., description="Policy level extracted (e.g., 'S2', 'P4', 'Base Obligatoire')")

    extracted_values: list[ExtractedValue] = Field(..., description="All values extracted for this category")
    unmappable_items: list[UnmappableItem] | None = Field(None, description="Items that don't map to taxonomy. Omit if none.")

    extraction_notes: str | None = Field(None, description="General notes about extraction (coverage gaps, ambiguities, etc.). Omit if none.")


def create_value_extraction_prompt(
    vendor: str,
    vendor_markdown: str,
    category_id: str,
    category_name: str,
    policy_level: str,
    taxonomy_leaves: list[dict],
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

    prompt = f"""You are an expert insurance analyst specializing in French health insurance (mutuelle) contracts. Your task is to extract COVERAGE VALUES from the {vendor} contract for the "{category_name}" category, mapping them to a pre-defined taxonomy.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL: EXTRACT VALUES MAPPED TO TAXONOMY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**What You're Extracting:**

For the **{vendor} {policy_level}** policy levels, extract coverage values for the **"{category_name}"** category.

**Your Reference Taxonomy:**

The taxonomy below defines what to extract. Each leaf represents a specific benefit that should have a coverage value:

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
  "frequency": "tous les 2 ans",
  "source_cell_ids": ["0-2v", "0-4E"],
  "vendor_conditions": [
    {{
      "condition_type": "network_bonus",
      "description": "Si partenaire opticien Sévéane",
      "coverage_modifier": "+50€ (150€ total)"
    }}
  ]
}}
```

**3. Handling Complex Coverage Strings**

**"100% BR - MR"** → Extract as-is: `"100% BR - MR"`
**"170% BR (base de remboursement)"** → Extract: `"170% BR"`
**"50€ + 60€"** → Extract: `"110€"` (or keep as `"50€ + 60€"` if semantic meaning matters)
**"Jusqu'à 100€"** → coverage: `"100€"`, cap: `"maximum 100€"`

**4. Handling Unmappable Items**

If you find a benefit in {vendor} document that doesn't match any taxonomy leaf:

**Step 1: Verify it truly doesn't map**
- Check all leaves carefully - might be worded differently
- Example: Taxonomy has "Verres simples", {vendor} has "Verres unifocaux" → SAME (map it)

**Step 2: If truly unmappable, flag it**
- Add to `unmappable_items`
- Suggest taxonomy path and leaf_id
- Explain why it should be added

**Example:**
{vendor} has "Chirurgie réfractive (LASIK)" but taxonomy has no such leaf under Optique.

```json
{{
  "description": "Chirurgie réfractive (LASIK)",
  "suggested_path": ["Optique", "Chirurgie réfractive"],
  "suggested_parent_id": "optique",
  "suggested_leaf_id": "optique_chirurgie_refractive",
  "reasoning": "AXA covers laser eye surgery but ProBTP taxonomy doesn't include it. This is a legitimate AXA-only benefit.",
  "coverage": "300€"
}}
```

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

**6. Policy Level Filtering**

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
3.5: If benefit not found → coverage: "Non couvert"

**STEP 4: Identify Unmappable Items**

Scan {vendor} "{category_name}" section for benefits not in taxonomy:
- Verify they truly don't map
- Flag as unmappable with suggested taxonomy extension

**STEP 5: Validate**

✓ All taxonomy leaves have extracted values (or "Non couvert")?
✓ Coverage values accurate?
✓ Universal conditions separated from vendor conditions?
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
          "coverage_modifier": "+50€ (200€ total)"
        }}
      ],
      "notes": null
    }},
    {{
      "leaf_id": "optique_lunettes_verres_simples",
      "coverage": "100€",
      "source_cell_ids": ["3-6v"],
      "frequency": "par an",
      "cap": "plafond 150€",
      "age_restriction": null,
      "other_universal_conditions": null,
      "vendor_conditions": null,
      "notes": null
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
      "notes": "AXA ne couvre pas les lentilles remboursées SS dans {policy_level}"
    }}
  ],
  "unmappable_items": [
    {{
      "description": "Chirurgie réfractive (LASIK)",
      "suggested_path": ["Optique", "Chirurgie réfractive"],
      "suggested_parent_id": "optique",
      "suggested_leaf_id": "optique_chirurgie_refractive",
      "reasoning": "AXA covers laser eye surgery but not in ProBTP taxonomy. Legitimate AXA-only benefit.",
      "coverage": "300€",
      "source_cell_ids": null
    }}
  ],
  "extraction_notes": "Extraction complete for {category_name}. 1 unmappable item flagged."
}}

Output the JSON now:"""

    return prompt
