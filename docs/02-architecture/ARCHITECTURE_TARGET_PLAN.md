# ODAP 目标架构总体规划（Semantica 能力引入版）

> **版本**: 1.1.0 | **日期**: 2026-08-16 | **状态**: 规划草案（v1.1 经 2026-08-16 架构 grilling 三轮决议修订）
> **v1.1 变更**：新增 B 组吸收项 ⑦-⑪（决策因果边类型化与前置门禁、时间智能、冲突消解策略库与 SourceTracker、两阶段实体解析、doctor 自检）；ADR-075/076 范围修订；Phase 2/4 排期各扩 1 周；补充原则性吸收清单
> **上游输入**: [RESEARCH_SEMANTICA_COMPARISON_2026-08-14.md](reports/RESEARCH_SEMANTICA_COMPARISON_2026-08-14.md)
> **权威基线**: [ARCHITECTURE.md](ARCHITECTURE.md) v6.0.0（唯一权威架构，本规划为其演进蓝图，不取代）
> **关联 ADR**: 现有 ADR-002/061/068/071/072/073/074；规划新增 ADR-075/076/077/078

---

## 目录

1. [规划背景与核心结论](#1-规划背景与核心结论)
2. [目标架构总览](#2-目标架构总览)
3. [新增能力落位（逐项）](#3-新增能力落位逐项)
4. [目标包结构](#4-目标包结构)
5. [关键链路数据流](#5-关键链路数据流)
6. [ADR 关系矩阵](#6-adr-关系矩阵)
7. [分阶段路线图](#7-分阶段路线图)
8. [技术选型清单](#8-技术选型清单)
9. [边界守护（不替代清单）](#9-边界守护不替代清单)
10. [风险与缓解](#10-风险与缓解)
11. [验收标准与下一步行动](#11-验收标准与下一步行动)

---

## 1. 规划背景与核心结论

### 1.1 背景

2026-08-14 完成对 semantica-agi/semantica（v0.6.5）的主源调研。Semantica 与 ODAP 在"本体/知识图谱驱动的可审计 AI 基础设施"定位上高度同构，在 **6 个领域** 具备 ODAP 当前缺失或薄弱的能力。调研结论：**不做整体替代，按 4 个 Phase 引入 6 项能力**。

### 1.2 核心结论（承袭调研报告）

| 决策 | 结论 |
|------|------|
| 整体替代 ODAP | ❌ 不做（74 个 ADR 沉淀、8 大业务域、OPA/HITL/AG-UI 深度集成） |
| 引入 semantica 整包 | ❌ 不做（与 Graphiti/HE 职责重叠，v0.6.5 仍早期），**仅参考架构设计** |
| 能力补齐 | ✅ 引入 11 项能力，新增 4 个 ADR（075/076/077/078），扩展 2 个 ADR（074 PROV-O、064 可观测性增补） |
| 最大缺口 | **决策智能**（Decision as First-Class Citizen）——对"决策平台"定位是核心短板，列为 P0 |

### 1.3 规划原则

1. **契约先行**：所有新能力先落到既有契约层（ReasoningServiceContract ADR-072、BuildResultContract ADR-071），实现可替换
2. **正交引入**：与 OPA（权限策略）正交——新推理引擎管业务推理，OPA 管权限，互不越界
3. **双轨共存**：自定义 Schema 保持内部主格式，SHACL/OWL 作为互操作层，自动转换、单一事实源
4. **零侵入写入路径**：PROV-O 映射在导出层实现，不影响 Graphiti 写入路径
5. **工作空间隔离**：所有新能力（决策记录、图分析、冲突检测）必须继承工作空间隔离语义

---

## 2. 目标架构总览

### 2.1 目标分层架构（标注新增能力）

```
┌────────────────────────────────────────────────────────────────────────────┐
│ L6 交互层 (React 19 + AntD 6)                                               │
│   现有: 本体/Agent/仿真/审计/管理台 UI                                       │
│   新增: ★决策溯源可视化(因果链图) ★本体健康仪表盘增强 ★推理路径解释面板        │
├────────────────────────────────────────────────────────────────────────────┤
│ L5 接口层 (FastAPI + AG-UI + MCP + WS)                                      │
│   现有: web/app.py 30+ 路由                                                  │
│   新增: ★/api/decisions/* (记录/追溯/先例/影响/因果边/门禁/回填 7 端点)      │
│         ★/api/ontology/{id}/shacl ★/api/audit/export?format=prov-o          │
│         ★/api/graph/analytics/* ★/api/graph/state-at                        │
├────────────────────────────────────────────────────────────────────────────┤
│ L4 业务编排层 (biz/ 8 大业务域)                                              │
│   core/       本体 3+1 分层 (ADR-068):                                      │
│     ├─ design/engine/        ★新增 SHACL 验证器 (pySHACL)                   │
│     ├─ construction/         ★新增冲突检测子模块                              │
│     ├─ +reasoning/           ★新增确定性推理引擎 (Datalog/Rete/前向链接)      │
│     │                        实现 ReasoningServiceContract (ADR-072)         │
│     └─ application/          (现有)                                         │
│   decision/   ★核心增强: DecisionRecord 一等公民 + 因果链/先例/影响三 API      │
│   semantic_admin/  (现有, ODAP 独有优势, 不动)                               │
│   simulation/ ★消费图分析服务 (推演路径计算)                                  │
│   data/qa/    ★消费图分析服务 (多跳推理)                                      │
├────────────────────────────────────────────────────────────────────────────┤
│ L3 领域工具层 (tools/ Skills)                                               │
│   新增: ★decision_record Skill ★graph_analytics Skill ★shacl_validate Skill │
├────────────────────────────────────────────────────────────────────────────┤
│ L2 平台服务层 (infra/)                                                       │
│   graph/      ★新增 GraphAnalyticsService (GDS/networkx) + state_at 时点查询 │
│   security/   ★审计导出层新增 PROV-O 映射 (扩展 ADR-074)                      │
│   opa/        (现有, 权限策略, 与新推理引擎正交)                              │
│   query/      (现有, 统一查询 ADR-055)                                       │
├────────────────────────────────────────────────────────────────────────────┤
│ L1 存储层                                                                    │
│   Neo4j+Graphiti(双时态事实/审计) · SQLite(操作审计/业务) · Redis · MinIO     │
│   ★决策记录存 Neo4j(带 valid_time) ★PROV-O 导出走 rdflib 序列化              │
└────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 六大能力 → 架构层映射

| # | 能力 | 优先级 | 落位 | 新增 ADR |
|---|------|:--:|------|:--:|
| ① | 决策智能（DecisionRecord + 7 端点全 API 面，含因果边三类型 + 前置规则门禁） | **P0** | `biz/decision/` + Neo4j | ADR-076（修订版） |
| ② | 确定性推理引擎（Datalog/前向链接 + Allen 时态代数） | **P1** | `biz/core/ontology/+reasoning/` | ADR-075（修订版） |
| ③ | SHACL/OWL 本体治理 | P2 | `biz/core/ontology/design/engine/` | ADR-077 |
| ④ | W3C PROV-O 溯源 | P2 | `infra/security/` 审计导出层 | 扩展 ADR-074 |
| ⑤ | 图分析（中心性/社区/链路预测） | P2 | `infra/graph/GraphAnalyticsService` | ADR-078 |
| ⑥ | 冲突检测 + 多策略消解 + SourceTracker 源可信度 | P2 | `biz/core/ontology/construction/conflicts/` | 并入 ADR-077 或独立 |
| ⑦ | 时间智能：`state_at()` 时点快照查询原语 | P1 | `infra/graph/`（GraphManager 增强，Graphiti `valid_at` 过滤器服务化暴露） | 无需新 ADR（Phase 2 工作项） |
| ⑧ | 两阶段实体解析（blocking 粗筛 + 语义精判） | P2 | `semantic_admin` candidate 去重推广 | 无需新 ADR |
| ⑨ | doctor 自检 + 流水线执行状态可观测 | P2 | `bootstep.py` + `infra/observability/` | 扩展 ADR-064 |
| ⑩ | 实体感知分块优化（参考 `semantica.split` 13 种分块法） | P3 | HE 分块策略 | 无需新 ADR |
| ⑪ | Polyglot 图存储（RDF+LPG） | P3 | 仅评估，不实施 | 暂缓 |

> **原则性吸收（不设独立模块，写入 ARCHITECTURE.md v7.0.0 总则）**：审计关键路径零 LLM；fail-closed 统一安全姿态（含 Cypher/SPARQL 注入面消毒，并入 ADR-055 硬化清单，P1）；冲突"标记而非覆盖"。**Backlog 参考项**：多 Agent 共享上下文 `bind_agent` 模式、MCP 12 工具标准开放面、语义距离矩阵（增强 `find_similar_decisions` 排序）。

---

## 3. 新增能力落位（逐项）

### 3.1 ① 决策智能（P0, ADR-076）— 最大缺口

**现状**：`biz/decision/` 有 `decision_pipeline` + `decision_recommendation`，但决策非一等公民：无持久化追溯、无因果链、无先例检索、无影响分析。

**目标设计**：

```
biz/decision/
├── decision_record/              # ★新增子模块
│   ├── api/routes.py             #   POST  /api/decisions               (record)
│   │                             #   GET   /api/decisions/{id}/chain    (追溯)
│   │                             #   GET   /api/decisions/similar       (先例)
│   │                             #   GET   /api/decisions/{id}/impact   (影响)
│   │                             #   POST  /api/decisions/{id}/causal-links (因果边, v1.1)
│   │                             #   POST  /api/decisions/check-rules   (前置门禁, v1.1)
│   │                             #   PATCH /api/decisions/{id}/outcome  (回填)
│   ├── models/decision_record.py #   DecisionRecord: id/context/rationale/
│   │                             #   options/outcome/valid_time/workspace_id
│   ├── interfaces/               #   DecisionStore ABC
│   ├── impl/neo4j_decision_store.py  # Neo4j 存储(带 valid_time, 双时态)
│   └── services/                 #   编排: 与 Graphiti 审计层集成
├── decision_pipeline/            # (现有, 产出决策时调用 record)
└── decision_recommendation/      # (现有, 推荐可引用 find_similar_decisions)
```

**核心 API 语义**（参考 semantica）：

| API | 语义 | 实现要点 |
|-----|------|----------|
| `record_decision()` | 决策持久化为一等公民节点 | Neo4j `Decision` 节点 + `DERIVED_FROM` 边链到证据 Episode；同步写 Graphiti 审计（ADR-074） |
| `trace_decision_chain()` | 因果链追溯 | Cypher 变长路径遍历 `DERIVED_FROM`/`CAUSED_BY` |
| `find_similar_decisions()` | 先例搜索 | 决策上下文向量化 + 向量索引，workspace 过滤 |
| `analyze_decision_impact()` | 下游影响分析 | 图遍历找出决策生效后被 invalidation 的边/后续决策 |
| `add_causal_relationship()` | 显式建立因果边（v1.1 新增） | 三类型：`CAUSED_BY`（直接导致）/`INFLUENCED_BY`（弱影响）/`PRECEDENT_FOR`（先例引用留痕——find_similar 结果被采纳时自动建立） |
| `check_decision_rules()` | 落库前规则门禁（v1.1 新增） | 决策产出后、record 落库前先过门禁；Phase 1 = OPA 权限门禁（复用现有调用）；ADR-075 落地后业务规则（BusinessRule）加入第二道门禁 |
| `update_decision_outcome()` | 结果回填（内部） | OPA 拒绝/执行失败也必须回填（ADR-051 反馈闭环） |

**集成点**：`decision_pipeline` 产出决策 → 自动 `record_decision`；执行结果回传（ADR-051 反馈闭环）→ 更新 `outcome`。

### 3.2 ② 确定性推理引擎（P1, ADR-075）

**现状**：ADR-072 定义了 `ReasoningServiceContract`（类型推断/约束建议/一致性校验），但仅契约无实现，推理依赖 LLM。

**目标设计**：

```
biz/core/ontology/+reasoning/
├── engines/
│   ├── deterministic/            # ★新增
│   │   ├── datalog_engine.py     #   pyDatalog 实现(规则演绎)
│   │   ├── forward_chainer.py    #   IF/THEN 前向链接
│   │   ├── temporal_algebra.py   #   Allen 13 区间关系时态推理(纯 Python, 零依赖, v1.1)
│   │   └── trace_builder.py      #   rule_trace 结构化输出(与 ADR-076 reasoning_trace 对齐)
│   ├── llm/                      # (现有/规划)
│   └── hybrid/                   # 确定性兜底 + LLM 补充 (ADR-072 已规划)
└── impl/reasoning_service.py     # 实现 ReasoningServiceContract
```

**关键决策**：
- 引擎选型 A/B：`pyDatalog`（轻量、Python 原生）vs `durable_rules`（Rete 高吞吐）。**默认 pyDatalog**，兼容性验证失败降级 `experta`；spike 验收标准（v1.1 决议）：100 条规则 + 10k 事实，单次推理 P95 < 500ms，rule_trace 完整输出
- 与 OPA 边界：**OPA 管权限策略（Rego），推理引擎管业务规则（Datalog）**，在 ADR-075 中写明正交声明
- 推理路径解释：每次推理输出 `rule_trace[]`（命中的规则序列），供 L6 解释面板展示
- **时态推理（v1.1 新增）**：Allen 区间代数（13 种关系）基于 Graphiti `valid_at`/`invalid_at` 纯 Python 实现，规避引擎依赖的 Python 3.11 兼容性风险
- **显式声明（v1.1 新增）**：不参考 Semantica Rete 实现（其官方自认 `match_patterns()` 条件匹配器不成熟）；`state_at()` 时点快照查询落 `infra/graph`（Phase 2 工作项，不单列 ADR）

### 3.3 ③ SHACL/OWL 本体治理（P2, ADR-077）

**现状**：自定义 Schema 格式（ADR-032），无 SHACL 约束、无 OWL 互操作。

**目标设计（双轨制）**：

```
biz/core/ontology/design/engine/
├── shacl/                        # ★新增
│   ├── shape_generator.py        #   自定义 Schema → SHACL Shape 自动生成
│   ├── validator.py              #   pySHACL 验证(实例数据合规检查)
│   └── api 暴露: POST /api/ontology/{id}/shacl/validate
├── owl/                          # ★新增
│   ├── owl_exporter.py           #   owlready2: Schema → OWL/Turtle 导出
│   └── owl_importer.py           #   标准本体导入(互操作)
└── (现有 schema 引擎不动 —— 内部主格式)
```

**双轨原则**：自定义 Schema 是**单一事实源**；SHACL/OWL 由它自动派生，禁止人工双写。质量闸（ADR-061 16 子指标）新增"SHACL 合规率"指标。

### 3.4 ④ W3C PROV-O 溯源（P2, 扩展 ADR-074）

**现状**：Graphiti Episode 记录溯源，非标准格式。

**目标设计**：

```
infra/security/
├── unified_audit.py              # (现有)
└── provenance/                   # ★新增
    ├── prov_o_mapper.py          #   Episode → PROV-O Entity/Activity/Agent
    └── audit_exporter.py         #   导出 JSON-LD / CSV / RDF
        # API: GET /api/audit/export?format=prov-o&workspace_id=...
```

**零侵入**：映射仅发生在**导出层**，Graphiti 写入路径不变。决策记录（①）天然纳入 PROV-O 的 Activity 体系。

### 3.5 ⑤ 图分析服务（P2, ADR-078）

**现状**：Neo4j 仅做存储 + Cypher，无中心性/社区/链路预测。

**目标设计**：

```
infra/graph/
├── graph_manager.py              # (现有: Neo4j 生产 / NetworkX 回退)
└── analytics/                    # ★新增 GraphAnalyticsService
    ├── service.py                #   统一 API: centrality/community/
    │                             #   link_prediction/shortest_path
    ├── gds_backend.py            #   Neo4j GDS 后端(生产)
    └── networkx_backend.py       #   networkx 回退(与 GraphManager 回退策略一致)
```

**消费方**：`simulation/` 推演路径计算、`data/qa/` 多跳推理、决策影响分析（①）。

### 3.6 ⑥ 冲突检测与实体去重（P2）

**落位**：`biz/core/ontology/construction/` 新增 `conflicts/` 子模块——在构建期（HE feed 产出后、写图前）检测属性/类型/关系/时态冲突，产出冲突报告进质量闸。

**核心原则（v1.1 新增，吸收 Semantica）**：冲突**标记而非覆盖**——多源汇聚时静默覆盖是数据质量灾难。消解策略库：可信度加权 / 最近优先 / 投票；配套 `SourceTracker` 源可信度模型（按数据源追踪历史准确率，作为消解权重输入）。

**实体去重（v1.1 深化）**：推广 `semantic_admin` candidate 去重时采用两阶段式——blocking 粗筛（候选分块）+ 语义精判，保持工作空间隔离。

### 3.7 ⑨ doctor 自检与流水线可观测（P2, 扩展 ADR-064）

**落位**：`bootstep.py` 新增 `doctor` 子命令——逐项 pass/fail 健康检查（Python/依赖版本、Neo4j/Redis/OPA 连通性、向量后端、配置完整性），对齐 Semantica `semantica doctor` 范式；OL 6 层流水线与 HE feed 执行暴露 status/progress 查询（复用 ADR-064 OTel 指标通道）。低成本 DFX 项（约 2-3 天），随 Phase 2 交付。

---

## 4. 目标包结构

```
odap/
├── biz/
│   ├── core/ontology/
│   │   ├── design/engine/{shacl/, owl/}          # ★ ADR-077
│   │   ├── construction/conflicts/               # ★ 冲突检测 + 消解策略库 + SourceTracker
│   │   └── +reasoning/engines/deterministic/     # ★ ADR-075（含 temporal_algebra.py）
│   ├── decision/decision_record/                 # ★ ADR-076 (P0)
│   └── ... (其余 6 业务域不动)
├── infra/
│   ├── graph/analytics/                          # ★ ADR-078
│   └── security/provenance/                      # ★ 扩展 ADR-074
├── tools/
│   └── skills/{decision_record, graph_analytics, shacl_validate}/  # ★ L3 封装
└── web/app.py                                    # 注册 4 组新路由
```

**硬性约束**（承袭现有约定）：新模块同样遵守 `api/models/interfaces/impl/services/storage` 六件套结构；新增路由必须在 `web/app.py` 注册；跨域调用走契约层，禁止跨层直调。

---

## 5. 关键链路数据流

### 5.1 决策全生命周期（Phase 1 落地后）

```
摄入(HE feed) → 图谱演化(Graphiti 双时态) → 分析(QA/推理)
      → decision_pipeline 产出决策
      → ★record_decision (Neo4j + Graphiti 审计)
      → OPA 权限校验 → 执行(Perform)
      → 结果回传 → ★更新 outcome → ★影响分析可查询
      → ★后续决策可 find_similar_decisions 引用先例
```

### 5.2 推理链路（Phase 2 落地后）

```
ReasoningServiceContract (ADR-072)
   ├── 确定性引擎: Datalog 规则演绎 → rule_trace 可解释输出  [默认]
   ├── 时态推理: Allen 区间代数 (事实间 13 种时态关系)        [确定性, v1.1]
   ├── LLM 引擎: 模糊/开放问题                             [补充]
   └── hybrid: 确定性兜底 + LLM 增强                        [策略可选]
```

---

## 6. ADR 关系矩阵

| 新 ADR | 关联现有 ADR | 关系 |
|--------|-------------|------|
| ADR-075 确定性推理引擎（修订版） | ADR-072 推理契约 / ADR-068 +Reasoning 层 | **实现** ADR-072 契约；落位 ADR-068 +Reasoning 层；+Allen 时态代数（v1.1） |
| ADR-076 决策智能（修订版） | ADR-074 审计分层 / ADR-051 反馈闭环 / ADR-002 双时态 | 决策记录**作为审计事件**；复用双时态；承接反馈闭环；7 端点全 API 面（因果边三类型 + 前置门禁，v1.1） |
| ADR-077 SHACL/OWL 治理 | ADR-068 L1 Design / ADR-032 本体格式 / ADR-061 质量闸 | **增强** L1 层；与自定义 Schema 双轨共存；质量闸加指标 |
| ADR-078 图分析服务 | ADR-073 检索总线 / ADR-018 仿真 | **服务**检索与推演，infra 层横向能力 |
| （扩展）ADR-074 | PROV-O 映射 | 审计导出层增强，写入路径不变 |
| （扩展）ADR-064 | doctor 自检 / 流水线进度可观测 | DFX 增补（v1.1），随 Phase 2 交付 |

---

## 7. 分阶段路线图

```
Phase 1 (P0, 6 周上限不变) — 决策智能落地                [ADR-076 修订版]
├── ADR-076 修订回写（7 端点 + 因果边三类型 + 门禁前移）并批准
├── DecisionRecord 模型 + Neo4j 存储(双时态)
├── record/trace/find_similar/impact/causal-links/check-rules/outcome 7 端点
├── decision_pipeline / feedback 闭环集成（前置门禁挂钩 OPA）
├── Graphiti 审计层集成(决策即审计事件)
└── 前端: 决策溯源因果链可视化(G6)

Phase 2 (P1, 4-5 周, v1.1 扩期) — 确定性推理引擎 + 时间智能 [ADR-075 修订版]
├── ✅ 引擎 spike 完成（2026-08-16）: pyDatalog 0.17.4 定案 / experta 出局（frozendict 硬锁）
│     验收: 场景 A 1.9ms / 场景 B 255ms P95 达标；递归/全量演绎需架构约束兜底
│     报告: reports/spike_engine_2026-08-16/REPORT.md
├── ✅ Datalog 引擎 + rule_trace 解释输出（2026-08-18 落地）
│     reasoning/engines/deterministic/{datalog_engine,rule_loader,fact_loader,trace_builder,temporal_algebra}.py
│     + rules/{models,storage}.py（odap_business_rules 表，version_id 回滚快照）+ engines/hybrid/
│     + impl/unified_reasoning_service.py（确定性优先 + hybrid 降级）+ /deduce /rules CRUD 端点
│     测试: test_reasoning_deterministic_engine.py 26 项 + test_reasoning_service_integration.py 4 项全绿
├── ✅ Allen 时态代数 (temporal_algebra.py, 纯 Python 零依赖)
├── ✅ infra/graph state_at() 时点快照查询
├── ✅ 实现 ReasoningServiceContract, hybrid 策略（UnifiedReasoningServiceV2）
├── ✅ pyDatalog==0.17.4 加入 apps/api/pyproject.toml（需 rebuild main 生效）
├── ✅ ADR-064 增补: doctor 自检 + 流水线进度可观测（2026-08-18 落地）
│     bootstep.py doctor 子命令（版本/连通性/环境变量，零新依赖）；
│     decision_pipeline 进度查询 GET /api/decision-pipeline/progress（按 workspace 过滤）
└── ✅ 前端: 推理路径解释面板（ReasoningTracePanel.tsx，对接 /api/reasoning/deduce）

Phase 3 (P2, 4-6 周不变) — 本体治理标准化 + 溯源         [ADR-077 + 扩展074]
├── ✅ ADR-077 SHACL/OWL 治理编写完成（2026-08-18 起草，2026-08-20 grilling 四轮裁决转 Accepted）
├── ✅ ADR-074 PROV-O 溯源扩展章节补充（2026-08-18，Episode→PROV-O 映射 + 导出 API）
├── ✅ SHACL 验证器 + Shape 自动生成（2026-08-20 落地）
│     design/engine/shacl/{shape_generator,validator}.py：Schema 实时派生 Shape（防漂移）、
│     实例 JSON→RDF→pySHACL 校验（properties 字面量 / links IRI 引用）
├── ✅ OWL 导出/导入（2026-08-20 落地）
│     design/engine/owl/{owl_exporter,owl_importer}.py：Turtle/RDFXML 导出、结构映射导入（草稿）
├── ✅ PROV-O 映射 + 审计导出 API（2026-08-20 落地）
│     infra/security/provenance/{prov_o_mapper,audit_exporter,provenance_routes}.py：
│     JSON-LD/Turtle/RDFXML/CSV 导出，GET /api/audit/export
├── ✅ API 端点 + 路由注册（shacl_owl_routes.py /api/ontology/{shacl,owl}/*，provenance_routes /api/audit/export）
├── ✅ 依赖入 pyproject.toml（pySHACL/owlready2/rdflib，需 rebuild main 生效）
├── ✅ 测试 17 项全绿（test_shacl_owl_governance 10 + test_prov_o_exporter 7）
└── ⏳ 质量闸新增"SHACL 合规率"指标

Phase 4 (P2, 4-5 周, v1.1 扩期) — 图分析与冲突检测        [ADR-078]
├── ✅ ADR-078 图分析服务编写完成（2026-08-20，Proposed，双后端 GDS/networkx）
├── ✅ GraphAnalyticsService 落地（2026-08-20）
│     infra/graph/analytics/{service,networkx_backend,gds_backend}.py：
│     centrality/community/link_prediction/shortest_path 四类能力，按 mode 选后端
├── ✅ construction/conflicts/ 落地（2026-08-20）
│     {models,detector,resolution,source_tracker}.py：类型/属性/关系/时态冲突检测、
│     消解策略库（可信度加权/最近优先/投票）+ SourceTracker 源可信度（Wilson 平滑）
├── ✅ API 端点 + 路由注册（/api/graph-analytics/*，按 workspace 隔离）
├── ✅ 测试 25 项全绿（test_graph_analytics 12 + test_conflict_detection 13）
├── ⏳ 两阶段实体解析推广 (blocking 粗筛 + 语义精判)
└── ⏳ 接入 simulation 推演 + qa 多跳推理

Backlog (P3, 仅评估) — 实体感知分块 13 法 / Polyglot RDF 存储 / bind_agent 共享上下文模式 / MCP 工具面扩展 / 语义距离矩阵
```

**依赖关系**：Phase 1 独立；Phase 2 独立；Phase 3 的 PROV-O 依赖 Phase 1（决策纳入 PROV-O Activity）；Phase 4 的图分析增强 Phase 1 的影响分析。

---

## 8. 技术选型清单

| 能力 | 选型 | 版本约束 | 理由 |
|------|------|----------|------|
| Datalog 推理 | `pyDatalog`（spike 定案 2026-08-16） | 0.17.4 | 轻量、Python 原生、与契约层兼容；experta 因 frozendict==1.2 硬锁 3.10+ 不可用而出局 |
| Rete（备选） | `durable_rules` | ≥2.1 | 吞吐瓶颈时再引入 |
| SHACL 验证 | `pySHACL` | ≥0.25 | 标准实现、活跃维护 |
| OWL 操作 | `owlready2` | ≥0.46 | Python 原生 OWL |
| RDF 序列化 | `rdflib` | ≥7.0 | PROV-O JSON-LD 导出 |
| 图算法 | Neo4j GDS + `networkx` | GDS ≥2.x | 与 GraphManager 回退策略一致 |
| 决策向量检索 | 复用现有向量能力 | — | 先例搜索，不新增向量库 |
| 时态推理 | 纯 Python 自研（Allen 13 关系） | — | 零依赖，规避引擎 3.11 兼容性风险（v1.1） |
| doctor 自检 | 复用 `bootstep.py` + 现有服务客户端 | — | 零新依赖（v1.1） |

**依赖治理**：所有新依赖进 `apps/api/pyproject.toml` + `uv.lock`，镜像需 `bootstep.py rebuild main`。

---

## 9. 边界守护（不替代清单）

| 模块 | 守护理由 |
|------|----------|
| Graphiti | ADR-074 已重新定位为事实审计层（零 LLM），双时态+edge invalidation 是可审计 100% 的根基 |
| Hyper-Extract | Submodule 深度集成 OL 6 层流水线，4 维校验能力 semantica 不具备 |
| Semantic Admin Suite | 7 层 6 子服务 + 10 状态机审批 + 16 子指标质量闸是 ODAP 独有核心优势 |
| OPA | 权限策略引擎，与新推理引擎正交（权限 vs 业务推理） |
| 模拟仿真模块 | ODAP 独有，semantica 无对应 |

---

## 10. 风险与缓解

| 风险 | 等级 | 缓解 |
|------|:--:|------|
| 新依赖增加镜像复杂度 | 中 | 仅引入必要库；图算法优先 GDS 复用现有 Neo4j |
| 确定性推理与 LLM 推理协调混乱 | 中 | ReasoningServiceContract 可替换实现 + hybrid 策略（ADR-072 已规划） |
| SHACL/OWL 与自定义 Schema 双轨漂移 | 中 | 自定义 Schema 单一事实源，SHACL/OWL 仅自动派生，禁人工双写 |
| 决策存储选型（Neo4j vs SQLite） | 低 | 因果链需图遍历 → Neo4j + Graphiti 审计 |
| semantica 版本快速迭代 | 低 | 不直接依赖其包，仅参考架构 |
| PROV-O 映射拖慢写入 | 低 | 映射仅在导出层，写入路径不变 |
| 工作空间隔离在新能力中遗漏 | 中 | 每个新 ADR 设隔离 Checklist 项，评审强制确认 |
| Semantica Rete 实现不成熟的连带引用风险 | 低 | 已显式声明不参考其 Rete（官方自认 `match_patterns()` 不成熟）；pyDatalog/experta 选型不受影响（v1.1） |
| Phase 2/4 范围膨胀（v1.1 新增项） | 低 | 新增项均为确定性实现（无 LLM 不确定性），估期可靠；doctor 与两阶段实体解析可降级为 stretch goal |

---

## 11. 验收标准与下一步行动

### 11.1 总体规划验收

- [x] ADR 索引清算回写（2026-08-16 完成：12 份状态修订 + 索引重构为单一权威表）
- [x] ADR-075/076 编写/修订并通过评审（2026-08-16 均转 **Accepted**；075 含 grilling 6 项裁决 + 引擎 spike 定案）
- [x] ADR-077 SHACL/OWL 治理编写完成并转 Accepted（2026-08-18 起草 → 2026-08-20 grilling 四轮裁决转 Accepted + 落地 SHACL/OWL 引擎）
- [x] ADR-078 图分析服务编写完成（2026-08-20，Proposed，双后端 GDS/networkx + conflicts 消解落地）
- [x] ADR-074 PROV-O 扩展修订完成（2026-08-18 补充 PROV-O 映射 + 导出 API 章节）
- [x] ADR-064 可观测性增补修订完成（doctor 自检 + 流水线进度可观测，2026-08-18 落地）
- [ ] 各 Phase 交付物满足 §7 清单
- [ ] 新能力全部通过工作空间隔离测试
- [ ] `ARCHITECTURE.md` 升级至 v7.0.0 合并本规划

### 11.2 下一步行动（按序）

1. ~~启动 ADR-076 grilling 审查~~（已完成：2026-08-15 九轮 + 2026-08-16 修订轮）→ **批准 ADR-076 修订版并开工 Phase 1**
2. ~~ADR-075 引擎选型 spike~~（已完成：2026-08-16，pyDatalog 定案 / experta 出局，见 `reports/spike_engine_2026-08-16/REPORT.md`）→ **开工 Phase 2 引擎实现**（`reasoning/` 落地：fact_loader / rule_loader / engine / trace_builder / temporal_algebra；state_at() 落 infra/graph）
3. ~~Phase 3 ADR-077 编写 + ADR-074 PROV-O 扩展~~（已完成：2026-08-18）→ **下一步：ADR-077 grilling 评审 → 落地 SHACL/OWL 引擎 + PROV-O 导出层**
4. ~~Phase 4 ADR-078 编写 + 图分析/冲突检测落地~~（已完成：2026-08-20）→ **下一步：两阶段实体解析推广 + 接入 simulation/qa 消费方，随后 4 个 Phase 收尾归档合入 ARCHITECTURE.md v7.0.0**

---

> **文档维护**：本规划随各 ADR 落地逐步归档；当 4 个 Phase 全部完成时，将新增能力合入 ARCHITECTURE.md 主文档并升级版本号，本文件移入 `reports/` 归档。
