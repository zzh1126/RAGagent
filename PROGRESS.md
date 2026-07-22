# 项目进度记录

本文档用于持续记录每次完成的开发工作。之后每一轮实质性改动都会追加记录，包含完成事项、涉及文件、验证结果和下一步计划。

## 2026-07-22 阶段 1：项目骨架与图谱底座

### 完成事项

- 固定项目路径为当前工作区 `E:\RAGagent`，不迁移到 `E:\ml_qa_agent`。
- 创建基础项目目录：
  - `config/`
  - `data/raw/html/`
  - `data/processed/`
  - `data/graph/`
  - `data/chroma/`
  - `data/evaluation/`
  - `scripts/`
  - `src/`
  - `app/`
  - `tests/`
  - `reports/`
- 创建配置文件：
  - `config/sources.yaml`
  - `config/ontology.yaml`
  - `config/settings.yaml`
  - `.env.example`
  - `requirements.txt`
- 创建统一路径模块：
  - `src/paths.py`
- 创建统一数据结构：
  - `TextEvidence`
  - `GraphTriple`
  - `GraphPath`
  - `LinkedEntity`
  - `RetrievalResult`
  - `AnswerPayload`
  - `ClaimResult`
  - `VerifyResult`
  - `FinalResponse`
- 创建统一图仓储接口：
  - `src/graph/repository.py`
- 创建两个图后端实现：
  - `src/graph/networkx_repository.py`
  - `src/graph/neo4j_repository.py`
- 创建初始图谱数据：
  - `data/graph/entities.csv`：50 个实体
  - `data/graph/relations.csv`：100 条关系
- 关系数据按 Day 1 策略处理：
  - 当前全部为页面级证据。
  - 当前全部为 `pending`。
  - 系统正式运行时只读取 `approved` 关系。
  - Day 3 生成真实 chunk 后再绑定 `evidence_chunk_ids` 并改为 `approved`。
- 创建校验和构建脚本：
  - `scripts/validate_config.py`
  - `scripts/validate_graph_data.py`
  - `scripts/build_neo4j.py`
- 创建测试：
  - `tests/conftest.py`
  - `tests/test_graph_repository.py`
- 完成“随机森林”局部图冒烟验收，能够输出：
  - `随机森林 -BELONGS_TO-> 集成学习`
  - `随机森林 -USES-> 决策树`
  - `随机森林 -HAS_ADVANTAGE-> 方差`

### 验证结果

以下命令均已通过：

```bash
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/build_neo4j.py
pytest -q
```

验证摘要：

- 配置校验通过：6 个 scikit-learn 官方文档来源，7 类本体节点。
- 图数据校验通过：50 个实体，100 条关系，100 条 `pending`，0 条 `approved`。
- NetworkX 图加载通过：50 个节点，100 条边。
- Pytest 通过：2 个测试全部通过。

### 当前状态

项目已完成第一阶段：基础目录、配置、统一 schema、图仓储接口、NetworkX 降级后端、Neo4j 后端骨架、初版实体关系数据和校验脚本。

下一阶段进入 Day 2：抓取六页 scikit-learn 官方文档，抽取主内容，生成 section 和稳定 chunk，并构建 Chroma 向量库。

## 2026-07-22 阶段 2：官方文档采集、chunk 与向量检索

### 完成事项

- 创建文档采集脚本：
  - `scripts/fetch_sources.py`
- 创建 HTML 解析与切分模块：
  - `src/ingestion/html_processing.py`
- 创建 chunk 构建脚本：
  - `scripts/build_chunks.py`
- 创建 chunk 校验脚本：
  - `scripts/validate_chunks.py`
- 创建向量检索与查询改写模块：
  - `src/retrieval/query_rewrite.py`
  - `src/retrieval/vector_retriever.py`
  - `src/retrieval/vector_rag.py`
- 创建向量库构建与查询脚本：
  - `scripts/build_chroma.py`
  - `scripts/query_vector.py`
  - `scripts/vector_answer.py`
- 完成六页官方文档抓取并缓存到：
  - `data/raw/html/`
- 完成文档主内容抽取与 chunk 生成：
  - `data/processed/sections.jsonl`
  - `data/processed/chunks.jsonl`
- 为了符合方案上限，增加按来源封顶的 chunk 选择策略，使最终 chunk 数固定为 180。
- 在本机缺少 `chromadb` 和 `sentence_transformers` 的情况下，自动构建 TF-IDF fallback 索引到：
  - `data/chroma/tfidf/`
- 完成两道 Day 2 验收题的向量检索冒烟：
  - “随机森林为什么更稳定”
  - “类别不平衡时用什么指标”
- 完成中文答案和官方引用的基础输出。

### 验证结果

以下命令已通过：

```bash
python scripts/fetch_sources.py
python scripts/build_chunks.py
python scripts/validate_chunks.py
python scripts/build_chroma.py
python scripts/vector_answer.py "随机森林为什么更稳定"
python scripts/vector_answer.py "类别不平衡时用什么指标"
pytest -q
```

验证摘要：

- 6 个官方页面全部抓取成功并缓存。
- 生成 164 个 section。
- 最终保留 180 个 chunk，满足当前冻结范围。
- chunk 校验通过，来源分布稳定。
- 向量库当前使用 TF-IDF fallback，因为 `chromadb` 尚未安装。
- 中文问题已能检索到对应英文官方文档证据，并生成带引用的中文答案。

### 当前状态

Day 2 已完成主要目标。下一阶段进入 Day 3：补充图谱关系证据绑定，准备把 `pending` 关系升级为 `approved`，并实现图检索接口与 Graph Only 基线。

## 2026-07-22 阶段 2.1：依赖补齐与离线 Chroma 调整

### 完成事项

- 安装缺失依赖：
  - `chromadb`
  - `sentence-transformers`
- 修复 pip 自动升级带来的兼容冲突：
  - 将 `protobuf` 调整回 `streamlit` 兼容范围
  - 将 `rich` 调整回 `streamlit` 兼容范围
- 调整向量库构建策略：
  - 不再依赖 Hugging Face 在线模型下载
  - 改为使用本地 TF-IDF 向量构建 Chroma collection
  - 保留 `sentence-transformers` 作为可选依赖，但当前不作为构建前置条件
- 成功构建离线 Chroma 索引：
  - `data/chroma/chroma/`
- 确认现有向量问答链路仍可正常工作。

### 验证结果

以下命令已通过：

```bash
python scripts/build_chroma.py
python scripts/vector_answer.py "随机森林为什么更稳定"
pytest -q
```

### 当前状态

Day 2 已完成并增强为离线可运行版本。向量库现在既有可复现的本地 embedding 构建，也保留了后续替换更强 embedding 模型的接口空间。

## 2026-07-22 阶段 3：图谱证据绑定与图检索

### 完成事项

- 创建实体链接模块：
  - `src/retrieval/entity_linker.py`
- 创建图检索模块：
  - `src/retrieval/graph_retriever.py`
- 创建图查询冒烟脚本：
  - `scripts/query_graph.py`
- 创建图证据绑定脚本：
  - `scripts/bind_graph_evidence.py`
- 创建图证据校验脚本：
  - `scripts/validate_graph_evidence.py`
- 将 `data/graph/relations.csv` 中全部 100 条关系从 `pending` 升级为 `approved`。
- 为 100 条关系绑定真实的 `evidence_chunk_ids`，来源于 `data/chroma/chunks_snapshot.jsonl`。
- 完成图谱到原文 chunk 的回指闭环。
- 验证随机森林和 Bagging / Boosting 相关图查询可正常返回路径与证据。

### 验证结果

以下命令已通过：

```bash
python scripts/bind_graph_evidence.py
python scripts/query_graph.py "随机森林属于什么模型族"
python scripts/query_graph.py "Bagging 和 Boosting 有什么区别"
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/build_neo4j.py
pytest -q
```

验证摘要：

- 100 条关系全部为 `approved`。
- 100 条关系均绑定了真实 chunk 证据。
- Graph Retriever 能输出实体链接、图路径和证据 chunk。
- `Bagging 和 Boosting 有什么区别` 已能回显图路径与对应官方证据。
- 全量测试通过，当前共 7 个测试全部通过。

### 当前状态

Day 3 已完成。下一阶段进入 Day 4：把 Vector / Graph / Hybrid 三路检索统一接入 LangGraph 主流程，并开始做证据融合与验证拒答。

## 2026-07-22 阶段 4：统一检索工作流、证据验证与拒答

### 完成事项

- 创建意图路由模块 `src/retrieval/intent_router.py`：
  - 关系问题路由到 Graph；
  - 定义问题路由到 Vector；
  - 解释、对比、推荐和多跳问题路由到 Hybrid。
- 创建统一混合检索模块 `src/retrieval/hybrid_retriever.py`：
  - 统一输出 `RetrievalResult`；
  - 合并图证据与向量证据；
  - 按 `chunk_id` 去重并重新生成稳定的 `E1...En` 引用编号。
- 增强实体链接与图检索：
  - 支持常见中文类型后缀归一化；
  - 支持按关系方向查询入边和出边；
  - 指标推荐可以从“类别不平衡问题”反向找到平衡准确率、F1 分数和准确率的相关关系；
  - 对比问题优先使用 `DIFFERS_FROM`，避免把普通路径误当成差异结论。
- 创建离线可运行的证据回答器 `src/agent/answer_generator.py`：
  - 每条 claim 绑定一个或多个证据编号；
  - 图关系转为中文可读句子；
  - 对全称判断添加限定说明；
  - 无证据时生成明确拒答文本。
- 创建证据验证器 `src/verification/evidence_verifier.py`：
  - 校验引用 ID；
  - 校验图路径是否存在于 approved 图中；
  - 检查问题关键属性是否在同一主题证据中出现；
  - 证据不足时最多重试一次，仍不足则拒答。
- 创建工作流 `src/agent/workflow.py` 和命令行入口 `scripts/run_agent.py`：
  - LangGraph 已预留完整节点和条件边；
  - 当前机器因包源连接超时未能安装 `langgraph`，自动使用等价的本地状态机执行；
  - LangGraph 安装后会自动切换到真实 `StateGraph`，不需要修改业务节点。
- 工作流工厂支持通过 `GRAPH_BACKEND` 在 NetworkX 和 Neo4j 实现之间切换，业务检索器不感知后端类型。
- 更新 `README.md`、`config/settings.yaml` 和 `requirements.txt`，补充 Day 4 运行入口及 `min_vector_score` 配置。
- 新增 Day 4 回归测试，覆盖三种路由、Hybrid 问答、入边指标检索、一次重试、未知问题拒答、外部算法引用拒答和实体未支持属性拒答。

### 验证结果

以下命令已串行通过：

```bash
python -m compileall -q src scripts
pytest -q
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/build_neo4j.py
python scripts/run_agent.py "随机森林为什么更稳定"
python scripts/run_agent.py "类别不平衡时用什么指标"
python scripts/run_agent.py "XGBoost 如何处理缺失值"
python -m pip check
```

验证摘要：

- Pytest：14 个测试全部通过；
- 配置、图数据和 100 条 approved 关系的 chunk 回指校验通过；
- “随机森林为什么更稳定”：Hybrid，`pass`，证据分数 `1.0000`；
- “类别不平衡时用什么指标”：Hybrid，`pass`，返回准确率局限、平衡准确率和 F1 分数关系；
- “随机森林的学习率是多少”：扩大检索一次后 `refuse`；
- “XGBoost 如何处理缺失值”：识别为当前六页文档外问题，`refuse`；
- 当前工作流引擎为 `local-state-machine`，原因是 `langgraph` 包尚未成功下载，不影响离线开发和测试。

### 当前状态

Day 4 的核心检索、回答、验证和拒答链路已完成。下一阶段进入 Day 5：构建 Streamlit 演示界面、整理统一响应展示，并准备开发集、演示题和正式 40 题评测数据结构。`langgraph` 的真实运行时安装仍需在包源可访问时补做一次验证。

## 2026-07-22 阶段 5：LangGraph 运行时、Streamlit 演示与冻结评测

### 完成事项

- 成功安装并启用 `langgraph 1.0.10`：
  - `QAWorkflow` 已从本地兼容执行器自动切换为真实 `StateGraph`；
  - 命令行输出已确认 `ENGINE: langgraph`；
  - `pip check` 未发现依赖冲突。
- 完成 Streamlit 演示应用 `app/streamlit_app.py`：
  - 支持输入问题和选择 8 道演示题；
  - 显示检索模式、问题类型、证据分数、重试次数和耗时；
  - 分页展示回答、图路径、官方证据和验证详情；
  - 支持下载完整 `FinalResponse` JSON；
  - 移动端默认收起侧栏，避免遮挡主问答表单。
- 创建评测数据与说明：
  - `data/evaluation/dev_questions.jsonl`：10 道开发题；
  - `data/evaluation/demo_questions.jsonl`：8 道演示题；
  - `data/evaluation/pilot_questions.jsonl`：40 道先导题；
  - `data/evaluation/final_questions.jsonl`：40 道冻结保留题；
  - `data/evaluation/README.md`：字段、分割及防泄漏规则。
- 创建评测工具：
  - `scripts/validate_evaluation.py`；
  - `scripts/run_evaluation.py`；
  - 输出总体准确率、关键词覆盖、实体覆盖、引用率、延迟和分类指标。
- 正式集保持预定分布：
  - 单跳关系 8；
  - 多跳关系 9；
  - 定义解释 7；
  - 对比 5；
  - 原理与优缺点 5；
  - 指标选择 2；
  - 无答案 4。
- 新增评测数据回归测试 `tests/test_evaluation_data.py`，锁定题量、分布、无答案数量和数据集零题面重合。
- 增强图检索与 Verifier：
  - 多跳查询对多个目标实体分别搜索并优先保留最短路径；
  - 补充 `R2` 实体别名；
  - 确认式问题会校验算法与任务、方法族或技术之间是否存在 approved 关系；
  - 修正关系问题同义词和多指标聚合。
- 修复 Windows 命令行输出 `R²` 等字符时的 UTF-8 编码问题。
- 更新 `README.md` 和 `requirements.txt`，移除未直接使用的完整 LangChain 依赖。

### 评测方法说明

首套 40 题曾用于发现两处实现缺口，因此已重命名为 `pilot`，不能作为无泄漏最终结果。其修复后回归结果保存在：

```text
reports/evaluation_pilot_postfix.json
```

随后重新创建了一套与开发集、先导集题面均不重合的 40 题保留集。该保留集冻结后仅运行一次，未根据结果继续修改路由、阈值或回答逻辑。

### 验证结果

以下命令已通过：

```bash
python -m compileall -q app src scripts tests
python scripts/validate_evaluation.py
python scripts/run_evaluation.py --split dev
python scripts/run_evaluation.py --split final
pytest -q
python -m pip check
```

开发集结果：

- 10 题决策准确率：`1.0000`；
- 平均关键词覆盖：`1.0000`；
- 平均实体覆盖：`1.0000`；
- 引用率：`1.0000`。

冻结保留集唯一一次结果：

- 40 题中 39 题决策正确；
- 决策准确率：`0.9750`；
- 4 道无答案题全部正确拒答；
- 引用率：`0.9750`；
- 平均关键词覆盖：`0.8375`；
- 平均实体覆盖：`0.9208`；
- 平均工作流耗时：`1.48 ms`；
- 唯一错误：`T-DF-01` AdaBoost 定义题被保守拒答；
- 完整结果：`reports/evaluation_final.json`。

浏览器验收：

- Streamlit 服务运行于 `http://localhost:8501`；
- 桌面视口 `1440 x 1000`：问答通过、5 个主指标和 4 个页签完整显示，无横向溢出；
- 移动视口 `390 x 844`：问答通过、侧栏默认收起，无横向溢出；
- 正常问题 `Verifier: PASS` 与错误前提问题 `Verifier: REFUSE` 均完成真实点击验证；
- 服务错误日志为空；
- 截图保存在：
  - `reports/streamlit_desktop_final.png`；
  - `reports/streamlit_mobile_final.png`；
  - `reports/streamlit_refuse.png`。

### 当前状态

Day 5 已完成。项目现在具有真实 LangGraph 编排、NetworkX/Neo4j 可切换图接口、离线向量检索、证据验证与拒答、Streamlit 演示界面，以及严格分割的开发/演示/先导/正式评测集。下一阶段进入 Day 6：整理消融实验、误差分析、最终科研报告与演示材料。

## 2026-07-22 阶段 6.1：冲刺方案审阅与 v1.0 基线冻结

### 完成事项

- 完整阅读并审计 `剩余四天冲刺方案_消融实验_误差分析_技术增强与科研报告.docx`：
  - 提取 253 个段落和 53 张表格到 `reports/sprint_plan_extracted.txt`；
  - 使用本机 Word 导出 18 页 PDF 和逐页 PNG；
  - 完成第 1～18 页视觉检查，未发现影响阅读的表格截断或分页问题；
  - 确认后续顺序固定为：冻结 v1.0、主实验与 No Verifier 消融、人工评分与误差分析、报告骨架、单个技术增强、独立 extension holdout、最终交付。
- 新增不可覆盖式冻结工具 `scripts/freeze_baseline.py`：
  - 默认只允许首次创建 `v1.0-baseline`；
  - 已存在归档不会被覆盖，只能通过 `--verify` 做完整性检查；
  - 自动生成数据统计、环境信息、`pip freeze`、Git 状态说明、发布说明、代码快照和 SHA-256 清单。
- 创建正式基线归档 `reports/releases/v1.0-baseline/`，共冻结 23 个受清单保护的 payload 文件：
  - 正式保留集和 pilot 评测结果；
  - 桌面、移动端和拒答流程三张最终截图；
  - `requirements.txt`、完整 `pip freeze` 和三份 YAML 配置；
  - `entities.csv`、`relations.csv`、`chunks_snapshot.jsonl`；
  - dev、demo、pilot、final 四套评测题及数据说明；
  - `data_statistics.json`、`environment.txt`、`git_commit.txt` 和 `release_notes.md`；
  - 包含 53 个代码、测试、配置和项目入口文件的 `source_snapshot.zip`。
- 当前工作区不是 Git 仓库，因此无法创建真实 commit 和 `v1.0-baseline` tag：
  - 该事实已明确写入 `git_commit.txt`；
  - 使用 `source_snapshot.zip`、`manifest.json` 和 `MANIFEST_SHA256.txt` 作为可核验的冻结替代；
  - 未伪造 Git commit 或 tag。
- 冻结过程只读取已有 `reports/evaluation_final.json`，没有重新运行 final 40 题，也没有针对 `T-DF-01` 调整系统，保留集唯一一次结果未被覆盖。

### 冻结统计

- 文档来源：6；
- Section：164；
- Chunk：180；
- 图实体：50；
- approved 图关系：100，且 100 条均绑定 Chunk 证据；
- 数据集：dev 10、demo 8、pilot 40、final 40；
- dev/final 题面重合：0；
- pilot/final 题面重合：0；
- final 决策准确率：`0.9750`；
- 无答案题拒答：4/4；
- 唯一失败：`T-DF-01`；
- Manifest SHA-256：`2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`。

### 验证结果

以下命令均已通过：

```bash
python -m py_compile scripts/freeze_baseline.py
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/validate_evaluation.py
pytest -q
python -m pip check
python scripts/freeze_baseline.py
python scripts/freeze_baseline.py --verify
```

验证摘要：

- Pytest：`18 passed`；
- 依赖检查：`No broken requirements found`；
- 归档校验：23 个 payload 文件的大小与 SHA-256 全部匹配；
- Streamlit 进程仍在运行，地址为 `http://localhost:8501`。

### 当前状态

方案要求的第一个冲刺动作已经完成，`v1.0-baseline` 现在是独立、可审计且不会被后续增强覆盖的交付基线。下一阶段只进入实验基础设施：先冻结 Vector RAG、Graph Only、Proposed 和 No Verifier 的统一实验配置与输出 Schema，再运行主实验和必做消融；暂不开始技术增强。

## 2026-07-22 补充：Git 认证与本地仓库补齐

### 完成事项

- 核实用户的 Git 登录状态：
  - Git Credential Manager 的 GitHub 账号为 `zzh1126`；
  - 全局 Git 身份为 `zzh1126 <2435539971@qq.com>`；
  - 因此此前归档中的“Git repository unavailable”只表示冻结当时工作区没有 `.git`，不表示用户没有登录 GitHub。
- 在 `E:\RAGagent` 创建本地 Git 仓库：
  - 分支：`main`；
  - 新增 `.gitignore`，忽略 Python/pytest 缓存、实际 `.env` 和运行日志；
  - 保留知识库、Chroma 索引、评测结果、截图和方案文档以支持基线复现。
- 创建基线 commit 和 annotated tag：
  - commit：`04f54f6039023b1165f569efef3a5191c52dde19`；
  - message：`release: freeze complete GraphRAG QA baseline`；
  - tag：`v1.0-baseline`，已确认指向上述 commit。
- 当前没有配置 `origin` 远程地址，因此没有执行 push；不会猜测或写入远程仓库地址。

### 验证结果

- `git status --short --branch`：工作树干净，当前分支为 `main`；
- `git rev-list -n 1 v1.0-baseline` 与 `git rev-parse HEAD` 完全一致；
- 暂存/提交文件中没有实际 `.env`、缓存目录或日志文件；
- GitHub Credential Manager 登录状态仍可查询到 `zzh1126`。

### 当前状态

v1.0 现在同时具备文件归档校验和本地 Git commit/tag 两种版本固定方式。后续实验应从当前 `v1.0-baseline` tag 创建独立分支；远程推送需要先确定目标仓库地址，当前不自动执行。

## 2026-07-22 补充：v1.0 发布到 GitHub 远程仓库

### 完成事项

- 配置远程仓库：`https://github.com/zzh1126/RAGagent.git`。
- 推送前检查确认远程仓库为空，本地工作树干净，因此不需要合并，也没有使用 force push。
- 已成功推送：
  - `main` 分支，包含当前基线 commit 和 Git 设置记录；
  - `v1.0-baseline` annotated tag，指向冻结 commit `04f54f6039023b1165f569efef3a5191c52dde19`。
- 本地 `main` 已设置为跟踪 `origin/main`。

### 验证结果

```bash
git push -u origin main
git push origin v1.0-baseline
```

两条命令均成功。未执行任何强制推送或远程历史覆盖操作。

### 当前状态

v1.0 基线已经同时存在于本地归档、本地 Git tag 和 GitHub 远程仓库。后续实验从 `v1.0-baseline` 创建独立分支，实验过程中的每次实质性改动继续追加到本文件并同步提交。

## 2026-07-22 阶段 6.2：主实验与消融配置合同

### 完成事项

- 从 `v1.0-baseline` 的历史分支创建独立实验分支：
  - `experiment/day6-main-ablation`；
  - 本轮所有实验基础设施改动都不会修改 `main` 或移动 `v1.0-baseline` tag。
- 新增统一实验协议 `config/experiments.yaml`：
  - 调参集：`dev`；
  - 实验运行集：`pilot`；
  - `final`：只读，只复用已有 `reports/evaluation_final.json`；
  - 检索指标固定为 Recall@5；
  - 统一使用离线规则生成器；
  - `Direct LLM` 明确禁用，不伪造联网模型结果。
- 冻结本轮方法矩阵：
  - `vector_rag`：固定 Vector、关闭 Verifier；
  - `graph_only`：固定 Graph、关闭 Verifier；
  - `proposed`：Adaptive 路由、启用 Verifier；
  - `no_verifier`：Adaptive 路由、关闭 Verifier；
  - `no_router`：可选且暂时禁用。
- 新增配置加载与约束模型 `src/evaluation/config.py`：
  - 校验必需方法、路由模式、Verifier 开关和 final 只读政策；
  - 为完整配置生成稳定 SHA-256 指纹：
    - `56dd6a55fd05a01490322283926a722a3fe0260d4b4b6534f21d2900ba04c44a`。
- 新增统一结果 Schema `src/evaluation/schemas.py`：
  - `MetricValue`：区分已计算、待人工评分和不适用；
  - `LatencyBreakdown`：路由、检索、生成、验证和总耗时；
  - `HumanAssessment`：正确性、忠实度、幻觉、过度拒答和评审备注；
  - `QuestionRunResult`：题目、决策、证据、路径、Chunk、延迟和错误阶段；
  - `ExperimentMetrics`：决策准确率、回答正确性、忠实度、Recall@5、路径有效性、拒答、幻觉、过度拒答、引用率和延迟；
  - `ExperimentRunReport`：实验配置快照、数据集哈希、配置指纹、逐题结果和指标。
- 新增 `scripts/validate_experiments.py` 和 `reports/experiments/README.md`，可在不运行问答的情况下检查协议及 final 文件存在性。
- 新增 4 个实验合同测试，覆盖配置矩阵、final 禁止调参、自动指标与人工指标分离、结果数量一致性。

### 验证结果

以下命令均已通过：

```bash
python -m compileall -q app src scripts tests
python scripts/validate_experiments.py
python scripts/validate_evaluation.py
pytest -q
python -m pip check
python scripts/freeze_baseline.py --verify
```

结果：

- Pytest：`22 passed`；
- 评测集：dev 10、demo 8、pilot 40、final 40，分布和零重合规则通过；
- 依赖检查通过；
- v1.0 归档 23 个 payload 哈希继续匹配；
- final 结果文件未重新生成，SHA-256 保持不变；
- 本阶段没有运行 Vector、Graph、Proposed 或 No Verifier 实验，也没有生成实验结果文件。

### 当前状态

实验协议和输出合同已经冻结，下一步才实现实验运行器：根据上述配置切换固定路由、关闭 Verifier，并将每题输出写入 `ExperimentRunReport`。运行器完成并通过回归测试后，再运行 `pilot` 上的四组主实验；仍不会重新运行或调参 `final` 保留集。

## 2026-07-22 阶段 6.3：实验运行器与 Verifier 消融适配

### 完成事项

- 扩展 `src/agent/workflow.py`，允许实验工厂注入自定义 Router 和 Verifier；默认工作流仍使用原有 EvidenceVerifier。
- 新增 `src/evaluation/workflow_factory.py`：
  - `ConfiguredRouter` 保留原始意图识别，只按实验配置强制 Vector、Graph 或 Hybrid；
  - `NoVerifier` 旁路不进行验证、不重试，固定输出 `pass`，但保留未支持 Claim 供幻觉分析；
  - 禁止构建 Direct LLM 和其他禁用实验。
- 新增 `scripts/run_experiments.py`：
  - 按 `config/experiments.yaml` 读取实验矩阵；
  - 默认运行集为 `pilot`，支持 `dev` 调试；
  - `final` split 永久拒绝，避免误触发冻结集重跑；
  - 已存在输出时拒绝覆盖；
  - 输出统一 `ExperimentRunReport` JSON，包含配置快照、数据集哈希、逐题证据、路径、延迟和自动/人工指标状态；
  - `Recall@5` 只对能由 approved 图关系保守推导 gold Chunk 的题计算，其余不伪造指标；
  - `--dry-run` 只显示执行计划，不调用工作流。
- 修复一个会影响消融有效性的接入问题：默认工作流不再覆盖传入的 NoVerifier 实例。
- 新增运行器回归测试，覆盖固定路由、NoVerifier 行为、工厂模式切换和禁用 Direct LLM 拦截。

### 验证结果

```bash
python -m compileall -q app src scripts tests
pytest -q
python scripts/run_experiments.py --dry-run
python scripts/run_experiments.py --split final
python scripts/validate_experiments.py
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/validate_evaluation.py
python -m pip check
python scripts/freeze_baseline.py --verify
```

结果：

- Pytest：`26 passed`；
- dry-run 正确列出 `vector_rag`、`graph_only`、`proposed`、`no_verifier` 四个 pilot 输出；
- final 防护命令按预期失败并提示复用 `reports/evaluation_final.json`；
- 图数据、证据回指、评测集和依赖检查通过；
- v1.0 归档哈希继续匹配；
- `reports/experiments/` 目前只有 README，尚未生成任何实验结果。

### 当前状态

实验运行器已经可以安全执行，但本阶段按分步要求只完成实现和 dry-run 验证。下一步运行四组 `pilot` 主实验并保存 JSON 结果，随后再做人工评分表，不触碰 `final` 保留集。

## 2026-07-22 阶段 6.4：Pilot 主实验、No Verifier 消融与比较材料

### 完成事项

- 使用冻结配置在 `pilot` 40 题上正式运行四组离线实验：
  - `reports/experiments/vector_rag_pilot.json`；
  - `reports/experiments/graph_only_pilot.json`；
  - `reports/experiments/proposed_pilot.json`；
  - `reports/experiments/no_verifier_pilot.json`。
- 四份报告均满足统一 `ExperimentRunReport` Schema，并具有相同的：
  - pilot 数据集 SHA-256：`fa48ddcb3e7f4ec794b9b95c0415b5f1ddbc937d6f2918987a29dd9abb7a19b0`；
  - 配置指纹：`56dd6a55fd05a01490322283926a722a3fe0260d4b4b6534f21d2900ba04c44a`；
  - 题目数量和顺序：每种方法 40 题。
- 新增 `scripts/compare_experiments.py`，对四份报告执行交叉校验并生成：
  - `reports/experiments/pilot_comparison.csv`；
  - `reports/experiments/pilot_comparison.json`；
  - `reports/experiments/pilot_comparison.md`。
- 新增 `scripts/build_human_scoring_template.py`，生成 `reports/human_scoring.csv`：
  - 共 160 行，即 4 种方法 × 40 题；
  - 已预填问题、题型、期望决策和实际决策；
  - `correctness_score`、`faithfulness_score`、`hallucination`、`over_refusal`、`reviewer` 均保持空白；
  - 当前文件是待人工评审模板，未伪装成已完成的人工作分。

### 自动实验结果

| 方法 | 决策准确率 | 引用率（可回答题） | 无答案拒答准确率 | Recall@5 | 路径有效率 | 平均本地耗时 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Vector RAG | 0.9000 | 1.0000 | 0.0000 | 0.8276 | 不适用 | 1.325 ms |
| Graph Only | 0.9000 | 1.0000 | 0.0000 | 0.9655 | 1.0000 | 1.000 ms |
| Proposed | 1.0000 | 1.0000 | 1.0000 | 0.9655 | 1.0000 | 1.700 ms |
| No Verifier | 0.9000 | 1.0000 | 0.0000 | 0.9655 | 1.0000 | 1.225 ms |

结果解释边界：

- 四种方法在 36 道可回答题上均作出了正确的 pass 决策，但这不等于人工回答正确性均为 100%。
- Proposed 正确拒答 4/4 无答案题；Vector RAG、Graph Only 和 No Verifier 均对 4 道无答案题作答，因此其 pilot 决策准确率为 36/40。
- No Verifier 结果说明仅有引用并不能保证回答与问题匹配；相关幻觉和忠实度仍需人工审查。
- Vector RAG 在保守图关系 gold Chunk 子集上的 Recall@5 为 0.8276，低于包含图检索的三种配置 0.9655。
- 耗时为本地离线热路径测量，不代表在线 LLM 延迟。
- 以上是 pilot 方法比较，不替代 v1.0 的 final 唯一一次冻结结果。

### 验证结果

```bash
python scripts/run_experiments.py --split pilot
python scripts/compare_experiments.py --split pilot
python scripts/build_human_scoring_template.py --split pilot
python -m compileall -q app src scripts tests
pytest -q
python scripts/validate_experiments.py
python scripts/validate_evaluation.py
python -m pip check
python scripts/freeze_baseline.py --verify
```

- Pytest：`26 passed`；
- 四份报告均通过 Pydantic Schema 校验；
- 比较脚本确认题量、题序、数据集哈希和配置指纹一致；
- 评测集、依赖和 v1.0 归档完整性继续通过；
- `reports/evaluation_final.json` 未重新生成，SHA-256 仍为 `BB468FD0E3B63CFEA6A3319D1C9AEB0573C8842B18FED17931545A7D906D55FC`。

### 当前状态

主实验和必做 No Verifier 消融的自动结果已经保存，横向比较材料可直接用于报告。下一阶段集中完成人工正确性/忠实度评分，并据此计算 Answer Correctness、Evidence Faithfulness、Hallucination Rate，随后整理至少 8 个错误或边界案例。

## 2026-07-22 阶段 6.5：初步语义评分、统一指标表与 9 案例误差分析

### 完成事项

- 保留原始空白人工评分模板 `reports/human_scoring.csv`，没有覆盖或伪造用户人工评审结果。
- 新增 `scripts/score_pilot_preliminary.py`，对 4 种方法 × 40 题执行可审计的 Codex 辅助初步语义复核：
  - 输出 `reports/human_scoring_pilot_preliminary.csv`；
  - 160 行均包含正确性 0/1/2、忠实度 0/1/2、幻觉、过度拒答、评分依据和 reviewer；
  - reviewer 固定为 `Codex-assisted preliminary review`；
  - review status 固定为 `preliminary_pending_user_confirmation`；
  - 支持“集成方法/集成学习”“过拟合/过拟合风险”等同义表达；
  - 显式区分实际决策和答案文本，例如 F-NA-01 的 pass 决策与拒答文本不混为一谈。
- 生成初步评分指标 `reports/experiments/pilot_human_metrics.json`。
- 新增 `scripts/summarize_scored_experiments.py`，把自动指标和初步语义评分合并为：
  - `reports/metrics_summary.csv`；
  - `reports/metrics_summary.md`。
- 新增 9 个错误或边界案例初稿 `reports/experiments/pilot_error_analysis_draft.md`：
  - 4 个无答案/错误前提案例；
  - Ridge 关系检索错误；
  - 随机森林多跳路径缺失；
  - SVC 特征缩放多跳不完整；
  - SVC 定义实体优先级错误；
  - 回归指标路由与关系方向错误；
  - 每个案例均记录发生阶段、具体原因和改进建议。
- 新增 `scripts/validate_scoring.py`，验证评分行数、方法分布、分值范围、唯一键、指标重算一致性和案例数量。

### 初步语义评分

以下结果只能表述为 Codex 辅助初步复核，用户确认前不能写成独立人工评分：

| 方法 | Answer Correctness* | Evidence Faithfulness* | Hallucination Rate* | Over-refusal Rate* |
| --- | ---: | ---: | ---: | ---: |
| Vector RAG | 0.5375 | 0.4875 | 0.0000 | 0.0000 |
| Graph Only | 0.8375 | 0.9250 | 0.0000 | 0.0000 |
| Proposed | 0.8625 | 1.0000 | 0.0000 | 0.0000 |
| No Verifier | 0.8000 | 0.8500 | 0.0000 | 0.0000 |

`*` 状态：`preliminary_pending_user_confirmation`。

结果解释：

- Proposed 的初步正确性和忠实度最高，但回答正确性 0.8625 明显低于自动决策准确率 1.0000，证明二者不能混用。
- 当前观察到的主要问题是回答不相关或信息不完整，而不是无证据专业事实，因此初步幻觉率为 0；该结论仍需用户复核。
- No Verifier 的主要损失是拒答与问题对齐，而非当前规则生成器下的明显事实幻觉。
- 所有结论只针对已参与调试的 pilot 集，不替代 final 冻结结果。

### 验证结果

```bash
python scripts/score_pilot_preliminary.py --split pilot
python scripts/summarize_scored_experiments.py
python scripts/validate_scoring.py
python -m compileall -q app src scripts tests
pytest -q
python scripts/validate_experiments.py
python scripts/validate_evaluation.py
python -m pip check
python scripts/freeze_baseline.py --verify
```

- Pytest：`26 passed`；
- 初步评分：160 行，四种方法各 40 行，无空分、无重复 method/question；
- 指标重算与 JSON 汇总一致；
- 误差分析案例：9；
- v1.0 归档校验通过；
- final 结果 SHA-256 仍为 `BB468FD0E3B63CFEA6A3319D1C9AEB0573C8842B18FED17931545A7D906D55FC`。

### 当前状态

自动实验、No Verifier 消融、初步语义评分和 9 案例误差分析已经形成完整科研材料。下一阶段可在不等待最终人工确认的前提下先搭建科研报告骨架，但报告中必须把带星号指标标为初步辅助评分；用户确认评分后再移除该限定。

## 2026-07-22 阶段 6.6：科研报告初稿、事实声明清单与自动校验

### 完成事项

- 新增 `reports/research_report_draft.md`，形成可继续排版的完整科研报告初稿：
  - 包含摘要、关键词、绪论、相关技术、数据与知识库、系统架构、核心方法、系统实现、实验结果、误差分析、有效性威胁、总结、参考文献和复现实验附录；
  - 明确 RQ1～RQ3，并使用轻量化混合 GraphRAG / Knowledge-Graph-Enhanced RAG 的准确课题定位；
  - 写入 6 个来源、164 个 Section、180 个 Chunk、50 个实体和 100 条 approved 关系的可追溯规模；
  - 写入 v1.0 final 唯一一次冻结结果、四组 pilot 主实验、No Verifier 消融和 9 个误差案例；
  - 技术增强章节保持“待决策”，没有把未实现内容写成项目贡献；
  - Codex 辅助语义分数继续保留 `preliminary_pending_user_confirmation` 状态，没有写成独立人工评测。
- 完成报告逐项事实对账并收紧三处措辞：
  - 将“Verifier 显著提高”改为 pilot 4 道无答案题上的具体 0 到 1.0000 结果，避免暗示统计显著性；
  - 明确 Chroma collection 是构建产物，当前运行时读取本地 TF-IDF 稀疏索引；
  - 将“final 结果证明”改为限定在当前知识库与 40 题测试集上的“结果显示”，避免过度外推。
- 新增独立文档 `reports/report_claims_checklist.md`：
  - 列出 8 类权威证据源；
  - 固定 18 项必须保留的事实边界；
  - 列出禁止出现的错误结论和发布前检查命令。
- 新增 `scripts/validate_report_claims.py`：
  - 从基线统计、pilot 比较和初步语义指标 JSON 中读取真实数值，而不是仅检查硬编码文案；
  - 校验 13 项来源派生事实；
  - 校验 13 项必须披露的范围与指标边界；
  - 拦截 8 类高风险声明，包括“问答准确率 97.5%”“系统不会产生幻觉”“完整实现 Microsoft GraphRAG”和“在线 LLM 延迟 1.48 ms”；
  - 使用 6 个故意错误声明完成负向规则冒烟测试。

### 验证结果

```bash
python scripts/validate_report_claims.py
python -m compileall -q app src scripts tests
pytest -q
python scripts/validate_scoring.py
python scripts/validate_experiments.py
python scripts/validate_evaluation.py
python -m pip check
python scripts/freeze_baseline.py --verify
```

- 报告声明校验：13 项来源事实、13 项必需声明和 8 类禁止声明全部通过；
- Pytest：`26 passed`；
- 初步评分：160 行、4 种方法各 40 行、9 个误差案例，状态仍为 `preliminary_pending_user_confirmation`；
- 实验配置指纹继续为 `56dd6a55fd05a01490322283926a722a3fe0260d4b4b6534f21d2900ba04c44a`；
- 依赖检查无冲突；
- v1.0 归档 23 个 payload 校验通过，Manifest SHA-256 仍为 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`；
- 没有重新运行或调参 final 冻结集，原始 final 结果保持不变。

### 当前状态

科研保底版本现已具备代码、冻结结果、主实验、消融、初步语义复核、误差分析和完整报告初稿。下一阶段按照冲刺方案先形成技术增强决策文档：核实是否存在稳定真实 LLM 接口，只选择一个增强，并在任何开发前冻结独立 `extension_holdout`；若前置条件不满足，则保留 v1.0，不伪造增强结果。
