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

No experiment result has been generated in this stage.
