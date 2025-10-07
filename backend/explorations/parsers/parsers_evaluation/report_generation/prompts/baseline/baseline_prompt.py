"""Baseline prompt template for insurance policy comparison report generation."""


def create_baseline_prompt(
    probtp_markdown: str,
    axa_markdown: str,
    probtp_levels: list[str] | None = None,
    axa_levels: list[str] | None = None,
    categories: list[str] | None = None,
    language: str = "French (France)"
) -> str:
    """
    Create a single-shot prompt for generating a complete comparison report.

    Args:
        probtp_markdown: Full markdown of ProBTP contract
        axa_markdown: Full markdown of AXA contract
        probtp_levels: List of ProBTP contract levels (e.g., ['S2', 'P3+'])
        axa_levels: List of AXA contract levels (e.g., ['Option 1', 'Option 2'])
        categories: List of healthcare categories to compare (e.g., ['Dental', 'Vision'])
        language: Language for the report (default: "French (France)")

    Returns:
        Formatted prompt string
    """
    # Default categories if not specified
    if categories is None:
        categories = [
            "Dental Care",
            "Vision/Optical",
            "Hospitalization",
            "Medical Consultations",
            "Pharmacy/Medications",
            "Medical Devices",
            "Prevention/Wellness",
            "Alternative Medicine"
        ]

    categories_str = "\n".join([f"- {cat}" for cat in categories])

    # Format levels if provided
    levels_context = ""
    if probtp_levels or axa_levels:
        levels_context = "\n\n**Contract Levels:**\n"
        if probtp_levels:
            levels_context += f"- ProBTP levels: {', '.join(probtp_levels)}\n"
        if axa_levels:
            levels_context += f"- AXA levels: {', '.join(axa_levels)}\n"

    prompt = f"""You are an expert insurance analyst specializing in French health insurance (mutuelle) contracts. Your task is to generate a comprehensive, sales-ready comparison report between ProBTP and AXA insurance policies.

**CRITICAL: Write the ENTIRE report in {language}. All text, tables, insights, and recommendations must be in {language}.**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCUMENT SOURCE & QUALITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**IMPORTANT: The documents provided below have been processed through an automated PDF parsing pipeline.**

As a result, you may encounter:
- **Formatting inconsistencies:** Tables may have misaligned columns, merged cells, or irregular spacing
- **Layout artifacts:** Headers may be missing, repeated, or incorrectly positioned
- **OCR errors:** Some text may contain character recognition mistakes (e.g., "1OO" instead of "100", "l" instead of "1")
- **Structural issues:** Information may span multiple tables or be split unexpectedly

**Your task is to:**
1. **Interpret the content intelligently** - Use context clues from the full document to infer the correct meaning
2. **Reconstruct logical structure** - If table headers are missing or misplaced, deduce them from surrounding data
3. **Correct obvious errors** - Fix clear OCR mistakes when the intended value is obvious from context
4. **Cross-reference information** - If a benefit appears in multiple places with slight variations, use your judgment to determine the most accurate representation
5. **Focus on semantic meaning** - Prioritize extracting the TRUE coverage information over preserving formatting quirks

When in doubt about a value or benefit, use your expertise in French health insurance to make the most reasonable interpretation given the document context and typical insurance contract structures.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROBTP CONTRACT STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**CRITICAL: Understanding ProBTP's Dual Coverage System**

ProBTP contracts use a **two-tier coverage structure** that combines different levels:

1. **"S" Levels (Soins)** - Apply to:
   - Medical consultations (GP, specialists)
   - Hospitalization (surgeon fees, anesthetist fees, room charges)
   - Pharmacy
   - Medical analyses
   - These are labeled as S1, S2, S3, S3+, S4, etc.

2. **"P" Levels (Prestations)** - Apply to:
   - Dental care (prosthetics, orthodontics, implants)
   - Optical/Vision (glasses, contact lenses, surgery)
   - Audiology (hearing aids)
   - Other specialized benefits
   - These are labeled as P1, P2, P3, P3+, P4, etc.

**How to Compose Coverage Levels:**
- A customer subscribes to **one "S" level AND one "P" level** independently
- Example: "S2 + P3+" means:
  - Hospitalization and consultations are covered at S2 level
  - Dental, optical, and audio are covered at P3+ level
- The document may show these in separate tables or columns
- When comparing, ensure you're matching the correct level category:
  - For hospitalization → use "S" level coverage
  - For dental/optical → use "P" level coverage

**In Your Analysis:**
- Clearly identify which "S" level and which "P" level you're analyzing
- When creating comparison tables, reference the appropriate level (e.g., "ProBTP S2" for hospitalization, "ProBTP P3+" for dental)
- If the user specifies levels, respect the combination (e.g., S2+P3+ means use S2 for medical, P3+ for dental/optical)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL: PROBTP AS REFERENCE DOCUMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**This report is for ProBTP's sales team.** Therefore:

1. **ProBTP is the REFERENCE document** - Use ProBTP's structure, terminology, and organization as the foundation
2. **Each category typically corresponds to ONE table in ProBTP** - Locate and use ProBTP's table structure
3. **Preserve ProBTP terminology** - Use ProBTP's exact benefit names and descriptions in comparison tables
4. **ProBTP-first framing:**
   - When ProBTP has advantages → Highlight them clearly with quantification
   - When AXA has advantages → Contextualize (Is it meaningful? Who benefits? Is it worth the trade-off?)
5. **Sales perspective:**
   - Focus on helping salespeople articulate ProBTP's value proposition
   - Provide talking points that address competitive gaps honestly but frame them appropriately
   - Show when ProBTP saves customers money or provides better protection

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK OVERVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Generate a detailed comparison report to help ProBTP salespeople communicate the value differences between ProBTP and AXA insurance contracts to potential customers.

**Target Audience:** ProBTP sales team and their customers evaluating insurance options

**Goal:** Create clear, actionable comparisons that help salespeople sell ProBTP effectively while being honest about competitive positioning

{levels_context}

**Categories to Compare:**
{categories_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REPORT STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your report MUST include these sections:

## 1. Executive Summary
- 2-3 paragraphs summarizing key findings
- Overall recommendation for different customer profiles (young singles, families, retirees, etc.)
- Top 3 differentiators between the policies

## 2. Category Comparison Tables
For EACH healthcare category, create a comparison table drqwing inspiration from the provided documents adding additional columns to the table if needed to cover the conditions and benefits.

**Table Requirements:**
- **Be EXTREMELY GRANULAR:** Extract ALL individual benefits and sub-categories from the original contract tables
  - Include EVERY specific benefit line item found in the source documents
  - Do NOT consolidate or summarize benefits - show each one separately
  - Example: Instead of "Dental prosthetics", break down into "Crowns", "Bridges", "Dentures", etc.
- **Handle mismatched benefits explicitly:**
  - If a benefit exists in ProBTP but NOT in AXA, still include it in the table
  - Use "Not covered" or "-" in the AXA columns for benefits that don't exist
  - Vice versa: if AXA covers something ProBTP doesn't, show "Not covered" or "-" for ProBTP
  - This makes gaps in coverage immediately visible to salespeople
- Show actual coverage amounts (e.g., "BR + 300%", "€500/year", "Unlimited")
- Include any conditions, limits, or caps in the "Conditions" column
- The "Advantage" column must clearly state which policy is better and quantify if possible (e.g., "ProBTP +50€", "AXA (no cap)")
- If coverage is equivalent, state "Equivalent" in the Advantage column
- If one policy doesn't cover the benefit, clearly state which policy has the advantage (e.g., "ProBTP only", "AXA only")

## 3. Category Insights
After each comparison table, provide:
- **Key Differences:** Plain language explanation of main differences
- **Concrete Examples:** Specific scenarios with euro amounts (e.g., "For orthodontics costing €3000, ProBTP reimburses €X while AXA reimburses €Y")
- **Critical Thinking:** Assess the TRUE value considering:
  - Real-world usage probability (e.g., orthodontics is rare but expensive)
  - Risk vs. benefit (which coverage protects against higher financial risk?)
  - Common customer needs
- **Best Coverage:** Determine which policy offers better value for this category with reasoning

## 4. Overall Recommendation
- **Strengths/Weaknesses Summary:** Bullet points for each policy
- **Customer Profile Recommendations:**
  - Young professionals (20-35)
  - Families with children
  - Middle-aged (40-60)
  - Retirees (60+)
  - Specific health conditions (chronic, dental, vision, etc.)
- **Decision Factors:** What should be the key considerations?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS GUIDELINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ **DO:**
- Extract exact coverage amounts and limits from the documents
- **Create COMPREHENSIVE, GRANULAR tables** - include EVERY benefit line from the source documents
- **Explicitly show coverage gaps** - if one insurer covers something the other doesn't, make it visible in the table
- Use plain, non-technical language for sales context
- Provide concrete euro amounts in examples
- Consider real-world value (not just raw percentages)
- Highlight caps, exclusions, and conditions that affect actual coverage
- Think critically about what matters to different customer profiles
- Use "Base de Remboursement" (BR) terminology where applicable
- Note if a benefit is unlimited vs. capped

✗ **DON'T:**
- Use insurance jargon without explanation
- **Consolidate or summarize benefits** - each benefit line should be its own table row
- **Omit benefits** that exist in only one contract - explicitly show these gaps
- Compare apples to oranges (ensure benefit categories align)
- Ignore conditions or fine print
- Make assumptions not supported by the documents
- Miss important exclusions or limitations
- Provide vague statements like "ProBTP is better" without quantification

**Value Assessment Framework:**
When determining "Advantage", consider:
1. **Coverage Amount:** Higher reimbursement percentage/amount
2. **Caps:** Presence of annual or lifetime limits
3. **Conditions:** Restrictions, waiting periods, exclusions
4. **Real-world cost:** Typical out-of-pocket based on average service costs
5. **Risk protection:** Which coverage protects against higher financial exposure?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROBTP INSURANCE CONTRACT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{probtp_markdown}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AXA INSURANCE CONTRACT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{axa_markdown}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Generate the complete comparison report following the structure above. Ensure:
1. All comparison tables are accurate and complete
2. Insights are written in plain, sales-ready language
3. Examples include specific euro amounts
4. Critical thinking is applied to assess TRUE value
5. Recommendations are actionable for different customer profiles

**REMEMBER: Write the ENTIRE report in {language}. Every section, heading, table, and explanation must be in {language}.**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**CRITICAL: Output ONLY the report content itself. Do NOT include:**
- Any preamble, introduction, or meta-commentary about the task (e.g., "Here is the report...", "Absolument, voici...", "I have analyzed...")
- Any concluding remarks or commentary after the report
- Any acknowledgments, confirmations, or conversational elements

**Simply begin directly with the report title/header and end with the final recommendation section.**

Your output should start immediately with the report content in Markdown format."""

    return prompt
