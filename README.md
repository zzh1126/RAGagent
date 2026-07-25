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
python scripts/validate_runtime_trace.py
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
python scripts/validate_runtime_trace.py
python scripts/run_agent.py "随机森林为什么更稳定"
pytest -q tests/test_llm_client.py tests/test_answer_generators.py tests/test_atomic_claim_prompt.py tests/test_claim_level_verifier.py
```

The Client always sends `think=false` and `stream=false`, reads only `message.content`, retries timeout or schema failure at most once, and emits metadata without prompts, generated content, thinking, or credentials. Every LLM Claim must bind existing E/P/R IDs and an exact source quote; the Verifier also applies a conservative bilingual term-coverage check.

Set `AGENT_GENERATOR_BACKEND=offline_rule` to force the deterministic mode. `OLLAMA_BASE_URL` and `OLLAMA_MODEL` can override the non-secret local endpoint and model. If Ollama is unavailable, the LLM mode automatically falls back to the offline generator.

The historical pre-Partial-pass 10-question dev candidate reached `10/10` structured outputs with no runtime fallback, but only `6/10` pass/refuse decisions; all four errors were over-refusals. This remains useful as the before-state in `reports/llm_generator_dev_audit.md`.

Stage 8.1 adds the deterministic `intent_aware_v2` Evidence Packer between retrieval and LLM generation. It deduplicates chunks, preserves graph-bound evidence, balances intent-specific evidence, enforces item and character budgets without mutating `RetrievalResult`, restricts LLM validation to visible E/P/R IDs, and records per-call packing traces. The read-only dev/pilot contract check covers 50 questions with mean 4.38 selected chunks, maximum context length 7,783 characters, and one expected `no_text_evidence` gap on no-answer case `F-NA-01`.

Stage 8.2 upgrades the generator to atomic Claim Prompt v2. The wire schema permits only 1-4 Claims, encodes separate E/P/R ID namespaces, requires at least one E ID and verbatim quote per Claim, and rejects a fifth Claim or unknown fields. Its frozen Prompt and wire-schema SHA-256 values are `e5c6fa6bbc992a9af2c66daffd8fcffeb2da1eae02202d932aef33fbbb774cad` and `b11bf9c445d3aa37c98cd571b880a157387661fdebf63a11a43aef786c7087eb`.

The formal synthetic probe passed `20/20` runs across random-forest, AdaBoost, comparison, and partial-evidence scenarios. It persists only aggregate structure, ID, error-code, and latency fields; prompts, generated answers, quotes, and thinking are not stored. This is an engineering gate, not an independent answer-quality result.

Stage 8.3 connects Claim-level verification and adds `partial_pass`. Each generated Claim now receives a stable C ID, supported/unsupported status, reason codes, retained/removed state, valid E/P IDs, and verification latency. LLM mode defaults to partial-pass, while the offline rule baseline remains strict and LLM strict mode is available as an explicit ablation override. Mixed Claims are filtered without a second LLM call; zero supported Claims may retry once, and a false graph premise refuses immediately.

The sanitized DEV02 smoke for “随机森林为什么更稳定” now returns `partial_pass`: 2 of 4 Claims are retained, 2 are removed, citation/path validity remain `1.0000`, retry count falls from 1 to 0, and unsupported-Claim leakage is 0. The warm recorded run used one LLM call with 7,275.8 ms generation and 7,288 ms end-to-end latency. This single development smoke demonstrates the filtering mechanism, not overall quality improvement or a new dev/pilot/extension result.

Stage 8.4 adds one response-level runtime contract for routing, every retrieval call, every generation call, Evidence Packer calls, every verification call, retry-branch wall-clock time, and monotonic end-to-end latency. Generation calls now expose provider/model plus requested and actual backend, so a failed Ollama call remains visible when the offline fallback answers. The CLI and development evaluation runner serialize the same trace rather than recomputing incompatible timing fields.

Streamlit now performs one fixed synthetic structured warmup when the cached workflow starts. The warmup never reads demo/dev/pilot/final/extension questions and is excluded from per-question latency. The UI gives `partial_pass` its own warning color and displays model, requested/actual backend, fallback reason, structured-output status, cache status, all stage latencies, and per-call trace tables. Answer caching remains disabled. Browser smoke artifacts cover pass, partial-pass, refuse, and fallback on 1440 px desktop and 390 px mobile viewports; they are engineering UI checks, not evaluation results.

Stage 8.5 reran all 10 dev questions with the current v2 workflow. The development candidate reached `9/10` automatic decisions, `10/10` structured outputs, `2/2` no-answer refusals, `1/8` answerable over-refusals, `3/10` retry usage, and zero unsupported-Claim leakage. DEV02, DEV03, and DEV10 now return filtered `partial_pass` answers; DEV05 remains refused because the fixed six-page corpus does not contain direct AdaBoost sample-weight mechanism evidence. The only implementation adjustment was conservative quote normalization for case, Unicode hyphens, and direct overfit/generalization variants. These are dev engineering gates, not an independent quality result or evidence that the LLM outperforms the rule baseline. See `reports/llm_agent_v2_dev_stage8_5_audit.md`.

The historical extension implementation is frozen at commit `bdedf7d`. Its release file still preserves the original `authorized_not_executed` value, while the immutable revocation record makes the effective status `revoked_before_execution`. The old command now fails before model inspection, holdout loading, or QA workflow construction.

Stage 8.6 consumed the one permitted 40-question pilot freeze run on implementation commit `e207cb9`. The candidate reached `0.8250` decision accuracy, `0.9750` structured-output success, `4/4` no-answer refusal accuracy, `7/36` answerable over-refusals, `13/40` retry usage, and zero unsupported-Claim leakage. The predeclared gate returned `go`; the result is an engineering freeze check, not independent quality evidence. Mean end-to-end latency was `34,180.72 ms`, which remains a material limitation.

Stage 8.7 then completed the only permitted v2 extension execution for release `extension-qwen3-4b-v2-e207cb91`: 23 questions x 4 frozen methods, for 92 QA invocations. The release record intentionally remains `authorized_not_executed`, while the immutable state and receipt make the effective execution status `completed_once`. Automatic decision accuracy was `21/23` for Rule Baseline, `7/23` for LLM Strict v2, `19/23` for LLM No Verifier v2, and `16/23` for LLM Partial-pass v2. Partial-pass reduced answerable over-refusal from Strict's `16/19` to `5/19` and leaked `0/27` unsupported Claims, but it falsely accepted two of four no-answer questions and did not beat the rule baseline on this automatic decision metric. These automatic labels do not replace human correctness, faithfulness, hallucination, or readability scoring.

The anonymous A/B/C/D blind-review CSV contains 92 rows and does not expose method IDs or expected-answer fields; the method key was kept separate until scoring was locked. Codex-assisted scores were subsequently reviewed and confirmed by the user before unblinding. User-confirmed Correctness / Faithfulness / Hallucination / Over-refusal / Readability were respectively `0.5870 / 0.8810 / 0.0000 / 0.0000 / 3.56` for Rule Baseline, `0.3043 / 1.0000 / 0.0000 / 0.8421 / 5.00` for LLM Strict v2, `0.7826 / 0.8182 / 0.2727 / 0.0000 / 4.32` for LLM No Verifier v2, and `0.5217 / 0.9375 / 0.0000 / 0.2632 / 3.73` for LLM Partial-pass v2. Readability denominators differ because refusals and fully incorrect answers are excluded; Strict's `5.00` is based on only three substantive answers.

These results show a tradeoff rather than an overall winner. Partial-pass reduces over-refusal relative to Strict and preserves high faithfulness with no observed hallucination, but it does not exceed the rule baseline on user-confirmed correctness. No Verifier has the highest correctness and readability while leaking unsupported claims and producing a `6/22` user-confirmed hallucination rate. The review is a single user confirmation of Codex-assisted scores, not independent double annotation or a significance test.

```bash
python scripts/validate_extension_holdout.py
python scripts/validate_extension_release_v2.py --check-runtime-model
python scripts/validate_extension_results_v2.py
python scripts/validate_extension_blind_confirmation.py
```

The generic evaluation runner and revoked v1 runner remain locked. The v2 runner now rejects another execution because the one-run receipt already exists. Do not rerun or overwrite any extension artifact.

## Final Research Report

The formal 30-page A4 report is generated deterministically from `reports/research_report_draft.md`:

```bash
python scripts/generate_research_report_docx.py --check
python scripts/validate_report_claims.py
pytest -q tests/test_research_report_docx.py
```

The deliverable is `reports/final/基于预定义知识图谱的轻量化混合GraphRAG科研实践报告.docx`. Its manifest binds the Markdown source, generator, nine figures, static render-verified TOC, and output SHA-256. All 30 rendered pages have been visually checked; QA PNGs are temporary review artifacts and are not committed.

## Streamlit Demo

```bash
streamlit run app/streamlit_app.py
```

Open `http://localhost:8501`. If that port is occupied, run `streamlit run app/streamlit_app.py --server.port 8502` instead. The interface exposes the answer, retained Claim coverage, graph paths, official source chunks, verifier details, real model/backend/fallback status, startup warmup status, routing/retrieval/packing/generation/verification/retry/end-to-end latency, per-call traces, and the downloadable structured response.

The optional browser smoke helper uses the locally installed Playwright package and Microsoft Edge:

```bash
python scripts/smoke_streamlit_runtime.py --url http://127.0.0.1:8501 --query "随机森林为什么更稳定" --expected-decision PARTIAL_PASS --expected-fallback false --expected-structured success --expected-prewarm ready --output-prefix reports/streamlit_stage8_4_partial
```

## Evaluation

```bash
python scripts/validate_evaluation.py
python scripts/validate_evidence_packer.py
python scripts/validate_atomic_claim_prompt.py
python scripts/validate_claim_level_verifier.py
python scripts/validate_runtime_trace.py
python scripts/validate_extension_holdout.py
python scripts/run_evaluation.py --split dev --output reports/evaluation_custom_dev.json
python scripts/validate_scoring.py
python scripts/generate_report_figures.py --check
```

Dataset ownership and leakage rules are documented in `data/evaluation/README.md`. Generated reports are written under `reports/`.

The `final` holdout is frozen and must not be rerun. Reuse `reports/evaluation_final.json` and verify it with `python scripts/freeze_baseline.py --verify`. The separate 23-question `extension` holdout has been consumed exactly once by the controlled v2 four-method runner, and its 92 blind scores are now user-confirmed. Reuse the immutable and post-release audit files under `reports/extension_v2/`; do not rerun the holdout or tune the frozen runtime from its results.

The frozen holdout run is stored in `reports/evaluation_final.json`: 39 of 40 routing/refusal decisions were correct (`0.975`), including all four no-answer cases. The single residual error is an overly conservative refusal on an AdaBoost definition question.
