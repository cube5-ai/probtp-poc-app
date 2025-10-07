"""Analysis prompt for taxonomy-first pipeline.

This prompt analyzes leaf-based comparison documents and outputs structured
leaf comparisons with advantage levels plus narrative summaries.
"""

import json
from enum import Enum

from pydantic import BaseModel, Field


class ProBTPAdvantage(str, Enum):
    """ProBTP advantage level relative to AXA."""

    MUCH_BETTER = "probtp_much_better"
    BETTER = "probtp_better"
    EQUAL = "equal"
    WORSE = "probtp_worse"
    MUCH_WORSE = "probtp_much_worse"


class LeafAnalysis(BaseModel):
    """Analysis result for a single taxonomy leaf comparison."""

    leaf_id: str = Field(..., description="Taxonomy leaf ID")
    probtp_advantage: ProBTPAdvantage = Field(
        ..., description="ProBTP advantage level relative to AXA"
    )
    rationale: str = Field(
        ..., description="Brief rationale for advantage assessment (1-2 sentences)"
    )
    probtp_display_value: str = Field(
        ..., description="ProBTP value formatted for display (e.g., '150€/2 ans', 'Non couvert')"
    )
    axa_display_value: str = Field(
        ..., description="AXA value formatted for display (e.g., '100€/2 ans', 'Non couvert')"
    )


class ObjectiveAssessment(BaseModel):
    """Brutally objective comparison assessment."""

    overall_winner: str = Field(
        ...,
        description="'probtp' or 'axa' - which contract is objectively better for this category",
    )
    confidence: str = Field(
        ..., description="'high', 'medium', or 'low' - confidence in the assessment"
    )
    reasoning: str = Field(
        ...,
        description="Brutally honest explanation of why, even if unfavorable to ProBTP",
    )
    probtp_weaknesses: list[str] = Field(
        ..., description="Specific areas where ProBTP is objectively weaker"
    )
    axa_weaknesses: list[str] = Field(
        ..., description="Specific areas where AXA is objectively weaker"
    )


class TaxonomyFirstAnalysisOutput(BaseModel):
    """Complete analysis output for taxonomy-first pipeline."""

    category: str = Field(..., description="Category name")

    # LEAF-LEVEL COMPARISONS (primary structured output)
    leaf_comparisons: list[LeafAnalysis] = Field(
        ..., description="Detailed comparison for each taxonomy leaf"
    )

    # OBJECTIVE ASSESSMENT
    objective_assessment: ObjectiveAssessment = Field(
        ..., description="Brutally honest competitive assessment"
    )

    # NARRATIVE SUMMARIES (synthesized from leaves)
    key_differences: str = Field(
        ...,
        description="Plain language explanation of main differences (2-3 sentences)",
    )
    concrete_examples: list[str] = Field(
        ..., description="2-3 specific scenarios with euro amounts"
    )
    critical_thinking: str = Field(
        ..., description="Analysis of real-world value, risk, and customer fit"
    )
    best_coverage: str = Field(
        ..., description="Sales-oriented determination of ProBTP's value proposition"
    )
    salesperson_talking_points: list[str] = Field(
        ..., description="3-5 key points for ProBTP salespeople to emphasize"
    )



def create_taxonomy_first_analysis_prompt(
    comparison_document: dict,
    other_categories: list[str] | None = None,
    language: str = "French (France)",
) -> str:
    """
    Create analysis prompt for taxonomy-first pipeline.

    Args:
        comparison_document: ComparisonDocument dict (LLM-optimized, source_cell_ids stripped)
        other_categories: List of other categories being analyzed separately
        language: Output language

    Returns:
        Formatted prompt string
    """
    category_id = comparison_document.get("category_id", "unknown")
    category_name = comparison_document.get("category_name", category_id)
    probtp_level = comparison_document.get("probtp_policy_level", "")
    axa_level = comparison_document.get("axa_policy_level", "")
    leaves = comparison_document.get("leaves", [])

    # Format comparison document as JSON
    comparison_json = json.dumps(comparison_document, indent=2, ensure_ascii=False)

    # Format policy levels context
    levels_context = f"""
**Contract Levels Being Compared:**
- ProBTP: {probtp_level}
- AXA: {axa_level}
"""

    # Format category boundaries context
    boundaries_context = ""
    if other_categories:
        boundaries_context = f"""
**Other Categories (analyzed separately):**
{chr(10).join(f"- {cat}" for cat in other_categories)}

*Note: This analysis focuses ONLY on the "{category_name}" category. Benefits from other categories are excluded to prevent redundancy.*
"""

    prompt = f"""You are an expert insurance analyst specializing in French health insurance. Your task is to analyze a leaf-based comparison document and generate comprehensive insights with structured leaf comparisons.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Generate comprehensive analysis including:
1. **Leaf-level comparisons** with advantage levels (>>, >, ~, <, <<) for filtering
2. **Narrative summaries** synthesized from leaf comparisons
3. **Sales-ready insights** for ProBTP sales team
4. **Brutally objective assessment** of which contract is actually better

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS COMPONENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1. Leaf-Level Comparisons** (structured output)

For EACH leaf in the comparison document:
- **probtp_advantage**: Assess ProBTP's advantage relative to AXA based on LLM judgment:
  - `probtp_much_better`: ProBTP significantly better coverage that materially impacts beneficiary
  - `probtp_better`: ProBTP moderately better coverage with noticeable advantage
  - `equal`: Roughly equivalent or minor differences
  - `probtp_worse`: ProBTP moderately worse coverage
  - `probtp_much_worse`: ProBTP significantly worse coverage
- **rationale**: 1-2 sentence explanation of the advantage assessment
- **display values**: Format coverage for human readability

**ProBTP Advantage Determination:**

Use your world knowledge of French health insurance and beneficiary psychology to assess ProBTP relative to AXA:

**Examples:**
- ProBTP 150€ vs AXA 100€ for glasses frames → `probtp_much_better` (50€ difference is significant)
- ProBTP 200€ vs AXA 180€ for dental crown → `probtp_better` (20€ difference is noticeable)
- ProBTP 100% BR vs AXA 100% BR → `equal` (identical coverage)
- ProBTP "Non couvert" vs AXA 300€ for laser surgery → `probtp_much_worse` (no coverage vs coverage)

**Context matters:**
- Small € differences on high-cost items (e.g., €20 on €2000 orthodontics) → `equal`
- Small € differences on frequent items (e.g., €5 on doctor visits) → `probtp_better` or `probtp_much_better` (cumulative impact)
- Coverage caps: 500€ cap vs no cap on €400 benefit → `equal` (cap unlikely to hit)
- Coverage caps: 300€ cap vs no cap on €1000+ benefit → advantage to uncapped insurer (cap very limiting)

**2. Objective Assessment** (brutally honest)
- **overall_winner**: 'probtp' or 'axa' - which contract is objectively better
- **confidence**: 'high', 'medium', or 'low'
- **reasoning**: Honest explanation even if unfavorable to ProBTP
- **probtp_weaknesses**: Specific areas where ProBTP is objectively weaker
- **axa_weaknesses**: Specific areas where AXA is objectively weaker

**3. Key Differences** (2-3 sentences)
- Main strategic differences between ProBTP and AXA for this category
- Which contract emphasizes what type of coverage?

**4. Concrete Examples** (2-3 specific scenarios)
- Realistic scenarios showing actual costs and reimbursements
- Exact out-of-pocket costs for each contract
- Use typical service prices (e.g., dental crown €750, progressive glasses €600)
- Format: "For [service] costing €X, ProBTP reimburses €Y (remain €Z), AXA reimburses €A (remain €B)"

**5. Critical Thinking & Value Assessment**
- **Real-world probability:** How often do people use these benefits?
- **Financial risk:** Which benefits protect against the highest financial exposure?
- **Customer segments:** Which types of customers benefit most from each contract?
- **Hidden value:** Network benefits, caps, or conditions that change value proposition

**6. Best Coverage** (1-2 paragraphs, ProBTP sales perspective)
- Sales-oriented framing of ProBTP's value proposition
- Specific sub-categories where ProBTP wins
- What salespeople should emphasize
- How to contextualize gaps where AXA is better

**7. Salesperson Talking Points** (3-5 key points)
- Actionable points for ProBTP salespeople
- Focus on ProBTP strengths and how to frame them
- How to address competitive gaps


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DUAL PERSPECTIVE REQUIREMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This analysis serves TWO distinct purposes:

**Part 1: Sales-Ready Insights (ProBTP Perspective)**
- Frame comparisons from ProBTP's perspective
- Highlight ProBTP strengths quantitatively
- Contextualize ProBTP gaps (is it worth it? does it matter?)
- Provide actionable talking points for salespeople
- Focus on what salespeople can say about ProBTP's value

**Part 2: Objective Assessment (Analyst Perspective)**
- Be brutally honest about which contract is objectively better
- Do NOT sugarcoat or spin results to favor ProBTP
- Clearly state ProBTP weaknesses where they exist
- Use "high" confidence when the winner is clear
- This section is for internal strategy, not customer-facing

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LEAF COMPARISON METHODOLOGY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each leaf, compare ProBTP vs AXA values considering:

**1. Coverage Amounts**
- Higher € amount or % BR = better
- "Non couvert" = worst

**2. Frequency Restrictions**
- Less restrictive frequency = better
- "par an" vs "tous les 2 ans" → annual is better
- No frequency limit = best

**3. Coverage Caps**
- Higher or no cap = better (if rates are similar)
- Consider typical service costs when evaluating cap impact

**4. Age Restrictions**
- Fewer age restrictions = better
- Broader coverage = better

**5. Vendor Conditions**
- Network bonuses: Can improve value but may not be accessible to all
- Administrative requirements: More requirements = worse
- Consider accessibility and practical usability

**6. Practical Value**
- Real-world usage patterns
- Financial impact on typical beneficiary
- Cumulative savings over time

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HANDLING UNMAPPABLE ITEMS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Leaves with `is_unmappable_probtp_only: true` or `is_unmappable_axa_only: true`:

**If ProBTP-only unmappable:**
- probtp_advantage: `probtp_much_better` (ProBTP covers something AXA doesn't)
- Highlight this in narrative as ProBTP unique benefit

**If AXA-only unmappable:**
- probtp_advantage: `probtp_much_worse` (AXA covers something ProBTP doesn't)
- Acknowledge this gap honestly in objective assessment
- In sales talking points: contextualize why this gap may not matter (or does matter)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK PARAMETERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Category:** {category_name}{levels_context}{boundaries_context}

**Output Language:** {language}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPARISON DOCUMENT (LEAF-BASED)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The comparison document below contains all leaves for the "{category_name}" category.
Each leaf shows ProBTP and AXA values side-by-side with all extracted fields.

**Structure:**
- `leaf_id`: Unique identifier
- `path`: Taxonomy hierarchy path
- `description`: Leaf description
- `probtp`: Full ProBTP ExtractedValue (coverage, frequency, cap, age_restriction, vendor_conditions, etc.)
- `axa`: Full AXA ExtractedValue
- `is_unmappable_probtp_only`: True if this is a ProBTP-only benefit not in taxonomy
- `is_unmappable_axa_only`: True if this is an AXA-only benefit not in taxonomy

**Comparison Document JSON:**

```json
{comparison_json}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY a JSON object conforming to the TaxonomyFirstAnalysisOutput schema.

**Example Output Structure:**

{{
  "category": "{category_name}",
  "leaf_comparisons": [
    {{
      "leaf_id": "optique_lunettes_monture",
      "probtp_advantage": "probtp_much_better",
      "rationale": "ProBTP 150€ vs AXA 100€ - 50€ difference is significant for frames (50% more coverage)",
      "probtp_display_value": "150€/2 ans",
      "axa_display_value": "100€/2 ans"
    }},
    {{
      "leaf_id": "optique_lentilles_non_remboursees_ss",
      "probtp_advantage": "equal",
      "rationale": "Both offer 60€/an - identical coverage",
      "probtp_display_value": "60€/an",
      "axa_display_value": "60€/an"
    }}
  ],
  "objective_assessment": {{
    "overall_winner": "probtp",
    "confidence": "high",
    "reasoning": "ProBTP offers objectively better optical coverage with 30-50% higher reimbursements across most categories, resulting in significantly lower out-of-pocket costs",
    "probtp_weaknesses": ["No network partnership bonuses", "Lower contact lens cap"],
    "axa_weaknesses": ["Lower frame coverage", "Lower progressive lens reimbursement", "More restrictive frequency limits"]
  }},
  "key_differences": "ProBTP emphasizes higher coverage amounts for frames and lenses, while AXA focuses on baseline coverage with network advantages...",
  "concrete_examples": [
    "For progressive glasses (€600 total: €200 frame + €400 lenses), ProBTP reimburses €350 (remain €250), AXA reimburses €280 (remain €320)",
    "For contact lenses costing €240/year, both reimburse €60 (remain €180)"
  ],
  "critical_thinking": "ProBTP's higher optical coverage provides better protection against the significant out-of-pocket costs...",
  "best_coverage": "From ProBTP's perspective, the S2 level excels in optical coverage by offering significantly higher reimbursements for frames and progressive lenses...",
  "salesperson_talking_points": [
    "Highlight 50% higher frame coverage (€150 vs €100) - saves €50 every 2 years",
    "Emphasize superior progressive lens coverage reducing out-of-pocket by €70",
    "Position ProBTP as premium optical protection for customers who value vision care"
  ]
}}

**Quality Standards:**
- Every leaf must have a comparison (use all {len(leaves)} leaves)
- ProBTP advantage levels must reflect real-world beneficiary impact (use LLM judgment)
- Concrete examples must use realistic euro amounts and typical service prices
- Be brutally honest in objective assessment even if unfavorable to ProBTP
- Output ONLY the JSON object - no preamble, no commentary

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK EXECUTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Based on the comparison document above, generate comprehensive analysis for the "{category_name}" category.

1. Analyze EACH of the {len(leaves)} leaves
2. Determine ProBTP advantage level using LLM judgment based on real-world impact
5. Give brutally objective assessment of which contract is objectively better
3. Synthesize narrative summaries from leaf comparisons
4. Provide sales-ready insights for ProBTP


Output all content in {language}. Output ONLY the JSON conforming to TaxonomyFirstAnalysisOutput schema.

Generate the JSON analysis now:"""

    return prompt
