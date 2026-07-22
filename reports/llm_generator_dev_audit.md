# LLM Answer Generator 开发集审计

## 审计边界

本审计只使用 10 题 `dev_questions.jsonl`，用于实现期调试和门槛检查。没有运行 `final` 或 `extension`，没有生成 extension 输出，也没有解除 extension 执行锁。以下结果不能作为独立保留集结论。

当前主链路为规则 Router + Vector/Graph/Hybrid Retriever + `qwen3:4b` LLM Answer Generator + Evidence Verifier，并在 LLM 服务、超时、空 content 或 Schema 失败时回退 `GroundedAnswerGenerator`。Planner 仍为规则实现。

## 三轮开发结果

| 运行 | Decision Accuracy | Final-payload Structured Success | Fallback Rate | Mean Total Latency | 说明 |
| --- | ---: | ---: | ---: | ---: | --- |
| initial | 0.7000 | 0.9000 | 0.1000 | 12295.4 ms | DEV02 JSON 截断后 fallback；DEV03/05/06 过度拒答 |
| postfix | 0.7000 | 0.9000 | 0.1000 | 11485.8 ms | 修复 SVC 中英改写；DEV02 仍截断；DEV03/05/10 过度拒答 |
| candidate | 0.6000 | 1.0000 | 0.0000 | 11437.7 ms | `num_predict=1536` 后 10/10 结构成功；DEV02/03/05/10 过度拒答 |

候选运行中两道无答案题均正确拒答，没有观察到错误放行；6 道题正确决策，4 个错误全部是 answerable 问题被拒绝。规则 dev 基线为 10/10，因此当前结果不能声称 LLM Generator 提高了决策准确率。

候选题集 SHA-256 为 `7db6c94473797ee63c03b16c9daaad2936118780277bd97bbc3906cff32533e3`，运行时 settings SHA-256 为 `245af4032950698f5e8b9d6ca556a6380b5ada170cee8d8f429a56bb48bafece`。

## 实现期修复

1. 将 LLM wire Schema 的 `claims` 改为必填，并要求每条 Claim 至少绑定一个文本证据 ID；
2. 要求每条 LLM Claim 提供 `supporting_quotes`，且 quote 必须是对应 Chunk 原文的归一化子串；
3. 增加保守的中英关键术语覆盖检查，拦截“引用存在但机制细节不受支持”的假阳性；
4. 增加“装袋法”“缩放特征”等查询改写，并在生成上下文中为图证据与 query-relevant 文本证据保留名额；
5. 将 Schema 修复提示限制为字段路径和错误类型，不保存或回传无效 content；
6. 将 `num_predict` 从 768 调整为 1536，DEV02 的 `root:json_invalid` 截断问题由两次失败变为一次成功；
7. 用户可见答案始终由结构化 Claim 及 E/P ID 重建，不直接展示模型自由生成的 `answer` 字段，防止额外事实绕过 Claim 级校验。

## 已知限制

- `supporting_quotes` 与双语术语覆盖是确定性下界检查，不等同于完整自然语言蕴含判断；
- DEV03 的 F1 与类别不平衡结论、DEV05 的 AdaBoost 机制缺少足够直接的当前 Chunk 证据；
- DEV02 和 DEV10 显示保守术语检查可能把可解释但 quote 不完整的 Claim 判为不支持；
- 候选平均端到端延迟约 11.44 s，明显高于约 2.2 ms 的离线规则 dev 基线；
- 当前只有 10 道开发题，不能进行统计显著性推断。
- 三份 dev JSON 生成时只保存最终 `AnswerPayload` 的 generation attempts/latency；端到端 `mean_latency_ms` 有效，但分阶段生成统计可能漏掉 Verifier 重试前的调用。候选运行后代码已新增逐调用 `generation_trace`，正式 extension 指标必须按完整 trace 聚合，不回写或美化历史 dev 文件。

## 当前决定

真实 LLM 已进入答案生成节点，结构化输出、引用边界、Verifier 和运行时 fallback 已形成可运行闭环；但 dev 决策结果尚未优于规则基线，extension 保留集继续锁定。下一阶段应先冻结实现/Prompt/配置哈希并设计一次性 extension 执行与盲评流程，不再使用 dev 反复调参。
