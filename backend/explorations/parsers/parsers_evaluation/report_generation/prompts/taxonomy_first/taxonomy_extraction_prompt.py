"""Taxonomy extraction prompt for building reference taxonomy from ProBTP contract.

This prompt extracts a universal, hierarchical taxonomy that:
1. Reflects ProBTP's organizational structure (the reference for comparison)
2. Includes universal insurance/medical distinctions (transferable across insurers)
3. Excludes vendor-specific modifiers (those become conditions during value extraction)

Updated to use recursive tree structure for better LLM generation and navigation.
"""

from pydantic import BaseModel, Field


class ExtractionMetadata(BaseModel):
    """Metadata about the taxonomy extraction."""
    source_document: str = Field(..., description="Name of the source document")
    extraction_date: str = Field(..., description="Date of extraction (ISO format)")
    extraction_approach: str = Field(..., description="Approach used for extraction")
    extractor_model: str = Field(..., description="Model used for extraction")


class TaxonomyNode(BaseModel):
    """A node in the taxonomy (can be category, subcategory, or leaf).

    This flat structure with parent_id references allows the taxonomy to have variable depth
    while being compatible with LLM structured output schemas. Nodes are output in depth-first
    order to match the document structure.
    """

    # ============ IDENTITY ============
    name: str = Field(
        ...,
        description="Human-readable name for this node. Should be a clean category name WITHOUT units, caps, or frequency (e.g., 'Monture' not 'Monture 150€ max'). Examples: 'Optique', 'Lunettes', 'Verres simples', 'Chambre particulière'"
    )

    node_id: str = Field(
        ...,
        description="Unique identifier using snake_case. Examples: 'optique', 'optique_lunettes', 'optique_lunettes_verres_simples'"
    )

    description: str = Field(
        ...,
        description="Clear description of what this node represents. Examples: 'Soins et équipements optiques', 'Verres correcteurs simples'"
    )

    # ============ HIERARCHY ============
    parent_id: str = Field(
        ...,
        description="ID of parent node. Use '_root_' for top-level categories. Examples: 'optique' is parent of 'optique_lunettes'"
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

    # ============ NODE CONDITIONS ============
    conditions: str | None = Field(
        None,
        description="Node-level conditions or constraints as prescribed by footnotes, annotations, or equivalent markers. These help refine what is meant for this node. Examples: 'Sous réserve d\\'accord préalable', 'Maximum 2 équipements par an', 'Uniquement pour certaines pathologies'. Leave null if no conditions apply."
    )

    # ============ SÉCURITÉ SOCIALE COVERAGE ============
    securite_sociale_coverage: str | None = Field(
        None,
        description="Sécurité Sociale (S.S.) reimbursement information for this benefit. Only applicable to leaf nodes. Examples: '60% BR', '70% du tarif de convention', 'Non remboursé par la S.S.', '100% BRSS'. Leave null for non-leaf nodes or if S.S. coverage is not specified."
    )

    # ============ OPTIONAL METADATA ============
    source_section: str | None = Field(
        None,
        description="Optional: reference to where in source document this was found (e.g., page number, table name)"
    )

    notes: str | None = Field(
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

**3. Capturing Node-Level Conditions**

Many nodes (both leaves and non-leaves) may have **conditions** specified via:
- Footnotes (e.g., markers like *, †, ‡, (1), (2))
- Annotations or parenthetical notes
- Explicit constraints in the text

These conditions help refine what is meant for the node and should be captured:
- ✓ "Sous réserve d'accord préalable" (requires prior approval)
- ✓ "Maximum 2 équipements par an" (frequency limit)
- ✓ "Uniquement pour certaines pathologies" (scope constraint)
- ✓ "Maximum 1 intervention par œil et par vie" (lifetime limit)
- ✓ "Sur présentation de devis" (procedural requirement)

**When to capture as conditions vs. excluding:**
- If it's a **universal constraint** that helps define the benefit → capture in `conditions`
- If it's **vendor-specific** (network bonuses, ProBTP-specific programs) → exclude entirely

**4. What is a Leaf Node?**

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

**IMPORTANT:** Use only the clean category name (without units, caps, or frequency) when generating node_id and path. For example, if you see "Monture (150€ maximum)", the name is "Monture" and NOT "Monture (150€ maximum)".

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
- Set name (human-readable, clean category name ONLY)
  ✓ Correct: "Chambre particulière", "Monture", "Verres simples"
  ✗ Wrong: "Chambre particulière 60€/jour", "Monture (150€ max)", "Verres simples - 2 équipements/an"
- Generate node_id (snake_case from path)
- Write description
- Set parent_id (null for top-level, otherwise parent's node_id)
- Set level (depth in tree: 0, 1, 2, ...)
- Set path (list from root to this node)
- Set is_leaf (true only if this is a measurable benefit endpoint)


For ANY node (leaf or non-leaf):
- Set conditions if footnotes, annotations, or markers specify constraints
  Examples: "Sous réserve d'accord préalable", "Maximum 2 équipements par an"

For LEAF nodes only:
- Set securite_sociale_coverage if S.S. reimbursement information is available
  Examples: "60% BR", "70% du tarif de convention", "Non remboursé par la S.S.", "100% BRSS"
  This is informative data about the baseline Sécurité Sociale coverage for this benefit

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
      "name": "Optique",
      "path": ["Optique"],
      "node_id": "optique",
      "description": "Soins et équipements optiques (lunettes, lentilles, chirurgie réfractive)",
      "parent_id": "_root_",
      "level": 0,
      "is_leaf": false
    }},
    // Optique → Lunettes
    {{
      "name": "Lunettes",
      "path": ["Optique", "Lunettes"],
      "node_id": "optique_lunettes",
      "description": "Équipements optiques de correction (montures et verres)",
      "parent_id": "optique",
      "level": 1,
      "is_leaf": false
    }},
    // Optique → Lunettes → Monture (leaf)
    {{
      "name": "Monture",
      "path": ["Optique", "Lunettes", "Monture"],
      "node_id": "optique_lunettes_monture",
      "description": "Remboursement de la monture de lunettes",
      "parent_id": "optique_lunettes",
      "level": 2,
      "is_leaf": true,
      "securite_sociale_coverage": "60% BR"
    }},
    // Optique → Lunettes → Verres (container)
    {{
      "name": "Verres",
      "path": ["Optique", "Lunettes", "Verres"],
      "node_id": "optique_lunettes_verres",
      "description": "Verres correcteurs (différents types selon correction)",
      "parent_id": "optique_lunettes",
      "level": 2,
      "is_leaf": false
    }},
    // Optique → Lunettes → Verres → Verres simples (leaf)
    {{
      "name": "Verres simples",
      "path": ["Optique", "Lunettes", "Verres", "Verres simples"],
      "node_id": "optique_lunettes_verres_simples",
      "description": "Verres correcteurs unifocaux simples",
      "parent_id": "optique_lunettes_verres",
      "level": 3,
      "is_leaf": true,
      "securite_sociale_coverage": "60% BR"
    }},
    // Optique → Lunettes → Verres → Verres complexes (leaf)
    {{
      "name": "Verres complexes",
      "path": ["Optique", "Lunettes", "Verres", "Verres complexes"],
      "node_id": "optique_lunettes_verres_complexes",
      "description": "Verres correcteurs complexes ou progressifs",
      "parent_id": "optique_lunettes_verres",
      "level": 3,
      "is_leaf": true,
      "securite_sociale_coverage": "60% BR"
    }},
    // Optique → Lentilles (container)
    {{
      "name": "Lentilles",
      "path": ["Optique", "Lentilles"],
      "node_id": "optique_lentilles",
      "description": "Lentilles de contact correctrices",
      "parent_id": "optique",
      "level": 1,
      "is_leaf": false
    }},
    // Optique → Lentilles → Remboursées SS (leaf)
    {{
      "name": "Remboursées par la S.S.",
      "path": ["Optique", "Lentilles", "Remboursées par la S.S."],
      "node_id": "optique_lentilles_remboursees_ss",
      "description": "Lentilles de contact remboursées par la Sécurité Sociale",
      "parent_id": "optique_lentilles",
      "level": 2,
      "is_leaf": true,
      "securite_sociale_coverage": "60% du tarif de convention"
    }},
    // Optique → Lentilles → Non remboursées SS (leaf)
    {{
      "name": "Non remboursées par la S.S.",
      "path": ["Optique", "Lentilles", "Non remboursées par la S.S."],
      "node_id": "optique_lentilles_non_remboursees_ss",
      "description": "Lentilles de contact non remboursées par la Sécurité Sociale",
      "parent_id": "optique_lentilles",
      "level": 2,
      "is_leaf": true,
      "securite_sociale_coverage": "Non remboursé par la S.S."
    }},
    // Optique → Chirurgie réfractive (leaf with conditions)
    {{
      "name": "Chirurgie réfractive",
      "path": ["Optique", "Chirurgie réfractive"],
      "node_id": "optique_chirurgie_refractive",
      "description": "Chirurgie de correction de la vue (laser, etc.)",
      "parent_id": "optique",
      "level": 1,
      "path": ["Optique", "Chirurgie réfractive"],
      "is_leaf": true,
      "conditions": "Sous réserve d'accord préalable. Maximum 1 intervention par œil et par vie.",
      "securite_sociale_coverage": "Non remboursé par la S.S."
    }},
    // Top-level category: Hospitalisation
    {{
      "name": "Hospitalisation",
      "path": ["Hospitalisation"],
      "node_id": "hospitalisation",
      "description": "Frais d'hospitalisation et soins associés",
      "parent_id": "_root_",
      "level": 0,
      "is_leaf": false
    }},
    // Hospitalisation → Frais de séjour (leaf)
    {{
      "name": "Frais de séjour",
      "path": ["Hospitalisation", "Frais de séjour"],
      "node_id": "hospitalisation_frais_sejour",
      "description": "Frais de séjour hospitalier (médicaux et chirurgicaux)",
      "parent_id": "hospitalisation",
      "level": 1,
      "is_leaf": true,
      "securite_sociale_coverage": "80% du tarif de convention"
    }},
    // Hospitalisation → Chambre particulière (leaf)
    {{
      "name": "Chambre particulière",
      "path": ["Hospitalisation", "Chambre particulière"],
      "node_id": "hospitalisation_chambre_particuliere",
      "description": "Supplément pour chambre particulière",
      "parent_id": "hospitalisation",
      "level": 1,
      "is_leaf": true,
      "securite_sociale_coverage": "Non remboursé par la S.S."
    }},
    // Hospitalisation → Forfait journalier (leaf)
    {{
      "name": "Forfait journalier",
      "path": ["Hospitalisation", "Forfait journalier"],
      "node_id": "hospitalisation_forfait_journalier",
      "description": "Forfait journalier hospitalier",
      "parent_id": "hospitalisation",
      "level": 1,
      "is_leaf": true,
      "securite_sociale_coverage": "100% BRSS"
    }}
  ]
}}

**CRITICAL REMINDERS:**

1. Output nodes in DEPTH-FIRST ORDER (complete each category before moving to next)
2. Use parent_id to indicate hierarchy ('_root_' for top-level)
3. Variable depth is NORMAL and EXPECTED
4. A leaf has is_leaf=true (no other nodes reference it as parent)
5. A non-leaf has is_leaf=false (other nodes reference it as parent_id)
6. Exclude vendor-specific modifiers (network bonuses, administrative requirements)
7. Include universal distinctions (S.S. status, medical classifications, age brackets)
8. Be COMPLETE - missing nodes means failed extraction
9. Validate before outputting

Output the complete JSON now:"""

    return prompt
