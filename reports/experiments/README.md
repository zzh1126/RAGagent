# Experiment Output Directory

This directory is reserved for the Day 6 main experiments and verifier ablation.

## Frozen Protocol

- Tuning split: `dev`.
- Reproducible experiment split: `pilot`.
- Frozen holdout: `final`, read-only; reuse `reports/evaluation_final.json` and do not rerun it.
- Retrieval metric: Recall@5.
- Required runnable methods: `vector_rag`, `graph_only`, `proposed`, and `no_verifier`.
- Disabled methods: `direct_llm` (no stable real LLM endpoint) and optional `no_router`.
- Human correctness, faithfulness, hallucination, and over-refusal metrics remain pending until manual review.

Validate the protocol without running an experiment:

```bash
python scripts/validate_experiments.py
```

At the initial contract-freeze stage this directory contained no experiment result; the pilot artifacts below were generated only after the runner passed its regression tests.

After the pilot run, the directory contains:

- `vector_rag_pilot.json`
- `graph_only_pilot.json`
- `proposed_pilot.json`
- `no_verifier_pilot.json`
- `pilot_comparison.csv`, `pilot_comparison.json`, and `pilot_comparison.md`

The blank 160-row manual review sheet is `reports/human_scoring.csv`. Empty score fields are intentional; they must be reviewed and filled separately.
