# Extension Holdout 冻结记录

## 冻结结论

`extension` 扩展保留集已在 LLM Client、LLM Answer Generator 和业务 Prompt 实现前冻结。v1 实现、Prompt、trace 口径与模型 digest 随后冻结在独立提交上，并创建了一次性 release record。该 release 在任何 extension QA 执行前被不可变撤销，当前有效状态为 `revoked_before_execution`。v2 四方法评分与 trace 合同已经冻结，但尚无 v2 release；因此仍没有 extension 答案或指标。

## 冻结范围

| 项目 | 值 |
| --- | --- |
| 基线提交 | `9e2c34f9d6fa2824d73d62c0b448f7520a8363b2` |
| 题目数 | 23 |
| 可回答题 | 19 |
| 无答案题 | 4 |
| 题集文件 | `data/evaluation/extension_questions.jsonl` |
| 评分合同 | `config/extension_evaluation.yaml` |
| 冻结 manifest | `data/evaluation/extension_holdout_manifest.json` |
| 实现提交 | `bdedf7dcb4e82bc918dfd7c92161501151b09742` |
| release ID | `extension-qwen3-4b-v1-bdedf7dc` |
| release 文件原始状态 | `authorized_not_executed`，仅作历史记录 |
| release 当前有效状态 | `revoked_before_execution` |
| 撤销提交 | `a518404` |
| v2 release 状态 | `locked_no_release` |

题型分布：

| 题型 | 数量 |
| --- | ---: |
| single_hop | 4 |
| multi_hop | 4 |
| definition | 3 |
| comparison | 3 |
| principle_pros_cons | 3 |
| metric_selection | 2 |
| no_answer | 4 |

四类无答案题分别覆盖完全超域、机器学习但不在六页知识库、实体存在但属性不存在、错误任务前提。

## 方法与指标合同

v1 历史合同冻结了三个比较方法：

1. Rule Baseline：规则 Router + 离线规则 Generator + Verifier；
2. LLM Generator：规则 Router + LLM Generator + Verifier；
3. LLM Generator No Verifier：规则 Router + LLM Generator，不使用 Verifier。

v2 合同在任何 extension 输出出现前改为四个方法：

1. `rule_baseline`；
2. `llm_strict_v2`；
3. `llm_no_verifier_v2`；
4. `llm_partial_pass_v2`。

v2 同时预先固定 `PARTIAL_PASS` 语义、逐 Claim 保留/删除 trace、分阶段延迟、四答案盲评标签和描述性比较口径。业务实现尚未完成，这些合同不等于实验已经执行。

LLM Query Planner 未通过前置语义门槛，因此本保留集不报告 Route Accuracy，也不将 Full LLM Agent 纳入当前比较。

人工评分合同在看到输出前固定：Answer Correctness 0/1/2、Evidence Faithfulness 0/1/2、Hallucination 0/1、Over-refusal 0/1、Readability 1～5。方法标签应隐藏，答案顺序应随机；当前计划仍是用户确认的单一复核流程，不声称独立双人标注。

## 防泄漏检查

- 与 dev、demo、pilot、final 的完全相同题面重合：0；
- 归一化文本最高相似度：0.7097；
- 近重复阈值：0.82；
- 最近题对：`X-SH-03` / `T-SH-05`；
- 题目设计时可查看冻结图谱 Schema 和历史题面，但未查看任何 extension 生成答案；因此应准确称为“实现前冻结保留集”，不描述为外部独立盲测集。

## 文件指纹

| 文件或内容 | SHA-256 |
| --- | --- |
| `extension_questions.jsonl` | `7b2b2e76ecdd690574fd0c8220bee7edf20a326bcd2ff8e401659f4acc15e3a5` |
| `extension_evaluation.yaml` | `a9415d4efc8b3e79bd65d6df84488364761695860bf53d04861e3e4148060b65` |
| 题目 ID + 归一化题面指纹 | `1dfbf35117b5a22e28bcee8f27b3cdd1cf86e7542c76122c583ef6780217fc28` |
| Runtime bundle | `b4676d37dc9f2babde6ade4f1a3d212ed775d590adf202e3cef710cadbbe03f0` |
| Prompt v1 | `f4af2d9668b8ba53cb8f884ff840e4ce282d55d15e4468039b039ff3a0e5c60e` |
| LLM wire Schema | `291e0ed4ccc600aed1043e745d64b9479db518a1f458beae00046a0c5ea7c932` |
| Trace contract | `f68cde4cae30845e1b04a98f27c6d95dd08a8af4d2edf4f32b615b25da08185d` |
| `qwen3:4b` 模型 digest | `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7` |
| v1 release record | `af4f8ac10c247483af20e93f5fdde5220b608fb8c9dfb8c031d777d8b1932d0c` |
| v1 revocation record | `29b198d5fa9309ce4d81919271df424cb87db29c40370bd0fc6e42bc091aa45b` |
| v2 scoring contract | `864c960f6f357ce528384408441ca189e571206b5d6a904d44f7992b4b034ac1` |
| v2 trace contract | `3b447885c08dbad3b6366670c5e7b09fc4f639570c912f994b7020f5b9d94ef5` |

## 可执行校验

```bash
python scripts/validate_evaluation.py
python scripts/validate_extension_holdout.py
python scripts/validate_extension_release.py --check-runtime-model --require-unexecuted
```

`scripts/run_evaluation.py --split final` 和 `--split extension` 均会主动拒绝执行。专用 runner 也会拒绝历史 v1 release ID；任意伪 v2 release ID 会因 `extension_holdout_release_v2.json` 不存在而失败。只有后续业务实现冻结、测试通过并单独创建 v2 release 后，专用 runner 才能被升级为允许一次正式执行。当前没有读取或运行 extension 问题。
