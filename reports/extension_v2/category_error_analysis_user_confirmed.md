# v2 Extension 类别与典型错误分析（用户确认版）

## 1. 分析边界

- Release：`extension-qwen3-4b-v2-e207cb91`；
- 数据规模：23 道题、4 种方法、92 条匿名答案；
- 评分状态：`user_confirmed`；评分由 Codex 辅助初评后经用户逐行审核确认，不是独立双人标注；
- 解盲顺序：评分确认后才读取 method key；
- 数据来源：`combined_metrics_user_confirmed.json` 与 `blind_review_unblinded_user_confirmed.csv`；
- 本文只做描述性误差分析，不进行显著性检验，也不据此重跑 extension 或修改冻结 runtime。

Correctness 使用 0/1/2 分并归一化到 0-1。Faithfulness、Hallucination 和 Readability 排除拒答，因此不同方法的有效分母不同。题型样本数很小，尤其 Metric selection 只有 2 题，类别差异只能作为定位线索。

## 2. 分题型 Correctness

| 方法 | 单跳 n=4 | 多跳 n=4 | 定义 n=3 | 对比 n=3 | 原理/优缺点 n=3 | 指标选择 n=2 | 无答案 n=4 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Rule Baseline | 0.7500 | 0.5000 | 0.8333 | 0.3333 | 0.5000 | 0.2500 | 0.7500 |
| LLM Strict v2 | 0.5000 | 0.0000 | 0.3333 | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| LLM No Verifier v2 | 1.0000 | 0.8750 | 1.0000 | 1.0000 | 0.6667 | 0.5000 | 0.3750 |
| LLM Partial-pass v2 | 0.6250 | 0.5000 | 0.8333 | 0.5000 | 0.1667 | 0.0000 | 0.7500 |

图表：`reports/figures/extension_v2/extension_category_correctness.png`。表中数值由 92 行用户确认评分重新聚合，并由 `generate_extension_figures.py --check` 校验输入哈希和输出哈希。

## 3. 主要观察

1. **定义题相对稳定。** Rule 与 Partial-pass 均为 0.8333，No Verifier 为 1.0000。`X-DF-02` 的主要问题不是事实错误，而是 Rule 只隐含说明关注点、Partial-pass 遗漏完整定义。
2. **多跳题的主要损失是答案不完整。** Rule 和 Partial-pass 均为 0.5000；`X-MH-01` 至 `X-MH-04` 多次只覆盖链条的一段或只回答两个要求中的一个。No Verifier 达到 0.8750，但 `X-MH-03`、`X-MH-04` 含超出直接证据的表述。
3. **指标选择是安全方法的共同短板。** Rule 为 0.2500，Strict 与 Partial-pass 均为 0。Rule 在 `X-MS-01` 只定义指标而未给优先建议，在 `X-MS-02` 返回了无关的 precision 细节；Partial-pass 对两题均过度拒答。
4. **无答案题揭示安全与覆盖的直接冲突。** Strict 为 1.0000，但其整体有 16/19 过度拒答；No Verifier 仅为 0.3750，4 道无答案题均未自动拒答，并在 `X-NA-02` 给出语料外实质回答。Rule 与 Partial-pass 均为 0.7500，但 `X-NA-03`、`X-NA-04` 没有清晰否定缺失属性或错误前提。
5. **Partial-pass 消除了已观察到的 unsupported Claim 泄漏，但没有自动保证完整性。** 它有 0/16 观察 hallucination，却在原理/优缺点题上仅为 0.1667，在 5 道可回答题上过度拒答，整体 Correctness 0.5217 仍低于 Rule 的 0.5870。

## 4. 按方法归纳的典型错误

| 方法 | 典型错误 | 代表题 | 用户确认依据 | 后续改进方向 |
| --- | --- | --- | --- | --- |
| Rule Baseline | 返回相关事实但没有执行题目要求 | `X-CM-01`、`X-MS-02`、`X-SH-04` | 分别遗漏比较、返回无关 precision 细节、给出无关定义 | 增加“问题动作 + 目标属性”对齐，生成前检查回答是否覆盖请求关系 |
| Rule Baseline | 多跳或双要求只覆盖一部分 | `X-MH-01` 至 `X-MH-04`、`X-PC-01` 至 `X-PC-03` | 常只保留第一段路径、任务事实或单个局限 | 为多目标题建立 required-aspect 覆盖检查 |
| LLM Strict v2 | 支持 Claim 存在时仍整题拒答 | 16 道可回答题 | 用户确认 over-refusal 为 16/19，仅 3 条实质答案进入 Faithfulness/Readability | 保留 Strict 作为安全上界对照，不作为默认覆盖方案 |
| LLM No Verifier v2 | 将合理推断或常识写成无直接证据结论 | `X-MH-03`、`X-MH-04`、`X-PC-01`、`X-PC-02` | 4 条答案含超出直接证据的机制、噪声或指标表述 | 继续保留 Claim-level Verifier，不采用无验证默认链路 |
| LLM No Verifier v2 | 对边界题强行作答 | `X-MS-01`、`X-NA-02` | 给出错误优先级；对语料外问题输出实质答案 | 增加属性存在性和知识库范围检查 |
| LLM Partial-pass v2 | 删除不支持 Claim 后只剩不完整答案 | `X-MH-01` 至 `X-MH-04`、`X-CM-03`、`X-SH-04` | 保留内容忠实，但遗漏第二跳、F1 或特征采样 | 在新开发集上研究逐 aspect 召回和逐 aspect Claim 生成 |
| LLM Partial-pass v2 | 证据判定过严导致完全拒答 | `X-SH-03`、`X-CM-01`、`X-PC-03`、`X-MS-01`、`X-MS-02` | 5 道可回答题被用户确认标为 over-refusal | 区分“无支持”与“支持但不完整”，只在前者拒答 |
| LLM Partial-pass v2 | 错误前提未被显式否定 | `X-NA-03`、`X-NA-04` | 提示证据不足或给相关事实，但未清楚拒绝前提 | 增加 premise validation 与明确纠错模板 |

No Verifier 的 6/22 Hallucination 来自 `X-MH-03`、`X-MH-04`、`X-PC-01`、`X-PC-02`、`X-MS-01` 和 `X-NA-02` 六条实质答案。这里的 6 表示被标记含不受支持专业事实的答案数，不是 Claim 总数。

## 5. 后续优先级

以下改进只用于未来版本，不回写或重跑本次 extension：

1. 在新开发集上加入 required-aspect 覆盖检查，优先解决多跳、对比、原理题的“有依据但不完整”；
2. 增加属性存在性与错误前提验证，让 `X-NA-03`、`X-NA-04` 类问题明确纠错，而不是只给相关事实；
3. 为指标选择题强化“指标定义 + 任务场景 + 选择建议”三类证据配额；
4. 将 Verifier 输出区分为无支持、部分支持和完整支持，并保留逐 Claim reason code 供误差定位；
5. 扩大冻结题集并采用独立双人评分，报告一致性和置信区间后再判断类别差异是否稳定。

## 6. 答辩可用结论

- No Verifier 的 Correctness 最高，但出现 6/22 观察 hallucination，说明可读、完整的生成不等于证据安全；
- Strict 将观察 hallucination 保持为 0/3，却过度拒答 16/19，说明整题级严格验证牺牲了覆盖率；
- Partial-pass 把过度拒答降至 5/19 并保持 0/16 观察 hallucination，但 Correctness 仍未超过 Rule，因此本项目的有效结论是“改善安全与覆盖的折中”，不是“全面优于规则基线”。
