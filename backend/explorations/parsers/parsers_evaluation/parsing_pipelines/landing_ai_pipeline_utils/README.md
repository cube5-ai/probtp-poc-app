# Landing AI Enhanced Pipeline Utilities

This folder contains the modular implementation of the 4-phase enhanced Landing AI pipeline.

## Structure

- **phase1_parsers.py**: Parse documents with Landing AI and PyMuPDF, extract tables
- **phase2_matching.py**: Match tables between parsers using TF-IDF similarity  
- **phase3_correction.py**: Apply LLM-based corrections using PyMuPDF as reference
- **phase4_sanity_check.py**: Run sanity checks and apply vision-based corrections

## Usage

The main orchestration script is `landing_ai_xtd.py` in the parent directory.

```bash
cd backend/explorations/parsers/parsers_evaluation
uv run parsing_pipelines/landing_ai_xtd.py
```

## Pipeline Flow

1. **Phase 1**: Parse with both Landing AI (OCR) and PyMuPDF (deterministic)
2. **Phase 2**: Match tables using TF-IDF and cosine similarity
3. **Phase 3**: Correct OCR errors using LLM with PyMuPDF reference
4. **Phase 4**: Validate with sanity checks, apply vision corrections if needed

## Observability

All phases are instrumented with Langfuse for observability and debugging.

