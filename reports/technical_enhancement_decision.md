# 技术增强前置审计与决策记录

## 决策信息

| 项目 | 结论 |
| --- | --- |
| 审计日期 | 2026-07-22 |
| 审计分支 | `experiment/day6-main-ablation` |
| 重新进入分支 | `experiment/llm-agent-v2` |
| 当前生成器 | `qwen3:4b` LLM Answer Generator；`GroundedAnswerGenerator` 作为运行时 fallback |
| 理论首选增强 | 增强 A：可插拔真实 LLM 结构化生成 + 离线规则 fallback |
| 初始决定 | `qwen3-vl:8b` 为 **No-Go**，保留 v1.0 |
| 重新进入复验 | `qwen3:4b`：**Generator Go，Planner No-Go** |
| 当前实施范围 | LLM Answer Generator、intent-aware Evidence Packer、Verifier 与规则 fallback 已接线；不接入 LLM Query Planner |
| final 处理 | 不重跑、不调参、不改变原始结果 |
| extension holdout | 23 题从未运行；v1 release 已在执行前撤销，v2 四方法合同已冻结但尚无 release |

## 前置条件审计

### 增强 A：真实 LLM 结构化生成

本机存在真实本地推理条件，而不是模拟接口：

- Ollama `0.32.1` 已安装并监听 `127.0.0.1:11434`；
- 已安装模型 `qwen3-vl:8b`，大小约 6.1 GB；
- 不需要把本地服务伪装成在线 API，也没有读取或输出任何密钥。

但当前模型与服务组合未通过生成器输出合同。初始 5 次手工探针加 1 次自动复验共 6 次，均出现：

```text
JSON Schema 内容本身可生成
    ↓
内容进入 thinking 字段
    ↓
正式 response / message.content 长度为 0
    ↓
AnswerPayload 无法从正式答案字段解析
```

关键测量：

| 项目 | 结果 |
| --- | ---: |
| 冷启动单次墙钟耗时 | 84.7 s |
| 其中模型加载耗时 | 67.2 s |
| 后续非首次调用探针 | 约 1.0～12.0 s |
| 正式答案字段结构化成功 | 0/6 |
| thinking 中观察到合法 JSON | 是 |

不能把 `thinking` 字段直接当作正式回答，原因是：

1. 这会依赖模型内部推理通道，而不是稳定的生成接口合同；
2. 后续模型或 Ollama 版本可能改变 thinking 格式；
3. 项目要求结构化答案进入可验证的正式字段，再交给同一个 Evidence Verifier；
4. 以临时解析补丁宣称“真实 LLM 增强已完成”会夸大当前成熟度。

因此，增强 A 当前判定为 No-Go。

### 增强 B：Sparse + Dense + Graph

`sentence-transformers` 和 PyTorch 已安装，但这只代表代码依赖存在。本机 Hugging Face 缓存中没有可直接加载的文本 Embedding 模型，现有缓存均为 CLIP/ViT 图像相关模型。根据冲刺方案“优先使用已能在本机加载的多语言模型”和“模型下载不稳定时止损”的规则，增强 B 也不具备立即实施条件。

此外，初始审计时生成器仍是离线模板，按照原决策树应优先解决真实生成能力，不应为了绕开增强 A 的前置失败而临时切换到增强 B。

## 初始决定（已由下方复验更新）

本轮不实现任何技术增强，不生成伪造的 enhanced 指标，也不把预检结果写成科研贡献。项目继续以 `v1.0-baseline` 和已完成的主实验、No Verifier 消融、用户确认语义复核及误差分析作为可交付版本。

当前也不创建 `extension_holdout`。该数据集的用途是对一个已经选定且通过前置检查的增强做一次性独立比较；在 No-Go 状态下提前创建会增加调试或误用风险，没有实验价值。

## 重新进入复验：qwen3:4b

在当时尚未修改 Agent 主链路的前提下，已新增并完成纯文本模型复验：

- 新建分支 `experiment/llm-agent-v2`，基线提交仍为 `02a122c`；
- 将新 Ollama 模型目录固定为 `E:\ollama-models`，C 盘原 `qwen3-vl:8b` 文件未删除；
- 安装纯文本模型 `qwen3:4b`，Q4_K_M，模型文件约 2.5 GB；
- 先完成三类各 1 次烟测，再完成三类各 20 次正式探针；
- `think=false`，所有请求均只读取 `message.content`，不记录 thinking 内容；
- 初始 Full Agent 门槛失败报告保留为 `reports/llm_probe_qwen3_4b_full_agent_initial.json`；
- 当前正式报告为 `reports/llm_probe_qwen3_4b.json`。

正式 60 次结果：

| 探针类型 | Schema 成功 | 语义成功 | 结论 |
| --- | ---: | ---: | --- |
| 简单状态 Schema | 20/20 | 20/20 | 通过 |
| QueryPlan | 20/20 | 1/20 | Planner 不通过 |
| 嵌套 AnswerPayload | 20/20 | 20/20 | Generator 通过 |
| **合计** | **60/60** | **41/60** | Generator-only Go |

其他观测：

- 空 `message.content`：0/60；
- 非空 thinking：0/60；
- 冷启动墙钟耗时：20.698 s；
- 热请求平均耗时：0.930 s；
- 热请求 P95：1.294 s；
- QueryPlan 的 19 次语义失败均为合法 JSON，但把关系题误判为 `comparison` 且漏掉实体，因此不能用 Schema 成功率替代 Planner 准确率。

复验后的正式决定：

1. 允许进入 LLM Answer Generator 的实现阶段；
2. 暂不实现 LLM Query Planner，继续使用现有规则 Router；
3. 独立 23 题 `extension_holdout`、评分合同、完整 trace 口径与实现 bundle 已冻结；历史 v1 release `extension-qwen3-4b-v1-bdedf7dc` 后续在任何执行前撤销，v2 四方法合同已单独冻结；
4. final 继续只读，原 v1.0 结果、配置指纹和归档哈希不变；
5. 不实施 Dense Retrieval，也不把 Planner 描述为已经可用。

## 重新进入条件

以下条件用于完成增强 A。当前条件 1～5 已满足，条件 6 始终有效；实现提交 `bdedf7d` 和模型 digest 已进入 release record，但 dev 结果尚未证明增强效果：

1. 使用适合纯文本指令的本地模型，或修复当前 Ollama/model 组合，使 JSON Schema 输出进入 `message.content`；
2. 在合成探针和 dev 上连续执行至少 20 次结构化输出，成功不少于 19 次；
3. 失败、超时和解析异常均能自动回退 `GroundedAnswerGenerator`；
4. 输出仍使用 `AnswerPayload`，并由现有 Evidence Verifier 复核；
5. 通过前置探针后，再冻结 23 题 `extension_holdout`，且只运行一次；
6. 不使用原 final 调参或重新报告成绩。

## 可复验命令

```bash
python scripts/check_enhancement_readiness.py
python scripts/check_enhancement_readiness.py --probe-ollama --model qwen3-vl:8b
python scripts/probe_llm_structured.py --model qwen3:4b --runs-per-schema 20 --target-gate generator --unload-before-run
python scripts/validate_llm_probe.py
python scripts/validate_evidence_packer.py
python scripts/validate_atomic_claim_prompt.py
python scripts/validate_extension_holdout.py
python scripts/smoke_llm_client.py --timeout 180
```

`check_enhancement_readiness.py` 只输出环境变量名称和模型清单，不输出密钥值；正式探针报告保存结构化解析结果、哈希和计时，但不保存 thinking 内容。统一 Client 的合成 smoke 已分别完成一次冷启动和一次热调用，均一次成功，耗时约 21.14 s 与 0.58 s。随后默认主链路已接入 LLM Generator；候选 dev 为 10/10 结构成功、0 fallback、6/10 决策正确，不能据此声称增强优于规则基线。

阶段 8.1 已进一步接入 `intent_aware_v2` Evidence Packer。它在不修改完整 `RetrievalResult` 的前提下完成稳定去重、图路径绑定、题型配额、字符预算、可见 E/P/R ID 边界和逐次 trace。dev/pilot 50 题只读合同检查平均选择 4.38 条证据、最长上下文 7,783 字符，仅 `F-NA-01` 出现预期空证据 gap。该结果只证明 Packer 工程合同成立；当时真实问题“随机森林为什么更稳定”仍因严格 Claim 术语覆盖在一次重试后拒答，并将剩余工作定位为原子 Claim Prompt v2 和 Claim-level `PARTIAL_PASS`。阶段 8.2 的当前结果见下段。

阶段 8.2 已接入原子 Claim Prompt v2：wire Schema 限制 1～4 条 Claim，并区分 E/P/R ID、逐字 quote 和无证据子问。四场景正式合成探针为 `20/20`，且不保存 Prompt、模型正文、quote 或 thinking。随机森林真实 smoke 的 Claim coverage 从 0.3333 提高到 0.5000，但严格整题 Verifier 仍拒答；当时将下一阶段限定为 Claim-level `PARTIAL_PASS`。该开发观察不能证明增强优于规则基线。

阶段 8.3 已接入 Claim-level Verifier：逐 Claim 输出 C ID、supported/retained、有效 E/P ID 和 reason codes；默认 LLM 使用 partial-pass，规则基线继续 strict，并保留 LLM strict override。DEV02 脱敏 warm smoke 保留 2/4 Claim、删除 2/4 Claim，返回 `partial_pass`，retry=0、generation calls=1、unsupported leakage=0。该结果只证明单题过滤机制成立，不是完整 dev/pilot 回归或增强有效性结论；extension 继续锁定。

阶段 8.4 已完成运行时 trace 与演示可观测性：`FinalResponse` 保存 routing、逐次 retrieval/generation/packing/verification、retry branch 和 end-to-end；GenerationCall 增加 provider/model 与 requested/actual backend。Streamlit 只在 cached workflow 启动时发送固定合成预热，不读取评测题面，问题缓存保持 disabled。pass、partial-pass、refuse 和 Ollama unavailable fallback 均完成桌面/移动 browser smoke。该阶段没有执行完整 dev/pilot/final/extension，也不能据此声称延迟或回答质量已经总体改善。

阶段 8.5 已完成 10 道 dev 的完整工程回归。候选为 10/10 结构成功、0 fallback、9/10 自动决策、2/2 无答案正确拒答、1/8 answerable over-refusal、3/10 retry 和 0 unsupported Claim leakage。DEV02/03/10 返回过滤后的 `partial_pass`；DEV05 因固定六页语料没有 AdaBoost 样本权重机制原文继续拒答。Verifier 只增加大小写、ASCII/Unicode 连字符、弯引号和 `overfit`/`do not generalize` 直接变体的保守规范化，实质改写 quote 的负向测试仍拒绝。Dense Retrieval 不触发，因为唯一剩余错误不是正确 Chunk 未召回。该 dev 已用于调试，不能证明增强优于规则基线；下一步只进入一次 pilot 冻结前回归。
