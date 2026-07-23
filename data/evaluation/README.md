# 评测数据说明

本目录将调试题、演示题、已用于修复的先导题和最终保留测试题明确分开。

## 数据集

- `dev_questions.jsonl`：10 题，仅用于路由、阈值和回答模板调试。
- `demo_questions.jsonl`：8 题，可与开发集重合，用于 Streamlit 演示。
- `pilot_questions.jsonl`：40 题，曾用于发现并修复两处实现缺口，不能再视为无泄漏最终结果。
- `final_questions.jsonl`：重新创建的 40 题保留测试集，与开发集和先导集题面不重合；冻结后只运行一次。
- `extension_questions.jsonl`：在 LLM Client 与 Generator 业务实现前冻结的 23 题扩展保留集；实现和一次性 release 已冻结，但当前尚未运行，仍禁止用于调参。

最终 40 题固定分布：

| category | count |
| --- | ---: |
| `single_hop` | 8 |
| `multi_hop` | 9 |
| `definition` | 7 |
| `comparison` | 5 |
| `principle_pros_cons` | 5 |
| `metric_selection` | 2 |
| `no_answer` | 4 |

扩展保留集固定分布：

| category | count |
| --- | ---: |
| `single_hop` | 4 |
| `multi_hop` | 4 |
| `definition` | 3 |
| `comparison` | 3 |
| `principle_pros_cons` | 3 |
| `metric_selection` | 2 |
| `no_answer` | 4 |

## 字段

- `question_id`：题目唯一标识。
- `split`：`dev`、`demo`、`pilot`、`final` 或 `extension`。
- `category`：题型。
- `question`：中文问题。
- `expected_behavior`：`answer` 或 `refuse`。
- `gold_entities`：预期涉及的实体 ID。
- `gold_relations`：预期涉及的关系类型。
- `expected_keywords`：答案内容覆盖检查用关键词。
- `notes`：题目设计说明。

扩展保留集还冻结：

- `expected_route`：规则 Router 的预期检索模式，不作为 Planner 指标；
- `required_aspects`：人工正确性评分必须覆盖的回答维度；
- `forbidden_claims`：不得出现的错误或越界事实；
- `config/extension_evaluation.yaml`：方法矩阵、指标分母、盲评协议和执行锁；
- `config/extension_trace_contract.yaml`：完整 generation trace、冷/热延迟和一次性执行口径；
- `extension_holdout_manifest.json`：题集与评分合同 SHA-256。
- `extension_implementation_manifest.json`：实现、Prompt、Schema、依赖、输入和模型 digest；
- `extension_holdout_release.json`：绑定实现提交的一次性执行授权。

运行校验和评测：

```bash
python scripts/validate_evaluation.py
python scripts/validate_extension_holdout.py
python scripts/validate_extension_release.py --check-runtime-model --require-unexecuted
python scripts/run_extension_evaluation.py --preflight
python scripts/run_evaluation.py --split dev
```

`run_evaluation.py` 始终拒绝 `final` 和 `extension`。final 复用冻结结果；extension 只能通过专用 runner、精确 release ID 和显式一次性确认执行。当前 release 状态为 `authorized_not_executed`，preflight 不会把 extension 问题发送给 QA 工作流。
