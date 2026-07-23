# scikit-learn Knowledge QA Agent

Lightweight GraphRAG / knowledge-graph-enhanced RAG project for a six-day research practice.

The project scope is fixed to six scikit-learn official documentation pages, a small predefined bilingual knowledge graph, local TF-IDF retrieval with Chroma persistence artifacts, optional Neo4j graph retrieval, LangGraph orchestration, evidence verification, and Streamlit demonstration.

## Project Documents

- [PROJECT_HANDBOOK.md](PROJECT_HANDBOOK.md): complete project reference covering scope, data, architecture, modules, schemas, configuration, commands, experiments, results, safeguards, and defense-oriented questions.
- [PROJECT_GAPS_AND_ROADMAP.md](PROJECT_GAPS_AND_ROADMAP.md): current shortcomings, evidence, priorities, acceptance criteria, immediate implementation sequence, deferred work, and explicit No-Go items.
- [PROGRESS.md](PROGRESS.md): append-only stage history and the source of truth for the latest implementation status.

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
python scripts/validate_evidence_packer.py
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

Stage 8.1 adds the deterministic `intent_aware_v2` Evidence Packer between retrieval and LLM generation. It deduplicates chunks, preserves graph-bound evidence, balances intent-specific evidence, enforces item and character budgets without mutating `RetrievalResult`, restricts LLM validation to visible E/P/R IDs, and records per-call packing traces. The read-only dev/pilot contract check covers 50 questions with mean 4.38 selected chunks, maximum context length 7,783 characters, and one expected `no_text_evidence` gap on no-answer case `F-NA-01`.

This does not yet fix over-refusal. A current real dev smoke for “随机森林为什么更稳定” still refused after one retry: all citations and paths were valid, but two of three Claims failed the strict term-coverage check. Prompt v2 and claim-level partial pass remain the next stages.

The historical extension implementation is frozen at commit `bdedf7d`. Its release file still preserves the original `authorized_not_executed` value, while the immutable revocation record makes the effective status `revoked_before_execution`. The old command now fails before model inspection, holdout loading, or QA workflow construction. Versioned v2 scoring and trace contracts predeclare a four-method comparison, but no v2 release exists yet.

```bash
python scripts/validate_extension_holdout.py
python scripts/validate_extension_release.py --check-runtime-model --require-unexecuted
```

Both the generic evaluation runner and the controlled extension runner remain locked for extension execution.

## Streamlit Demo

```bash
streamlit run app/streamlit_app.py
```

Open `http://localhost:8501`. The interface exposes the answer, graph paths, official source chunks, verifier scores, retry count, and downloadable structured response.

## Evaluation

```bash
python scripts/validate_evaluation.py
python scripts/validate_evidence_packer.py
python scripts/validate_extension_holdout.py
python scripts/run_evaluation.py --split dev --output reports/evaluation_custom_dev.json
python scripts/validate_scoring.py
python scripts/generate_report_figures.py --check
```

Dataset ownership and leakage rules are documented in `data/evaluation/README.md`. Generated reports are written under `reports/`.

The `final` holdout is frozen and must not be rerun. Reuse `reports/evaluation_final.json` and verify it with `python scripts/freeze_baseline.py --verify`. The separate 23-question `extension` holdout has never been run. Its v1 release is revoked, the v2 protocol is frozen, and runtime enhancement must be completed and independently released before the one permitted v2 execution. No extension QA result exists yet.

The frozen holdout run is stored in `reports/evaluation_final.json`: 39 of 40 routing/refusal decisions were correct (`0.975`), including all four no-answer cases. The single residual error is an overly conservative refusal on an AdaBoost definition question.
