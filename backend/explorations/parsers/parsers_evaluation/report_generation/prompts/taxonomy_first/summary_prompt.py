"""Summary prompt template for taxonomy-first pipeline.

Generates high-level comparison overview across all categories from taxonomy-first analyses.
"""

from pydantic import BaseModel, Field


class CategoryStrengths(BaseModel):
    """Key strengths for a specific category."""
    category: str = Field(..., description="Category name (e.g., 'Soins courants', 'Dentaire')")
    probtp_strengths: list[str] = Field(..., description="2-3 key ProBTP advantages in this category")
    axa_strengths: list[str] = Field(..., description="2-3 key AXA advantages in this category")


class CategoryObjectiveAssessment(BaseModel):
    """Objective winner for a specific category."""
    category: str = Field(..., description="Category name")
    winner: str = Field(..., description="'probtp' or 'axa' - which contract is objectively better")
    confidence: str = Field(..., description="'high', 'medium', or 'low'")
    key_reason: str = Field(..., description="One-sentence explanation of why this contract wins")


class OverallComparison(BaseModel):
    """Overall comparison summary."""
    overall_winner: str = Field(..., description="'probtp', 'axa', or 'mixed' - overall assessment across all categories")
    confidence: str = Field(..., description="'high', 'medium', or 'low'")
    reasoning: str = Field(..., description="2-3 sentence explanation of overall assessment")


class ComparisonSummary(BaseModel):
    """High-level structured summary of the comparison across all categories."""
    key_differences: str = Field(..., description="2-3 paragraphs: High-level strategic differences between ProBTP and AXA")
    category_strengths: list[CategoryStrengths] = Field(..., description="Strengths breakdown by category")
    probtp_overall_strengths: list[str] = Field(..., description="3-5 top ProBTP strengths across all categories")
    axa_overall_strengths: list[str] = Field(..., description="3-5 top AXA strengths across all categories")
    objective_evaluation: OverallComparison = Field(..., description="Brutally honest overall assessment")
    category_winners: list[CategoryObjectiveAssessment] = Field(..., description="Winner assessment for each category")
    selling_points: list[str] = Field(..., description="5-7 key talking points for ProBTP salespeople")
    target_customer_fit: str = Field(..., description="2-3 paragraphs: Which customer segments fit each contract best")


def create_summary_prompt(
    category_analyses: list[dict],
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
              probtp_weaknesses, axa_weaknesses
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

**Best Coverage (ProBTP Sales Perspective):**
{analysis.get('best_coverage', 'N/A')}

**Salesperson Talking Points:**
{chr(10).join(f'- {point}' for point in analysis.get('salesperson_talking_points', []))}

**Objective Assessment:**
- Winner: {obj_assessment.get('overall_winner', 'N/A')}
- Confidence: {obj_assessment.get('confidence', 'N/A')}
- Reasoning: {obj_assessment.get('reasoning', 'N/A')}
- ProBTP Weaknesses: {', '.join(obj_assessment.get('probtp_weaknesses', []))}
- AXA Weaknesses: {', '.join(obj_assessment.get('axa_weaknesses', []))}
"""

    prompt = f"""You are an expert insurance analyst specializing in French health insurance. Your task is to generate a high-level structured summary of a multi-category comparison between ProBTP and AXA health insurance contracts.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Generate a concise, high-level comparison summary suitable for display on a web app landing page. This summary should:
1. Provide quick insights into key strategic differences
2. Show category-by-category strength breakdown
3. Give an overall objective evaluation
4. Provide actionable selling points for ProBTP sales team

This is a SUMMARY - be concise and to-the-point. No tables needed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GENERAL TASK DESCRIPTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Summary Components Required:**

1. **Key Differences** (2-3 paragraphs)
   - High-level strategic positioning differences between ProBTP and AXA
   - What is each insurer's philosophy/approach to coverage?
   - What do they each prioritize?

2. **Category Strengths** (structured breakdown)
   - For EACH category analyzed, list:
     - Category name
     - 2-3 key ProBTP strengths in that category
     - 2-3 key AXA strengths in that category
   - Keep these concise (one line each)

3. **Overall Strengths** (cross-category synthesis)
   - 3-5 top ProBTP strengths that emerge across ALL categories
   - 3-5 top AXA strengths that emerge across ALL categories
   - Focus on patterns and themes

4. **Objective Evaluation**
   - Overall winner: 'probtp', 'axa', or 'mixed'
   - Confidence level: 'high', 'medium', or 'low'
   - 2-3 sentence reasoning
   - Category-by-category winner breakdown with one-sentence explanations

5. **Selling Points** (5-7 points)
   - Key talking points for ProBTP salespeople
   - Should work across all categories
   - Actionable and specific

6. **Target Customer Fit** (2-3 paragraphs)
   - Which customer segments are best suited for ProBTP?
   - Which customer segments are best suited for AXA?
   - Consider age, health needs, risk tolerance, budget

**Output Format:**

Return a JSON object conforming to the ComparisonSummary Pydantic schema.

Example structure:

{{
  "key_differences": "ProBTP adopts a comprehensive coverage philosophy with emphasis on routine care and preventive services, offering higher baseline reimbursement rates across most categories. AXA takes a more selective approach, concentrating superior coverage on high-cost specialized care like dental work and optics, while maintaining competitive but lower rates for everyday medical expenses.\\n\\nThe fundamental difference lies in risk management strategy: ProBTP reduces out-of-pocket costs for frequent, predictable expenses, while AXA provides stronger protection against major one-time costs. This reflects different value propositions for different customer profiles.",
  "category_strengths": [
    {{
      "category": "Soins courants",
      "probtp_strengths": [
        "Higher reimbursement rates for GP and specialist consultations (100% vs 90% BR)",
        "No caps on routine care visits"
      ],
      "axa_strengths": [
        "Lower premium costs for basic coverage level",
        "Preventive care bonus program"
      ]
    }},
    {{
      "category": "Dentaire",
      "probtp_strengths": [
        "Better coverage for routine dental checkups and cleanings"
      ],
      "axa_strengths": [
        "Higher orthodontics cap (€2000 vs €1500)",
        "Better coverage for dental prosthetics (crowns, bridges)"
      ]
    }}
  ],
  "probtp_overall_strengths": [
    "Consistently higher reimbursement rates for routine medical care across all categories",
    "Better cumulative value for customers with frequent healthcare needs",
    "Simpler coverage structure with fewer restrictions and conditions",
    "Superior coverage for preventive care and early detection",
    "Lower out-of-pocket costs for everyday health expenses"
  ],
  "axa_overall_strengths": [
    "Superior coverage for high-cost specialized treatments (orthodontics, optics)",
    "Better value for customers with infrequent but expensive healthcare needs",
    "More competitive pricing at entry-level tiers",
    "Stronger network benefits for specialists",
    "Innovation bonuses and wellness programs"
  ],
  "objective_evaluation": {{
    "overall_winner": "mixed",
    "confidence": "high",
    "reasoning": "Neither contract is universally superior. ProBTP wins decisively for customers with frequent routine healthcare needs, while AXA is objectively better for those prioritizing protection against major specialized care costs. The optimal choice depends heavily on customer profile and healthcare usage patterns."
  }},
  "category_winners": [
    {{
      "category": "Soins courants",
      "winner": "probtp",
      "confidence": "high",
      "key_reason": "Consistently higher reimbursement rates result in lower cumulative out-of-pocket costs"
    }},
    {{
      "category": "Dentaire",
      "winner": "axa",
      "confidence": "medium",
      "key_reason": "Superior coverage for high-cost orthodontics and prosthetics outweighs ProBTP's routine care advantage"
    }}
  ],
  "selling_points": [
    "ProBTP delivers better everyday value: lower out-of-pocket costs for the medical care you actually use regularly",
    "Cumulative savings advantage: ProBTP's higher routine care rates save customers €200-400 per year on average",
    "Simpler, more predictable coverage: fewer caps and conditions mean fewer surprises at reimbursement",
    "Better for families and those with chronic conditions requiring frequent care",
    "Strong value proposition for preventive care encourages early detection and better health outcomes",
    "When comparing total cost of ownership (premiums + out-of-pocket), ProBTP wins for typical usage patterns",
    "AXA's advantages are concentrated in infrequent, specialized care - ProBTP protects your daily health budget"
  ],
  "target_customer_fit": "ProBTP is ideally suited for customers with regular healthcare needs: families with children, individuals with chronic conditions requiring ongoing treatment, older adults with frequent GP and specialist visits, and health-conscious individuals who prioritize preventive care. The higher routine care reimbursement rates translate directly into hundreds of euros in annual savings for these segments.\\n\\nAXA is better positioned for younger, healthier individuals with infrequent healthcare usage who want strong protection against major one-time costs like orthodontics or complex dental work. AXA also appeals to budget-conscious customers at entry-level tiers and those who value wellness program incentives over baseline coverage rates."
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**DUAL PERSPECTIVE REQUIREMENT:**

This summary serves TWO distinct purposes:

**Part 1: Sales-Ready Content**
- Key differences should be factual but framed positively for ProBTP
- Selling points are specifically for ProBTP sales team
- Best coverage framing focuses on ProBTP value proposition
- Target customer fit should help salespeople qualify leads

**Part 2: Objective Evaluation**
- Be brutally honest about overall and category winners
- Do NOT sugarcoat or spin to favor ProBTP
- "mixed" is a valid and often correct answer for overall_winner
- Acknowledge where AXA is objectively superior
- Confidence should reflect actual certainty

**Synthesis Methodology:**

1. **Read all category analyses** provided below
2. **Identify cross-category patterns:**
   - Where does ProBTP consistently win?
   - Where does AXA consistently win?
   - What strategic differences explain these patterns?
3. **Synthesize key differences** at a high level (not category-specific details)
4. **Extract category strengths** from each analysis (2-3 per side per category)
5. **Determine overall strengths** by finding themes across categories
6. **Make objective evaluation:**
   - Count category wins for each side
   - Assess strength of wins (high confidence wins count more)
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
- Objective evaluation: honest even if ProBTP loses overall
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
5. Provide actionable selling points for ProBTP sales team
6. Define target customer segments for each contract

Output all content in {language}. Output ONLY the JSON conforming to ComparisonSummary schema.

Generate the JSON summary now:"""

    return prompt
