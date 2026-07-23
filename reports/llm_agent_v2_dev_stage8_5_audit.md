# LLM Agent v2 Stage 8.5 Dev 调试与误差审计

## 1. 审计边界

本阶段只读取 10 道 `dev_questions.jsonl`，并使用合成测试和单元测试验证修正边界。没有运行 pilot、final 或 extension，没有创建 v2 release，也没有修改 Prompt v2、LLM wire Schema、Evidence Packer 配置或知识库。

本报告属于开发集工程审计，不是独立保留集结果，不证明 LLM 优于规则基线，也不把 `partial_pass` 自动等同于人工正确答案。

关键产物：

```text
reports/evaluation_llm_agent_v2_dev_stage8_5_initial.json
reports/evaluation_llm_agent_v2_dev_stage8_5_candidate.json
```

候选运行使用：

| 项目 | 值 |
| --- | --- |
| Router | rule |
| Generator | Ollama `qwen3:4b` |
| Prompt | v2，冻结哈希未修改 |
| Evidence Packer | `intent_aware_v2` |
| Verifier | Claim-level `partial_pass` |
| 图后端 | NetworkX |
| dev 题集 SHA-256 | `7db6c94473797ee63c03b16c9daaad2936118780277bd97bbc3906cff32533e3` |
| settings SHA-256 | `715d2a50414f84b39c6b3475ec9e138c16212b9d6bdce97b760fccabfe7ea651` |

## 2. 新增评测口径

`scripts/run_evaluation.py` 现在记录并汇总：

- answerable/no-answer 数量；
- over-refusal、false accept 和 refusal accuracy；
- `pass / partial_pass / refuse` 分布；
- retry 题数、retry rate 和总 retry 次数；
- structured output 的 `success / failed / not_called`；
- generated/supported/retained/removed Claim 数量与比例；
- 用户可见 unsupported Claim 泄漏数；
- Verifier reason codes、Claim reason codes、Packer coverage gaps；
- generation/retrieval/packing/verification 阶段审计标记；
- routing、retrieval、packing、generation、verification、retry 和 end-to-end 延迟。

`not_called` 不再被误算为 Schema 失败。`retry_latency_ms` 是与补检索、第二次生成和第二次验证重叠的墙钟时间，不能和这些子阶段再次相加。

## 3. 三个开发基线对比

| 指标 | 历史候选 | Stage 8.5 initial | Stage 8.5 candidate |
| --- | ---: | ---: | ---: |
| Decision Accuracy | 0.6000 | 0.8000 | 0.9000 |
| Structured Output Success | 1.0000 | 1.0000 | 1.0000 |
| Fallback Rate | 0.0000 | 0.0000 | 0.0000 |
| Answerable Over-refusal | 4/8 | 2/8 | 1/8 |
| No-answer Refusal Accuracy | 2/2 | 2/2 | 2/2 |
| Retry Rate | 7/10 | 4/10 | 3/10 |
| Partial-pass 数 | 0 | 3 | 4 |
| Mean End-to-end | 11437.7 ms | 9966.31 ms | 9420.28 ms |

历史候选来自 `evaluation_llm_generator_dev_candidate.json`，使用整题严格决策。Stage 8.5 两次运行使用 Claim-level Partial-pass；initial 在 Verifier 文本归一化修正前运行，candidate 在修正后运行。由于本地生成输出可能存在细微变化，延迟和 Claim 数只做描述性比较，不作为单一修正的因果证明。

候选 Claim 汇总：

| 指标 | 结果 |
| --- | ---: |
| Generated Claims | 19 |
| Supported Claims | 9 |
| Retained Claims | 9 |
| Removed Claims | 10 |
| Claim Support Rate | 0.4737 |
| Claim Retention Rate | 0.4737 |
| Unsupported Claim Leakage | 0 |

候选决策分布为 `pass=3`、`partial_pass=4`、`refuse=3`。其中两个 `refuse` 是应拒答题，唯一 answerable over-refusal 是 DEV05。

## 4. 四个历史错误样例

| 题目 | 历史候选 | Stage 8.5 candidate | 归因与处理 |
| --- | --- | --- | --- |
| DEV02 随机森林降低方差 | refuse | partial-pass，保留 1/3，retry=0 | 检索和 Packer 覆盖充分；Partial-pass 保留直接支持内容并删除两条术语不足 Claim |
| DEV03 不平衡类别下 Balanced Accuracy/F1 | refuse | partial-pass，保留 2/3，retry=0 | 两个 gold 实体均召回；保留有直接证据部分，对缺少完整比较依据的部分披露证据不足 |
| DEV05 Bagging/AdaBoost 机制对比 | refuse | refuse，保留 0/2，retry=1 | Bagging 证据充分，但 180 个 Chunk 中只有两处 AdaBoost 提及，均不包含“调整错分样本权重”的直接机制原文；不放宽 Verifier 硬判通过 |
| DEV10 决策树过拟合 | refuse | partial-pass，保留 1/3，retry=0 | 正确 Chunk 已进入 top-k；原误杀来自 `Decision-tree`/`Decision tree`、Unicode 连字符和 `overfit`/`do not generalize` 词形差异 |

### DEV10 的低风险修正

Verifier 只增加文本规范化和保守术语别名：

- quote 比较统一大小写；
- ASCII/Unicode 连字符统一为空格；
- 弯引号统一为普通引号；
- `overfit`、`do not generalize` 等官方文档中的直接等价表述可支持“过拟合”。

正向测试允许：

```text
Decision-tree -> Decision tree
over-complex -> over complex
do not generalize -> 过拟合语义支撑
```

负向测试仍拒绝实质改变原文的 quote，例如把原文改成“always generalize perfectly”。该修正没有放宽未知 E/P/R ID、证据相关性、错误前提或不在原文中的专业机制。

## 5. Stage 8.5 门槛

| 工程门槛 | 目标 | 候选结果 | 状态 |
| --- | ---: | ---: | --- |
| Structured Output Success | >= 0.95 | 1.0000 | PASS |
| No-answer Refusal Accuracy | 2/2 | 2/2 | PASS |
| Answerable Over-refusal | <= 2/8 | 1/8 | PASS |
| Unsupported Claim Leakage | 0 | 0 | PASS |
| Retry Rate | < 7/10 | 3/10 | PASS |
| Fallback/error trace | 可追踪 | reason/stage/trace 均落盘 | PASS |

这些是进入 pilot 冻结前回归的工程门槛，不是最终科研结论。

## 6. 延迟与剩余问题

候选平均延迟：

| 阶段 | 平均耗时 |
| --- | ---: |
| Routing | 0.036 ms |
| Retrieval | 3.149 ms |
| Evidence Packing | 2.698 ms |
| LLM Generation | 9408.91 ms |
| Verification | 1.267 ms |
| Retry wall clock | 1953.367 ms |
| End-to-end | 9420.28 ms |

主要延迟仍来自本地 LLM 生成。当前不继续通过缩短证据或减少 Claim 上限来追求速度，因为这可能改变已经通过的质量门槛；后续冻结时只记录真实模型、参数和冷/热口径。

剩余限制：

- DEV05 的完整 AdaBoost 机制不在当前六页语料中；
- DEV04 虽保留 1/1 Claim，但模型主动报告额外证据缺口，因此状态为 partial-pass；
- DEV06 自动关键词覆盖为 0，但 Verifier 决策为 pass，说明字面关键词指标不能替代人工语义评分；
- 4 个 partial-pass 尚未进行独立人工正确性评估；
- dev 已用于调试，不能作为最终独立效果证据。

## 7. Dense Retrieval 决定

不触发 Dense Retrieval。唯一剩余 answerable 错误 DEV05 不是“正确 Chunk 存在但未进入 top-k”，而是当前语料没有 AdaBoost 权重更新机制原文。增加 Dense Retriever 无法补出不存在的证据，只会引入新的实验变量。

## 8. 下一阶段

阶段 8.5 完成后进入阶段 8.6：一次 pilot 冻结前回归和 v2 runtime 冻结。进入 pilot 后不根据逐题结果继续调参；仍不得运行 final/extension，且在 implementation manifest、模型 digest、依赖和 release 全部冻结前不得创建可执行 v2 extension release。
