"""Category recommendation prompt for policy recommendation pipeline.

This prompt analyzes a multi-level comparison document and recommends the best vendor A level
to compete with vendor B's level for a specific category.
"""

import json
from typing import Any

from pydantic import BaseModel, Field


class LevelEvaluation(BaseModel):
    """Brief evaluation of a candidate level."""
    level: str = Field(..., description="Level identifier (e.g., 'S4', 'P5')")
    reason_not_selected: str = Field(..., description="Concrete explanation why this candidate was not selected, with specific coverage values for key prestations comparing: (1) this level vs recommended level, and (2) this level vs vendor B level. Example: 'S3 covers optique at 150€ vs S4's 200€ and vendor B's 180€, making S3 too weak and S4 closer to vendor B.'")


class CategoryRecommendation(BaseModel):
    """Recommendation for best vendor A level to compete with vendor B level in a category."""

    category_name: str = Field(..., description="Category name")

    # Stage 1: Initial screening
    eliminated_levels: list[str] = Field(..., description="Vendor A levels eliminated in initial screening because they are clearly too weak or excessive compared to vendor B level")
    shortlisted_levels: list[str] = Field(..., description="Vendor A levels shortlisted as reasonable potential matches (typically 2-4 levels)")

    # Stage 2-3: Candidate analysis & best match selection
    recommended_vendor_a_ref_level: str = Field(..., description="Recommended vendor A level - the best match (e.g., 'S4', 'P5')")
    other_candidates: list[LevelEvaluation] = Field(..., description="Other shortlisted candidates with brief explanation why they weren't selected")

    # Stage 4: Deep analysis of best match
    equivalent_coverage_examples: list[str] = Field(..., description="Max 3 examples of objectively equivalent coverage between recommended vendor A level and vendor B. Pick the most important ones from the customer's perspective.")

    vendor_a_ref_wins: list[str] = Field(..., description="Max 3 impactful wins for vendor A at recommended level vs vendor B. Focus on coverage gaps that matter in practice.")
    selling_arguments: list[str] = Field(..., description="Arguments emphasizing the value of vendor A wins. Use world knowledge to assess real-world impact (e.g., average costs, frequency of use).")

    vendor_b_wins: list[str] = Field(..., description="Max 3 impactful wins for vendor B vs recommended vendor A level. Be honest about where vendor B is better.")
    counter_arguments: list[str] = Field(..., description="Arguments explaining why vendor B wins are not that important. Use world knowledge (e.g., unrealistic coverage limits, rare use cases).")

    # Summary
    section_title: str = Field(..., description="Brief, newspaper-style title without category name (e.g., 'S4 leads on key prestations' or 'P5 offers best value balance'). Max 8 words. The category name will be prepended automatically in the report.")
    summary_paragraph: str = Field(..., description="50 words max paragraph summarizing the recommendation, rationale, and key examples. Should convince a commercial that this is the best option to propose.")


def create_category_recommendation_prompt(
    comparison_document: dict[str, Any],
    vendor_a_ref_name: str,
    vendor_b_name: str,
    language: str = "French (France)",
) -> str:
    """Create category recommendation prompt.

    Args:
        comparison_document: Multi-level comparison document with all vendor A levels vs single vendor B level
        vendor_a_ref_name: Vendor A reference name (e.g., 'ProBTP')
        vendor_b_name: Vendor B name (e.g., 'AXA')
        language: Output language

    Returns:
        Recommendation prompt
    """
    category_name = comparison_document.get("category_name", "Unknown")
    vendor_b_level = comparison_document.get("vendor_b_policy_level", "Unknown")
    vendor_a_ref_levels = comparison_document.get("vendor_a_ref_policy_levels", [])

    # Format comparison document for LLM
    comparison_json = json.dumps(comparison_document, ensure_ascii=False, indent=2)

    prompt = f"""You are an expert insurance analyst. Your goal is to recommend which {vendor_a_ref_name} level best competes with {vendor_b_name}'s "{vendor_b_level}" level for the {category_name} category.

**Context**: A {vendor_a_ref_name} commercial wants to propose the best {vendor_a_ref_name} level to compete with {vendor_b_name}. You must identify the level that appears globally equivalent or slightly better, even if {vendor_a_ref_name} doesn't win everywhere.

**Evaluation Process**:
1. **Initial screening**: Eliminate {vendor_a_ref_name} levels that are clearly too weak or excessive compared to {vendor_b_name} "{vendor_b_level}"
2. **Shortlist candidates**: Identify 2-4 reasonable potential matches
3. **Deep candidate analysis**: Compare shortlisted levels to determine the best match
   - For each rejected candidate, provide specific coverage values for key prestations showing why it's inferior to the recommended level
   - Compare each rejected candidate to both the recommended level AND {vendor_b_name} level
4. **Final recommendation**: Select the level that is globally equivalent or slightly better

**Key Principles**:
- **Use world knowledge**: Assess real-world value of coverage differences (e.g., if {vendor_b_name} covers up to 900€ but average cost is 250€, and {vendor_a_ref_name} covers 300€, the gap is insignificant)
- **Consider frequency**: A win on frequently-used prestations outweighs a loss on rarely-used ones
- **Be balanced**: Acknowledge {vendor_b_name}'s wins but explain why they matter less
- **Ground in data**: Use concrete coverage values in all comparisons
- **IMPORTANT**: Higher {vendor_a_ref_name} levels than the recommended one likely exist. Avoid absolute claims like "unbeatable" or "maximum coverage". Frame the recommendation as the best **value proposition** to compete with {vendor_b_name}'s level - higher levels may exist but offer diminishing returns.

**Comparison Document**:
{comparison_json}
a
**Output Language**: {language}. Use factual language for factual statements, persuasive language for selling arguments.

**Task**: Follow the 4-stage evaluation process to recommend the {vendor_a_ref_name} level that best competes with {vendor_b_name}'s "{vendor_b_level}" level. Provide concrete evidence, selling arguments, and a compelling summary.
Format the output as a JSON object conforming to CategoryRecommendation schema."""

    return prompt
