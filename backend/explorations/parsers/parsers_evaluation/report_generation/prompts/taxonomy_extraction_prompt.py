"""Taxonomy extraction prompt for building reference taxonomy from ProBTP contract.

This prompt extracts a universal, hierarchical taxonomy that:
1. Reflects ProBTP's organizational structure (the reference for comparison)
2. Includes universal insurance/medical distinctions (transferable across insurers)
3. Excludes vendor-specific modifiers (those become conditions during value extraction)
"""

from pydantic import BaseModel, Field


class VendorCondition(BaseModel):
    """A vendor-specific modifier that affects coverage (not part of universal taxonomy)."""
    condition_type: str = Field(..., description="Type of condition: 'network_bonus', 'administrative_requirement', 'geographic_restriction', etc.")
    description: str = Field(..., description="Human-readable description (e.g., 'Si partenaire opticien Sévéane')")
    coverage_modifier: str | None = Field(None, description="How this changes coverage (e.g., '+20€', 'remboursement majoré'). Omit if not specified.")


class TaxonomyLeaf(BaseModel):
    """A leaf node in the taxonomy representing a specific, measurable benefit."""
    path: list[str] = Field(..., description="Hierarchical path with variable depth. Examples: ['Optique', 'Lunettes', 'Verres', 'Verres simples'], ['Hospitalisation', 'Chambre particulière']. First element is top-level category.")
    leaf_id: str = Field(..., description="Unique identifier for this leaf (e.g., 'optique_lunettes_verres_simples'). Use snake_case.")
    description: str = Field(..., description="Clear description of what this leaf represents (e.g., 'Remboursement verres correcteurs simples')")
    basis: str | None = Field(None, description="What makes this a distinct category: 'securite_sociale_status', 'medical_classification', 'age_bracket', 'service_type', etc. Omit if straightforward.")


class TaxonomyCategory(BaseModel):
    """A top-level category in the taxonomy (e.g., 'Hospitalisation', 'Optique')."""
    category_name: str = Field(..., description="Top-level category name")
    category_id: str = Field(..., description="Unique identifier (snake_case)")
    description: str = Field(..., description="What this category covers")
    leaves: list[TaxonomyLeaf] = Field(..., description="All leaf nodes in this category")


class ProBTPTaxonomy(BaseModel):
    """Complete ProBTP taxonomy extracted from reference document."""
    categories: list[TaxonomyCategory] = Field(..., description="All top-level categories")
    metadata: dict[str, str] = Field(..., description="Metadata about extraction (source_document, extraction_date, etc.)")


def create_taxonomy_extraction_prompt(
    probtp_markdown: str,
    language: str = "French (France)"
) -> str:
    """
    Create prompt for extracting ProBTP taxonomy from reference document.

    Args:
        probtp_markdown: Full markdown of ProBTP contract
        language: Output language

    Returns:
        Formatted prompt string
    """

    prompt = f"""You are an expert insurance analyst specializing in French health insurance (mutuelle) contracts. Your task is to extract a COMPLETE UNIVERSAL TAXONOMY from the ProBTP reference document.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL: EXTRACT UNIVERSAL TAXONOMY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**What is a Taxonomy?**

A taxonomy is a hierarchical classification system that defines:
- **Top-level categories** (e.g., "Hospitalisation", "Optique", "Soins Courants")
- **Subcategories and nested levels** (variable depth - no fixed limit)
- **Leaf nodes** (specific, measurable benefits that have actual coverage values)

**Dual Purpose of This Taxonomy:**

1. **ProBTP's Structure** - Use ProBTP's organizational perspective
   - How ProBTP organizes categories and subcategories
   - ProBTP's level of detail and granularity
   - This becomes the comparison reference (sales team uses ProBTP view)

2. **Universal Distinctions** - Include transferable insurance/medical categories
   - Based on Sécurité Sociale regulations (e.g., "remboursées S.S." vs "non remboursées S.S.")
   - Based on medical/clinical classification (e.g., "Verres simples" vs "Verres complexes")
   - Based on standard French insurance practice (e.g., "Consultation généraliste" vs "spécialiste")

**What BELONGS in Taxonomy:**

✓ **ProBTP's category structure** (their organizational view)
  - Example: "Soins Courants → Consultations → Médecin généraliste"
  - Example: "Optique → Lunettes → Verres → Verres simples"

✓ **Universal insurance distinctions** (any mutuelle would have this)
  - Example: "Lentilles remboursées par la S.S." vs "Lentilles non remboursées par la S.S."
  - Reason: Based on Sécurité Sociale rules, universal across insurers

✓ **Medical/clinical classifications** (standard medical taxonomy)
  - Example: "Verres simples" vs "Verres progressifs" vs "Verres complexes"
  - Example: "Prothèses dentaires amovibles" vs "Prothèses fixes"

✓ **Standard age brackets or service types** (common insurance practice)
  - Example: "Orthodontie enfant" vs "Orthodontie adulte"
  - Example: "Chambre particulière" vs "Chambre double"

**What DOES NOT belong in Taxonomy (extract as conditions later):**

✗ **Vendor-specific modifiers** (ProBTP implementation details)
  - Example: "Si partenaire opticien Sévéane" → This is a ProBTP network bonus
  - Example: "Dans le réseau ProBTP" vs "Hors réseau" → Vendor-specific
  - These will be extracted as **vendor conditions** during value extraction phase

✗ **Administrative procedures** (vendor-specific processes)
  - Example: "Sur présentation de devis"
  - Example: "Après accord préalable"

✗ **Temporal or promotional** (temporary vendor programs)
  - Example: "Offre 2024"
  - Example: "Promotion été"

**The Decision Rule:**

Ask yourself: **"Would AXA (or any French mutuelle) need to make this same distinction?"**
- YES → Include in taxonomy (it's universal)
- NO, it's ProBTP-specific → Exclude from taxonomy (it's a condition)

Also ask: **"Is this how ProBTP organizes this category?"**
- YES → Include ProBTP's structure (it's the reference)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION GUIDELINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1. Flexible Depth (IMPORTANT)**

The taxonomy has **variable depth** - some branches are shallow, others are deep:
- "Hospitalisation → Chambre particulière" (2 levels)
- "Optique → Lunettes → Verres → Verres simples" (4 levels)
- "Soins Courants → Médecines douces → Ostéopathie" (3 levels)

**DO NOT enforce a fixed number of levels.** Extract the natural structure from ProBTP's document.

**2. What is a Leaf Node?**

A **leaf** is the finest granularity where:
- There is an actual **coverage value** that can be measured
- It represents a **specific, billable benefit**
- It's the endpoint for value extraction

Examples:
- ✓ "Consultation médecin généraliste" (leaf - has coverage value)
- ✓ "Verres simples" (leaf - has coverage value)
- ✗ "Optique" (NOT a leaf - it's a category container)
- ✗ "Lunettes" (NOT a leaf - it has sub-items: Monture, Verres)

**3. Handling Complex Cases**

**Case: "Lentilles remboursées S.S." vs "Lentilles non remboursées S.S."**
- These are **separate leaf nodes** (different paths)
- Path 1: `["Optique", "Lentilles", "Remboursées par la S.S."]`
- Path 2: `["Optique", "Lentilles", "Non remboursées par la S.S."]`
- Basis: `"securite_sociale_status"` (universal distinction)

**Case: "Si partenaire Sévéane" vs "Dans les autres cas"**
- These are **NOT separate leaves** (vendor-specific modifier)
- Single leaf: `["Optique", "Lunettes", "Monture"]`
- "Si partenaire Sévéane" → extracted as **vendor condition** during value extraction

**Case: "Verres simples" vs "Verres progressifs"**
- These are **separate leaf nodes** (medical/optical classification)
- Path 1: `["Optique", "Lunettes", "Verres", "Verres simples"]`
- Path 2: `["Optique", "Lunettes", "Verres", "Verres progressifs"]`
- Basis: `"medical_classification"` (universal)

**4. Generating leaf_id**

Create unique identifiers using snake_case:
- Path: `["Optique", "Lunettes", "Verres", "Verres simples"]`
- leaf_id: `"optique_lunettes_verres_simples"`

- Path: `["Hospitalisation", "Chambre particulière"]`
- leaf_id: `"hospitalisation_chambre_particuliere"`

**5. Completeness Check**

For each top-level category (e.g., "Optique"), ensure you extract:
- ✓ ALL subcategories from ProBTP's table
- ✓ ALL leaf-level benefits with distinct coverage values
- ✓ ALL universal distinctions (S.S. status, medical types, etc.)

**Missing leaves = failed extraction.** Be thorough.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROBTP REFERENCE DOCUMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**ProBTP Insurance Contract:**

{probtp_markdown}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION PROCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**STEP 1: Identify Top-Level Categories**

Scan the ProBTP document and identify all major categories:
- "Hospitalisation"
- "Soins Courants"
- "Optique"
- "Soins Dentaires"
- "Audiologie"
- "Médecines Douces"
- "Prestations Complémentaires"
- etc.

**STEP 2: For Each Category, Extract Hierarchical Structure**

2.1: Identify subcategories (if any)
2.2: Identify sub-subcategories (if any)
2.3: Continue until you reach **leaf nodes** (benefits with coverage values)

**STEP 3: Create Leaf Nodes**

For each leaf:
- Generate hierarchical `path` (variable depth)
- Create unique `leaf_id`
- Write clear `description`
- Note `basis` if it's a universal distinction (S.S. status, medical type, etc.)

**STEP 4: Group by Category**

Organize all leaves under their top-level category.

**STEP 5: Validate**

✓ All ProBTP benefits covered?
✓ Vendor-specific modifiers excluded?
✓ Universal distinctions included?
✓ Leaf IDs are unique?
✓ Paths reflect ProBTP's structure?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Output Language:** {language}

**Return:** ONLY the JSON object conforming to ProBTPTaxonomy schema.

**Example Output Structure:**

{{
  "categories": [
    {{
      "category_name": "Optique",
      "category_id": "optique",
      "description": "Soins et équipements optiques (lunettes, lentilles)",
      "leaves": [
        {{
          "path": ["Optique", "Lunettes", "Monture"],
          "leaf_id": "optique_lunettes_monture",
          "description": "Remboursement monture de lunettes",
          "basis": null
        }},
        {{
          "path": ["Optique", "Lunettes", "Verres", "Verres simples"],
          "leaf_id": "optique_lunettes_verres_simples",
          "description": "Verres correcteurs simples",
          "basis": "medical_classification"
        }},
        {{
          "path": ["Optique", "Lunettes", "Verres", "Verres complexes"],
          "leaf_id": "optique_lunettes_verres_complexes",
          "description": "Verres correcteurs complexes ou progressifs",
          "basis": "medical_classification"
        }},
        {{
          "path": ["Optique", "Lentilles", "Remboursées par la S.S."],
          "leaf_id": "optique_lentilles_remboursees_ss",
          "description": "Lentilles de contact remboursées par la Sécurité Sociale",
          "basis": "securite_sociale_status"
        }},
        {{
          "path": ["Optique", "Lentilles", "Non remboursées par la S.S."],
          "leaf_id": "optique_lentilles_non_remboursees_ss",
          "description": "Lentilles de contact non remboursées par la Sécurité Sociale",
          "basis": "securite_sociale_status"
        }}
      ]
    }},
    {{
      "category_name": "Hospitalisation",
      "category_id": "hospitalisation",
      "description": "Frais d'hospitalisation et soins associés",
      "leaves": [
        {{
          "path": ["Hospitalisation", "Frais de séjour"],
          "leaf_id": "hospitalisation_frais_sejour",
          "description": "Frais de séjour hospitalier",
          "basis": null
        }},
        {{
          "path": ["Hospitalisation", "Chambre particulière"],
          "leaf_id": "hospitalisation_chambre_particuliere",
          "description": "Supplément chambre particulière",
          "basis": "service_type"
        }}
      ]
    }}
  ],
  "metadata": {{
    "source_document": "ProBTP",
    "extraction_approach": "taxonomy_first"
  }}
}}

Output the JSON now:"""

    return prompt
