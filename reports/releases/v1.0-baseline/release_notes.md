# v1.0 Baseline Release Notes

Frozen on 2026-07-22 before the main ablation and technical-enhancement work.

## Scope

- Six scikit-learn official documentation pages, 180 text chunks, 50 graph entities, and 100 approved graph relations with chunk-level evidence.
- Vector, graph, and hybrid retrieval with dynamic routing in a real LangGraph `StateGraph` workflow.
- A shared `GraphRepository` contract with a verified NetworkX backend and an optional Neo4j backend.
- Claim-level evidence verification, one retry, conservative refusal, and a Streamlit demonstration UI.
- Offline rule/template answer generation. This release does not call a production LLM API.

This is a lightweight Knowledge-Graph-Enhanced RAG implementation. It does not implement the complete Microsoft GraphRAG community-detection, community-summary, or global-search pipeline.

## Frozen Evaluation

- Final holdout: 40 questions, run once after freezing the question set.
- Decision accuracy: 39/40 (`0.9750`).
- Citation rate: `0.9750`.
- Mean keyword coverage: `0.8375`.
- Mean entity coverage: `0.9208`.
- No-answer refusal accuracy: 4/4 (`1.0000`, with a small sample).
- Mean local workflow latency: `1.48 ms`; this is a hot local rule-path measurement, not online LLM latency.
- Known failure: `T-DF-01`, an AdaBoost definition question, was conservatively refused.

The earlier 40-question set is archived as `pilot`; it was used to find implementation gaps and is not reported as an unseen final test.

## Runtime Status

- LangGraph `1.0.10` is installed and the workflow reports `engine=langgraph`.
- NetworkX is the default, fully offline graph backend.
- The Neo4j repository implementation and import script are present; an external Neo4j server is optional and was not required for the frozen final evaluation.
- Streamlit was verified at `http://localhost:8501` on desktop and mobile viewports. Pass and refusal paths were both exercised.
- Vector retrieval uses local TF-IDF representations, including the Chroma collection build; no neural dense embedding model is active in v1.0.

## Known Limitations

- Sparse TF-IDF retrieval has limited semantic recall for paraphrases and mixed-language terminology.
- Answer wording is rule/template based, so fluency and synthesis are intentionally limited.
- The final holdout contains 40 questions, including only four no-answer cases.
- The knowledge base is restricted to six selected scikit-learn pages.
- Neo4j requires an external service and credentials; NetworkX remains the reproducible fallback.

## Integrity And Source State

The workspace was not a Git repository at freeze time, so no commit or tag could be recorded. `source_snapshot.zip` preserves the executable source, tests, and project entry files. `manifest.json` records byte sizes and SHA-256 hashes for every archived payload, and `MANIFEST_SHA256.txt` anchors the manifest itself.
