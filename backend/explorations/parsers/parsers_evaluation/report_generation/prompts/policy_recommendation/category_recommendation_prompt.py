"""Category recommendation prompt for policy recommendation pipeline.

This prompt analyzes a multi-level comparison document and recommends the best vendor A level
to compete with vendor B's level for a specific category.
"""

import json
from typing import Any

from pydantic import BaseModel, Field


class CategoryRecommendation(BaseModel):
    """Recommendation for best vendor A level to compete with vendor B level in a category."""

    category_name: str = Field(..., description="Category name")
    recommended_vendor_a_ref_level: str = Field(..., description="Recommended vendor A level (e.g., 'S4', 'P5')")

    # Evidence
    equivalent_coverage_examples: list[str] = Field(..., description="Max 3 examples of objectively equivalent coverage between recommended vendor A level and vendor B. Pick the most important ones from the customer's perspective.")
    vendor_a_ref_wins: list[str] = Field(..., description="Max 3 impactful wins for vendor A at recommended level vs vendor B. Focus on coverage gaps that matter in practice.")
    vendor_b_wins: list[str] = Field(..., description="Max 3 impactful wins for vendor B vs recommended vendor A level. Be honest about where vendor B is better.")

    # Selling arguments
    selling_arguments: list[str] = Field(..., description="Arguments emphasizing the value of vendor A wins. Use world knowledge to assess real-world impact (e.g., average costs, frequency of use).")
    counter_arguments: list[str] = Field(..., description="Arguments explaining why vendor B wins are not that important. Use world knowledge (e.g., unrealistic coverage limits, rare use cases).")

    # Summary
    section_title: str = Field(..., description="Informative section title (e.g., 'S4 recommended: better on 3 out of 4 key prestations')")
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

    vendor_a_levels_str = ", ".join(vendor_a_ref_levels) if vendor_a_ref_levels else "multiple levels"

    prompt = f"""You are an expert insurance analyst. Your goal is to recommend which {vendor_a_ref_name} level best competes with {vendor_b_name}'s "{vendor_b_level}" level for the {category_name} category.

**Context**: A {vendor_a_ref_name} commercial wants to propose the best {vendor_a_ref_name} level to compete with {vendor_b_name}. You must identify the level that appears globally equivalent or slightly better, even if {vendor_a_ref_name} doesn't win everywhere.

**Key Principles**:
1. **Find the best match**: Identify the {vendor_a_ref_name} level that is globally equivalent or better than {vendor_b_name}
2. **Use world knowledge**: Assess real-world value of differences
   - Example: If {vendor_b_name} covers up to 900€ but average cost is 250€, and {vendor_a_ref_name} covers 300€, the gap is less important
   - Example: If {vendor_a_ref_name} is better on Prestation A (used frequently) but worse on Prestation B (rare), emphasize frequency
3. **Be balanced**: Acknowledge {vendor_b_name}'s wins but explain why they matter less
4. **Focus on customer value**: Pick examples the decision-maker would care about most

**Comparison Document**:
{comparison_json}

**Output Language**: {language}

**Task**: Analyze the comparison and recommend the {vendor_a_ref_name} level that best competes with {vendor_b_name}'s "{vendor_b_level}" level. Provide evidence, selling arguments, and a compelling summary for the commercial."""

    return prompt
