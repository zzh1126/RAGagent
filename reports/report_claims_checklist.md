# 科研报告事实声明检查清单

## 使用范围

本清单约束 `reports/research_report_draft.md` 中容易被误述的范围、指标和实验状态。当前基线仍为 `v1.0-baseline`，开发分支为 `experiment/llm-agent-v2`；pilot 语义评分已经由用户确认，Evidence Packer、原子 Claim Prompt v2、Claim-level Partial-pass、完整 trace 和 Stage 8.5 dev 工程回归已完成，但 Stage 8.6 pilot 冻结前回归与 extension 独立实验尚未运行，extension 仍处于锁定状态。

## 权威证据源

| 证据 | 用途 |
| --- | --- |
| `reports/releases/v1.0-baseline/data_statistics.json` | 知识库规模、final 自动指标、唯一错误 |
| `reports/releases/v1.0-baseline/release_notes.md` | v1.0 范围、运行后端和指标解释边界 |
| `reports/releases/v1.0-baseline/manifest.json` | 23 个归档 payload 及逐文件 SHA-256 |
| `reports/releases/v1.0-baseline/MANIFEST_SHA256.txt` | Manifest SHA-256 |
| `reports/experiments/pilot_comparison.json` | 四种 pilot 方法的自动指标 |
| `reports/experiments/pilot_human_metrics.json` | 用户确认后的 pilot 语义评分与评审状态 |
| `reports/experiments/pilot_human_metrics_preliminary.json` | 确认前的指标快照，仅用于审计 |
| `reports/human_scoring_pilot_confirmed.csv` | 当前正式使用的 160 行用户确认评分 |
| `reports/technical_enhancement_decision.md` | `qwen3-vl` 初始 No-Go、`qwen3:4b` Generator Go 与 Planner No-Go |
| `reports/llm_probe_qwen3_4b.json` | 60 次正式结构化与语义探针明细 |
| `data/evaluation/extension_holdout_manifest.json` | extension 题集、评分合同哈希与执行锁 |
| `reports/extension_holdout_freeze.md` | extension 冻结范围、方法和人工评分披露 |
| `data/evaluation/extension_implementation_manifest.json` | 实现、Prompt、Schema、依赖、输入与模型 digest |
| `data/evaluation/extension_holdout_release.json` | 历史 v1 一次性授权和固定输出路径 |
| `data/evaluation/extension_release_revocations/extension-qwen3-4b-v1-bdedf7dc.json` | v1 执行前撤销事实与历史文件哈希 |
| `config/extension_evaluation_v2.yaml` | v2 四方法、评分与盲评合同 |
| `config/extension_trace_contract_v2.yaml` | v2 Claim 与分阶段 trace 合同 |
| `src/llm/ollama_client.py` | 统一 Client 的正式 content、一次重试和脱敏调用记录合同 |
| `reports/llm_generator_dev_audit.md` | 三轮 dev 调试结果、修复轨迹与已知限制 |
| `reports/evaluation_llm_generator_dev_candidate.json` | 当前 LLM Generator 候选 dev 自动结果 |
| `src/agent/generators/evidence_packer.py` | Stage 8.1 确定性证据选择、题型配额和字符预算实现 |
| `scripts/validate_evidence_packer.py` | dev/pilot 50 题只读 Packer 合同检查 |
| `reports/random_forest_over_refusal_diagnosis.md` | Packer 后随机森林真实 smoke 与剩余过度拒答证据 |
| `config/atomic_claim_prompt_v2.yaml` | Prompt v2、wire Schema 哈希、1～4 Claim 与探针门槛 |
| `reports/llm_atomic_claim_prompt_v2_probe.json` | 四场景 20 次脱敏合成结构探针 |
| `scripts/validate_atomic_claim_prompt.py` | Prompt/Schema 哈希、探针门槛和无原文持久化校验 |
| `src/verification/evidence_verifier.py` | Claim-level supported/retained、四状态决策、strict 对照和 reason codes |
| `scripts/validate_claim_level_verifier.py` | 合成状态机与脱敏 DEV02 smoke 合同检查 |
| `reports/claim_level_partial_pass_dev02_smoke.json` | 不含问题/答案/Claim/quote 的 DEV02 Partial-pass 工程 smoke |
| `src/agent/workflow.py` 与 `src/schemas.py` | routing/retrieval/generation/verification/retry/end-to-end 统一 trace 合同 |
| `scripts/validate_runtime_trace.py` | 非重试 1/1/1 与重试 2/2/2 调用链合同检查 |
| `scripts/smoke_streamlit_runtime.py` | model/backend/fallback/prewarm/阶段延迟与桌面/移动 UI smoke |
| `reports/streamlit_stage8_4_*_{desktop,mobile}.png` | pass/partial/refuse/fallback 工程截图，不是质量实验结果 |
| `reports/evaluation_llm_agent_v2_dev_stage8_5_candidate.json` | Stage 8.5 当前 v2 的 10 题 dev 自动指标、Claim 汇总、错误阶段和延迟 |
| `reports/llm_agent_v2_dev_stage8_5_audit.md` | 历史/initial/candidate 对比、DEV02/03/05/10 归因和 Dense No-Go 决定 |
| `config/settings.yaml` | 当前 rule Router、LLM Generator 与 offline_rule fallback 配置 |
| `config/experiments.yaml` | 方法开关、final 只读策略、生成器类型 |
| `config/settings.yaml` | Verifier 阈值、重试次数和默认后端 |

## 必须保留的事实边界

| ID | 声明要求 | 当前核验结果 |
| --- | --- | --- |
| C01 | 知识库仅包含 6 个官方页面、164 个 Section、180 个 Chunk | 已核验 |
| C02 | 图谱为 50 个实体、100 条 approved 关系，100 条关系均有 Chunk 证据 | 已核验 |
| C03 | Vector 检索使用 TF-IDF 稀疏表示，不是神经稠密 Embedding | 已核验 |
| C04 | v1.0 与冻结实验使用离线规则生成器；当前增强分支默认使用本地 LLM Generator | 已核验 |
| C05 | 当前工作流使用真实 LangGraph 1.0.10 `StateGraph` | 已核验 |
| C06 | final 与 pilot 当前使用 NetworkX；Neo4j 仅为可选适配器，未做在线服务基准 | 已核验 |
| C07 | 项目是轻量化 Knowledge-Graph-Enhanced RAG，不是完整 Microsoft GraphRAG | 已核验 |
| C08 | final 冻结集只运行一次，观察 T-DF-01 后未重新调参报告 | 已核验 |
| C09 | final 的 0.9750 是 39/40 pass/refuse 决策准确率，不是回答正确率 | 已核验 |
| C10 | final 的 0.9750 引用率只表示引用存在，不等于证据忠实度 | 已核验 |
| C11 | 无答案拒答为 4/4，但必须注明样本量小 | 已核验 |
| C12 | 1.48 ms 是本地离线规则热路径均值，不是在线 LLM 延迟 | 已核验 |
| C13 | final 唯一错误为 T-DF-01，即 AdaBoost 定义题过度拒答 | 已核验 |
| C14 | pilot 的 Proposed 决策准确率和拒答准确率均为 1.0000 | 已核验 |
| C15 | pilot 的语义分数已由用户确认，状态为 `user_confirmed`；分数初稿由 Codex 辅助生成 | 已核验 |
| C16 | 用户确认样本中的幻觉率为 0 只描述当前小样本观察，不能推出系统不会产生幻觉 | 已核验 |
| C17 | Manifest SHA-256 为 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1` | 已核验 |
| C18 | `qwen3-vl:8b` 仍为 No-Go；`qwen3:4b` 只通过 Generator 前置门槛，Planner 为 No-Go | 已核验 |
| C19 | 23 题 extension holdout 已在业务实现前冻结；v1 release 已在执行前撤销，v2 尚无 release，未生成 extension 或 enhanced 结果 | 已核验 |
| C20 | 当前 Agent 使用规则 Router、`qwen3:4b` LLM Generator、确定性 Verifier 与 `GroundedAnswerGenerator` fallback | 已核验 |
| C21 | 候选 dev 结构化输出 10/10、fallback 0/10、决策 6/10；4 个错误均为过度拒答，不能证明优于规则基线 | 已核验 |
| C22 | v1 extension 实现提交为 `bdedf7d`，runtime/Prompt/trace 哈希与模型 digest 已冻结；文件原始状态为 `authorized_not_executed`，有效状态为 `revoked_before_execution` | 已核验 |
| C23 | `intent_aware_v2` Packer 已实现确定性去重、题型配额、10,000 字符预算、可见 ID 边界和逐次 trace，且不修改原始 `RetrievalResult` | 已核验 |
| C24 | Packer 的 50 题 dev/pilot 检查是工程合同回归，不是独立效果实验；阶段 8.2 随机森林 smoke 仍拒答 | 已核验 |
| C25 | Prompt v2 限制 1～4 条原子 Claim，并冻结 Prompt/Schema 哈希；20/20 合成探针是工程门槛，不是独立回答质量结果 | 已核验 |
| C26 | Prompt v2 随机森林 smoke 的 Claim coverage 为 0.5000，但阶段 8.2 整题仍 `refuse`；不能宣称 Prompt 单独解决过度拒答 | 已核验 |
| C27 | Stage 8.3 DEV02 脱敏 smoke 为 2/4 Claim retained、2/4 removed、`partial_pass`、retry=0、generation calls=1、unsupported leakage=0 | 已核验 |
| C28 | Stage 8.3 单题 smoke 只证明过滤机制，不是整体 dev/pilot 结果、正式准确率或 LLM 优于规则的证据 | 已核验 |
| C29 | Stage 8.4 已记录 routing、全部 retrieval/generation/verification、packing、retry branch 和 end-to-end；retry 与子阶段重叠，不能再次求和 | 已核验 |
| C30 | Streamlit 四路径 browser smoke 只证明状态与布局合同；合成预热不读取评测题面，预热耗时不能当作问题端到端延迟 | 已核验 |
| C31 | Stage 8.5 dev candidate 为 9/10 自动决策、10/10 结构成功、2/2 无答案拒答、1/8 answerable over-refusal、3/10 retry、0 unsupported leakage | 已核验 |
| C32 | DEV02/03/10 为 filtered partial-pass；DEV05 因固定语料没有 AdaBoost 权重机制原文继续拒答，不能靠放宽 Verifier 硬判通过 | 已核验 |
| C33 | Stage 8.5 只是开发集工程门槛，`partial_pass` 未经独立人工正确性评估，不能证明 LLM 增强有效或优于规则基线 | 已核验 |

## 禁止出现的结论

- “问答准确率为 97.5%”或含义相同的表述。
- “引用率 97.5% 等于证据忠实度 97.5%”。
- “系统不会产生幻觉”。
- “完整实现/完整复现 Microsoft GraphRAG”。
- “在线 LLM 延迟为 1.48 ms”。
- 将用户确认语义评分写成独立双人标注或统计显著性结论。
- 声称当前正式检索使用 sentence-transformers 或神经 Dense Embedding。
- 声称完成了 Neo4j 在线性能基准。
- 在技术增强尚未完成和独立评测前宣称增强有效。
- 将 thinking 字段中的 JSON 当作已经通过正式 `AnswerPayload` 输出合同。
- 将 `qwen3:4b` 的探针成功描述为已经接入 Agent 主链路或完成 enhanced 实验。
- 将统一 Client 的合成 smoke 成功描述为已经完成 LLM Answer Generator、fallback 或 Agent 主链路接线。
- 将 dev 调试结果描述为独立保留集结果、统计显著结论或 LLM 已优于规则基线。
- 将历史文件中的 `authorized_not_executed` 误写为当前有效执行授权，或在 execution receipt 出现前描述为已完成 extension 实验。
- 将 Evidence Packer 的 dev/pilot 合同检查描述为回答质量提升实验，或声称它已经解决过度拒答。
- 将 Prompt v2 的 20/20 合成探针描述为 LLM 优于规则基线、正式答案准确率或 extension 结果。
- 声称 Prompt v2 单独解决了过度拒答；阶段 8.2 的 strict smoke 仍拒答。
- 将 Stage 8.3 单题 DEV02 Partial-pass smoke 描述为总体过度拒答已解决、正式准确率提升或 LLM 优于规则基线。
- 将 `partial_pass` 状态自动等同于人工正确答案。
- 将 Stage 8.4 截图或 browser smoke 描述为回答正确率、LLM 增强有效性或 extension 结果。
- 把 Streamlit 启动预热耗时与单题 generation/end-to-end 混为同一指标，或把 retry latency 与其子阶段重复相加。
- 将 Stage 8.5 的 9/10 dev 自动决策描述为独立保留集、正式回答正确率、统计显著结果或 LLM 优于规则基线。
- 将 4 个 `partial_pass` 自动视为 4 道人工正确答案，或声称 DEV05 已经被修复。

## 发布前检查

```bash
python scripts/validate_report_claims.py
python scripts/validate_evidence_packer.py
python scripts/validate_atomic_claim_prompt.py
python scripts/validate_claim_level_verifier.py
python scripts/validate_scoring.py
python scripts/validate_extension_holdout.py
python scripts/freeze_baseline.py --verify
```

自动校验只能拦截已知高风险措辞和数值漂移。每次新增结果、图表或摘要结论后，仍需人工逐项核对本清单。
