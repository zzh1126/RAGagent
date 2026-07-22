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

## LLM Client Readiness

The shared Ollama Client and strict structured-output contracts are available, with `qwen3:4b` configured locally:

```bash
python scripts/validate_config.py
python scripts/smoke_llm_client.py --timeout 180
pytest -q tests/test_llm_client.py
```

The Client always sends `think=false` and `stream=false`, reads only `message.content`, retries timeout or schema failure at most once, and emits metadata without prompts, generated content, thinking, or credentials. `OLLAMA_BASE_URL` and `OLLAMA_MODEL` can override the non-secret local endpoint and model settings.

The QA workflow still uses `GroundedAnswerGenerator` with `agent.generator_backend: offline_rule`. The LLM Answer Generator and fallback wiring are a separate implementation stage; the locked extension holdout must not be run during Client development.

## Streamlit Demo

```bash
streamlit run app/streamlit_app.py
```

Open `http://localhost:8501`. The interface exposes the answer, graph paths, official source chunks, verifier scores, retry count, and downloadable structured response.

## Evaluation

```bash
python scripts/validate_evaluation.py
python scripts/validate_extension_holdout.py
python scripts/run_evaluation.py --split dev
python scripts/validate_scoring.py
python scripts/generate_report_figures.py --check
```

Dataset ownership and leakage rules are documented in `data/evaluation/README.md`. Generated reports are written under `reports/`.

The `final` holdout is frozen and must not be rerun. Reuse `reports/evaluation_final.json` and verify it with `python scripts/freeze_baseline.py --verify`. The 23-question `extension` holdout is also frozen and remains execution-locked until the LLM Generator implementation and configuration are frozen.

The frozen holdout run is stored in `reports/evaluation_final.json`: 39 of 40 routing/refusal decisions were correct (`0.975`), including all four no-answer cases. The single residual error is an overly conservative refusal on an AdaBoost definition question.
