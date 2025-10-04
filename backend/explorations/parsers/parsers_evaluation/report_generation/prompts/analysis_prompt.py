"""Analysis prompt template for generating insights from comparison tables."""

import json
from pydantic import BaseModel, Field


class CellMetadata(BaseModel):
    """Metadata for a table cell."""

    document: str | None = Field(
        None, description="Document source: 'probtp' or 'axa' (for header cells)"
    )
    footnotes: list[str] = Field(
        default_factory=list, description="Footnote references (e.g., ['*', '(1)'])"
    )
    conditions: str | None = Field(None, description="Special conditions or modifiers")


class CellSources(BaseModel):
    """Source cell IDs from original documents."""

    probtp: list[str] | None = Field(None, description="Cell IDs from ProBTP document")
    axa: list[str] | None = Field(None, description="Cell IDs from AXA document")


class TableCell(BaseModel):
    """A single cell in the comparison table."""

    value: str = Field(
        ..., description="Cell content (coverage amount, benefit name, etc.)"
    )
    type: str | None = Field(
        None,
        description="'data' for data cells. OMIT for dimension cells (labels/headers) to match alignment format.",
    )
    colspan: int | None = Field(None, description="Column span (omit if 1)")
    rowspan: int | None = Field(None, description="Row span (omit if 1)")
    sources: CellSources | None = Field(
        None, description="Source cell IDs from original parsed documents (preserve exact structure from alignment)"
    )
    metadata: CellMetadata | None = Field(None, description="Additional cell metadata")
    is_best: bool | None = Field(
        None,
        description="For data cells: True if this coverage is better than competitor. For dimension cells: null.",
    )


class TableRow(BaseModel):
    """A single row in the comparison table."""

    cells: list[TableCell] = Field(..., description="Cells in this row")


class PolicyLevels(BaseModel):
    """Policy levels for each insurer."""

    probtp: list[str] = Field(
        ..., description="ProBTP policy levels (e.g., ['S1', 'S2', 'S3'])"
    )
    axa: list[str] = Field(
        ..., description="AXA policy levels (e.g., ['Option 1', 'Option 2'])"
    )


class ComparisonTableMetadata(BaseModel):
    """Metadata for the comparison table."""

    category: str = Field(
        ..., description="Healthcare category (e.g., 'Soins courants', 'Dentaire')"
    )
    policy_levels: PolicyLevels = Field(..., description="Policy levels being compared")


class AnnotatedComparisonTable(BaseModel):
    """Comparison table with is_best annotations for each data cell."""

    metadata: ComparisonTableMetadata = Field(..., description="Table metadata")
    rows: list[TableRow] = Field(
        ..., description="Table rows with is_best annotations on data cells"
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


class AnalysisOutput(BaseModel):
    """Complete analysis output with annotated table and assessments."""

    category: str = Field(..., description="Category name")
    annotated_table: AnnotatedComparisonTable = Field(
        ..., description="Comparison table with is_best annotations"
    )
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
    objective_assessment: ObjectiveAssessment = Field(
        ..., description="Brutally honest competitive assessment"
    )


def _format_comparison_table(
    rows: list[dict], probtp_levels: list[str], axa_levels: list[str]
) -> tuple[str, str]:
    """
    Format the ComparisonTable rows into both text and JSON representations.

    Args:
        rows: List of TableRow dicts from ComparisonTable
        probtp_levels: ProBTP policy levels
        axa_levels: AXA policy levels

    Returns:
        Tuple of (text_representation, json_representation)
    """
    # Generate text representation
    text_lines = []

    for row_idx, row in enumerate(rows):
        cells = row.get("cells", [])
        cell_values = []

        for cell in cells:
            value = cell.get("value", "")
            cell_type = cell.get("type", "")
            sources = cell.get("sources", {})
            metadata = cell.get("metadata", {})

            # Format cell with metadata
            cell_repr = f'"{value}"'
            if cell_type:
                cell_repr += f" (type: {cell_type})"

            # Add source info
            probtp_sources = sources.get("probtp") or []
            axa_sources = sources.get("axa") or []
            if probtp_sources or axa_sources:
                source_parts = []
                if probtp_sources:
                    source_parts.append(f"probtp: {','.join(probtp_sources)}")
                if axa_sources:
                    source_parts.append(f"axa: {','.join(axa_sources)}")
                cell_repr += f" [sources: {'; '.join(source_parts)}]"

            # Add metadata info
            meta_parts = []
            if metadata.get("document"):
                meta_parts.append(f"doc: {metadata['document']}")
            if metadata.get("footnotes"):
                meta_parts.append(f"footnotes: {','.join(metadata['footnotes'])}")
            if metadata.get("conditions"):
                meta_parts.append(f"conditions: {metadata['conditions']}")
            if meta_parts:
                cell_repr += f" {{meta: {'; '.join(meta_parts)}}}"

            cell_values.append(cell_repr)

        text_lines.append(f"Row {row_idx}: [{' | '.join(cell_values)}]")

    text_representation = "\n".join(text_lines)

    # Generate JSON representation (nicely formatted)
    json_representation = json.dumps(rows, indent=2, ensure_ascii=False)

    return text_representation, json_representation


def create_analysis_prompt(
    comparison_table: dict, language: str = "French (France)"
) -> str:
    """
    Create a prompt for generating insights and analysis from a comparison table.

    Args:
        comparison_table: ComparisonTable output from alignment phase (dict with metadata and rows)
        language: Language for the output (default: "French (France)")

    Returns:
        Formatted prompt string
    """
    # Extract metadata
    metadata = comparison_table.get("metadata", {})
    category = metadata.get("category", "Unknown")
    policy_levels = metadata.get("policy_levels", {})
    probtp_levels = policy_levels.get("probtp", [])
    axa_levels = policy_levels.get("axa", [])

    # Format table as both text and JSON for the prompt
    rows = comparison_table.get("rows", [])
    table_text, table_json = _format_comparison_table(rows, probtp_levels, axa_levels)

    # Format levels context
    levels_context = ""
    if probtp_levels or axa_levels:
        levels_context = "\n\n**Contract Levels Being Compared:**"
        if probtp_levels:
            levels_context += f"\n- ProBTP: {', '.join(probtp_levels)}"
        if axa_levels:
            levels_context += f"\n- AXA: {', '.join(axa_levels)}"

    prompt = f"""You are an expert insurance analyst specializing in French health insurance. Your task is to generate comprehensive sales-ready insights and brutally objective analysis for a specific healthcare category.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Generate comprehensive analysis including:
1. Annotated comparison table with "is_best" flags for each data cell
2. Sales-ready insights for ProBTP sales team
3. Brutally objective assessment of which contract is actually better

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GENERAL TASK DESCRIPTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Analysis Components Required:**

1. **Annotated Comparison Table**
   - **CRITICAL**: Copy the EXACT structure from the input table (provided below as structured data)
   - **ONLY add the `is_best` field** - do NOT modify any other fields
   - Add `is_best: true/false` to EVERY data cell
   - For ProBTP data cells: is_best = true if ProBTP coverage is better
   - For AXA data cells: is_best = true if AXA coverage is better
   - Dimension cells (labels/headers) should have is_best = null
   - **Preserve EXACTLY**: value, type, sources, metadata, colspan, rowspan
   - **Do NOT add `type` field where it was omitted** (token optimization)
   - **Do NOT modify sources structure** (keep null fields as omitted, not as explicit None)
   - **Maintain exact row count, cell count, and all span values**

2. **Key Differences** (2-3 sentences in plain language)
   - Main strategic differences between ProBTP and AXA for the category
   - Which contract emphasizes what type of coverage?

3. **Concrete Examples** (2-3 specific scenarios with euro amounts)
   - Realistic scenarios showing actual costs and reimbursements
   - Exact out-of-pocket costs for each contract
   - Use typical service prices (e.g., dental crown €750, progressive glasses €600)
   - Format: "For [service] costing €X, ProBTP reimburses €Y (remain €Z), AXA reimburses €A (remain €B)"

4. **Critical Thinking & Value Assessment**
   - **Real-world probability:** How often do people use these benefits?
   - **Financial risk:** Which benefits protect against the highest financial exposure?
   - **Customer segments:** Which types of customers benefit most from each contract?
   - **Hidden value:** Network benefits, caps, or conditions that change value proposition

5. **Best Coverage** (1-2 paragraphs, ProBTP sales perspective)
   - Sales-oriented framing of ProBTP's value proposition
   - Specific sub-categories where ProBTP wins
   - What salespeople should emphasize
   - How to contextualize gaps where AXA is better

6. **Salesperson Talking Points** (3-5 key points)
   - Actionable points for ProBTP salespeople
   - Focus on ProBTP strengths and how to frame them
   - How to address competitive gaps

7. **Objective Assessment** (brutally honest)
   - **overall_winner**: 'probtp' or 'axa' - which contract is objectively better
   - **confidence**: 'high', 'medium', or 'low'
   - **reasoning**: Honest explanation even if unfavorable to ProBTP
   - **probtp_weaknesses**: Specific areas where ProBTP is objectively weaker
   - **axa_weaknesses**: Specific areas where AXA is objectively weaker

**Output Format:**

Return a JSON object conforming to the AnalysisOutput Pydantic schema (defined at the top of this file).

Example structure:

{{
  "category": "Soins courants",
  "annotated_table": {{
    "metadata": {{
      "category": "Soins courants",
      "policy_levels": {{
        "probtp": ["S1", "S2", "S3"],
        "axa": ["Base", "Option 1"]
      }}
    }},
    "rows": [
      {{
        "cells": [
          {{
            "value": "Consultations généraliste",
            "type": "dimension",
            "sources": {{"probtp": ["1-a"], "axa": ["2-b"]}},
            "metadata": {{}},
            "is_best": null
          }},
          {{
            "value": "100% BR",
            "type": "data",
            "sources": {{"probtp": ["1-c"]}},
            "metadata": {{"document": "probtp"}},
            "is_best": true
          }},
          {{
            "value": "90% BR",
            "type": "data",
            "sources": {{"axa": ["2-d"]}},
            "metadata": {{"document": "axa"}},
            "is_best": false
          }}
        ]
      }}
    ]
  }},
  "key_differences": "ProBTP emphasizes comprehensive coverage with higher reimbursement rates...",
  "concrete_examples": [
    "For a specialist consultation costing €50 (BR €25), ProBTP reimburses €40 (remain €10), AXA reimburses €35 (remain €15)",
    "For orthodontics costing €3000..."
  ],
  "critical_thinking": "Analysis of real-world value...",
  "best_coverage": "From ProBTP's sales perspective...",
  "salesperson_talking_points": [
    "Highlight ProBTP's superior coverage for routine care",
    "Emphasize cumulative savings over time",
    "Address orthodontics gap by focusing on adult coverage"
  ],
  "objective_assessment": {{
    "overall_winner": "probtp",
    "confidence": "high",
    "reasoning": "ProBTP offers objectively better value for this category because...",
    "probtp_weaknesses": ["Lower orthodontics coverage cap", "No preventive care bonus"],
    "axa_weaknesses": ["Lower reimbursement rates for routine care", "Higher out-of-pocket costs"]
  }}
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**DUAL PERSPECTIVE REQUIREMENT:**

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

**is_best Determination Methodology:**

For each data cell, determine is_best by comparing:
1. **Reimbursement rates**: Higher % BR or higher absolute € amount = better
2. **Coverage caps**: Higher or no cap = better (if rates are similar)
3. **Network benefits**: Better network access = better (note in metadata)
4. **Conditions**: Fewer restrictions = better (note in metadata)
5. **Practical value**: Consider real-world usage and financial impact

Example comparisons:
- ProBTP "150% BR" vs AXA "130% BR" → ProBTP is_best=true, AXA is_best=false
- ProBTP "€500/year" vs AXA "€800/year" → ProBTP is_best=false, AXA is_best=true
- ProBTP "100% BR (no cap)" vs AXA "100% BR (€300 cap)" → ProBTP is_best=true
- Equal coverage → both get is_best=true

**Analysis Methodology:**

1. Review the comparison table data (provided below)
2. **Annotate EVERY data cell** with is_best flag based on objective comparison
3. Calculate realistic reimbursement scenarios using typical BR values for France
4. Assess TRUE value - not just raw percentages, consider caps, conditions, networks
5. Think about customer psychology - what matters to different age groups?
6. **For sales insights:** Identify ProBTP advantages and how to frame gaps
7. **For objective assessment:** Determine true winner regardless of whose product it is
8. Consider cumulative costs over time

**Quality Standards:**

- Use exact euro amounts in examples
- **Annotated table**: Every data cell must have is_best value (true/false)
- **Sales insights**: Quantify ProBTP advantages, contextualize gaps
- **Objective assessment**: Be honest even if ProBTP loses
- Provide clear, actionable talking points for ProBTP salespeople
- Address different customer scenarios
- Output ONLY the JSON object - no preamble, no commentary

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK PARAMETERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Category:** {category}{levels_context}

**Output Language:** {language}

**Comparison Table Data (from alignment phase):**

### Text Representation (for human readability):

{table_text}

### JSON Representation (structured data for modification):

```json
{table_json}
```

**Task Recap:**
Based on the instructions above, generate a comprehensive analysis for the "{category}" category. The analysis must include:
1. Annotated comparison table with is_best flags for all data cells
2. Sales-ready insights from ProBTP's perspective
3. Brutally objective assessment of which contract is actually better

Output all content in {language}. Output ONLY the JSON conforming to AnalysisOutput schema.

Generate the JSON analysis now:"""

    return prompt
