# scikit-learn Knowledge QA Agent

Lightweight GraphRAG / knowledge-graph-enhanced RAG project for a six-day research practice.

The project scope is fixed to six scikit-learn official documentation pages, a small predefined bilingual knowledge graph, Chroma vector retrieval, optional Neo4j graph retrieval, LangGraph orchestration, evidence verification, and Streamlit demonstration.

## Day 1 Smoke Commands

```bash
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/build_neo4j.py
pytest -q
```

`GRAPH_BACKEND=networkx` is the default development fallback. Neo4j can be enabled later without changing retriever or agent code because both backends implement the same graph repository interface.

## Current Local Workflow

Build or validate the local data, then run the unified QA workflow:

```bash
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/run_agent.py "随机森林为什么更稳定"
python scripts/run_agent.py "类别不平衡时用什么指标"
pytest -q
```

The workflow routes each query to vector, graph, or hybrid retrieval, generates citation-bearing claims, verifies evidence and graph paths, retries at most once, and refuses unsupported questions. It uses the real `langgraph` runtime when that package is installed; otherwise it uses the included local state-machine runner with the same node transitions so development remains offline-capable.

Set `GRAPH_BACKEND=neo4j` together with `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` to switch the graph repository. The default remains `networkx`.

## LLM Generation Mode

The default workflow uses the rule Router with a real `qwen3:4b` Answer Generator, deterministic Evidence Verifier, and `GroundedAnswerGenerator` fallback:

```bash
python scripts/validate_config.py
python scripts/smoke_llm_client.py --timeout 180
python scripts/run_agent.py "随机森林为什么更稳定"
pytest -q tests/test_llm_client.py tests/test_answer_generators.py
```

The Client always sends `think=false` and `stream=false`, reads only `message.content`, retries timeout or schema failure at most once, and emits metadata without prompts, generated content, thinking, or credentials. Every LLM Claim must bind existing E/P/R IDs and an exact source quote; the Verifier also applies a conservative bilingual term-coverage check.

Set `AGENT_GENERATOR_BACKEND=offline_rule` to force the deterministic mode. `OLLAMA_BASE_URL` and `OLLAMA_MODEL` can override the non-secret local endpoint and model. If Ollama is unavailable, the LLM mode automatically falls back to the offline generator.

The candidate 10-question dev run reached `10/10` structured outputs with no runtime fallback, but only `6/10` pass/refuse decisions; all four errors were over-refusals. This is development evidence, not an independent result, and does not establish that LLM generation outperforms the rule baseline. See `reports/llm_generator_dev_audit.md`.

The extension implementation is frozen at commit `bdedf7d`, and release `extension-qwen3-4b-v1-bdedf7dc` is authorized but not executed. The generic evaluation runner remains locked. Validate the release without exposing holdout questions to the QA workflow:

```bash
python scripts/validate_extension_release.py --check-runtime-model --require-unexecuted
python scripts/run_extension_evaluation.py --preflight
```

## Streamlit Demo

```bash
streamlit run app/streamlit_app.py
```

Open `http://localhost:8501`. The interface exposes the answer, graph paths, official source chunks, verifier scores, retry count, and downloadable structured response.

## Evaluation

```bash
python scripts/validate_evaluation.py
python scripts/validate_extension_holdout.py
python scripts/run_evaluation.py --split dev --output reports/evaluation_custom_dev.json
python scripts/validate_scoring.py
python scripts/generate_report_figures.py --check
```

Dataset ownership and leakage rules are documented in `data/evaluation/README.md`. Generated reports are written under `reports/`.

The `final` holdout is frozen and must not be rerun. Reuse `reports/evaluation_final.json` and verify it with `python scripts/freeze_baseline.py --verify`. The 23-question `extension` holdout is frozen separately; its implementation and one-time release are ready, but no extension QA run or result exists yet.

The frozen holdout run is stored in `reports/evaluation_final.json`: 39 of 40 routing/refusal decisions were correct (`0.975`), including all four no-answer cases. The single residual error is an overly conservative refusal on an AdaBoost definition question.
