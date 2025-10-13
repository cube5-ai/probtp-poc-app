"""Global recommendation prompt for policy recommendation pipeline.

This prompt takes all category recommendations and selects the overall best vendor A level
combination (one S level + one P level) to compete with vendor B.
"""

import json
from typing import Any

from pydantic import BaseModel, Field


class CategoryJustification(BaseModel):
    """Per-category justification for level selection."""
    category_name: str = Field(..., description="Category name")
    justification: str = Field(..., description="1-2 sentences explaining why the recommended level for this category is part of the global choice")


class GlobalRecommendation(BaseModel):
    """Global recommendation for best vendor A level combination to compete with vendor B."""

    recommended_s_level: str = Field(..., description="Recommended S level (e.g., 'S4')")
    recommended_p_level: str = Field(..., description="Recommended P level (e.g., 'P5')")

    # Justification
    overall_justification: str = Field(..., description="200-400 words explaining why this S+P combination is the best choice to compete with vendor B. Include general presentation of selected levels and overall competitive rationale.")

    category_justifications: list[CategoryJustification] = Field(..., description="Per-category justification for level selection")

    key_competitive_advantages: list[str] = Field(..., description="Top competitive advantages of the recommended combination across all categories")

    acknowledged_gaps: list[str] = Field(..., description="List of areas where vendor A is behind vendor B, with explanation of why this is acceptable or not critical")

    # For commercial use
    target_customer_profile: str = Field(..., description="Description of the ideal customer profile for this recommendation")
    key_talking_points: list[str] = Field(..., description="Key selling points the commercial should emphasize when presenting this offer")


def create_global_recommendation_prompt(
    category_recommendations: list[dict[str, Any]],
    vendor_a_ref_name: str,
    vendor_b_name: str,
    vendor_b_level: str,
    language: str = "French (France)",
) -> str:
    """Create global recommendation prompt.

    Args:
        category_recommendations: List of category recommendations
        vendor_a_ref_name: Vendor A reference name (e.g., 'ProBTP')
        vendor_b_name: Vendor B name (e.g., 'AXA')
        vendor_b_level: Vendor B policy level being compared against (e.g., 'Base obligatoire')
        language: Output language

    Returns:
        Global recommendation prompt
    """
    # Separate recommendations by type (S vs P)
    s_recommendations = []
    p_recommendations = []

    for rec in category_recommendations:
        category_name = rec.get("category_name", "Unknown")
        recommended_level = rec.get("recommended_vendor_a_ref_level", "Unknown")

        if recommended_level.startswith("S"):
            s_recommendations.append({
                "category": category_name,
                "level": recommended_level,
                "summary": rec.get("summary_paragraph", ""),
                "section_title": rec.get("section_title", ""),
            })
        elif recommended_level.startswith("P"):
            p_recommendations.append({
                "category": category_name,
                "level": recommended_level,
                "summary": rec.get("summary_paragraph", ""),
                "section_title": rec.get("section_title", ""),
            })

    # Format recommendations
    recommendations_json = json.dumps(category_recommendations, ensure_ascii=False, indent=2)

    prompt = f"""You are an expert insurance strategist. Your goal is to select the overall best {vendor_a_ref_name} level combination (one S level + one P level) to compete with {vendor_b_name}'s "{vendor_b_level}" level.

**Context**: {vendor_a_ref_name} policies are defined by one S level (covering Soins categories like Hospitalisation, Soins Courants) and one P level (covering Prévoyance categories like Optique, Dentaire, Audiologie, Prestations Complémentaires).

**S-level recommendations** (from Soins categories):
{json.dumps(s_recommendations, ensure_ascii=False, indent=2)}

**P-level recommendations** (from Prévoyance categories):
{json.dumps(p_recommendations, ensure_ascii=False, indent=2)}

**All category recommendations**:
{recommendations_json}

**Task**:
1. Select ONE S level that best represents the recommendations from Soins categories
2. Select ONE P level that best represents the recommendations from Prévoyance categories
3. Justify why this S+P combination is the best global offer to compete with {vendor_b_name}'s "{vendor_b_level}"

**Key Principles**:
- Find the level that appears most frequently in recommendations within each group (S or P)
- If there's a tie, prefer the higher level (more coverage)
- Consider the overall competitive story: can you present this combination as globally equivalent or better?
- Think about the target customer: who would benefit most from this combination?
- Provide compelling justification that a {vendor_a_ref_name} commercial can use to convince their client

**Output Language**: {language}

**Format**: Return a structured recommendation with S+P levels, justifications, competitive advantages, and selling points."""

    return prompt
