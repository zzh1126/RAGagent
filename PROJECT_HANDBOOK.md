# scikit-learn 知识问答 Agent 项目全量知识手册

## 1. 文档用途与事实基线

这是一份项目交接、复习和答辩用的全量知识手册。阅读后应能够回答：项目为什么做、做了什么、每个模块如何工作、数据从哪里来、指标如何计算、当前结果是什么、哪些结论可以说、哪些结论不能说，以及下一步为什么这样安排。

| 项目 | 当前事实 |
| --- | --- |
| 工作区 | `E:\RAGagent` |
| GitHub | `https://github.com/zzh1126/RAGagent.git` |
| 当前分支 | `experiment/llm-agent-v2` |
| 本文审计基线 | 阶段 8.10 完成状态 |
| 审计日期 | 2026-07-25 |
| v1.0 标签 | `v1.0-baseline` |
| 当前工作流引擎 | LangGraph `1.0.10` |
| 当前默认图后端 | NetworkX `3.3` |
| 当前默认生成器 | Ollama `qwen3:4b`，失败时回退规则生成器 |
| 正式基线状态 | v1.0 规则基线已冻结、可复验 |
| LLM 增强状态 | Evidence Packer、原子 Claim Prompt v2 与 Claim-level Partial-pass 已实现；Stage 8.7 四方法实验、Stage 8.8 用户确认盲评及 8.8c 图表误差分析均已完成 |
| extension 状态 | 23 题已按 v2 合同执行且只执行一次；v1 有效状态为 `revoked_before_execution`；v2 有效执行状态为 `completed_once` |
| 正式报告状态 | 30 页 A4 DOCX 已生成并完成逐页渲染视觉验收；源稿、生成器、图表和输出哈希由 manifest 与自动测试保护 |
| 答辩材料状态 | 14 页 16:9 可编辑 PPTX 已生成并完成全页渲染、联系表和布局验收；逐页讲稿与故障预案待下一阶段完成 |

事实优先级如下：

1. 当前代码、配置和数据文件；
2. `PROGRESS.md` 中日期最新的阶段记录；
3. `reports/releases/v1.0-baseline/` 中不可变的基线归档；
4. 其他历史报告；
5. 未来计划文档。

历史文档可能描述当时状态。例如 v1 release 文件保留创建时的 `authorized_not_executed`，但其不可变 revocation record 已取消执行权。本文会明确区分“历史文件值”“当前有效状态”“已实现”“已评测”和“计划实现”。

## 2. 一句话定义项目

本项目是一个面向 scikit-learn 六个官方文档页面的、基于预定义双语知识图谱与官方文本证据的轻量化 Knowledge-Graph-Enhanced RAG 问答 Agent。

系统使用规则 Router 选择文本、图或混合检索；使用 NetworkX 或可选 Neo4j 查询结构关系；使用 TF-IDF 检索官方文档 Chunk；通过 LangGraph 编排检索、生成、验证、重试与拒答；当前默认使用本地 `qwen3:4b` 生成结构化 Claim，并在运行故障时回退到确定性规则生成器。

## 3. 准确的课题表述

推荐表述：

> 基于预定义知识图谱的混合 GraphRAG / Knowledge-Graph-Enhanced RAG scikit-learn 知识问答 Agent。

更完整的报告表述：

> 本项目借鉴 GraphRAG 将图结构知识与文本证据结合的思想，针对预定义领域知识图谱和短周期科研实践，采用图检索与本地文本检索相结合的轻量化混合方案，并通过证据验证器约束回答和拒答。

不能声称：

- 已实现完整 Microsoft GraphRAG；
- 已实现社区检测、社区摘要或全局搜索；
- 已自动从语料抽取完整知识图谱；
- 已实现可靠的 LLM Query Planner；
- LLM Agent 已在独立 extension 上证明优于规则基线；
- 当前 Chroma 使用了神经语义 Embedding。

## 4. 项目目标、对象与研究问题

### 4.1 项目目标

1. 在固定、可追溯的知识范围内回答 scikit-learn 基础知识问题；
2. 将结构关系与官方文档原文结合，而不是只做关键词检索；
3. 为每个关键结论绑定文本证据、图路径或关系 ID；
4. 在证据不足、属性不存在或问题前提错误时拒答；
5. 保持本地可运行、可复现、可消融、可演示；
6. 通过冻结数据、配置、哈希和实验合同减少测试泄漏。

### 4.2 目标用户

- 学习 scikit-learn 基础算法、任务、指标和模型关系的学生；
- 需要查看“结论来自哪段官方文档”的答辩评审者；
- 需要复现实验或继续开发该项目的维护者。

### 4.3 研究问题

| 研究问题 | 对应实验 |
| --- | --- |
| 图结构是否改善结构化问题的证据覆盖和回答质量？ | Vector RAG、Graph Only、Proposed 对比 |
| Verifier 是否改善拒答、问题对齐和证据忠实度？ | Proposed 与 No Verifier 消融 |
| 系统是否可以本地、可追溯、可复现地运行？ | NetworkX、TF-IDF、LangGraph、归档和自动校验 |
| LLM 是否改善可读性和完整性，同时保持证据忠实度？ | No Verifier 提高 Correctness/Readability 但产生 6/22 hallucination；Partial-pass 保持 0 hallucination 和 0.9375 Faithfulness，但 Correctness 未超过 Rule |
| Partial-pass 是否降低过度拒答？ | 用户确认 over-refusal 相对 Strict 从 16/19 降到 5/19，同时 0/16 hallucination；该改善不等于总体正确性提升 |

## 5. 项目边界

### 5.1 固定知识范围

知识库只包含六个 scikit-learn 官方用户指南页面：

| ID | 主题 | 官方 URL | Chunk 数 |
| --- | --- | --- | ---: |
| S1 | Linear Models | `https://scikit-learn.org/stable/modules/linear_model.html` | 32 |
| S2 | Support Vector Machines | `https://scikit-learn.org/stable/modules/svm.html` | 18 |
| S3 | Decision Trees | `https://scikit-learn.org/stable/modules/tree.html` | 16 |
| S4 | Ensembles | `https://scikit-learn.org/stable/modules/ensemble.html` | 30 |
| S5 | Clustering | `https://scikit-learn.org/stable/modules/clustering.html` | 38 |
| S6 | Metrics and scoring | `https://scikit-learn.org/stable/modules/model_evaluation.html` | 46 |
| 合计 | 6 个页面 |  | 180 |

HTML 缓存于 `data/raw/html/`，当前 manifest 显示六页都在 2026-07-22 抓取成功。运行时不需要重新联网抓取这些页面。

### 5.2 明确不覆盖

- 完整 scikit-learn API；
- 六页之外的算法、参数和行为；
- 实时新闻或最新版本差异；
- 代码执行、训练模型或自动调参；
- 医疗、法律、金融等专业建议；
- 通用开放域知识问答。

## 6. 总体架构

```text
中文问题
   ↓
规则 IntentRouter
   ↓
vector / graph / hybrid
   ↓
实体链接 + TF-IDF 文本检索 + 图关系/路径检索
   ↓
HybridRetriever 去重合并
   ↓
EvidenceContextSerializer
   ↓
qwen3:4b 结构化 Claim 生成
   ↓                 运行故障
Evidence Verifier  ←────────→ GroundedAnswerGenerator fallback
   ↓
PASS / PARTIAL_PASS / RETRY / REFUSE
   ↓
最终回答 + E/P/R 引用 + 验证指标 + trace
```

阶段 8.3 已接入 `PARTIAL_PASS`。LLM 默认使用逐 Claim 保留策略；离线规则生成器默认保持 strict，LLM 也可通过显式 strict override 作为消融对照。

## 7. 数据处理流水线

### 7.1 配置驱动的数据源

`config/sources.yaml` 定义六个 source ID、名称、标题、URL 和部分关注关键词。所有路径由项目根目录和 `config/settings.yaml` 计算，不依赖硬编码的迁移目录。

### 7.2 HTML 抓取与缓存

`scripts/fetch_sources.py` 下载官方页面，保存：

- 原始 HTML：`data/raw/html/S*_*.html`；
- 抓取元数据：`data/raw/html/S*_*.json`；
- 汇总清单：`data/raw/html/manifest.json`。

重新抓取会改变原始数据和后续哈希。冻结实验期间不应重新抓取后再覆盖结果。

### 7.3 Section 提取

`src/ingestion/html_processing.py` 使用 BeautifulSoup 和 lxml：

1. 移除 script、style、导航、页脚、代码块等噪声；
2. 选择 main、body 或 article 主体；
3. 按 h1/h2/h3 构造 `heading_path`；
4. 聚合段落和列表文本；
5. 丢弃过短或典型导航噪声；
6. 为 Section 计算 SHA-256 内容哈希。

当前共有 164 个 Section：S1 35、S2 16、S3 12、S4 22、S5 32、S6 47。

### 7.4 Chunk 构造

Chunk 构造规则：

- 以英文句号等边界拆句；
- 目标约 580 个粗略 token；
- 单 Chunk 上限约 950 个粗略 token；
- 相邻 Chunk 可保留最多两个短句作为轻量重叠；
- 过短文本不输出；
- 按 `content_hash` 去重；
- 再按每个 source 的上限裁剪，总量固定为 180。

每个 Chunk 包含：

- `chunk_id`；
- `source_id`；
- `page_title`；
- `heading_path`；
- `url`；
- `display_text`；
- `embedding_text`；
- `language=en`；
- `retrieved_at`；
- `content_hash`。

稳定 Chunk ID 形如 `SKL-S4-...-001`。图关系、回答证据和评测 gold 都依赖这些 ID。

### 7.5 文本索引

`scripts/build_chroma.py` 当前做两件事：

1. 用 scikit-learn `TfidfVectorizer` 构建本地 TF-IDF vectorizer 和 matrix；
2. 如 Chroma 可用，将 TF-IDF 矩阵转成稠密列表写入持久化 Chroma collection。

关键事实：

- 当前 Chroma collection 中仍是 TF-IDF 向量，不是 Transformer Embedding；
- 在线问答的 `TfidfVectorRetriever` 直接读取 `data/chroma/tfidf_vectorizer.pkl`、`tfidf_matrix.pkl` 和 `chunks_snapshot.jsonl`；
- `sentence-transformers` 已安装，但没有激活任何 Dense Retriever 模型；
- 因此当前检索应准确称为稀疏 TF-IDF 检索。

## 8. 预定义知识图谱

### 8.1 图谱规模

| 项目 | 数量 |
| --- | ---: |
| 实体 | 50 |
| 关系 | 100 |
| 绑定 Chunk 证据的关系 | 100 |
| approved 关系 | 100 |

实体类型：

| 类型 | 数量 | 示例 |
| --- | ---: | --- |
| Algorithm | 16 | Random Forest、SVC、Lasso |
| Concept | 8 | 方差、正则化等 |
| MethodFamily | 5 | 线性模型、集成学习等 |
| Metric | 9 | F1、Balanced Accuracy 等 |
| Problem | 4 | 过拟合、类别不平衡等 |
| Task | 3 | 分类、回归、聚类 |
| Technique | 5 | 特征缩放、剪枝等 |

关系类型：

| 关系 | 数量 | 语义 |
| --- | ---: | --- |
| BELONGS_TO | 16 | 算法属于方法族 |
| SOLVES | 17 | 算法解决任务 |
| USES | 13 | 算法使用概念、技术或算法 |
| REQUIRES | 5 | 算法需要某种技术或条件 |
| EVALUATED_BY | 12 | 任务或算法由指标评估 |
| DIFFERS_FROM | 9 | 算法、技术或指标之间存在差异 |
| HAS_ADVANTAGE | 14 | 优势相关概念或问题 |
| HAS_LIMITATION | 7 | 局限相关问题或概念 |
| MITIGATES | 7 | 技术、算法或指标缓解问题 |

### 8.2 图谱文件

- `data/graph/entities.csv`：实体 ID、中英文名称、别名、类型和中文描述；
- `data/graph/relations.csv`：关系 ID、源实体、关系类型、目标实体、页面级来源、Chunk 证据和审核状态；
- `config/ontology.yaml`：允许的实体类型和关系端点约束。

当前实体行的 `review_status` 为 `pending`，运行时不按实体状态过滤；关系全部为 `approved`，NetworkX 和 Neo4j 查询只应使用 approved 关系。这是一个数据治理不一致点，不影响当前关系加载结果，但需要在未来版本明确状态语义。

### 8.3 证据绑定

`scripts/bind_graph_evidence.py` 根据实体名称、别名、关系类型和 Chunk 内容为关系选择证据。每条 approved 关系至少有一个真实 `evidence_chunk_id`，并由 `scripts/validate_graph_evidence.py` 检查：

- Chunk ID 存在；
- source ID 一致；
- reviewed relation 具有证据；
- 关系端点和 ontology 一致。

### 8.4 统一图接口

业务代码依赖 `GraphRepository`，接口包括：

```python
find_entity(name)
get_neighbors(entity_id, relation_types=None, include_incoming=True)
find_paths(source_id, target_id=None, max_hops=2)
validate_path(triples)
```

实现：

- `NetworkXGraphRepository`：默认、完全本地、正式实验使用；
- `Neo4jGraphRepository`：可选外部服务实现。

当前本机没有安装 Python `neo4j` 驱动，且没有提供正在运行的 Neo4j 服务。因此“Neo4j 代码存在”不等于“当前 Neo4j 环境可直接运行”。

## 9. 检索模块

### 9.1 规则 Router

`IntentRouter` 按问题中的确定性标记选择意图和模式：

| 意图 | 典型标记 | 模式 |
| --- | --- | --- |
| comparison | 区别、对比、相比、vs | hybrid |
| recommendation | 用什么、怎么选、哪个指标 | hybrid |
| explanation | 为什么、机制、优缺点、稳定 | hybrid |
| multi_hop | 关系、路径、共同、如何影响 | hybrid |
| definition | 什么是、定义、含义 | vector |
| relation | 属于、使用、解决、评估 | graph |
| general | 无明确标记 | vector |

LLM Query Planner 没有进入主链路。`qwen3:4b` 的 QueryPlan 探针只有 1/20 语义正确，因此 Planner 为 No-Go。

### 9.2 实体链接

`EntityLinker`：

- 匹配实体中英文名、ID 和别名；
- 去掉“问题、方法、模型、算法、指标”等常见中文后缀再匹配；
- 无精确匹配时，对实体描述做轻量词项回退；
- 最多返回 3 个候选实体。

它是规则字符串匹配，不是神经实体链接模型。

### 9.3 查询改写

`rewrite_query_to_english` 使用人工维护的 `TERM_MAP`，将“随机森林、类别不平衡、特征缩放、F1”等中文术语映射为英文检索词。文本检索会分别查询原问题和英文改写，再按最高分去重合并。

### 9.4 TF-IDF 文本检索

`TfidfVectorRetriever`：

1. 读取冻结的 Chunk snapshot、vectorizer 和 sparse matrix；
2. 对原问题和英文改写分别计算 TF-IDF 相似度；
3. 每路先取 `2 × top_k`；
4. 按 Chunk ID 去重，保留最高分；
5. 返回最终 top-k，并重新编号为 E1、E2……。

默认 `final_top_k=8`。Verifier 重试时，工作流将 top-k 乘 2，并强制改成 hybrid 模式。

### 9.5 图检索

`GraphRetriever`：

- 先链接实体；
- 根据问题词选择关系类型；
- 单跳题读取邻居关系；
- 对比题优先寻找两个实体间含 `DIFFERS_FROM` 的路径，否则分别取优势、局限和差异邻居；
- 多跳题查找最多 2 hop 的最短路径；
- 指标推荐题在多个实体上搜索 `EVALUATED_BY`、优势和局限；
- 将路径绑定的 Chunk 转成高优先级文本证据。

图路径临时编号为 P1、P2……；关系使用持久化 R001 等 ID。

### 9.6 混合融合

`HybridRetriever` 合并图证据和 TF-IDF 证据：

- 以 `chunk_id` 去重；
- 同一 Chunk 保留更高 score；
- 当前顺序以图证据在前、向量证据在后；
- 截断到 top-k；
- 最终统一重编号 E1、E2……。

当前不是学习排序，也不是 RRF。Evidence Packer v2 已在 Retriever 之后优化送给 LLM 的证据，但不会改写底层 Retriever 的完整召回结果。

## 10. Evidence Packer 与上下文组织

阶段 8.1 已将原 `EvidenceContextSerializer` 演进为 `EvidencePacker` 的兼容外壳。Packer 位于 Retriever 与 LLM Generator 之间，只创建证据子集和序列化上下文，不原地修改 `RetrievalResult`。

硬预算：

| 参数 | 当前值 |
| --- | ---: |
| 最大文本证据 | 8 |
| 最大图路径 | 8 |
| 单条文本最大字符 | 900 |
| 总上下文最大字符 | 10000 |

intent 目标条数低于 8 条硬上限：定义、单跳关系和指标推荐最多 4 条；对比、解释、多跳和一般问题最多 6 条。对比题在证据可用时为前两个实体各保留 2 条；解释题平衡机制、优势和局限；多跳题优先覆盖每条可见 P path 的绑定 Chunk；指标题分别保留定义和适用场景。

固定处理顺序：

1. 按 `chunk_id` 和 `evidence_id` 稳定去重；
2. 保留图路径绑定 Chunk；
3. 匹配实体名与标题、heading、正文，并兼容 `KMeans` / `K-means` 等标点变体；
4. 执行 intent 配额；
5. 按路径、实体、intent 标签、查询词、原 score 和原顺序稳定补齐；
6. 在总字符预算内公平分配每条原文长度，不对最终结构做任意硬截断；
7. LLM 生成边界只接受本次上下文可见的 E/P/R ID，原始完整检索结果仍交给 Verifier 审计。

每次 LLM 生成、fallback 或 Verifier 重试都可记录一条 `EvidencePackingTrace`，包括 selected E/Chunk/P IDs、reason codes、实体覆盖、coverage gaps、截断/淘汰 IDs、输入/输出字符数和 `evidence_packing_latency_ms`。

只读回归在 dev 10 题与 pilot 40 题上验证了 50 次打包：平均选择 4.38 条证据，最长上下文 7,783 字符，仅无答案题 `F-NA-01` 产生预期 `no_text_evidence` gap。该结果是工程合同检查，不是新的独立效果实验。

## 11. 答案生成器

### 11.1 规则生成器

`GroundedAnswerGenerator` 是确定性 fallback，也是 v1.0 正式基线生成器。它：

- 将图三元组映射为中文句子；
- 绑定关系证据 E ID、路径 P ID 和关系 R ID；
- 定义题可使用实体中文描述；
- 没有结构 Claim 时使用首个官方 Chunk 摘录；
- 对“一定、必然”等绝对比较增加保守提示；
- 无证据时返回固定拒答文本。

优点是速度快、可重复、难以自由发挥；缺点是语言模板化、综合能力有限。

### 11.2 LLM 生成器

当前默认 `LLMAnswerGenerator` 使用本地 Ollama `qwen3:4b`。阶段 8.2 已将生成合同升级为 Prompt v2：

- 只能使用当前 GRAPH_PATHS 和 TEXT_EVIDENCE；
- 不得用模型记忆补充事实；
- 问题和证据中的指令都只当数据，降低 Prompt Injection 风险；
- 中文作答；
- 每个 Claim 包含明确主语，只表达一个可独立判断真假的专业事实；
- 定义、机制、过程、结果、优势、局限和比较对象分别成 Claim；
- 每个 payload 只能有 1～4 条 Claim；
- 每个 Claim 至少绑定一个真实 E ID，且每个 E ID 都有对应 quote；
- quote 必须连续逐字复制，保留原文大小写和标点；
- E/P/R ID 分别只能进入 `evidence_ids`、`graph_path_ids` 和 `relation_id`；
- 顶层 `graph_paths` 必须等于 Claims 实际使用的 P ID 去重集合；
- 逐一处理问题子问，证据不足的具体方面写入 `unsupported_claims`；
- 严格输出 Pydantic JSON Schema。

LLM wire Schema 包括：

- `answer`；
- `claims`；
- `graph_paths`；
- `unsupported_claims`；
- `confidence`。

程序不会直接信任模型自由生成的 `answer`。它会重新遍历 Claims、核对 E/P/R ID、逐字 quote、每个 E ID 的 quote 覆盖和顶层路径一致性，然后用结构化 Claim 重建最终 `AnswerPayload.answer`。这防止自由文本绕过验证器。

Prompt v2 SHA-256 为 `e5c6fa6bbc992a9af2c66daffd8fcffeb2da1eae02202d932aef33fbbb774cad`，wire Schema SHA-256 为 `b11bf9c445d3aa37c98cd571b880a157387661fdebf63a11a43aef786c7087eb`。四个合成场景各运行 5 次，Schema 与语义合同均为 `20/20`；报告不保存 Prompt、模型回答、quote 或 thinking。该结果只证明生成结构合同稳定，不证明独立回答质量提升。

### 11.3 Fallback

`FallbackAnswerGenerator` 只捕获预期的 LLM 运行异常：

- `LLMUnavailableError`；
- `LLMTimeoutError`；
- `LLMEmptyResponseError`；
- `LLMSchemaError`。

发生这些错误后，系统使用规则生成器完成当前问题，并记录：

- `fallback_used=true`；
- `fallback_reason`；
- LLM 尝试次数；
- LLM 已消耗的延迟。

程序错误如普通 `ValueError` 不会被静默吞掉。

## 12. 统一 LLM Client

当前 Client 位于 `src/llm/`，核心合同：

| 参数 | 当前配置 |
| --- | --- |
| Provider | Ollama |
| Base URL | `http://127.0.0.1:11434` |
| Model | `qwen3:4b` |
| think | false |
| stream | false |
| temperature | 0.0 |
| timeout | 120 s |
| keep_alive | 30m |
| num_predict | 1536 |
| seed | 42 |
| max_retries | 1 |

Client 调用 `/api/chat`，把 Pydantic JSON Schema直接作为 Ollama `format`。它只解析 `message.content`，不会把 `thinking` 当答案。

重试规则：

- timeout：最多重试一次；
- 无效 envelope 或 Schema：最多修复一次；
- connection/HTTP 服务错误：立即转为 unavailable；
- 空 content：立即失败并交给 fallback；
- Schema 修复提示只包含字段路径和错误类型，不回传无效模型内容。

日志只记录脱敏元数据：request ID、节点、provider、model、Schema、成功状态、尝试次数、延迟、token 数、done reason、错误类型和有限 validation issues。不会记录 Prompt、生成 content、thinking、凭据或带认证信息的 URL。

Stage 8.4 增加 `warmup()` 合同。Streamlit 缓存工作流首次创建时发送固定的合成结构化健康检查，只要求返回 `{"status":"ready"}`，不读取任何 demo/dev/pilot/final/extension 题目。预热记录只包含 status、provider、model、keep-alive、尝试次数、耗时、结构成功和错误类型；预热耗时不计入后续问题的端到端延迟。CLI、普通评测和 extension runner 都不会自动预热，因此正式冷/热延迟口径不会被演示逻辑污染。

## 13. Evidence Verifier

### 13.1 验证内容

Verifier 检查：

1. Claim 引用的 E ID 是否存在；
2. 引用是否达到最低文本分数，或 Claim 的 relation ID 是否存在于图路径；
3. Claim 引用的 P ID 是否存在；
4. 图路径是否能由 GraphRepository 重新验证；
5. LLM quote 是否属于对应 Chunk 的归一化原文子串；
6. Claim 中关键中文术语是否被英文 quote 覆盖；
7. 检索证据是否覆盖问题属性和限定条件；
8. “是否/是不是”类问题的图谱前提是否成立；
9. 对比题是否至少链接两个实体。

Stage 8.5 对 quote 子串和术语覆盖增加了保守规范化：统一大小写、ASCII/Unicode 连字符和弯引号，并把官方原文中的 `overfit`、`do not generalize` 识别为“过拟合”的直接表述。该规范化只消除标点和词形误杀；实质改写原文的 quote 仍返回 `quote_not_in_source`。

### 13.2 当前评分与决策

```text
evidence_score =
    0.30 × claim_coverage
  + 0.25 × citation_validity
  + 0.20 × path_validity
  + 0.25 × retrieval_sufficiency
```

当前阈值：

- `pass_threshold=0.80`；
- `retry_threshold=0.55`；
- `min_vector_score=0.08`；
- `max_retries=1`。
- `decision_policy=partial_pass`，规则生成器默认覆盖为 strict。

PASS 要求：

- 所有 Claim 均受支持；
- citation validity ≥ 0.80；
- path validity ≥ 0.80；
- `unsupported_claims` 为空。

默认 LLM partial-pass 策略按以下顺序决策：

- 全部 Claim 支持且无缺口：`pass`；
- 至少一个 Claim 支持，但存在 removed Claim 或明确证据缺口：`partial_pass`；
- 零 Claim 支持、缺口仍可能通过扩大检索恢复：最多 `retry` 一次；
- 零 Claim 支持且不可恢复、错误前提或重试后仍失败：`refuse`。

`partial_pass` 不触发第二次 LLM。strict 策略使用同一组 ClaimResult，但只有完整通过才保留答案；混合 Claim 仍按 retry 后 refuse 处理。

### 13.3 Claim-level 过滤

Verifier 为每条 Claim 生成 `C1...Cn`，记录 supported、retained、reason codes、原始/有效 E/P ID 和关系 ID。FinalResponse 只保留 retained Claims；removed Claim 的正文只存在于验证诊断，不进入用户答案。错误前提会把全部 Claim 标为 unsupported，不能借部分回答绕过。

## 14. LangGraph 工作流

当前节点：

```text
route -> retrieve -> answer -> verify
                           ↓
          pass/partial_pass/refuse -> finalize -> END
                           ↓
                         retry -> answer
```

重试节点不会重新执行 Router，而是：

- 保留原 intent；
- 强制 retrieval mode 为 hybrid；
- top-k 从 8 扩大到 16；
- 再调用一次 Generator 和 Verifier。

LangGraph 安装时使用真实 `StateGraph`；未安装时有相同转移逻辑的本地状态机 fallback。当前环境已安装 LangGraph，正式运行 `engine=langgraph`。

LangGraph 与本地 fallback 状态机都支持 `retry/pass/partial_pass/refuse`。`partial_pass` 直接进入 finalize，不再经过 retry。

### 14.1 运行时 Trace

每个 `FinalResponse` 现在保存：

- 一次 `RouteTrace`；
- 每次初始/补充检索的 `RetrievalCall`；
- 每次 answer 节点的 `GenerationCall`；
- 每次 Packer 的 `EvidencePackingTrace`；
- 每次 Verifier 的 `VerificationCall`；
- 聚合的 `WorkflowLatencyTrace`；
- `cache_status=disabled`。

统一延迟字段为：

```text
routing_latency_ms
retrieval_latency_ms
evidence_packing_latency_ms
llm_generation_latency_ms
verification_latency_ms
retry_latency_ms
end_to_end_latency_ms
```

`retrieval`、`generation` 和 `verification` 都汇总所有调用；第一次验证结果不会在重试后丢失。`retry_latency_ms` 从补充检索开始，到重试后的验证结束，属于与检索/生成/验证子阶段重叠的墙钟时间，不能与这些字段再次求和。fallback 的 `GenerationCall` 保留 requested=`ollama`、actual=`offline_rule`、模型名、失败原因和已消耗的 LLM 延迟。end-to-end 使用 `time.perf_counter()` 单调时钟。

## 15. 核心 Schema

| Schema | 用途 |
| --- | --- |
| `TextEvidence` | E ID、Chunk、来源、标题、URL、原文和分数 |
| `GraphTriple` | 源实体、关系、目标实体、R ID 和证据 Chunk |
| `GraphPath` | P ID、三元组列表和聚合证据 Chunk |
| `LinkedEntity` | 实体 ID、中英文名、类型、命中文本和分数 |
| `RetrievalResult` | intent、mode、entities、paths、text evidence |
| `EvidenceQuote` | evidence ID 与 12～500 字符原文 quote |
| `AnswerClaim` | Claim、E/P/R 引用和 quotes |
| `AnswerPayload` | 答案、Claims、路径、unsupported、置信度和生成元数据 |
| `ClaimResult` | C ID、Claim、supported/retained、有效 E/P ID、R ID 和 reason codes |
| `VerifyResult` | 四状态决策、逐 Claim 结果、保留/删除 ID、coverage、validity、sufficiency 和验证耗时 |
| `GenerationCall` | provider/model、请求/实际后端、fallback、尝试次数、延迟和结构成功 |
| `RouteTrace` | intent、mode、路由理由和路由耗时 |
| `RetrievalCall` | 调用序号、是否重试、mode、top-k、返回数量和耗时 |
| `VerificationCall` | 调用序号、是否重试、决策、policy、Claim 数量和耗时 |
| `WorkflowLatencyTrace` | routing/retrieval/packing/LLM/verification/retry/end-to-end 聚合耗时 |
| `FinalResponse` | 问题、最终答案、完整逐阶段 trace、缓存状态、总延迟和重试数 |

E/P ID 是每次检索结果内的临时编号；R ID 和 Chunk ID 是数据中的稳定编号。

## 16. 配置与环境变量

### 16.1 主配置

`config/settings.yaml` 管理：

- 项目名和默认图后端；
- 数据路径；
- top-k；
- Chunk 上限；
- Verifier 阈值；
- Ollama 参数；
- Router/Generator/fallback；
- Evidence Context 预算。

### 16.2 环境变量

| 变量 | 作用 |
| --- | --- |
| `GRAPH_BACKEND` | `networkx` 或 `neo4j` |
| `NEO4J_URI` | Neo4j Bolt URI |
| `NEO4J_USER` | Neo4j 用户 |
| `NEO4J_PASSWORD` | Neo4j 密码 |
| `AGENT_GENERATOR_BACKEND` | `llm` 或 `offline_rule` |
| `OLLAMA_BASE_URL` | 覆盖本地 Ollama URL |
| `OLLAMA_MODEL` | 覆盖模型名 |

`.env` 被 Git 忽略，`.env.example` 只提供占位示例。Client 禁止 base URL 中嵌入用户名或密码。

### 16.3 当前环境

| 软件 | 当前版本/状态 |
| --- | --- |
| Python | 3.12.7 |
| langgraph | 1.0.10 |
| pydantic | 2.8.2 |
| scikit-learn | 1.5.1 |
| networkx | 3.3 |
| chromadb | 1.5.9 |
| sentence-transformers | 5.6.0 |
| streamlit | 1.37.1 |
| playwright | 1.61.0，本机 UI smoke 使用 Microsoft Edge channel |
| requests | 2.32.3 |
| PyYAML | 6.0.3 |
| Ollama | 0.32.1 |
| qwen3:4b | Q4_K_M，约 2.5 GB，digest 前缀 `359d7dd4bcda` |
| Python neo4j 驱动 | 当前未安装 |

`requirements.txt` 已列出 `neo4j`，但当前环境检测不到该包；默认 NetworkX 不受影响。

## 17. Streamlit 演示界面

入口：`app/streamlit_app.py`。

运行：

```bash
streamlit run app/streamlit_app.py
```

默认地址：`http://localhost:8501`。

当前功能：

- 输入自由问题；
- 选择 8 道 demo 预设题；
- 启动时执行一次不含业务题的合成 Ollama 预热，并显示 ready/failed/not-applicable；
- 对 `pass`、`partial_pass` 和 `refuse` 使用绿/琥珀/红三种独立状态；
- 显示检索模式、问题类型、证据分数、Claim 覆盖率、重试次数和端到端耗时；
- 显示真实 Generator model、requested/actual backend、fallback、原因、结构化输出和缓存状态；
- 显示 routing、retrieval、packing、LLM generation、verification、retry 分阶段耗时；
- 分页显示回答、图路径、官方证据、验证详情和逐调用运行轨迹；
- 显示 Chunk ID、source、score、原文和官方 URL；
- 下载完整 `FinalResponse` JSON；
- sidebar 显示工作流引擎、图后端、Generator、预热状态和正式题数量。

Stage 8.4 浏览器 smoke：

- `PASS`：规则生成器，offline_rule -> offline_rule，fallback=false，prewarm=not_applicable；
- `PARTIAL_PASS`：qwen3:4b，ollama -> ollama，fallback=false，structured=success，prewarm=ready；
- `REFUSE`：qwen3:4b 配置但无证据时不调用模型，structured=not called；
- `fallback`：qwen3:4b 请求失败，ollama -> offline_rule，fallback=true，prewarm=failed；
- 四条路径均生成 1440 px 桌面和 390 px 移动截图，自动检查无水平溢出；
- 截图位于 `reports/streamlit_stage8_4_*_{desktop,mobile}.png`。

这些截图只验证界面状态与 trace 一致，不是回答质量实验。当前没有答案缓存；如果以后启用演示缓存，必须显式显示 hit/miss，正式评测仍需禁用。

## 18. 评测数据集与防泄漏规则

| Split | 数量 | 用途 | 当前约束 |
| --- | ---: | --- | --- |
| dev | 10 | 开发和调试 | 可以使用 |
| demo | 8 | Streamlit 演示 | 可与 dev 重合 |
| pilot | 40 | 历史先导实验和消融 | 已用于发现缺口，不能称为无泄漏测试集，也不再用于自由调参 |
| final | 40 | v1.0 冻结正式测试 | 已运行一次，只读，禁止重跑 |
| extension | 23 | LLM 增强保留集 | Stage 8.7 已运行一次并消费，禁止重跑、调参或覆盖结果 |

final 与 pilot 的题型分布：8 单跳、9 多跳、7 定义、5 对比、5 原理优缺点、2 指标选择、4 无答案。

extension 分布：4 单跳、4 多跳、3 定义、3 对比、3 原理优缺点、2 指标选择、4 无答案。

四类无答案题覆盖：

1. 完全超出机器学习范围；
2. 属于机器学习但不在六页知识库；
3. 实体存在但询问不存在属性；
4. 问题包含错误前提。

## 19. 评价指标

### 19.1 自动指标

- Decision Accuracy：最终 pass/refuse 决策是否符合 expected behavior；
- Refusal Accuracy：无答案题中正确拒答比例；
- Over-refusal Rate：可回答题中错误拒答比例；
- Citation Rate / Validity：是否有引用，以及引用 ID 是否有效；
- Retrieval Recall@5：保守 gold Chunk 是否进入前 5；
- Path Validity：图路径能否由 GraphRepository 复核；
- Keyword Coverage：回答覆盖预期关键词的程度；
- Entity Coverage：回答覆盖预期实体的程度；
- Structured Output Success：LLM 是否成功返回结构化 payload；
- Fallback Rate：是否发生离线规则回退；
- Latency：当前主要记录端到端和 generation trace。

### 19.2 人工指标

- Answer Correctness：0/1/2；
- Evidence Faithfulness：0/1/2；
- Hallucination：0/1；
- Over-refusal：0/1；
- Readability：1～5，在 extension v2 中对正确或部分正确的实质答案计算。

Pilot 和 extension 语义评分都是 Codex 辅助初评后由用户确认的单一复核流程，不是独立双人标注，不能报告标注者一致性。Extension 在评分锁定后才读取独立 method key 解盲。

## 20. v1.0 规则基线结果

### 20.1 冻结 final 结果

v1.0 使用：规则 Router + TF-IDF/图/混合检索 + 规则生成器 + Verifier。

| 指标 | 结果 |
| --- | ---: |
| 题目数 | 40 |
| Decision Accuracy | 39/40 = 0.9750 |
| Citation Rate | 0.9750 |
| Mean Keyword Coverage | 0.8375 |
| Mean Entity Coverage | 0.9208 |
| 无答案拒答 | 4/4 = 1.0000 |
| 本地热路径平均延迟 | 1.48 ms |

唯一错误：`T-DF-01`，“请解释 AdaBoost 的基本含义”，系统因证据充分度判断过严而拒答。这是 Over-refusal。

1.48 ms 只代表本地规则热路径，不代表 LLM 延迟、网络服务延迟或冷启动延迟。

### 20.2 v1.0 归档

`reports/releases/v1.0-baseline/` 保存：

- 配置 snapshot；
- 数据 snapshot；
- final 和 pilot 结果；
- 环境信息；
- Streamlit 截图；
- 源码快照 ZIP；
- 每个 payload 的大小和 SHA-256 manifest；
- `MANIFEST_SHA256.txt`。

归档 Manifest SHA-256 为 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`。

## 21. Pilot 主实验与消融

Pilot 使用规则生成器，是历史先导数据，不是最终无泄漏结论。

| 方法 | Decision Acc. | Correctness | Faithfulness | Recall@5 | Path Validity | Refusal Acc. | Hallucination | 延迟 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Vector RAG | 0.9000 | 0.5375 | 0.4875 | 0.8276 | N/A | 0.0000 | 0.0000 | 1.325 ms |
| Graph Only | 0.9000 | 0.8375 | 0.9250 | 0.9655 | 1.0000 | 0.0000 | 0.0000 | 1.000 ms |
| Proposed | 1.0000 | 0.8625 | 1.0000 | 0.9655 | 1.0000 | 1.0000 | 0.0000 | 1.700 ms |
| No Verifier | 0.9000 | 0.8000 | 0.8500 | 0.9655 | 1.0000 | 0.0000 | 0.0000 | 1.225 ms |

可支持的描述性结论：

- 图关系提高了保守 gold 子集上的结构证据 Recall@5；
- Proposed 在该 pilot 上正确拒绝 4 道无答案题；
- No Verifier 的拒答准确率为 0，说明 Verifier 对问题对齐和拒答有直接作用；
- 该小样本、规则生成器实验没有观察到事实幻觉，不代表真实 LLM 不会幻觉。

## 22. LLM 模型前置探针

### 22.1 qwen3-vl:8b

初始视觉模型在 `think=false` 组合下无法稳定把结构化 JSON 放进正式 `message.content`，6 次正式字段结构成功为 0，因此 No-Go。不能解析 thinking 字段来冒充正式答案。

### 22.2 qwen3:4b

正式 60 次探针：

| 场景 | Schema 成功 | 语义成功 |
| --- | ---: | ---: |
| simple status | 20/20 | 20/20 |
| QueryPlan | 20/20 | 1/20 |
| nested AnswerPayload | 20/20 | 20/20 |
| 合计 | 60/60 | 41/60 |

其他结果：

- 空 content：0/60；
- 非空 thinking：0/60；
- 冷启动约 20.70 s；
- 热请求平均约 0.93 s；
- 热请求 P95 约 1.29 s。

结论：Generator Go，Planner No-Go。Schema 正确不等于语义规划正确。

## 23. 当前 LLM 主链路 dev 审计

当前默认主链路为：Rule Router + qwen3:4b Generator + Evidence Verifier + offline rule fallback。

历史候选 dev 结果：

| 指标 | 结果 |
| --- | ---: |
| 题目数 | 10 |
| Decision Accuracy | 0.6000 |
| Structured Output Success | 1.0000 |
| Fallback Rate | 0.0000 |
| 平均端到端延迟 | 11437.7 ms |
| 平均生成延迟 | 5691.18 ms |
| 触发一次重试 | 7/10 |
| 无答案题正确拒答 | 2/2 |
| 可回答题过度拒答 | 4/8 |

四个错误全部是过度拒答：DEV02、DEV03、DEV05、DEV10。没有观察到错误放行。

可以说：

- LLM 已真实进入默认 answer 节点；
- 10/10 结构化输出成功；
- fallback 与引用验证闭环已经实现；
- 当前安全性保守。

不能说：

- LLM 比规则基线更准确；
- LLM Agent 增强已被正式实验验证；
- 当前延迟达到约 1 秒。探针热调用约 1 秒，不等于完整工作流。

上表是 Claim-level Partial-pass 接入前的旧审计基线。Stage 8.5 使用当前 v2 工作流重新运行全部 10 道 dev，候选结果如下：

| 指标 | 结果 |
| --- | ---: |
| 题目数 | 10 |
| Decision Accuracy | 0.9000 |
| Structured Output Success | 1.0000 |
| Fallback Rate | 0.0000 |
| 平均端到端延迟 | 9420.28 ms |
| 平均生成延迟 | 9408.91 ms |
| 触发一次重试 | 3/10 |
| 无答案题正确拒答 | 2/2 |
| 可回答题过度拒答 | 1/8 |
| Partial-pass | 4/10 |
| Unsupported Claim leakage | 0 |

19 条生成 Claim 中，9 条 supported/retained，10 条 removed，Claim retention rate 为 0.4737。DEV02、DEV03 和 DEV10 从历史整题拒答变为过滤后的 `partial_pass`；DEV05 仍拒答，因为当前 180 个 Chunk 只有两处 AdaBoost 名称提及，没有样本权重更新机制的直接原文。DEV10 的低风险修正仅规范化大小写、ASCII/Unicode 连字符、弯引号以及 `overfit`/`do not generalize` 等直接术语变体，并保留实质改写 quote 的拒绝测试。

Stage 8.5 结果达到进入 pilot 冻结前回归的工程门槛，但 dev 已用于调试，`partial_pass` 未经独立人工正确性评估，因此不能据此声称 LLM 优于规则基线或增强已被正式验证。完整审计见 `reports/llm_agent_v2_dev_stage8_5_audit.md`。

## 24. Extension holdout 与 release 治理

### 24.1 extension 题集

- 23 题；
- 19 道可回答、4 道拒答；
- 在 LLM Client 和 Generator 业务实现前冻结；
- 与 dev/demo/pilot/final 完全相同题面重合为 0；
- 最高归一化相似度 0.7097，低于 0.82 阈值；
- 题集 SHA-256：`7b2b2e76ecdd690574fd0c8220bee7edf20a326bcd2ff8e401659f4acc15e3a5`。

### 24.2 v1 release

| 项目 | 值 |
| --- | --- |
| Release ID | `extension-qwen3-4b-v1-bdedf7dc` |
| 文件原始状态 | `authorized_not_executed` |
| 当前有效状态 | `revoked_before_execution` |
| Release 文件 SHA-256 | `af4f8ac10c247483af20e93f5fdde5220b608fb8c9dfb8c031d777d8b1932d0c` |
| Revocation 文件 | `data/evaluation/extension_release_revocations/extension-qwen3-4b-v1-bdedf7dc.json` |
| 实现提交 | `bdedf7dcb4e82bc918dfd7c92161501151b09742` |
| Runtime bundle | `b4676d37dc9f2babde6ade4f1a3d212ed775d590adf202e3cef710cadbbe03f0` |
| Prompt v1 | `f4af2d9668b8ba53cb8f884ff840e4ce282d55d15e4468039b039ff3a0e5c60e` |
| Trace contract | `f68cde4cae30845e1b04a98f27c6d95dd08a8af4d2edf4f32b615b25da08185d` |
| 模型 digest | `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7` |

原 v1 协议固定 3 个方法：Rule Baseline、LLM Generator、LLM Generator No Verifier。

### 24.3 最新治理决定

以下边界只针对历史 v1 release：

- `reports/extension/` 不存在；
- v1 没有 execution state、receipt、答案、方法报告或盲评表；
- v1 extension 从未进入 QA workflow；
- v1 release 在任何 extension 输出出现前被撤销。

由于项目决定先实现 Evidence Packer、原子 Claim 和 Partial-pass，原 v1 runtime 不再代表目标协议。阶段 8.0 已在独立提交中创建不可覆盖的撤销记录，runner 会在 runtime/model 校验和题集读取前拒绝原授权命令。

版本化的 `extension_evaluation_v2.yaml` 与 `extension_trace_contract_v2.yaml` 已冻结四方法矩阵：`rule_baseline`、`llm_strict_v2`、`llm_no_verifier_v2`、`llm_partial_pass_v2`。Stage 8.6 已在实现提交 `e207cb9` 上消费唯一一次 40 题 pilot：Decision Accuracy 0.8250、Structured Output 0.9750、4/4 无答案正确拒答、7/36 可回答题 over-refusal、13/40 retry、unsupported Claim leakage 为 0，平均端到端延迟 34180.72 ms。预声明 gate 为 `go`，但该结果只是工程冻结门槛，不是独立效果证据，也不能证明 LLM 优于规则基线。

Stage 8.7 已使用 release `extension-qwen3-4b-v2-e207cb91` 执行唯一一次 4 方法 x 23 题 extension，共 92 次 QA 调用。release 文件状态仍按不可变合同保留 `authorized_not_executed`，state/receipt 给出的有效执行状态为 `completed_once`。自动结果如下：

| 方法 | Decision Accuracy | Refusal Accuracy | Over-refusal | Unsupported Leakage | Mean E2E |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rule Baseline | 21/23 | 2/4 | 0/19 | 0/1 | 5.46 ms |
| LLM Strict v2 | 7/23 | 4/4 | 16/19 | 0/24 | 11891.29 ms |
| LLM No Verifier v2 | 19/23 | 0/4 | 0/19 | 25/25 | 5207.65 ms |
| LLM Partial-pass v2 | 16/23 | 2/4 | 5/19 | 0/27 | 7607.35 ms |

Partial-pass 自动减少了相对 Strict 的过度拒答并保持零 unsupported Claim 泄漏，但没有超过 Rule Baseline，且误接受 `X-NA-03`、`X-NA-04`。92 行 A/B/C/D 评分由 Codex 辅助初评并经用户确认，评分锁定后才解盲：

| 方法 | Correctness | Faithfulness | Hallucination | Over-refusal | Readability |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rule Baseline | 0.5870 | 0.8810 | 0/21 | 0/19 | 3.56 (n=18) |
| LLM Strict v2 | 0.3043 | 1.0000 | 0/3 | 16/19 | 5.00 (n=3) |
| LLM No Verifier v2 | 0.7826 | 0.8182 | 6/22 | 0/19 | 4.32 (n=19) |
| LLM Partial-pass v2 | 0.5217 | 0.9375 | 0/16 | 5/19 | 3.73 (n=15) |

结果支持 Partial-pass 作为 Strict 与 No Verifier 之间的安全性/覆盖率折中：它降低 Strict 的过度拒答并保持零观察 hallucination，但 Correctness 未超过 Rule。No Verifier 的 Correctness 最高，同时幻觉和无答案误接受风险明显。Strict 的高 Faithfulness/Readability 只有 3 条实质答案，必须连同分母披露。v1/v2 release、manifest、state、receipt 和结果继续保留且不可覆盖。

## 25. 复现与常用命令

### 25.1 安装

```bash
python -m pip install -r requirements.txt
```

Ollama 需单独安装，并确保 `qwen3:4b` 可见。当前模型目录和服务已在本机配置完成。

### 25.2 核心校验

```bash
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/validate_chunks.py
python scripts/validate_evidence_packer.py
python scripts/validate_atomic_claim_prompt.py
python scripts/validate_claim_level_verifier.py
python scripts/validate_runtime_trace.py
python scripts/validate_evaluation.py
python scripts/validate_experiments.py
python scripts/validate_scoring.py
python scripts/validate_report_claims.py
python scripts/generate_report_figures.py --check
python scripts/freeze_baseline.py --verify
pytest -q
```

### 25.3 运行 Agent

默认真实 LLM：

```bash
python scripts/run_agent.py "随机森林为什么更稳定"
```

强制规则生成：

```powershell
$env:AGENT_GENERATOR_BACKEND="offline_rule"
python scripts/run_agent.py "随机森林为什么更稳定"
```

图查询和文本查询：

```bash
python scripts/query_graph.py "随机森林"
python scripts/query_vector.py "类别不平衡时用什么指标"
```

### 25.4 LLM 校验

```bash
python scripts/smoke_llm_client.py --timeout 180
python scripts/validate_llm_probe.py
```

### 25.5 Streamlit 与浏览器 Smoke

```bash
streamlit run app/streamlit_app.py
python scripts/smoke_streamlit_runtime.py --url http://127.0.0.1:8501 --query "随机森林为什么更稳定" --expected-decision PARTIAL_PASS --expected-fallback false --expected-structured success --expected-prewarm ready --output-prefix reports/streamlit_stage8_4_partial
```

`smoke_streamlit_runtime.py` 使用本机 Playwright 与 Microsoft Edge，检查状态、模型、backend、fallback、结构化输出、预热、缓存和阶段延迟，并生成桌面/移动截图。它只应使用 demo/dev 或人工合成问题，禁止把 final/extension 题面传给该脚本。

### 25.6 数据重建

```bash
python scripts/fetch_sources.py
python scripts/build_chunks.py
python scripts/build_chroma.py
python scripts/bind_graph_evidence.py
```

这些命令会改变数据、索引或证据绑定。冻结实验和 release 审计期间不应随意运行或覆盖现有产物。

### 25.7 Extension 校验

Stage 8.7 后只允许只读审计校验：

```bash
python scripts/validate_extension_holdout.py
python scripts/validate_extension_release_v2.py --check-runtime-model
python scripts/validate_extension_results_v2.py
python scripts/validate_extension_blind_confirmation.py
```

当前 v1 正式命令仍被撤销；v2 的唯一执行已经完成，runner 会因 `completed_once` 拒绝再次运行。通用 runner、覆盖输出、自动重跑和基于 holdout 结果调参仍被禁止。

## 26. 目录与文件职责

```text
app/                         Streamlit 演示
config/                      数据源、ontology、运行参数、实验合同
data/raw/html/               六页官方 HTML 缓存
data/processed/              Section 和 Chunk
data/chroma/                 TF-IDF index、snapshot 和 Chroma 持久化数据
data/graph/                  实体和关系 CSV
data/evaluation/             dev/demo/pilot/final/extension 题集与冻结记录
src/ingestion/               HTML 清洗与 Chunk 逻辑
src/graph/                   GraphRepository、NetworkX、Neo4j
src/retrieval/               Router、改写、实体、文本、图、混合检索
src/agent/                   规则/LLM/fallback Generator 与 LangGraph workflow
src/llm/                     统一 Client、配置、Schema、异常和脱敏 trace
src/verification/            Evidence Verifier
src/evaluation/              实验 Schema、workflow factory、extension release/runner
scripts/                     构建、运行、评测、冻结和校验入口
tests/                       单元、合同、工作流、评测与 release 护栏测试
reports/                     结果、图、评分、报告、截图和 release 归档
PROGRESS.md                  按阶段追加的唯一进度日志
```

当前代码规模约为：`src` 45 个 Python 文件/6418 行，`scripts` 51 个/8782 行，`tests` 23 个/3184 行，Streamlit 1 个/307 行。

## 27. 主要脚本索引

| 类别 | 脚本 | 作用 |
| --- | --- | --- |
| 数据 | `fetch_sources.py` | 抓取并缓存六页官方文档 |
| 数据 | `build_chunks.py` | 生成 Section 和 180 个 Chunk |
| 索引 | `build_chroma.py` | 构建 TF-IDF 与 Chroma 持久化索引 |
| 图谱 | `bind_graph_evidence.py` | 为关系绑定 Chunk 证据 |
| 图谱 | `build_neo4j.py` | 构建 NetworkX smoke 或导入 Neo4j |
| 查询 | `query_graph.py` | 查看实体与图关系 |
| 查询 | `query_vector.py` | 查看 TF-IDF 文本结果 |
| 问答 | `run_agent.py` | 运行统一 QAWorkflow 并输出诊断 |
| 问答 | `vector_answer.py` | 文本问答辅助入口 |
| 评测 | `run_evaluation.py` | dev 等普通 split 评测；拒绝 final/extension |
| 实验 | `run_experiments.py` | 规则主实验与消融 |
| 对比 | `compare_experiments.py` | 汇总方法比较和类别结果 |
| 评分 | `build_human_scoring_template.py` | 生成评分模板 |
| 评分 | `score_pilot_preliminary.py` | 生成 pilot 初步评分 |
| 评分 | `confirm_pilot_scoring.py` | 晋级用户确认评分 |
| 评分 | `confirm_extension_blind_review.py` | 显式确认后锁定 92 行评分并解盲汇总 |
| 评分 | `validate_extension_blind_confirmation.py` | 重算用户确认指标、分数签名和输出哈希 |
| 评分 | `summarize_scored_experiments.py` | 汇总人工指标 |
| 图表 | `generate_report_figures.py` | 生成并校验 5 张报告图 |
| 图表 | `generate_extension_figures.py` | 从用户确认结果生成并校验 4 张 extension 图与类别指标 |
| LLM | `check_enhancement_readiness.py` | 检查 Ollama 和 Dense 模型条件 |
| LLM | `probe_llm_structured.py` | 批量结构化 Schema/语义探针 |
| LLM | `smoke_llm_client.py` | 统一 Client 合成 smoke |
| Trace | `validate_runtime_trace.py` | 验证路由、逐次检索/验证、retry 和聚合耗时合同 |
| UI | `smoke_streamlit_runtime.py` | 验证 pass/partial/refuse/fallback 状态与桌面/移动布局 |
| 冻结 | `freeze_baseline.py` | 创建/验证 v1.0 归档 |
| Extension | `create_extension_release_v2.py` | 创建 v2 一次性 release，当前不得再次创建 |
| Extension | `run_extension_evaluation_v2.py` | 已消费的一次性 runner，当前只允许验证拒绝重跑 |
| Extension | `validate_extension_results_v2.py` | 重算指标并校验 state、receipt、哈希与盲评匿名性 |
| 校验 | `validate_*.py` | 配置、图、Chunk、评测、实验、评分、报告和 release 护栏 |

## 28. 测试与质量保障

测试覆盖：

- GraphRepository 合同；
- NetworkX 路径和邻居；
- 图检索和证据绑定；
- TF-IDF 向量检索；
- Router、工作流、重试和拒答；
- LLM Client Schema、timeout、服务故障和日志脱敏；
- LLM Generator 引用、quote、fallback；
- 合成预热、provider/model、逐次 route/retrieval/verification 和 retry latency；
- Streamlit 四状态值、阶段耗时和桌面/移动无水平溢出 browser smoke；
- 实验配置和运行器；
- 数据集泄漏和 split 护栏；
- extension release、不可覆盖输出、哈希和一次性执行保护。

Stage 8.8c 图表与类别误差分析后的全量测试结果为 `140 passed`；Claim-level、extension 结果、release、holdout、盲评确认、图表哈希与报告声明校验均已通过，`python scripts/validate_runtime_trace.py` 继续通过。浏览器 smoke 仍覆盖 pass、partial-pass、refuse 和 fallback 四条路径。

## 29. 可复现性与安全设计

### 29.1 可复现性

- 配置文件固定参数；
- TF-IDF index 和 Chunk snapshot 持久化；
- NetworkX 默认不依赖外部服务；
- Ollama 固定模型 digest、temperature=0 和 seed=42；
- 题集、评分合同、Prompt、Schema 和 runtime bundle 使用 SHA-256；
- final 结果只读；
- extension 使用一次性 release、独占创建、state、receipt 和输出哈希；
- 历史结果不被回写美化。

### 29.2 安全性

- 只使用列出的官方证据；
- Prompt 将证据内指令当数据；
- 不读取 thinking 作为答案；
- 不记录 Prompt/content/thinking/凭据；
- 引用 ID 和 quote 做确定性校验；
- 无证据时拒答；
- 运行时故障有明确 fallback；
- release runner 禁止覆盖输出或自动重跑已暴露题目。

## 30. 当前技术贡献

可以作为当前项目贡献表述：

1. 构建了六页官方文档与 50 实体、100 关系的小型证据绑定知识库；
2. 实现了统一 GraphRepository，使 NetworkX 与 Neo4j 业务接口解耦；
3. 实现了规则路由下的文本、图和混合检索；
4. 通过 E/P/R 标识把 Claim、图路径和官方 Chunk 关联；
5. 实现了 Evidence Verifier、一次重试和保守拒答；
6. 实现了真实本地 LLM 结构化生成与规则 fallback；
7. 实现了确定性的 intent-aware Evidence Packer、可见 ID 边界和逐次 packing trace；
8. 实现了最多 4 条原子 Claim 的 Prompt v2、E/P/R wire Schema 和逐字 quote 合同；
9. 实现了 Claim-level 支持判断、retained/removed Claim 过滤、`PARTIAL_PASS` 和 strict 消融模式；
10. 实现了 routing/retrieval/packing/generation/verification/retry/end-to-end 的逐次 trace；
11. 提供带真实 model/backend/fallback/预热/延迟状态的响应式 Streamlit 演示界面；
12. 建立了冻结题集、哈希、消融、人工评分和一次性 release 护栏。

尚不能算已完成贡献：Dense Retrieval、Neo4j 正式部署基准和独立双人标注。v2 四方法自动与用户确认人工指标已完成，但只适用于当前 23 题小样本。

## 31. 常见答辩问答

### Q1：为什么不用纯 LLM？

纯 LLM 难以限定六页知识范围，也无法稳定提供可核验的官方出处。项目把 LLM 限制在“基于当前证据组织答案”的角色，并让 Verifier 检查引用和问题对齐。

### Q2：为什么需要知识图谱？

TF-IDF 适合找相似文本，但“属于哪个方法族、解决什么任务、与什么不同、通过什么路径关联”等结构问题更适合显式关系。Pilot 中 Graph Only 和 Proposed 的 Recall@5 高于 Vector RAG，但样本较小，只能作描述性结论。

### Q3：为什么图谱是预定义而不是自动抽取？

项目周期短、领域小，预定义图谱更容易审核关系和绑定官方证据，也更适合做可控科研实践。自动抽取会引入实体合并、关系幻觉和额外标注问题，不在当前范围。

### Q4：这是不是完整 GraphRAG？

不是。它是 Knowledge-Graph-Enhanced RAG，借鉴图结构与文本证据结合思想，没有 Microsoft GraphRAG 的社区检测、社区摘要和 global search。

### Q5：为什么默认 NetworkX？

NetworkX 无外部服务依赖，适合本地复现和答辩演示。Neo4j 实现保留了可扩展性，但正式结果不依赖数据库服务。

### Q6：Neo4j 是否完成？

Repository 和导入脚本已实现，但当前 Python 环境没有 neo4j 驱动，也没有正式 Neo4j 性能实验。因此只能说“代码接口已实现、后端可选”，不能说“Neo4j 已完成正式部署评测”。

### Q7：Chroma 是否就是 Dense Retrieval？

不是。当前写入 Chroma 的向量由 TF-IDF 产生，在线路径也直接读取 TF-IDF pickle。只有以后接入多语言神经 Embedding 并完成对比，才能称为 Dense Retrieval。

### Q8：LLM 在哪里参与？

LLM 只参与 answer 节点，把检索证据组织成结构化 Claims。Router 仍是规则，Retriever 和 Verifier 也是确定性模块。

### Q9：为什么不用 LLM Planner？

`qwen3:4b` 在 20 次 QueryPlan 探针中只有 1 次语义正确，虽然 20/20 JSON Schema 合法。使用它会降低路由质量，因此保持 Rule Router。

### Q10：如何防止 LLM 编造？

Prompt 禁止使用模型记忆；每条 Claim 必须绑定真实 E ID 和逐字 quote；Packer 将可用 ID 限定为本次可见证据子集；程序检查 E/P/R ID 和 quote 子串；最终正文由 Claims 重建；Verifier 再检查术语、路径和问题限定条件。

### Q11：过度拒答修复到什么程度？

阶段 8.3 先解决了“一个 Claim 失败导致所有支持 Claim 一起丢弃”的机制问题。阶段 8.5 完整 dev 候选进一步把 answerable over-refusal 从历史 4/8 降到 1/8，retry 从 7/10 降到 3/10，且 unsupported Claim leakage 为 0。DEV02、DEV03、DEV10 返回 `partial_pass`；DEV05 因语料缺少 AdaBoost 权重机制原文仍拒答。这是开发集工程门槛，不是独立效果结论。

### Q12：Partial-pass 为什么重要？

它允许保留已被证据支持的 Claim，删除不支持 Claim，并明确披露其余方面证据不足。阶段 8.3 已实现该机制；`partial_pass` 只是验证状态，不自动等于人工正确答案。

### Q13：规则基线为什么比当前 LLM dev 准确？

规则模板直接使用图谱中已审核关系，输出范围小；LLM 会尝试组织更完整答案，触发更多 quote 和术语校验。历史候选 dev 中 LLM 有 4/8 可回答题被拒绝，Stage 8.5 candidate 已降为 1/8，但自动决策仍是 9/10，且 dev 已参与调试，不能与规则基线做独立优越性结论。剩余 DEV05 主要是固定语料没有直接 AdaBoost 机制证据。

### Q14：当前最好的正式结果是什么？

v1.0 规则基线 final 的 Decision Accuracy 为 39/40，4/4 无答案题正确拒答。v2 extension 中 Rule 的用户确认 Correctness 为 0.5870，Partial-pass 为 0.5217，No Verifier 为 0.7826；但 No Verifier 有 6/22 hallucination 和 0/4 自动拒答准确率。两套题集不能直接替代，v2 结果也不支持宣称 Partial-pass 全面优于规则基线。

### Q15：为什么不能重跑 final？

final 已经运行并查看结果，再根据它修改参数会造成测试泄漏。它只作为 v1.0 历史冻结结果保存。

### Q16：Pilot 为什么不再调参？

Pilot 曾用于发现并修复实现缺口，因此已被消费。后续只允许做预先声明门槛的冻结前回归，不能把它重新包装成独立测试集。

### Q17：Extension 运行到什么状态？

Stage 8.7 已按冻结 v2 release 执行且只执行一次：23 题、4 方法、92 次 QA 调用，receipt 状态为 `completed_once`。Stage 8.8 的 92 行盲评已由用户确认并在确认后解盲；不能再重跑 extension 或根据结果调参。

### Q18：项目的创新点是什么？

创新不在提出新基础模型，而在小型可控领域内把预定义图关系、官方文本证据、结构化 Claim、确定性验证、拒答与严格实验治理组合成一个可运行系统。

### Q19：目前最大的风险是什么？

当前主要风险是 LLM 方法平均延迟约 5.21 至 11.89 秒、Partial-pass 仍有 5/19 过度拒答和 2/4 无答案误接受、Correctness 未超过 Rule、样本规模小、单一确认而非双人标注，以及稀疏检索语义能力有限。Stage 8.4 已能定位延迟来源，但“可观测”不等于“延迟已经优化完成”。

### Q20：下一步是什么？

v1 revocation、v2 实验合同、Evidence Packer、原子 Claim Prompt v2、Claim-level Partial-pass、完整阶段 trace、Ollama 预热、Streamlit 状态展示、Stage 8.5 dev 审计、Stage 8.6 冻结、Stage 8.7 extension、Stage 8.8 用户确认盲评及图表误差分析、Stage 8.9 正式 DOCX 和 Stage 8.10 答辩 PPT 均已完成。下一步只编写逐页讲稿、现场演示步骤和故障预案；仍禁止重跑 final/extension、结果覆盖和 holdout 后调参。

## 32. 关联文档

- `PROJECT_GAPS_AND_ROADMAP.md`：不足、修复办法、优先级和暂缓项；
- `reports/llm_agent_partial_pass_plan.md`：Partial-pass v2 的详细执行合同；
- `reports/extension_v2/category_error_analysis_user_confirmed.md`：用户确认的类别指标、典型错误和答辩结论；
- `PROGRESS.md`：每个阶段的实际完成记录；
- `reports/research_report_draft.md`：最终报告的 Markdown 单一内容源；
- `reports/final/基于预定义知识图谱的轻量化混合GraphRAG科研实践报告.docx`：已完成渲染验收的 30 页正式报告；
- `reports/final/research_report_docx_manifest.json`：报告源稿、生成器、图表、目录和输出哈希清单；
- `reports/final/轻量化混合GraphRAG科研实践答辩.pptx`：已完成渲染与布局验收的 14 页答辩 PPT；
- `reports/technical_enhancement_decision.md`：LLM/Dense 前置审计；
- `reports/llm_generator_dev_audit.md`：LLM dev 三轮结果；
- `reports/extension_holdout_freeze.md`：extension 冻结与哈希；
- `reports/llm_agent_v2_extension_stage8_7_audit.md`：一次性执行、自动指标、错误边界、产物哈希和盲评状态；
- `reports/llm_agent_v2_extension_stage8_8_user_confirmed_audit.md`：用户确认指标、解盲结论、分母和输出哈希；
- `reports/report_claims_checklist.md`：可声明和禁止声明；
- `reports/releases/v1.0-baseline/release_notes.md`：v1.0 归档说明。

本手册描述的是 2026-07-25 Stage 8.10 完成后的项目状态。后续每完成一个阶段，应同步更新本文的状态表、实验结果和常见问答，同时继续在 `PROGRESS.md` 追加不可回写的阶段记录。
