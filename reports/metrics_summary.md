# Pilot Metrics Summary

Automatic experiment metrics are combined with Codex-assisted preliminary semantic scores.
The preliminary columns require user confirmation before being described as human evaluation.
The frozen final split was not rerun.

| Method | Decision acc. | Answer correctness* | Faithfulness* | Recall@5 | Path validity | Refusal acc. | Hallucination* | Over-refusal | Latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| vector_rag | 0.9000 | 0.5375 | 0.4875 | 0.8276 | n/a | 0.0000 | 0.0000 | 0.0000 | 1.3250 |
| graph_only | 0.9000 | 0.8375 | 0.9250 | 0.9655 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| proposed | 1.0000 | 0.8625 | 1.0000 | 0.9655 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.7000 |
| no_verifier | 0.9000 | 0.8000 | 0.8500 | 0.9655 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.2250 |

`*` Codex-assisted preliminary semantic review, status: `preliminary_pending_user_confirmation`.

Interpretation: Proposed has the strongest preliminary correctness and faithfulness among the four methods, while its main verified gain is 4/4 no-answer refusal. The zero preliminary hallucination rate means the observed failures were mostly irrelevant or incomplete but cited answers, not unsupported professional facts.
