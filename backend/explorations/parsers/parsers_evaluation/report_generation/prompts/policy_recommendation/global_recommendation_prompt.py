"""Global recommendation prompt for policy recommendation pipeline.

This prompt takes all category recommendations and selects the overall best vendor A level
combination (one S level  &  one P level) to compete with vendor B.
"""

import json
from typing import Any

from pydantic import BaseModel, Field

# Import text formatter utility
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.recommendation_text_formatter import format_category_recommendations_to_text


class GlobalRecommendation(BaseModel):
    """Global recommendation for best vendor A level combination to compete with vendor B."""

    # Candidate levels identified
    s_level_candidates: list[str] = Field(..., description="S levels that appear in category recommendations (e.g., ['S3', 'S4', 'S5'])")
    p_level_candidates: list[str] = Field(..., description="P levels that appear in category recommendations (e.g., ['P4', 'P5', 'P6'])")

    # Recommended combination
    recommended_s_level: str = Field(..., description="Recommended S level (e.g., 'S4')")
    recommended_p_level: str = Field(..., description="Recommended P level (e.g., 'P5')")

    # Deep analysis
    alternatives_rejected_rationale: str = Field(..., description="150-250 words explaining why 2-3 alternative S & P combinations were considered but ultimately rejected. For each alternative, provide concrete coverage comparisons showing: (1) how it compares to the recommended combination, (2) how it compares to vendor B, (3) why it's inferior (e.g., overkill with marginal gains, too weak in key categories, poor overall balance). Must be grounded in specific coverage values across multiple categories.")

    overall_justification: str = Field(..., description="200-400 words explaining why this S & P combination offers the best overall competitive package vs vendor B. Must: (1) explain how this combination is globally equivalent or better, (2) show how losses in some categories are compensated by wins in others, (3) include concrete coverage values across multiple categories, (4) present a compelling competitive story.")

    key_competitive_advantages: list[str] = Field(..., description="Most impactful wins of the recommended combination across all categories. Must be coverage value grounded.")

    acknowledged_gaps: list[str] = Field(..., description="List of specific prestations, that could be generally perceived as important by the client, where vendor A is behind vendor B, with explanation of why this is acceptable or not critical. Downplay the differences with arguments. Must be coverage value grounded.")

    # For commercial use
    key_selling_arguments_points: list[str] = Field(..., description="Key selling points the commercial should emphasize to highlight the advantages of the recommended combination over the competitor's level. Must be coverage value grounded.")


def create_global_recommendation_prompt(
    category_recommendations: list[dict[str, Any]],
    comparison_documents: dict[str, dict[str, Any]],
    vendor_a_ref_name: str,
    vendor_b_name: str,
    vendor_b_level: str,
    language: str = "French (France)",
) -> str:
    """Create global recommendation prompt.

    Args:
        category_recommendations: List of category recommendations with pre-generated coverage tables
        comparison_documents: Category ID -> comparison document mapping (unused, kept for compatibility)
        vendor_a_ref_name: Vendor A reference name (e.g., 'ProBTP')
        vendor_b_name: Vendor B name (e.g., 'AXA')
        vendor_b_level: Vendor B policy level being compared against (e.g., 'Base obligatoire')
        language: Output language

    Returns:
        Global recommendation prompt
    """
    # Format category recommendations as readable text WITH their attached coverage tables
    recommendations_with_tables = format_category_recommendations_to_text(
        category_recommendations,
        include_tables=True,  # Keep tables attached to their category!
    )

    prompt = f"""You are an expert insurance analyst and strategist, hired to advise a {vendor_a_ref_name} commercial.
Your goal is to select the overall best {vendor_a_ref_name} level combination (one S level & one P level) that competes with {vendor_b_name}'s "{vendor_b_level}" level as a complete package.

**Context**: {vendor_a_ref_name} policies are defined by one S level (covering categories like Hospitalisation, Soins Courants) and one P level (covering categories like Optique, Dentaire, Audiologie, Prestations Complémentaires).

**Critical insight**: The goal is to find the best **overall package**, not to win every category. A lower level in one category can be acceptable if compensated by wins elsewhere, as long as the total package is globally equivalent or better than {vendor_b_name}.

**Category-Level Recommendations & Analysis**:

Each category below includes:
- The recommended level and rationale
- Analysis of other candidates considered
- Coverage comparison table (shortlisted levels + one level above vs {vendor_b_name})

Use the coverage tables to:
- Verify claims made in category recommendations
- Identify if a level marked as "not shortlisted" or "excessive" might actually be valuable for the global package
- Reassess category-level decisions in light of the global optimization goal
- Ground all arguments in actual coverage values

{recommendations_with_tables}

**Evaluation Process**:
1. **Identify all plausible S & P combinations** from category recommendations (e.g., if categories recommend S3, S4 for S-categories and P4, P5 for P-categories, consider S3 & P4, S3 & P5, S4 & P4, S4 & P5)

2. **For each combination, assess global competitiveness**:
   - Where does this combo win vs {vendor_b_name}?
   - Where does it lose?
   - What's the overall balance across ALL categories?
   - Can you tell a compelling story that this package is globally equivalent or better?

3. **Select the combination with the best overall competitive story**:
   - Not necessarily the highest levels from each category
   - Could be a balanced combination where losses in some categories are compensated by wins in others
   - Must be defensible as globally competitive

4. **Document alternatives analysis** (150-250 words):
   - Identify 2-3 alternative S & P combinations that were seriously considered
   - For each alternative, explain with concrete coverage values why it was rejected
   - Compare each alternative to both your recommended combination AND {vendor_b_name}
   - Be specific: e.g., "S5 & P6: Optique 250€ vs recommended S4 & P5's 200€ vs {vendor_b_name}'s 180€ - marginal 50€ gain doesn't justify the cost increase"

5. **Justify your recommendation** (200-400 words):
   - Explain why your recommended combination offers the best overall competitive position
   - Show with concrete coverage values how losses in specific categories are compensated by wins elsewhere
   - Demonstrate that the total package is globally equivalent or better than {vendor_b_name}
   - Present a compelling competitive story

**Key Principles**:
- You're advising a {vendor_a_ref_name} commercial. Be objective on facts, convincing in arguments.
- Focus on the **overall package competitiveness**, not individual category optimization
- A loss in one category is acceptable if compensated elsewhere
- Ground all arguments in concrete coverage values across multiple categories
- The combination should tell a compelling competitive story
- **IMPORTANT**: {vendor_a_ref_name} has higher levels than those recommended (e.g., if recommending S4, levels S5/S6 exist). Avoid absolute claims like "unbeatable", "best-in-class", "exceptional" or "maximum coverage". Instead, frame the recommendation as the best **value proposition** or **optimal balance** to compete with {vendor_b_name}'s specific level. Higher levels exist but offer marginal gains at higher cost.

**Output Language**: {language}. Use factual language for factual statements, persuasive language for selling arguments.

**Task**: Follow the 5-stage evaluation process to recommend the best {vendor_a_ref_name} S & P combination. Provide:
1. A detailed alternatives analysis explaining why 2-3 other combinations were rejected (with concrete coverage comparisons)
2. A comprehensive justification for your recommendation showing how it balances coverage across all categories
3. A list impactful wins that could be perceived as critical by the client of the recommended combination across all categories
4. A list of gaps that could be perceived as critical by the client of the recommended combination across all categories
5. A list of key selling arguments globaly and for prestations that could be perceived as critical by the client of the recommended combination across all categories
Format the output as a JSON object conforming to GlobalRecommendation schema."""

    return prompt
