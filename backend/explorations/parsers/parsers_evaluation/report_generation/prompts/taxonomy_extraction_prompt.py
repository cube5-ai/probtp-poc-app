"""Taxonomy extraction prompt for building reference taxonomy from ProBTP contract.

This prompt extracts a universal, hierarchical taxonomy that:
1. Reflects ProBTP's organizational structure (the reference for comparison)
2. Includes universal insurance/medical distinctions (transferable across insurers)
3. Excludes vendor-specific modifiers (those become conditions during value extraction)

Updated to use recursive tree structure for better LLM generation and navigation.
"""

from pydantic import BaseModel, Field
from typing import Optional


class TaxonomyNode(BaseModel):
    """A node in the taxonomy (can be category, subcategory, or leaf).

    This flat structure with parent_id references allows the taxonomy to have variable depth
    while being compatible with LLM structured output schemas. Nodes are output in depth-first
    order to match the document structure.
    """

    # ============ IDENTITY ============
    node_id: str = Field(
        ...,
        description="Unique identifier using snake_case. Examples: 'optique', 'optique_lunettes', 'optique_lunettes_verres_simples'"
    )

    name: str = Field(
        ...,
        description="Human-readable name for this node. Examples: 'Optique', 'Lunettes', 'Verres simples'"
    )

    description: str = Field(
        ...,
        description="Clear description of what this node represents. Examples: 'Soins et équipements optiques', 'Verres correcteurs simples'"
    )

    # ============ HIERARCHY ============
    parent_id: Optional[str] = Field(
        None,
        description="ID of parent node. Null for top-level categories. Examples: 'optique' is parent of 'optique_lunettes'"
    )

    level: int = Field(
        ...,
        description="Depth in tree (0=top-level category, 1=subcategory, 2=sub-subcategory, etc.)"
    )

    path: list[str] = Field(
        ...,
        description="Full path from root for convenience. Example: ['Optique', 'Lunettes', 'Verres', 'Verres simples']"
    )

    # ============ NODE TYPE ============
    is_leaf: bool = Field(
        ...,
        description="True if this represents a measurable benefit with actual coverage values. False if it's a container/category."
    )

    # ============ LEAF-SPECIFIC ATTRIBUTES ============
    basis: Optional[str] = Field(
        None,
        description="ONLY for leaves: What makes this a distinct category. Examples: 'securite_sociale_status', 'medical_classification', 'age_bracket', 'service_type', 'network_requirement'. Omit if straightforward or if not a leaf."
    )

    # ============ OPTIONAL METADATA ============
    source_section: Optional[str] = Field(
        None,
        description="Optional: reference to where in source document this was found (e.g., page number, table name)"
    )

    notes: Optional[str] = Field(
        None,
        description="Optional: any additional context or clarifications"
    )


class ProBTPTaxonomy(BaseModel):
    """Complete ProBTP taxonomy as a flat list with parent-child references.

    Nodes are listed in depth-first order, making it easy to read and understand
    the hierarchy while remaining compatible with LLM structured output schemas.
    """

    nodes: list[TaxonomyNode] = Field(
        ...,
        description="ALL taxonomy nodes (categories, subcategories, and leaves) in depth-first order. Top-level categories have parent_id=null."
    )

    metadata: dict[str, str] = Field(
        ...,
        description="Extraction metadata. Should include: source_document, extraction_date, extraction_approach, extractor_model, etc."
    )


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

    prompt = f"""You are an expert insurance analyst specializing in French health insurance (mutuelle) contracts. Your task is to extract a COMPLETE UNIVERSAL TAXONOMY from the ProBTP reference document as a FLAT LIST IN DEPTH-FIRST ORDER.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL: EXTRACT UNIVERSAL TAXONOMY AS A FLAT LIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**What is a Taxonomy?**

A taxonomy is a hierarchical classification system that defines:
- **Top-level categories** (e.g., "Hospitalisation", "Optique", "Soins Courants")
- **Subcategories at multiple levels** (variable depth - no fixed limit)
- **Leaf nodes** (specific, measurable benefits that have actual coverage values)

**Why a Flat Structure with parent_id?**

Instead of recursive nesting, we use a FLAT LIST where:
- ✓ Each node has a `parent_id` pointing to its parent (null for top-level)
- ✓ Nodes are listed in DEPTH-FIRST ORDER (as they appear in the document)
- ✓ This captures the ORGANIZATIONAL LOGIC while being schema-compatible
- ✓ It makes validation and navigation easier

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

**1. Think Hierarchically in Depth-First Order**

Start from the top and list nodes as you encounter them (depth-first):

Step 1: List top-level category (parent_id=null, level=0)
→ Add node: "Hospitalisation"

Step 2: For that category, list its immediate children (parent_id="hospitalisation", level=1)
→ Add node: "Frais de séjour" (parent: hospitalisation)
→ Add node: "Chambre particulière" (parent: hospitalisation)

Step 3: Before moving to next top-level category, complete the FULL TREE for current category
→ If "Verres" has children, add them immediately after "Verres" node

Step 4: Move to next top-level category and repeat

**Depth-First Order Example:**
```
Optique (level=0, parent_id=null)
  Lunettes (level=1, parent_id="optique")
    Monture (level=2, parent_id="optique_lunettes", is_leaf=true)
    Verres (level=2, parent_id="optique_lunettes")
      Verres simples (level=3, parent_id="optique_lunettes_verres", is_leaf=true)
      Verres complexes (level=3, parent_id="optique_lunettes_verres", is_leaf=true)
  Lentilles (level=1, parent_id="optique")
    ...
```

**2. Variable Depth (IMPORTANT)**

The taxonomy has **variable depth** - some branches are shallow, others are deep:
- "Hospitalisation → Chambre particulière" (2 levels total)
- "Optique → Lunettes → Verres → Verres simples" (4 levels total)
- "Soins Courants → Médecines douces → Ostéopathie" (3 levels total)

**DO NOT enforce a fixed number of levels.** Extract the natural structure from ProBTP's document.

**3. What is a Leaf Node?**

A **leaf** is the finest granularity where:
- There is an actual **coverage value** that can be measured
- It represents a **specific, billable benefit**
- It's the endpoint for value extraction
- `is_leaf=true` (no child nodes will reference this as parent)

Examples:
- ✓ "Consultation médecin généraliste" (leaf - has coverage value)
- ✓ "Verres simples" (leaf - has coverage value)
- ✗ "Optique" (NOT a leaf - other nodes will have parent_id="optique")
- ✗ "Lunettes" (NOT a leaf - Monture and Verres have parent_id="optique_lunettes")

**4. Handling Complex Cases**

**Case: "Lentilles remboursées S.S." vs "Lentilles non remboursées S.S."**
- These are **separate leaf nodes** (different benefits)
- Output in depth-first order:
  1. Lentilles (level=1, parent_id="optique", is_leaf=false)
  2. Remboursées par la S.S. (level=2, parent_id="optique_lentilles", is_leaf=true)
  3. Non remboursées par la S.S. (level=2, parent_id="optique_lentilles", is_leaf=true)

**Case: "Si partenaire Sévéane" vs "Dans les autres cas"**
- These are **NOT separate nodes** (vendor-specific modifier)
- Single leaf: Monture (parent_id="optique_lunettes", is_leaf=true)
- "Si partenaire Sévéane" → extracted as **vendor condition** during value extraction

**Case: "Verres simples" vs "Verres progressifs"**
- These are **separate leaf nodes** (medical/optical classification)
- Output in depth-first order:
  1. Verres (level=2, parent_id="optique_lunettes", is_leaf=false)
  2. Verres simples (level=3, parent_id="optique_lunettes_verres", is_leaf=true)
  3. Verres progressifs (level=3, parent_id="optique_lunettes_verres", is_leaf=true)
  4. Verres complexes (level=3, parent_id="optique_lunettes_verres", is_leaf=true)

**5. Generating node_id**

Create unique identifiers using snake_case by joining the path:
- Path: ["Optique", "Lunettes", "Verres", "Verres simples"]
- node_id: "optique_lunettes_verres_simples"

- Path: ["Hospitalisation", "Chambre particulière"]
- node_id: "hospitalisation_chambre_particuliere"

- Path: ["Optique"]
- node_id: "optique"

**6. Generating path**

The path is the full list from root to current node:
- Top-level category: ["Hospitalisation"]
- Subcategory: ["Hospitalisation", "Frais de séjour"]
- Leaf: ["Optique", "Lunettes", "Verres", "Verres simples"]

**7. Completeness Check**

For each top-level category (e.g., "Optique"), ensure you extract:
- ✓ ALL subcategories from ProBTP's table
- ✓ ALL nested levels until you reach leaves
- ✓ ALL leaf-level benefits with distinct coverage values
- ✓ ALL universal distinctions (S.S. status, medical types, etc.)

**Missing nodes = failed extraction.** Be thorough and systematic.

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
- "Audiologie" (or "Aides auditives")
- "Médecines Douces" (or "Prestations")
- "Prévention"
- etc.

**STEP 2: For Each Category, Extract Nodes in Depth-First Order**

For each top-level category:

2.1: Add the category node (level=0, parent_id=null, is_leaf=false)
2.2: Add its immediate children (level=1, parent_id=category_id)
2.3: For each child that has sub-children, add those IMMEDIATELY after the child
2.4: Continue depth-first until all leaves are reached
2.5: Move to next top-level category

**STEP 3: For Each Node, Fill in Attributes**

For EVERY node (category, subcategory, or leaf):
- Generate node_id (snake_case from path)
- Set name (human-readable)
- Write description
- Set parent_id (null for top-level, otherwise parent's node_id)
- Set level (depth in tree: 0, 1, 2, ...)
- Set path (list from root to this node)
- Set is_leaf (true only if this is a measurable benefit endpoint)

For LEAF nodes only:
- Set basis if it's a universal distinction (otherwise null)

**STEP 4: Validate the Taxonomy**

Before outputting, check:
✓ All top-level categories covered?
✓ Every non-leaf has at least one child referencing it as parent_id?
✓ Every leaf has is_leaf=true and no nodes reference it as parent_id?
✓ Nodes are in depth-first order?
✓ Vendor-specific modifiers excluded?
✓ Universal distinctions included?
✓ Node IDs are unique and consistent?
✓ Paths are correct and complete?
✓ parent_id references are valid (point to existing nodes)?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Output Language:** {language}

**Return:** ONLY the JSON object conforming to ProBTPTaxonomy schema.

**Example Output Structure (Depth-First Flat List):**

{{
  "nodes": [
    // Top-level category: Optique
    {{
      "node_id": "optique",
      "name": "Optique",
      "description": "Soins et équipements optiques (lunettes, lentilles, chirurgie réfractive)",
      "parent_id": null,
      "level": 0,
      "path": ["Optique"],
      "is_leaf": false,
      "basis": null
    }},
    // Optique → Lunettes
    {{
      "node_id": "optique_lunettes",
      "name": "Lunettes",
      "description": "Équipements optiques de correction (montures et verres)",
      "parent_id": "optique",
      "level": 1,
      "path": ["Optique", "Lunettes"],
      "is_leaf": false,
      "basis": null
    }},
    // Optique → Lunettes → Monture (leaf)
    {{
      "node_id": "optique_lunettes_monture",
      "name": "Monture",
      "description": "Remboursement de la monture de lunettes",
      "parent_id": "optique_lunettes",
      "level": 2,
      "path": ["Optique", "Lunettes", "Monture"],
      "is_leaf": true,
      "basis": null
    }},
    // Optique → Lunettes → Verres (container)
    {{
      "node_id": "optique_lunettes_verres",
      "name": "Verres",
      "description": "Verres correcteurs (différents types selon correction)",
      "parent_id": "optique_lunettes",
      "level": 2,
      "path": ["Optique", "Lunettes", "Verres"],
      "is_leaf": false,
      "basis": null
    }},
    // Optique → Lunettes → Verres → Verres simples (leaf)
    {{
      "node_id": "optique_lunettes_verres_simples",
      "name": "Verres simples",
      "description": "Verres correcteurs unifocaux simples",
      "parent_id": "optique_lunettes_verres",
      "level": 3,
      "path": ["Optique", "Lunettes", "Verres", "Verres simples"],
      "is_leaf": true,
      "basis": "medical_classification"
    }},
    // Optique → Lunettes → Verres → Verres complexes (leaf)
    {{
      "node_id": "optique_lunettes_verres_complexes",
      "name": "Verres complexes",
      "description": "Verres correcteurs complexes ou progressifs",
      "parent_id": "optique_lunettes_verres",
      "level": 3,
      "path": ["Optique", "Lunettes", "Verres", "Verres complexes"],
      "is_leaf": true,
      "basis": "medical_classification"
    }},
    // Optique → Lentilles (container)
    {{
      "node_id": "optique_lentilles",
      "name": "Lentilles",
      "description": "Lentilles de contact correctrices",
      "parent_id": "optique",
      "level": 1,
      "path": ["Optique", "Lentilles"],
      "is_leaf": false,
      "basis": null
    }},
    // Optique → Lentilles → Remboursées SS (leaf)
    {{
      "node_id": "optique_lentilles_remboursees_ss",
      "name": "Remboursées par la S.S.",
      "description": "Lentilles de contact remboursées par la Sécurité Sociale",
      "parent_id": "optique_lentilles",
      "level": 2,
      "path": ["Optique", "Lentilles", "Remboursées par la S.S."],
      "is_leaf": true,
      "basis": "securite_sociale_status"
    }},
    // Optique → Lentilles → Non remboursées SS (leaf)
    {{
      "node_id": "optique_lentilles_non_remboursees_ss",
      "name": "Non remboursées par la S.S.",
      "description": "Lentilles de contact non remboursées par la Sécurité Sociale",
      "parent_id": "optique_lentilles",
      "level": 2,
      "path": ["Optique", "Lentilles", "Non remboursées par la S.S."],
      "is_leaf": true,
      "basis": "securite_sociale_status"
    }},
    // Optique → Chirurgie réfractive (leaf)
    {{
      "node_id": "optique_chirurgie_refractive",
      "name": "Chirurgie réfractive",
      "description": "Chirurgie de correction de la vue (laser, etc.)",
      "parent_id": "optique",
      "level": 1,
      "path": ["Optique", "Chirurgie réfractive"],
      "is_leaf": true,
      "basis": "service_type"
    }},
    // Top-level category: Hospitalisation
    {{
      "node_id": "hospitalisation",
      "name": "Hospitalisation",
      "description": "Frais d'hospitalisation et soins associés",
      "parent_id": null,
      "level": 0,
      "path": ["Hospitalisation"],
      "is_leaf": false,
      "basis": null
    }},
    // Hospitalisation → Frais de séjour (leaf)
    {{
      "node_id": "hospitalisation_frais_sejour",
      "name": "Frais de séjour",
      "description": "Frais de séjour hospitalier (médicaux et chirurgicaux)",
      "parent_id": "hospitalisation",
      "level": 1,
      "path": ["Hospitalisation", "Frais de séjour"],
      "is_leaf": true,
      "basis": null
    }},
    // Hospitalisation → Chambre particulière (leaf)
    {{
      "node_id": "hospitalisation_chambre_particuliere",
      "name": "Chambre particulière",
      "description": "Supplément pour chambre particulière",
      "parent_id": "hospitalisation",
      "level": 1,
      "path": ["Hospitalisation", "Chambre particulière"],
      "is_leaf": true,
      "basis": "service_type"
    }},
    // Hospitalisation → Forfait journalier (leaf)
    {{
      "node_id": "hospitalisation_forfait_journalier",
      "name": "Forfait journalier",
      "description": "Forfait journalier hospitalier",
      "parent_id": "hospitalisation",
      "level": 1,
      "path": ["Hospitalisation", "Forfait journalier"],
      "is_leaf": true,
      "basis": null
    }}
  ],
  "metadata": {{
    "source_document": "ProBTP GARANTIES 2025",
    "extraction_date": "2025-01-XX",
    "extraction_approach": "flat_depth_first",
    "extractor_model": "gemini-2.5-flash"
  }}
}}

**CRITICAL REMINDERS:**

1. Output nodes in DEPTH-FIRST ORDER (complete each category before moving to next)
2. Use parent_id to indicate hierarchy (null for top-level)
3. Variable depth is NORMAL and EXPECTED
4. A leaf has is_leaf=true (no other nodes reference it as parent)
5. A non-leaf has is_leaf=false (other nodes reference it as parent_id)
6. Exclude vendor-specific modifiers (network bonuses, administrative requirements)
7. Include universal distinctions (S.S. status, medical classifications, age brackets)
8. Be COMPLETE - missing nodes means failed extraction
9. Validate before outputting

Output the complete JSON now:"""

    return prompt
