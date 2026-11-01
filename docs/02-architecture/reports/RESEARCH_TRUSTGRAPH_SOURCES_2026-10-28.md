---
id: odap.l2.reports-research-trustgraph-sources-2026-10-28
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

# 技术调研报告：TrustGraph 主源调研（截至 2026-10-28）

> **调研对象**：[trustgraph-ai/trustgraph](https://github.com/trustgraph-ai/trustgraph)（Apache-2.0，PyPI `trustgraph` 2.11.1）
> **调研目的**：评估其作为 ODAP（本体驱动分析决策平台）的**整体底座 / 环节替换 / 设计借鉴**三种候选角色的可行性
> **调研方法**：只取主源——PyPI sdist 源码（2.11.1，含 `trustgraph-flow` 408 个 `.py` / 57,090 行、`trustgraph-base` 154 个 `.py` / 26,117 行）、官方文档站（docs.trustgraph.ai，含 1,914 条搜索索引）、GitHub 仓库 raw 文件（LICENSE/README/tech-specs/workflow）、npm registry、shields.io（GitHub API 只读代理）
> **可达性说明**：`github.com` / `api.github.com` / `trustgraph.ai` 在本调研环境直连不可达；GitHub raw 文件经 `ghproxy.net` 镜像读取，仓库元数据经 shields.io 读取；营销站无法访问，相关结论一律不外推
> **作者**：AI 架构调研

---

## 0. 证据分级（结论可信度前提）

| 级别 | 来源 | 本次使用情况 |
|---|---|---|
| A 源码 | PyPI sdist 解包后的 Python 源码 | `trustgraph-flow` 2.11.1、`trustgraph-base` 2.11.1、`trustgraph-mcp` 2.11.1 |
| A 仓库文件 | GitHub raw（LICENSE、README、SECURITY.md、`docs/tech-specs/*.md`、`.github/workflows/release.yaml`） | 已读取 |
| A 文档 | docs.trustgraph.ai 官方文档 + changelog | 已读取架构/存储/检索/可解释性/工作空间/安全/部署/API/变更日志 |
| B 包元数据 | PyPI JSON API、npm registry、shields.io | 版本、发布节奏、许可证徽章、star/fork/贡献者 |
| C 未核实 | 营销站客户案例、Discord 讨论、issue 正文 | 不可达，明确标"未核实" |

**方法学提醒**：本报告区分"文档声称"与"源码可验证"。凡二者冲突处单独标注——TrustGraph 的文档漂移率较高（见 §6.5）。

---

## 1. 项目定位与目标用户

### 1.1 自述定位：2026 年内发生过一次口径切换

| 时点 | 口径 | 来源 |
|---|---|---|
| 2026 上半年（文档站仍沿用） | "open-source **context orchestration layer**"，"context hypergraph + 三种 RAG" | [what-is-trustgraph](https://docs.trustgraph.ai/learn/what-is-trustgraph.html)、[how-it-works](https://docs.trustgraph.ai/learn/how-it-works.html) |
| 2026-10（master README） | "**The Semantic Agent Governance Platform**"——"ontology-grounded operating graph connected to a **policy runtime that governs what AI agents can do**"，"Agents propose actions. TrustGraph checks them against business meaning, authority, and evidence before execution" | [README](https://github.com/trustgraph-ai/trustgraph/blob/master/README.md) |

这条切换极其关键：README 的新定位（面向 Agent 动作的语义治理 + 决策留存 + PROV-O 溯源）与 ODAP 的"本体驱动分析决策"几乎正面相撞；但**源码层面尚未落地"动作治理"**（见 §4 第 12 行、§6.6）。

### 1.2 与"企业知识智能底座 / 上下文图谱 / Agent 平台"的关系

- 自我归类为**知识与 Agent 的基质（substrate）**，而非单体应用："a knowledge and agent substrate that sits alongside your existing data sources and LLM providers — not a monolithic application"（[architecture](https://docs.trustgraph.ai/architecture/architecture.html)）。
- 三层价值主张：**结构化上下文**（实体/关系而非文本块）→ **可解释检索**（每条边为何被选中）→ **可追溯来源**（PROV-O）（[explainability](https://docs.trustgraph.ai/architecture/explainability.html)）。
- 对"上下文图谱"的定义优于业内常见用法：knowledge graph 记"知道什么"，context graph 记"知识 + 来源 + 既往推理"（[retrieval](https://docs.trustgraph.ai/architecture/retrieval.html)）。这与 ODAP 的 PROV-O + 审计导出方向同构。

### 1.3 目标用户

企业知识运营、安全运营/合规、金融与战略研究、**做多租户 SaaS 的厂商**（把 TrustGraph 当知识层嵌入自有产品）（[use-cases](https://docs.trustgraph.ai/learn/use-cases.html)）。
工程侧画像：愿意自托管整套消息总线 + 列存 + 向量库、能接受 YAML/CLI 驱动、有 K8s 能力的平台团队。

---

## 2. 许可证、版本、发布节奏、活跃度、生产可用性

### 2.1 许可证与治理模式

| 项 | 事实 | 证据 |
|---|---|---|
| 主许可证 | **Apache-2.0**（LICENSE 全文 203 行，标准 Apache 头） | [LICENSE](https://github.com/trustgraph-ai/trustgraph/blob/master/LICENSE)、[shields license badge](https://img.shields.io/github/license/trustgraph-ai/trustgraph) 返回 `Apache-2.0` |
| 专利授权/商标 | Apache-2.0 含专利授权条款；商标未单独声明 | LICENSE 原文 |
| 开源模式 | **Open-core**：OSS 版含全部检索/抽取/Agent/基础 RBAC；**Enterprise 另售** 精细 RBAC、**attestation engine（推理的密码学证明）**、SLA、培训 | [learn/open-source](https://docs.trustgraph.ai/learn/open-source.html)、[security](https://docs.trustgraph.ai/architecture/security.html) |
| 商业实体 | 企业支持由 **Knownext Inc.** 提供 | [help-and-resources](https://docs.trustgraph.ai/contributing/help-and-resources.html) |
| 安全策略 | 仅最新 stable 线获补丁；< 2.0.0 EOL；漏洞走邮件而非公开 issue | [SECURITY.md](https://github.com/trustgraph-ai/trustgraph/blob/master/SECURITY.md) |

**判断**：许可证本身干净（Apache-2.0，无 BSL/SSPL 类限制），但**治理类能力（密码学证明、企业 IAM、防篡改审计）在闭源侧**，若 ODAP 需要"可验证推理"，OSS 版拿不到。

### 2.2 版本与发布节奏

| 指标 | 数值 | 证据 |
|---|---|---|
| 当前版本 | **2.11.1**（2026-10-27 发布） | [PyPI trustgraph](https://pypi.org/pypi/trustgraph/json) |
| 历史发布数 | **559 个**（首个 0.11.20，2024-10-04） | 同上 |
| 近期节奏 | 2.10.10→2.11.1 共 11 个版本集中在 2026-10-07 ~ 10-27（**近乎每周多次**） | 同上 |
| 主版本节奏 | v2.8（2026-08-24）、v2.9（2026-09-16）、v2.10（2026-10-25）——约**月度** minor | [changelog](https://docs.trustgraph.ai/changelog/trustgraph.html) |
| 发布自动化 | tag `v*` 触发 CI → PyPI + 容器镜像 | [release.yaml](https://github.com/trustgraph-ai/trustgraph/blob/master/.github/workflows/release.yaml) |
| 版本一致性 | 包与容器同号；官方要求"容器与包版本号匹配" | [containers](https://docs.trustgraph.ai/reference/containers.html) |

**风险信号**：**minor 版本承载破坏性变更**（v2.9 移除 langchain + 删除 `trustgraph-unstructured`；v2.10 重命名容器 `trustgraph-hf`→`trustgraph-torch`、删除 `Triple.o_datatype/o_language` 字段），不符合语义化版本对 minor 的常规预期（[changelog](https://docs.trustgraph.ai/changelog/trustgraph.html)）。

### 2.3 社区活跃度（2026-10-28 读取）

| 指标 | 数值 | 证据 |
|---|---|---|
| Stars | **2.8k** | [shields stars](https://img.shields.io/github/stars/trustgraph-ai/trustgraph.json) |
| Forks | 337 | [shields forks](https://img.shields.io/github/forks/trustgraph-ai/trustgraph.json) |
| Contributors | **29** | [shields contributors](https://img.shields.io/github/contributors/trustgraph-ai/trustgraph.json) |
| 提交频率 | 42 次/月；最后提交"昨天" | [commit activity](https://img.shields.io/github/commit-activity/m/trustgraph-ai/trustgraph.json) |
| Open issues | 17 | [shields issues](https://img.shields.io/github/issues/trustgraph-ai/trustgraph.json) |
| 仓库体积 | 101.7 MiB | [repo size](https://img.shields.io/github/repo-size/trustgraph-ai/trustgraph.json) |
| GitHub Releases | 最新标记 **v2.8.17**，明显落后 PyPI 2.11.1 | [shields release](https://img.shields.io/github/v/release/trustgraph-ai/trustgraph.json) |

**解读**：2.8k star / 29 贡献者 ≈ **核心小团队 + 少量外部贡献**；issue 存量低（17）可能是团队响应快，也可能是外部使用面窄——二者本报告无法区分（issue 正文不可达）。GitHub Releases 未随 tag 更新，**版本真值以 PyPI 为准**。

### 2.4 生产可用性证据

**支持面（有据）**：
- 8 份云/自托管部署指南：AWS EC2/RKE、Azure AKS、GCP GKE、OVHcloud、Scaleway、Minikube、Intel Gaudi、compose（[choosing-deployment](https://docs.trustgraph.ai/deployment/choosing-deployment.html)）。
- 基础设施即代码用 Pulumi，且**在 CI 中对部署配置做安全测试**（[security](https://docs.trustgraph.ai/architecture/security.html)）。
- 运维栈内置：Prometheus 指标（`tg_` 前缀）、Grafana + Loki（[architecture](https://docs.trustgraph.ai/architecture/architecture.html)、[v2.8 changelog](https://docs.trustgraph.ai/changelog/trustgraph.html)）。
- 官方 benchmark 页给出可复现的摄取吞吐（Gaudi2 8 卡 Llama-3.3-70B：总 3,039.5 tok/s，8.5 分钟处理一份标准文档）（[benchmarks](https://docs.trustgraph.ai/benchmarks.html)）。

**反对面（同样有据）**：
- **生产运维指南是空壳**："Production Considerations" 全页为 "Coming soon - detailed content!"，且页首自述"This page is currently a placeholder"（[production-considerations](https://docs.trustgraph.ai/deployment/production-considerations.html)）。
- **公开客户案例为零**：use-cases 页只有场景描述，无客户名/数据（[use-cases](https://docs.trustgraph.ai/learn/use-cases.html)）。
- **文档漂移严重**（详见 §6.5），影响"按文档可运维"的可信度。

**结论**：**"可跑起来"的证据充分，"长期稳定运维"的证据不足**。定位为"可评估 / 可试点"，不宜直接承载关键生产链路。

---

## 3. 架构与组件

### 3.1 服务模型：processor / flow / blueprint 三级

```
客户端 ──REST /api/v1/{kind}──┐
        ──WS  /api/v1/socket──┤
                              ▼
                       api-gateway (8888)
                              │  Pulsar / RabbitMQ / Kafka（v2.8+）
        ┌─────────────────────┼──────────────────────┐
   pdf-decoder → chunker → kg-extract-relationships → triples-write
   graph-rag → prompt → text-completion
        └─────────────────────┴──────────────────────┘
   存储：Cassandra(图/行/元数据) · Qdrant(向量) · Garage(S3 对象) · PROV 命名图
```

- **Processor**：单一职责服务，只经消息总线通信；**Flow** = 运行中的流水线；**Flow Blueprint** = 可复用模板（[architecture](https://docs.trustgraph.ai/architecture/architecture.html)）。
- 规模实测：启动后 **34 个 processor、9 个 flow class、16 个 prompt**（[quickstart/launch](https://docs.trustgraph.ai/quickstart/launch.html)）。
- 消息总线：Pulsar 为默认；**v2.8 起官方支持 RabbitMQ（aio-pika）与 Kafka（aiokafka）**，`trustgraph-base` 依赖同时含 `pulsar-client`/`pika`/`aio-pika`/`confluent-kafka`/`aiokafka`（[trustgraph-base pyproject](https://pypi.org/pypi/trustgraph-base/json)、[v2.8 changelog](https://docs.trustgraph.ai/changelog/trustgraph.html)）。
- 网关内部有 **47 个 dispatch 模块**（agent/graph_rag/document_rag/triples/sparql/rows/structured/mcp_tool/reranker/decision_scoring/cloze…），经统一 `kind` 路由分发（源码 `trustgraph/gateway/dispatch/manager.py`）。

### 3.2 数据模型与存储

| 层 | 实现 | 证据 |
|---|---|---|
| 图 | **RDF 三元组 (s,p,o,**g**)**，`g` 为命名图 IRI；Literal 带 `datatype`/`language` | 源码 `trustgraph_base-2.11.1/trustgraph/schema/triples.py` |
| 命名图 | 三个：默认图（知识）、`urn:graph:source`（PROV-O 抽取血缘）、`urn:graph:retrieval`（检索推理轨迹） | [storage](https://docs.trustgraph.ai/architecture/storage.html)、[explainability](https://docs.trustgraph.ai/architecture/explainability.html) |
| 图后端 | Cassandra（默认，实体中心分区表）、Neo4j、Memgraph、FalkorDB | [architecture](https://docs.trustgraph.ai/architecture/architecture.html)、源码 `pyproject.toml` scripts |
| 向量 | Qdrant（默认）、Milvus、Pinecone、FAISS | 同上 |
| 结构/行 | Cassandra 结构表 + **GraphQL（Strawberry）**按 RowSchema 动态生成 schema | 源码 `trustgraph/query/graphql/schema.py` |
| 对象 | Garage（S3 兼容），`librarian` 管生命周期/分片上传 | [storage](https://docs.trustgraph.ai/architecture/storage.html) |
| 时序/版本 | **无**：`Triple` 无 `valid_at/invalid_at`，全仓 grep 无 `valid_at`/`bitemporal` | 源码 `schema/triples.py`；`grep -ri "valid_at\|bitemporal"` 为空 |

**"hypergraph" 口径校正**：README 称"RDF 1.2 named graphs with **reification** … enabling n-ary relationships"；源码中 reification 仅指**把三元组作为被引用的嵌套项**（`TRIPLE ("t")` 类型，用于血缘边），并非通用 n 元超边（源码 `storage/triples/cassandra/write.py:81`、`query/triples/cassandra/service.py:126`）。**能力实质是 quad + 具体化，不是超图引擎**。

### 3.3 部署形态与资源门槛

| 形态 | 要求/工具 | 证据 |
|---|---|---|
| Docker/Podman compose | **12GB+ RAM / 8 CPU**（[compose 页](https://docs.trustgraph.ai/deployment/compose.html)）；[choosing-deployment 页](https://docs.trustgraph.ai/deployment/choosing-deployment.html) 却写 8GB/4 核 → **官方自相矛盾** | 两页对比 |
| Minikube | 16GB / 8 核 / 50GB 盘 | [choosing-deployment](https://docs.trustgraph.ai/deployment/choosing-deployment.html) |
| 生产 K8s | Pulumi 生成清单（AWS RKE2 / AKS / GKE / OVH / Scaleway） | 同页 + [architecture](https://docs.trustgraph.ai/architecture/architecture.html) |
| 配置生成 | `npx @trustgraph/config` → `deploy.zip`（compose 或 K8s `resources.yaml`）+ INSTALLATION.md | [README](https://github.com/trustgraph-ai/trustgraph/blob/master/README.md) |
| 容器镜像 | 8 个：base / flow / mcp / hf(torch) / unstructured / ocr / bedrock / vertexai（Docker Hub `trustgraph/*`） | [containers](https://docs.trustgraph.ai/reference/containers.html) |
| 启动耗时 | 40–120s 稳定；健康检查 8 项 | [quickstart/launch](https://docs.trustgraph.ai/quickstart/launch.html) |

### 3.4 代码规模

`trustgraph-flow` 57,090 行 / 408 文件；`trustgraph-base`（schema + 消息原语）26,117 行 / 154 文件（sdist 统计）。体量与 ODAP 后端同量级，但**分布形态相反**：TrustGraph 是"多进程 + 消息总线"，ODAP 是"单 FastAPI 进程 + 模块分层"。

---

## 4. 能力 — 成熟度 — 证据

成熟度判定口径：**GA** = 有独立文档 + 有 CLI/SDK + 有 changelog 迭代记录；**Beta** = 可用但文档标"needs work"/刚发布 ≤1 个 minor；**实验** = 源码存在但无入口/无文档。

| # | 能力 | 判定 | 证据 |
|---|---|---|---|
| 1 | 文档摄取：PDF（pypdf）、OCR（Tesseract）、**Docling**（DOCX/XLSX/PPTX/HTML/MD/CSV）、图片转文（OpenAI vision）、Mistral OCR | **GA** | 源码 `decoding/pdf`、`decoding/mistral_ocr`、`model/image_to_text/openai`；[v2.8 changelog](https://docs.trustgraph.ai/changelog/trustgraph.html) |
| 2 | LLM 知识抽取（relationships / definitions / rows / agent 模式） | **GA**，强依赖 LLM | `pyproject.toml` 入口 `kg-extract-*`；[retrieval](https://docs.trustgraph.ai/architecture/retrieval.html) |
| 3 | 本体管理（**BYOO**，OWL 导入；Ontology RAG 抽取引导；Workbench 支持 OWL/XML + Turtle 双向导入导出） | **GA**（引导抽取）/ **Beta**（往返保真、循环依赖检测仅 UI 层） | [learn/ontologies](https://docs.trustgraph.ai/learn/ontologies.html)、[README](https://github.com/trustgraph-ai/trustgraph/blob/master/README.md)；源码 `extract/kg/ontology/*` |
| 4 | OWL 推理（类层次、属性约束、逻辑推断） | **实验/未实现**：仅有 `subClassOf` 祖先遍历用于本体子集选择，无 DL reasoner | 源码 `ontology_loader.py:109`、`grep -r "reasoner"` 为空；README 的"logical inference"**未在代码中兑现** |
| 5 | SHACL：**写路径校验** | **未实现**（无 pyshacl/校验器） | 全仓 grep `shacl` 仅命中 `policy/policy_filter.py` |
| 6 | SHACL-AF：**查询期策略过滤**（按 user_context 屏蔽节点；三态 Allowed/Filtered/Violation；覆盖 SPARQL/GraphRAG/DocRAG/Agent） | **GA 但 3 天新**（v2.10，2026-10-25） | [policy-filtering](https://docs.trustgraph.ai/guides/policy-filtering/)、[tech-spec](https://github.com/trustgraph-ai/trustgraph/blob/master/docs/tech-specs/policy-filtering.md)、[changelog v2.10 #1141-#1151](https://docs.trustgraph.ai/changelog/trustgraph.html) |
| 7 | SPARQL 1.1 查询 | **Beta**：自研 parser + 内存 join/algebra，非成熟引擎；无属性路径全支持证据 | 源码 `query/sparql/{parser,algebra}.py`；[REST doc](https://docs.trustgraph.ai/reference/apis/rest.html) 声称 SPARQL 1.1 |
| 8 | GraphQL | **GA（仅结构化行数据）**，不覆盖图 | 源码 `query/graphql/schema.py` |
| 9 | Cypher / NL→Cypher | **实验（休眠）**：`query/ontology/` 16 个文件（含 cypher_generator/sparql_generator/question_analyzer）**无任何入口点、无外部 import** | 源码目录 + `pyproject.toml` 无对应 script |
| 10 | 向量检索 / GraphRAG / 多跳 | **GA**：概念抽取→实体向量召回→子图批量遍历→语义预过滤→LLM 边打分→边推理→源文档回溯源；**v2.8 起 BM25+向量 RRF 混合检索** | [retrieval](https://docs.trustgraph.ai/architecture/retrieval.html)、[v2.8 #1030](https://docs.trustgraph.ai/changelog/trustgraph.html) |
| 11 | Agent 编排：ReAct + `plan-then-execute` + `supervisor`（并行子 agent）+ meta-router 自选模式 | **GA** | [agent-patterns](https://docs.trustgraph.ai/reference/configuration/agent-patterns)、源码 `agent/{react,orchestrator}` |
| 12 | Agent 动作治理（"checks actions against authority/risk/value before execution"） | **未实现**：全仓无 action gate / authority 校验引擎；authority 仅出现在 IAM 注释 | `grep -rni "propose_action\|action_gate"` 为空；对照 [README](https://github.com/trustgraph-ai/trustgraph/blob/master/README.md) |
| 13 | MCP：**客户端**（ReAct agent 调外部 MCP 工具，streamable HTTP） | **GA（自评 Beta）**：文档自述"production deployment and authentication may not be ready" | [mcp-integration](https://docs.trustgraph.ai/guides/mcp-integration/)、源码 `agent/mcp_tool/service.py` |
| 14 | MCP：**服务端**（把 TrustGraph 暴露给外部 Agent） | **GA**：`trustgraph-mcp` 2.11.1，HTTP + Bearer + OAuth metadata，**31 个工具**（graph-rag/sparql/graphql/triples/agent/config/flows/documents/knowledge cores…） | [PyPI trustgraph-mcp](https://pypi.org/project/trustgraph-mcp/)、源码 `mcp_server/mcp.py:366-396` |
| 15 | A2A / AG-UI | **无**：全仓 grep 为空 | 源码检索 |
| 16 | 确定性推理（Datalog/规则引擎） | **无**（仅 SHACL-AF 的 SPARQL 规则用于过滤，非推理） | 源码检索 |
| 17 | 权限/多租户 | **OSS：3 角色 RBAC（reader/writer/admin）+ 工作空间结构性隔离**（队列/存储/网关三层）；**企业：OIDC/SAML/LDAP、细粒度规则、按用户 MCP 凭证** | [security](https://docs.trustgraph.ai/architecture/security.html)、[workspaces](https://docs.trustgraph.ai/architecture/workspaces.html) |
| 18 | 审计 | **Beta**：结构化 AuditEvent + request_id 关联，但**默认非持久化**（pub/sub 投递，消费端自行落库） | [v2.8 #1027](https://docs.trustgraph.ai/changelog/trustgraph.html) |
| 19 | 溯源 | **GA（OSS）**：PROV-O 抽取血缘（Document→Page→Chunk→Subgraph→Edge）+ 检索轨迹持久化在 `urn:graph:retrieval`；**密码学证明 attestation 仅企业版** | [explainability](https://docs.trustgraph.ai/architecture/explainability.html)、[open-source](https://docs.trustgraph.ai/learn/open-source.html) |
| 20 | 可观测性 | **GA**：Prometheus `tg_*` 指标、Grafana/Loki、token 计量与成本 | [architecture](https://docs.trustgraph.ai/architecture/architecture.html)、[v2.8 #1075](https://docs.trustgraph.ai/changelog/trustgraph.html) |
| 21 | 分类/打分小模型（cloze 分类、decision scoring） | **Beta**：v2.10 新增独立包 `trustgraph-cloze`/`trustgraph-laya`，laya 决策打分 ~35ms/次 | [changelog v2.10 #1171-#1180](https://docs.trustgraph.ai/changelog/trustgraph.html)、[PyPI trustgraph-laya](https://pypi.org/project/trustgraph-laya/) |
| 22 | 知识核心（Context Core）打包迁移 | **GA**（导入/导出 CLI + 网关 core_export/core_import）；"可版本化"**未核实**（源码无 version 元数据） | 源码 `gateway/dispatch/core_{export,import}.py`；[architecture](https://docs.trustgraph.ai/architecture/architecture.html) |

---

## 5. 集成面

| 接口 | 形态 | 稳定性 | 证据 |
|---|---|---|---|
| REST | **RPC 风格**：`POST /api/v1/{kind}`、`/api/v1/flow/{flow}/service/{kind}`，body 即请求对象；非资源型 REST | 中（2.x 内破坏性变更存在） | [REST doc](https://docs.trustgraph.ai/reference/apis/rest.html)、源码 `gateway/dispatch/manager.py` |
| OpenAPI 契约 | 有：Redoc 渲染，spec 标注 **2.4**；**但页面"Download OpenAPI specification"无下载链接** | 弱：无可下载工件 | REST doc 页 HTML 实测 |
| WebSocket | `GET /api/v1/socket`，多路复用，覆盖约 95% REST 能力 | 中 | [architecture](https://docs.trustgraph.ai/architecture/architecture.html) |
| 异步 API 规约 | AsyncAPI（v1.8 引入） | 文档未在该站可检索到下载 | [changelog v1.8](https://docs.trustgraph.ai/changelog/trustgraph.html) |
| Python SDK | `trustgraph-cli` 2.11.1（CLI + client 库，同步/异步、bulk、socket） | 中 | [PyPI trustgraph-cli](https://pypi.org/project/trustgraph-cli/) |
| TypeScript SDK | `@trustgraph/client` 2.3.6（Apache-2.0，repo `trustgraph-ai/trustgraph-ui`），另有 trustkit/react-provider/react-state/portal | 中 | [npm](https://www.npmjs.com/package/@trustgraph/client)、[README](https://github.com/trustgraph-ai/trustgraph/blob/master/README.md) |
| MCP 服务端 | `trustgraph-mcp`：31 工具，HTTP + Bearer | 中（自评未达生产） | §4 #14 |
| 认证 | Bearer（不透明 token）→ IAM 解析 identity + workspace；JWT 用 **Ed25519** 本地验签 | — | [security](https://docs.trustgraph.ai/architecture/security.html) |
| 默认端口 | 网关 + UI **8888**（v2.8 由 8088 改，属破坏性变更；REST 文档示例仍写 8088） | 弱 | [changelog v2.8 #1078](https://docs.trustgraph.ai/changelog/trustgraph.html)、REST doc |

**可替换粒度（关键）**：

| 想替换的环节 | 是否可行 | 代价 |
|---|---|---|
| 仅"检索/GraphRAG" | ⚠️ 名义可行、工程上不可行：GraphRAG 是 flow 内的 processor，必须起 gateway + flow + 消息总线 + 图库 + 向量库 | 最小 compose 12GB/8CPU（[compose](https://docs.trustgraph.ai/deployment/compose.html)） |
| 仅"向量库/图库" | ✅ 官方插件式：Qdrant/Milvus/Pinecone/FAISS；Cassandra/Neo4j/Memgraph/FalkorDB | 需适配其 quad 表结构 |
| 仅"Agent runtime" | ✅ 可"自带框架"接网关；或反过来用其 MCP 服务端 | [README](https://github.com/trustgraph-ai/trustgraph/blob/master/README.md) |
| 二次开发/插件 | ✅ 三条官方路径：自定义 **processor**（继承 `FlowProcessor`）+ **flow blueprint**；**IAM regime** 插件（网关零策略状态）；**messaging fabric** 插件；企业扩展走 **passthrough** dispatch | [architecture](https://docs.trustgraph.ai/architecture/architecture.html)、[capabilities spec](https://github.com/trustgraph-ai/trustgraph/blob/master/docs/tech-specs/capabilities.md)、[changelog v2.8 #1079](https://docs.trustgraph.ai/changelog/trustgraph.html) |

---

## 6. 关键限制与风险

**6.1 技术栈重量与锁定**：Pulsar + Cassandra + Qdrant + Garage + Grafana/Loki 五件套为默认；ODAP 现有 Neo4j/SQLite/Redis/MinIO 与其几乎无交集。即便换 Neo4j 图后端，**消息总线与 Cassandra 仍是硬依赖**（工作空间/元数据/行存）。锁定点在"部署形态"而非"数据格式"——数据可用 Turtle 迁出（[README](https://github.com/trustgraph-ai/trustgraph/blob/master/README.md)），但**运行形态不可拆**。

**6.2 与 Graphiti/Neo4j 的重叠与本质差异**：二者都在 Neo4j 上建图，但 TrustGraph 用 **quad + 命名图 + PROV-O 具体化**；Graphiti 用 **LPG + episode/entity/edge + `valid_at/invalid_at` 双时态**。TrustGraph **无时间有效性**（源码确认），这是与 ODAP"双时态事实层"的**不可调和差异**。

**6.3 数据模型不匹配**：ODAP 主格式为自定义 schema（ADR-084 双层事实模型），SHACL/OWL 为互操作层（ADR-077）。TrustGraph 以 RDF 为**唯一**主格式，反向导入需一次性本体映射；其"OWL 引导抽取"要求本体是 OWL 类/属性，而 ODAP 的本体是自研对象/关系/动作/规则/指标类型（7 类），**映射成本高且会丢语义**（动作/规则/指标类型在 OWL 中无对应）。

**6.4 运维复杂度与稳定性**：月度 minor 破坏性变更（v2.9/v2.10）；容器改名；schema 字段删除；默认端口变更；GitHub Releases 落后 PyPI 三个 minor。**升级即迁移**，与 ODAP "bootstep.py 一键 dev/restart-dev" 的运维模型冲突。

**6.5 文档漂移（高频且可验证）**：
- 容器页仍写 `trustgraph-unstructured`（v2.9 已删除）与 `trustgraph-hf`（v2.10 已改名 torch）、仍称"LangChain ecosystem"（v2.9 已移除）（[containers](https://docs.trustgraph.ai/reference/containers.html) vs [changelog](https://docs.trustgraph.ai/changelog/trustgraph.html)）。
- 资源要求 8GB/4 核 vs 12GB/8 核。
- LLM 供应商"12+"vs"40+"。
- REST 示例端口 8088 vs 实际 8888。
- "Production Considerations" 为空壳页。

**6.6 定位超前于实现**：README 的"sematic agent governance / action policy runtime"在 OSS 代码中无对应实现；当前"policy"仅指**查询结果过滤**。若按 README 预期采购，会踩空。

**6.7 Open-core 天花板**：attestation（密码学可验证推理）、企业 IAM、防篡改审计均在闭源侧（[open-source](https://docs.trustgraph.ai/learn/open-source.html)、[security](https://docs.trustgraph.ai/architecture/security.html)）。ODAP 若需"决策可证明"，OSS 版只能到 PROV-O 级别。

**6.8 许可风险**：**低**。Apache-2.0，无附加条款；但商标与"TrustGraph"名称使用未声明。

---

## 7. 与 ODAP 的契合度初判

### 7.1 总体结论

| 候选角色 | 结论 | 一句话理由 |
|---|---|---|
| 整体底座替换 ODAP | ❌ 否决 | 无决策一等公民、无确定性推理、无双时态、无本体版本审批流；且技术栈与 ODAP 零复用（§6.1） |
| 环节替换（检索 / 摄取 / Agent runtime） | ⚠️ 仅"试点级"可行 | 任何环节都要拖入 Pulsar+Cassandra 全栈，12GB/8CPU 起步（§5 表） |
| 设计借鉴 | ✅ 强烈建议，4 项 | 见 §7.3，其中 SHACL-AF 数据级过滤是 ODAP 当前真实空白 |
| 作为外部服务并行接入（REST/MCP） | ✅ 可行但收益低 | MCP 31 工具面可直接给 ODAP Agent 用；但需独立维护第二套知识栈 |

### 7.2 可替换（建议评估，不急于落地）

| ODAP 环节 | 替换对象 | 判断 |
|---|---|---|
| 多格式解码（DOCX/XLSX/PPTX） | TrustGraph **Docling 解码器** | 可作为 `infra/data_pipeline` 的**算法参考**而非依赖；ODAP 已有 Hyper-Extract，重复引入收益低 |
| 摄取流水线的"边级 LLM 打分/推理" | TrustGraph **edge scoring + edge reasoning** | 属检索质量增强，可在 `biz/data/qa` 内部实现同构逻辑，无需引入外部服务 |
| Agent 工具面 | TrustGraph **MCP 服务端 31 工具** | 与 ODAP 的 `/api/mcp`（ADR-089 按需查询）**同构**，价值在"工具粒度清单"参考，不在替换 |

### 7.3 可借鉴（按价值排序）

1. **SHACL-AF 查询期策略过滤 + UserContext→RDF 注入**（最高价值）。
   TrustGraph 把"谁能看到哪条边"下沉到图查询层：`sh:SPARQLTarget` 选节点、`sh:SPARQLRule` 出 `ValidationResult`、三态（Allowed/Filtered/Violation）、`tg-pol:blocks` 决定是否拦截，且 `user_context` 随 JWT 贯穿 REST→网关翻译器→TriplesClient→SPARQL→GraphRAG（[policy-filtering](https://docs.trustgraph.ai/guides/policy-filtering/)、[changelog v2.10](https://docs.trustgraph.ai/changelog/trustgraph.html)）。
   **对 ODAP 的意义**：ODAP 的 OPA 管"能不能调这个 API"，SHACL 管"本体形状对不对"（写路径，ADR-085），但**"同一张图里按密级/部门裁剪结果集"没有实现**。这正是可平移的空白，且 ODAP 已有 pyshacl + pyDatalog 基础设施，落地成本远低于引入 TrustGraph。

2. **三命名图分层：知识 / 抽取血缘 / 检索轨迹**。
   把 `urn:graph:retrieval` 设为**默认开启**而非可选导出：每次 GraphRAG/Agent 查询落一条 Question→Grounding→Exploration→Focus→Synthesis 轨迹，并可用"reified triple lookup"从 Focus 的边跨到 `urn:graph:source` 的血缘链（[explainability](https://docs.trustgraph.ai/architecture/explainability.html)）。
   **对 ODAP 的意义**：ODAP 的 PROV-O 目前在"审计导出层"（ADR-074），是**事后导出**；TrustGraph 是**写入即图、查询即证据**。这是"决策可追溯"从报表升级为图查询的关键一步，且与 ADR-076 决策因果链天然衔接。

3. **Context Core 作为可移植知识包**。
   导出/导入核心（triples + embeddings + entity contexts）以便跨环境搬运，并在秒级加载（[architecture](https://docs.trustgraph.ai/architecture/architecture.html)、源码 `core_export/core_import`）。
   **对 ODAP 的意义**：ODAP 有本体版本（OntologyVersion）但**没有"知识实例"的可搬运单元**；场景级知识包对演示、交付、隔离测试价值高。

4. **IAM 契约与网关解耦（网关零策略状态）**。
   网关只传 `(identity, capability, resource, params)`，策略全在 IAM regime；capability 是**封闭词表**，角色包只是 OSS 的一种实现（[capabilities spec](https://github.com/trustgraph-ai/trustgraph/blob/master/docs/tech-specs/capabilities.md)）。
   **对 ODAP 的意义**：与 OPA 方向一致，但"capability 封闭词表 + 插件化 regime"的写法比 ODAP 当前"路由逐个判权"更利于审计与替换。

### 7.4 不可替代（必须保留 ODAP 自有实现）

| 能力 | ODAP 现状 | 为何 TrustGraph 替不了 |
|---|---|---|
| 双时态事实层 + `state_at()` | Graphiti `valid_at/invalid_at` + 时点查询 | TrustGraph `Triple` 无时间字段（源码确认）；这是**数据模型级缺失**，非配置可解 |
| 决策一等公民（记录/因果链/先例/影响/门禁） | `biz/decision/decision_record`（ADR-076） | TrustGraph 无 Decision 实体、无因果边类型、无先例检索；README 的"decision"只是叙述 |
| 确定性推理（pyDatalog + Allen 时态） | `biz/core/ontology/reasoning/engines/deterministic/`（ADR-075） | TrustGraph 推理=LLM；无规则引擎、无时态代数 |
| SHACL/OWL 写路径治理 + 冲突检测 | ADR-077/085 | TrustGraph 无写路径校验（§4 #5） |
| 语义管理台（USL/OL 6 层/质量闸/2 级审批/缺口回路/路由工单） | `biz/semantic_admin/`（ADR-086/090/091） | TrustGraph 无本体治理流程，只有"导入 OWL + 抽取引导" |
| OPA 权限 + 统一审计落库 | `infra/opa`、`infra/security/unified_audit.py` | TrustGraph 审计事件**默认不持久化**（§4 #18），企业版才防篡改 |
| 中文业务语义与 7 类本体类型（对象/关系/动作/过程/规则/函数/指标） | `biz/core/ontology/` 全链路 | TrustGraph 只有 OWL Class/ObjectProperty/DatatypeProperty，**动作/规则/指标无对应** |

### 7.5 建议动作（不做代码改动，仅决策输入）

1. **不引入 TrustGraph 作为运行时依赖**。理由：全栈重量（§6.1）+ 月度破坏性变更（§6.4）+ 关键能力在企业版（§6.7），与 ODAP "单容器 + Neo4j" 的交付模型冲突。
2. **立"数据级策略过滤"能力项**（借鉴 §7.3-1），落点在 `infra/graph` 读路径或 `infra/query` 统一查询（ADR-055），复用现有 pyshacl，避免新建第二个策略引擎。
3. **把检索轨迹从"可选导出"改为"默认写入"**（借鉴 §7.3-2），与 ADR-074 PROV-O、ADR-076 因果链合并成一条证据链。
4. **评估"场景知识包"**（借鉴 §7.3-3）作为 OntologyVersion 的伴生交付物。
5. 若确需外部 GraphRAG 对照基线：以**离线评测**方式使用 TrustGraph（起一套 compose，跑同一批文档/问题，比对其 edge-scoring 与本仓 GraphRAG 的召回/可解释性），**不进生产链路**。

---

## 8. 未核实项（明确声明）

| 项 | 原因 |
|---|---|
| 客户名单 / 案例 / 付费转化 | trustgraph.ai 不可达；docs 无案例页 |
| GitHub issue 正文与维护响应质量 | github.com 与 api.github.com 不可达，仅有 open 数 17 |
| "Context Cores versioned" 的具体语义 | 文档声称，源码未见版本元数据 |
| SPARQL 1.1 规范覆盖度（属性路径/子查询/聚合） | 仅读 parser/algebra 结构，未做一致性测试 |
| 中文/多语种抽取与检索质量 | 仅见 RDF language tag 与 gateway i18n packs，无质量数据 |
| 企业版 attestation 的实现与 API | 闭源 |
| 容器镜像实际 tag 列表 | Docker Hub 与 auth.docker.io 不可达 |

---

## 9. 来源清单（访问日期均为 2026-10-28）

**仓库与包**
1. https://github.com/trustgraph-ai/trustgraph （README / LICENSE / SECURITY.md，经 ghproxy 镜像读取 raw）
2. https://github.com/trustgraph-ai/trustgraph/blob/master/README.md
3. https://github.com/trustgraph-ai/trustgraph/blob/master/LICENSE
4. https://github.com/trustgraph-ai/trustgraph/blob/master/SECURITY.md
5. https://github.com/trustgraph-ai/trustgraph/blob/master/docs/tech-specs/capabilities.md
6. https://github.com/trustgraph-ai/trustgraph/blob/master/docs/tech-specs/iam-contract.md
7. https://github.com/trustgraph-ai/trustgraph/blob/master/docs/tech-specs/policy-filtering.md
8. https://github.com/trustgraph-ai/trustgraph/blob/master/.github/workflows/release.yaml
9. https://pypi.org/pypi/trustgraph/json （2.11.1，559 releases）
10. https://pypi.org/pypi/trustgraph-flow/json
11. https://pypi.org/pypi/trustgraph-base/json
12. https://pypi.org/pypi/trustgraph-mcp/json
13. https://pypi.org/pypi/trustgraph-cli/json
14. https://pypi.org/pypi/trustgraph-docling/json
15. https://pypi.org/pypi/trustgraph-cloze/json
16. https://pypi.org/pypi/trustgraph-laya/json
17. https://www.npmjs.com/package/@trustgraph/client （registry.npmjs.org 元数据，2.3.6）
18. https://img.shields.io/github/stars/trustgraph-ai/trustgraph.json （2.8k）
19. https://img.shields.io/github/forks/trustgraph-ai/trustgraph.json （337）
20. https://img.shields.io/github/contributors/trustgraph-ai/trustgraph.json （29）
21. https://img.shields.io/github/v/release/trustgraph-ai/trustgraph.json （v2.8.17）
22. https://img.shields.io/github/commit-activity/m/trustgraph-ai/trustgraph.json （42/month）
23. https://img.shields.io/github/issues/trustgraph-ai/trustgraph.json （17 open）
24. https://img.shields.io/github/license/trustgraph-ai/trustgraph.json （Apache-2.0）
25. https://img.shields.io/github/repo-size/trustgraph-ai/trustgraph.json （101.7 MiB）

**官方文档**
26. https://docs.trustgraph.ai/learn/what-is-trustgraph.html
27. https://docs.trustgraph.ai/learn/how-it-works.html
28. https://docs.trustgraph.ai/learn/ontologies.html
29. https://docs.trustgraph.ai/learn/use-cases.html
30. https://docs.trustgraph.ai/learn/open-source.html
31. https://docs.trustgraph.ai/architecture/architecture.html
32. https://docs.trustgraph.ai/architecture/storage.html
33. https://docs.trustgraph.ai/architecture/retrieval.html
34. https://docs.trustgraph.ai/architecture/explainability.html
35. https://docs.trustgraph.ai/architecture/workspaces.html
36. https://docs.trustgraph.ai/architecture/security.html
37. https://docs.trustgraph.ai/reference/apis/rest.html （Redoc，spec 2.4）
38. https://docs.trustgraph.ai/reference/containers.html
39. https://docs.trustgraph.ai/reference/configuration/agent-patterns
40. https://docs.trustgraph.ai/guides/mcp-integration/
41. https://docs.trustgraph.ai/guides/policy-filtering/
42. https://docs.trustgraph.ai/quickstart/launch.html （34 processors / 9 flow classes）
43. https://docs.trustgraph.ai/quickstart/ontologies.html
44. https://docs.trustgraph.ai/deployment/compose.html （12GB/8CPU）
45. https://docs.trustgraph.ai/deployment/choosing-deployment.html （8GB/4 核，与 44 冲突）
46. https://docs.trustgraph.ai/deployment/production-considerations.html （占位页）
47. https://docs.trustgraph.ai/benchmarks.html
48. https://docs.trustgraph.ai/changelog/trustgraph.html （v2.8 / v2.9 / v2.10）
49. https://docs.trustgraph.ai/contributing/help-and-resources.html （Knownext Inc.）
50. https://docs.trustgraph.ai/assets/js/search-data.json （1,914 条文档索引，用于全站关键词核验）

**源码（sdist 解包，本地只读核验，2.11.1）**
- `trustgraph-flow-2.11.1/pyproject.toml`（processor 入口清单、依赖）
- `trustgraph-flow-2.11.1/trustgraph/gateway/dispatch/manager.py`（47 dispatch）
- `trustgraph-flow-2.11.1/trustgraph/policy/policy_filter.py`（SHACL-AF）
- `trustgraph-flow-2.11.1/trustgraph/query/ontology/*`（无入口，休眠）
- `trustgraph-flow-2.11.1/trustgraph/agent/mcp_tool/service.py`（MCP 客户端）
- `trustgraph-mcp-2.11.1/trustgraph/mcp_server/mcp.py`（31 工具）
- `trustgraph-base-2.11.1/trustgraph/schema/{triples,user_context}.py`（quad / 无时间字段 / UserContext）
