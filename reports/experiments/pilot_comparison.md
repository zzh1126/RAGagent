# Pilot Experiment Comparison

This report compares the four configured offline methods on the pilot split.
The frozen `final` split was not rerun.

- Dataset SHA-256: `fa48ddcb3e7f4ec794b9b95c0415b5f1ddbc937d6f2918987a29dd9abb7a19b0`
- Configuration fingerprint: `56dd6a55fd05a01490322283926a722a3fe0260d4b4b6534f21d2900ba04c44a`
- Semantic scores are user-confirmed; the original Codex-assisted scoring draft is retained for audit.

## Overall Metrics

| Method | Decision accuracy | Citation rate | Refusal accuracy | Over-refusal rate | Recall@5 | Path validity | Mean latency (ms) | Wrong IDs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Vector RAG | 0.9000 | 1.0000 | 0.0000 | 0.0000 | 0.8276 | n/a | 1.3250 | F-NA-01;F-NA-02;F-NA-03;F-NA-04 |
| Graph Only | 0.9000 | 1.0000 | 0.0000 | 0.0000 | 0.9655 | 1.0000 | 1.0000 | F-NA-01;F-NA-02;F-NA-03;F-NA-04 |
| Proposed | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.9655 | 1.0000 | 1.7000 | none |
| No Verifier | 0.9000 | 1.0000 | 0.0000 | 0.0000 | 0.9655 | 1.0000 | 1.2250 | F-NA-01;F-NA-02;F-NA-03;F-NA-04 |

## Category Accuracy

| Category | Vector RAG | Graph Only | Proposed | No Verifier |
| --- | ---: | ---: | ---: | ---: |
| comparison | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| definition | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| metric_selection | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| multi_hop | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| no_answer | 0.0000 | 0.0000 | 1.0000 | 0.0000 |
| principle_pros_cons | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| single_hop | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## Observations

- All four methods answered the 36 answerable pilot questions correctly at the decision level.
- Proposed correctly refused all four no-answer questions; the three verifier-disabled/fixed-route methods answered all four and therefore show 0/4 refusal accuracy.
- Vector RAG has lower Recall@5 than Graph Only, Proposed, and No Verifier on the conservative graph-derived gold subset.
- Latency is a local offline workflow measurement and is not an online LLM latency claim.
- These are pilot comparison results for method analysis, not a replacement for the frozen final result.

## Failure Cases

- `vector_rag`: `F-NA-01`, `F-NA-02`, `F-NA-03`, `F-NA-04`
- `graph_only`: `F-NA-01`, `F-NA-02`, `F-NA-03`, `F-NA-04`
- `proposed`: none
- `no_verifier`: `F-NA-01`, `F-NA-02`, `F-NA-03`, `F-NA-04`
