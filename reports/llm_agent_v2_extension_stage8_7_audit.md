# LLM Agent v2 Stage 8.7 Extension 一次性实验审计

## 1. 审计边界

Stage 8.7 只执行冻结的 23 题 extension 四方法实验、校验不可变产物并生成匿名盲评表。没有重跑 final 或 pilot，没有修改 Prompt、Schema、Router、Retriever、Evidence Packer、Verifier、语料、图谱、阈值或模型配置，也没有根据 extension 逐题结果继续调参。

冻结身份：

| 项目 | 值 |
| --- | --- |
| Release ID | `extension-qwen3-4b-v2-e207cb91` |
| Implementation commit | `e207cb9142ff0066bae58501185b157998abe68f` |
| Runtime bundle SHA-256 | `ae639c6a51bdb65c3cd291db865485ffa8eb22ffcc0dd2c443e339cd0e00e44b` |
| Dataset SHA-256 | `7b2b2e76ecdd690574fd0c8220bee7edf20a326bcd2ff8e401659f4acc15e3a5` |
| Model | Ollama `qwen3:4b` |
| Model digest | `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7` |

v1 release 继续保持 `revoked_before_execution`，没有被执行。v2 release record 的原始状态字段按不可变合同保留为 `authorized_not_executed`；完成后的有效状态由 state 和 receipt 共同确定为 `completed_once`。

## 2. 一次性执行

唯一一次受控命令：

```bash
python scripts/run_extension_evaluation_v2.py --execute-once --release-id extension-qwen3-4b-v2-e207cb91 --confirm-one-time-run
```

执行记录：

| 项目 | 结果 |
| --- | ---: |
| State status | `completed` |
| Effective status | `completed_once` |
| Questions per method | 23 |
| Frozen methods | 4 |
| QA invocations | 92 |
| Started at | `2026-07-24T03:20:44.032420+00:00` |
| Completed at | `2026-07-24T03:30:28.346020+00:00` |

执行完成后不再调用 runner。任何后续分析只读取现有结果文件。

## 3. 自动指标

这里的 Decision Accuracy 只检查 answerable 题是否返回 `pass/partial_pass`、no-answer 题是否返回 `refuse`。它不判断答案是否覆盖 required aspects，也不等于人工回答正确性。

| 方法 | Decision Accuracy | Refusal Accuracy | Answerable Over-refusal | Unsupported Leakage | Mean E2E |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rule Baseline | 21/23 (0.9130) | 2/4 (0.5000) | 0/19 (0.0000) | 0/1 (0.0000) | 5.46 ms |
| LLM Strict v2 | 7/23 (0.3043) | 4/4 (1.0000) | 16/19 (0.8421) | 0/24 (0.0000) | 11891.29 ms |
| LLM No Verifier v2 | 19/23 (0.8261) | 0/4 (0.0000) | 0/19 (0.0000) | 25/25 (1.0000) | 5207.65 ms |
| LLM Partial-pass v2 | 16/23 (0.6957) | 2/4 (0.5000) | 5/19 (0.2632) | 0/27 (0.0000) | 7607.35 ms |

三个 LLM 方法的结构化输出成功均为 22/23，fallback 均为 0/23。Partial-pass 在 19 道可回答题中产生 12 个 `partial_pass`，支持 Claim 保留率为 23/23，未支持 Claim 泄漏为 0/27。

## 4. 可支持的自动结论

1. Claim-level Partial-pass 相比 LLM Strict v2 明显减少自动过度拒答：`16/19` 降至 `5/19`。
2. Partial-pass 在本轮自动审计中保留全部已判支持 Claim，且没有将已判不支持 Claim 暴露给用户。
3. 关闭 Verifier 后，四道 no-answer 题全部被接受，25 条已判不支持 Claim 全部泄漏，说明 Verifier 对边界控制有直接作用。
4. Partial-pass 没有在自动决策准确率上超过 Rule Baseline，并且仍有 5 道可回答题拒答和 2 道 no-answer 题误接受。
5. LLM 生成是主要延迟来源；本轮三个 LLM 方法平均端到端耗时约 5.21 至 11.89 秒，规则方法约 5.46 毫秒。

不能据此声明：LLM 答案已经优于规则答案、Partial-pass 的 14 个 `partial_pass` 都人工正确、citation validity 等于 Evidence Faithfulness，或结果具有统计显著性。

## 5. 错误边界

LLM Partial-pass v2 的自动错误：

- over-refusal：`X-SH-03`、`X-CM-01`、`X-PC-03`、`X-MS-01`、`X-MS-02`；
- false accept：`X-NA-03`、`X-NA-04`，均返回 `partial_pass`。

对照现象：

- Rule Baseline 的两个错误同样是 `X-NA-03`、`X-NA-04` false accept；
- LLM Strict v2 正确拒绝 4/4 no-answer，但拒绝了 16/19 可回答题；
- LLM No Verifier v2 接受全部 23 题，包括全部 4 道 no-answer。

这些结果只进入误差分析。冻结 runtime 不得因这些 holdout 观察被修改。

## 6. 匿名盲评状态

`blind_review.csv` 包含 92 行，每题恰有 A/B/C/D 四个随机标签；可见字段不包含 `method_id`、expected behavior、required aspects 或 forbidden claims。`blind_method_key.json` 单独保存映射。

人工评分状态为 `pending_user_confirmed_single_review`。Answer Correctness、Evidence Faithfulness、Hallucination、Over-refusal 和 Readability 尚无人工结果，不得填造或提前汇总。Stage 8.8 必须先完成可见盲评表，再使用 method key 解盲。

用户随后明确授权 Codex 进行辅助初评。初评严格只读取匿名 `blind_review.csv` 和其中展示的题目/证据，没有读取 method key 或 expected-answer 字段。92 行初评分数、理由、哈希和审核量表保存在：

```text
reports/extension_v2/blind_review_codex_preliminary_scores.csv
reports/extension_v2/blind_review_codex_preliminary.csv
reports/extension_v2/blind_review_codex_preliminary.md
reports/extension_v2/blind_review_codex_preliminary_manifest.json
reports/extension_v2/blind_review_rubric.md
```

初评分数状态为 `preliminary_pending_user_confirmation`，不能视为用户确认的人工结果。用户可修改紧凑 score map 后重新生成和校验匿名输出；确认前不解盲、不按方法汇总、不更新正式报告指标。

## 7. 不可变产物

| 产物 | SHA-256 |
| --- | --- |
| Execution state | `f433dfc6b6fa8d1eb52f15c40621bc2a3c506694eafc5e5a617b4ad0aad9707c` |
| Rule Baseline report | `9d8943c0ba7f10b9ee0af8efc4c3481bb45e728980264214ba6d0e7010377af5` |
| LLM Strict v2 report | `88606acde5785aa4760d9b6074c37de653a5d2a03fa34a9ada0d602eff3c820f` |
| LLM No Verifier v2 report | `89e75a6531c86708add51dfdaf32f6839d7bf3d2c92b4b5034f89f7aeb2f10f6` |
| LLM Partial-pass v2 report | `7c9c2c701382762dc5c645e3da7b5109cdf64d3978cfad89baaca0b7abeb6469` |
| Combined metrics | `543b923f23886df9485d7f0c6ec07aece196d8e3d7ca783c974583789b6e5fc2` |
| Blind review CSV | `5e8ce394a76dd0ca4e2fd91decf80191f625c7024ea1dc3073301c0ab70a189e` |
| Blind method key | `fdbf33cd26bdd21f22981cdbb7be2c4c0fc3efd9945f88d60a10672e7e1bc0ec` |

Receipt 同时绑定上述路径与哈希。`validate_extension_results_v2.py` 会重新计算四方法指标、核对 state/receipt/输出哈希、检查 23 题顺序和 92 行盲评匿名性，并拒绝持久化 raw prompt 或 thinking 字段。

## 8. 阶段结论

Stage 8.7 的一次性自动实验与结果审计已完成。下一阶段仅进入 Stage 8.8 人工盲评、解盲汇总、图表和最终报告；不得重跑 extension，不得根据本轮结果调整冻结实现，也不得在人工评分完成前声称 LLM 改善了回答正确性、证据忠实度或可读性。
