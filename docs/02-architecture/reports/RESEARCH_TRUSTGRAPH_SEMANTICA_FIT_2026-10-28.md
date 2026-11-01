---
id: odap.l2.reports-research-trustgraph-semantica-fit-2026-10-28
status: reference
owner: architect
version: ''
layer: L2
concern: architecture
lifecycle: historical
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 一次性架构审计/评审/研究报告，结论已并入现行架构文档
governance_evidence: docs/02-architecture/README.md 目录说明；文件名含审计日期或 REPORT/AUDIT 标识
---

# TrustGraph 与 Semantica 功能契合度评估及上层整合方案

> **日期**：2026-10-28
> **状态**：研究结论（决策建议，未进入实施）
> **评估对象**：TrustGraph（trustgraph-ai/trustgraph）、Semantica（semantica-agi/semantica）、ODAP（本仓库）
> **一句话结论**：**不整体替换，不在三者之上再造一层"统一底座"。以 ODAP 现有控制面为唯一底座，TrustGraph 与 Semantica 降级为受契约约束的候选能力提供者；优先"参考吸收"，其次"窄库/算法移植"，旁车仅用于离线对照，不进生产主链。**

---

## 0. 结论摘要

| 问题 | 结论 | 置信度 |
|---|---|---|
| TrustGraph 能否整体替换 ODAP？ | **不能** | 高 |
| Semantica 能否整体替换 ODAP？ | **不能** | 高 |
| 能否替换 ODAP 的部分环节？ | **能，但仅限非核心能力件**（多源接入连接器、切分算法、离线评测、RDF/SPARQL 只读互操作） | 中高 |
| 能否把两者"上层整合"为统一企业知识智能底座？ | **不能以合并/新编排层的方式实现**；可行形态是"ODAP 控制面 + 能力提供者联邦" | 高 |
| 最大的可借鉴项 | TrustGraph：Knowledge Core 快照、Flow 声明式流水线、**SHACL-AF 查询期策略过滤**；Semantica：30 个 ingestor、22 个 chunker、7 类冲突策略、PROV 链式校验设计、evals 框架 | 中高 |
| 建议的第一步 | 写《知识交换契约 v0.1》+ 在 ODAP 内实现"场景级知识快照"，**不引入任何新依赖** | 高 |

四条判断展开：

1. **三者不是同一层产品。** ODAP 是"本体驱动的分析决策平台"，覆盖语义治理、知识构建、检索、确定性推理、决策闭环、仿真、Agent 编排与审计；TrustGraph 是"语义智能体治理平台"，强在 RDF 四元组/命名图、PROV-O 检索轨迹、查询期策略过滤、Agent 运行时与 MCP 工具面；Semantica 是"图原生上下文与可问责 AI 基础设施"的**能力件集合**，强在连接器/切分广度、决策域模型与冲突策略清单，但运行时契约未定。任何一方都不是另一方的超集。
2. **TrustGraph 是更接近的平台竞争者，但仍不是替代者。** 它具备 Workspaces/Collections/Flows/Knowledge Cores、Agent Runtime、RDF 1.2 命名图与溯源；但公开仓库与文档中**没有** ODAP 的 USL 术语治理、OL 六层流水线、16 项质量闸、二级审批与 HITL 飞轮、决策一等公民、因果边、结果闭环与仿真推演。更关键的是，其 README 宣称的"Agent 动作治理 / authority 校验"在 OSS 源码中**没有对应实现**；当前 policy 只是 v2.10（2026-10-25）新增的 SHACL-AF **查询期结果过滤**，且 attestation、企业 IAM、防篡改审计在闭源侧。其 `Triple` 也没有 `valid_at/invalid_at`，**无法替代 Graphiti 双时态**。
3. **Semantica 的能力已被 ODAP 大部分吸收，且 0.7.0 存在四项硬阻断。** 2026-08-14 的评估已推动 ADR-075/076/077/078 落地（确定性推理、决策智能、SHACL/OWL、图分析），TARGET_PLAN v1.1 仅剩质量闸 SHACL 合规率、两阶段实体解析、simulation/qa 消费方接入等尾项。同时，源码级复核确认：`sanitize_identifier` 只接受 ASCII（中文标签 `人物` 直接 `ValidationError`）、全仓无 workspace/tenant、零 async 公共入口、REST `/build` 为未接线桩且 `/health` 无条件 200。它不能作为运行时依赖，只能作为能力清单与领域模型参考；局部接触面仅 ingestor、chunker、PROV 校验思路三处（§7.2）。
4. **"可持续迭代的上层整合"只有一种稳态：单一控制面 + 多能力提供者。** 两个上游都有各自的身份/工作空间、图模型、摄入流水线与 Agent 运行时；把它们并入同一个"底座"会产生第二控制面、双写与真相源分裂。正确做法是让 ODAP 继续拥有身份、本体、治理、决策、审计与配额，外部能力只能**单向投影进、候选态回流**。

---

## 1. 任务拆解与评估口径

用户的原始要求可拆成四个可判定问题：

| 编号 | 问题 | 本文对应章节 |
|---|---|---|
| Q1 | 功能契合度如何？ | §3 九要素矩阵 |
| Q2 | 能否更替部分环节？ | §4 逐环节判定 |
| Q3 | 若不能整体替换，差异在哪里、可借鉴什么？ | §5、§7 |
| Q4 | 能否基于两者持续迭代、上层整合为统一底座？ | §5.4、§6、§8 |

判定不只看"功能有没有"，还看六个工程维度：

1. **覆盖面**：是否覆盖 ODAP 的核心链路，而不是单点能力。
2. **控制面归属**：身份、工作空间、本体 schema、摄入流水线、Agent 运行时、审计由谁拥有。
3. **数据模型兼容性**：Graphiti 双时态 Episode、RDF 命名图、属性图 LPG 之间的语义损耗。
4. **组织适配**：ODAP 是 3–5 人团队、无专职 SRE/DevOps 的模块化单体（ADR-046）。
5. **上游稳定性**：版本节奏、API 破坏性变更、测试与供应链成熟度。
6. **许可与安全**：许可证、传递依赖、数据驻留、可审计性。

**证据边界**：两个项目各有独立主源调研，本文的结论以其源码核验为准——TrustGraph 见 [`RESEARCH_TRUSTGRAPH_SOURCES_2026-10-28.md`](RESEARCH_TRUSTGRAPH_SOURCES_2026-10-28.md)（PyPI sdist 2.11.1、官方文档站、GitHub raw、npm/shields），Semantica 见 [`RESEARCH_SEMANTICA_SOURCES_2026-10-28.md`](RESEARCH_SEMANTICA_SOURCES_2026-10-28.md)（0.7.0 wheel 实解、导入/体积实测、issue 与文档站）。两份报告均区分"文档声称"与"源码可验证"。未部署完整栈、未运行基准、未做端到端集成验证；Semantica 的 30 个 ingestor 与 22 个 chunker 未逐个执行。因此本文结论是**架构与接口层结论**，不是性能结论；任何采纳动作前必须做 2 周 spike。

---

## 2. 事实基线

### 2.1 ODAP 当前规模与能力

| 维度 | 事实 | 证据 |
|---|---|---|
| 架构版本 | v7.0.0，"一纵一横"：纵向 3+1 业务主干，横向 T1–T8 技术能力层 | `docs/02-architecture/ARCHITECTURE.md` 版本说明 |
| 代码规模 | 后端 `apps/api/odap` 1,435 个 `.py`；测试 373 个 `test_*.py` | 2026-10-28 仓库扫描 |
| API 面 | 104 个独立 `/api/*` 前缀；统一注册于 `router_registry.py` | 2026-10-28 仓库扫描 |
| 前端 | 26 个一级业务模块目录 | 2026-10-28 仓库扫描 |
| 治理资产 | 89 个 ADR | `docs/07-adr/` |
| 语义治理 | USL 术语体系、OL 六层流水线、16 项质量闸、10 状态二级审批 + HITL、缺口池、漂移扫描、路由工单 | `docs/03-modules/semantic_admin/DESIGN.md`、ADR-086/090 |
| 推理与决策 | pyDatalog 0.17.4 + Allen 时态代数；DecisionRecord 一等公民、7 个决策端点、因果边、规则门禁、结果闭环 | ADR-075/076、`biz/decision/` |
| 图与溯源 | Graphiti 双时态 + Neo4j；SHACL/OWL；PROV-O 导出；图分析双后端 | T2/T7/T8、ADR-077/078 |
| 检索 | `auto/graph/nl/metric/chain/mdl/hybrid` 多模式统一检索 + 查询审计 + 工作空间隔离 | `biz/core/ontology/semantic_retrieval/api/routes.py` |
| LLM 边界 | 三层治理：推理层零 LLM；理解层"只选不创"；生成层事实必须锚定来源 | ADR-079 |
| 组织约束 | 3–5 人，无专职 SRE/DevOps；模块化单体优先 | ADR-046 |
| 已知缺口 | 摄入车道绕过治理（F1）、质量闸占位子项按 1.0 计入（F2）、USL 归一未接写入链（F3）、SHACL 未持久化且不在写路径（F7） | ADR-084 |

### 2.2 TrustGraph 事实卡

| 维度 | 事实 | 证据 |
|---|---|---|
| 自我定位 | "The Semantic Agent Governance Platform"；"ontology-grounded operating graph"；"Agents propose actions… checks them against business meaning, authority, and evidence before execution" | README（2026-10） |
| 定位落差 | **OSS 源码无 action gate / authority 校验引擎**；`grep propose_action\|action_gate` 为空。当前 "policy" = SHACL-AF **查询期**结果过滤（v2.10，2026-10-25，发布 3 天） | 源码 `policy/policy_filter.py`、主源调研 §4 #12 |
| 数据模型 | RDF 1.2、命名图/四元组（s,p,o,g）、OWL 导入、PROV-O；reification 仅指"三元组作为被引用项"，**不是 n 元超图** | 源码 `schema/triples.py` |
| 时序 | **无** `valid_at/invalid_at`，无双时态；全仓无 bitemporal 检索 | 源码核验 |
| 推理/校验 | **无 DL reasoner**，仅 `subClassOf` 祖先遍历；**无 SHACL 写路径校验**，SHACL 仅出现在查询期策略过滤 | 源码核验 |
| 存储 | Cassandra（四元组/行/元数据）、Qdrant（向量）、Garage（S3）；可选 Neo4j/Memgraph/FalkorDB、Milvus/Pinecone/FAISS | README、文档站 |
| 消息/流 | Pulsar（默认）、RabbitMQ、Kafka；`trustgraph-base` 同时依赖 `pulsar-client`、`pika`、`aio-pika`、`confluent-kafka`、`aiokafka` | `trustgraph-base/pyproject.toml` |
| LLM | vLLM、TGI、Ollama、LM Studio、Llamafiles | README |
| 组织抽象 | Workspaces、Collections、Flows、Context Cores（可导出/导入知识包） | README、源码 `core_export/core_import` |
| Agent | ReAct、plan-then-execute、supervisor 并行子 Agent、meta-router；行为追踪 | 文档站、源码 `agent/` |
| API/协议 | RPC 风格 `POST /api/v1/{kind}` + WS `/api/v1/socket`；OpenAPI spec 2.4 有 Redoc 渲染但**下载链接失效**；`trustgraph-mcp` 暴露 **31 个 MCP 工具** | 文档站、源码 |
| 代码结构 | `trustgraph-base`（26k 行）、`trustgraph-flow`（57k 行 / 408 文件）、`trustgraph-cli`、`trustgraph-mcp`、Bedrock/VertexAI/Torch/OCR 适配包 | PyPI sdist |
| 部署 | Docker/K8s，`npx @trustgraph/config`；最小 compose **12GB/8CPU**（另一页写 8GB/4 核，自相矛盾）；启动 34 个 processor / 9 个 flow class；UI 8888 | 文档站 |
| 许可 | Apache-2.0；**open-core**：attestation、企业 IAM、防篡改审计在闭源侧（Knownext Inc.） | LICENSE、文档站 |
| 版本/节奏 | PyPI **2.11.1**（2026-10-27）；历史 **559 个版本**；月度 minor 且 minor 承载破坏性变更（删 LangChain、容器改名、删 schema 字段）；GitHub Releases 停在 v2.8.17 | PyPI、changelog |
| 社区 | 2.8k stars、337 forks、29 contributors、17 open issues、42 commits/月 | shields.io |
| Python | `trustgraph-base` 要求 `>=3.10` | `trustgraph-base/pyproject.toml` |
| 成熟度信号 | "可跑起来"证据充分；"长期稳定运维"证据不足——Production Considerations 为占位页、零公开客户案例、文档漂移 5 处 | 文档站、主源调研 §6.5 |

**判断**：TrustGraph 的强项是"标准语义 + 查询期策略过滤 + 运行时"，弱项是"企业业务决策与语义运营"。它是一个**可对标的平台**，但公开证据不足以证明它具备 ODAP 的语义治理深度与决策闭环。

### 2.3 Semantica 事实卡

| 维度 | 事实 | 证据 |
|---|---|---|
| 自我定位 | "Graph-Native Infrastructure for Context and Accountable AI Systems" | README |
| 许可 | **MIT**；商业侧 Free(MIT) / Paid Pilot / Managed Cloud 与 Self-Hosted Enterprise 均标 "In Development" | LICENSE、getsemantica.ai/pricing |
| 发布版本 | **0.7.0**（2026-09-22，PyPI 已发布）；main 分支 `pyproject.toml` 为 0.8.0 **未发布**。本文一律以 0.7.0 为准 | PyPI JSON、`pyproject.toml` |
| 发布节奏 | 25 个 release / 10 个月；自我声明 MAJOR 每季度（**含破坏性变更**）、MINOR 每月 | releases、docs governance |
| Python | 0.7.0 `>=3.10,<3.14`（与 ODAP 一致）；main 已升至 `>=3.11`，下一版将破坏 3.10 兼容 | `pyproject.toml` |
| 依赖重量 | 核心依赖 **22**（0.6.5 为 42）；extras **62**；`pip download` 实得 47 wheels / 118.3 MB；安装后 **512 MB** | `pyproject.toml`、实测 |
| 导入成本 | `import semantica` 23 ms（`__init__` 几乎不导入，是假象）；`semantica.reasoning` **963 ms**；`semantica.kg` 834 ms | 实测 |
| 公共 API 形态 | `__all__ = []`；顶层模块白名单**不含** context/reasoning/provenance/conflicts/deduplication；无 `.pyi`、无 Protocol 层；**全同步，无 async 公共入口** | `__init__.py`、源码检索 |
| 模块面 | ingest/parse/split/normalize/semantic_extract/kg/ontology/reasoning/graph_store/triplet_store/context/provenance/conflicts/deduplication/change_management/pipeline/... | 0.7.0 wheel |
| 能力广度 | **30 个 ingestor、22 个 chunker**；7 类冲突消解策略；MCP **15 个工具**；RDF 四后端、LPG 四后端 | wheel 目录 |
| Polyglot 真相 | `graph_store`（LPG）与 `triplet_store`（RDF）是**两套独立客户端、两套查询语言、两套事务语义**，无统一查询；"polyglot" = 两种都支持，不是联合查询 | 源码 |
| 推理 | 0.7.0 Rete 已重写为 alpha/beta 网络，但**无 alpha 共享**，复杂度仍 O(规则数 × 事实数)；1,000 事实 × 100 规则 = 0.41 s；unification 仍靠正则命名组。TMS 仅支持非递归规则 | `rete_engine.py`、实测 |
| 决策域模型 | Decision/DecisionContext/Policy/PolicyException/Precedent/ApprovalChain；但**无 tenant/workspace 属性**、`CREATE (d:Decision {...})` **非幂等**；影响分析缺 gensim 时返回 `{"error": ...}` 而非抛错 | `context/decision_recorder.py`、`decision_query.py` |
| PROV 完整性 | 导出可用（实测 1,270 字节合法 Turtle）；**checksum 非单射**（16 字段无分隔符直接拼接），`verify_chain()` 会假通过，而 docstring 宣称支持 21 CFR Part 11 / SOX / HIPAA | issue #2136、`provenance/integrity.py` |
| 服务面 | REST `/build` 为**未接线桩**（真实调用被注释仍返回 accepted）；`/health` **无条件 200**；orchestrator 失败分支返回 `{"status": "placeholder"}` | `server.py`、`core/orchestrator.py` |
| 中文标识符 | `graph_store/query_sanitize.py` 的 `sanitize_identifier` **只接受 ASCII**；标签 `人物` 直接 `ValidationError`（源于 Cypher 注入修复 GHSA-482h-hw99-h62p） | 源码实测 |
| 隔离 | 全仓无 workspace/tenant 概念；Decision/Entity 节点无隔离属性 | 源码检索 |
| 测试 | 81 个测试文件 / 2,117 个 `def test_`；但**无 rete/reasoning/decision/ontology 专项测试**；`PipelineBuilder.validate_pipeline()` 对 `ValidationResult` 调 `.get('valid')` 直接 AttributeError，跨 0.6.5/0.7.0 未修 | wheel tests、源码 |
| 供应链 | issue #2135：定时安全扫描失败，authlib 1.8.0（6 个 CVE）、litellm 1.100.1、msgpack 1.2.2 命中高危 | issue #2135 |
| 社区/生产 | 14,276 stars / 1,673 forks / 134 contributors / 79 open issues / 60 open PRs；近 30 天下载 14,741；官网仅 **2 个**公开案例（Nereus、Ausgrid） | GitHub API、pypistats、官网 |
| CI | pytest、benchmark、CodeQL、安全扫描 | workflows |

**判断**：Semantica 是**功能面很宽、单点深度不均、工程契约未定的 0.x 工具箱**。它的价值是"该做什么"的能力清单与领域模型，不是"可以直接调用"的组件。四项硬阻断（中文标识符被拒、无租户隔离、零 async、REST 假健康/假构建）加上 PROV checksum 假通过，决定它不能作为运行时依赖。

### 2.4 版本与成熟度对"可持续迭代"的含义

| 信号 | TrustGraph | Semantica | 对整合策略的影响 |
|---|---|---|---|
| 发布节奏 | 559 个 PyPI 版本；月度 minor；11 个版本集中在 2026-10-07～10-27 | **0.7.0**（2026-09-22）；25 个 release / 10 个月；声明 MAJOR 每季度 | 两者都不适合深度运行时绑定；应锁 minor/patch，做契约测试 |
| 破坏性变更 | **minor 承载破坏性变更**：删 LangChain、容器改名、删 schema 字段、端口 8088→8888 | **季度 MAJOR 含破坏性变更**：0.7.0 把 `Entity.confidence` 改 Optional、`PolicyEngine.check_compliance` 改为抛异常、移除 `dev`/`crewai` extras；main 已把 Python 抬到 3.11 | 升级即迁移；旁车必须可 kill |
| Python 约束 | `>=3.10`（与 ODAP 兼容） | 0.7.0 `>=3.10,<3.14`（与 ODAP 一致）；**下一版 `>=3.11`** | 0.7.0 不触碰基线，但升级路径会；不得把版本漂移绑进主链 |
| 依赖重量 | Pulsar + Cassandra + Qdrant + Garage + Grafana/Loki；最小 compose 12GB/8CPU | 核心 **22** 依赖、**62** extras；安装 **512 MB**；`reasoning` 导入 **963 ms** | 两者都会显著扩大 SBOM、CVE 与镜像体积 |
| 测试/运维证据 | 有 tests 目录；Production Considerations 为占位页；零公开客户案例 | 81 文件 / 2,117 测试，但**无 rete/reasoning/decision/ontology 专项**；`validate_pipeline()` 跨两版崩溃；`/health` 无条件 200 | 不能把"有测试"当质量保证；必须自建黄金集与负向测试 |
| 社区 | 2.8k stars / 29 contributors / 17 open issues | 14.3k stars / 134 contributors / 60 open PRs / 2 个公开案例 | 关注度 ≠ 交付深度；长期维护需 G1 复核 |
| 文档/API 稳定性 | 文档漂移 5 处；OpenAPI 2.4 下载链接失效；RPC + WS | `__all__ = []`、无 `.pyi`、无 Protocol；白名单不含核心五子包；无 async | 契约必须由 ODAP 定义，不能依赖上游 schema |

---

## 3. 九要素契合度矩阵

评分口径：1 = 基本缺失；2 = 有概念但不可用；3 = 可用但需大量补齐；4 = 覆盖主要场景；5 = 该维度可作行业标杆/ODAP 独有深度。评分为架构判断，非基准测试。

| 要素 | ODAP | TrustGraph | Semantica | 判定 |
|---|:--:|:--:|:--:|---|
| 本体与语义治理 | **5** | 3 | 3 | ODAP 独有 USL + OL 六层 + 质量闸 + 二级审批 + 缺口池；TG 有 OWL 导入/Workbench 但无 DL 推理、无写路径 SHACL、无治理流程；Sem 有 OWL/SHACL/SKOS 原语但无运营流程 |
| 知识摄入与构建 | 4 | 4 | 4 | ODAP 有 HE/KB/爬取/模板/四维校验，但切分固定、治理旁路；TG 有 Docling/OCR/Flow；Sem 有 **30 ingestor / 22 chunker**，广度最大 |
| 图谱存储与查询 | 4 | 4 | 2 | ODAP Graphiti 双时态 + Neo4j；TG 原生 RDF 四元组 + 多后端但**无时序**；Sem 只有适配器，且 LPG 中文标签被拒、RDF/LPG 不互通 |
| 检索与 GraphRAG | 4 | 4 | 3 | ODAP 多模式统一检索 + 审计 + 隔离；TG graph-rag/BM25+向量 RRF/检索轨迹；Sem 向量与上下文原语 |
| 推理与决策 | **5** | 2 | 2 | ODAP pyDatalog + Allen + 决策一等公民 + 因果边 + 结果闭环；TG 推理=LLM、无规则引擎、无 Decision 实体；Sem 有 Datalog/SPARQL，但 Rete 无 alpha 共享 O(R×F)、TMS 仅非递归、决策非幂等且无隔离 |
| Agent 运行时与编排 | 4 | 4 | 3 | ODAP OpenHarness v1/v2 + MCP + AG-UI + hooks + 记忆 + 技能；TG ReAct/plan/supervisor + 31 工具 MCP 服务端；Sem MCP 15 工具 + 外部集成 |
| 治理/审计/溯源 | **5** | 3 | 2 | ODAP JWT + OPA + 工作空间隔离 + 统一审计 + PROV-O + 三层 LLM 边界；TG 3 角色 RBAC + PROV-O，但审计默认不持久化、企业 IAM/防篡改审计闭源；Sem 无 RBAC/租户，PROV checksum 非单射且 verify 假通过（#2136） |
| 部署与可观测 | 4 | 3 | 2 | ODAP 单栈 Podman + dev/prod 隔离 + OTel/Prometheus + doctor；TG 分布式五件套 12GB/8CPU、生产运维页占位；Sem 512 MB 安装 + 963 ms 导入 + 零 async + REST 假健康 |
| **综合** | **4.4** | **3.4** | **2.9** | **没有超集；ODAP 在治理与决策上领先，两项目在标准互操作、连接器与切分广度上可补位** |

矩阵解读：

- **ODAP 的领先不是"功能更多"，而是"治理更深"。** USL/OL/审批/缺口池/决策闭环/三层 LLM 边界是组织与合规资产，不是代码量能快速追平的。
- **TrustGraph 的领先在"标准与证据面"。** RDF 四元组/命名图、检索轨迹、SHACL-AF 查询期策略过滤、31 工具 MCP 服务端、Agent 行为追踪，恰好对应 ODAP 的"互操作、数据级裁剪、工具面"三个薄弱点；但写路径 SHACL、动作级权限、双时态均不具备。
- **Semantica 的领先在"能力广度"，不在"可组合原语"。** 30 个 ingestor、22 个 chunker、7 类冲突策略、MCP 15 工具、evals 框架，是 ODAP 可以直接抄的清单；但 Pipeline DSL 的 `validate_pipeline()` 跨两版崩溃、两阶段 ER 无 P/R 基准、Rete 无 alpha 共享、PROV checksum 非单射——这些都说明它**广度优先、深度欠账**，不能当作现成运行时。
- **三者都不具备对方的控制面。** 这正是"不能合并"的根因。

---

## 4. 可替换性逐环节判定

| 环节 | 判定 | 建议方式 | 理由 | 主要风险 |
|---|---|---|---|---|
| 图存储 / 双时态 | **不替换** | 保留 Graphiti + Neo4j | TrustGraph `Triple` 只有 s/p/o/g，**无 `valid_at/invalid_at`**；双时态是数据模型级能力，不是配置可解 | 数据迁移不可逆、决策可复现性受损 |
| 文档解析 / OCR | **仅离线对照** | 不起旁车；Docling/OCR 只作算法参考或离线评测 | TrustGraph 任一环节都要拖入 gateway + flow + 消息总线 + 图库 + 向量库，最小 12GB/8CPU | 为 3% 解析质量引入五件套运维 |
| 多源接入连接器 | **可借鉴，逐个 copy-adapt** | 从 Semantica **30 个 ingestor** 中挑选 ODAP 缺的源类型，重写到 `IIngestor` 端口 | 纯 I/O 适配层、无状态、无 schema 侵入，是复用价值最高的部分；但上游无统一重试/限流/增量水位语义 | 连接器质量未核实；许可证与归属需保留 |
| 切分 / 抽取 | **可改善，不替换** | 从 **22 个 chunker** 中挑选实体/结构/代码/表格感知实现，统一到 ODAP 分块契约与 metadata schema | ODAP 固定 4096/512 切分是明确短板；算法移植比整包依赖可控 | 算法移植的维护成本、回归风险 |
| 实体解析 | **可改善** | 按 TARGET_PLAN 做 blocking + 语义精判两阶段；只借鉴 Semantica 的阶段划分 | Semantica 结构完整但**无 P/R 基准、阈值靠经验**，不能直接继承魔数 | 误合并、跨工作空间泄漏 |
| 检索 / GraphRAG | **不整体替换** | 保留统一检索总线；借鉴 TG 检索轨迹与图嵌入 | ODAP 已有 7 种模式、查询审计、隔离；TG 不能接管其治理 | 两套检索结果冲突、评测口径不一 |
| 数据级策略过滤 | **可改善（ODAP 内实现）** | 借鉴 SHACL-AF + UserContext→RDF，落 `infra/query` 读路径 | ODAP 的 OPA 管 API 门禁、pyshacl 管写路径形状，但"同一张图按密级/部门裁剪结果集"是空白 | 规则误杀、越权漏放；需三态审计 |
| 确定性推理 | **不替换** | 保留 pyDatalog + Allen | Semantica Rete 0.7.0 虽已重写为 alpha/beta 网络，但**无 alpha 共享**，仍 O(规则数 × 事实数)，unification 靠正则；TrustGraph 推理=LLM，无规则引擎 | 引入第二推理引擎导致结论不一致 |
| 决策 / 仿真 | **不替换** | 保留 ODAP 决策一等公民与仿真 | 两项目均无决策生命周期、因果边、结果闭环、沙盘推演 | 无替代品 |
| 语义治理 / USL / OL / 审批 | **不替换** | 保留 ODAP 语义管理台 | 两项目均无术语治理、质量闸、二级审批、HITL 飞轮 | 无替代品 |
| Agent 运行时 | **不替换** | 保留 OpenHarness；参考 TG 的 31 工具 MCP 面 | Agent 运行时与工具、记忆、权限、审计深度耦合；替换等于重做 T1 | 行为不兼容、工具生态断裂 |
| 审计 / 溯源 | **不替换** | 保留统一审计 + PROV-O；借鉴三命名图/检索轨迹与"每步 checksum + 链式 verify"的**设计意图** | 审计是合规主链；TG 审计事件默认 pub/sub **不持久化**，防篡改审计在闭源侧；Sem 的 PROV checksum **非单射且 verify_chain 假通过**（#2136），实现必须自建 | 双写、证据链断裂、假通过 |
| 前端门户 | **不替换** | 保留现有 React 前端 | TrustGraph UI 是独立产品，不是可嵌入组件 | 双入口、权限与路由分裂 |
| 部署形态 | **不替换** | 保留 Podman 模块化单体 | Cassandra/Pulsar/Qdrant/Garage 五件套 12GB/8CPU，与 3–5 人团队、无 SRE 约束冲突 | 运维成本、故障面扩大 |

**结论**：可局部替换或借鉴的只有"与主数据模型解耦、失败可回退、不拥有真相源"的能力件；TrustGraph 因全栈门槛，连文档解析也只建议离线对照。凡涉及身份、schema、审计、决策、治理的环节，一律不替换。

---

## 5. 为什么"上层再包一层统一底座"不可行

### 5.1 三个控制面冲突

| 控制面 | ODAP | TrustGraph | Semantica |
|---|---|---|---|
| 身份与租户 | JWT + 角色 + 工作空间隔离 + OPA | Workspaces/Collections（数据组织）+ 3 角色 RBAC；企业 IAM 闭源 | **全仓无 workspace/tenant 概念**；无 RBAC |
| 本体/schema | 3+1 分层、版本化、USL、SHACL/OWL | RDF/OWL 导入 + SHACL-AF 查询过滤；无 DL 推理、无写路径校验 | OWL/SHACL/SKOS；OWL 只序列化，无 DL 推理 |
| 事实时间 | Graphiti 双时态 + `state_at()` | **无时序字段** | **无 `valid_at`**；`CREATE` 写入、`id(n)` 作身份、非幂等 |
| 摄入流水线 | HE + KB + 爬取 + 模板 + 四维校验 | Flows + Librarian + Docling/OCR | PipelineBuilder 设计在，但 `validate_pipeline()` 跨两版崩溃 |
| Agent 运行时 | OpenHarness + MCP + AG-UI + hooks | ReAct/plan/supervisor + 行为追踪 | MCP 15 工具 + 外部集成 |
| 审计/溯源 | 统一审计 + PROV-O + 决策审计事件 | PROV-O + 检索轨迹；审计默认不持久化 | provenance + change management；checksum 非单射、verify 假通过 |

六个控制面全部重叠。把它们"合在一起"不是集成，而是**合并六个有状态系统**；任何一个成为主，另外两个都要被降级改造，工作量接近重写。

### 5.2 数据模型与真相源

- ODAP 的真相源是 **Graphiti Episode + 双时态事实 + 决策记录 + 审计事件**。
- TrustGraph 的真相源是 **RDF 四元组 + 命名图 + PROV-O 轨迹**；但 `Triple` 无 `valid_at/invalid_at`，**连"事实何时为真"都无法表达**。
- Semantica 的写入是**无时态的 LPG 写入**：`CREATE (n:Label $props)`、用 `id(n)` 作为身份、无 `valid_at/invalid_at`、不感知失效；若与 Graphiti 共用 Neo4j，会产生"永久有效的 Semantica 事实"与"已失效的 Graphiti 事实"并存，**无法判定真相**。它的定位只能是对外部存储的**派生投影**，不是真相源。

三者的"事实"粒度不同：Episode 是叙事单元，四元组是命题，LPG 是节点/边；而 TrustGraph 还缺少时间维度。强行映射会丢失时序、置信度、来源片段与治理状态。**双写**会立即产生两个真相源；**单向投影**只能解决读，不解决写。因此外部能力只能产出**候选**，不能直接写 canonical 图。

### 5.3 组织与运维约束

ADR-046 明确：团队 3–5 人、无专职 SRE/DevOps、模块化单体。TrustGraph 的 Cassandra + Qdrant + Garage + Pulsar/RabbitMQ 是典型分布式平台运维面；Semantica 虽在 0.7.0 把核心依赖从 42 降到 22，但仍有 62 个 extras、512 MB 安装体积、`reasoning` 导入 963 ms、且**公共 API 全同步**——嵌入 FastAPI 异步栈只能靠线程池桥接，请求级取消与 P95 都会退化。引入任何一个作为底座，都会把"功能整合"变成"基础设施整合"。

### 5.4 三种整合拓扑对比

| 拓扑 | 形态 | 粗估周期 | 风险 | 结论 |
|---|---|---|---|---|
| 合并式 | 选一个平台整体替换 ODAP | 12–24 个月 | 极高：治理/决策/仿真需重写，数据迁移不可逆 | **否决** |
| 双层式 | 新建 meta-orchestrator，三者在下 | 9–18 个月 | 高：第二控制面、双写、契约频繁破裂、运维翻倍 | **否决** |
| 联邦式 | ODAP 控制面 + 能力提供者 + 契约 | 每能力 6–12 周 | 中：契约与适配器维护 | **推荐** |

### 5.5 "上层整合"的正确含义

用户要求的"上层整合"应当解释为：**在 ODAP 已有的控制面之上，定义统一的能力契约与注册机制**，而不是再写一个平台。ODAP 的 `infra/providers.py`（ADR-081）已经提供了正确的 seam：`register_provider` / `resolve_provider`，未注册即抛错，禁止静默降级。外部能力应作为 provider 实现接入，而不是成为新的控制面。

---

## 6. 推荐目标架构：控制面 + 能力提供者

### 6.1 架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                    ODAP 控制面（唯一真相源）                      │
│  身份/工作空间 │ 本体与版本 │ 语义治理(USL/OL/审批/质量闸)        │
│  决策闭环      │ 审计/PROV-O│ 检索路由/配额/成本/可观测            │
└──────────────┬───────────────────────────────┬───────────────────┘
               │  Knowledge Exchange Contract  │
    ┌──────────▼───────────┐        ┌──────────▼───────────┐
    │ TrustGraph Adapter   │        │ Semantica Adapter    │
    │ 离线评测 / 只读互操作 │        │ 窄库 / 算法移植       │
    └──────────┬───────────┘        └──────────┬───────────┘
               │                               │
    ┌──────────▼───────────┐        ┌──────────▼───────────┐
    │ TrustGraph 评测环境   │        │ Semantica 进程/库     │
    │ Cassandra/Qdrant/... │        │ pipeline/reasoning   │
    └──────────────────────┘        └──────────────────────┘
```

> 默认拓扑中 TrustGraph **不进入生产**；仅当 G3 通过、且业务接受 12GB/8CPU 与五件套运维时，才考虑作为只读能力提供者。Semantica 只做 copy-adapt（连接器、切分、校验思路），不做窄库或整包运行时依赖。

### 6.2 五条硬约束

1. **单一真相源**：canonical 图、决策、审计只在 ODAP；外部存储只能是派生视图。
2. **禁止双写**：任何一方不得同时写两个存储；外部服务不得直连 ODAP 的 Neo4j/SQLite。
3. **单向投影 + 水位线 + 幂等**：ODAP → 外部按 `watermark` 增量投影；外部 → ODAP 只回传候选，带 `idempotency_key`。
4. **外部结果只能进候选区**：进入 `candidate_store`，走质量闸与审批，不得直接写 typed 图。
5. **契约版本化 + 可杀死**：每个适配器有版本矩阵、健康检查、kill switch；失败必须显式，禁止兜底（规则 14）。

### 6.3 知识交换契约 v0.1（Knowledge Exchange Contract）

| 对象 | 关键字段 | 约束 |
|---|---|---|
| `CapabilityDescriptor` | name、version、license、inputs、outputs、SLA、determinism_class、model_deps、data_residency | 注册时必填；无描述不得上线 |
| `KnowledgePacket` | packet_id、workspace_id、scenario_id、ontology_version、source{uri,hash,media_type}、content_ref、classification、acl | 必须带来源哈希与 ACL；跨工作空间拒绝 |
| `ProvenanceEnvelope` | activity、agent、model、prompt_hash、source_spans、timestamp、parent_ids | 与 PROV-O 对齐；缺来源即拒绝 |
| `AccessContext` | user_id、workspace_id、roles、attributes、purpose、clearance | 随请求透传；用于数据级策略过滤；不得由外部服务自行推断 |
| `EntityMention` | mention_id、surface、span、type_hint、confidence、extractor{name,version}、provenance | 类型只能是 closed set 或标记 open |
| `RelationAssertion` | subject_ref、predicate、object_ref、confidence、evidence_spans、extractor | 证据片段必填 |
| `CandidateEnvelope` | candidate_id、origin、status、dedupe_key、quality_report、provenance | `status` 只能是 candidate/rejected/accepted；禁止 direct write |
| `QualityReport` | metric_scores、evaluated_flags、violations、gate_version | 未评估子项必须标 `not_evaluated`，不得按 1.0 计入 |
| `ProjectionManifest` | direction、watermark、schema_version、idempotency_key、checksum | 单向、可重放、可审计 |

契约的四个"不可协商"：

- `workspace_id` + `scenario_id` + `ontology_version` 是复合主键的一部分。
- 任何外部产出不得携带 `status=accepted`；接受权在 ODAP。
- 任何事实必须可追溯到 `source_spans`；无来源即拒绝。
- `determinism_class` 必须声明（deterministic / probabilistic / llm_assisted），供决策与审计分层。

### 6.4 代码落点与依赖方向

遵循现有 import-linter 契约（C1–C4）与 ADR-081：

```
apps/api/odap/
├── biz/
│   ├── integration/
│   │   └── knowledge_exchange/
│   │       ├── contracts.py          # Pydantic v2 契约对象
│   │       ├── registry.py           # 能力注册 + 版本矩阵
│   │       ├── adapters/
│   │       │   ├── trustgraph.py     # HTTP/MCP 客户端，只读/候选
│   │       │   └── semantica.py      # 窄库/本地进程适配
│   │       └── projection.py         # 水位线、幂等、重放
│   └── providers_bootstrap.py        # 注册 provider 工厂
└── infra/
    └── providers.py                  # resolve_provider（已存在）
```

规则：

- `infra/` 不得 import `biz/`；适配器工厂在 `biz/providers_bootstrap.py` 注册。
- 外部服务只通过 HTTP/MCP 访问，禁止直连数据库。
- 适配器失败必须抛错并记录结构化日志（规则 14），不得返回空结果冒充成功。
- 所有适配器必须有契约测试，用真实响应样本回放，不以 MagicMock 替代主逻辑。

### 6.5 四种适配模式与适用条件

| 模式 | 适用条件 | 成本 | 风险 | 本文建议 |
|---|---|---|---|---|
| 参考吸收（reference absorption） | 只需要设计思想/算法 | 低 | 低 | **默认** |
| 窄库 / 算法移植（narrow library） | 单个模块可独立、许可允许、依赖可控 | 中 | 中 | Semantica ingestor/chunker 候选（copy-adapt，不做运行时依赖） |
| 旁车服务（sidecar） | 能力有状态、需独立扩缩容、接口清晰 | 中高 | 中高 | 仅离线评测/只读互操作；TrustGraph 全栈 12GB/8CPU，当前不推荐生产 |
| Fork / vendor | 上游停更且能力关键 | 高 | 高 | **当前不采用** |
| 整体替换 | 上游是超集 | 极高 | 极高 | **否决** |

---

## 7. 可借鉴清单

### 7.1 来自 TrustGraph

| # | 借鉴点 | ODAP 现状 | 落点 | 优先级 | 粗估 |
|---|---|---|---|---|---|
| T1 | **Context Core / Knowledge Core**：不可变知识快照，可加载/卸载/导出 | 无场景级知识快照；QA/决策复现依赖实时图 | `semantic_admin` 或 `infra/graph` 增加 snapshot/restore | **P0** | 2–3 人周 |
| T2 | **Flow**：声明式处理图 + Flow Blueprint 模板 | OL 六层与摄入流水线以代码编排 | `biz/integration` 增加 pipeline 配置模型与执行器 | **P0** | 3–4 人周 |
| T3 | **SHACL-AF 查询期策略过滤 + UserContext→RDF 注入** | OPA 管 API 门禁、pyshacl 管写路径；缺"按密级/部门裁剪结果集" | `infra/query` 读路径或 `infra/graph`，复用 pyshacl | **P0** | 3–4 人周 |
| T4 | **三命名图默认开启**：知识 / 抽取血缘 / 检索轨迹 | PROV-O 在审计导出层，属事后导出 | ADR-074 + ADR-076 合并为查询即证据 | P1 | 3–5 人周 |
| T5 | **Context Core 可移植知识包** | 有 OntologyVersion，无"知识实例"可搬运单元 | 场景级知识包（交付/演示/隔离测试） | P1 | 2–3 人周 |
| T6 | **命名图 / 具体化**（注意：不是 n 元超图） | PROV-O 为 episode 级，缺事实级归属 | `infra/graph` + PROV-O 导出 | P1 | 3–4 人周 |
| T7 | **IAM capability 封闭词表 + 网关零策略状态** | OPA 路由逐个判权 | `infra/opa` 策略契约 | P1 | 2–3 人周 |
| T8 | **Librarian**：文档生命周期（add/list/remove） | KB 有文档管理，但生命周期与血缘不完整 | `biz/data/knowledge_base` 增强 | P1 | 2 人周 |
| T9 | **Agent 行为追踪**：结构化执行轨迹 | 有 AG-UI/hooks，但 trace schema 不统一 | `biz/integration/openharness_agent` | P1 | 2 人周 |
| T10 | **图嵌入检索** | 有语义检索与 GraphRAG，图级向量可评估 | `semantic_retrieval` | P2 | 3–5 人周 |
| T11 | **配置/自检 CLI** | `bootstep.py doctor` 已有 | 对齐命令面与输出格式 | P2 | 1 人周 |
| T12 | **多语言文档体系**（10 语言 × 43 文件） | 中文为主 | `docs/` i18n | P2 | 低 |

**T1 与 T3 的价值最高**：T1 同时解决"决策可复现、QA 可回放、评测可基线"；T3 填补"数据级裁剪"这一真实治理空白，且可复用 ODAP 已有的 pyshacl，不需要引入 TrustGraph 运行时。两项都不依赖外部服务，建议作为第一批落地项。

### 7.2 来自 Semantica

| # | 借鉴点 | ODAP 现状 | 落点 | 优先级 | 粗估 |
|---|---|---|---|---|---|
| S1 | **30 个 ingestor**（纯 I/O 适配层，无状态、无 schema 侵入） | HE/KB 覆盖源类型有限 | `biz/data/` 或 HE 适配层，**按缺口挑选**逐个重写到 `IIngestor` 端口，补重试/限流/增量水位 | **P0** | 每类 1–2 人周 |
| S2 | **22 个 chunker**（实体/结构/代码/表格感知） | HE 固定 4096/512 | `biz/data_pipeline`，统一到 ODAP 分块契约与 metadata schema | **P0** | 3–4 人周 |
| S3 | **Pipeline DSL 设计**（阶段、输入输出、依赖分层、`parallel_safe` 标记） | OL 六层与摄入流水线以代码编排 | `ol_pipeline` + 通用执行器；**只抄设计，不抄实现**（上游 `validate_pipeline()` 直接崩溃） | P1 | 4–6 人周 |
| S4 | **两阶段 ER 结构**（blocking → clustering → merge） | TARGET_PLAN 已规划未推广 | `semantic_admin` candidate 去重；用 ODAP 语料重标定 P/R，不继承上游魔数 | P1 | 4–6 人周 |
| S5 | **7 类冲突消解策略 + 冲突分析器 + 调查指南** | `construction/conflicts` 已有 3 策略 + Wilson 平滑 | 补齐策略清单；消解逻辑仍与 ODAP 本体/审批/审计耦合 | P1 | 3–4 人周 |
| S6 | **变更管理 / 版本 diff** | 本体有版本，缺影响面 diff | `biz/core/ontology` 版本模块 | P1 | 3–4 人周 |
| S7 | **PROV 链式校验的设计意图**（每步 checksum + `verify_chain`） | 有 PROV-O 导出，无单射 checksum 与碰撞测试 | **自建**：带长度前缀/分隔符的单射 checksum + 碰撞负向测试；**不引上游实现** | **P0** | 2–3 人周 |
| S8 | **MCP 工具粒度**（15 工具切分） | 已有 MCP 适配 | 参考工具描述、参数与错误契约 | P2 | 2 人周 |
| S9 | **evals 框架** | 缺统一评测入口 | 并入 Phase 1 的质量评估 harness，不新起一套 | P1 | 3–4 人周 |
| S10 | **RDF/SPARQL 只读投影** | 有 OWL 导出，无 SPARQL 端点 | `infra/query` 只读投影；与现有 rdflib 方案二选一，不并行 | P2 | 4–6 人周 |
| S11 | **决策域模型字段对照** | ADR-076 模型更完整（异步 + 隔离 + 幂等） | 仅对齐字段命名与文档，不采纳模型 | P2 | 1–2 人周 |

**S1 + S2 是最高性价比组合**：两者都是纯适配/算法层，可在 ODAP 内部实现，不引入 Semantica 运行时依赖，直接改善抽取覆盖与切分质量。**S7 是合规红线**：上游 checksum 已证明会"假通过"，ODAP 必须自建单射校验并写碰撞用例，不能因为"对方有 PROV 实现"而省这一步。S3 只抄设计——上游 `PipelineBuilder.validate_pipeline()` 在 0.6.5 与 0.7.0 都崩溃，说明该入口没有测试覆盖。

### 7.3 明确不借鉴 / 否决

| 项 | 原因 |
|---|---|
| Semantica 作为运行时依赖 | 四项硬阻断：中文标签被 `sanitize_identifier` 拒绝、无 workspace/tenant、零 async、REST `/build` 桩 + `/health` 无条件 200 |
| Semantica `PipelineBuilder` 实现 | `validate_pipeline()` 对 `ValidationResult` 调 `.get('valid')` 直接 AttributeError，跨 0.6.5/0.7.0 未修 |
| Semantica PROV `integrity.py` | checksum 非单射、`verify_chain()` 假通过，而 docstring 宣称支持 21 CFR Part 11/SOX/HIPAA |
| Semantica DecisionRecorder | 同步、无 tenant 属性、`CREATE` 非幂等；影响分析缺 gensim 时返回 `{"error": ...}` 而非抛错 |
| Semantica Rete 引擎 | 0.7.0 已重写但**无 alpha 共享**，O(规则数 × 事实数)；unification 基于正则；ODAP 已有 pyDatalog + Allen |
| Semantica Polyglot 双存储（RDF + LPG 同时写） | 两套独立客户端、两套查询语言，无统一事务；双真相源，违反单一真相源与禁双写 |
| Semantica 与 Graphiti 共享 Neo4j | 两套时间语义不可调和（Graphiti 双时态 vs Semantica 无 `valid_at`），无法判定真相 |
| Semantica 整包引入 | 62 extras / 512 MB / `reasoning` 导入 963 ms / 零 async；供应链 #2135 有 8 个高危 CVE |
| TrustGraph Cassandra/Pulsar/Qdrant 重栈 | 与 3–5 人团队、无 SRE、模块化单体约束冲突 |
| TrustGraph UI 作为统一门户 | 第二入口、权限/路由/审计分裂 |
| TrustGraph README 的 action gate / authority 校验 | OSS 源码无实现；当前只有查询期 SHACL-AF 过滤 |
| TrustGraph 替代 Graphiti 双时态 | `Triple` 无 `valid_at/invalid_at`，属数据模型级缺失 |
| TrustGraph "hypergraph" 能力 | 源码只是 reified triple，不是 n 元超边引擎 |
| TrustGraph 企业治理能力 | attestation、企业 IAM、防篡改审计在闭源侧 |
| TrustGraph 作为生产旁车 | 任一环节都需 gateway + flow + 总线 + 图库 + 向量库，12GB/8CPU 起步 |
| LLM 直接创建本体类型 | 违反 ADR-079 理解层"只选不创" |
| "types never gate" | 与 ODAP 治理闸门和 typed 图强不变量冲突 |
| 共享图库跨写 | 外部服务直连 Neo4j 会绕过审计、隔离与写路径不变量 |

---

## 7.4 已落地：P0 三项（2026-10-30）

本节记录「落地报告并执行修改」实际产生的代码变更，与 §7.1 / §7.2 的规划项对应。
**未完成项在 7.4.4 显式列明，不混入已完成清单。**

三项 P0 的共同点：都不引入 TrustGraph / Semantica 任何运行时依赖，改动全部落在
ODAP 现有的治理、摄入、审计三条主链上。

### 7.4.1 质量闸去伪绿（对应 ADR-084 F2/F7，§7.2 S7 的治理前置）

**问题**：22 子指标计算器对 7 个数据子项在缺值/非法值时默认 `1.0`；G2 的
基数/is_a 无环/LLM Judge 是占位满分并计入 gate 均分；SHACL 未接入时按"通过"
处理。结果是「没有数据」被算成「满分」，KPI 伪绿。

**改动**

| 文件 | 变更 |
|---|---|
| `apps/api/odap/biz/semantic_admin/quality_gate/services/quality_calculator.py` | 6 个数据子项（fill_rate / empty_rate / orphan_ratio / dangling_relations / invalid_action_targets / invalid_rule_references）缺值或非法值 → `score=0.0, evaluated=False`，`reason` 以 `[未评估]` 开头；`_compute_gate1_score_22` 按 `evaluated=True` 重算分母；`_compute_gate2_score_22` 只对已评估项求均值，空集归零；`_eval_g2_shacl_compliance(candidate, provider)` 支持外部 provider；报告新增 `evaluation_complete` / `not_evaluated_submetrics` |
| `.../quality_gate/services/shacl_compliance.py`（新增） | `compliance_ratio(shapes_ttl, data_ttl)`：按 `sh:targetClass` 求焦点节点集，pyshacl 校验后返回「未违规焦点节点占比」；无形状 / 无焦点节点返回 `None`（交由上层标未评估，不伪造 1.0）。`make_storage_provider(...)` 从 `shacl_store` 取形状 TTL |
| `.../quality_gate/services/__init__.py` | 导出 `compliance_ratio` / `make_storage_provider` |

**语义**：`evaluated=False` 的子项既不打分也不进分母。全部子项未评估时 gate 分诚实
归零——`usl_quality_reports.gate1_score / total_score` 是 `NOT NULL`，无法返回
`None`，因此用「0.0 + `evaluation_complete=false`」表达"没评估过"，避免把契约改空。

**测试**：`tests/unit/biz/semantic_admin/test_quality_gate_not_evaluated_22.py`（新增）
锁定缺字段、占位项不进均分、G1 分母剔除、全未评估归零、provider 优先级与非法值；
`test_quality_calculator_22.py` 中原先编码「缺值=满分」的用例已改写。定向结果 `82 passed`。

### 7.4.2 Ingestor 端口化（对应 §7.2 S1）

**问题**：统一摄入门面用两个 frozenset + 一串 `if source_type == ...` 分派，
支持列表与实际路由可能漂移；没有任何统一的摄入元数据（来源 URI / 内容指纹 /
增量水位），重复摄入无法识别；`_validate_ingest_contract` 与 `validate_entity_type`
在异常时返回「通过」，属于规则 14 明令禁止的静默假成功。

**改动**

| 文件 | 变更 |
|---|---|
| `apps/api/odap/biz/data/ingest/ports/ingestor.py`（新增） | `IngestRequest` / `RawPayload` / `NormalizedDoc` / `IngestorPort` 协议；`SourceCategory` / `ExtractionMode` 迁入并保持旧导入路径兼容；`canonical_text`、`hash_text`（UTF-8 + SHA-256） |
| `apps/api/odap/biz/data/ingest/registry.py`（新增） | `IngestorRegistry`（source_type → 端口，重复注册直接 `ValueError`）；`FacadeIngestor` 两段式适配器（`fetch` 归集来源 URI，`normalize` 计算 `content_hash/bytes_len/watermark`）；`build_source_uri` 显式字段优先，无标识时返回空串（不猜测） |
| `unified_ingest_facade.py` | `ingest()` 改为查表路由，未命中返回 `Unknown source type: X; supported: ...` 且附 `supported_source_types`；`get_supported_source_types()` 由注册表生成；契约校验异常 → 显式 error；`validate_entity_type` 异常 → 抛 `EntityTypeValidationError`（不会再有 `{"valid": True}`） |
| `ingest/api/routes.py` | `UnifiedIngestResponse` 增加 `source_uri` / `content_hash` / `watermark` / `bytes_len` / `mime` / `supported_source_types`，元数据对成功与失败都回传 |

**语义**：成功与失败响应都带 `source_uri + content_hash`，失败时同样能定位"哪一份
输入坏了"；`content_hash` 为规范化文本的 SHA-256，可直接作为去重/幂等键。

**边界**：当前 `fetch` 阶段归集的是**请求侧负载**。对 `url` / `news` 这类由下游
handler 自行抓取的源，`content_hash` 是请求参数指纹，不是抓取后的正文指纹；待该源
实现真实两段式（先取正文再 normalize）后自动变成正文指纹。接口字段描述已写明这一点，
避免消费方误用它做正文去重。

**测试**：`tests/unit/test_ingest_ports.py`（新增，覆盖规范化、注册冲突、未知来源、
契约失败、元数据透传）；`test_unified_ingest_facade.py` 保持全绿；两份摄入集成
测试 `76 passed`。定向结果 `50 passed`。

### 7.4.3 PROV 完整性（对应 §7.2 S7，Semantica #2136 为反面教材）

**问题**：PROV-O 只能导出三元组，不能证明审计记录未被改；仓库内
`HashChainV2.compute_hash` 使用 `f"{a}|{b}|..."` 拼接——正是 #2136 的碰撞形态：
`("a|b","c")` 与 `("a","b|c")` 序列化后完全相同，两批不同事件得到同一摘要；
`verify_chain` 只比对链接字段，不复算内容，改一条记录不会被发现。

**改动**

| 文件 | 变更 |
|---|---|
| `infra/security/provenance/integrity.py`（新增） | `canonical_bytes`（键排序 + 紧凑分隔符 + UTF-8 + datetime→ISO）、`event_digest`（剔除派生字段）、`chain_digest` / `collection_digest`（**8 字节大端长度前缀**，编码单射）、`GENESIS_DIGEST` |
| `.../provenance/chain_store.py`（新增） | `ProvenanceChainStore`：追加式 SQLite 链表（`event_id` 唯一、不覆盖）；`seal()` 单事务追加并跳过已封存；`verify()` 复算每条事件的内容指纹并逐节校验 `prev_digest` 与 `chain_hash`；结果区分 `tampered` / `broken_chain` / `unsealed` / `empty_window` |
| `.../provenance/audit_exporter.py` | 每条 Activity 附 `odap:sha256`；新增 `prov:Collection` 清单节点（`odap:sha256` 聚合指纹 + `odap:memberCount` + `odap:partOfExport` 成员关系）；CSV 增加 `event_digest` 列；宾语类型判定由 `endswith` 猜测改为显式谓词集合 |
| `.../provenance/provenance_routes.py` | 新增 `POST /api/audit/provenance/seal`（显式写）、`GET /api/audit/provenance/verify`（只读复算） |
| `infra/security/audit_logger_v2.py` | `HashChainV2.compute_hash` 改用 `event_digest + chain_digest`，消除分隔符拼接碰撞 |

**语义**：`valid=true` 只在「窗口内全部已封存 + 内容指纹一致 + 链路自洽」时成立；
未封存、空窗口都不算通过。封存是显式 POST，GET 不产生副作用。

**测试**：`tests/unit/test_prov_integrity.py`（新增）含 #2136 碰撞复现与反证
（旧拼接确实碰撞、新编码不碰撞）、时序排序、重复封存跳过、内容篡改、链哈希改写、
中段删除、空窗口、导出清单三元组与路由透传。审计/溯源相邻套件 `129 passed`。

### 7.4.4 已落地 vs 未落地

| 项 | 状态 |
|---|---|
| T1 场景级知识快照 / T3 SHACL-AF 查询期策略过滤 | **未开始**（仍建议作为下一批） |
| S1 多源 ingestor 逐个补齐 | **只落了端口与注册表**，未新增具体数据源实现（当前 15 类仍由既有 handler 承接） |
| S2 22 类 chunker / S3 Pipeline DSL / S4 两阶段 ER | **未开始** |
| 质量闸 22 子指标接入服务层 | **未完成**：`QualityGateService` 仍调用 16 子指标的 `evaluate_candidate`；切到 `evaluate_candidate_22` 需同步报告字段与前端消费方 |
| SHACL 合规率覆盖率 | `compliance_ratio` 仅支持 `sh:targetClass` 焦点节点，未覆盖 `sh:targetNode` / `sh:sparql` |
| 溯源链自动封存 | 当前为显式 POST；若要在写入路径内自动封存，会牺牲"零侵入"，需单独评审 |

**文档同步**：新增路由已登记到 `agents.md` 附录 E；本次未新增业务模块目录，故
`docs/03-modules/README.md` 无需变更。

---

## 8. 可持续迭代的整合机制

### 8.1 上游跟踪（每季度）

- **版本与破坏性变更**：订阅 release notes；对 `CapabilityDescriptor.version` 做 semver 兼容矩阵。TrustGraph 的 GitHub Releases 可能滞后，**以 PyPI 版本为准**。
- **API diff**：对适配器使用的端点抓取响应样本，做 schema diff；破坏性变更必须触发 G2 重跑。
- **供应链**：SBOM、CVE、传递依赖、Python 版本、镜像基座。
- **许可证**：MIT/Apache 兼容性、NOTICE/归属文件、再分发义务。
- **活跃度**：release cadence、issue 响应、维护者数量；连续两个季度无 release 触发降级评估。

### 8.2 契约与测试

| 测试 | 内容 | 通过标准 |
|---|---|---|
| 契约测试 | 用固定响应样本验证 `contracts.py` 反序列化与必填字段 | 100% 通过；字段缺失必须报错 |
| 黄金集回归 | 抽取/切分/ER 的标注集 | 不低于基线；关键类目 ±2% 内 |
| 影子回放 | 只读重放真实流量，不写 canonical | 结果差异可解释；无写入 |
| 隔离测试 | 跨 workspace/scenario 请求 | 100% 拒绝 |
| 故障注入 | 超时、5xx、半开、脏数据 | 显式失败；无静默降级 |
| 性能 | SC-001 ≤3s、SC-002 ≤5s | P95 达标 |

### 8.3 决策门 G0–G4

| 门 | 问题 | 产出 | 不通过后果 |
|---|---|---|---|
| G0 战略契合 | 是否填补已命名缺口？是否新增控制面？ | 能力清单 + 缺口映射 | 直接放弃 |
| G1 许可/安全/依赖 | 许可证、CVE、Python/依赖冲突？ | SBOM + 法务/安全签字 | 放弃或改算法移植 |
| G2 契约/影子 | 契约稳定？影子无回归？ | 契约测试 + 影子报告 | 回到 G0/G1 |
| G3 灰度 | 小流量/小场景可用？可回滚？ | 灰度报告 + kill switch 演练 | 回滚并暂停 |
| G4 GA | SLO、成本、on-call、文档齐备？ | 运维手册 + 成本模型 | 维持灰度或下线 |

### 8.4 Kill criteria（任一触发即下线）

1. 上游连续 2 个季度无 release，或核心维护者流失。
2. 高危 CVE 超过 30 天未修复。
3. 契约破坏性变更且上游拒绝兼容层。
4. 黄金集质量连续 2 个迭代下降超过阈值。
5. 单文档成本超过预算 2 倍且无优化路径。
6. 出现任何双写或跨工作空间数据泄漏。
7. 运维告警月均超过团队承受上限。
8. 关键能力被移入闭源版，或许可证发生不利变更。
9. 出现"假成功"：健康检查恒 200、placeholder 结果被当成功、校验器假通过。
10. 外部写入绕过了 ODAP 的写路径不变量或时间语义。

### 8.5 Semantica 重新评估触发条件（任一满足即重评，**当前 0/7**）

1. 发布 **1.0** 且 changelog 明确"公共 API 冻结"，`__all__` 非空并有 `.pyi`。
2. `graph_store` 支持**非 ASCII 标识符**（或改为参数化 label 白名单映射），且有 i18n 测试。
3. 出现 **workspace/tenant 一级概念**并落到 all stores（代码里的必填参数，不是文档承诺）。
4. 提供 **async 公共 API**（至少 ingest/query 两条路径）。
5. `/build` 与 `/health` 变为真实实现，且 orchestrator 的 `placeholder` 分支被删除。
6. #2136 修复并附**碰撞回归测试**；#2135 安全扫描转绿。
7. 出现**金融/制药/能源强审计行业**的公开生产案例，且披露规模与 SLA。

其中 1/2/3/5 是"能不能用"，4/6/7 是"敢不敢用"。在这些条件满足前，Semantica 只作为能力清单与算法参考源。

### 8.6 所有权与节奏

- 每个适配器**一个 owner**，不允许"孤儿适配器"。
- 每季度一次"继续/降级/移除"评审，输出一页决策记录。
- 适配器数量上限：同时在线不超过 2 个；新适配器必须先下线一个或证明必要性。
- 所有集成决策写入 ADR，遵守规则 12 的文档同步要求。

---

## 9. 路线图

| 阶段 | 时间 | 交付物 | 决策门 | 人周（粗估） |
|---|---|---|---|---|
| Phase 0 | 第 1–2 周 | 《知识交换契约 v0.1》、能力清单、基线指标、黄金集定义 | G0/G1 | 2–3 |
| Phase 1 | 第 3–6 周 | 场景级知识快照（T1）、声明式流水线配置（T2/S1）、质量评估 harness | G2 | 5–7 |
| Phase 2 | 第 7–10 周 | 数据级策略过滤（T3，ODAP 内实现，复用 pyshacl）；TrustGraph **离线对照评测**（compose 跑同批文档/问题，不接生产） | G2/G3 | 4–6 + 评测基础设施 |
| Phase 3 | 第 11–16 周 | Semantica **copy-adapt**：30 个 ingestor 中适配 ODAP 缺的源类型、22 个 chunker 中适配的结构/表格/代码切分；PROV checksum 自建单射实现 + 碰撞负向测试；**不引入运行时依赖** | G1/G2 | 6–9 |
| Phase 4 | 第 17 周起 | GA 或 kill；季度上游评审 | G4 | 2/季度 |

总计约 23–33 人周（6 个月），不含评测基础设施采购与安全评审。**若只能做一件事**：做 Phase 1 的 T1（知识快照）+ T2/S1（声明式流水线）。这两项不引入外部依赖，直接改善可复现性与可维护性，且为后续任何集成提供基线；T3（数据级策略过滤）可作为紧接的第二项。

### 9.1 需要业务方拍板的点（非技术）

1. 是否允许将脱敏样本用于 TrustGraph **离线对照评测**（不接生产链路）？
2. 是否接受 Phase 3 对 ingestor/chunker 做 copy-adapt 后的**长期维护成本**（上游季度 MAJOR 会带来回归）？
3. 是否接受为一次性评测环境投入 12GB/8CPU 的资源与运维时间？
4. 质量与成本的优先级：当外部能力提升 3% 质量但增加 30% 成本时，是否采纳？

---

## 10. 风险登记册

| # | 风险 | 触发信号 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 上游 API 漂移 | TrustGraph 主版本跳跃、Semantica pre-1.0 | 适配器频繁破裂 | 锁版本、契约测试、G2 影子回放 |
| R2 | 依赖/运行时冲突 | 62 组 extras、512 MB 安装、`reasoning` 导入 963 ms、零 async | 构建矩阵扩大、镜像膨胀、事件循环阻塞 | copy-adapt 优先；独立 venv/容器；禁止把同步库直接塞进请求主链 |
| R3 | 供应链/CVE | 传递依赖含已知漏洞 | 安全评审不通过 | SBOM、镜像扫描、季度升级 |
| R4 | 双写/真相源分裂 | 外部服务直连图库 | 审计失真、决策不可复现 | 网络隔离、只读凭据、写路径代理 |
| R5 | 运维复杂度 | Cassandra/Pulsar 故障 | 可用性下降 | 不部署生产；仅离线评测；未来若灰度，限定单场景并托管 |
| R6 | 数据驻留/多租户 | 跨 workspace 请求 | 合规事故 | 契约复合主键、隔离测试、ACL 透传 |
| R7 | 质量回归 | 黄金集下降 | 用户不信任 | 基线、灰度、回滚 |
| R8 | 集成焦油坑 | 适配器数量增长 | 维护成本失控 | 上限 2 个、季度下线评审 |
| R9 | 团队带宽 | 3–5 人 | 主线延期 | 限定 Phase、复用现有 provider seam |
| R10 | 上游停更/被收购 | 无 release、许可变更 | 能力不可持续 | kill criteria、算法移植兜底 |
| R11 | 安全边界扩大 | 外部服务可见敏感数据 | 泄漏 | 数据分级、脱敏、最小权限 |
| R12 | "集成即重写" | 需求蔓延到控制面 | 项目失控 | G0 一票否决、控制面不外包 |
| R13 | Open-core 天花板 | 需要密码学证明/企业 IAM/防篡改审计 | 关键合规能力拿不到 | G1 前确认闭源边界；只承诺 PROV-O 级 |
| R14 | 上游叙事超前实现 | README 有 action gate，源码无 | 按文档采购踩空 | 以源码核验为准；G2 前做能力探针 |
| R15 | 文档漂移/破坏性 minor | 资源要求矛盾、容器改名、字段删除、端口变更 | 升级即迁移 | 锁版本、契约测试、升级演练 |
| R16 | 无时序模型 | 需要"某时点事实" | 决策不可复现 | 不替换 Graphiti；只做只读投影 |
| R17 | 资源门槛 | 12GB/8CPU 起步、34 个 processor | 本地/边缘不可用 | 仅离线评测；不进生产 |
| R18 | 非 ASCII 标识符被拒 | Semantica `sanitize_identifier` 只接受 ASCII | 中文业务标签无法写入 LPG | 不引入其 graph_store；自建 label 参数化白名单 + i18n 测试 |
| R19 | 无租户/工作空间 | 全仓无 tenant 概念 | 多租户部署下数据混合 | 不把它作为存储层；只做无状态适配 |
| R20 | 零 async 阻塞事件循环 | 公共 API 全同步 | P95 退化、无法请求级取消 | 不嵌入请求主链；只做离线/批处理 |
| R21 | REST 假健康/假构建 | `/health` 无条件 200、`/build` 桩、placeholder | 故障被当成功，违反规则 14 | 不部署其服务面；以源码核验为准 |
| R22 | PROV 校验假通过 | checksum 非单射、`verify_chain()` 恒过 | 审计存证不可信 | 自建单射 checksum + 碰撞负向测试 |
| R23 | 供应链 CVE | #2135 命中 authlib/litellm/msgpack 高危 | 安全评审不通过 | 不整包引入；copy-adapt 时逐个审依赖 |
| R24 | 上游季度 MAJOR | 0.7.0 已有 4 项破坏性变更 | copy-adapt 后的同步成本 | 锁定参考版本 + 变更日志跟踪 + 季度评审 |

---

## 11. 验收标准

任何外部能力接入，必须同时满足：

1. **契约**：`contracts.py` 全部字段可验证；缺字段/越权/无来源一律拒绝。
2. **单写**：审计日志证明 canonical 图只有 ODAP 写入；外部服务使用只读凭据。
3. **隔离**：跨 workspace/scenario 请求 100% 拒绝。
4. **质量**：黄金集不低于基线；关键类目波动在 ±2% 内。
5. **性能**：SC-001 P95 ≤3s、SC-002 P95 ≤5s（沿用现有性能基准）。
6. **可回滚**：kill switch 演练，回滚 <1 小时。
7. **可观测**：适配器有健康检查、延迟、错误率、成本四项指标。
8. **合规**：许可证与 NOTICE 齐备；SBOM 与 CVE 扫描通过。
9. **文档**：ADR + 模块 DESIGN + 运维手册 + 契约版本矩阵。
10. **成本**：单文档/单查询成本在预算内，且有上限保护。
11. **数据级策略过滤**：Allowed/Filtered/Violation 三态可审计；越权请求默认拒绝；策略变更可重放；不依赖第二个策略引擎。
12. **非 ASCII 标识符**：中文 label/属性名在写入、查询、导出全链路通过；非法标识符必须显式拒绝，不得静默转写。
13. **租户边界**：外部能力不得持有跨 workspace 的持久状态；隔离测试覆盖所有接触面。
14. **异步不阻塞**：接入路径不得阻塞事件循环；同步库必须隔离在批处理线程/进程，并有 P95 回归基线。
15. **存证真实性**：PROV checksum 碰撞用例必须失败；篡改后 `verify_chain` 必须报错；禁止"校验恒通过"的实现进入主链。

---

## 12. 来源与证据边界

### 12.1 外部主源（访问日期 2026-10-28）

| 来源 | 用途 | 链接 |
|---|---|---|
| TrustGraph README | 定位、架构、存储、LLM、许可 | https://github.com/trustgraph-ai/trustgraph |
| TrustGraph README（CDN 镜像） | 同上，实际抓取源 | https://cdn.jsdelivr.net/gh/trustgraph-ai/trustgraph@master/README.md |
| TrustGraph `trustgraph-base/pyproject.toml` | Python 版本、依赖 | https://cdn.jsdelivr.net/gh/trustgraph-ai/trustgraph@master/trustgraph-base/pyproject.toml |
| TrustGraph API 文档目录 | REST/WebSocket/Pulsar/Agent/GraphRAG | https://github.com/trustgraph-ai/trustgraph/tree/master/docs/apis |
| TrustGraph 版本元数据 | 版本范围 0.21.14–2.11.1 | https://data.jsdelivr.com/v1/packages/gh/trustgraph-ai/trustgraph |
| TrustGraph 仓库树 | 模块结构、tests、容器 | https://data.jsdelivr.com/v1/packages/gh/trustgraph-ai/trustgraph@master?structure=flat |
| Semantica README | 定位、模块、许可、能力 | https://github.com/semantica-agi/semantica |
| Semantica PyPI 元数据 | **0.7.0**（2026-09-22）、25 个 release、依赖与 Python 约束 | https://pypi.org/pypi/semantica/json |
| Semantica `pyproject.toml`（0.7.0 tag） | 22 核心依赖、62 extras、`>=3.10,<3.14` | https://github.com/semantica-agi/semantica/blob/v0.7.0/pyproject.toml |
| Semantica `pyproject.toml`（main） | 0.8.0 未发布、`>=3.11`（升级路径） | https://cdn.jsdelivr.net/gh/semantica-agi/semantica@main/pyproject.toml |
| Semantica issue #2136 | PROV checksum 非单射、`verify_chain()` 假通过 | https://github.com/semantica-agi/semantica/issues/2136 |
| Semantica issue #2135 | 安全扫描失败：authlib/litellm/msgpack 高危 CVE | https://github.com/semantica-agi/semantica/issues/2135 |
| Semantica 文档站 | governance/versioning、能力矩阵 | https://docs.getsemantica.ai/llms.txt |
| Semantica 定价/开源模式 | Free(MIT)/Paid Pilot/Enterprise "In Development" | https://getsemantica.ai/pricing |
| Semantica 主源深调（本地） | 0.7.0 wheel 级核验、硬阻断、PROV 缺陷、0/7 触发条件 | [`RESEARCH_SEMANTICA_SOURCES_2026-10-28.md`](RESEARCH_SEMANTICA_SOURCES_2026-10-28.md) |
| TrustGraph 主源深调（本地） | 源码级核验、文档漂移、版本/社区/部署 | [`RESEARCH_TRUSTGRAPH_SOURCES_2026-10-28.md`](RESEARCH_TRUSTGRAPH_SOURCES_2026-10-28.md) |
| TrustGraph PyPI 元数据 | 2.11.1、559 个版本、发布节奏 | https://pypi.org/pypi/trustgraph/json |
| TrustGraph 策略过滤文档 | SHACL-AF 查询期过滤、三态、UserContext | https://docs.trustgraph.ai/guides/policy-filtering/ |
| TrustGraph 存储/可解释性 | 三命名图、PROV-O、检索轨迹 | https://docs.trustgraph.ai/architecture/storage.html · https://docs.trustgraph.ai/architecture/explainability.html |
| TrustGraph changelog | 破坏性 minor、容器改名、端口变更 | https://docs.trustgraph.ai/changelog/trustgraph.html |
| TrustGraph 安全/开源模式 | 3 角色 RBAC、企业 IAM、attestation 闭源 | https://docs.trustgraph.ai/architecture/security.html · https://docs.trustgraph.ai/learn/open-source.html |
| TrustGraph MCP 包 | 31 个工具、HTTP + Bearer | https://pypi.org/project/trustgraph-mcp/ |

### 12.2 仓库内主源

| 文档/代码 | 用途 |
|---|---|
| `docs/02-architecture/ARCHITECTURE.md` | ODAP v7.0.0 架构、T1–T8 |
| `docs/02-architecture/ARCHITECTURE_TARGET_PLAN.md` | Semantica 能力吸收 v1.1 与实施状态 |
| `docs/02-architecture/reports/RESEARCH_SEMANTICA_COMPARISON_2026-08-14.md` | 上一轮 Semantica v0.6.5 评估基线 |
| `docs/02-architecture/reports/RESEARCH_TRUSTGRAPH_SOURCES_2026-10-28.md` | TrustGraph 源码级主源调研（PyPI sdist、文档站、changelog） |
| `docs/02-architecture/reports/RESEARCH_SEMANTICA_SOURCES_2026-10-28.md` | Semantica 0.7.0 wheel 级主源调研（版本、体积、硬阻断、PROV 缺陷、触发条件） |
| `docs/07-adr/ADR-046_modular_monolith_deployment.md` | 3–5 人团队、无 SRE、模块化单体 |
| `docs/07-adr/ADR-063_tenant_aware_isolation.md` | 租户隔离现状 |
| `docs/07-adr/ADR-075_确定性推理引擎引入.md` | pyDatalog + Allen；不参考 Semantica Rete |
| `docs/07-adr/ADR-076_决策智能架构_决策作为一等公民对象.md` | 决策端点、因果边、规则门禁 |
| `docs/07-adr/ADR-077_SHACL_OWL本体治理.md` | SHACL/OWL 双轨 |
| `docs/07-adr/ADR-079_本体论与LLM结合边界.md` | 三层 LLM 治理 |
| `docs/07-adr/ADR-081_infra依赖倒置provider注册表.md` | `register_provider` / `resolve_provider` seam |
| `docs/07-adr/ADR-084_open_typed双层事实模型与写路径不变量.md` | F1/F2/F3/F7 缺口 |
| `apps/api/odap/web/router_registry.py` | 104 个 API 前缀统一注册 |
| `apps/api/odap/infra/providers.py` | provider 注册表实现 |
| `apps/api/odap/biz/providers_bootstrap.py` | biz 侧工厂注册 |
| `apps/api/odap/biz/core/ontology/semantic_retrieval/api/routes.py` | 多模式检索与查询审计 |
| `apps/api/odap/biz/decision/decision_record/api/routes.py` | 决策端点与工作空间校验 |

### 12.3 证据局限

1. **TrustGraph 已做源码级核验，但未部署运行**：主源调研基于 PyPI sdist 2.11.1（`trustgraph-flow` 57k 行、`trustgraph-base` 26k 行），未启动完整五件套，未复现官方 benchmark。
2. **Semantica 已做 0.7.0 wheel 级核验，但未逐个运行连接器**：版本、依赖、安装体积、导入耗时、`sanitize_identifier`、PROV 缺陷、REST 桩均已按源码/实测确认；**30 个 ingestor 与 22 个 chunker 未逐个执行**，其重试/限流/增量水位语义与质量未核实。
3. **文档覆盖不对称**：TrustGraph 文档站已读架构/存储/检索/安全/策略/部署/changelog；Semantica 文档站仅读索引页与治理/定价页，Explorer 的 83 条路由与鉴权未审计。
4. **测试观察**：Semantica 有 81 个测试文件 / 2,117 个 `def test_`，但**无 rete/reasoning/decision/ontology 专项**；测试数量不等于覆盖，不能据此推断核心能力可靠。
5. **社区数据**：两者均有 star/fork/contributor/issue 数据；Semantica 14,276 stars / 134 contributors，TrustGraph 2.8k stars / 29 contributors；star 数不构成交付深度证据。
6. **商业条款**：TrustGraph 企业版价格、SLA、闭源能力清单未核实；Semantica 企业版标注 "In Development"，核心团队规模与资助方未核实。
7. **评分为判断**：§3 的 1–5 分是架构覆盖度判断，不是基准分数；不得用于对外宣传。

---

## 附录 A：评分口径

| 分值 | 含义 |
|:--:|---|
| 1 | 该维度基本缺失，或只有名词没有可用实现 |
| 2 | 有概念/原型，但不足以支撑生产 |
| 3 | 可用，但需要大量补齐或强约束 |
| 4 | 覆盖主要生产场景，有明确边界 |
| 5 | 该维度具备独有深度，可作为平台差异化能力 |

## 附录 B：术语对照

| 术语 | 含义 | 在本报告中的意义 |
|---|---|---|
| Episode | Graphiti 的叙事单元，带双时态 | ODAP 的事实真相源粒度 |
| Quad / 命名图 | RDF 四元组与图归属 | TrustGraph 的事实粒度，利于事实级溯源 |
| LPG | 属性图（节点/边/属性） | Neo4j/Graphiti 的存储形态 |
| USL | 统一语义层，术语/层级/属性/不相交/基数 | ODAP 语义治理的核心资产 |
| OL Pipeline | 本体学习六层流水线 | ODAP 从候选到写回的治理链 |
| PROV-O | W3C 溯源本体 | 审计与证据链的标准表达 |
| KEC | 本报告定义的 Knowledge Exchange Contract | 控制面与能力提供者的唯一接口 |
| 旁车（sidecar） | 独立部署、通过 API 接入的辅助服务 | 本报告不推荐生产旁车；仅离线评测/只读互操作 |
| 窄库（narrow library） | 只取单个模块/算法，不做整包依赖 | 不作首选；Semantica 有四项硬阻断与 62 extras |
