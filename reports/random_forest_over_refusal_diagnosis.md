# “随机森林为什么更稳定”过度拒答诊断

## 诊断信息

| 项目 | 内容 |
| --- | --- |
| 日期 | 2026-07-23 |
| 分支 | `experiment/llm-agent-v2` |
| 问题 | `随机森林为什么更稳定？` |
| 对应开发题 | `DEV02` |
| 结论 | 知识库和检索证据充足；阶段 8.3 已用 Claim-level Partial-pass 修复本题的整题拒答 |
| extension | 未运行、未读取 |

## 初始 LLM 主链路复现

```text
Intent: explanation
Mode: hybrid
Decision: refuse
Evidence score: 0.7200
Claim coverage: 0.4000
Citation validity: 0.6000
Path validity: 1.0000
Retrieval sufficiency: 1.0000
Retry count: 1
Generation calls: 2
Fallback: false
```

`retrieval_sufficiency=1.0000` 和 `path_validity=1.0000` 表明本次不是“没有检索到随机森林证据”。系统已经返回 Random Forests 官方章节的 E1、E2，以及降低方差、噪声鲁棒性和缓解过拟合的图路径。

## LLM 生成的 Claims

模型第二次生成了 5 条 Claim：

1. 随机森林通过 bootstrap 采样和随机特征选择引入双重随机性；
2. 双重随机性使单个决策树的预测误差相互解耦；
3. 随机森林通过平均预测结果降低整体方差；
4. 随机森林对噪声数据具有鲁棒性；
5. 随机森林可以降低过拟合风险。

前两条具有有效 E1 原文支持。后三条触发了验证问题：

### Claim 3：quote 过短

模型选择的 quote 只有：

```text
By taking an average of those predictions,
```

这段原文虽然与平均有关，但自身没有出现 Random Forest 或 variance。保守术语覆盖检查因此认为“随机森林、方差”没有被直接 quote 覆盖。

### Claim 4：把路径 ID 当作文本证据 ID

模型输出：

```text
evidence_ids = ["P2"]
graph_path_ids = ["P2"]
```

`P2` 是图路径，不是文本证据。程序因此记录：

```text
claim 4 引用了不存在的 evidence_id: P2
```

### Claim 5：同样混淆 E/P ID

模型输出：

```text
evidence_ids = ["P3"]
graph_path_ids = ["P3"]
```

程序记录：

```text
claim 5 引用了不存在的 evidence_id: P3
```

## 为什么最终整题拒答

阶段 8.3 之前的 Verifier 虽然逐 Claim 检查，但最终只做整题聚合：

1. 5 条 Claim 中只有 2 条通过，`claim_coverage=0.4`；
2. 5 组引用中只有 3 组文本 ID 有效，`citation_validity=0.6`；
3. 存在 unsupported 项，不能满足 PASS 的“unsupported 为空”要求；
4. 第一次验证触发扩大检索和第二次 LLM 生成；
5. 第二次仍含无效 Claim；
6. 达到最大重试次数后整题 REFUSE。

所以失败链路是：

```text
证据充分
  -> LLM 生成部分正确、部分引用错误的 Claims
  -> Verifier 拦截错误 Claims
  -> 当时没有 PARTIAL_PASS
  -> 支持 Claim 也被一起丢弃
  -> 整题拒答
```

## 规则基线对照

同一问题在 `AGENT_GENERATOR_BACKEND=offline_rule` 下复现结果：

```text
Decision: pass
Evidence score: 1.0000
Claim coverage: 1.0000
Citation validity: 1.0000
Path validity: 1.0000
Retrieval sufficiency: 1.0000
Retry count: 0
```

规则基线给出的核心回答为：

> 随机森林通过随机性和多个决策树的聚合降低方差，因此通常比单一估计器更稳定；当前图谱还标注了其对噪声数据的鲁棒性和缓解过拟合风险的关系。

这进一步证明 Retriever、官方 Chunk 和图谱关系具备回答条件。

## 根因优先级

1. **最高优先级：** 当前没有 Claim-level retained/removed 结果和 `PARTIAL_PASS`；
2. **已在阶段 8.2 修复：** Prompt v1 未充分强化 E/P/R 字段边界和原子 Claim；
3. **高优先级：** Claim quote 可能只截取半句，未覆盖完整专业结论；
4. **中优先级：** 任何 unsupported 都触发整题重试，第二次调用成本高且没有定向修复；
5. **非主要原因：** 本题不属于文本召回失败，不能靠简单提高 top-k 或 Dense Retrieval 直接解决。

## 正式修复路径

不对冻结 runtime 做临时补丁。按既定顺序：

1. 阶段 8.0：撤销未执行的 v1 extension release，建立 v2 合同（已完成）；
2. 阶段 8.1：Evidence Packer 保留完整直接证据（已完成）；
3. 阶段 8.2：Prompt v2 限制最多 4 个原子 Claim，强化 E/P/R 字段语义和直接 quote（已完成）；
4. 阶段 8.3：逐 Claim 输出 ClaimResult，删除失败项并实现 `PARTIAL_PASS`（已完成）；
5. dev 回归重点复核 `DEV02`，确保支持 Claim 被保留、错误 Claim 不进入用户答案；
6. 参数冻结后才建立并运行一次 v2 extension。

## 阶段 8.1 完成后的复核

最终 `intent_aware_v2` Packer 接线后，对同一 dev 问题再次执行真实 `qwen3:4b` smoke：

```text
Decision: refuse
Evidence score: 0.8000
Claim coverage: 0.3333
Citation validity: 1.0000
Path validity: 1.0000
Retrieval sufficiency: 1.0000
Retry count: 1
Generation latency: 10186.3 ms + 8696.6 ms
Packing latency: 6.024 ms + 5.200 ms
```

两次 Packer 调用都稳定选择 `E1,E4,E8,E2,E6,E5` 和 `P1,P2,P3`，当前首轮序列化上下文为 7,371 字符，无 coverage gap。该次模型没有再把 P ID 填入 `evidence_ids`，三条引用和图路径全部合法；但严格 Verifier 仍因两条 Claim 的“随机森林 / 平均 / 过拟合”等术语未被对应 quote 完整覆盖，只保留 1/3 Claim 支持并最终拒答。

因此阶段 8.1 的结论是：证据选择、可见 ID 边界和 trace 已正常工作，Packer 耗时相对两次 LLM 生成很小；过度拒答仍未解决，剩余根因集中在原子 Claim、quote 对齐和整题聚合决策。不能把本次 smoke 描述为答案质量提升实验，也不能据此运行 extension。

## 阶段 8.2 完成后的复核

Prompt v2 将 wire Schema 限制为 1～4 条 Claim，并强化逐字 quote、E/P/R 命名空间、每个 E ID 的 quote 覆盖和顶层路径一致性。四个合成场景各运行 5 次，正式结构与语义探针为 `20/20`；该结果只属于工程门槛。

同一真实 dev 问题再次执行：

```text
Decision: refuse
Evidence score: 0.8500
Claim coverage: 0.5000
Citation validity: 1.0000
Path validity: 1.0000
Retrieval sufficiency: 1.0000
Retry count: 1
Generation latency: 8176.2 ms + 7400.9 ms
Packing latency: 1.863 ms + 3.748 ms
Generated Claims: 4
```

四条 Claim 已分别表达随机性来源、降低方差目的、单树高方差/过拟合倾向和平均预测；不存在 E/P/R 混填，所有 quote 均为直接原文。旧 Verifier 仍因“过拟合”以及“随机森林/决策树/方差”的跨语言术语覆盖只支持 2/4 Claim，并按整题策略拒答。

因此阶段 8.2 改善了 Claim 粒度和严格覆盖，但没有完成最终修复。下一步必须逐 Claim 保留已支持结论并删除失败项；不能把 0.5000 的单题开发观察写成质量提升实验。

期望的 v2 行为：

```text
Claim 1 supported
Claim 2 supported
Claim 3 unsupported or repaired
Claim 4 unsupported
Claim 5 unsupported
    ↓
保留 Claim 1/2
    ↓
PARTIAL_PASS，而不是 REFUSE
```

## 阶段 8.3 完成后的复核

Claim-level Verifier 已为每条 Claim 生成稳定 C ID、supported/unsupported、retained/removed、有效 E/P ID 和 reason codes。默认 LLM 策略保留 supported Claims；离线规则基线继续使用 strict，LLM 也可显式切换 strict 作为消融。

同一 DEV02 的脱敏 warm smoke 结果：

```text
Decision: partial_pass
Evidence score: 0.8500
Claim coverage: 0.5000
Citation validity: 1.0000
Path validity: 1.0000
Retrieval sufficiency: 1.0000
Generated Claims: 4
Retained Claims: C1, C2
Removed Claims: C3, C4
Retry count: 0
Generation calls: 1
Generation latency: 7275.8 ms
Evidence packing latency: 1.901 ms
Verification latency: 0.342 ms
End-to-end latency: 7288 ms
Unsupported Claim leakage: 0
Fallback: false
```

最终用户答案只包含 C1/C2 和固定证据限制句，不包含 C3/C4 的专业结论。相比阶段 8.2，本题从“2/4 Claim 支持但整题 refuse、重试 1 次”变为“2/4 Claim 保留、partial_pass、重试 0 次”。脱敏报告为 `reports/claim_level_partial_pass_dev02_smoke.json`，SHA-256 为 `f32f763603a5d5984400bd20b9226d56a66b2cadb13b4f98f94ab28a6c4b5fd8`。

该结果只证明本题的过滤和状态机机制成立。它不是完整 dev/pilot 回归，不能证明总体 Over-refusal Rate 已达到目标，也不能证明 LLM 优于规则基线。第一次冷启动式探索调用的单次生成约 29.2 秒，正式脱敏 warm smoke 为 7.3 秒，因此当前只确认“第二次 LLM 调用已消失”，不把两次不同运行条件下的墙钟时间直接比较为性能提升。

## 当前临时使用方式

需要稳定演示已有 v1.0 能力时，可以使用规则生成器：

```powershell
$env:AGENT_GENERATOR_BACKEND="offline_rule"
python -m streamlit run app/streamlit_app.py
```

该方式是明确标注的规则基线，不应伪装成 LLM 结果。默认 LLM 模式现在使用 Claim-level Partial-pass；阶段 8.4 的 trace/UI、合成预热和四路径 browser smoke 已完成，正式质量结论仍需阶段 8.5 的完整 dev 回归。
