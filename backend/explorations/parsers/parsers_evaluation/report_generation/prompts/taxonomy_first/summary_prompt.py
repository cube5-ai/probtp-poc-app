"""Summary prompt template for taxonomy-first pipeline.

Generates high-level comparison overview across all categories from taxonomy-first analyses.
"""

from pydantic import BaseModel, Field


class CategoryStrengths(BaseModel):
    """Key strengths for a specific category."""
    category: str = Field(..., description="Category name (e.g., 'Soins courants', 'Dentaire')")
    vendor_a_ref_strengths: list[str] = Field(..., description="2-3 key vendor_a_ref_name advantages in this category. Keep each short and concise (one line each).")
    vendor_b_strengths: list[str] = Field(..., description="2-3 key vendor_b_name advantages in this category. Keep each short and concise (one line each).")


class CategoryObjectiveAssessment(BaseModel):
    """Objective winner for a specific category."""
    category: str = Field(..., description="Category name")
    winner: str = Field(..., description="'vendor_a_ref' or 'vendor_b' - which contract is objectively better")
    confidence: str = Field(..., description="How much better is the winner in this category? 'high', 'medium', or 'low'")
    key_reason: str = Field(..., description="One-sentence explanation of why this contract wins")


class OverallComparison(BaseModel):
    """Overall comparison summary."""
    overall_winner: str = Field(..., description="'vendor_a_ref', 'vendor_b', or 'mixed' - overall assessment across all categories")
    confidence: str = Field(..., description="How much better is the winner overall? 'high', 'medium', or 'low'")
    reasoning: str = Field(..., description="2-3 sentence explanation of overall assessment")


class ComparisonSummary(BaseModel):
    """High-level structured summary of the comparison across all categories."""
    key_differences: str = Field(..., description="2-3 paragraphs: High-level strategic differences between vendor_a_ref_name and vendor_b_name")
    category_strengths: list[CategoryStrengths] = Field(..., description="Strengths breakdown by category")
    vendor_a_ref_overall_strengths: list[str] = Field(..., description="3-4 top vendor_a_ref_name strengths across all categories")
    vendor_b_overall_strengths: list[str] = Field(..., description="3-4 top vendor_b_name strengths across all categories")
    objective_evaluation: OverallComparison = Field(..., description="Brutally honest overall assessment")
    category_winners: list[CategoryObjectiveAssessment] = Field(..., description="Winner assessment for each category")
    selling_points: list[str] = Field(..., description="4-6 key talking points for vendor_a_ref_name salespeople")


def create_summary_prompt(
    category_analyses: list[dict],
    vendor_a_ref_name: str,
    vendor_b_name: str,
    language: str = "French (France)"
) -> str:
    """
    Create a prompt for generating a high-level comparison summary.

    Args:
        category_analyses: List of TaxonomyFirstAnalysisOutput dicts (subset of fields):
            Each dict should contain:
            - category: str
            - key_differences: str
            - critical_thinking: str
            - best_coverage: str
            - salesperson_talking_points: list[str]
            - objective_assessment: dict with overall_winner, confidence, reasoning,
              vendor_a_ref_weaknesses, vendor_b_weaknesses
        vendor_a_ref_name: Name of vendor A (reference vendor, e.g., "ProBTP")
        vendor_b_name: Name of vendor B (competitor vendor, e.g., "Generali")
        language: Language for the output (default: "French (France)")

    Returns:
        Formatted prompt string
    """
    # Format category analyses
    analyses_text = ""
    for i, analysis in enumerate(category_analyses, 1):
        obj_assessment = analysis.get("objective_assessment", {})
        analyses_text += f"""
━━━ Category {i}: {analysis.get('category', 'Unknown')} ━━━

**Key Differences:**
{analysis.get('key_differences', 'N/A')}

**Critical Thinking:**
{analysis.get('critical_thinking', 'N/A')}

**Best Coverage ({vendor_a_ref_name} Sales Perspective):**
{analysis.get('best_coverage', 'N/A')}

**Salesperson Talking Points:**
{chr(10).join(f'- {point}' for point in analysis.get('salesperson_talking_points', []))}

**Objective Assessment:**
- Winner: {obj_assessment.get('overall_winner', 'N/A')}
- Confidence: {obj_assessment.get('confidence', 'N/A')}
- Reasoning: {obj_assessment.get('reasoning', 'N/A')}
- {vendor_a_ref_name} Weaknesses: {', '.join(obj_assessment.get('vendor_a_ref_weaknesses', []))}
- {vendor_b_name} Weaknesses: {', '.join(obj_assessment.get('vendor_b_weaknesses', []))}
"""

    prompt = f"""You are an expert insurance analyst specializing in French health insurance. Your task is to generate a high-level structured summary of a multi-category comparison between {vendor_a_ref_name} and {vendor_b_name} health insurance contracts.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Generate a concise, high-level comparison summary suitable for display on a web app landing page. This summary should:
1. Provide quick insights into key strategic differences
2. Show category-by-category strength breakdown
3. Give an overall objective evaluation
4. Provide actionable selling points for {vendor_a_ref_name} sales team

This is a SUMMARY - be concise and to-the-point. No tables needed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GENERAL TASK DESCRIPTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Summary Components Required:**

1. **Key Differences** (2-3 paragraphs)
   - High-level strategic positioning differences between {vendor_a_ref_name} and {vendor_b_name}
   - What is each insurer's philosophy/approach to coverage?
   - What do they each prioritize?

2. **Category Strengths** (structured breakdown)
   - For EACH category analyzed, list:
     - Category name
     - 2-3 key {vendor_a_ref_name} strengths in that category
     - 2-3 key {vendor_b_name} strengths in that category
   - Keep these concise (one line each)

3. **Overall Strengths** (cross-category synthesis)
   - 3-5 top {vendor_a_ref_name} strengths that emerge across ALL categories
   - 3-5 top {vendor_b_name} strengths that emerge across ALL categories
   - Focus on patterns and themes

4. **Objective Evaluation**
   - Overall winner: 'vendor_a_ref', 'vendor_b', or 'mixed'
   - Confidence level: 'high', 'medium', or 'low'
   - 2-3 sentence reasoning
   - Category-by-category winner breakdown with one-sentence explanations

5. **Selling Points** (5-7 points)
   - Key talking points for {vendor_a_ref_name} salespeople
   - Should work across all categories
   - Actionable and specific

6. **Target Customer Fit** (2-3 paragraphs)
   - Which customer segments are best suited for {vendor_a_ref_name}?
   - Which customer segments are best suited for {vendor_b_name}?
   - Consider age, health needs, risk tolerance, budget

**Output Format:**

Return a JSON object conforming to the ComparisonSummary Pydantic schema.

Example structure:

{{
  "key_differences": "{vendor_a_ref_name} adopts a comprehensive coverage philosophy with emphasis on routine care and preventive services, offering higher baseline reimbursement rates across most categories. {vendor_b_name} takes a more selective approach, concentrating superior coverage on high-cost specialized care like dental work and optics, while maintaining competitive but lower rates for everyday medical expenses.\\n\\nThe fundamental difference lies in risk management strategy: {vendor_a_ref_name} reduces out-of-pocket costs for frequent, predictable expenses, while {vendor_b_name} provides stronger protection against major one-time costs. This reflects different value propositions for different customer profiles.",
  "category_strengths": [
    {{
      "category": "Soins courants",
      "vendor_a_ref_strengths": [
        "Higher reimbursement rates for GP and specialist consultations (100% vs 90% BR)",
        "No caps on routine care visits"
      ],
      "vendor_b_strengths": [
        "Lower premium costs for basic coverage level",
        "Preventive care bonus program"
      ]
    }},
    {{
      "category": "Dentaire",
      "vendor_a_ref_strengths": [
        "Better coverage for routine dental checkups and cleanings"
      ],
      "vendor_b_strengths": [
        "Higher orthodontics cap (€2000 vs €1500)",
        "Better coverage for dental prosthetics (crowns, bridges)"
      ]
    }}
  ],
  "vendor_a_ref_overall_strengths": [
    "Consistently higher reimbursement rates for routine medical care across all categories",
    "Better cumulative value for customers with frequent healthcare needs",
    "Simpler coverage structure with fewer restrictions and conditions",
    "Superior coverage for preventive care and early detection",
    "Lower out-of-pocket costs for everyday health expenses"
  ],
  "vendor_b_overall_strengths": [
    "Superior coverage for high-cost specialized treatments (orthodontics, optics)",
    "Better value for customers with infrequent but expensive healthcare needs",
    "More competitive pricing at entry-level tiers",
    "Stronger network benefits for specialists",
    "Innovation bonuses and wellness programs"
  ],
  "objective_evaluation": {{
    "overall_winner": "mixed",
    "confidence": "high",
    "reasoning": "Neither contract is universally superior. {vendor_a_ref_name} wins decisively for customers with frequent routine healthcare needs, while {vendor_b_name} is objectively better for those prioritizing protection against major specialized care costs. The optimal choice depends heavily on customer profile and healthcare usage patterns."
  }},
  "category_winners": [
    {{
      "category": "Soins courants",
      "winner": "vendor_a_ref",
      "confidence": "high",
      "key_reason": "Consistently higher reimbursement rates result in lower cumulative out-of-pocket costs"
    }},
    {{
      "category": "Dentaire",
      "winner": "vendor_b",
      "confidence": "medium",
      "key_reason": "Superior coverage for high-cost orthodontics and prosthetics outweighs {vendor_a_ref_name}'s routine care advantage"
    }}
  ],
  "selling_points": [
    "{vendor_a_ref_name} delivers better everyday value: lower out-of-pocket costs for the medical care you actually use regularly",
    "Cumulative savings advantage: {vendor_a_ref_name}'s higher routine care rates save customers €200-400 per year on average",
    "Simpler, more predictable coverage: fewer caps and conditions mean fewer surprises at reimbursement",
    "Better for families and those with chronic conditions requiring frequent care",
    "Strong value proposition for preventive care encourages early detection and better health outcomes",
    "When comparing total cost of ownership (premiums + out-of-pocket), {vendor_a_ref_name} wins for typical usage patterns",
    "{vendor_b_name}'s advantages are concentrated in infrequent, specialized care - {vendor_a_ref_name} protects your daily health budget"
  ],
  "target_customer_fit": "{vendor_a_ref_name} is ideally suited for customers with regular healthcare needs: families with children, individuals with chronic conditions requiring ongoing treatment, older adults with frequent GP and specialist visits, and health-conscious individuals who prioritize preventive care. The higher routine care reimbursement rates translate directly into hundreds of euros in annual savings for these segments.\\n\\n{vendor_b_name} is better positioned for younger, healthier individuals with infrequent healthcare usage who want strong protection against major one-time costs like orthodontics or complex dental work. {vendor_b_name} also appeals to budget-conscious customers at entry-level tiers and those who value wellness program incentives over baseline coverage rates."
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**DUAL PERSPECTIVE REQUIREMENT:**

This summary serves TWO distinct purposes:

**Part 1: Sales-Ready Content**
- Key differences should be factual but framed positively for {vendor_a_ref_name}
- Selling points are specifically for {vendor_a_ref_name} sales team
- Best coverage framing focuses on {vendor_a_ref_name} value proposition
- Target customer fit should help salespeople qualify leads

**Part 2: Objective Evaluation**
- Be brutally honest about overall and category winners
- Do NOT sugarcoat or spin to favor {vendor_a_ref_name}
- "mixed" is a valid and often correct answer for overall_winner
- Acknowledge where {vendor_b_name} is objectively superior
- Confidence should reflect how clear-cut the winner is, based on the difference intensity between the winner and the loser as a beneficiary would perceive it.

**Synthesis Methodology:**

1. **Read all category analyses** provided below
2. **Identify cross-category patterns:**
   - Where does {vendor_a_ref_name} consistently win?
   - Where does {vendor_b_name} consistently win?
   - What strategic differences explain these patterns?
3. **Synthesize key differences** at a high level (not category-specific details)
4. **Extract category strengths** from each analysis (2-3 per side per category)
5. **Determine overall strengths** by finding themes across categories
6. **Make objective evaluation:**
   - Count category wins for each side
   - Assess strength of wins (high gap intensity wins count more)
   - Consider customer base composition (most people need routine care frequently)
   - Determine if there's a clear overall winner or if it's truly mixed
7. **Craft selling points** that work across categories and address competitive gaps
8. **Define target customer segments** based on which contract serves them better

**Quality Standards:**

- Be concise - this is a summary, not detailed analysis
- Category strengths: one clear line per point
- Overall strengths: 3-5 points max, focused on themes
- Selling points: actionable, specific, address real competitive landscape
- Target customer fit: help salespeople qualify and position
- Objective evaluation: honest even if {vendor_a_ref_name} loses overall
- Use \\n for paragraph breaks in string fields
- Output ONLY the JSON object - no preamble, no commentary

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK PARAMETERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Output Language:** {language}

**Category Analyses:**
{analyses_text}

**Task Recap:**
Based on the category analyses above, generate a high-level comparison summary suitable for a web app landing page. The summary must:
1. Synthesize key strategic differences across all categories
2. Provide category-by-category strength breakdown
3. Give overall strengths for each insurer
4. Make brutally honest objective evaluation (overall + per category)
5. Provide actionable selling points for {vendor_a_ref_name} sales team
6. Define target customer segments for each contract

Output all content in {language}. Output ONLY the JSON conforming to ComparisonSummary schema.

Generate the JSON summary now:"""

    return prompt
