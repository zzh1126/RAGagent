# scikit-learn 知识问答 Agent 不足与完善路线图

## 1. 文档目的

本文只回答四类问题：

1. 项目现在还缺什么；
2. 每个不足有什么实际证据和影响；
3. 马上要做什么、按什么顺序做、怎样才算完成；
4. 哪些内容暂时不做，以及在什么条件下才重新考虑。

本文审计基线为 2026-07-23、分支 `experiment/llm-agent-v2`，Stage 8.5 从提交 `16ac995` 开始。详细项目事实见 `PROJECT_HANDBOOK.md`，Partial-pass 协议设计见 `reports/llm_agent_partial_pass_plan.md`，dev 误差审计见 `reports/llm_agent_v2_dev_stage8_5_audit.md`。

状态含义：

| 状态 | 含义 |
| --- | --- |
| P0 | 当前主线，必须先完成 |
| P1 | P0 完成后应完成，影响演示或报告质量 |
| P2 | 有余力或有证据触发后再做 |
| Deferred | 暂时不实现，保留重审条件 |
| No-Go | 当前课题明确不做 |

## 2. 总体判断

项目不是“还没有做出来”，而是已经有两个成熟度不同的层次：

1. **v1.0 规则基线已经完整**：数据、图谱、检索、Verifier、LangGraph、Streamlit、final、pilot 消融、归档和报告素材都已具备；
2. **LLM 增强主链路已经可运行但尚未完成科研验证**：结构化输出稳定，安全边界保守，但过度拒答、延迟和实验协议还需完善。

当前最重要的缺口不是再增加新工具，而是把 LLM 链路从：

```text
一个 Claim 不受支持
    ↓
整题重试
    ↓
整题拒答
```

升级为：

```text
逐 Claim 验证
    ↓
删除不支持 Claim
    ↓
保留受支持 Claim
    ↓
完整回答 / 部分回答 / 拒答
```

## 3. 当前不足总表

| ID | 不足 | 证据 | 影响 | 优先级 | 计划状态 |
| --- | --- | --- | --- | --- | --- |
| G01 | v1 extension 授权与最新暂停决定并存 | v1 已建立不可变撤销记录，runner 先于题集读取拒绝旧 ID | 风险已关闭 | Done | 阶段 8.0 完成 |
| G02 | Verifier 过度拒答 | Stage 8.5 dev candidate 为 1/8 answerable over-refusal，历史值 4/8 | 工程门槛通过；正式效果仍待 extension | Done | 阶段 8.5 完成 |
| G03 | ClaimResult 未真正接线 | VerifyResult 已输出逐 Claim supported/retained/reason codes | 风险已关闭 | Done | 阶段 8.3 完成 |
| G04 | 没有 `PARTIAL_PASS` | 四状态决策、过滤和固定限制句已接入 | 风险已关闭 | Done | 阶段 8.3 完成 |
| G05 | 证据上下文未按题型平衡 | `intent_aware_v2` 已完成 50 题只读合同回归 | 风险已关闭 | Done | 阶段 8.1 完成 |
| G06 | Prompt 未限制原子 Claim | Prompt v2 与 1～4 Claim wire Schema 已通过 20/20 合成探针 | 风险已关闭 | Done | 阶段 8.2 完成 |
| G07 | 重试过多 | Stage 8.5 dev retry rate 为 3/10，历史值 7/10 | 工程门槛通过；真实延迟仍主要来自 LLM | Done | 阶段 8.5 完成 |
| G08 | 没有 LLM 正式 extension 结果 | extension 从未运行 | 无法回答 LLM 是否真正提升 | P0 | 完成 v2 后一次性运行 |
| G09 | 延迟 trace 不完整 | Stage 8.4 已保存完整 trace；Stage 8.5 dev 平均端到端 9420.28 ms，其中生成 9408.91 ms | trace 风险关闭，生成延迟保留为限制 | Done | 阶段 8.5 已分析 |
| G10 | Streamlit 不展示 LLM 参与细节 | model/backend/fallback/prewarm/结构状态/阶段延迟与 partial 样式已完成 | 风险已关闭 | Done | 阶段 8.4 完成 |
| G11 | 稀疏检索语义能力有限 | TF-IDF + 人工词表 | 同义改写和跨语言召回受限 | P2 | 条件触发 |
| G12 | 混合融合较简单 | 图证据优先顺序合并，无 RRF/归一化 | 多来源排序可能偏置 | P2 | 先做误差分析 |
| G13 | 多跳路径对方向和中间实体敏感 | pilot 已出现路径不完整案例 | 多跳答案覆盖不足 | P2 | 核心实验后考虑 |
| G14 | Neo4j 只完成代码接口 | 驱动当前未安装、无服务基准 | 不能宣称 Neo4j 部署完成 | Deferred | 不影响当前主线 |
| G15 | 实体审核状态语义不一致 | 50 实体 pending，100 关系 approved | 数据治理解释不够整齐 | P2 | 冻结后统一处理 |
| G16 | 人工评分只有单一确认 | 无独立双人标注与一致性 | 外部有效性有限 | Deferred | 时间允许再做 |
| G17 | 数据和题集规模小 | 6 页、final 40、extension 23 | 结论不可泛化 | Deferred | 报告中披露 |
| G18 | 依赖版本约束较宽 | requirements 多数无精确版本 | 新环境可能漂移 | P2 | v2 release 时锁定快照 |
| G19 | 正式报告仍是 Markdown 草稿 | DOCX、PPT、演示脚本未定稿 | 最终交付尚未完成 | P1 | extension 后完成 |

## 4. P0：Extension release 治理

### 4.1 已解决的问题

原 release `extension-qwen3-4b-v1-bdedf7dc` 已绑定 Prompt v1、三方法矩阵和严格整题 Verifier。当前计划要修改 Evidence Packer、Prompt、Schema、Verifier 和方法矩阵，这些都会改变 runtime bundle。

文件层面它仍是：

```text
status = authorized_not_executed
```

该文件值作为历史事实永久保留，但阶段 8.0 新增的 revocation record 将有效状态改为：

```text
effective_execution_status = revoked_before_execution
```

runner、release validator 和 holdout validator 都先检查撤销记录。直接复制旧授权命令会在 runtime/model 校验、题集读取和 QA workflow 构建前失败。

### 4.2 已完成

阶段 8.0 已完成治理和合同，未实现业务增强：

1. 再次确认 `reports/extension/` 不存在；
2. 计算并记录原 release 文件 SHA-256；
3. 新建不可覆盖的 v1 revocation record；
4. 记录 `revoked_before_execution=true`；
5. 原因固定为“在观察任何 extension 输出前升级实验协议”；
6. runner 和 validator 必须读取 revocation record；
7. 被撤销 release ID 无条件拒绝执行；
8. 保留原 release、implementation manifest 和 trace contract；
9. 新建版本化 `extension_evaluation_v2.yaml`；
10. 新建版本化 `extension_trace_contract_v2.yaml`。

### 4.3 验收结果

- [x] 原 v1 授权命令明确失败，并说明 release 已撤销；
- [x] revocation 文件在独立提交 `a518404` 中创建并推送；
- [x] v1 release SHA-256 保持 `af4f8ac10c247483af20e93f5fdde5220b608fb8c9dfb8c031d777d8b1932d0c`；
- [x] extension 题目没有进入 QA workflow；
- [x] `reports/extension/` 仍不存在；
- [x] final 结果未运行、未修改；
- [x] v2 四方法合同和 release 护栏测试通过。

## 5. P0：Intent-aware Evidence Packer

### 5.1 原问题

`EvidenceContextSerializer` 已有两个有价值的能力：

- 图路径绑定 Chunk 优先；
- 查询词命中数和原 score 重排。

但它没有回答：

- 对比题的两个对象是否都被覆盖；
- 定义题是否优先直接标题和定义段；
- 原理题是否同时包含机制、优势和局限；
- 指标题是否同时提供定义和适用场景；
- 多跳题的每条关键路径是否有对应 Chunk。

单纯提高 top-k 会增加上下文长度和模型负担，不保证覆盖平衡。

### 5.2 已完成

已在 Retriever 与 LLM Generator 之间增加确定性 Packer：

```text
RetrievalResult
  -> chunk_id 去重
  -> 图路径绑定证据
  -> 实体/标题/heading 匹配
  -> intent 配额
  -> 查询相关性排序
  -> 字符预算裁剪
  -> 稳定 E ID 和 packing trace
```

策略：

| Intent | 最低策略 |
| --- | --- |
| definition | 实体直接标题或 heading 证据优先 |
| comparison | 证据可用时，两方各至少 2 条 |
| explanation | 机制、优势、局限平衡 |
| multi_hop | 每条关键 P path 的绑定 Chunk 优先 |
| recommendation | 指标定义和适用场景同时保留 |
| relation | 直接关系证据优先 |

Packer 不修改原始 `RetrievalResult`，只返回选中证据、选择原因和序列化上下文。这样可保留完整检索审计。

### 5.3 验收结果

- [x] 相同输入产生完全相同的选择和顺序；
- [x] 不原地修改 RetrievalResult；
- [x] 不产生不存在的 E/P/R/Chunk ID，并拒绝原检索中存在但本次未展示的 ID；
- [x] 严格遵守最大证据条数和字符预算，不任意截断结构块；
- [x] 对比双方有证据时各覆盖至少 2 条；
- [x] 多跳路径绑定 Chunk 在预算内逐路径优先；
- [x] 输出 `evidence_packing_latency_ms`、selected IDs、reason codes、实体覆盖和 coverage gaps；
- [x] 定义、对比、解释、多跳、关系、指标题、零路径预算和极端字符预算均有单元测试；
- [x] dev/pilot 50 题只读回归平均选择 4.38 条、最长 7,783 字符，仅 `F-NA-01` 出现预期空证据 gap。

阶段 8.1 的真实 dev smoke 在一次重试后拒答：citation/path validity 均为 1.0000，但只有 1/3 Claim 通过术语覆盖。阶段 8.2 随后把 Claim coverage 提高到 0.5000；阶段 8.3 最终保留 2/4 Claim并返回 `partial_pass`。这一序列说明 Packer 缩小了上下文噪声，但真正修复整题拒答需要 Claim-level 决策。

## 6. P0：Prompt v2 与原子 Claim

### 6.1 原问题

当前 Prompt 已要求真实 E ID 和逐字 quote，但允许无限数量 Claim，也没有充分阻止一条 Claim 同时表达机制、结果和优势。

示例：

> AdaBoost 逐步调整样本权重，并重点关注错误样本来提升性能。

这可能是多个可独立验证的事实。如果 quote 只支持其中一部分，当前 Verifier 会把整个 Claim 判为不支持。

### 6.2 已完成

Prompt v2 固定要求：

1. 每条 Claim 只表达一个可独立判断真假的事实；
2. 不在一条 Claim 中组合多个机制或因果结论；
3. 每条 Claim 至少一个真实 `evidence_id`；
4. 每条 Claim 至少一段直接 `supporting_quotes`；
5. 最多 4 条 Claims；
6. 证据不足的方面进入 `unsupported_claims`；
7. 继续禁止模型记忆、伪造 ID、URL、参数和性能结论。

Schema 改为：

```python
claims: list[LLMAnswerClaim] = Field(min_length=1, max_length=4)
```

保留 `supporting_quotes` 列表，不退化成单个 quote，因为一个原子 Claim 仍可能需要两个直接片段共同支持。

不实现简单的中文连接词硬拒绝规则。“并且、同时”可能出现在单一术语描述中，机械拦截会产生新的误杀。原子性通过 Prompt、Schema、合成反例和人工审计控制。

### 6.3 验收结果

- [x] 第 5 条 Claim 被 Schema 拒绝；
- [x] Claim 无 E ID 或无 quote 时被拒绝；
- [x] E/P/R ID 在 wire Schema 中使用不同正则命名空间；
- [x] quote 必须是对应 Chunk 连续、保留大小写的原文子串；
- [x] 每个 evidence ID 必须有 quote，顶层路径必须等于 Claim 路径并集；
- [x] 不允许未知字段；
- [x] 20 次合成结构探针成功 `20/20`，四个场景各 5 次；
- [x] 报告不记录 Prompt、原始 content、Claim 正文、quote 或 thinking；
- [x] Prompt v2 SHA-256=`e5c6fa6bbc992a9af2c66daffd8fcffeb2da1eae02202d932aef33fbbb774cad`；
- [x] wire Schema SHA-256=`b11bf9c445d3aa37c98cd571b880a157387661fdebf63a11a43aef786c7087eb`。

阶段 8.2 的随机森林 smoke 生成 4 条分离 Claim，citation/path validity 均为 1.0000，Claim coverage 从阶段 8.1 的 0.3333 提高到 0.5000，但 strict 整题策略仍在一次重试后拒答。阶段 8.3 随后验证逐 Claim 保留与删除可以把同题转为 `partial_pass`；两者都只是开发工程观察，不是独立效果实验。

## 7. P0：Claim-level Verifier 与 `PARTIAL_PASS`

### 7.1 原问题

阶段 8.3 前的代码已经逐 Claim 检查引用、quote 和术语，但验证结果被聚合成一个比例。旧 `ClaimResult` 未接入 `VerifyResult`，FinalResponse 也不删除失败 Claim。

当前 dev 的直接后果：

| 项目 | 结果 |
| --- | ---: |
| 可回答题 | 8 |
| 错误拒答 | 4 |
| Over-refusal | 50% |
| 全部 dev 重试 | 7/10 |

### 7.2 已实现的 ClaimResult

当前包含：

```python
class ClaimResult(BaseModel):
    claim_id: str
    claim_index: int
    claim: str
    status: Literal["supported", "unsupported"]
    supported: bool
    retained: bool
    evidence_ids: list[str]
    valid_evidence_ids: list[str]
    graph_path_ids: list[str]
    valid_graph_path_ids: list[str]
    relation_id: str
    reason_codes: list[str]
```

推荐 reason codes：

- `missing_evidence_reference`；
- `unknown_evidence_id`；
- `quote_not_bound`；
- `quote_not_in_source`；
- `missing_grounding_term`；
- `unknown_graph_path`；
- `invalid_graph_path`；
- `invalid_relation_id`；
- `evidence_not_relevant`；
- `query_alignment_failed`；
- `premise_not_supported`。

### 7.3 四状态决策

```text
全部 Claim 支持且无缺口 -> PASS
至少一个支持，至少一个移除/缺口 -> PARTIAL_PASS
零支持且检索缺口可恢复 -> RETRY
零支持且不可恢复，或重试后仍零支持 -> REFUSE
```

关键约束：

- `partial_pass` 不再触发第二次 LLM 调用；
- 错误前提不能用部分回答绕过，应保留零 Claim 并拒答；
- 用户可见 payload 只包含 retained Claims；
- 被移除 Claim 只留在诊断 trace；
- 部分回答的限制句不复述未经支持的专业事实；
- `partial_pass` 不自动计为人工正确。

### 7.4 验收结果

| 输入情况 | 期望结果 |
| --- | --- |
| 所有 Claims 支持 | pass |
| 支持与不支持混合 | partial_pass，只显示支持项 |
| 所有 Claims 不支持且可恢复 | 最多 retry 一次 |
| 重试后仍全部不支持 | refuse |
| 错误前提 | refuse |
| 未知 E/P/R ID | 对应 Claim 删除 |
| quote 非原文 | 对应 Claim 删除 |
| partial 用户答案 | 不包含 removed Claim |

以上状态机均有自动测试。DEV02 脱敏 warm smoke 进一步确认：generated=4、supported=2、retained=`C1,C2`、removed=`C3,C4`、decision=`partial_pass`、retry=0、generation calls=1、unsupported leakage=0。该单题结果不替代阶段 8.5 的完整 dev 回归。

## 8. P0/P1：重试与延迟

### 8.1 历史问题

探针热调用平均约 0.93 s，但完整 dev 平均 11.44 s，说明完整链路受以下因素叠加：

- 生成上下文更长；
- `num_predict=1536`；
- 7/10 题发生第二次生成；
- Verifier 和扩大检索重复执行；
- Stage 8.3 前没有完整阶段计时，无法严谨拆分。

### 8.2 Stage 8.4 已实施

已新增：

```text
routing_latency_ms
retrieval_latency_ms
evidence_packing_latency_ms
llm_generation_latency_ms
verification_latency_ms
retry_latency_ms
end_to_end_latency_ms
```

口径要求：

- generation 汇总全部 answer 节点调用；
- retry 是重试分支墙钟时间，会与子阶段重叠，不能重复求和；
- end-to-end 使用单调时钟；
- LLM cold 和 warm 分开；
- fallback 延迟保留失败 LLM 调用时间；
- 历史 dev JSON 不回写。

实现细节：

- `RouteTrace` 保存 intent、mode、理由和路由耗时；
- `RetrievalCall` 保存每次初始/补充检索、top-k、返回数量和耗时；
- `GenerationCall` 增加 provider/model，并保留 requested/actual backend；
- `VerificationCall` 保存每次中间/最终决策和 Claim 汇总；
- `WorkflowLatencyTrace` 汇总七项阶段耗时；
- `FinalResponse.cache_status=disabled`，正式路径没有答案缓存；
- CLI、普通评测与 extension runner 读取相同 trace；
- `validate_runtime_trace.py` 的 pass 为 1/1/1 次检索/生成/验证，retry 为 2/2/2。

优化顺序：

1. Partial-pass 避免“已有支持 Claim 仍重试”；
2. 只有零支持且缺口可恢复时重试；
3. Packer 限制上下文；
4. Claims 最多 4 条；
5. Streamlit 启动后做合成预热；
6. 继续使用 `keep_alive=30m`；
7. 结构成功率稳定后再评估降低 `num_predict`；
8. 保留 offline fallback。

不能直接把 `num_predict` 从 1536 降回 768。DEV02 曾因 768 token 截断产生无效 JSON，任何降低都必须重新通过结构成功门槛。

### 8.3 验收状态

- [x] 每个阶段时间非负；
- [x] end-to-end 不小于任何单一阶段；
- [x] retry trace 含第一次和第二次 retrieval/generation/verification call；
- [x] 无答案 smoke 不因减少重试而错误放行；
- [x] UI 分开显示 prewarm、LLM 和端到端延迟；
- [x] dev 平均重试率低于历史 7/10：Stage 8.5 candidate 为 3/10；
- [x] dev 分阶段均值已落盘：generation 9408.91 ms、end-to-end 9420.28 ms；
- [ ] cold/warm 正式统计图：留给阶段 8.7，不能只凭 dev 或单题截图下结论。

## 9. P1：Streamlit 演示完整性

### 9.1 历史问题

当前 UI 能展示回答、图路径、证据和 Verifier 指标，但无法让评审者直接确认真实 LLM 是否参与。

缺少：

- model 名；
- requested/actual backend；
- fallback 状态和原因；
- generation latency；
- structured output success；
- `PARTIAL_PASS` 独立样式；
- packing 和验证阶段延迟；
- cache 状态。

### 9.2 Stage 8.4 已实施

状态区显示真实值：

```text
Generator: qwen3:4b
Backend: ollama
Fallback: false
LLM latency: <measured>
End-to-end latency: <measured>
Verifier: PARTIAL_PASS
```

要求：

- 不写死示例延迟；
- fallback 时明确 actual backend；
- partial 使用独立警示色，不等同 pass 或 refuse；
- 保留完整 JSON 下载；
- 正式评测禁用答案缓存；
- 演示缓存若启用必须显示 `cache_hit`；
- 启动预热不得读取 dev/pilot/final/extension 业务题。

当前实现：

- Streamlit cached workflow 启动时执行固定合成结构化预热；
- sidebar 显示工作流、图后端、Generator 和预热状态；
- 主状态区显示 model、requested -> actual backend、fallback、结构成功和 cache；
- 分阶段显示 routing、retrieval、packing、LLM、verification、retry、end-to-end；
- 新增“运行轨迹”页签，显示 route/retrieval/generation/verification 调用表；
- 无证据且未调用 LLM 时显示 `Structured JSON: not called`，不误写成 failed；
- answer cache 保持 disabled。

### 9.3 验收结果

- [x] pass、partial_pass、refuse、fallback 四条路径均有浏览器 smoke；
- [x] 每条路径均生成 1440 px 桌面和 390 px 移动截图；
- [x] 自动检查两种视口无水平溢出，人工截图未发现文本重叠；
- [x] backend、model、fallback、结构状态和延迟来自 `FinalResponse` trace；
- [x] partial 用户答案只展示 retained Claims；
- [x] fallback 显示 `ollama -> offline_rule` 和失败状态；
- [x] refuse 无 LLM 调用时显示 `not called`。

## 10. P0：四方法正式实验

### 10.1 方法矩阵

| 方法 | Router | Generator | Packer/Prompt | Verifier |
| --- | --- | --- | --- | --- |
| Rule Baseline | Rule | Rule | 不使用 LLM Prompt | 标准规则 Verifier |
| LLM Strict v2 | Rule | LLM | v2/v2 | 严格整题模式 |
| LLM No Verifier v2 | Rule | LLM | v2/v2 | 不干预，shadow 验证 |
| LLM Partial-pass v2 | Rule | LLM | v2/v2 | Claim-level |

Strict 和 Partial-pass 必须共用完全相同的 Router、Retriever、Packer、Prompt、模型和生成参数，只改变 Verifier 决策模式。这样才能把差异归因于 Partial-pass。

### 10.2 指标

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
- cold/warm/阶段/end-to-end latency。

人工指标：Correctness、Faithfulness、Hallucination、Over-refusal、Readability。

计分约束：

- expected answer 的 pass/partial 都属于“未拒答”，但不自动表示内容正确；
- expected refusal 只有 refuse 正确；
- partial 的完整性由 Correctness 评分体现；
- Faithfulness 对 partial 等所有实质回答计算；
- 23 题只做描述性统计，不声称显著性。

### 10.3 研究问题

1. Partial-pass 对比 Strict：是否降低过度拒答，同时维持 Faithfulness；
2. Partial-pass 对比 Rule：是否提高可读性和完整性；
3. Partial-pass 对比 No Verifier：是否降低无证据 Claim、错误引用和幻觉。

## 11. 开发、回归与冻结门槛

### 11.1 数据使用

| 数据 | 允许做什么 | 禁止做什么 |
| --- | --- | --- |
| 合成测试 | 调 Schema、状态机和异常路径 | 不替代真实 dev |
| dev | 调 Packer、Prompt、阈值、重试 | 不作为独立最终结论 |
| pilot | 参数冻结后一次回归 | 不看逐题后继续调参 |
| final | 只读 v1.0 历史结果 | 禁止重跑 |
| extension | v2 release 后一次正式实验 | 禁止调参、自动重跑和覆盖 |

### 11.2 Dev 进入冻结候选门槛

- Structured Output Success ≥ 0.95；
- 两道 dev 无答案题保持 2/2 正确拒答；
- 可回答题 Over-refusal 从 4/8 降至不高于 2/8；
- 用户答案不包含 unsupported Claim；
- 平均重试率低于 7/10；
- fallback、Schema 错误、timeout 和服务关闭都可追踪；
- strict 和 partial 模式均有回归测试。

这些是工程放行门槛，不是最终科研结论。

### 11.3 Pilot 回归规则

参数冻结后只运行一次。若失败：

- 记录失败；
- 返回 dev；
- 将 pilot 明确标记为已消费；
- 不再把后续 pilot 结果当作保留集证明。

### 11.4 v2 冻结

必须冻结：

- runtime bundle；
- Packer 代码和参数；
- Prompt v2；
- LLM wire Schema；
- Verifier 模式；
- v2 evaluation/trace contract；
- extension 题集和评分合同；
- Python 与依赖版本；
- Ollama 版本和模型完整 digest。

新 release 创建后状态必须为 `authorized_not_executed`，并先通过 preflight。

## 12. P2：Sparse Retrieval 与融合不足

### 12.1 当前限制

TF-IDF 依赖词项重合，中文问题通过人工词表改写成英文。它对已知术语有效，但存在：

- 未登记同义词召回差；
- 复杂中文改写可能只生成少量英文词；
- 标题和正文没有独立权重学习；
- 图 score=1 与 TF-IDF score 的语义不同；
- 当前融合按来源顺序和 Chunk 去重，不是 RRF；
- 相邻高分 Chunk 可能挤掉另一实体的关键证据。

### 12.2 为什么暂不立即做 Dense

Stage 8.5 后只剩 DEV05 一个 answerable over-refusal。两个 gold 实体均已召回，Packer 无 coverage gap；项目对全部 180 个 Chunk 的审计只找到两处 AdaBoost 名称提及，均没有样本权重更新或聚焦错分样本的直接机制原文。因此该错误不是“正确 Chunk 存在但未进入 top-k”，Dense Retriever 无法补出不存在的证据。

### 12.3 Dense Retrieval 触发门槛

只有同时满足以下条件才立项：

1. Partial-pass dev 后仍有可回答错误；
2. 至少 30% 剩余错误被归因为 text retrieval；
3. 正确 Chunk 确实存在于 180 个 Chunk 中；
4. 正确 Chunk未进入当前 top-k；
5. 主要原因是同义改写或中英匹配；
6. 不会推迟 extension v2。

若触发，候选结构：

```text
Sparse TF-IDF
   +
Multilingual Dense
   +
Graph evidence
   ↓
RRF fusion
```

必须单独做 recall、延迟、模型下载和离线复现对比，不能只因为装了 `sentence-transformers` 就声称 Dense 已完成。

## 13. P2：多跳图检索不足

### 13.1 已知问题

Pilot 已观察到：

- RF -> Tree -> TreeFamily 路径可能不完整；
- 多目标问题可能只覆盖特征缩放，遗漏高维问题；
- NetworkX `find_paths` 只沿出边搜索；
- 图检索虽然尝试反向 source/target，但复杂中间实体仍可能漏掉；
- 当前 max hops 固定为 2；
- Neo4j 实现的 Cypher `[*1..2]` 实际硬编码 2 hop，传入的 `max_hops` 参数没有改变查询范围。

### 13.2 暂缓原因

当前主问题是 LLM 过度拒答，不是构建通用图查询引擎。扩大路径会增加证据噪声和上下文长度，也会改变冻结 runtime。

### 13.3 后续可选完善

- 显式拆分源、目标和中间实体；
- 对每个目标分别找最短路径再合并；
- 支持受控的双向边遍历；
- 让 Neo4j `max_hops` 语义与接口一致；
- 加入 path coverage 诊断；
- 用多跳 gold path 做独立测试。

## 14. P2/Deferred：图后端和数据治理

### 14.1 Neo4j

不足：

- 当前环境没有 Python `neo4j` 包；
- 需要外部 server、URI、用户名和密码；
- 没有正式 Neo4j 延迟或一致性报告；
- `find_paths(max_hops)` 有硬编码问题。

当前决定：不作为 LLM v2 前置条件。NetworkX 已满足本地复现。只有需要展示持久化图数据库或做后端对比时再补：

1. 安装驱动和固定版本；
2. 启动本地服务；
3. 导入 50/100 图数据；
4. 运行 Repository 合同测试；
5. 比较路径、邻居和验证结果；
6. 报告延迟，但不改变主实验结论。

### 14.2 实体审核状态

当前关系全部 approved，但实体为 pending，运行时仍全部加载。建议未来二选一：

- 完成人工复核后将实体晋级 approved；
- 或明确规定实体 status 只记录构建阶段，不参与 runtime filter。

不能在旧 release 上直接修改 CSV，因为这会改变 runtime bundle。应在 v2 治理后决定是否纳入新版本。

## 15. Deferred：评测有效性不足

### 15.1 样本规模

- final 40；
- extension 23；
- 无答案分别只有 4；
- 不能做强统计显著性结论；
- 不代表完整 scikit-learn。

当前做法：只报告描述性统计、分子分母和案例，不扩大结论。

### 15.2 人工标注

当前是 Codex 辅助初评、用户确认，不是独立双人标注。未来可选：

- 两名独立标注者；
- 隐藏方法标签；
- 随机答案顺序；
- 计算 Cohen's kappa 或加权 kappa；
- 对争议项仲裁。

当前时间范围内不把双人标注设为 extension 前置条件，但报告必须披露该限制。

### 15.3 外部评测

暂不创建更多“保留集”来不断测试同一实现。频繁创建小 holdout 容易产生选择偏差。extension 完成后如继续研究，应重新定义更大范围和新的外部数据来源。

## 16. P2：依赖和环境复现

### 16.1 当前不足

`requirements.txt` 多数依赖只有包名或宽范围，例如 `requests`、`chromadb`、`streamlit`。当前机器可运行不代表未来解析到同一版本。

同时存在：

- requirements 包含 neo4j，但当前环境未安装；
- Ollama 不属于 pip 环境；
- 模型文件约 2.5 GB，不进入 Git；
- v1.0 环境 snapshot 与当前 LLM 分支环境不同。

### 16.2 v2 冻结时完善

- 在 implementation manifest 记录关键包精确版本；
- 保存 `pip freeze` 快照；
- 记录 Python、OS、Ollama 和 model digest；
- 运行 `python -m pip check`；
- 明确可选依赖与必需依赖；
- 不把本机绝对模型路径写入业务代码。

不建议现在大规模切换 Poetry、Conda lock 或容器框架。短周期内保持现有 pip + manifest 体系更稳妥。

## 17. P1：报告与交付不足

当前已有：

- 科研报告 Markdown 初稿；
- 5 张静态图；
- 用户确认 pilot 评分；
- 9 个错误案例；
- v1.0 release；
- Streamlit 截图；
- 完整阶段日志。

仍缺：

- v2 extension 结果；
- 四方法盲评；
- Partial-pass 前后错误分析；
- 分阶段 LLM 延迟图；
- 正式 DOCX 排版；
- 答辩 PPT；
- 演示脚本和故障预案；
- 最终事实声明复核。

这些应在 extension 一次性实验和评分完成后集中处理，避免报告先写结论再找数据。

## 18. 马上要做的阶段顺序

### 阶段 8.0：撤销 v1 release、建立 v2 合同（已完成）

只做治理、配置和护栏，不实现业务增强，不运行 extension。

### 阶段 8.1：Evidence Packer（已完成）

完成确定性证据选择、题型配额、trace 和单元测试。

### 阶段 8.2：Prompt v2（已完成）

完成最多 4 条原子 Claim、quote 合同、Schema 和合成探针。

### 阶段 8.3：Claim-level Verifier（已完成）

完成 ClaimResult、过滤、`PARTIAL_PASS`、strict 模式和状态机测试。DEV02 脱敏 smoke 保留 C1/C2、删除 C3/C4，零 unsupported leakage，且不再触发重试。

### 阶段 8.4：Trace 与 Streamlit（已完成）

已完成阶段延迟、模型/fallback 展示、合成预热、partial UI、CLI/评测 trace 和四路径桌面/移动 browser smoke。

### 阶段 8.5：Dev 调试（已完成）

只用 dev、合成测试和单元测试复核 DEV02/03/05/10。候选达到 Decision Accuracy 0.9000、Structured Output 1.0000、Refusal Accuracy 2/2、Over-refusal 1/8、retry 3/10 和 unsupported leakage 0。DEV05 被确认是语料边界，DEV10 只做保守 quote/术语归一化修正。

### 阶段 8.6：Pilot 回归与冻结（已完成）

已在 commit `e207cb9` 上消费唯一一次 40 题 pilot，预声明 gate 为 `go`。结果为 Decision Accuracy 0.8250、Structured Output 0.9750、4/4 无答案拒答、7/36 answerable over-refusal、13/40 retry、unsupported leakage 0；平均端到端延迟 34180.72 ms。v2 runtime、Prompt、Schema、配置、依赖和模型 digest 已冻结，release `extension-qwen3-4b-v2-e207cb91` 为 `authorized_not_executed`。

### 阶段 8.7：Extension 一次性实验

4 方法 × 23 题；完整 receipt 和哈希；A/B/C/D 盲评表；不自动重跑。

### 阶段 8.8：评分、报告与答辩

完成自动/人工指标、图表、误差分析、DOCX、PPT 和演示材料。

每个阶段单独实现、验证、写入 `PROGRESS.md`、提交 Git，再进入下一阶段。不会一次性跨过全部阶段。

## 19. 暂时不打算实现的内容

### 19.1 Conditional Deferred

| 内容 | 当前不做的原因 | 重新考虑条件 |
| --- | --- | --- |
| 多语言 Dense Retriever | Stage 8.5 唯一剩余错误是语料缺失，不是 top-k 召回失败 | 后续独立误差中 ≥30% 明确为正确 Chunk 未召回 |
| RRF 或学习融合 | 会引入额外实验变量 | Packer 后仍有明确 fusion 错误 |
| Neo4j 正式部署和基准 | NetworkX 已满足复现，驱动/服务未就绪 | 需要后端对比或数据库演示 |
| 通用多跳图查询 | 当前两跳小图足以支撑主实验 | extension 显示多跳为主要错误来源 |
| 双人独立标注 | 时间和人员成本较高 | 需要投稿级一致性证据 |
| 演示答案缓存 | 可能掩盖真实延迟 | 实测 warm 延迟仍影响答辩，并能清楚标注 cache hit |
| 完整依赖锁定工具迁移 | 现有 manifest 已可冻结关键版本 | 项目进入长期维护或跨平台部署 |

### 19.2 当前 No-Go

| 内容 | 不做原因 |
| --- | --- |
| 扩充官方知识源 | 会改变课题边界和冻结数据，不能解决验证逻辑问题 |
| 增加大量实体和关系 | 当前规模足够完成实验，会增加审核成本 |
| 自动知识图谱抽取 | 容易引入关系幻觉，超出六天项目范围 |
| LLM Query Planner | qwen3:4b 语义探针 1/20，不具备可靠性 |
| 多 Agent | 增加复杂度、延迟和归因困难，没有当前必要性 |
| 完整 Microsoft GraphRAG | 项目不是社区检测和全局摘要场景 |
| 复杂动态图可视化 | 不改善核心问答和实验结论 |
| 大规模更换框架 | 当前 LangGraph、Pydantic、NetworkX 已稳定 |
| 解析 thinking 作为答案 | 违反正式输出合同，版本不稳定且难以审计 |
| 重跑 v1 final | 会造成测试泄漏和历史结果污染 |

## 20. 风险与应对

| 风险 | 概率 | 影响 | 应对 |
| --- | --- | --- | --- |
| revocation 实现错误导致 v1 仍可运行 | 低 | 高 | runner/validator 双重检查和专门测试已通过 |
| Partial-pass 放行错误前提 | 中 | 高 | premise failure 强制零 Claim retained |
| 过滤后答案语义不连贯 | 中 | 中 | 按 retained Claims 重新构造，不删除自由文本片段 |
| Prompt v2 输出截断 | 中 | 中 | 保留 1536 上限，先过结构探针再优化 |
| Packer 配额导致高分证据被挤掉 | 中 | 中 | trace coverage gap，dev 对比和稳定回退 |
| LLM 服务答辩时未启动 | 中 | 高 | 启动 smoke、预热、offline fallback |
| extension 运行中断 | 低到中 | 高 | in-flight state、人工审计、禁止自动重跑 |
| 人工评分偏差 | 中 | 中 | 盲方法标签、随机顺序、公开 rubric 和限制 |
| 修改冻结资产 | 低 | 高 | v1 文件只读、hash validator、Git 审计 |
| 延迟仍较高 | 中 | 中 | 减少重试、Packer、预热，诚实报告真实延迟 |

## 21. 最终完成定义

项目达到当前规划的“完整 LLM Agent 科研版本”，必须同时满足：

1. v1 release 已在未执行状态下被不可变撤销；
2. v2 Evidence Packer、Prompt、ClaimResult、Partial-pass 和完整分阶段 trace 已实现；
3. dev 工程门槛通过；
4. pilot 只做一次冻结前回归且未用于继续调参；
5. v2 implementation manifest 和一次性 release 已冻结；
6. extension 只运行一次并产生完整 receipt；
7. 四方法自动指标和盲评完成；
8. 报告没有夸大 Planner、Dense、Neo4j 或 GraphRAG 范围；
9. Streamlit 能展示真实 LLM、fallback、Verifier 和延迟；
10. 全量测试、数据校验、报告事实检查和 release 哈希全部通过；
11. `PROGRESS.md` 记录每个阶段；
12. 最终 DOCX、PPT 和演示脚本与冻结结果一致。

## 22. 下一步唯一入口

阶段 8.0～8.6 已验收。下一步只进入阶段 8.7：

```text
核对 v2 release preflight
    ↓
用户明确授权下一阶段
    ↓
受控执行 4 方法 × 23 题 extension 一次
    ↓
生成 receipt、版本化结果和 A/B/C/D 盲评表
    ↓
禁止自动重跑或覆盖
```

Stage 8.6 pilot 已消费，不能重跑或继续逐题调参。当前 release 只是 `authorized_not_executed`，本阶段没有运行 extension。Stage 8.7 只能使用 `scripts/run_extension_evaluation_v2.py` 和 release 中的精确 ID 执行一次；任何中断都进入人工审计，不能自动重试整轮。
