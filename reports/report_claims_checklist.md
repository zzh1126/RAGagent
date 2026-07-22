# 科研报告事实声明检查清单

## 使用范围

本清单约束 `reports/research_report_draft.md` 中容易被误述的范围、指标和实验状态。当前基线仍为 `v1.0-baseline`，开发分支为 `experiment/llm-agent-v2`；pilot 语义评分已经由用户确认，LLM Generator 仅通过前置门槛，extension 仍处于锁定未运行状态。

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
| `src/llm/ollama_client.py` | 统一 Client 的正式 content、一次重试和脱敏调用记录合同 |
| `config/settings.yaml` | 当前 LLM 参数及 rule/offline_rule 主链路开关 |
| `config/experiments.yaml` | 方法开关、final 只读策略、生成器类型 |
| `config/settings.yaml` | Verifier 阈值、重试次数和默认后端 |

## 必须保留的事实边界

| ID | 声明要求 | 当前核验结果 |
| --- | --- | --- |
| C01 | 知识库仅包含 6 个官方页面、164 个 Section、180 个 Chunk | 已核验 |
| C02 | 图谱为 50 个实体、100 条 approved 关系，100 条关系均有 Chunk 证据 | 已核验 |
| C03 | Vector 检索使用 TF-IDF 稀疏表示，不是神经稠密 Embedding | 已核验 |
| C04 | 当前生成器为离线规则/模板，不调用生产 LLM API | 已核验 |
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
| C19 | 23 题 extension holdout 已在业务实现前冻结并锁定，尚未生成任何 extension 或 enhanced 结果 | 已核验 |
| C20 | 统一 Schema 与 LLM Client 已完成，但当前 Agent 仍使用规则 Router 和 `GroundedAnswerGenerator`，不能据此声称 LLM 已进入主链路 | 已核验 |

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

## 发布前检查

```bash
python scripts/validate_report_claims.py
python scripts/validate_scoring.py
python scripts/validate_extension_holdout.py
python scripts/freeze_baseline.py --verify
```

自动校验只能拦截已知高风险措辞和数值漂移。每次新增结果、图表或摘要结论后，仍需人工逐项核对本清单。
