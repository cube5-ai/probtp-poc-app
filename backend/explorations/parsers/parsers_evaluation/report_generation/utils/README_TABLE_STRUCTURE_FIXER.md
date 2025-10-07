# Table Structure Fixer - Bidirectional Validation

## Overview

The Table Structure Fixer leverages **schema redundancy** to automatically correct LLM mistakes in table generation. It performs **bidirectional validation** in three phases:

1. **Phase 1 (Priority)**: Real cells with `rowspan`/`colspan` → Add missing virtual cells
2. **Phase 2 (Fallback)**: Virtual cells with `ref` → Infer missing `rowspan`/`colspan` 
3. **Phase 3 (Consistency)**: Update `inherited_from_above` arrays

This ensures tables are **self-healing** regardless of which part the LLM got right.

## Test Results

On actual `Soins_Courants_analysis.json`:
- **Phase 2**: Fixed 6 missing rowspans (E2, E7, B18)
- **Phase 3**: Fixed 7 `inherited_from_above` arrays

All HTML tables now render correctly with proper rowspan/colspan! 🎉
