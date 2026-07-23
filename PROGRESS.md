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

## 2026-07-22 阶段 6.7：技术增强前置审计、真实 Ollama 探针与 No-Go 止损

### 完成事项

- 完成真实运行环境审计，没有仅凭 Python 包安装状态判断 LLM 可用性：
  - 本机已安装 Ollama `0.32.1`；
  - 本地服务真实监听 `127.0.0.1:11434`；
  - 已安装 `qwen3-vl:8b`，模型文件约 6.1 GB；
  - 当前没有 OpenAI、Anthropic、DashScope、DeepSeek 或 Azure OpenAI 密钥环境变量；
  - `openai`、`anthropic` 和 Python `ollama` 客户端未安装，但本地 Ollama HTTP API 可直接访问。
- 对增强 A“可插拔真实 LLM 结构化生成”执行真实前置探针：
  - 初始 5 次手工受控调用加 1 次自动复验，共 6 次；
  - JSON Schema 内容能够生成，但全部进入 `thinking` 字段；
  - 正式 `response` 或 `message.content` 均为空；
  - 正式答案字段结构化成功率为 `0/6`；
  - 冷启动墙钟耗时约 84.7 s，其中模型加载约 67.2 s；
  - 后续非首次调用耗时约 1.0～12.0 s；
  - 没有把 thinking 临时当作答案，也没有伪造 `AnswerPayload` 成功结果。
- 审计增强 B“Sparse + Dense + Graph”的前置条件：
  - `sentence-transformers` 与 PyTorch 已安装；
  - 本机 Hugging Face 缓存没有文本 Embedding 模型；
  - 现有缓存为 CLIP/ViT 图像相关模型，不能作为当前文本 Dense Retriever 的已验证模型；
  - 按冲刺方案的下载止损规则，本阶段不临时下载新模型绕开增强 A 的失败。
- 新增 `scripts/check_enhancement_readiness.py`：
  - 检查 Ollama 可达性、版本、模型清单和本地文本模型缓存；
  - 只输出已配置的环境变量名称，不输出任何密钥值；
  - `--probe-ollama` 通过真实 `/api/chat` 和 JSON Schema 检查正式答案字段；
  - thinking 内容不写入日志，只记录长度和是否包含 JSON；
  - `--require-ready` 在未满足输出合同时返回退出码 2，阻止误判为可实施状态。
- 新增独立决策文档 `reports/technical_enhancement_decision.md`：
  - 正式结论为 No-Go，本轮不实施增强 A 或 B；
  - 保留 v1.0，不生成 enhanced 指标；
  - 当前不创建 `extension_holdout`，避免在没有获准增强时产生可被调试或误用的冻结集；
  - 固定重新进入条件：20 次结构化探针至少成功 19 次、具备离线 fallback、复用 Evidence Verifier，随后才冻结 23 题独立保留集。
- 同步更新科研报告与事实约束：
  - `reports/research_report_draft.md` 第 5.8 节从“待决策”更新为有证据的 No-Go；
  - 第 8.4 节明确 v1.0 在增强 No-Go 状态下仍可提交；
  - 附录待办标记前置审计已完成，extension holdout 仅在重新获准后创建；
  - `reports/report_claims_checklist.md` 与 `scripts/validate_report_claims.py` 同步要求 No-Go 表述。

### 正式决定

```text
增强 A：No-Go，正式答案字段结构化成功率 0/6
增强 B：No-Go，无已缓存且验证可用的文本 Embedding 模型
当前版本：保留 v1.0-baseline
extension_holdout：不创建
final：不重跑、不调参
```

### 验证结果

```bash
python scripts/check_enhancement_readiness.py
python scripts/check_enhancement_readiness.py --probe-ollama --model qwen3-vl:8b
python scripts/check_enhancement_readiness.py --require-ready
python scripts/validate_report_claims.py
python -m compileall -q app src scripts tests
pytest -q
python scripts/validate_scoring.py
python scripts/validate_experiments.py
python scripts/validate_evaluation.py
python -m pip check
python scripts/freeze_baseline.py --verify
```

- 自动 Ollama 复验：`schema_success=False`、`content_length=0`、`thinking_contains_json=True`；
- `--require-ready` 按预期以退出码 2 拒绝当前状态；
- 报告事实声明校验通过；
- Pytest：`26 passed`；
- 初步评分状态继续为 `preliminary_pending_user_confirmation`；
- 实验配置指纹仍为 `56dd6a55fd05a01490322283926a722a3fe0260d4b4b6534f21d2900ba04c44a`；
- 依赖无冲突；
- v1.0 归档 23 个 payload 和 Manifest SHA-256 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1` 继续匹配；
- 未运行 final，未生成 extension holdout 或任何 enhanced 实验结果。

### 当前状态

技术增强已按照冲刺方案完成真实前置审计和及时止损，不再占用报告与交付时间。下一阶段转入实验可视化与报告素材：根据已有 pilot 和初步评分结果生成可追溯图表，将 Mermaid 架构图导出为静态图片，并继续保持初步语义指标的星号与用户确认状态。

## 2026-07-22 阶段 6.8：用户确认评分晋级与报告图表素材

### 完成事项

- 用户已确认 pilot 四种方法共 160 行语义评分，覆盖正确性、忠实度、幻觉和过度拒答四个字段。
- 新增 `scripts/confirm_pilot_scoring.py`，执行确认版数据提升：
  - 逐行比对 preliminary 与 confirmed 的题目、方法和四个评分字段；
  - 分数未发生任何变化；
  - 将正式状态更新为 `user_confirmed`；
  - 将需要人工核对的说明改为用户已确认的评分解释；
  - 生成当前正式文件 `reports/human_scoring_pilot_confirmed.csv`；
  - 将旧指标 JSON 归档为 `pilot_human_metrics_preliminary.json`，当前 `pilot_human_metrics.json` 改为确认状态；
  - 同步更新 `metrics_summary.csv/md`、pilot 比较材料和用户确认版误差分析。
- 将四份 `vector_rag_pilot.json`、`graph_only_pilot.json`、`proposed_pilot.json` 和 `no_verifier_pilot.json` 的四类语义 `MetricValue` 补齐为 `user_confirmed`，自动检索、决策和延迟指标保持原值。
- 保留原始审计材料，不删除任何 preliminary 文件：
  - `reports/human_scoring_pilot_preliminary.csv`；
  - `reports/experiments/pilot_human_metrics_preliminary.json`；
  - `reports/experiments/pilot_error_analysis_draft.md`。
- 更新 `scripts/validate_scoring.py`：
  - 检查 160 行 confirmed 数据和四种方法分布；
  - 检查 confirmed 与 preliminary 的评分字段完全一致；
  - 检查当前指标为 `user_confirmed`、历史快照仍保留原状态；
  - 检查 9 个误差案例和指标重算结果。
- 更新报告与声明约束：
  - 正式报告移除语义评分表的 `*`、待确认状态和“初步语义评分”表述；
  - 改为“用户确认后的语义复核”，并保留“评分初稿由 Codex 辅助生成、未进行独立双人标注”的方法透明度；
  - `report_claims_checklist.md` 和 `validate_report_claims.py` 现在要求 `user_confirmed`，并拦截当前报告中的 stale preliminary 状态；
  - 新增 `reports/scoring_confirmation.md` 记录确认范围、正式文件和审计留痕。
- 完成报告静态图表素材：
  - `architecture.png`：替换 Mermaid 的 LangGraph 状态流；
  - `pilot_automatic_metrics.png`：自动指标对比；
  - `pilot_semantic_confirmed.png`：用户确认语义指标；
  - `pilot_latency.png`：本地热路径耗时；
  - `pilot_category_decision_accuracy.png`：按题型决策准确率热图；
  - `figure_manifest.json`：记录输入和图片 SHA-256。
- 新增 `scripts/generate_report_figures.py`，支持生成和 `--check` 哈希校验；静态图片已完成视觉抽查，修复了架构图右侧裁切、热图文字对比度和语义图残留星号。
- 修正根 `README.md` 的评测命令：移除直接运行 final 的示例，改为复用冻结结果并执行 confirmed 评分与图表校验。

### 验证结果

```bash
python scripts/confirm_pilot_scoring.py
python scripts/validate_scoring.py
python scripts/validate_report_claims.py
python scripts/generate_report_figures.py --check
python -m compileall -q app src scripts tests
pytest -q
python scripts/validate_experiments.py
python scripts/validate_evaluation.py
python -m pip check
python scripts/freeze_baseline.py --verify
```

- 确认提升：160 行，四种方法各 40 行，评分字段与原始 preliminary 完全一致；
- 当前评分状态：`user_confirmed`；
- 报告声明校验通过，当前报告不再包含待确认语义评分状态；
- 图表 manifest 和 5 张图全部通过哈希校验；
- Pytest：`26 passed`；
- 实验配置指纹仍为 `56dd6a55fd05a01490322283926a722a3fe0260d4b4b6534f21d2900ba04c44a`；
- v1.0 归档 23 个 payload 和 Manifest SHA-256 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1` 继续匹配；
- final 未重跑，技术增强仍为 No-Go，未创建 extension holdout。

### 当前状态

pilot 语义评分现在可以作为报告正式结果使用，但应准确称为“用户确认后的语义复核”，不延伸为独立双人标注。实验结果和静态图表素材已齐备，下一阶段进入 Markdown 报告定稿、DOCX 排版和答辩材料制作。

## 2026-07-22 阶段 6.9：评分确认清理验收

### 完成事项

- 清理正式交付面中的过渡标记：报告、指标汇总、pilot 比较材料、四份实验 JSON 和图表均以 `user_confirmed` 为当前语义评分状态，不再使用星号、待确认说明或 `preliminary_pending_user_confirmation` 作为正式结果描述。
- 核对正式读取路径：`human_scoring_pilot_confirmed.csv` 与 `pilot_human_metrics.json` 是当前权威评分文件；确认前的三份原始文件不参与正式统计和报告读取，仅作为审计快照保留。
- 保留通用 `pending_human_review` 契约、空白评分模板和历史进度记录，避免把未来评测能力与本次已确认结果混为一谈。
- 未修改冻结 `final` 结果、实验配置指纹、评分数值或图表输入数据。

### 验证结果

- `pytest -q`：`26 passed`；
- `python scripts/validate_scoring.py`：160 行、四种方法各 40 行、9 个误差案例，状态 `user_confirmed`；
- `python scripts/validate_report_claims.py`、`python scripts/generate_report_figures.py --check`、`python scripts/validate_experiments.py`、`python scripts/validate_evaluation.py` 全部通过；
- `python -m pip check` 无依赖冲突；
- `python scripts/freeze_baseline.py --verify` 通过，v1.0 Manifest SHA-256 仍为 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`；
- `git diff --cached --check` 与工作区空白检查通过。

### 当前状态

评分确认清理已验收，可以提交阶段 6.8/6.9 改动。下一步进入 Markdown 报告定稿、DOCX 排版和答辩材料制作；技术增强仍保持 No-Go，不生成 enhanced 结果。

## 2026-07-22 阶段 7.0：纯文本 LLM 重新进入审计与 Generator Go

### 完成事项

- 从已推送基线提交 `02a122c` 创建独立分支 `experiment/llm-agent-v2`；用户提供的 LLM 完善方案 DOCX 保持未跟踪、未修改状态。
- 核对本机资源与 Ollama 启动方式：
  - Ollama `0.32.1`；
  - RTX 4060 8 GB；
  - 系统内存约 16 GB；
  - 原模型目录位于 C 盘，C 盘剩余约 12.5 GB。
- 新建 E 盘模型目录 `E:\ollama-models` 并写入用户级 `OLLAMA_MODELS`：
  - 通过独立隐藏 `ollama.exe serve` 进程验证配置生效；
  - 服务日志明确记录 `OLLAMA_MODELS:E:\ollama-models`；
  - 原 C 盘 `qwen3-vl:8b` 模型没有删除或迁移；
  - 新服务不再读取旧目录。
- 下载并验证纯文本 `qwen3:4b`：
  - 架构 `qwen3`，参数量 4.0B，量化 Q4_K_M；
  - 主权重约 2.5 GB，实际 E 盘 blob 约 2.33 GB；
  - 单次 readiness 探针首次让正式 JSON 进入 `message.content`，thinking 长度为 0。
- 新增 `scripts/probe_llm_structured.py`：
  - 简单状态、QueryPlan、嵌套 AnswerPayload 三类严格 Pydantic Schema；
  - 每类默认执行 20 次，使用 `think=false`、`stream=false`、temperature 0 和固定 seed；
  - 不记录 thinking 内容，只记录长度、Schema、语义结果、哈希和延迟；
  - 分离 Structured、Generator、Planner 和 Full Agent 四个门槛；
  - Generator 门槛不能被 Planner 的 Schema 成功误导，Planner 门槛也不能被答案生成成功掩盖。
- 新增 `tests/test_llm_probe.py`，覆盖 Planner 语义约束、未知引用拒绝和门槛拆分逻辑。
- 保留第一次 Full Agent 门槛失败报告 `reports/llm_probe_qwen3_4b_full_agent_initial.json`，不覆盖失败证据。
- 生成当前正式报告 `reports/llm_probe_qwen3_4b.json`，并新增 `scripts/validate_llm_probe.py` 执行离线重算校验。

### 正式探针结果

| 类型 | Schema 成功 | 语义成功 | 判定 |
| --- | ---: | ---: | --- |
| 简单状态 | 20/20 | 20/20 | 通过 |
| QueryPlan | 20/20 | 1/20 | Planner No-Go |
| 嵌套 AnswerPayload | 20/20 | 20/20 | Generator Go |
| **合计** | **60/60** | **41/60** | **仅批准 Generator** |

- 空正式 content：0；
- 非空 thinking：0；
- 冷启动：20.698 s；
- 热请求均值：0.930 s；
- 热请求 P95：1.294 s；
- QueryPlan 的 19 次失败均能通过 JSON/Pydantic，但固定误判 intent 并漏掉实体，证明结构化成功率不等于 Planner 准确率。

### 验证结果

```bash
python scripts/check_enhancement_readiness.py --probe-ollama --model qwen3:4b --timeout 180
pytest -q tests/test_llm_probe.py
python -m py_compile scripts/probe_llm_structured.py tests/test_llm_probe.py
python scripts/probe_llm_structured.py --model qwen3:4b --runs-per-schema 20 --minimum-success-rate 0.95 --target-gate generator --unload-before-run --output reports/llm_probe_qwen3_4b.json
python scripts/validate_llm_probe.py
```

- 探针明细与汇总已独立重算，结果完全一致；
- 4 个新增单元测试通过；
- 本阶段没有修改 LangGraph、Retriever、Verifier、实验配置或 Streamlit；
- 未运行或修改 final，未创建 extension holdout，未生成 enhanced 实验成绩。

### 当前决定

LLM Answer Generator 的前置门槛已经通过，可以进入下一阶段；LLM Query Planner 仍为 No-Go，继续使用规则 Router。下一阶段必须先冻结独立 23 题 `extension_holdout` 和评分合同，之后才允许修改统一 Schema、LLM Client 与 Generator 主链路。

## 2026-07-22 阶段 7.1：Extension Holdout 与评分合同冻结

### 完成事项

- 在 LLM Client、LLM Answer Generator 和业务 Prompt 实现前创建并冻结 `data/evaluation/extension_questions.jsonl`：
  - 共 23 题；
  - 可回答题 19 题；
  - 无答案题 4 题，分别覆盖完全超域、机器学习但不在六页知识库、实体存在但属性不存在、错误任务前提；
  - 每题增加 `expected_route`、`required_aspects` 和 `forbidden_claims`，供后续盲评和错误检查使用。
- 固定 extension 题型分布：

| 题型 | 数量 |
| --- | ---: |
| single_hop | 4 |
| multi_hop | 4 |
| definition | 3 |
| comparison | 3 |
| principle_pros_cons | 3 |
| metric_selection | 2 |
| no_answer | 4 |

- 新增 `config/extension_evaluation.yaml`，在看到任何 extension 输出前冻结：
  - Rule Baseline；
  - LLM Generator；
  - LLM Generator No Verifier；
  - 不包含 LLM Planner，Route Accuracy 明确为不适用；
  - 自动指标包括决策、拒答、过度拒答、引用、结构化成功、fallback 和冷/热延迟；
  - 人工指标包括 Correctness、Faithfulness、Hallucination、Over-refusal 和 Readability；
  - 固定各指标分母、0/1/2 或 1～5 评分规则、隐藏方法标签和随机答案顺序；
  - 当前仍是用户确认的单一复核流程，不声称独立双人标注。
- 新增冻结 manifest `data/evaluation/extension_holdout_manifest.json`：
  - 题集 SHA-256：`7b2b2e76ecdd690574fd0c8220bee7edf20a326bcd2ff8e401659f4acc15e3a5`；
  - 评分合同 SHA-256：`a9415d4efc8b3e79bd65d6df84488364761695860bf53d04861e3e4148060b65`；
  - 题目 ID + 归一化题面指纹：`1dfbf35117b5a22e28bcee8f27b3cdd1cf86e7542c76122c583ef6780217fc28`；
  - 基线提交：`9e2c34f9d6fa2824d73d62c0b448f7520a8363b2`；
  - 状态：`frozen_locked`；
  - release record 不存在，extension 输出不存在。
- 新增 `scripts/validate_extension_holdout.py`：
  - 校验 23 题、题型分布和 19/4 行为分布；
  - 校验实体、关系及 approved 关系与 gold 实体的一致性；
  - 校验题集、评分合同和题面指纹哈希；
  - 检查 dev/demo/pilot/final 完全重合和近重复；
  - 检查评分方法、指标合同和执行锁；
  - 锁定期间发现 release record 或任何 extension 输出即失败。
- 与四个已有数据集的完全相同题面重合为 0；归一化最高相似度为 0.7097，低于 0.82 阈值，最近题对为 `X-SH-03` / `T-SH-05`。
- 修复旧评测入口保护：
  - `scripts/run_evaluation.py --split final` 现在明确拒绝运行并要求复用冻结结果；
  - `scripts/run_evaluation.py --split extension` 在 release record 创建前明确拒绝运行；
  - 没有为 extension 增加任何可执行实验入口。
- 新增 `reports/extension_holdout_freeze.md`，记录冻结范围、方法、评分披露、防泄漏边界和文件指纹。
- 同步更新研究报告、事实声明清单和自动声明校验：
  - 初始 `qwen3-vl:8b` 仍为 No-Go；
  - `qwen3:4b` 仅为 Generator 前置 Go，Planner No-Go；
  - extension 已冻结但尚未运行；
  - 当前主链路和正式生成器仍未增强，不能宣称 enhanced 有效。

### 验证结果

```bash
python scripts/validate_evaluation.py
python scripts/validate_extension_holdout.py
python scripts/run_evaluation.py --split final
python scripts/run_evaluation.py --split extension
pytest -q tests/test_evaluation_data.py tests/test_evaluation_guards.py
python scripts/validate_report_claims.py
```

- 评测数据校验通过：dev=10、demo=8、pilot=40、final=40、extension=23；
- extension 题集、评分合同、manifest、关系证据和执行锁校验通过；
- final 与 extension 两个运行入口均按预期拒绝；
- 7 个相关数据与运行保护测试通过；
- 没有调用工作流读取 extension 问题，没有生成 extension 或 enhanced 结果；
- final 未运行、未修改，v1.0 结果继续只读。

### 当前状态

条件 1、2、5 已满足：纯文本模型与 Generator 结构化门槛通过，extension holdout 已冻结。下一阶段可以开始统一 Schema 和 LLM Client，但仍禁止运行 extension；只有 Client、Generator、fallback、Verifier 接线、测试和配置全部冻结后，才创建独立 release record 并执行一次正式比较。

### 阶段 7.1 最终验收

- 将研究报告页眉中的当前实验分支修正为 `experiment/llm-agent-v2`；
- 全量测试通过：`35 passed`；
- LLM 探针校验通过：Schema `60/60`、简单语义 `20/20`、嵌套 AnswerPayload `20/20`、QueryPlan `1/20`，结论保持 Generator Go / Planner No-Go；
- extension 结构、关系证据、防泄漏、评分合同、三项哈希和执行锁全部通过校验；
- 新增仅作用于 3 个 extension 冻结工件的 `.gitattributes` LF 约束，避免 Windows `core.autocrlf` 导致逐字节 SHA-256 在重新检出后漂移；
- evaluation、experiments、scoring、report claims 与 5 张报告图均通过一致性校验；
- `run_evaluation.py --split final` 与 `--split extension` 均在工作流构建前按预期拒绝执行；
- `python -m pip check` 返回 `No broken requirements found`，`git diff --check` 未发现空白错误；
- v1.0 归档的 23 个 payload 校验通过，Manifest SHA-256 仍为 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`；
- 用户提供的方案 DOCX 保持未跟踪、未修改，不纳入提交；没有生成 extension 输出或 release record。

## 2026-07-22 阶段 7.2：统一 Schema 与 LLM Client

### 完成事项

- 将 `AnswerPayload.claims` 从无约束的 `list[dict]` 迁移为强类型 `AnswerClaim`：
  - 固定 `claim`、`evidence_ids`、`graph_path_ids` 和 `relation_id` 字段；
  - 未知字段使用 Pydantic `extra="forbid"` 拒绝；
  - `confidence` 限制在 0～1；
  - 新增 `generator_backend`，当前正式规则生成器固定为 `offline_rule`；
  - 同步迁移 `GroundedAnswerGenerator`、`EvidenceVerifier` 和 `NoVerifier`，没有改变原打分公式、路由或重试决策。
- 新建统一 `src/llm/` 模块：
  - `base.py`：泛型 `LLMClient` Protocol 和统一事件回调类型；
  - `config.py`：严格 `LLMSettings` 与 `AgentLLMSettings`；
  - `exceptions.py`：区分服务不可用、超时、正式 content 为空、Schema 失败和策略失败；
  - `schemas.py`：严格 `ChatMessage` 与脱敏 `LLMCallRecord`；
  - `ollama_client.py`：生产 Ollama `/api/chat` 结构化 Client；
  - `factory.py`：统一 Factory，并允许通过 `OLLAMA_BASE_URL`、`OLLAMA_MODEL` 覆盖非敏感本地配置。
- Ollama Client 固定执行以下合同：
  - `think=false`、`stream=false`；
  - `format=response_model.model_json_schema()`；
  - 只解析 `message.content`，content 为空时不读取 thinking，立即抛出 `LLMEmptyResponseError`；
  - 超时或 Schema 失败最多重试一次；Schema 修复提示不回传无效原文；
  - 服务不可达或 HTTP 错误立即抛出 `LLMUnavailableError`；
  - `base_url` 禁止嵌入用户名或密码，空白模型名、keep-alive 和节点名在发送请求前失败；
  - 日志和事件只记录 request ID、节点、provider、model、Schema、成功状态、尝试次数、延迟、token 数和错误类型，不记录 Prompt、content、thinking、URL 凭据或 API Key。
- 在 `config/settings.yaml` 中登记 `ollama/qwen3:4b` 的正式参数，同时保持：
  - `planner_backend: rule`；
  - `generator_backend: offline_rule`；
  - `planner_fallback: rule`；
  - `generator_fallback: offline_rule`。
- `scripts/validate_config.py` 现在会使用强类型 Schema 校验 LLM 与 Agent 配置，并拒绝 `think=true`、超过一次重试或未知配置字段。
- 新增 `tests/test_llm_client.py` 的 11 个合同测试，覆盖：
  - 正常严格 Schema 输出；
  - 空 content 且 thinking 含 JSON 时仍严格失败；
  - Schema 一次修复成功与二次失败；
  - 超时一次恢复与二次失败；
  - 服务关闭和 HTTP 错误立即失败；
  - Factory 环境覆盖与配置约束；
  - URL 凭据与空白节点在网络请求前被拒绝；
  - Prompt/content 不进入日志；
  - `AnswerPayload` 强类型 Claim 与未知字段拒绝。
- 新增 `scripts/smoke_llm_client.py`，只使用合成状态 Schema 复验生产 Client，不读取任何业务题集：
  - 冷启动调用一次成功，`attempts=1`，约 `21140.4 ms`；
  - 热调用一次成功，`attempts=1`，约 `584.7 ms`；
  - 两次均通过 Schema 和固定语义检查，只使用正式 content，不记录 thinking 内容。
- README、研究报告、技术增强决策和事实声明清单已同步：统一 Client 可用不等于 LLM 已进入 Agent；当前正式生成器仍为 `GroundedAnswerGenerator`。

### 验证结果

```bash
python scripts/validate_config.py
python scripts/smoke_llm_client.py --timeout 180
python scripts/smoke_llm_client.py --timeout 30
pytest -q
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/validate_chunks.py
python scripts/validate_llm_probe.py
python scripts/validate_extension_holdout.py
python scripts/validate_evaluation.py
python scripts/validate_experiments.py
python scripts/validate_scoring.py
python scripts/validate_report_claims.py
python scripts/generate_report_figures.py --check
python scripts/freeze_baseline.py --verify
python -m pip check
git diff --check
```

- 全量测试：`46 passed`；
- 配置校验确认 `llm=ollama/qwen3:4b planner=rule generator=offline_rule`；
- 图谱仍为 50 个实体、100 条 approved 关系，100 条关系证据全部有效；
- 文档数据仍为 164 个 Section、180 个 Chunk；
- 正式探针结论保持 Schema `60/60`、Generator Go、Planner No-Go；
- extension 仍为 23 题锁定状态，题集与评分合同哈希保持不变，没有 release record 或输出；
- 旧实验配置指纹、160 行用户确认评分、5 张报告图均保持一致；
- v1.0 的 23 个归档 payload 全部通过，Manifest SHA-256 仍为 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`；
- `pip check` 无损坏依赖，`git diff --check` 无空白错误。

### 当前状态与下一步

模块 2 已完成，但 LLM 尚未进入 `QAWorkflow`。下一阶段实现 `AnswerGenerator` Protocol、证据上下文序列化、`LLMAnswerGenerator` 和 `FallbackAnswerGenerator`，并用 dev/合成测试验证无效引用与服务关闭回退；在 Generator、fallback、Verifier 接线和配置全部冻结前，继续禁止运行 extension。

## 2026-07-22 阶段 7.3：LLM Answer Generator、Verifier 与规则 Fallback 主链路

### 完成事项

- 新建模块化 `src/agent/generators/`：
  - `AnswerGenerator` Protocol；
  - `EvidenceContextSerializer`；
  - 独立 LLM wire Schema `LLMAnswerDraft` / `LLMAnswerClaim`；
  - `LLMAnswerGenerator`；
  - `FallbackAnswerGenerator`；
  - 统一 Generator Factory。
- 证据上下文固定长度和来源边界：
  - 最多 8 条文本证据和 8 条图路径；
  - 每条文本最多 900 字符；
  - 总上下文最多 10,000 字符；
  - 一半文本预算优先保留图路径绑定证据，其余按问题英文改写词对当前 RetrievalResult 候选重排；
  - 不改变或重建冻结 RetrievalResult，只控制送入生成器的上下文。
- LLM wire Schema 不允许模型填写运行时 backend/fallback 元数据：
  - `claims` 必填且至少 1 条；
  - 每条 Claim 必须绑定至少一个 `evidence_id`；
  - 每条 Claim 必须提供至少一段 `supporting_quotes`；
  - quote 必须标注 evidence ID，长度限制 12～500 字符；
  - 模型输出验证后才转换为内部 `AnswerPayload`，backend、fallback、attempts 和 latency 由程序写入。
- Prompt v1 强制：只使用当前 TEXT_EVIDENCE / GRAPH_PATHS，中文回答，不读取模型记忆补充事实，不伪造 E/P/R ID，quote 逐字来自原文，证据不足写入 `unsupported_claims`。
- 增强确定性 Verifier：
  - 检查模型声明的 `unsupported_claims`；
  - 检查所有 evidence/path/relation ID 是否属于当前 RetrievalResult；
  - 检查 supporting quote 归一化后是否为对应 Chunk 原文子串；
  - 增加保守的中英关键术语覆盖检查，拦截“引用存在但机制细节不受支持”的假阳性；
  - Claim 只有在引用、路径、quote 和术语检查全部通过后才计入 claim coverage；
  - pass 额外要求不存在 unsupported 项。
- 用户可见答案始终由结构化 Claim 重建并附带 E/P 引用，不直接展示模型自由生成的 `answer` 字段，避免正文夹带未进入 Verifier 的额外事实。
- Fallback 仅捕获预期 LLM 运行故障：服务不可达、超时、空 content 或两次 Schema 失败；`ValueError` 等程序错误不会被吞掉。
- 默认配置已切换为：
  - `planner_backend: rule`；
  - `generator_backend: llm`；
  - `generator_fallback: offline_rule`；
  - Ollama `qwen3:4b`、Prompt v1、`num_predict=1536`；
  - 可通过 `AGENT_GENERATOR_BACKEND=offline_rule` 强制离线模式。
- `QAWorkflow`、LangGraph answer 节点和 `FinalResponse` 已接入生成器 Factory；历史实验 Factory 与 v1 回归测试显式固定 `offline_rule`，不会因当前默认配置改变旧实验语义。
- 新增逐调用 `generation_trace`：每次生成节点记录 requested/actual backend、fallback、原因、attempts、latency 和 structured success；评测聚合整题所有调用，不再只读取 Verifier 重试后的最后一个 payload。
- `run_agent.py` 增加安全诊断输出：backend、fallback、生成尝试、generation trace、Claim 的 E/P/R 和 quote、Generator/Verifier unsupported；不输出 Prompt、content 原始 JSON 或 thinking。
- `run_evaluation.py` 增加：
  - structured output success、fallback rate、generation call count/attempts/latency；
  - Generator 与 Verifier unsupported；
  - 模型/Provider/Prompt 版本；
  - dev 数据集和 settings SHA-256；
  - final 与 extension 运行锁保持不变。
- 修复 dev 暴露的两个检索词缺口：
  - `装袋法 -> bagging`，`AdaBoost -> adaboost boosting`；
  - `缩放特征 -> feature scaling scale`；
  - DEV06 因此能检索到明确写有 SVM 不具尺度不变性的官方 Chunk，并由真实 LLM 一次 pass。
- Ollama Client 的 Schema 修复提示现在只附带最多 5 个 Pydantic 字段路径/错误类型，不包含无效 content；调用记录增加脱敏 `validation_issues`。
- DEV02 持续 `root:json_invalid` 被定位为 768 token 截断；提高到 1536 后一次生成成功，`done_reason=stop`，completion tokens 为 957；重试次数没有增加。

### 真实主链路验收

- DEV01 随机森林模型族：真实 LLM 一次 pass，绑定 `E1/P1/R009`；
- DEV05 Bagging / AdaBoost：模型尝试补充未在 Chunk 中出现的重加权机制，quote/术语检查将其拦截并在一次补检索后 refuse；
- DEV08 随机森林学习率：模型常识没有绕过属性对齐，最终 refuse；
- DEV06 SVC 特征缩放：中英改写修复后，一次 pass，quote 明确包含 `not scale invariant`；
- 模拟 Ollama 不可达：DEV01 自动切换 `offline_rule`，`fallback_reason=LLMUnavailableError`，最终仍 pass；
- 没有运行 final 或 extension。

### 三轮 Dev 审计

| 运行 | Decision Accuracy | Final-payload Structured Success | Fallback Rate | Mean Total Latency |
| --- | ---: | ---: | ---: | ---: |
| initial | 0.7000 | 0.9000 | 0.1000 | 12295.4 ms |
| postfix | 0.7000 | 0.9000 | 0.1000 | 11485.8 ms |
| candidate | 0.6000 | 1.0000 | 0.0000 | 11437.7 ms |

- candidate 的 10 个最终生成 payload 均通过结构化合同且没有运行时 fallback；
- 两道无答案题均正确拒答；
- 4 个错误全部是 answerable 问题被过度拒答，没有观察到错误放行；
- 规则 dev 基线为 1.0000，因此不能声称 LLM Generator 提高了决策准确率；
- candidate 数据集 SHA-256：`7db6c94473797ee63c03b16c9daaad2936118780277bd97bbc3906cff32533e3`；
- candidate settings SHA-256：`245af4032950698f5e8b9d6ca556a6380b5ada170cee8d8f429a56bb48bafece`；
- 三份 dev JSON 生成时尚未聚合首次生成节点，端到端 latency 有效，但分阶段 generation 指标只代表最终 payload；代码随后已加入完整 trace，历史 dev 文件不回写。

完整审计见 `reports/llm_generator_dev_audit.md`。

### 验证结果

```bash
pytest -q
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/validate_chunks.py
python scripts/validate_llm_probe.py
python scripts/validate_extension_holdout.py
python scripts/validate_evaluation.py
python scripts/validate_experiments.py
python scripts/validate_scoring.py
python scripts/validate_report_claims.py
python scripts/generate_report_figures.py --check
python scripts/freeze_baseline.py --verify
python -m pip check
git diff --check
```

- 全量测试：`59 passed`；
- 配置校验确认 `llm=ollama/qwen3:4b planner=rule generator=llm`；
- 图谱仍为 50 个实体、100 条 approved 关系，文档仍为 164 个 Section、180 个 Chunk；
- 正式探针仍为 Schema 60/60、Generator Go、Planner No-Go；
- extension 23 题、题集/评分合同哈希和执行锁全部通过，没有 release record 或输出；
- 旧实验配置、160 行用户确认评分、5 张图和报告事实声明均通过；
- v1.0 的 23 个归档 payload 全部通过，Manifest SHA-256 仍为 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`；
- `pip check` 无损坏依赖，`git diff --check` 无空白错误。

### 当前决定与下一步

真实 LLM 已进入默认答案生成节点，结构化生成、引用/quote 边界、Verifier、一次补检索和运行时离线 fallback 已形成闭环；Planner 继续 No-Go。由于候选 dev 决策结果低于规则基线，当前只确认“实现完成且结构稳定”，不确认“增强有效”。extension 继续锁定；下一阶段先冻结实现、Prompt、配置和 trace 评分合同哈希，再创建一次性 release record，不能继续使用 dev 调参。

## 2026-07-23 阶段 7.4A：Extension 实现冻结与一次性执行护栏

### 完成事项

- 新增冻结的 `config/extension_trace_contract.yaml`，在查看任何 extension 输出前固定：
  - 方法顺序为 Rule Baseline、LLM Generator、LLM Generator No Verifier；
  - 问题顺序保持数据集原顺序；
  - generation call count、attempts、latency、structured success 和 fallback 均聚合初次生成与 Verifier 重试的完整 trace；
  - Decision Accuracy 分母为全部 23 题，Refusal Accuracy 分母为 4 道无答案题，Over-refusal Rate 分母为 19 道可回答题；
  - Citation Validity 使用不改变方法决策的标准 Verifier shadow 复核；
  - Rule Baseline 的 structured/fallback 指标为 not applicable；
  - 首个 LLM 问题在显式卸载模型后计冷启动，其余 LLM 问题计热端到端延迟；
  - 盲评使用逐题随机答案顺序、A/B/C 方法标签和独立 method key。
- 新增 `src/evaluation/extension_release.py`：
  - 冻结全部 `src/**/*.py`、专用 runner、settings、题集、评分/trace 合同、图数据、Chunk 和 TF-IDF 索引；
  - 单独计算 runtime bundle、Prompt v1、LLM wire Schema、settings 和 trace contract SHA-256；
  - 记录 Python 与关键依赖版本、Ollama 版本和模型完整 digest；
  - 文本哈希先将 CRLF/CR 归一化为 LF，二进制文件按原始字节计算，避免 Windows 检出导致指纹漂移；
  - release 文件使用独占创建，不覆盖既有 manifest、record 或结果；
  - 当前提交必须是冻结实现提交的后代，任何运行时代码、输入、依赖或 Prompt 变化都会使 release 校验失败。
- 新增专用 `scripts/run_extension_evaluation.py`：
  - 普通 `run_evaluation.py --split extension` 继续无条件拒绝；
  - 专用 runner 在读取题目并调用 QA 工作流前，必须验证 implementation manifest、release record、runtime bundle、模型 digest 和固定 NetworkX 后端；
  - 正式运行必须同时提供 `--execute-once`、精确 release ID 和 `--confirm-one-time-run`；
  - 首次调用前以独占方式创建 execution state，禁止覆盖已有状态或输出；
  - 每道题调用前先记录 method/question in-flight 状态，异常或中断转为 `failed_requires_manual_audit`，不自动重跑可能已经暴露的题目；
  - 完成后生成三份方法报告、描述性汇总、盲评 CSV、独立 method key 和带文件哈希的 execution receipt；
  - final v1.0 结果继续只读，不属于该 runner 的输出范围。
- 新增 `scripts/create_extension_release.py` 与 `scripts/validate_extension_release.py`，分别负责在干净实现提交上创建一次性授权，以及离线/运行时复验 release 指纹。
- 扩展 `validate_extension_holdout.py`：
  - release 前继续要求无 implementation manifest、无 release record、无 extension 输出；
  - release 后验证实现指纹和授权；
  - 执行后验证 state、69 次方法/题目调用计数、receipt 和全部输出哈希；
  - 旧 `evaluation_extension.json` 或实验目录旁路输出始终视为错误。
- 新增 `tests/test_extension_release.py`，覆盖 trace 指标分母、Rule Baseline N/A、盲评随机化、孤立输出拒绝、completed receipt 哈希防篡改、release 不覆盖和 CRLF 稳定哈希。
- 修复本地 Ollama 启动来源：
  - 发现桌面 `ollama app` 仍按旧 C 盘目录自动拉起服务，导致当前 `ollama list` 只显示 `qwen3-vl:8b`；
  - 停止桌面进程后，使用用户级 `OLLAMA_MODELS=E:\ollama-models` 启动独立隐藏 `ollama.exe serve`；
  - 当前可见模型恢复为 `qwen3:4b`，完整 digest 为 `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`，大小 2,497,293,931 bytes。

### 验证结果

```bash
pytest -q
python scripts/validate_config.py
python scripts/validate_extension_holdout.py
python scripts/validate_evaluation.py
python scripts/validate_experiments.py
python scripts/validate_scoring.py
python scripts/validate_report_claims.py
python scripts/freeze_baseline.py --verify
python -m pip check
git diff --check
```

- 全量测试：`67 passed`；
- extension 仍为 23 题、19/4 行为分布，题集和评分合同 SHA-256 保持不变；
- 当前有效执行状态仍为 `locked`，implementation manifest 与 release record 尚未创建；
- 普通 runner 按预期拒绝 extension，专用 runner 因 release 不存在也按预期拒绝 preflight；
- 旧实验配置、160 行用户确认评分和报告事实声明保持一致；
- v1.0 的 23 个归档 payload 继续通过，Manifest SHA-256 为 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`；
- 无依赖冲突，无空白错误；没有调用 extension QA 工作流，没有生成任何 extension 答案或指标。

### 当前状态与下一步

一次性执行代码、trace 口径和 release 校验已经实现并通过测试，但执行锁尚未解除。下一步先提交本阶段代码，使运行实现获得稳定 Git commit；随后只在该干净提交上生成 implementation manifest 和 `authorized_not_executed` release record，再执行 preflight。本阶段不会运行 extension。

## 2026-07-23 阶段 7.4B：实现指纹冻结与 Extension 一次性授权

### 完成事项

- 将 Stage 7.4A 的专用 runner、trace 合同和 release 校验提交为冻结实现：
  - commit：`bdedf7dcb4e82bc918dfd7c92161501151b09742`；
  - 提交信息：`feat: freeze controlled extension runner`。
- 仅在该干净提交上运行 `python scripts/create_extension_release.py --create`，生成：
  - `data/evaluation/extension_implementation_manifest.json`；
  - `data/evaluation/extension_holdout_release.json`。
- implementation manifest 冻结结果：
  - runtime bundle SHA-256：`b4676d37dc9f2babde6ade4f1a3d212ed775d590adf202e3cef710cadbbe03f0`；
  - settings SHA-256：`245af4032950698f5e8b9d6ca556a6380b5ada170cee8d8f429a56bb48bafece`；
  - Prompt v1 SHA-256：`f4af2d9668b8ba53cb8f884ff840e4ce282d55d15e4468039b039ff3a0e5c60e`；
  - LLM wire Schema SHA-256：`291e0ed4ccc600aed1043e745d64b9479db518a1f458beae00046a0c5ea7c932`；
  - trace contract SHA-256：`f68cde4cae30845e1b04a98f27c6d95dd08a8af4d2edf4f32b615b25da08185d`；
  - implementation manifest SHA-256：`2f6e0b06c66d66d6efcc020d8ea7b291ba4ec92e6a1e4b9c575d06f3b2676382`；
  - Python `3.12.7`，LangGraph `1.0.10`，Pydantic `2.8.2`，scikit-learn `1.5.1`；
  - Ollama `0.32.1` / `qwen3:4b`，模型完整 digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`。
- 一次性 release：
  - release ID：`extension-qwen3-4b-v1-bdedf7dc`；
  - 状态：`authorized_not_executed`；
  - 最多执行次数：1；
  - 固定 3 种方法、23 题原顺序、盲评随机种子、state/receipt 与 6 个结果路径；
  - final 结果继续采用 `v1.0_final_read_only_unchanged` 策略。
- 完成两类 preflight：
  - `validate_extension_release.py --check-runtime-model --require-unexecuted` 验证实现、依赖、模型和无输出状态；
  - `run_extension_evaluation.py --preflight` 验证专用 runner 的完整执行前条件；
  - preflight 明确输出“extension questions were not sent to the QA workflow”。
- 审计两个新 JSON：只包含版本、哈希、固定方法、模型元数据、随机种子和输出路径；不包含 Prompt 原文、模型 content、thinking、凭据或 extension 答案。
- 同步 README、评测数据说明、extension 冻结记录、技术决策、研究报告与事实声明清单：当前统一表述为“release 已授权但尚未执行”，不得提前声称 enhanced 有效。

### 验证结果

```bash
python scripts/validate_extension_release.py --check-runtime-model --require-unexecuted
python scripts/run_extension_evaluation.py --preflight
python scripts/validate_extension_holdout.py
python scripts/validate_report_claims.py
pytest -q
```

- release/runtime/model 复验全部通过；
- extension 有效状态：`authorized_not_executed`；
- 报告事实声明：23 项来源检查、16 项必需声明、14 项禁止声明全部通过；
- 全量测试：`67 passed`；
- 配置、图谱、100 条关系证据、180 个 Chunk、LLM 探针、评测数据、旧实验、评分、5 张图、依赖和编译检查全部通过；
- v1.0 的 23 个归档 payload 继续通过，Manifest SHA-256 仍为 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`；
- `reports/extension/` 不存在，没有 execution state、receipt、方法报告、盲评表或 combined metrics；
- 未调用 extension QA 工作流，未生成 extension 答案，未观察任何 extension 实验结果；
- final 未运行、未修改。

### 当前状态与下一步

实现、Prompt、Schema、依赖、输入、模型和 trace 评分合同现已不可变地绑定到 release `extension-qwen3-4b-v1-bdedf7dc`。下一阶段只能使用 release record 中的精确命令执行一次正式 extension 比较；执行完成后先校验 receipt/输出哈希，再生成用户确认的盲评结果。在正式执行前不再修改任何 manifest 中列出的运行时文件。

## 2026-07-23 阶段 7.5：Partial-pass 建议评测与 v2 合并计划

### 完成事项

- 根据用户提出的 5 项不足，对候选 dev 结果、当前 Schema、Evidence Context Serializer、LLM Prompt、Evidence Verifier、LangGraph 决策路径、extension 协议和延迟 trace 做了对应核查。
- 确认当前候选 dev 的主要瓶颈是过度拒答：
  - Decision Accuracy：`0.6000`；
  - Structured Output Success：`1.0000`；
  - Fallback Rate：`0.0000`；
  - 平均端到端延迟：`11437.7 ms`；
  - 平均生成延迟：`5691.18 ms`；
  - 7/10 题触发一次重试；
  - 2/2 无答案题正确拒答；
  - 4/8 可回答题被过度拒答，分别为 `DEV02`、`DEV03`、`DEV05`、`DEV10`。
- 确认代码已逐 Claim 循环检查，但当前仍是整题聚合决策：
  - `ClaimResult` 已定义但未进入 `VerifyResult`；
  - `VerifyDecision` 只有 `pass/retry/refuse`；
  - 任一 unsupported 项会阻止 `pass`，通常触发一次重试后整题拒答；
  - 当前 Prompt 没有最多 4 条 Claim 和明确的原子事实限制；
  - Context Serializer 尚未按题型平衡证据。
- 新增独立计划文档 `reports/llm_agent_partial_pass_plan.md`，正式接受并合并：
  - intent-aware Evidence Packer；
  - Prompt v2 原子 Claim 与最多 4 条限制；
  - Claim-level Verifier 和 ClaimResult trace；
  - `PASS / PARTIAL_PASS / RETRY / REFUSE` 四状态；
  - Rule、LLM Strict、LLM No Verifier、LLM Partial-pass 四方法对照；
  - retrieval、packing、generation、verification、retry 和 end-to-end 分阶段延迟；
  - Streamlit 真实模型、fallback、Verifier 和延迟状态展示。
- 对用户建议做了两项实验口径修正：
  - pilot 已参与历史修复，不再用于自由调参；只允许在参数冻结后做一次预声明门槛的回归，且不得按逐题结果继续调参；
  - `partial_pass` 只表示保留了部分受支持 Claim，不自动计为答案正确，完整性仍由 Answer Correctness 人工评分。
- Dense Retrieval 设为条件增强：只有当剩余可回答错误中至少 30% 明确属于“正确 Chunk 在语料中但未进入 top-k”的召回失败时才单独立项。
- LLM Planner、多 Agent、扩充知识源/实体关系、自动图谱抽取、复杂动态图、完整 Microsoft GraphRAG 和框架迁移继续为 No-Go。
- 制定阶段 8.0～8.8 的实施与验收顺序：release 治理 -> Evidence Packer -> Prompt v2 -> Claim-level Partial-pass -> trace/UI -> dev -> pilot 回归与 v2 冻结 -> extension 一次性实验 -> 盲评和报告。

### Release 治理决定

- 当前 release `extension-qwen3-4b-v1-bdedf7dc` 仍是文件层面的 `authorized_not_executed`，但根据本轮计划立即暂停执行。
- 截至本轮仍未运行 extension，`reports/extension/` 不存在，也没有观察任何 extension 输出，因此可以在无结果泄漏的前提下升级实验协议。
- 在任何 runtime、Prompt、Packer 或 Verifier 改动前，阶段 8.0 必须先：
  - 创建独立且不可覆盖的 v1 revocation record；
  - 保留原 release、implementation manifest 和 v1 trace contract，不删除、不覆盖；
  - 让 runner/validator 对已撤销 release ID 无条件拒绝执行；
  - 新建版本化 `extension_evaluation_v2.yaml` 和 `extension_trace_contract_v2.yaml`；
  - 完成 v2 后重新冻结 runtime、Prompt、Schema、配置、依赖和模型 digest，并创建新的单次 release。
- 该决定取代阶段 7.4B 中“下一步直接执行 v1 extension”的后续安排，但不改写或删除 7.4B 的历史记录。

### 本轮边界与验证

- 本轮只新增计划文档并更新 `PROGRESS.md`；
- 未修改任何 `src/**/*.py`、冻结配置、题集、图数据、Chunk、索引、release 或 implementation manifest；
- 未调用 final 或 extension QA 工作流；
- 未生成 extension execution state、receipt、答案、方法报告或盲评表；
- 用户提供的 DOCX 保持未跟踪、未修改，不纳入提交。

```bash
python scripts/validate_extension_release.py --check-runtime-model --require-unexecuted
python scripts/run_extension_evaluation.py --preflight
git diff --check
```

- release/runtime/model 复验通过，runtime bundle、Prompt 和 trace contract 哈希保持不变；
- preflight 返回 `effective_execution_status=authorized_not_executed`；
- preflight 明确确认 extension questions were not sent to the QA workflow；
- `reports/extension/` 仍不存在；
- `git diff --check` 通过，仅有 Windows 工作区的 LF/CRLF 提示，没有空白错误。

### 当前状态与下一步

评测结论为 **Go**，但不是直接执行 extension。下一步只实施阶段 8.0：建立 v1 撤销记录、执行护栏和 v2 实验合同；该阶段验收完成后再进入 Evidence Packer，继续保持 final 只读和 extension 未执行状态。

## 2026-07-23 阶段 7.6：项目全量知识手册与不足完善路线图

### 完成事项

- 按用户要求新增 `PROJECT_HANDBOOK.md`，作为项目交接、复习和答辩使用的全量知识手册，共 1107 个物理行（797 行非空内容），覆盖：
  - 项目定位、准确课题表述、目标、研究问题和知识边界；
  - 六个官方来源、164 个 Section、180 个 Chunk 的处理流程；
  - 50 个实体、100 条 approved 关系、7 类节点和 9 类关系；
  - GraphRepository、NetworkX 与可选 Neo4j 的接口和实际运行状态；
  - Router、实体链接、查询改写、TF-IDF、图检索和混合融合；
  - Evidence Context、规则 Generator、qwen3:4b Generator、fallback 和 Ollama Client；
  - Evidence Verifier 公式、阈值、决策条件和当前过度拒答原因；
  - LangGraph 节点、统一 Schema、配置、环境变量、Streamlit 和脚本索引；
  - dev/demo/pilot/final/extension 的所有权、防泄漏约束和指标口径；
  - v1.0 final、pilot 消融、LLM 探针、LLM dev 和 extension release 的准确状态；
  - 可复验命令、目录职责、测试、安全边界、可声明贡献和 20 个答辩常见问题。
- 手册明确区分三层成熟度：
  - v1.0 规则基线已冻结并完成正式 final；
  - 当前 LLM Generator 主链路可运行，但只有 dev 审计，不能声称增强有效；
  - Evidence Packer、Prompt v2、Claim-level Verifier 和 Partial-pass 仍是下一阶段计划。
- 手册澄清三个容易误述的事实：
  - Chroma 当前存储的是 TF-IDF 产生的向量，在线 Retriever 也直接读取 TF-IDF index，不能称为神经 Dense Retrieval；
  - Neo4j Repository 和导入脚本存在，但当前 Python 环境没有安装 `neo4j` 驱动，正式实验使用 NetworkX；
  - v1 extension release 文件仍写 `authorized_not_executed`，但阶段 7.5 已暂停执行，必须先撤销并建立 v2 协议。
- 新增 `PROJECT_GAPS_AND_ROADMAP.md`，共 778 个物理行（567 行非空内容），系统记录 19 项当前不足，并为每项给出证据、影响、优先级、处理状态和验收条件。
- 路线图将后续工作分为：
  - P0：v1 release 治理、Evidence Packer、Prompt v2、Claim-level Verifier、`PARTIAL_PASS`、重试优化和四方法实验；
  - P1：阶段延迟、Streamlit 状态展示、正式报告与交付；
  - P2/Conditional：Dense Retrieval、RRF、多跳增强、依赖锁定、实体审核状态和 Neo4j；
  - No-Go：扩充知识库、自动图谱抽取、LLM Planner、多 Agent、完整 Microsoft GraphRAG、复杂动态图和框架迁移。
- 路线图固定阶段 8.0～8.8 的执行顺序、dev 工程门槛、pilot 使用边界、v2 冻结项、extension 一次性协议、风险和最终完成定义。
- 审计并记录额外的当前不足：
  - 50 个实体的 `review_status` 仍为 pending，而 100 条 runtime 关系均为 approved；
  - 混合融合是顺序去重，不是 RRF 或学习排序；
  - Neo4j `find_paths` 的 Cypher 仍硬编码 `[*1..2]`，没有真正使用接口的 `max_hops`；
  - requirements 列出 `neo4j`，但当前环境未安装该可选驱动；
  - Streamlit 尚未展示模型、fallback、generation latency 或 partial 状态。
- 更新 `README.md`：
  - 增加两份新文档和 `PROGRESS.md` 的入口；
  - 将旧的“v1 extension 可直接执行”修正为“v1 release 已暂停，当前只允许 validation/preflight”；
  - 明确下一步是 revocation + v2 release，不存在任何 extension QA 结果。

### 验证结果

```bash
pytest -q
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/validate_chunks.py
python scripts/validate_evaluation.py
python scripts/validate_experiments.py
python scripts/validate_scoring.py
python scripts/validate_llm_probe.py
python scripts/validate_extension_holdout.py
python scripts/validate_extension_release.py --check-runtime-model --require-unexecuted
python scripts/run_extension_evaluation.py --preflight
python scripts/validate_report_claims.py
python scripts/generate_report_figures.py --check
python scripts/freeze_baseline.py --verify
python -m pip check
git diff --check
```

- 全量测试通过：`67 passed`；
- 配置确认 `ollama/qwen3:4b + rule planner + llm generator`；
- 图数据确认 50 个实体、100 条关系，100 条 approved 关系证据全部有效；
- 文档数据确认 164 个 Section、180 个 Chunk；
- 五套评测数据确认 dev=10、demo=8、pilot=40、final=40、extension=23；
- 用户确认评分确认 160 行、4 种方法、9 个错误案例一致；
- LLM 探针确认 Schema 60/60、Generator Go、Planner No-Go；
- extension dataset、评分合同、release/runtime/model 哈希全部通过；
- preflight 返回 `authorized_not_executed`，并确认 extension questions were not sent to the QA workflow；
- 报告 23 项来源、16 项必需声明、14 项禁止声明全部通过；
- 5 张报告图仍与 manifest 一致；
- v1.0 归档 23 个 payload 全部通过，Manifest SHA-256 仍为 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`；
- `pip check` 无损坏依赖；
- `git diff --check` 无空白错误，只有 Windows LF/CRLF 提示。

### 本轮边界

- 本轮只新增两份 Markdown 文档，并更新 README 和 `PROGRESS.md`；
- 未修改 `src/`、`scripts/`、`tests/`、冻结配置、题集、图谱、Chunk、索引、release 或 manifest；
- 未运行 final 或 extension QA；
- `reports/extension/` 仍不存在；
- 用户提供的 DOCX 保持未跟踪、未修改，不纳入提交。

### 当前状态与下一步

项目现已有一份完整事实手册和一份可执行不足路线图。下一步仍严格从阶段 8.0 开始：创建 v1 revocation record、使旧 release ID 无法执行、建立 v2 evaluation/trace contract；验收后才进入 Evidence Packer。

## 2026-07-23 阶段 7.7：随机森林稳定性问题的过度拒答复现

### 完成事项

- 在用户通过 Streamlit 提问“随机森林为什么更稳定？”并遇到拒答后，使用默认 LLM 主链路复现同一问题。
- LLM 主链路复现结果：
  - intent=`explanation`，mode=`hybrid`；
  - decision=`refuse`；
  - evidence score=`0.7200`；
  - claim coverage=`0.4000`；
  - citation validity=`0.6000`；
  - path validity=`1.0000`；
  - retrieval sufficiency=`1.0000`；
  - retry count=`1`；
  - generation calls=`2`；
  - fallback=`false`。
- 确认 Retriever 已返回 Random Forests 官方章节 E1/E2 和三条有效图路径，因此本题不是知识库缺失或召回失败。
- 定位三类生成/验证问题：
  - “平均预测降低方差”的 quote 只截取 `By taking an average of those predictions,`，没有直接覆盖 Random Forest 和 variance；
  - 噪声鲁棒性 Claim 将图路径 `P2` 错填入 `evidence_ids`；
  - 缓解过拟合 Claim 将图路径 `P3` 错填入 `evidence_ids`。
- 当前 Verifier 因只有 2/5 Claim 通过、存在 unsupported 项且没有 `partial_pass`，在一次重试后把整题拒答。
- 使用 `AGENT_GENERATOR_BACKEND=offline_rule` 对同一问题做对照：
  - decision=`pass`；
  - evidence score、claim coverage、citation validity、path validity、retrieval sufficiency 均为 `1.0000`；
  - retry count=`0`。
- 对照结果证明本题的主要故障位于 LLM Claim 引用与严格整题决策，而不是图谱、Chunk 或 Retriever。
- 新增独立诊断文档 `reports/random_forest_over_refusal_diagnosis.md`，记录完整复现数据、错误 Claim、根因、规则基线对照、正式修复路径和临时规则模式命令。

### 当前处理决定

- 不直接修改冻结 runtime，也不运行 extension；
- 正式修复仍按阶段 8.0～8.3 顺序进行：release 治理 -> Evidence Packer -> Prompt v2 -> Claim-level `PARTIAL_PASS`；
- `DEV02` 将作为 v2 dev 回归的必测案例；
- 当前需要稳定演示时可显式使用 `offline_rule`，但必须标注为规则基线，不能冒充 LLM 输出。

## 2026-07-23 阶段 8.0：v1 Extension 执行前撤销与 v2 评测合同冻结

### 完成事项

- 在修改任何业务 runtime 前重新核验 extension 暴露状态：
  - `reports/extension/` 不存在；
  - execution state、execution receipt、三份方法报告、combined metrics、blind review 和 method key 全部不存在；
  - v1 release 文件 SHA-256 为 `af4f8ac10c247483af20e93f5fdde5220b608fb8c9dfb8c031d777d8b1932d0c`；
  - v1 implementation manifest SHA-256 为 `2f6e0b06c66d66d6efcc020d8ea7b291ba4ec92e6a1e4b9c575d06f3b2676382`；
  - 撤销依据提交为 `c21ce9f4e2389765e898b6b670332fcae908262b`。
- 新建不可覆盖的撤销记录 `data/evaluation/extension_release_revocations/extension-qwen3-4b-v1-bdedf7dc.json`：
  - artifact=`extension_release_revocation`；
  - status=`revoked_before_execution`；
  - reason_code=`protocol_upgrade_before_holdout_exposure`；
  - 固定历史 release/manifest 路径、哈希、实现提交和四项“未观察到执行产物”事实；
  - replacement protocol 固定为 v2，replacement release ID 保持 null；
  - 撤销记录 SHA-256 为 `29b198d5fa9309ce4d81919271df424cb87db29c40370bd0fc6e42bc091aa45b`。
- 严格按审计顺序将撤销记录单独提交并推送：
  - commit=`a518404`；
  - message=`chore: revoke unexecuted extension v1 release`；
  - 该提交只包含一份 revocation JSON，未包含 runtime、合同或文档修改。
- 扩展 `src/evaluation/extension_release.py`：
  - 保留 v1 `METHOD_ORDER`、旧配置、旧 release 和旧输出路径语义；
  - 新增 canonical revocation 路径、读取、历史哈希审计和有效状态判定；
  - revocation 文件即使损坏也会产生 `revocation_invalid` 并继续阻止执行；
  - 历史撤销审计只校验原 release、manifest、撤销事实和无执行产物，不要求当前 runtime 等于已撤销的 v1 bundle；
  - 新增独立 `V2_METHOD_ORDER` 和 v2 合同一致性校验。
- 修改专用 runner：
  - 在 Ollama/model 校验、extension 题集读取和 QA workflow 构建前检查 revocation；
  - 旧 release ID 无条件返回 `effective_execution_status=revoked_before_execution` 并失败；
  - 伪 v2 release ID 因尚无 `extension_holdout_release_v2.json` 明确失败；
  - 未修改 Generator、Verifier、Workflow 或 extension runner 的历史三方法执行逻辑。
- 修改 release/holdout validator：
  - `validate_extension_release.py` 改为验证历史文件和 revocation 审计，并明确输出“not executable”；
  - `validate_extension_holdout.py` 报告 v1 有效状态 `revoked_before_execution` 和 v2 状态 `locked_no_release`；
  - 避免因后续源码变更而错误要求已撤销 v1 runtime 继续等于历史 bundle。
- 新建并冻结 v2 合同：
  - `config/extension_evaluation_v2.yaml`，SHA-256=`864c960f6f357ce528384408441ca189e571206b5d6a904d44f7992b4b034ac1`；
  - `config/extension_trace_contract_v2.yaml`，SHA-256=`3b447885c08dbad3b6366670c5e7b09fc4f639570c912f994b7020f5b9d94ef5`；
  - 四方法固定为 `rule_baseline`、`llm_strict_v2`、`llm_no_verifier_v2`、`llm_partial_pass_v2`；
  - 固定 `PASS / PARTIAL_PASS / REFUSE` 最终状态、Claim 保留/删除、unsupported leakage、四标签盲评和分阶段延迟口径；
  - v2 仍要求独立 release、精确 ID、最多一次执行和不可覆盖输出；当前没有 v2 release。
- 扩展 `tests/test_extension_release.py`：
  - 锁定 v1/v2 方法矩阵互不覆盖；
  - 锁定历史 release/manifest 哈希；
  - 校验已提交 revocation record；
  - 校验嵌套字段被篡改为非对象时返回审计错误而不是异常退出；
  - 通过子进程证明 v1 正式命令和未授权 v2 命令均失败且不创建 `reports/extension/`。
- 同步 README、全量知识手册、不足路线图、partial-pass 计划、extension 冻结记录、技术决策记录、科研报告草稿、报告声明清单和评测数据说明。
- 更新报告事实校验，使其要求同时披露“v1 文件原始状态”和“当前有效撤销状态”，不能再把历史 `authorized_not_executed` 写成当前授权。

### 阶段验证

```bash
pytest -q
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/validate_chunks.py
python scripts/validate_evaluation.py
python scripts/validate_experiments.py
python scripts/validate_scoring.py
python scripts/validate_llm_probe.py
python scripts/validate_extension_holdout.py
python scripts/validate_extension_release.py --check-runtime-model --require-unexecuted
python scripts/run_extension_evaluation.py --execute-once --release-id extension-qwen3-4b-v1-bdedf7dc --confirm-one-time-run
python scripts/run_extension_evaluation.py --execute-once --release-id extension-qwen3-4b-v2-pending --confirm-one-time-run
python scripts/validate_report_claims.py
python scripts/generate_report_figures.py --check
python scripts/freeze_baseline.py --verify
python -m pip check
git diff --check
```

- 全量测试：`72 passed`，其中 release/合同定向测试为 `13 passed`；
- 配置确认 `ollama/qwen3:4b + rule planner + llm generator`；
- 图数据确认 50 个实体、100 条 approved 关系和 100 份有效关系证据；
- 文档数据确认 164 个 Section、180 个 Chunk；
- 五套评测数据确认 dev=10、demo=8、pilot=40、final=40、extension=23；
- 用户确认评分确认 160 行、4 种方法、9 个错误案例一致；
- LLM 探针确认 Schema 60/60、Generator Go、Planner No-Go；
- holdout validator：23 题、题型分布、题集哈希和近重复检查全部通过；
- 历史 release 审计：`effective_execution_status=revoked_before_execution`；
- v2 执行状态：`locked_no_release`；
- 旧 v1 授权命令按预期以非零状态失败；
- 未授权 v2 命令按预期以非零状态失败；
- 报告事实校验：24 项来源、16 项必需声明、14 项禁止声明全部通过；
- 5 张报告图与 manifest 一致；
- v1.0 归档 23 个 payload 全部通过，Manifest SHA-256 保持 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`；
- `pip check` 无损坏依赖；
- `git diff --check` 无空白错误，只有 Windows LF/CRLF 提示。

### 本轮边界

- 未实现 Evidence Packer、Prompt v2、Claim-level Verifier 或 `PARTIAL_PASS` 业务逻辑；
- 未读取或运行 extension QA，未运行 final；
- `reports/extension/`、v2 release、execution state、receipt、答案和指标仍不存在；
- v1 release、implementation manifest、v1 配置、v1 trace、题集、图谱、Chunk、索引和冻结结果均未删除或覆盖；
- 用户提供的 DOCX 保持未跟踪、未修改，不纳入提交。

### 当前状态与下一步

阶段 8.0 已完成，原 v1 授权的误执行风险已关闭，v2 研究问题和评测口径已在业务增强前冻结。下一阶段进入 8.1：只实现确定性的 intent-aware Evidence Packer、packing trace、字符预算和题型覆盖测试；完成 dev/pilot 回归前仍不运行 extension。

## 2026-07-23 阶段 8.1：Intent-aware Evidence Packer 与可见证据边界

### 完成事项

- 新增 `src/agent/generators/evidence_packer.py`，实现确定性的 `intent_aware_v2` Evidence Packer：
  - 按 `chunk_id` 和 `evidence_id` 稳定去重文本证据，按 `path_id` 稳定去重图路径；
  - 优先选择图路径绑定 Chunk，再按实体标题/heading/正文匹配、题型标签、查询词、原检索分数和原顺序稳定补齐；
  - 实体匹配兼容 `KMeans` / `K-means` 等标点变体；
  - 定义、单跳关系和指标推荐题的目标上限为 4 条；对比、解释、多跳和一般问题的目标上限为 6 条；配置硬上限仍为 8 条；
  - 对比题在证据可用时为前两个实体各保留 2 条；
  - 解释题平衡机制、优势和局限证据；
  - 多跳题优先为每条可见图路径保留绑定 Chunk；
  - 指标推荐题同时保留指标定义和适用场景；
  - 总上下文严格限制为 10,000 字符，单条证据最多 900 字符；预算不足时移除完整证据或路径块并记录 gap，不对最终结构任意硬截断。
- 将 `EvidenceContextSerializer` 改为兼容外壳：
  - 旧 `serialize()` 调用仍可使用；
  - 新 `pack()` 返回结构化 `EvidencePack`；
  - Retriever 输出的原始 `RetrievalResult` 不被原地修改。
- 扩展统一 Schema：
  - 新增 `EvidencePackingTrace`，记录 selected E/Chunk/P IDs、reason codes、实体覆盖、coverage gaps、截断/淘汰 ID、输入/输出字符数、目标条数、硬预算和 `evidence_packing_latency_ms`；
  - 新增 `EvidencePack`，封装本次 Generator 可见的文本证据、图路径、序列化上下文和 trace；
  - `AnswerPayload` 保留当前生成调用的 packing trace；
  - `FinalResponse` 保留首轮与重试的完整 `evidence_packing_trace` 列表。
- 收紧 LLM 可见证据边界：
  - `LLMAnswerGenerator` 只接受本次 packed context 中可见的 E/P/R ID；
  - 原始完整 `RetrievalResult` 仍交给 Verifier，Packer 不缩小验证审计范围；
  - 无文本证据时也返回带 trace 的受控空证据 payload；
  - LLM 服务失败并回退 `GroundedAnswerGenerator` 时保留本次 packing trace；
  - Verifier 触发一次重试时分别记录两次 packing trace。
- 扩展运行与评测 trace：
  - `scripts/run_agent.py` 输出 packing 调用数、selected IDs、paths、gap 和 packing latency；
  - `scripts/run_evaluation.py` 输出逐题 packing trace、总 packing latency、均值和 Packer 版本；
  - `src/evaluation/extension_runner.py` 预接 v2 packing trace 与均值字段，但本阶段没有运行 extension；
  - `config/settings.yaml` 新增 `evidence_packer=intent_aware_v2` 和 `comparison_evidence_per_entity=2`；
  - `src/llm/config.py` 与 `scripts/validate_config.py` 同步强类型配置和状态输出。
- 新增测试与验证：
  - `tests/test_evidence_packer.py` 覆盖稳定去重、非原地修改、定义题、标点变体、对比配额、解释题、多跳、零路径预算、字符预算、指标推荐、intent 目标和空证据；
  - `tests/test_answer_generators.py` 覆盖未展示 ID 拒绝、fallback trace 和工作流重试 trace；
  - `tests/test_extension_release.py` 覆盖新 trace 字段与 v1 治理隔离；
  - 新增 `scripts/validate_evidence_packer.py`，只读取 dev/pilot，执行 Router、Retriever 与 Packer 合同检查，不调用 LLM，也不读取 final/extension 题面。
- 同步项目文档：
  - 更新 `README.md`、`PROJECT_HANDBOOK.md`、`PROJECT_GAPS_AND_ROADMAP.md`、Partial-pass 计划和随机森林过度拒答诊断；
  - 更新科研报告、报告事实检查清单、技术增强决策和评测数据说明；
  - 明确 Packer 是确定性上下文组织，不是 Dense Retrieval、RRF 或学习式重排；
  - 明确 Packer 已完成但过度拒答尚未解决，不能提前宣称 LLM 增强有效。

### 工程回归与真实 smoke

- `python scripts/validate_evidence_packer.py`：
  - dev 10 题与 pilot 40 题，共 50 题；
  - 相同输入重复打包结果稳定；
  - 平均选择 4.38 条文本证据；
  - 最长上下文 7,783 字符；
  - coverage gap 仅 1 次，为无答案题 `F-NA-01` 的预期 `no_text_evidence`；
  - 未修改任何原始 `RetrievalResult`，未产生未知 E/P/Chunk ID。
- 对真实 dev 问题“随机森林为什么更稳定”执行最终 LLM smoke：
  - decision=`refuse`；
  - evidence score=`0.8000`；
  - claim coverage=`0.3333`；
  - citation validity=`1.0000`；
  - path validity=`1.0000`；
  - retrieval sufficiency=`1.0000`；
  - retry count=`1`；
  - 两次 generation latency 分别为 `10186.3 ms` 与 `8696.6 ms`；
  - 两次 packing latency 分别为 `6.024 ms` 与 `5.200 ms`；
  - 两次均选择 `E1,E4,E8,E2,E6,E5` 和 `P1,P2,P3`，首轮上下文为 7,371 字符且无 gap；
  - P/E ID 混填问题没有再次出现，但仍有 2/3 Claim 未通过严格术语覆盖。
- 本次 smoke 证明证据选择、可见 ID 边界和 trace 正常工作，但没有证明回答质量提升；剩余根因集中在原子 Claim、quote 对齐和整题聚合决策。

### 当前阶段验证

```bash
pytest -q
python scripts/validate_config.py
python scripts/validate_graph_data.py
python scripts/validate_graph_evidence.py
python scripts/validate_chunks.py
python scripts/validate_evidence_packer.py
python scripts/validate_evaluation.py
python scripts/validate_experiments.py
python scripts/validate_scoring.py
python scripts/validate_llm_probe.py
python scripts/validate_extension_holdout.py
python scripts/validate_extension_release.py --check-runtime-model --require-unexecuted
python scripts/validate_report_claims.py
python scripts/generate_report_figures.py --check
python scripts/freeze_baseline.py --verify
python -m pip check
git diff --check
```

- 全量测试：`87 passed`；
- 配置确认 `ollama/qwen3:4b + rule planner + llm generator + intent_aware_v2 packer`；
- 图数据确认 50 个实体、100 条 approved 关系和 100 份有效关系证据；
- 文档数据确认 164 个 Section、180 个 Chunk；
- Packer 合同检查：50 题全部通过；
- 五套评测数据确认 dev=10、demo=8、pilot=40、final=40、extension=23；
- 实验配置和用户确认评分一致，160 行评分覆盖 4 种方法和 9 个错误案例；
- LLM 探针保持 Schema 60/60、Generator Go、Planner No-Go；
- extension holdout 保持 23 题和原题集哈希，v1 有效状态为 `revoked_before_execution`，v2 为 `locked_no_release`；
- 历史 v1 release SHA-256 保持 `af4f8ac10c247483af20e93f5fdde5220b608fb8c9dfb8c031d777d8b1932d0c`；
- 历史 v1 implementation manifest SHA-256 保持 `2f6e0b06c66d66d6efcc020d8ea7b291ba4ec92e6a1e4b9c575d06f3b2676382`；
- 报告事实校验：24 项来源、16 项必需声明、14 项禁止声明全部通过；
- 5 张报告图与 manifest 一致；
- v1.0 归档 23 个 payload 全部通过，Manifest SHA-256 保持 `2e9c08ff379c2a953d4356b307e20adca62ee2b3bf19ffe602be2832c4c44ba1`；
- `pip check` 无损坏依赖；
- `git diff --check` 无空白错误，仅有 Windows LF/CRLF 提示；
- `reports/extension/` 和 `extension_holdout_release_v2.json` 均不存在。

### 本轮边界

- 未修改 Prompt v1、Verifier 决策逻辑或 `PASS / RETRY / REFUSE` 状态集合；
- 未实现原子 Claim Prompt v2、Claim-level Verifier 或 `PARTIAL_PASS`；
- 未运行 final 或 extension QA，也未生成任何 extension 指标；
- `reports/extension/` 与 `extension_holdout_release_v2.json` 仍不存在；
- v1 release、implementation manifest、v1 配置、v1 trace contract、revocation record、题集、图谱、Chunk、索引和冻结结果均未删除或覆盖；
- 工作区中的两份 DOCX 删除来自外部状态，本阶段不恢复、不修改、不暂存、不提交。

### 当前状态与下一步

阶段 8.1 已完成。Evidence Packer 已把“送给 LLM 的证据”从固定半预算 Serializer 升级为可审计的题型感知选择，同时保持完整 Retriever/Verifier 证据链不变。下一阶段只进入 8.2：冻结原子 Claim Prompt v2、限制最多 4 条 Claim、强化 E/P 字段与逐字 quote 合同并完成合成结构探针；仍不修改 Partial-pass 决策，也不运行 final/extension。
