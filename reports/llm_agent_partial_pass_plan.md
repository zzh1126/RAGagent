# LLM Agent Partial-pass 增强评测与合并执行计划

## 评测信息

| 项目 | 内容 |
| --- | --- |
| 评测日期 | 2026-07-23 |
| 当前分支 | `experiment/llm-agent-v2` |
| 当前提交 | `57635f4` |
| 计划状态 | 建议通过，进入分阶段实现 |
| 当前 extension release | `extension-qwen3-4b-v1-bdedf7dc` |
| release 状态 | `authorized_not_executed`，尚未运行 |
| 本轮边界 | 只做技术评测与计划冻结；不改 runtime，不运行 final/extension |

## 一、总体结论

这组建议方向正确，而且与当前真实误差高度一致。下一阶段的核心不应是扩充知识库或增加框架，而应把现有验证逻辑从“任一 Claim 不支持就整题失败”升级为“逐 Claim 判定、过滤不支持内容、保留有证据内容、必要时部分回答”。

建议纳入主计划的内容：

1. 将 Evidence Packer 作为当前 `EvidenceContextSerializer` 的确定性增强；
2. 将 LLM Prompt 和 wire Schema 升级为最多 4 条原子 Claim；
3. 正式使用并扩展 `ClaimResult`，输出逐 Claim 验证结果；
4. 将验证决策扩展为 `PASS / PARTIAL_PASS / RETRY / REFUSE`；
5. 增加 Rule、LLM Strict、LLM No Verifier、LLM Partial-pass 四方法对照；
6. 增加检索、证据打包、生成、验证、重试和端到端延迟追踪；
7. 在 Streamlit 中展示真实模型、fallback、延迟和 Verifier 决策；
8. Dense Retrieval 仅保留为误差分析触发的后备增强。

不纳入当前主计划的内容：扩充知识源、增加实体关系、自动图谱抽取、LLM Planner、多 Agent、复杂动态图、完整 Microsoft GraphRAG 和大规模框架迁移。

## 二、现状证据与问题定位

当前候选 dev 运行的关键结果如下：

| 指标 | 当前结果 |
| --- | ---: |
| Decision Accuracy | 0.6000 |
| Structured Output Success | 1.0000 |
| Fallback Rate | 0.0000 |
| 平均端到端延迟 | 11437.7 ms |
| 平均生成延迟 | 5691.18 ms |
| 触发一次重试 | 7/10 |
| 无答案题正确拒答 | 2/2 |
| 可回答题过度拒答 | 4/8 |

4 个错误全部是可回答问题被拒绝：

- `DEV02`：随机森林降低方差的机制；
- `DEV03`：类别不平衡下 Balanced Accuracy 与 F1 的选择；
- `DEV05`：Bagging 与 AdaBoost 的对比；
- `DEV10`：决策树过拟合。

代码层面的直接原因：

1. `EvidenceVerifier` 已逐条遍历 Claim，但只累计 `supported_claim_count` 和全局 `unsupported_claims`；
2. `ClaimResult` 已存在，但没有进入 `VerifyResult`，也没有参与最终答案重建；
3. 当前 `VerifyDecision` 只有 `pass/retry/refuse`；
4. 只要存在 unsupported 项，当前 `pass` 条件就失败，通常先重试，再整题拒答；
5. Prompt 要求 quote，但没有 Claim 数量上限和明确的原子事实约束；
6. 当前 Context Serializer 有图路径证据优先和查询相关重排，但没有按题型做证据覆盖配额；
7. 7/10 的重试意味着当前策略既放大延迟，也没有有效缓解过度拒答。

因此，当前主要矛盾不是“模型不会输出 JSON”，也不是“知识库太小”，而是证据组织、Claim 粒度和最终验证决策之间不匹配。

## 三、逐项评测

| 建议 | 结论 | 优先级 | 处理方式 |
| --- | --- | --- | --- |
| 逐 Claim 验证与 `PARTIAL_PASS` | 接受 | P0 | 作为本轮核心技术增强 |
| Evidence Packer | 接受 | P0 | 演进现有 Serializer，不改变冻结语料和 Retriever 输出 |
| 原子 Claim Prompt | 接受 | P0 | 最多 4 条；保留 `supporting_quotes` 列表 |
| 四方法 LLM Agent 对照实验 | 接受 | P0 | 改为 v2 一次性 extension 协议 |
| 延迟拆分与演示稳定性 | 接受 | P1 | 与工作流接线同步实现 |
| Dense Retrieval | 有条件暂缓 | P2 | 仅在召回误差审计满足触发条件时实现 |
| LLM Planner、多 Agent、扩库等 | 不接受 | No-Go | 保持原计划边界 |

需要修正两点：

1. `pilot` 已参与历史修复和结果分析，不能重新作为自由调参集。实现期只使用 dev、合成样例和单元测试；pilot 只允许做一次预先声明门槛的冻结前回归，不能根据逐题结果继续调参。
2. `PARTIAL_PASS` 不是“正确答案”的自动标签。它只表示至少一个 Claim 被证据支持且用户可见答案已过滤。最终完整性和正确性仍由 Answer Correctness 人工评分决定。

## 四、v2 目标状态

### 4.1 决策语义

| 决策 | 精确定义 |
| --- | --- |
| `pass` | 所有保留 Claim 均受支持，且没有需要披露的证据缺口 |
| `partial_pass` | 至少一个 Claim 受支持，但有 Claim 或问题方面因证据不足被移除 |
| `retry` | 当前没有可安全保留的 Claim，但缺口被判定为可通过一次扩大检索恢复 |
| `refuse` | 没有任何可安全保留的 Claim，且重试无效、不可恢复或问题前提不成立 |

固定决策顺序：

```text
逐 Claim 验证
    ↓
保留 supported Claims，移除 unsupported Claims
    ↓
全部支持且无缺口 -> PASS
部分支持 -> PARTIAL_PASS
零支持且检索缺口可恢复 -> RETRY（最多一次）
零支持且不可恢复/重试后仍失败 -> REFUSE
```

`partial_pass` 不再触发第二次 LLM 调用。这样可以同时减少无效重试和端到端延迟。错误前提、未知属性和无答案问题必须在零 Claim 保留时进入 `refuse`，不能用部分回答掩盖问题前提错误。

### 4.2 Claim 级验证结构

计划扩展 `ClaimResult`，至少记录：

```python
class ClaimResult(BaseModel):
    claim_index: int
    claim: str
    status: Literal["supported", "unsupported"]
    evidence_ids: list[str]
    graph_path_ids: list[str]
    reason_codes: list[str]
    retained: bool
```

`VerifyResult` 增加：

- `claim_results`；
- `supported_claim_count`；
- `removed_claim_count`；
- `retained_claim_indexes`；
- `partial_pass_reason`；
- `decision="partial_pass"`。

用户可见 `answer_payload` 只保留 supported Claims；被删除内容仅以 ClaimResult 诊断信息保存，不再进入用户答案。部分回答统一使用以下语义，不复述未经支持的专业结论：

> 根据当前知识库，可以确认……；但问题中的其余方面缺少足够证据，因此不作进一步判断。

### 4.3 Evidence Packer

Evidence Packer 位于 Retriever 与 Generator 之间，只选择和排序送入 LLM 的证据，不修改原始 `RetrievalResult`，也不改变冻结语料、图谱或 TF-IDF 索引。

固定处理流程：

```text
RetrievalResult
    ↓
按 chunk_id 去重
    ↓
保留图路径绑定 Chunk
    ↓
实体名与标题/heading 匹配
    ↓
问题类型配额
    ↓
查询相关性排序
    ↓
字符预算裁剪与稳定编号
```

题型策略：

| 题型 | 证据策略 |
| --- | --- |
| 定义题 | 直接包含目标实体的标题、heading 和定义段优先 |
| 对比题 | 两个对象分别保留至少 2 条证据；不足时记录 coverage gap |
| 原理与优缺点 | 平衡机制、优势、局限相关段落 |
| 多跳题 | 在预算内优先保留每条图路径绑定的 Chunk |
| 指标选择 | 同时保留指标定义和适用场景证据 |
| 单跳关系 | 直接关系证据和对应实体段落优先 |

Packer 输出需带 selected chunk ID、选择原因、各实体覆盖数和 `packing_latency_ms`，以便调试和实验审计。排序必须是确定性的，相同输入产生相同结果。

### 4.4 Prompt v2 与 wire Schema

Prompt v2 固定要求：

1. 每条 Claim 只表达一个可独立验证的专业事实；
2. 不在同一 Claim 中组合机制、结果、优势等多个结论；
3. 每条 Claim 至少绑定一个真实 `evidence_id`；
4. 每条 Claim 至少提供一段逐字来自证据的 `supporting_quotes`；
5. 最多输出 4 条 Claims；
6. 证据不足的方面写入 `unsupported_claims`，不得用模型记忆补全；
7. `supporting_quotes` 继续使用列表，允许一个 Claim 由多个直接片段共同支持。

wire Schema 将 `claims` 设置为 `min_length=1, max_length=4`。不采用简单的“出现并且/同时就拒绝”字符串规则，因为它会误伤单一复合概念；原子性主要由 Prompt、少量合成反例和 Claim 级人工审计控制。

## 五、实验设计

### 5.1 四方法矩阵

| 方法 ID | Router | Generator | Evidence Packer / Prompt | Verifier |
| --- | --- | --- | --- | --- |
| `rule_baseline` | Rule | Rule | 不适用 LLM Prompt | 现有规则 Verifier |
| `llm_strict_v2` | Rule | LLM | v2 / v2 | 严格整题决策模式 |
| `llm_no_verifier_v2` | Rule | LLM | v2 / v2 | 不干预最终决策，另做 shadow 验证 |
| `llm_partial_pass_v2` | Rule | LLM | v2 / v2 | Claim-level Partial-pass |

`llm_strict_v2` 与 `llm_partial_pass_v2` 必须共用相同 Retriever、Packer、Prompt、模型和生成参数，只改变 Verifier 决策方式，才能把差异归因于 Partial-pass。No Verifier 方法仍使用 shadow verifier 计算引用和 Claim 支持指标，但 shadow 结果不得改变答案。

### 5.2 指标口径

自动指标：

- Decision Accuracy；
- Refusal Accuracy；
- Over-refusal Rate；
- Partial-pass Rate；
- Claim Support Rate；
- Claim Retention Rate；
- Citation Validity；
- Structured Output Success；
- Fallback Rate；
- Retry Rate；
- 分阶段与端到端延迟。

人工指标：

- Answer Correctness：0/1/2；
- Evidence Faithfulness：0/1/2；
- Hallucination：0/1；
- Over-refusal：0/1；
- Readability：1～5。

自动决策计分规则：

- 对 expected answer，`pass` 和 `partial_pass` 都属于“未拒答”，但不自动代表内容正确；
- 对 expected refusal，只有 `refuse` 正确；
- Over-refusal 只统计可回答题中的 `refuse`；
- `partial_pass` 的完整性差异由人工 Answer Correctness 体现；
- Faithfulness 对所有实质性回答计算，包括 `partial_pass`。

主要研究比较：

1. `llm_partial_pass_v2` 对比 `llm_strict_v2`：是否降低过度拒答，并维持证据忠实度；
2. `llm_partial_pass_v2` 对比 `rule_baseline`：是否提高可读性和答案完整性；
3. `llm_partial_pass_v2` 对比 `llm_no_verifier_v2`：Verifier 是否降低幻觉和无效引用。

由于 extension 只有 23 题，结果只做描述性统计，不声称统计显著性。

### 5.3 数据使用边界

| 数据集 | 用途 | 是否允许调参 |
| --- | --- | --- |
| 合成样例 | Schema、Claim 过滤、状态机和异常路径测试 | 是 |
| dev 10 题 | Packer、Prompt、阈值和重试策略开发 | 是 |
| pilot 40 题 | 冻结前一次回归检查 | 否 |
| final 40 题 | v1.0 历史结果，只读 | 否，禁止重跑 |
| extension 23 题 | v2 冻结后一次性四方法实验 | 否，只运行一次 |

如果 pilot 回归失败，不允许查看逐题结果后直接微调并继续把 pilot 称为保留集。应记录失败、返回 dev，并将 pilot 标记为已消费的回归集。

## 六、延迟与演示稳定性

新增时间字段：

```text
routing_latency_ms
retrieval_latency_ms
evidence_packing_latency_ms
llm_generation_latency_ms
verification_latency_ms
retry_latency_ms
end_to_end_latency_ms
```

其中 `retry_latency_ms` 是重试分支墙钟时间，会与检索、生成、验证阶段部分重叠，不能再次加入阶段总和。

低风险优化顺序：

1. Streamlit 启动后执行一次不读取业务题集的 Ollama 预热；
2. 继续使用 `keep_alive`，当前配置为 `30m`；
3. Packer 限制证据条数和总字符数；
4. Claims 最多 4 条；
5. Partial-pass 后不再重试；
6. 仅在零 Claim 支持且缺口可恢复时重试；
7. 根据 dev 结构成功率再决定是否降低 `num_predict=1536`，不能直接降低导致 JSON 再次截断；
8. 保留 `offline_rule` fallback；
9. 演示缓存属于可选项，正式评测必须禁用；若启用，前端必须显示 `cache_hit`。

Streamlit 状态区至少展示：

```text
Generator: qwen3:4b
Fallback: false
LLM latency: 1.86 s
End-to-end latency: 2.04 s
Verifier: PARTIAL_PASS
```

界面展示真实测量值，不写死示例数值。

## 七、Extension release 治理

当前 v1 release 已授权但未执行。Evidence Packer、Prompt 或 Verifier 的任何改动都会改变 runtime bundle，因此不能继续拿 v1 release 执行，也不能直接覆盖原文件。

开始实现前必须先完成：

1. 再次确认 `reports/extension/` 不存在、没有 execution state、receipt 或任何 extension 答案；
2. 为 `extension-qwen3-4b-v1-bdedf7dc` 创建独立、不可覆盖的 revocation record；
3. revocation record 固定原 release ID、release 文件哈希、撤销时间、撤销提交、`revoked_before_execution=true` 和原因“在观察任何 extension 输出前升级实验协议”；
4. 保留并禁止覆盖现有 `extension_holdout_release.json`、implementation manifest 和 v1 trace contract；
5. 修改专用 runner 和 validator，使被撤销的 release ID 无条件拒绝执行；
6. 新建 `config/extension_evaluation_v2.yaml` 和 `config/extension_trace_contract_v2.yaml`；
7. 完成 v2 runtime 后创建新的 implementation manifest、release record 和 release ID；
8. v2 extension 仍复用未被查看的 23 题冻结题集，且只执行一次。

撤销是实验治理动作，不代表 v1 实现错误；它表示在看见保留集结果之前主动采用更完整的协议。所有 v1 文件和哈希继续作为审计记录保留。

## 八、分阶段执行顺序

### 阶段 8.0：撤销 v1 release 并建立 v2 合同

- 创建不可变 revocation record；
- 为 runner/validator 增加撤销检查；
- 创建 v2 evaluation 和 trace contract；
- 固定四方法矩阵、四状态决策和指标口径；
- 不读取或运行 extension 问题。

验收：旧授权命令必须明确失败；v1 文件未删除、未覆盖；extension 输出仍不存在。

### 阶段 8.1：Evidence Packer

- 新建确定性 Packer；
- 实现去重、图路径绑定、实体/标题匹配和题型配额；
- 输出 packing trace 与计时；
- 增加定义、对比、多跳、指标题单元测试。

验收：相同输入稳定输出；不修改 `RetrievalResult`；严格遵守条数和字符预算；对比题在证据可用时覆盖双方。

### 阶段 8.2：原子 Claim Prompt v2

- Prompt 增加单事实约束和最多 4 条 Claims；
- wire Schema 增加 `max_length=4`；
- 保留 quote 子串校验；
- 增加合成结构、无效引用、超长 Claim 列表和多事实 Claim 样例。

验收：至少 20 次合成结构探针中成功不少于 19 次；不存在第 5 条 Claim；无真实证据 ID 时不能生成可接受 Claim。

### 阶段 8.3：Claim-level Verifier 与 Partial-pass

- 扩展 `ClaimResult` 和 `VerifyResult`；
- 逐 Claim 保存 reason code；
- 过滤 unsupported Claims；
- 重建 `pass/partial_pass/refuse` 用户答案；
- 将 retry 限定为零 Claim 支持且可恢复；
- 保留 strict 模式供消融。

验收：混合 Claim -> `partial_pass`；全部支持 -> `pass`；全部失败 -> 最多重试一次后 `refuse`；错误前提不能部分放行；用户答案中不出现被移除 Claim。

### 阶段 8.4：工作流、trace 与 Streamlit

- LangGraph 增加 `partial_pass -> finalize` 路径；
- 增加阶段计时和 Claim 诊断 trace；
- 更新 CLI、评测输出和 Streamlit 状态区；
- 增加启动预热，保持 fallback；
- 正式评测路径禁用答案缓存。

验收：四种决策均有测试；阶段时间非负且端到端口径一致；前端展示真实 backend、fallback、模型、Verifier 和延迟。

### 阶段 8.5：Dev 调试与误差审计

- 只用合成样例和 dev 调试；
- 对 4 个过度拒答样例做前后对比；
- 统计 Claim 保留率、重试率和分阶段延迟；
- 审计失败来自召回、打包、生成还是验证。

进入冻结候选的目标门槛：

- Structured Output Success 不低于 0.95；
- 无答案题 Refusal Accuracy 保持 2/2；
- dev 可回答题 Over-refusal 从 4/8 降至不高于 2/8；
- 用户可见答案不包含已判定 unsupported 的 Claim；
- 平均重试率低于当前 7/10；
- fallback 和所有异常路径可追踪。

这些是进入下一阶段的工程门槛，不是最终科研结论。

### 阶段 8.6：Pilot 回归与 v2 冻结

- 参数冻结后运行一次 pilot 回归；
- 不根据逐题结果继续调参；
- 冻结 runtime、Prompt v2、wire Schema、Packer 配置、Verifier 模式、trace contract、依赖和模型 digest；
- 创建 v2 implementation manifest 和一次性 release。

验收：全部哈希稳定；模型 digest 匹配；旧 release 已撤销；新 release 为 `authorized_not_executed`；extension 输出不存在。

### 阶段 8.7：Extension 一次性实验

- 先执行完整 preflight；
- 一次性运行 4 方法 × 23 题；
- 中断时进入人工审计，不自动重跑已暴露题目；
- 校验 execution receipt 和所有输出哈希；
- 生成 A/B/C/D 盲评表与独立 method key；
- 不修改 final v1.0 结果。

验收：92 个方法-题目调用完整或有可审计中断记录；结果文件不可覆盖；运行后不再调参。

### 阶段 8.8：盲评、图表和报告

- 完成 Correctness、Faithfulness、Hallucination、Over-refusal、Readability 评分；
- 汇总四方法自动与人工指标；
- 输出过度拒答、Claim 保留和延迟图；
- 更新科研报告、事实声明清单和答辩材料；
- 只陈述数据支持的结论。

## 九、Dense Retrieval 触发条件

Dense Retrieval 不进入当前关键路径。只有在阶段 8.5 的错误归因满足以下条件时才单独立项：

1. 剩余可回答错误中至少 30% 明确属于文本召回失败；
2. 正确 Chunk 存在于当前 180 个 Chunk 中，但没有进入当前 top-k；
3. 问题主要表现为同义改写或中英匹配，而不是语料本身缺失；
4. 实现不会推迟 Partial-pass extension 冻结。

如果正确证据根本不在语料中，Dense Retrieval 无法解决问题，此时应诚实报告知识边界，而不是继续增加检索器。

## 十、计划中的主要文件

预计新增或修改：

```text
data/evaluation/<v1-revocation-record>.json
config/extension_evaluation_v2.yaml
config/extension_trace_contract_v2.yaml
src/agent/generators/context.py 或 evidence_packer.py
src/agent/generators/llm_generator.py
src/schemas.py
src/verification/evidence_verifier.py
src/agent/workflow.py
src/evaluation/extension_runner.py
src/evaluation/extension_release.py
app/streamlit_app.py
tests/test_answer_generators.py
tests/test_day4_workflow.py
tests/test_extension_release.py
PROGRESS.md
```

冻结的 v1 release、manifest、trace contract、final 结果和用户提供的 DOCX 均不得删除或覆盖。

## 十一、最终 Go / No-Go 决定

**Go：** Evidence Packer、原子 Claim、Claim-level Verifier、`PARTIAL_PASS`、四方法 v2 对照、阶段延迟、Streamlit 状态展示。

**Conditional Go：** Dense Retrieval，仅在召回误差审计触发后考虑。

**No-Go：** LLM Planner、多 Agent、知识库扩充、自动图谱抽取、完整 Microsoft GraphRAG 和框架迁移。

下一步只执行阶段 8.0：撤销尚未执行的 v1 release、建立 v2 合同和保护测试。完成验收后，再进入 Evidence Packer，不会在同一步运行 extension。
