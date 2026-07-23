# 评测数据说明

本目录将调试题、演示题、已用于修复的先导题和最终保留测试题明确分开。

## 数据集

- `dev_questions.jsonl`：10 题，仅用于路由、阈值和回答模板调试。
- `demo_questions.jsonl`：8 题，可与开发集重合，用于 Streamlit 演示。
- `pilot_questions.jsonl`：40 题，曾用于发现并修复两处实现缺口，不能再视为无泄漏最终结果。
- `final_questions.jsonl`：重新创建的 40 题保留测试集，与开发集和先导集题面不重合；冻结后只运行一次。
- `extension_questions.jsonl`：在 LLM Client 与 Generator 业务实现前冻结的 23 题扩展保留集；从未运行，v1 release 已在执行前撤销，v2 尚无 release，仍禁止读取题面用于调参或执行 QA。

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
- `extension_holdout_release.json`：保留原始状态的历史 v1 执行授权；
- `extension_release_revocations/extension-qwen3-4b-v1-bdedf7dc.json`：v1 执行前撤销记录；
- `config/extension_evaluation_v2.yaml`：v2 四方法评分与盲评合同；
- `config/extension_trace_contract_v2.yaml`：v2 Claim、分阶段延迟与一次性执行 trace 合同。
- `config/atomic_claim_prompt_v2.yaml`：Prompt v2、wire Schema 哈希和合成探针门槛，不是 extension release。
- `reports/claim_level_partial_pass_dev02_smoke.json`：脱敏 DEV02 Partial-pass 工程 smoke，不包含问题、答案、Claim 或 quote 正文。

运行校验和评测：

```bash
python scripts/validate_evaluation.py
python scripts/validate_evidence_packer.py
python scripts/validate_atomic_claim_prompt.py
python scripts/validate_claim_level_verifier.py
python scripts/validate_extension_holdout.py
python scripts/validate_extension_release.py --check-runtime-model --require-unexecuted
python scripts/run_evaluation.py --split dev
```

`run_evaluation.py` 始终拒绝 `final` 和 `extension`，并把 answerable 问题的 `pass/partial_pass` 都视为自动决策成功；final 复用冻结结果。`validate_evidence_packer.py` 只在 dev/pilot 上执行 Router、Retriever 与确定性打包合同检查；Prompt v2 的 20 次探针只使用脚本内人工合成证据，不读取任何评测题面，且不保存模型正文。Claim-level validator 使用合成数据和已使用的 DEV02 脱敏 smoke，不保存问题、答案、Claim、quote 或 thinking。v1 release 文件保留历史值 `authorized_not_executed`，但不可变 revocation record 将其有效状态改为 `revoked_before_execution`；旧授权命令在读取题集前失败。v2 合同已经冻结，但 `extension_holdout_release_v2.json` 尚不存在，因此当前没有任何可执行的 extension release。
