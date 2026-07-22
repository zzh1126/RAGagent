# Pilot Error Analysis Draft

This is an agent-assisted preliminary draft. It is not a claim of independent human annotation.
The final report should retain the raw answers and have a reviewer confirm or revise each score.

| Case | Question ID | Category | Methods / observed issue | Stage and root cause | Proposed improvement |
| --- | --- | --- | --- | --- | --- |
| E01 | `F-NA-01` | no_answer | vector_rag: correctness=2, decision=pass<br>graph_only: correctness=2, decision=pass<br>proposed: correctness=2, decision=refuse<br>no_verifier: correctness=2, decision=pass | **verification/finalization**<br>答案生成器已输出无证据拒答句，但关闭 Verifier 后状态仍被标记为 pass，决策标签与文本语义不一致。 | 为 AnswerPayload 增加显式 refusal_intent，并让实验统计同时报告内容级拒答与验证器决策。 |
| E02 | `F-NA-02` | no_answer | vector_rag: correctness=0, decision=pass<br>graph_only: correctness=2, decision=pass<br>proposed: correctness=2, decision=refuse<br>no_verifier: correctness=0, decision=pass | **entity linking/text retrieval/verification**<br>XGBoost 只在参考文献片段中出现，稀疏检索返回了相关名称但没有缺失值处理证据；Verifier 能识别限定条件未覆盖。 | 增加实体范围门控和属性级证据检查，区分正文主题实体与参考文献提及。 |
| E03 | `F-NA-03` | no_answer | vector_rag: correctness=0, decision=pass<br>graph_only: correctness=0, decision=pass<br>proposed: correctness=2, decision=refuse<br>no_verifier: correctness=0, decision=pass | **query alignment/verification**<br>随机森林实体存在，但知识库没有学习率属性；无验证流程仍返回随机森林定义或普通关系。 | 增加属性白名单与不存在属性检测，在生成前验证实体和询问属性是否共同得到证据支持。 |
| E04 | `F-NA-04` | no_answer | vector_rag: correctness=1, decision=pass<br>graph_only: correctness=1, decision=pass<br>proposed: correctness=2, decision=refuse<br>no_verifier: correctness=1, decision=pass | **premise validation/verification**<br>检索能找到 KMeans 的聚类关系，但无验证流程只陈述聚类事实，没有明确否定监督分类这一错误前提。 | 对“是否属于/是否解决”问题增加图谱前提校验，并生成明确的否定与纠正答案。 |
| E05 | `F-SH-04` | single_hop | vector_rag: correctness=0, decision=pass<br>graph_only: correctness=0, decision=pass<br>proposed: correctness=0, decision=pass<br>no_verifier: correctness=0, decision=pass | **entity linking/graph retrieval**<br>关系查询没有锁定 Ridge--USES--正则化，而是扩展到多个线性模型的 SOLVES--回归关系。 | 使用问题中的算法实体和 USES 关系类型联合约束邻居检索，避免泛化到同族算法。 |
| E06 | `F-MH-01` | multi_hop | vector_rag: correctness=1, decision=pass<br>graph_only: correctness=0, decision=pass<br>proposed: correctness=0, decision=pass<br>no_verifier: correctness=0, decision=pass | **multi-hop retrieval/fusion**<br>系统优先返回随机森林直属的集成学习关系，没有完成随机森林--USES--决策树--BELONGS_TO--树模型路径。 | 多跳题按显式中间实体拆分目标，并合并每个目标的最短路径；报告中同时说明随机森林直属方法族的本体歧义。 |
| E07 | `F-MH-03` | multi_hop | vector_rag: correctness=0, decision=pass<br>graph_only: correctness=1, decision=pass<br>proposed: correctness=1, decision=pass<br>no_verifier: correctness=1, decision=pass | **multi-hop retrieval/fusion**<br>仅返回支持向量分类需要特征缩放，未继续连接特征缩放与高维问题。 | 要求多跳检索覆盖全部已链接目标实体，并在缺少任一目标路径时降低完整性分数。 |
| E08 | `F-DF-05` | definition | vector_rag: correctness=1, decision=pass<br>proposed: correctness=1, decision=pass<br>no_verifier: correctness=1, decision=pass | **entity linking/generation**<br>定义题把通用分类任务排在支持向量分类算法之前，生成了分类定义而非 SVC 定义。 | 定义题优先选择问题中精确命中的 Algorithm 实体，再以任务实体作为补充上下文。 |
| E09 | `F-MS-02` | metric_selection | vector_rag: correctness=0, decision=pass<br>graph_only: correctness=0, decision=pass<br>proposed: correctness=0, decision=pass<br>no_verifier: correctness=0, decision=pass | **routing/graph retrieval**<br>指标选择题返回了可解决回归的算法列表，没有沿回归任务的 EVALUATED_BY 入边找到均方误差和 R2。 | 指标选择路由固定优先查询 Task--EVALUATED_BY--Metric，并支持从任务节点聚合多个指标。 |

## Required Follow-up

1. Confirm correctness and faithfulness scores against the full answer and cited source chunks.
2. Treat irrelevant but supported text as an answer-relevance failure unless it also introduces unsupported professional facts.
3. Keep these improvements as future-work analysis; do not change or rerun the frozen final result.
