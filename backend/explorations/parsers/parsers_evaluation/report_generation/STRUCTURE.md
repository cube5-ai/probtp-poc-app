# Report Generation Structure

This document explains the complete structure of the structured output pipeline for insurance comparison reports.

## Overview

The pipeline has **3 phases**:
1. **Alignment**: Extract aligned comparison tables per category (JSON)
2. **Analysis**: Annotate tables and generate insights (JSON)
3. **Summary**: Generate cross-category summary (JSON)

All outputs are JSON with Pydantic schemas. Human-readable reports are generated using formatters.

---

## Phase 1: Alignment

**Input:** Two document markdowns (ProBTP + AXA), category name
**Output:** `ComparisonTable` (JSON)

### Schema

```python
ComparisonTable {
  metadata: {
    category: str
    policy_levels: {
      probtp: list[str]
      axa: list[str]
    }
  }
  rows: list[TableRow]
}

TableRow {
  cells: list[TableCell]
  # Note: comparison is added in Analysis phase, not here
}

TableCell {
  value: str
  type: "dimension" | "data"
  colspan?: int  # omit if 1
  rowspan?: int  # omit if 1
  sources: {
    probtp?: list[str]  # cell IDs from ProBTP doc
    axa?: list[str]     # cell IDs from AXA doc
  }
  metadata?: {
    document?: "probtp" | "axa"
    footnotes?: list[str]
    conditions?: str
  }
}
```

**Key Features:**
- Cell IDs provide grounding to original parsed PDF
- `type="dimension"` for labels/headers (alignable)
- `type="data"` for coverage values (document-specific)
- Supports merged cells (colspan/rowspan)
- **Condition extraction from two sources**:
  - **Source 1**: Direct conditions in cell/dimension text (e.g., "plafond €300", "jusqu'à 16 ans")
  - **Source 2**: Conditions from footnotes (e.g., "*jusqu'à 18 ans")
  - `metadata.footnotes`: Array of footnote markers (e.g., ["*", "(1)"])
  - `metadata.conditions`: **Combined** translation of direct conditions + footnote conditions
  - Examples:
    - "200% BR*" + footnote "*jusqu'à 18 ans" → conditions: "Limited to under 18 years old"
    - "100% BR (plafond €300)" → conditions: "Annual cap of €300"
    - Dimension: "Orthodontie (jusqu'à 16 ans)" + Cell: "€500(1)" + footnote "(1) 1 séance/an" → conditions: "Under 16 years old only; 1 session per year maximum"

---

## Phase 2: Analysis

**Input:** `ComparisonTable` from Phase 1
**Output:** `AnalysisOutput` (JSON)

### Schema

```python
AnalysisOutput {
  category: str
  annotated_table: AnnotatedComparisonTable
  key_differences: str
  concrete_examples: list[str]
  critical_thinking: str
  best_coverage: str
  salesperson_talking_points: list[str]
  objective_assessment: ObjectiveAssessment
}

AnnotatedComparisonTable {
  # Same as ComparisonTable but with annotations
  metadata: ComparisonTableMetadata
  rows: list[TableRow]  # with is_best and comparison added
}

TableRow {
  cells: list[TableCell]  # with is_best added
  comparison?: RowComparison  # NEW: row-level assessment
}

TableCell {
  # All fields from Phase 1, plus:
  is_best?: bool  # true if this coverage is better than competitor
}

RowComparison {
  winner: "probtp_much_better" | "probtp_better" | "equivalent" | "axa_better" | "axa_much_better"
  reasoning?: str  # brief explanation
}

ObjectiveAssessment {
  overall_winner: "probtp" | "axa"
  confidence: "high" | "medium" | "low"
  reasoning: str
  probtp_weaknesses: list[str]
  axa_weaknesses: list[str]
}
```

**Key Features:**
- **Cell-level `is_best`**: Flags which coverage is better for each data cell
  - **Factors in conditions from Phase 1**: A higher rate with restrictive conditions (e.g., age limits) may be worse than lower rate without conditions
  - Example: "200% BR" limited to under 18 may lose to "150% BR" with no age limit for adult customers
- **Row-level `comparison`**: 5-level assessment enabling filtering/sorting
  - `probtp_much_better`: >20% difference or €100+ impact
  - `probtp_better`: 10-20% difference or €20-100 impact
  - `equivalent`: <10% difference or <€20 impact
  - `axa_better`: 10-20% AXA advantage
  - `axa_much_better`: >20% AXA advantage
- **Dual perspective**: Sales-ready insights + brutally objective assessment

---

## Phase 3: Summary

**Input:** List of `AnalysisOutput` (subset of fields) for all categories
**Output:** `ComparisonSummary` (JSON)

### Schema

```python
ComparisonSummary {
  key_differences: str  # 2-3 paragraphs
  category_strengths: list[CategoryStrengths]
  probtp_overall_strengths: list[str]  # 3-5 points
  axa_overall_strengths: list[str]     # 3-5 points
  objective_evaluation: OverallComparison
  category_winners: list[CategoryObjectiveAssessment]
  selling_points: list[str]  # 5-7 points
  target_customer_fit: str   # 2-3 paragraphs
}

CategoryStrengths {
  category: str
  probtp_strengths: list[str]  # 2-3 points
  axa_strengths: list[str]     # 2-3 points
}

OverallComparison {
  overall_winner: "probtp" | "axa" | "mixed"
  confidence: "high" | "medium" | "low"
  reasoning: str  # 2-3 sentences
}

CategoryObjectiveAssessment {
  category: str
  winner: "probtp" | "axa"
  confidence: "high" | "medium" | "low"
  key_reason: str  # 1 sentence
}
```

**Key Features:**
- High-level synthesis across all categories
- Category-by-category breakdown for foldable UI sections
- Overall winner determination (`mixed` is valid)
- Sales-oriented talking points
- Customer segment targeting

---

## Formatters

Convert JSON to human-readable formats:

### `comparison_table_to_html(table_data)`
- Full HTML table with CSS classes
- `class="cell-best"` for is_best=true cells
- `class="cell-dimension"` vs `class="cell-data"`

### `comparison_table_to_markdown(table_data, include_row_comparison=True)`
- Markdown table with ✓ indicators for best coverage
- Optional row comparison notes with emoji indicators:
  - 🟢🟢 ProBTP beaucoup mieux
  - 🟢 ProBTP mieux
  - 🟡 Équivalent
  - 🔴 AXA mieux
  - 🔴🔴 AXA beaucoup mieux

### `analysis_to_markdown(analysis_data)`
- Full category analysis with sections:
  - Annotated comparison table
  - Key differences
  - Concrete examples
  - Value analysis
  - Sales perspective
  - Talking points
  - Objective assessment

### `summary_to_markdown(summary_data)`
- Landing page format:
  - Strategic differences
  - Category-by-category strengths
  - Overall strengths
  - Objective evaluation
  - Selling points
  - Customer fit analysis

---

## Use Cases

### Filtering Tables by Row Comparison
```python
# Get only rows where ProBTP is better
probtp_wins = [
    row for row in table["rows"]
    if row.get("comparison", {}).get("winner", "").startswith("probtp")
]

# Get only major differences (much_better on either side)
major_diffs = [
    row for row in table["rows"]
    if "much_better" in row.get("comparison", {}).get("winner", "")
]
```

### Building Web App UI
```json
{
  "summary": ComparisonSummary,  // Landing page
  "categories": [
    {
      "name": "Soins Courants",
      "analysis": AnalysisOutput,  // Full category page
      "table_html": "...",         // Generated HTML table
      "filters": {
        "probtp_advantages": [...rows where comparison.winner starts with "probtp"...],
        "axa_advantages": [...rows where comparison.winner starts with "axa"...],
        "equivalent": [...rows where comparison.winner == "equivalent"...]
      }
    }
  ]
}
```

### Exporting Reports
```python
# Markdown report
markdown = summary_to_markdown(summary_data)
for analysis in analyses:
    markdown += "\n\n" + analysis_to_markdown(analysis)

# JSON dump (for data analysis/reuse)
json.dump({
    "metadata": {...},
    "comparison_tables": [...],
    "analyses": [...],
    "summary": summary_data
}, output_file)
```

---

## Files

- **Prompts:**
  - `prompts/alignment_prompt.py`: Phase 1
  - `prompts/analysis_prompt.py`: Phase 2
  - `prompts/summary_prompt.py`: Phase 3

- **Pipeline:**
  - `pipelines/two_phase_pipeline.py`: Main orchestration

- **Utilities:**
  - `utils/json_formatters.py`: JSON → HTML/Markdown converters
  - `utils/document_loader.py`: Load parsed PDFs
  - `utils/gemini_client.py`: LLM API client
  - `utils/report_formatter.py`: Metadata utilities

---

## Benefits of This Structure

1. **Grounding**: Cell IDs link back to original PDF regions
2. **Filterability**: Row comparison enables UI filtering/sorting
3. **Dual Perspective**: Sales-ready + objective assessment
4. **Reusability**: JSON outputs can be consumed by web apps, analysis tools
5. **Extensibility**: Easy to add new fields or analysis dimensions
6. **Traceability**: Each cell tracks source documents
7. **Type Safety**: Pydantic validation ensures schema compliance
