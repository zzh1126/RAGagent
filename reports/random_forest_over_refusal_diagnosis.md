# “随机森林为什么更稳定”过度拒答诊断

## 诊断信息

| 项目 | 内容 |
| --- | --- |
| 日期 | 2026-07-23 |
| 分支 | `experiment/llm-agent-v2` |
| 问题 | `随机森林为什么更稳定？` |
| 对应开发题 | `DEV02` |
| 结论 | 知识库和检索证据充足；失败发生在 LLM Claim 引用与严格整题验证阶段 |
| extension | 未运行、未读取 |

## LLM 主链路复现

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

当前 Verifier 虽然逐 Claim 检查，但最终只做整题聚合：

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
  -> 当前没有 PARTIAL_PASS
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
2. **高优先级：** Prompt v1 没有充分强化 E ID 与 P ID 的字段边界；
3. **高优先级：** Claim quote 可能只截取半句，未覆盖完整专业结论；
4. **中优先级：** 任何 unsupported 都触发整题重试，第二次调用成本高且没有定向修复；
5. **非主要原因：** 本题不属于文本召回失败，不能靠简单提高 top-k 或 Dense Retrieval 直接解决。

## 正式修复路径

不对冻结 runtime 做临时补丁。按既定顺序：

1. 阶段 8.0：撤销未执行的 v1 extension release，建立 v2 合同；
2. 阶段 8.1：Evidence Packer 保留完整直接证据；
3. 阶段 8.2：Prompt v2 限制最多 4 个原子 Claim，强化 E/P 字段语义和直接 quote；
4. 阶段 8.3：逐 Claim 输出 ClaimResult，删除失败项并实现 `PARTIAL_PASS`；
5. dev 回归重点复核 `DEV02`，确保支持 Claim 被保留、错误 Claim 不进入用户答案；
6. 参数冻结后才建立并运行一次 v2 extension。

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

## 当前临时使用方式

需要稳定演示已有 v1.0 能力时，可以使用规则生成器：

```powershell
$env:AGENT_GENERATOR_BACKEND="offline_rule"
python -m streamlit run app/streamlit_app.py
```

该方式是明确标注的规则基线，不应伪装成 LLM 结果。默认 LLM 模式保留当前行为，用于展示和修复真实的过度拒答问题。
