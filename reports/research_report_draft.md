# 基于预定义知识图谱的轻量化混合 GraphRAG 机器学习知识问答 Agent

## 科研实践报告草稿

> - 版本：Draft v1
> - 项目路径：`E:\RAGagent`
> - 基线版本：`v1.0-baseline`
> - 当前实验分支：`experiment/day6-main-ablation`
> - 写作状态：方法、基线、主实验、消融、用户确认语义评分和误差分析已填入；技术增强前置审计为 No-Go。

## 摘要

面向机器学习领域知识问答中存在的文本检索语义不足、结构关系难以表达以及生成答案缺少证据约束等问题，本项目构建了一个以六页 scikit-learn 官方文档为文本来源、以预定义领域知识图谱为结构知识的轻量化混合 GraphRAG 问答 Agent。系统将 164 个文档 Section 切分为 180 个稳定 Chunk，并构建包含 50 个实体、100 条 approved 关系的双语知识图谱；每条图关系均绑定真实 Chunk 证据。系统使用 LangGraph 编排查询路由、Vector/Graph/Hybrid 三路检索、离线规则生成、证据验证、一次重试和保守拒答，并通过统一 `GraphRepository` 接口支持 NetworkX 离线后端与可选 Neo4j 后端。

本项目严格区分开发集、演示集、pilot 集和 final 冻结保留集。v1.0 在仅运行一次的 40 题 final 集上取得 97.5% 的 pass/refuse 决策准确率，4 道无答案题全部正确拒答；该指标不等同于回答正确率。进一步在 pilot 集上比较 Vector RAG、Graph Only、Proposed 和 No Verifier 四种配置，Proposed 的决策准确率和无答案拒答准确率分别为 100% 和 100%，而关闭 Verifier 的配置对 4 道无答案题均未作出正确决策。用户确认后的语义复核显示 Proposed 的回答正确性为 0.8625、证据忠实度为 1.0000；评分初稿由 Codex 辅助生成，随后由用户确认，当前状态为 `user_confirmed`。

实验结果显示，在由 approved 图关系定义的保守 gold Chunk 子集上，包含图检索的配置具有更高的 Recall@5；在 pilot 的 4 道无答案题上，Proposed 将拒答准确率从 No Verifier 的 0 提高到 1.0000。同时，唯一 final 错误 T-DF-01 说明保守验证也可能导致过度拒答。项目结果支持在短周期、小型领域知识库中采用“预定义知识图谱 + 文本证据 + 状态化验证”的可复现方案。

**关键词：** 检索增强生成；知识图谱；GraphRAG；LangGraph；证据验证；拒答机制；scikit-learn

---

# 第 1 章 绪论

## 1.1 研究背景

大语言模型能够生成流畅答案，但在专业知识问答中可能出现事实错误、引用不匹配和知识边界不清等问题。传统 RAG 通过从外部文档检索相关片段来约束生成，但单纯文本检索难以稳定表达“算法属于哪个方法族”“算法解决什么任务”“任务使用什么指标”等结构关系。知识图谱擅长表示实体和关系，却可能缺少足够的原文上下文。因此，将文本证据与图结构结合，并在输出前验证引用与图路径，是构建可追溯领域问答系统的一条可行路径。

本项目以 scikit-learn 官方文档为唯一文本来源，在六天科研实践范围内构建一个机器学习知识问答 Agent。系统不追求扩大知识库，而强调数据闭环、统一接口、可复现运行、证据回指和可审计实验。

## 1.2 问题定义

给定自然语言问题 $q$，系统需要在限定知识库 $K=(D,G)$ 中完成：

1. 判断问题意图并选择文本检索、图检索或混合检索；
2. 从文档集合 $D$ 和预定义知识图谱 $G$ 获取证据；
3. 生成由证据编号支撑的回答；
4. 验证 Claim 引用、图路径和问题限定条件；
5. 在证据不足或前提错误时拒答，而不是补充知识库外事实。

## 1.3 研究目标

- 构建小型但闭环完整的 scikit-learn 文本与图谱知识库；
- 实现 Vector、Graph 和 Hybrid 三路检索及动态路由；
- 使用 LangGraph 表达检索、生成、验证、重试和终止状态；
- 设计可解释的证据验证和拒答机制；
- 通过冻结集、主实验、消融和误差分析评估各模块作用；
- 保持项目离线可运行，并为 Neo4j 和后续生成器增强保留统一接口。

## 1.4 研究问题

**RQ1：** 图结构知识与文本检索结合后，是否能够改善关系型问题的检索覆盖和回答完整性？

**RQ2：** Evidence Verifier 对无答案拒答、证据忠实度和过度拒答有什么影响？

**RQ3：** 在不依赖在线 LLM 的条件下，能否构建一个可复现、可追溯且具备完整 Agent 状态流的轻量化系统？

## 1.5 主要贡献

1. 构建了一个以六页 scikit-learn 官方文档为文本证据、以预定义双语知识图谱为结构知识的领域知识库。
2. 设计并实现了基于 LangGraph 的查询理解、动态三路检索、证据融合、离线生成和验证回退流程。
3. 设计了引用合法性、Claim 覆盖、图路径真实性和查询限定条件联合验证机制，并支持无证据问题拒答。
4. 实现了 Neo4j 与 NetworkX 共用的 `GraphRepository` 接口；当前实验使用 NetworkX 离线后端，Neo4j 作为可选部署后端。
5. 使用严格分离的 dev/demo/pilot/final 数据集，保留 final 唯一错误，并完成主实验、No Verifier 消融和 9 案例误差分析。

## 1.6 课题定位

本项目属于**基于预定义知识图谱的轻量化混合 GraphRAG / Knowledge-Graph-Enhanced RAG**。项目借鉴图结构知识与文本证据结合的思想，但**未实现 Microsoft GraphRAG 的完整社区检测、社区摘要和全局检索流水线**，因此不将其描述为 Microsoft GraphRAG 的完整复现。

---

# 第 2 章 相关技术

## 2.1 检索增强生成

RAG 通常由文档切分、向量表示、相似度检索和生成器组成。其优势是能使用外部文档更新知识并提供来源；局限包括短查询语义偏移、复杂关系表达不足和“有引用但不回答问题”的表面接地。本项目使用 TF-IDF 稀疏表示构建本地检索，目的是获得稳定、低依赖和可复现的基线，而不声称使用了神经稠密 Embedding。

## 2.2 知识图谱检索

知识图谱以三元组 $(h,r,t)$ 表示实体关系，适合回答方法族、用途、依赖、优缺点和评价指标等结构问题。本项目的图谱不是从文本自动诱导，而是根据领域 Schema 预定义并人工构建，再将每条关系绑定到官方文档 Chunk。这样可以降低图关系来源不明的问题，但也限制了图谱规模和自动扩展能力。

## 2.3 GraphRAG 思想

GraphRAG 的核心价值在于利用图结构组织和检索相关知识。完整 Microsoft GraphRAG 还包括实体关系抽取、社区检测、社区摘要和全局检索等环节。本项目仅采用“图路径证据 + 原文 Chunk”融合策略，范围更接近 Knowledge-Graph-Enhanced RAG。

## 2.4 LangGraph 状态编排

LangGraph 使用状态图组织多节点 Agent 工作流。项目使用真实 `StateGraph` 实现 route、retrieve、answer、verify、retry 和 finalize 节点，并通过条件边决定通过、重试或拒答。相较于单函数调用，状态图能清晰记录每一步输入输出和停止条件。

## 2.5 证据验证与拒答

仅检查是否存在引用不能证明答案忠实。Verifier 还需要检查：

- Claim 引用 ID 是否存在；
- 引用文本是否覆盖 Claim 主题；
- 图路径是否存在于 approved 图中；
- 问题中的关键属性和限定条件是否得到证据支持；
- 证据不足时是否应扩大检索或拒答。

本项目的拒答是降低无依据输出的一种工程手段，但可能带来过度拒答，final 中的 T-DF-01 即为该权衡的实例。

---

# 第 3 章 数据与知识库构建

## 3.1 文档来源

| ID | 官方页面 | 主要覆盖内容 |
| --- | --- | --- |
| S1 | Linear Models | 线性回归、Ridge、Lasso、逻辑回归 |
| S2 | Support Vector Machines | SVC、SVR、核函数、使用注意事项 |
| S3 | Decision Trees | 分类树、回归树、剪枝、局限 |
| S4 | Ensembles | Bagging、随机森林、AdaBoost、梯度提升 |
| S5 | Clustering | KMeans、DBSCAN、层次聚类 |
| S6 | Metrics and scoring | 分类、回归和聚类评价指标 |

全部来源为 scikit-learn 官方文档，抓取页面和时间戳保存在 `data/raw/html/`。

## 3.2 文档处理与 Chunk

系统使用 BeautifulSoup 和结构化 HTML 解析抽取标题层级与正文，生成 164 个 Section。随后按标题边界和长度切分，并按来源配额保留 180 个稳定 Chunk。Chunk 包含：

- 稳定 `chunk_id`；
- `source_id`、页面标题和标题路径；
- 官方 URL；
- 展示文本与检索文本；
- 抓取时间和内容哈希。

| 来源 | Chunk 数量 |
| --- | ---: |
| S1 | 32 |
| S2 | 18 |
| S3 | 16 |
| S4 | 30 |
| S5 | 38 |
| S6 | 46 |
| **总计** | **180** |

## 3.3 图谱 Schema

图谱包含 7 类节点：Algorithm、Concept、Task、Metric、MethodFamily、Technique 和 Problem。关系类型如下：

| 关系 | 含义 | 数量 |
| --- | --- | ---: |
| BELONGS_TO | 算法属于方法族 | 16 |
| SOLVES | 算法解决任务 | 17 |
| USES | 算法使用概念或技术 | 13 |
| REQUIRES | 算法需要技术 | 5 |
| EVALUATED_BY | 任务或算法由指标评价 | 12 |
| DIFFERS_FROM | 方法或指标存在差异 | 9 |
| HAS_ADVANTAGE | 优势关联 | 14 |
| HAS_LIMITATION | 局限关联 | 7 |
| MITIGATES | 缓解问题 | 7 |
| **总计** |  | **100** |

## 3.4 关系证据绑定

Day 1 关系先以页面级证据和 pending 状态建立。Chunk 生成后，系统为每条关系绑定一个或多个 `evidence_chunk_ids`，再升级为 approved。运行时只读取 approved 关系。最终 100 条关系全部绑定真实 Chunk，形成：

```text
图关系 -> evidence_chunk_ids -> 官方页面标题路径与 URL
```

## 3.5 数据集划分与防泄漏

| 数据集 | 数量 | 用途 |
| --- | ---: | --- |
| dev | 10 | 路由、阈值和回答模板调试 |
| demo | 8 | Streamlit 演示 |
| pilot | 40 | 发现实现缺口及主实验/消融分析，不作为无泄漏最终结果 |
| final | 40 | 冻结保留集，仅运行一次 |

final 与 dev、pilot 题面重合均为 0。final 运行后没有根据 T-DF-01 调整路由、阈值或答案逻辑。

---

# 第 4 章 系统总体架构

## 4.1 总体流程

![图 4-1 系统状态流](figures/architecture.png)

> 图 4-1：系统状态流。静态图片由 `scripts/generate_report_figures.py` 根据当前实现生成。

## 4.2 统一数据结构

核心运行结构包括 `TextEvidence`、`GraphPath`、`LinkedEntity`、`RetrievalResult`、`AnswerPayload`、`VerifyResult` 和 `FinalResponse`。实验层另外定义 `ExperimentRunReport`，记录配置快照、数据集哈希、逐题结果、自动指标和人工指标状态，避免不同实验返回不同格式。

## 4.3 GraphRepository 接口

业务检索器只依赖以下统一能力：实体查找、邻居查询、多跳路径和路径验证。NetworkX 与 Neo4j 分别实现该接口。当前冻结评测和 pilot 实验均使用 NetworkX，以保证无外部数据库环境下可复现；Neo4j 实现和导入脚本已提供，但本报告不声称完成了在线 Neo4j 服务基准测试。

## 4.4 LangGraph 节点与条件边

| 节点 | 输入 | 输出 |
| --- | --- | --- |
| route | query | intent、retrieval mode |
| retrieve | query、route | 文本证据、实体和图路径 |
| answer | retrieval | Claim 与引用编号 |
| verify | answer、retrieval | pass/retry/refuse 与分项分数 |
| retry | failed verification | 扩大后的 Hybrid 检索结果 |
| finalize | verified state | `FinalResponse` |

Verifier 最多触发一次重试，避免无限循环。LangGraph 不可用时保留等价本地状态机，但当前环境已安装并启用 `langgraph 1.0.10`。

## 4.5 运行后端与降级

- 默认图后端：NetworkX；
- 可选图后端：Neo4j，需要 URI、用户和密码；
- 当前向量表示：本地 TF-IDF；
- 向量构建产物：Chroma collection 与本地 TF-IDF 稀疏索引；当前运行时检索读取后者；
- 当前生成器：离线规则/模板；
- 在线 LLM：未启用，不进入 v1.0 实验结果。

---

# 第 5 章 核心方法

## 5.1 查询意图与动态路由

系统使用确定性规则识别 definition、relation、comparison、recommendation、explanation、multi-hop 和 general 等意图，再选择检索模式：

- 定义题优先 Vector；
- 明确关系题优先 Graph；
- 对比、原因、指标推荐和多跳题优先 Hybrid；
- 验证失败后的重试固定使用扩大 Top-K 的 Hybrid。

该设计便于解释和消融，但规则覆盖有限，复杂改写和中英混合术语仍可能路由不准。

## 5.2 Vector 检索

Vector 路径先将中文查询通过领域词典重写为英文检索表达，再使用本地 TF-IDF 向量检索官方文档 Chunk。设查询向量为 $v_q$，Chunk 向量为 $v_i$，以余弦相似度排序：

$$
s_i = \frac{v_q \cdot v_i}{\|v_q\|\|v_i\|}
$$

v1.0 的“Vector”是稀疏 TF-IDF 表示，不是神经稠密 Embedding。`sentence-transformers` 已安装为可选依赖，但当前正式索引没有使用其模型输出。

## 5.3 Graph 检索

Graph 路径先进行实体链接，再根据问题标记约束关系类型，例如“属于”映射 BELONGS_TO，“需要”映射 REQUIRES，“指标”映射 EVALUATED_BY。对多跳题，系统在最多 2 跳范围内搜索，并优先保留最短路径。每条 `GraphPath` 同时返回关系三元组和 evidence Chunk。

## 5.4 Hybrid 融合

Hybrid 同时调用 Graph 与 Vector。融合过程先放入图路径绑定的证据，再加入文本检索结果，以 `chunk_id` 去重并重新编号为 E1...En。当前融合采用稳定顺序与最高分保留策略，没有实现学习式重排序或 RRF；若后续选择 Dense 技术增强，必须在独立 extension holdout 上评估后才能写入本章。

## 5.5 离线回答生成

当前 `GroundedAnswerGenerator` 不调用在线 LLM。它将 approved 图关系转换为中文 Claim，并把每条 Claim 绑定到一个或多个 Evidence ID；定义题可使用图实体的中文描述和对应文本证据。若没有可用 Claim 和文本证据，则生成明确的“当前知识库证据不足”文本。

该生成器的优势是确定、快速、离线和便于审计；局限是语言综合能力弱，复杂多跳题可能只覆盖部分关系，且引用存在不代表回答目标完全匹配。

## 5.6 Evidence Verifier

Verifier 计算 Claim 覆盖 $C$、引用合法性 $V$、路径有效性 $P$ 和检索充分度 $R$：

$$
S = 0.30C + 0.25V + 0.20P + 0.25R
$$

当前阈值为：

- pass threshold：0.80；
- retry threshold：0.55；
- max retries：1；
- minimum vector score：0.08。

除总分外，pass 还要求 Claim 覆盖、引用合法性和路径有效性均达到 0.80。Verifier 还检查查询中的关键限定条件和图谱前提。第一次证据不足可扩大检索；仍不足则拒答。

## 5.7 No Verifier 消融

No Verifier 配置保留完全相同的自适应路由、检索和生成器，只关闭证据验证与重试。其决策固定为 pass，因此可以观察 Verifier 对拒答能力和答案对齐的影响。需要注意，回答生成器本身可能输出“无证据”文本，因此实验同时保留状态决策和答案内容，不能仅凭 pass 标签判断文本是否真的作答。

## 5.8 技术增强决策

**当前状态：No-Go，未作为项目贡献。**

根据冲刺方案的决策树，当前生成器为离线规则模板，因此理论首选是“可插拔真实 LLM 结构化生成 + 离线规则 fallback”。本机 Ollama `0.32.1` 和 `qwen3-vl:8b` 可以真实推理，但 5 次手工受控调用与 1 次自动复验均把 JSON Schema 内容放入 `thinking` 字段，正式 `response` 或 `message.content` 为空。冷启动耗时约 84.7 s，其中模型加载约 67.2 s；后续非首次调用约 1.0～12.0 s。由于正式答案字段的结构化成功率为 0/6，当前组合不满足 `AnswerPayload` 输出合同，不能通过读取 thinking 的临时补丁宣称增强完成。

备选的 Sparse + Dense + Graph 增强也未启动。虽然 `sentence-transformers` 已安装，但本机没有已缓存、可直接加载的文本 Embedding 模型；现有 Hugging Face 缓存为图像相关 CLIP/ViT 模型。按照模型下载和接口稳定性的止损规则，本轮保留 v1.0，不临时下载新模型，不伪造 enhanced 结果。

No-Go 状态下不创建 `extension_holdout`。只有兼容的本地文本模型在 20 次结构化探针中至少成功 19 次后，才重新选择增强 A、冻结独立保留集并开始实现。完整依据见 `reports/technical_enhancement_decision.md`。

---

# 第 6 章 系统实现

## 6.1 软件环境

| 组件 | 当前版本或状态 |
| --- | --- |
| Python | 3.12.7 |
| LangGraph | 1.0.10，真实 StateGraph |
| scikit-learn | 1.5.1 |
| NetworkX | 3.3，当前评测后端 |
| ChromaDB | 1.5.9 |
| Streamlit | 1.37.1 |
| Pydantic | 2.8.2 |
| 操作系统 | Windows 11 |

完整环境快照和 `pip freeze` 位于 `reports/releases/v1.0-baseline/`。

## 6.2 模块结构

| 模块 | 主要职责 |
| --- | --- |
| `src/ingestion/` | HTML 主体解析、Section 和 Chunk |
| `src/retrieval/` | 查询重写、实体链接、Vector/Graph/Hybrid 检索与路由 |
| `src/graph/` | GraphRepository、NetworkX、Neo4j |
| `src/agent/` | 回答生成和 LangGraph 工作流 |
| `src/verification/` | Evidence Verifier |
| `src/evaluation/` | 实验配置、工作流工厂和统一结果 Schema |
| `app/` | Streamlit 演示 |
| `scripts/` | 数据构建、校验、评测、冻结和实验工具 |

## 6.3 Streamlit 演示

界面支持问题输入和 8 道演示题，显示检索模式、意图、证据分数、重试次数和耗时，并分别展示回答、图路径、官方证据和验证详情。桌面 1440×1000 与移动 390×844 视口均完成浏览器验收，正常回答和错误前提拒答均真实点击验证。

## 6.4 可复现与版本冻结

- v1.0 Git tag：`v1.0-baseline`；
- 基线 commit：`04f54f6039023b1165f569efef3a5191c52dde19`；
- 归档 payload：23 个；
- Manifest SHA-256：`2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`；
- GitHub：`https://github.com/zzh1126/RAGagent`。

归档同时保留结果、配置、数据、环境、截图和源代码快照。后续实验位于独立分支，不移动 v1.0 tag。

## 6.5 工程测试

当前全量测试为 `26 passed`，覆盖 GraphRepository、Vector/Graph Retriever、LangGraph 工作流、Verifier 重试与拒答、评测集隔离、实验配置和实验运行器。`pip check` 无依赖冲突，100 条 approved 图关系的证据回指校验通过。

## 6.6 运行命令

```bash
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/validate_evaluation.py
python scripts/validate_experiments.py
pytest -q
streamlit run app/streamlit_app.py
```

final 已冻结，不应再次执行 `run_evaluation.py --split final`。实验运行器也会主动拒绝 final split。

---

# 第 7 章 实验设计与结果

## 7.1 实验原则

1. dev 用于调试，pilot 曾参与发现实现缺口，只用于方法比较和误差分析；
2. final 与 dev/pilot 题面无重合，冻结后仅运行一次；
3. 不针对 final 唯一错误 T-DF-01 再调参并重新声称无泄漏结果；
4. 自动决策准确率、引用率和人工回答正确性是不同指标；
5. pilot 语义评分已由用户确认；本文将其称为用户确认后的语义复核，不将其描述为独立双人标注。

## 7.2 实验配置

| 方法 | 文本检索 | 图检索 | 路由 | Verifier | 生成器 |
| --- | --- | --- | --- | --- | --- |
| Vector RAG | 是 | 否 | 固定 Vector | 否 | 离线规则 |
| Graph Only | 仅图证据 | 是 | 固定 Graph | 否 | 离线规则 |
| Proposed | 是 | 是 | Adaptive | 是 | 离线规则 |
| No Verifier | 是 | 是 | Adaptive | 否 | 离线规则 |

Direct LLM 因没有稳定真实接口而禁用；No Router 为可选消融，当前未运行。

## 7.3 评价指标

设题目总数为 $N$，人工正确性评分 $c_i\in\{0,1,2\}$，忠实度评分 $f_i\in\{0,1,2\}$：

$$
DecisionAccuracy = \frac{\#\ correct\ pass/refuse}{N}
$$

$$
AnswerCorrectness = \frac{\sum_i c_i}{2N}
$$

$$
Faithfulness = \frac{\sum_i f_i}{2N}
$$

$$
Recall@5 = \frac{\#\ questions\ whose\ gold\ chunk\ appears\ in\ top5}{\#\ eligible\ answerable\ questions}
$$

同时统计 Path Validity、Refusal Accuracy、Hallucination Rate、Over-refusal Rate 和本地端到端延迟。当前 gold Chunk 只在可由 approved 图关系保守推导的题上计算，因此 Recall@5 的适用范围必须在表注中说明。

## 7.4 final 冻结结果

| 指标 | 结果 | 正确解释 |
| --- | ---: | --- |
| 问题数 | 40 | final 仅运行一次 |
| 决策准确率 | 0.9750 | 39/40 的 pass/refuse 决策正确，不是问答准确率 |
| 引用率 | 0.9750 | 39 道输出包含引用，不等于忠实度 |
| 平均关键词覆盖 | 0.8375 | 自动字符串覆盖 |
| 平均实体覆盖 | 0.9208 | 检索实体覆盖 |
| 无答案拒答准确率 | 1.0000 | 4/4，样本数较小 |
| 平均本地工作流耗时 | 1.48 ms | 离线规则生成热路径，不是在线 LLM 延迟 |

唯一错误是 T-DF-01：AdaBoost 定义题被保守拒答。该结果保持不变。

## 7.5 pilot 主结果

| 方法 | 决策准确率 | Answer Correctness | Faithfulness | Recall@5 | Path Validity | Refusal Acc. | Hallucination | Latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Vector RAG | 0.9000 | 0.5375 | 0.4875 | 0.8276 | 不适用 | 0.0000 | 0.0000 | 1.325 ms |
| Graph Only | 0.9000 | 0.8375 | 0.9250 | 0.9655 | 1.0000 | 0.0000 | 0.0000 | 1.000 ms |
| Proposed | 1.0000 | 0.8625 | 1.0000 | 0.9655 | 1.0000 | 1.0000 | 0.0000 | 1.700 ms |
| No Verifier | 0.9000 | 0.8000 | 0.8500 | 0.9655 | 1.0000 | 0.0000 | 0.0000 | 1.225 ms |

语义列为用户确认后的复核结果，状态为 `user_confirmed`。评分初稿由 Codex 辅助生成后经用户确认；该流程不等同于独立双人标注。

![图 7-1 Pilot 自动指标对比](figures/pilot_automatic_metrics.png)

![图 7-2 Pilot 用户确认语义指标](figures/pilot_semantic_confirmed.png)

![图 7-3 Pilot 本地工作流耗时](figures/pilot_latency.png)

## 7.6 结果分析

**回答 RQ1：** Graph Only、Proposed 和 No Verifier 在保守 gold 子集上的 Recall@5 均为 0.9655，高于 Vector RAG 的 0.8276。用户确认的语义评分中 Graph Only 和 Proposed 的回答正确性也明显高于 Vector RAG，说明图关系有助于结构问题，但多跳路径不完整仍会降低答案覆盖。

**回答 RQ2：** Proposed 对 4 道无答案题全部拒答，No Verifier 的拒答准确率为 0。No Verifier 的用户确认忠实度低于 Proposed，主要原因是回答虽然带引用，却可能与问题限定条件不匹配。当前规则生成器没有观察到明显无证据专业事实，因此本次用户确认样本中的 Hallucination Rate 为 0；Verifier 的主要收益体现为拒答和问题对齐，而不是该小样本中的事实幻觉下降。

**回答 RQ3：** 系统在 NetworkX、TF-IDF 和离线规则生成器下可独立运行，真实 LangGraph、数据哈希、配置指纹、归档清单和 26 项测试提供了可复现基础。

## 7.7 No Verifier 消融

| 方法 | Adaptive 路由 | Verifier | 决策准确率 | Faithfulness | 拒答准确率 | 平均重试 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Proposed | 是 | 是 | 1.0000 | 1.0000 | 1.0000 | 无答案题中 3/4 触发一次重试 |
| No Verifier | 是 | 否 | 0.9000 | 0.8500 | 0.0000 | 0 |

两者具有相同检索与生成配置，差异集中在验证器。该结果支持 Verifier 对错误前提、属性不存在和知识库外问题的拒答作用。

## 7.8 final 错误案例 T-DF-01

| 项目 | 内容 |
| --- | --- |
| 问题 | 请解释 AdaBoost 的基本含义。 |
| 期望行为 | 给出 AdaBoost 定义并引用 Ensemble 页面 |
| 实际行为 | Verifier 判定证据不足并拒答 |
| 类型 | Over-refusal / 定义证据充分度判断过严 |

可能原因是直接定义 Chunk 排序不足、标题与实体奖励不足，以及统一阈值对定义题偏保守。可考虑定义意图专用检索奖励和阈值，但不能在已观察 final 后修改并重新报告该成绩。

## 7.9 pilot 误差分析

| ID | 问题 | 阶段 | 主要原因 | 改进方向 |
| --- | --- | --- | --- | --- |
| E01 | F-NA-01 | verification/finalization | 生成器已输出拒答文本，但 No Verifier 状态仍为 pass | 分离内容级拒答与验证决策 |
| E02 | F-NA-02 | entity/text/verification | 参考文献提及 XGBoost，但无缺失值证据 | 实体范围与属性证据门控 |
| E03 | F-NA-03 | query alignment | 实体存在但学习率属性不存在 | 属性白名单与不存在属性检测 |
| E04 | F-NA-04 | premise validation | 检索到聚类事实但未明确否定错误前提 | 图谱前提校验与纠正生成 |
| E05 | F-SH-04 | entity/graph retrieval | Ridge 查询扩展成多个算法的 SOLVES 关系 | 算法实体 + USES 关系联合约束 |
| E06 | F-MH-01 | multi-hop/fusion | 未完成 RF--Tree--TreeFamily 路径 | 按中间实体拆分并合并最短路径 |
| E07 | F-MH-03 | multi-hop/fusion | 只覆盖特征缩放，遗漏高维问题 | 全目标实体路径覆盖检查 |
| E08 | F-DF-05 | entity/generation | 通用分类任务优先于 SVC 算法 | 定义题优先精确 Algorithm 实体 |
| E09 | F-MS-02 | routing/graph retrieval | 返回回归算法而非 MSE/R2 指标 | 优先 Task--EVALUATED_BY--Metric |

用户确认版误差分析见 `reports/experiments/pilot_error_analysis.md`；原始分析草稿 `pilot_error_analysis_draft.md` 保留用于审计。

![图 7-4 Pilot 各题型决策准确率](figures/pilot_category_decision_accuracy.png)

## 7.10 有效性威胁

- final 仅 40 题，无答案题仅 4 道，统计置信度有限；
- pilot 曾用于发现实现缺口，不能视为无泄漏最终结果；
- 语义评分由 Codex 辅助生成并经用户确认，但未进行独立双人标注或一致性统计；
- gold Chunk 由图关系保守推导，仅覆盖部分题；
- 规则生成器限制了对真实 LLM 幻觉问题的外推；
- 延迟为单机热路径，没有冷启动与在线服务基准；
- 知识库仅包含六页文档，结论不应泛化到完整 scikit-learn。

---

# 第 8 章 总结与展望

## 8.1 研究结论

本项目完成了一个可运行、可追溯和可复现的 scikit-learn 知识问答 Agent。系统使用预定义知识图谱表达机器学习结构关系，使用官方文档 Chunk 提供文本证据，并通过 LangGraph 将检索、生成、验证和拒答组织成状态流。final 冻结结果显示系统在该限定知识库与 40 题测试集上具有较高的决策稳定性；pilot 消融进一步说明图检索改善结构证据覆盖，Verifier 对无答案拒答和问题对齐具有直接作用。

## 8.2 局限

1. 文本检索仍为 TF-IDF，复杂语义改写能力有限；
2. 生成器为规则模板，答案综合与自然表达能力有限；
3. 多跳检索对中间实体和关系方向敏感；
4. Verifier 可能产生过度拒答；
5. 数据集和知识库规模较小；
6. Neo4j 代码接口已实现，但当前实验使用 NetworkX，未提供独立在线 Neo4j 性能结果；
7. 用户确认的语义评分来自单一确认流程，尚未进行双人一致性评估。

## 8.3 后续工作

- 在独立 extension holdout 上实施且只实施一个技术增强；
- 完善属性级问题对齐和错误前提验证；
- 改进多目标实体和多跳路径覆盖；
- 增加冷启动、热启动和分阶段延迟统计；
- 扩大人工标注集并进行双人一致性评估；
- 在不改变 v1.0 final 结果的前提下研究定义题检索充分度。

## 8.4 当前可提交性

技术增强前置审计当前为 No-Go，但 v1.0 已包含完整知识库、三路检索、LangGraph、Verifier、Streamlit、冻结结果、主实验、消融和误差分析，可作为科研实践保底版本提交。

---

# 参考文献（草稿）

[1] Pedregosa F, Varoquaux G, Gramfort A, et al. Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research*, 2011, 12: 2825-2830.

[2] Lewis P, Perez E, Piktus A, et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS*, 2020.

[3] Edge D, Trinh H, Cheng N, et al. From Local to Global: A Graph RAG Approach to Query-Focused Summarization. arXiv:2404.16130, 2024.

[4] scikit-learn User Guide: Linear Models. https://scikit-learn.org/stable/modules/linear_model.html

[5] scikit-learn User Guide: Support Vector Machines. https://scikit-learn.org/stable/modules/svm.html

[6] scikit-learn User Guide: Decision Trees. https://scikit-learn.org/stable/modules/tree.html

[7] scikit-learn User Guide: Ensembles. https://scikit-learn.org/stable/modules/ensemble.html

[8] scikit-learn User Guide: Clustering. https://scikit-learn.org/stable/modules/clustering.html

[9] scikit-learn User Guide: Metrics and scoring. https://scikit-learn.org/stable/modules/model_evaluation.html

[10] LangGraph Documentation. https://langchain-ai.github.io/langgraph/

[11] Neo4j Documentation. https://neo4j.com/docs/

[12] NetworkX Documentation. https://networkx.org/documentation/stable/

---

# 附录 A 可复现实验命令

```bash
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/validate_evaluation.py
python scripts/validate_experiments.py
python scripts/validate_report_claims.py
python scripts/generate_report_figures.py --check
python scripts/freeze_baseline.py --verify
pytest -q

# pilot 实验结果已经生成；运行器会拒绝覆盖已有文件
python scripts/run_experiments.py --dry-run
python scripts/validate_scoring.py
```

# 附录 B 待完成清单

- [x] 用户已确认 `human_scoring_pilot_confirmed.csv` 中 160 行 pilot 语义评分；原始 preliminary 文件仅作审计留痕；
- [x] 完成技术增强前置审计并将 No-Go 决策写入 5.8；
- [ ] 仅在增强重新获准后冻结 extension holdout，并在实现完成后只运行一次；
- [x] 已生成 5 张实验/架构图并用静态 PNG 替换 Mermaid；
- [ ] 将 Markdown 定稿转换为 DOCX 并完成分页、图表编号和参考文献格式；
- [ ] 制作答辩 PPT、演示脚本和录屏。
