---
id: odap.l2.reports-research-semantica-comparison-2026-08-14
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

# 技术调研报告：Semantica 项目与 ODAP 平台对比分析

> **调研日期**: 2026-08-14
> **调研对象**: [semantica-agi/semantica](https://github.com/semantica-agi/semantica) (v0.6.5, MIT, 6.4k Stars)
> **调研目的**: 评估 semantica 是否可用于更新 ODAP 的部分功能替代,或参考其技术栈实现更好的落地效果
> **调研方法**: 主源调研(GitHub README + 官网 getsemantica.ai + pyproject.toml),对照 ODAP 现有 ADR-002/061/068/071/072/073/074
> **作者**: AI 架构调研

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [Semantica 项目概览](#2-semantica-项目概览)
3. [ODAP 现状速写](#3-odap-现状速写)
4. [核心维度对比矩阵](#4-核心维度对比矩阵)
5. [可参考的技术栈与组件](#5-可参考的技术栈与组件)
6. [不建议直接替代的模块](#6-不建议直接替代的模块)
7. [落地建议与路线图](#7-落地建议与路线图)
8. [风险与缓解](#8-风险与缓解)
9. [参考来源](#9-参考来源)

---

## 1. 执行摘要

### 1.1 核心结论

**Semantica 与 ODAP 在定位上高度重叠(均为"本体/知识图谱驱动的可审计 AI 基础设施"),但实现路径和成熟度差异显著。**

| 维度 | 结论 |
|------|------|
| **整体替代** | ❌ **不建议**。ODAP 已有 74 个 ADR 沉淀、8 大业务域、深度的 OPA/HITL/AG-UI 集成,迁移成本远大于收益 |
| **部分模块参考** | ✅ **强烈推荐**。Semantica 在 6 个领域有 ODAP 当前缺失或薄弱的能力,可直接借鉴其设计 |
| **技术栈借鉴** | ✅ **部分推荐**。SHACL/OWL 治理、Rete/Datalog 推理、Polyglot 图存储三块值得引入 |
| **作为依赖引入** | ⚠️ **谨慎评估**。`pip install semantica` 可作为库使用,但与 Graphiti/HE 存在职责重叠,需明确边界 |

### 1.2 一句话定位

> **Semantica 是"AI Agent 的开源 Palantir"——图原生、可审计、确定性的上下文基础设施;ODAP 是"本体驱动的分析决策平台"——两者在知识图谱层高度同构,但 ODAP 更重业务建模(本体设计→构建→应用全链路),Semantica 更重推理治理(SHACL/Rete/PROV-O)。**

---

## 2. Semantica 项目概览

### 2.1 项目定位

> 来源: [GitHub README](https://github.com/semantica-agi/semantica) · [官网 getsemantica.ai](https://getsemantica.ai)

- **自定位**: "Graph-Native Infrastructure for Context and Accountable AI Systems"——面向上下文和可问责 AI 系统的图原生基础设施
- **口号**: "AI Agent 的开源 Palantir"
- **目标场景**: 高风险、受监管领域(金融、医疗、法律、政府)的确定性、可解释、可审计 AI
- **核心承诺**: 可自托管、无供应商锁定、完全可审计、**无需 LLM 即可进行图构建/推理/溯源**

### 2.2 技术栈

| 层 | 选型 | 来源 |
|----|------|------|
| **语言** | Python (核心包) + React 19 + Sigma.js (Explorer UI) | GitHub README |
| **LLM 适配** | LiteLLM (统一 OpenAI/Anthropic/Gemini/Mistral/Llama/Groq/Cohere/Bedrock/Ollama/DeepSeek) | 官网 |
| **图数据库 (LPG)** | Neo4j · FalkorDB · Apache AGE · AWS Neptune | GitHub README |
| **三元组存储 (RDF)** | Oxigraph (嵌入式) · Blazegraph · Apache Jena · Eclipse RDF4J | GitHub README |
| **向量数据库** | FAISS · Qdrant · Weaviate · Milvus · Pinecone · PgVector · SQLite | GitHub README |
| **企业数据** | Databricks (Unity Catalog + Delta Lake) · Snowflake 原生连接器 | 官网 |
| **数据源** | 文件/Web/DB(PostgreSQL/MySQL/Oracle)/Parquet/Kafka/Kinesis/Git/Email/MongoDB/Elasticsearch | GitHub README |
| **协议** | REST API · MCP Server · CLI | GitHub README |

### 2.3 架构(端到端流水线)

> 来源: [GitHub README](https://github.com/semantica-agi/semantica)

```
Sources → Ingest → Parse → Normalize → Split → Extract →
  Conflict Detection → Deduplication → Knowledge Graph →
  [Ontology · Reasoning · Provenance · Decisions] →
  Enriched KG → Vector Store + Polyglot Graph Store →
  Export / Visualize / REST · MCP · CLI
```

**13 个生产就绪模块**:

| 模块 | 能力 |
|------|------|
| `semantica.ingest` | 多源数据摄取 |
| `semantica.semantic_extract` | NER、关系提取、事件检测、三元组生成 |
| `semantica.kg` | 知识图谱构建、中心性、社区检测、链路预测、双时态事实 |
| `semantica.reasoning` | 前向链接、Rete、Datalog、SPARQL 推理引擎 |
| `semantica.vector_store` | 混合与过滤语义搜索 |
| `semantica.split` | GraphRAG 原生文档分块(实体感知、关系感知) |
| `semantica.provenance` | W3C PROV-O 血缘追溯 |
| `semantica.ontology` | OWL 生成、SHACL 验证、SKOS 词汇表 |
| `semantica.conflicts` | 冲突检测和解决 |
| `semantica.deduplication` | 实体解析与去重 |
| `semantica.normalize` | 文本、实体、日期、数字规范化 |
| `semantica.pipeline` | 声明式并行管道 DSL |
| `semantica.export` | RDF/OWL/Parquet/Cypher/JSON-LD 导出 |

### 2.4 四大差异化能力

> 来源: [官网 getsemantica.ai](https://getsemantica.ai) 模块详情

1. **决策智能 (Decision Intelligence)**: 决策作为一等公民对象
   - `record_decision()` 持久化决策记录
   - `trace_decision_chain()` 因果链追溯
   - `find_similar_decisions()` 先例搜索
   - `analyze_decision_impact()` 下游影响分析
   - 策略引擎(Policy Engine)

2. **确定性推理引擎 (Deterministic Reasoning)**:
   - 前向链接(IF/THEN 规则)
   - Rete 网络(高吞吐匹配)
   - 演绎与归纳推理
   - SPARQL RDF 推理
   - **推理路径完全可解释**

3. **本体治理 (Ontology Governance)**:
   - 自动生成 OWL 本体
   - SHACL 形状约束 + 自动生成
   - HermiT/Pellet 验证器
   - 跨本体对齐
   - SKOS 词汇浏览
   - 本体健康仪表盘

4. **多语言图存储 (Polyglot Graph Store)**:
   - 统一 API 在 RDF 三元组存储与 LPG 之间无缝切换
   - 同时支持 SPARQL + Cypher
   - 零代码改动切换后端

### 2.5 实际案例验证

> 来源: [官网 getsemantica.ai](https://getsemantica.ai)

| 案例 | 规模 | 成果 |
|------|------|------|
| **Nereus 海洋保护** | 1 亿+ OBIS 生物多样性记录 + 卫星数据 | 量化 9 个印太海洋试点的 16.2 亿美元自然资本,生成 TNFD/LEAP 合规披露包 |
| **Ausgrid 能源监管** | 10 年监管历史文档(数千页) | 3 秒内回答英语查询并附精确引用,预计减少 20% 提交准备工作量 |

---

## 3. ODAP 现状速写

> 来源: AGENTS.md + ADR-002/061/068/071/072/073/074

### 3.1 架构骨架

```
odap/
├── biz/          # 8 大业务域
│   ├── core/              # 本体 + 认知 + Agent 编排
│   ├── decision/          # action_service + decision_pipeline
│   ├── integration/       # openharness + mcp + hook
│   ├── platform/          # workspace + roles + skill_system
│   ├── data/              # data_warehouse + qa + perception
│   ├── simulation/        # event_simulator + sandbox + deduction
│   ├── management/        # agent_management + business
│   └── semantic_admin/    # USL + OL 6 层 + 质量闸 + 审批 (ADR-061)
├── infra/        # graph(Graphiti/Neo4j) + opa + security + llm
└── web/          # app.py + gateway + ws
```

### 3.2 核心技术选型

| 层 | ODAP 现状 | 关键 ADR |
|----|-----------|----------|
| **知识图谱** | Graphiti(双时态) + Neo4j | ADR-002 |
| **抽取引擎** | Hyper-Extract(子模块) | ADR-074 |
| **策略治理** | OPA (Rego + bundles) | ADR-003/009 |
| **权限** | JWT + OPA RBAC | ADR-023/041/058 |
| **本体分层** | 3+1: Design/Construction/+Reasoning/Application | ADR-068 |
| **推理契约** | ReasoningServiceContract (规则/LLM/混合可替换) | ADR-072 |
| **检索总线** | SemanticRetrievalService (三层路由) | ADR-073 |
| **审计分层** | Graphiti(事实演化,零 LLM) + SQLite(操作审计) | ADR-074 |
| **语义治理** | Semantic Admin Suite (7 层 6 子服务, 10 状态机审批) | ADR-061 |
| **Agent 协议** | AG-UI (CopilotKit) + MCP | ADR-074 |
| **部署** | Podman 模块化单体 | ADR-046 |

### 3.3 已识别的痛点(来自 ADR-074)

1. **Graphiti 被误用为"重抽取存储"**: `add_episode` 每次 3-9 次 LLM 调用,未用双时态/edge invalidation
2. **HE 被当作"一次性抽取服务"**: 未用 `he feed` 增量演化能力
3. **审计体系缺失**: 过程审计、推理审计、查询审计均缺,`audit_helper` 为占位实现
4. **推理引擎薄弱**: ReasoningServiceContract 仅定义契约(类型推断/约束建议/一致性校验),无确定性推理引擎实现
5. **本体治理缺标准**: 自定义 Schema 格式,无 SHACL/OWL/SKOS 标准

---

## 4. 核心维度对比矩阵

### 4.1 知识图谱层

| 能力 | ODAP (Graphiti+Neo4j) | Semantica | 差距 |
|------|----------------------|-----------|------|
| 双时态 | ✅ valid_time + transaction_time (ADR-002) | ✅ 双时态事实 + Allen 区间代数(13 种关系) | Semantica 时间推理更强 |
| edge invalidation | ⚠️ 有能力但未用(ADR-074 修正中) | ✅ 原生支持 | ODAP 需落地 |
| point-in-time 查询 | ⚠️ 计划中 | ✅ 时间点查询 | Semantica 成熟 |
| 图分析(中心性/社区/链路预测) | ❌ 无 | ✅ 内置 | **ODAP 缺口** |
| Polyglot 存储(RDF+LPG) | ❌ 仅 LPG (Neo4j) | ✅ RDF+LPG 统一 API | **ODAP 缺口** |
| SPARQL | ❌ 仅 Cypher | ✅ SPARQL + Cypher | **ODAP 缺口** |

### 4.2 抽取与摄入层

| 能力 | ODAP (HE + 摄入) | Semantica | 差距 |
|------|------------------|-----------|------|
| 实体感知分块 | ⚠️ HE 有但用法未对齐(ADR-074) | ✅ GraphRAG 原生实体感知分块 | 可借鉴 |
| NER/关系/事件提取 | ✅ HE 4 维校验 | ✅ NER 流水线 + LLM 类型化提取 | 相当 |
| 冲突检测 | ❌ 无(ADR-074 提及但未实现) | ✅ 冲突检测和解决模块 | **ODAP 缺口** |
| 实体去重/实体解析 | ⚠️ semantic_admin 有 candidate 去重 | ✅ 独立 deduplication 模块 | Semantica 更通用 |
| 规范化(文本/日期/数字) | ⚠️ 散落各处 | ✅ 统一 normalize 模块 | 可借鉴 |
| 多源连接器 | ⚠️ 新闻/爬虫/PDF/Word/DB | ✅ 文件/Web/DB/Parquet/Kafka/Kinesis/Git/Email/Mongo/ES | **Semantica 更广** |
| 持续演化(feed) | ✅ HE feed (ADR-074 修正中) | ✅ 增量知识图谱构建 | 相当 |

### 4.3 推理与决策层

| 能力 | ODAP | Semantica | 差距 |
|------|------|-----------|------|
| 推理契约 | ✅ ReasoningServiceContract (ADR-072) | ✅ 推理引擎模块 | ODAP 有契约无实现 |
| 前向链接 | ❌ | ✅ IF/THEN 规则 | **ODAP 缺口** |
| Rete 网络 | ❌ | ✅ 高吞吐匹配 | **ODAP 缺口** |
| Datalog | ❌ | ✅ | **ODAP 缺口** |
| SPARQL 推理 | ❌ | ✅ RDF 推理 | **ODAP 缺口** |
| 推理路径可解释 | ⚠️ 计划中 | ✅ 完全可解释 | **ODAP 缺口** |
| 决策记录 | ⚠️ decision_pipeline 存在但非一等公民 | ✅ record_decision() 一等公民对象 | **重大差距** |
| 决策因果链追溯 | ❌ | ✅ trace_decision_chain() | **ODAP 缺口** |
| 决策先例搜索 | ❌ | ✅ find_similar_decisions() | **ODAP 缺口** |
| 决策影响分析 | ❌ | ✅ analyze_decision_impact() | **ODAP 缺口** |

> ⚠️ **决策智能是 ODAP 与 Semantica 最大的能力差距**。ODAP 的 `biz/decision/` 模块定位为"决策推演",但缺乏决策作为一等公民对象的持久化、追溯、先例检索能力。这对"本体驱动分析决策平台"的定位是关键短板。

### 4.4 本体治理层

| 能力 | ODAP | Semantica | 差距 |
|------|------|-----------|------|
| 本体格式 | ⚠️ 自定义 Schema (ADR-032) | ✅ OWL/RDF/Turtle/JSON-LD 标准 | **ODAP 缺口** |
| SHACL 约束 | ❌ | ✅ SHACL 验证 + 自动生成形状 | **ODAP 缺口** |
| OWL 生成 | ❌ | ✅ 从数据自动生成 OWL | **ODAP 缺口** |
| 本体验证器 | ⚠️ 自定义 Schema 验证 | ✅ HermiT/Pellet 推理机验证 | **ODAP 缺口** |
| SKOS 词汇管理 | ❌ | ✅ SKOS 词汇表浏览 | **ODAP 缺口** |
| 跨本体对齐 | ❌ | ✅ 跨本体对齐 | **ODAP 缺口** |
| OL 流水线 | ✅ 6 层 OL (ADR-061) | ❌ 无对应 | ODAP 独有 |
| 质量闸 | ✅ 16 子指标 (ADR-061) | ⚠️ 本体健康仪表盘(较简单) | ODAP 更深 |
| HITL 审批 | ✅ 10 状态机 + 2 级审批 (ADR-061) | ❌ 无对应 | ODAP 独有 |
| USL 统一语义层 | ✅ 独立业务域 (ADR-061) | ❌ 无对应 | ODAP 独有 |

### 4.5 审计与溯源层

| 能力 | ODAP | Semantica | 差距 |
|------|------|-----------|------|
| 溯源标准 | ⚠️ Graphiti Episode(非标准) | ✅ W3C PROV-O 标准 | **ODAP 缺口** |
| 审计分层 | ✅ Graphiti + SQLite (ADR-074) | ✅ ProvenanceTracker | 相当 |
| 审计导出 | ❌ | ✅ JSON/CSV/RDF 导出 | **ODAP 缺口** |
| 零 LLM 审计 | ✅ EpisodicNode.save (ADR-074) | ✅ 无需 LLM 图构建 | 相当 |

### 4.6 Agent 与协议层

| 能力 | ODAP | Semantica | 差距 |
|------|------|-----------|------|
| Agent 框架 | ✅ OpenHarness + 自研 Swarm | ✅ Agno 框架原生集成 | 各有侧重 |
| MCP Server | ✅ mcp_adapter (ADR-026) | ✅ MCP Server | 相当 |
| Agent↔用户协议 | ✅ AG-UI (CopilotKit) | ❌ 无对应 | ODAP 独有 |
| 多 Agent 共享上下文图 | ⚠️ 通过 Graphiti 间接实现 | ✅ 原生共享上下文图 | Semantica 更直接 |
| Hook 系统 | ✅ 独立模块 (ADR-027) | ❌ 无对应 | ODAP 独有 |

### 4.7 模拟仿真层

| 能力 | ODAP | Semantica | 差距 |
|------|------|-----------|------|
| 事件推演 | ✅ event_simulator (ADR-018) | ❌ 无对应 | ODAP 独有 |
| 沙盘推演 | ✅ simulation_sandbox | ❌ 无对应 | ODAP 独有 |
| 反馈闭环 | ✅ feedback (ADR-051) | ❌ 无对应 | ODAP 独有 |
| 双时态推演隔离 | ✅ ADR-073 | ❌ 无对应 | ODAP 独有 |

---

## 5. 可参考的技术栈与组件

### 5.1 强烈推荐引入(ODAP 明显缺口)

#### ① 确定性推理引擎(Rete/Datalog/前向链接)

**现状**: ODAP 的 `ReasoningServiceContract`(ADR-072)仅定义契约,无确定性推理引擎实现,推理能力依赖 LLM。

**Semantica 方案**: 内置 Rete 网络(高吞吐)+ Datalog + 前向链接 + SPARQL 推理,推理路径完全可解释。

**引入建议**:
- **不引入 semantica 整包**,而是参考其推理引擎架构,在 ODAP 的 `reasoning/` 层(ADR-068)实现确定性推理
- 可选 Python 库: `pyDatalog`(Datalog)、`durable_rules`(Rete)、`clingo`(ASP)
- 与 OPA Rego(已有)互补:OPA 管权限策略,新引擎管业务推理
- 优先级: **P1**
- 对应 ADR: 需新增 ADR-075 确定性推理引擎引入

#### ② 决策智能(Decision as First-Class Citizen)

**现状**: ODAP 的 `biz/decision/` 有 `decision_pipeline` 和 `decision_recommendation`,但决策非一等公民对象,无因果链追溯、先例搜索、影响分析。

**Semantica 方案**:
```python
record_decision(decision_id, context, rationale, outcome)
trace_decision_chain(decision_id)        # 因果链追溯
find_similar_decisions(query, top_k)     # 先例搜索
analyze_decision_impact(decision_id)     # 下游影响分析
```

**引入建议**:
- 在 `biz/decision/` 新增 `DecisionRecord` 模型,持久化到 Neo4j(带 valid_time)
- 实现 `trace_decision_chain` / `find_similar_decisions` / `analyze_decision_impact` 三大 API
- 与 ADR-074 的 Graphiti 审计层集成:决策记录作为审计事件
- 优先级: **P0**(对"决策平台"定位是核心能力)
- 对应 ADR: 需新增 ADR-076 决策智能架构

#### ③ SHACL/OWL 本体治理

**现状**: ODAP 使用自定义 Schema 格式(ADR-032),无 SHACL 约束、无 OWL 生成、无标准本体验证。

**Semantica 方案**: 自动生成 OWL + SHACL 形状约束 + HermiT/Pellet 验证 + SKOS 词汇管理 + 跨本体对齐。

**引入建议**:
- 在 `biz/core/ontology/design/engine/`(ADR-068 L1 层)新增 SHACL 验证器
- 可选 Python 库: `pySHACL`(SHACL 验证)、`owlready2`(OWL 操作)、`rdflib`(RDF 基础)
- 保留 ODAP 自定义 Schema 作为业务层,SHACL/OWL 作为互操作层(导出/导入标准格式)
- 优先级: **P2**(标准化是中长期诉求)
- 对应 ADR: 需新增 ADR-077 SHACL/OWL 本体治理层

#### ④ W3C PROV-O 溯源标准

**现状**: ODAP 用 Graphiti Episode 记录溯源(ADR-074),非标准格式,难以与外部系统互操作。

**Semantica 方案**: W3C PROV-O 标准,审计追踪可导出 JSON/CSV/RDF。

**引入建议**:
- 在 ADR-074 的审计层增加 PROV-O 映射:Graphiti Episode → PROV-O Entity/Activity/Agent
- 审计导出 API 支持 PROV-O JSON-LD 格式
- 优先级: **P2**(合规场景刚需)
- 对应 ADR: 扩展 ADR-074 增加 PROV-O 映射

#### ⑤ 图分析能力(中心性/社区检测/链路预测)

**现状**: ODAP 无图分析能力,Neo4j 仅用于存储和 Cypher 查询。

**Semantica 方案**: 内置中心性计算、社区检测、链路预测、最短路径。

**引入建议**:
- 可选 Python 库: `networkx`(图算法)、`neo4j-graph-data-science`(Neo4j GDS 库)
- 在 `infra/graph/` 新增 `GraphAnalyticsService`
- 服务 `biz/simulation/` 的推演场景和 `biz/data/qa/` 的多跳推理
- 优先级: **P2**
- 对应 ADR: 需新增 ADR-078 图分析服务

### 5.2 可选借鉴(ODAP 已有但可增强)

#### ⑥ 实体感知分块(GraphRAG 原生)

**现状**: ODAP 的 HE 有分块能力,但 ADR-074 指出用法未对齐。

**Semantica 方案**: GraphRAG 原生实体感知分块,避免切断命名实体。

**引入建议**: 参考 semantica 的 `semantica.split` 模块设计,优化 HE 的分块策略。优先级: **P3**。

#### ⑦ 冲突检测与实体去重

**现状**: ODAP 的 semantic_admin 有 candidate 去重,但无通用冲突检测;ADR-074 提及但未实现。

**Semantica 方案**: 独立 `conflicts` 和 `deduplication` 模块。

**引入建议**: 在 `biz/core/ontology/construction/`(ADR-068 L2 层)新增冲突检测子模块。优先级: **P2**。

#### ⑧ Polyglot 图存储(RDF + LPG)

**现状**: ODAP 仅用 Neo4j (LPG),无 RDF 三元组存储。

**Semantica 方案**: 统一 API 在 RDF/LPG 间无缝切换。

**引入建议**: **谨慎**。引入 RDF 会增加复杂度,仅在需要 SPARQL 推理或与 RDF 生态互操作时考虑。优先级: **P3**(仅评估,不急于实施)。

---

## 6. 不建议直接替代的模块

### 6.1 不替代 Graphiti

**原因**:
- ADR-074 已重新定位 Graphiti 为"事实审计层(零 LLM)",用 `EpisodicNode.save` 替代 `add_episode`
- Graphiti 的双时态 + edge invalidation 是 ODAP"可审计 100%"的独特保障
- Semantica 的图存储虽更丰富,但替换成本极高(涉及 OpenHarness 会话记忆依赖)
- **替代方案不可逆性**: 高(ADR-002 已明确)

### 6.2 不替代 Hyper-Extract

**原因**:
- HE 是 Git Submodule,深度集成 ODAP 的本体构建流水线
- ADR-074 已修正 HE 用法(回归 `he feed` 增量演化)
- Semantica 的 `semantic_extract` 虽功能相当,但无 HE 的 4 维校验和模板沉淀能力
- ODAP 的 OL 6 层流水线(ADR-061)依赖 HE 产出

### 6.3 不替代 Semantic Admin Suite

**原因**:
- ADR-061 的 7 层 6 子服务 + 10 状态机审批 + 16 子指标质量闸是 ODAP 独有的深度能力
- Semantica 无对应的 USL 管理、OL 流水线、HITL 审批飞轮
- 这是 ODAP 相对 Semantica 的**核心优势**,不应替换

### 6.4 不替代 OPA

**原因**:
- ADR-003/009 已确立 OPA 作为策略治理引擎
- OPA 的 Rego 策略与 ODAP 的 RBAC/工作空间隔离深度集成
- Semantica 无对应能力

### 6.5 不替代模拟仿真模块

**原因**:
- `biz/simulation/`(event_simulator + sandbox + deduction)是 ODAP 独有能力
- Semantica 无对应模块
- ADR-018/031 已确立架构

---

## 7. 落地建议与路线图

### 7.1 分阶段实施路线

```
Phase 1 (P0, 4-6 周) — 决策智能落地
├── 新增 ADR-076: 决策智能架构
├── biz/decision/ 新增 DecisionRecord 模型
├── 实现 record_decision / trace_decision_chain / find_similar_decisions / analyze_decision_impact
├── 集成 Graphiti 审计层 (ADR-074)
└── 前端决策溯源可视化

Phase 2 (P1, 3-4 周) — 确定性推理引擎
├── 新增 ADR-075: 确定性推理引擎引入
├── reasoning/ 层 (ADR-068 +AI 层) 实现确定性推理
├── 选型: pyDatalog 或 durable_rules
├── 与 ReasoningServiceContract (ADR-072) 对接
└── 推理路径可解释输出

Phase 3 (P2, 4-6 周) — 本体治理标准化
├── 新增 ADR-077: SHACL/OWL 本体治理层
├── design/engine/ 新增 SHACL 验证器 (pySHACL)
├── OWL 导出能力 (owlready2)
├── 扩展 ADR-074: PROV-O 溯源映射
└── 审计导出 API (JSON/CSV/RDF)

Phase 4 (P2, 3-4 周) — 图分析与冲突检测
├── 新增 ADR-078: 图分析服务
├── infra/graph/ 新增 GraphAnalyticsService
├── construction/ 新增冲突检测子模块
└── 服务 simulation 推演和 qa 多跳推理
```

### 7.2 技术选型建议

| 能力 | 推荐选型 | 理由 |
|------|----------|------|
| Datalog 推理 | `pyDatalog` | 轻量、Python 原生、与现有架构兼容 |
| Rete 网络 | `durable_rules` | 高吞吐、支持前向链接 |
| SHACL 验证 | `pySHACL` | 标准实现、活跃维护 |
| OWL 操作 | `owlready2` | Python 原生 OWL 操作库 |
| RDF 基础 | `rdflib` | RDF/SPARQL 基础库(已可能是 semantica 依赖) |
| 图算法 | `networkx` + Neo4j GDS | 前者通用,后者利用现有 Neo4j |
| 实体去重 | 自研(参考 semantica 设计) | 需与 ODAP 工作空间隔离深度集成 |

### 7.3 与现有 ADR 的关系

| 新 ADR | 关联现有 ADR | 关系 |
|--------|-------------|------|
| ADR-075 推理引擎 | ADR-072 (ReasoningServiceContract) | 实现 ADR-072 定义的契约 |
| ADR-076 决策智能 | ADR-074 (审计分层) | 决策记录作为审计事件 |
| ADR-077 SHACL/OWL | ADR-068 (L1 Design) + ADR-032 (本体格式) | 增强 L1 层,与自定义 Schema 共存 |
| ADR-078 图分析 | ADR-073 (检索总线) + ADR-018 (仿真) | 服务检索和推演 |

---

## 8. 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 引入过多 Python 库增加依赖复杂度 | 中 | 仅引入必要库,优先用 Neo4j GDS 替代 networkx |
| 确定性推理与 LLM 推理的协调 | 中 | ReasoningServiceContract 已支持可替换实现,规则引擎兜底(ADR-072 已规划) |
| SHACL/OWL 与自定义 Schema 双轨维护 | 中 | SHACL/OWL 作为互操作层,自定义 Schema 为内部主格式,提供自动转换 |
| 决策智能的存储选型(Neo4j vs SQLite) | 低 | 决策记录需图遍历(因果链),用 Neo4j + Graphiti 审计 |
| Semantica 版本快速迭代(v0.6.5 仍早期) | 低 | 不直接依赖 semantica 包,仅参考架构设计 |
| PROV-O 映射增加 Graphiti 写入复杂度 | 低 | 映射在导出层做,不影响写入路径 |

---

## 9. 参考来源

### Semantica 主源

1. **GitHub README**: https://github.com/semantica-agi/semantica — 项目定位、技术栈、13 模块、架构流水线
2. **官网**: https://getsemantica.ai — 13 模块详情、与 LangChain/LlamaIndex 对比、定价、案例(Nereus/Ausgrid)
3. **pyproject.toml**: https://github.com/semantica-agi/semantica/blob/main/pyproject.toml (抓取失败,依赖清单未获取)
4. **源码目录**: https://github.com/semantica-agi/semantica/tree/main/semantica (抓取中断,模块列表来自 README)

### ODAP 内部 ADR

5. **ADR-002**: Graphiti 作为双时态知识图谱
6. **ADR-061**: Semantic Admin Suite 架构决策(7 层 6 子服务 + 10 状态机)
7. **ADR-068**: 本体模块四层分层架构(Design/Construction/+Reasoning/Application)
8. **ADR-071**: BuildResultContract 构建产物契约
9. **ADR-072**: ReasoningServiceContract 推理服务契约
10. **ADR-073**: 基于本体的数据服务四步落地架构(语义检索服务总线)
11. **ADR-074**: 情报驱动架构——HE 与 Graphiti 正确定位及分层审计

### 调研局限

- **未克隆 semantica 源码**: 本次调研基于 README + 官网,未深入源码。建议后续克隆仓库做 LSP 级代码分析,验证推理引擎和决策智能的实现细节。
- **pyproject.toml 未获取**: 精确依赖清单未获取,技术栈信息来自 README 描述。
- **性能基准缺失**: semantica 未提供标准化基准测试,性能表现仅来自案例描述(3 秒查询响应、1 亿记录处理)。

---

> **下一步行动**: 本报告建议在 Phase 1 启动 ADR-076(决策智能)的 grilling 审查,这是 ODAP"决策平台"定位的核心补强。可使用 `/grill-with-docs` 流程深化设计。
