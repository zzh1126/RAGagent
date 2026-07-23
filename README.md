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
python scripts/validate_atomic_claim_prompt.py
python scripts/validate_claim_level_verifier.py
python scripts/run_agent.py "随机森林为什么更稳定"
python scripts/run_agent.py "类别不平衡时用什么指标"
pytest -q
```

The workflow routes each query to vector, graph, or hybrid retrieval, generates citation-bearing claims, verifies each Claim and graph path, retains supported Claims, retries only when no Claim can yet be kept, and refuses unsupported questions. It uses the real `langgraph` runtime when that package is installed; otherwise it uses the included local state-machine runner with the same node transitions so development remains offline-capable.

Set `GRAPH_BACKEND=neo4j` together with `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` to switch the graph repository. The default remains `networkx`.

## LLM Generation Mode

The default workflow uses the rule Router with a real `qwen3:4b` Answer Generator, deterministic Evidence Verifier, and `GroundedAnswerGenerator` fallback:

```bash
python scripts/validate_config.py
python scripts/smoke_llm_client.py --timeout 180
python scripts/validate_atomic_claim_prompt.py
python scripts/validate_claim_level_verifier.py
python scripts/run_agent.py "随机森林为什么更稳定"
pytest -q tests/test_llm_client.py tests/test_answer_generators.py tests/test_atomic_claim_prompt.py tests/test_claim_level_verifier.py
```

The Client always sends `think=false` and `stream=false`, reads only `message.content`, retries timeout or schema failure at most once, and emits metadata without prompts, generated content, thinking, or credentials. Every LLM Claim must bind existing E/P/R IDs and an exact source quote; the Verifier also applies a conservative bilingual term-coverage check.

Set `AGENT_GENERATOR_BACKEND=offline_rule` to force the deterministic mode. `OLLAMA_BASE_URL` and `OLLAMA_MODEL` can override the non-secret local endpoint and model. If Ollama is unavailable, the LLM mode automatically falls back to the offline generator.

The candidate 10-question dev run reached `10/10` structured outputs with no runtime fallback, but only `6/10` pass/refuse decisions; all four errors were over-refusals. This is development evidence, not an independent result, and does not establish that LLM generation outperforms the rule baseline. See `reports/llm_generator_dev_audit.md`.

Stage 8.1 adds the deterministic `intent_aware_v2` Evidence Packer between retrieval and LLM generation. It deduplicates chunks, preserves graph-bound evidence, balances intent-specific evidence, enforces item and character budgets without mutating `RetrievalResult`, restricts LLM validation to visible E/P/R IDs, and records per-call packing traces. The read-only dev/pilot contract check covers 50 questions with mean 4.38 selected chunks, maximum context length 7,783 characters, and one expected `no_text_evidence` gap on no-answer case `F-NA-01`.

Stage 8.2 upgrades the generator to atomic Claim Prompt v2. The wire schema permits only 1-4 Claims, encodes separate E/P/R ID namespaces, requires at least one E ID and verbatim quote per Claim, and rejects a fifth Claim or unknown fields. Its frozen Prompt and wire-schema SHA-256 values are `e5c6fa6bbc992a9af2c66daffd8fcffeb2da1eae02202d932aef33fbbb774cad` and `b11bf9c445d3aa37c98cd571b880a157387661fdebf63a11a43aef786c7087eb`.

The formal synthetic probe passed `20/20` runs across random-forest, AdaBoost, comparison, and partial-evidence scenarios. It persists only aggregate structure, ID, error-code, and latency fields; prompts, generated answers, quotes, and thinking are not stored. This is an engineering gate, not an independent answer-quality result.

Stage 8.3 connects Claim-level verification and adds `partial_pass`. Each generated Claim now receives a stable C ID, supported/unsupported status, reason codes, retained/removed state, valid E/P IDs, and verification latency. LLM mode defaults to partial-pass, while the offline rule baseline remains strict and LLM strict mode is available as an explicit ablation override. Mixed Claims are filtered without a second LLM call; zero supported Claims may retry once, and a false graph premise refuses immediately.

The sanitized DEV02 smoke for “随机森林为什么更稳定” now returns `partial_pass`: 2 of 4 Claims are retained, 2 are removed, citation/path validity remain `1.0000`, retry count falls from 1 to 0, and unsupported-Claim leakage is 0. The warm recorded run used one LLM call with 7,275.8 ms generation and 7,288 ms end-to-end latency. This single development smoke demonstrates the filtering mechanism, not overall quality improvement or a new dev/pilot/extension result.

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
python scripts/validate_atomic_claim_prompt.py
python scripts/validate_claim_level_verifier.py
python scripts/validate_extension_holdout.py
python scripts/run_evaluation.py --split dev --output reports/evaluation_custom_dev.json
python scripts/validate_scoring.py
python scripts/generate_report_figures.py --check
```

Dataset ownership and leakage rules are documented in `data/evaluation/README.md`. Generated reports are written under `reports/`.

The `final` holdout is frozen and must not be rerun. Reuse `reports/evaluation_final.json` and verify it with `python scripts/freeze_baseline.py --verify`. The separate 23-question `extension` holdout has never been run. Its v1 release is revoked, the v2 protocol is frozen, and runtime enhancement must be completed and independently released before the one permitted v2 execution. No extension QA result exists yet.

The frozen holdout run is stored in `reports/evaluation_final.json`: 39 of 40 routing/refusal decisions were correct (`0.975`), including all four no-answer cases. The single residual error is an overly conservative refusal on an AdaBoost definition question.
