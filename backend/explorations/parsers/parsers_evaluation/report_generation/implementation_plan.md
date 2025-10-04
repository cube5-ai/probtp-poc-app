# Insurance Policy Comparison Report - Implementation Plan

## Goal

Automatically generate comparison reports between ProBTP and AXA insurance contracts for sales use. Reports will include readable comparison tables (Markdown/HTML) and insights that help salespeople communicate value differences to customers.

**Input:** Parsed AXA and ProBTP documents (JSON/Markdown from `landing_ai_xtd`)
**Output:** Sales-ready report with comparison tables and insights
**Model:** Gemini 2.5 Pro with high reasoning effort

---

## Report Structure (Sales-Focused)

### 1. Executive Summary
- Overall recommendation for different customer profiles
- Key differentiators between policies

### 2. Category Comparison Tables
For each healthcare category (Dental, Vision, Hospitalization, etc.):

**Example Table Format:**
| Benefit | ProBTP S2&P3+ | AXA Option | Advantage |
|---------|---------------|------------|-----------|
| Dental checkup | BR + 300% | BR + 200% | **ProBTP +50€** |
| Orthodontics | Unlimited | €500/year cap | **ProBTP** |

### 3. Category Insights
- Key differences explained in plain language
- Specific monetary examples
- Best coverage determination with reasoning

### 4. Overall Recommendation
- Strengths/weaknesses summary
- Use case recommendations

---

## Technical Approaches

### Approach A: Single-Shot Generation (Baseline)
**How:** One LLM call with both documents → complete report
**Pros:** Simple, fast, cost-effective
**Cons:** May miss categories, harder to debug

### Approach B: Two-Phase Pipeline
**Phase 1:** Extract aligned comparison tables per category (structured data)
**Phase 2:** Generate insights and sales narrative from tables
**Pros:** Better accuracy, debuggable, reusable tables
**Cons:** Higher cost, more complex

---

## Implementation Plan

### Phase 1: Setup (2-3 days)
- Create folder structure (`pipelines/`, `prompts/`, `output/`)
- Configure Gemini API with reasoning mode
- Build document loaders and report formatters

### Phase 2: Baseline Pipeline (3-4 days)
- Design single-shot prompt for sales report generation
- Implement `baseline_pipeline.py`
- Generate first report and evaluate quality
- Measure cost and execution time

### Phase 3: Two-Phase Pipeline (5-7 days)
- Build `alignment_pipeline.py` (extract comparison tables)
- Build `analysis_pipeline.py` (generate insights)
- Build `report_assembler.py` (create final Markdown/HTML)
- Compare with baseline

### Phase 4: Refinement (3-5 days)
- Optimize prompts for sales language clarity
- Add parallel processing for categories
- Test with different coverage combinations
- Polish report formatting

---

## Success Criteria

**Functional:**
- Report covers all major healthcare categories
- Tables are accurate and readable
- Insights use plain language with concrete examples
- Fully automated generation

**Quality:**
- Salesperson can understand and use the report immediately
- Comparison tables are factually correct (>90% accuracy)
- Insights include specific euro amounts where relevant

**Performance:**
- Generation time < 10 minutes
- Cost documented and acceptable

---

## Model Settings

**Gemini 2.5 Pro Configuration:**
- Reasoning effort: High
- Temperature: 0.2-0.3 (tables), 0.5-0.6 (insights)
- Output: Markdown with tables

---

## Next Steps

1. Set up infrastructure
2. Implement baseline approach first
3. Evaluate and compare with two-phase approach
4. Iterate based on output quality
