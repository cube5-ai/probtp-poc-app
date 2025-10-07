"""Ambiguous case classification prompt for categorizing edge cases."""

from pydantic import BaseModel, Field


class ClassifiedCase(BaseModel):
    """A classified ambiguous case."""
    original_description: str = Field(..., description="Original item description from ambiguous cases")
    assigned_category: str = Field(..., description="The category this item should belong to")
    confidence: str = Field(..., description="Confidence level: 'high', 'medium', or 'low'")
    reasoning: str = Field(..., description="Why this category was chosen")
    probtp_classification: str | None = Field(None, description="For AXA items: how ProBTP would classify this. Omit for ProBTP items.")
    axa_classification: str | None = Field(None, description="For ProBTP items: how AXA would classify this. Omit for AXA items.")


class AmbiguousClassificationOutput(BaseModel):
    """Output schema for ambiguous case classification."""
    vendor: str = Field(..., description="Vendor being classified (ProBTP or AXA)")
    category: str = Field(..., description="Original category these cases were extracted from")
    classified_cases: list[ClassifiedCase] = Field(..., description="All classified cases")


def create_ambiguous_classification_prompt(
    vendor: str,
    category: str,
    ambiguous_cases: list[dict],
    probtp_taxonomy_tree: str,
    language: str = "French (France)"
) -> str:
    """
    Create a prompt for classifying ambiguous cases using ProBTP taxonomy.

    Args:
        vendor: Vendor name (ProBTP or AXA)
        category: Original category the ambiguous cases came from
        ambiguous_cases: List of ambiguous case dicts
        probtp_taxonomy_tree: ASCII art tree of ProBTP categories
        language: Output language

    Returns:
        Formatted prompt string
    """
    # Format ambiguous cases for display
    cases_text = ""
    for i, case in enumerate(ambiguous_cases, 1):
        cases_text += f"\n{i}. **{case.get('item_description', 'Unknown')}**\n"
        cases_text += f"   - Reasoning: {case.get('reasoning', 'N/A')}\n"
        cases_text += f"   - Candidate Categories: {', '.join(case.get('candidate_categories', []))}\n"

    prompt = f"""You are an expert insurance analyst specializing in French health insurance (mutuelle) contracts. Your task is to classify ambiguous benefits into the correct category using the ProBTP taxonomy as the reference.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL: CLASSIFY AMBIGUOUS CASES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Context:**

We extracted benefits from the {vendor} contract for the "{category}" category. Some benefits were flagged as ambiguous because they could belong to multiple categories or might be out of scope.

Your task is to classify each ambiguous case into the CORRECT category using the ProBTP taxonomy as the authoritative reference.

**ProBTP Taxonomy (Reference):**

```
{probtp_taxonomy_tree}
```

**Classification Rules:**

1. **ProBTP is the Reference**: Always use ProBTP's category structure as the authoritative taxonomy
2. **For ProBTP Items**: Classify directly using the ProBTP taxonomy above
3. **For AXA Items**: Map to ProBTP categories semantically (AXA may use different terminology)
4. **Semantic Mapping**: Focus on the nature of the benefit, not just the name
5. **Specificity Preference**: Choose the most specific applicable category
6. **Out of Scope**: If an item doesn't fit any category, classify it as "Out of Scope"

**Confidence Levels:**
- **high**: Clear semantic match, unambiguous classification
- **medium**: Reasonable match but some ambiguity remains
- **low**: Best guess, significant uncertainty

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AMBIGUOUS CASES TO CLASSIFY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Vendor:** {vendor}
**Original Category:** {category}

**Cases:**
{cases_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each ambiguous case above:

1. Determine the correct category from the ProBTP taxonomy
2. Assign a confidence level (high/medium/low)
3. Provide clear reasoning for the classification
4. If {vendor} == "AXA": Also note how ProBTP would classify this benefit
5. If {vendor} == "ProBTP": Also note how AXA might classify this benefit (if different)

**Output Language:** {language}

**Return**: ONLY the JSON object conforming to AmbiguousClassificationOutput schema.

**Example Output:**

{{
  "vendor": "{vendor}",
  "category": "{category}",
  "classified_cases": [
    {{
      "original_description": "Ostéopathie (3 séances/an)",
      "assigned_category": "Médecines Douces",
      "confidence": "high",
      "reasoning": "Ostéopathie is a complementary medicine practice, which fits under 'Médecines Douces' rather than 'Soins Courants' in the ProBTP taxonomy",
      "probtp_classification": "Médecines Douces"  // Only if vendor == AXA
    }},
    {{
      "original_description": "Consultation spécialiste hors parcours",
      "assigned_category": "Soins Courants",
      "confidence": "medium",
      "reasoning": "This is a medical consultation, which belongs to 'Soins Courants', though the 'hors parcours' aspect could make it fit in a subcategory if available",
      "axa_classification": "Soins de Ville"  // Only if vendor == ProBTP
    }}
  ]
}}

Output the JSON now:"""

    return prompt
