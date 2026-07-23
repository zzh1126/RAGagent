# Extension Holdout 冻结记录

## 冻结结论

`extension` 扩展保留集已在 LLM Client、LLM Answer Generator 和业务 Prompt 实现前冻结。实现、Prompt、trace 口径与模型 digest 随后冻结在独立提交上，并已创建一次性 release record。当前有效状态为 `authorized_not_executed`：允许执行 preflight，但尚未运行任何 extension QA 工作流，也没有 extension 答案或指标。

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
| release 状态 | `authorized_not_executed` |

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

冻结比较方法：

1. Rule Baseline：规则 Router + 离线规则 Generator + Verifier；
2. LLM Generator：规则 Router + LLM Generator + Verifier；
3. LLM Generator No Verifier：规则 Router + LLM Generator，不使用 Verifier。

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

## 可执行校验

```bash
python scripts/validate_evaluation.py
python scripts/validate_extension_holdout.py
python scripts/validate_extension_release.py --check-runtime-model --require-unexecuted
python scripts/run_extension_evaluation.py --preflight
```

`scripts/run_evaluation.py --split final` 和 `--split extension` 均会主动拒绝执行。extension 只能由 `scripts/run_extension_evaluation.py` 使用精确 release ID 和 `--confirm-one-time-run` 执行一次；任何已有 state、receipt 或输出都会阻止第二次运行。当前只完成 preflight，未执行正式命令。
