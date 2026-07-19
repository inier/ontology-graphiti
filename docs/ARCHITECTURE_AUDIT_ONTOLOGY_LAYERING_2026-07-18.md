# 本体模块架构审计 — 3+1 分层模型决策

> **日期**: 2026-07-18 | **状态**: 已完成 — 最终架构已采纳
> **审计范围**: `apps/api/odap/biz/core/ontology/` (20 子模块, 300+ .py) + 关联模块 (`core/assistant/`, `core/chat/`, `core/cognition/`)
> **最终决策**: ADR-068 — 3 领域层 (Design / Construction / Application) + 1 技术能力层 (+Reasoning)
> **论证方式**: 三视角多智能体协同审查（领域DDD专家 + 代码审计员 + 文档对齐员）
> 
> **关键结论**: Design↔Construction 分离通过 DDD 五项测试；AI 推理能力作为技术层独立管理（非领域层）；cognition 模块合并入 L3 Application；ADR-038/048/049 标记废弃；3 组 ADR 编号冲突已修复

---

## 一、目标四层模型定义

```
┌──────────────────────────────────────────────────────────────────┐
│  L4  本体应用 — AI 助手 (Ontology Application)                    │
│  Chat / 问答 / 本体编辑辅助 / 可视化 / 态势推演                   │
├──────────────────────────────────────────────────────────────────┤
│  L3  本体推理服务 (Ontology Reasoning Service)                     │
│  意图识别 / 知识导航 / 解释引擎 / 思维图谱 / 类型推断 / 一致性校验 │
├──────────────────────────────────────────────────────────────────┤
│  L2  本体构建 (Ontology Construction)                              │
│  数据摄入 / 实体解析 / 关系抽取 / 流水线构建 / 质量验证            │
├──────────────────────────────────────────────────────────────────┤
│  L1  本体设计 (Ontology Design)                                    │
│  类型定义 / Schema建模 / 版本管理 / 约束规则 / 编辑锁 / 分支合并   │
└──────────────────────────────────────────────────────────────────┘

  所有四层通过定义良好的 Contract（契约接口）通信
  上层依赖下层，下层不知上层 — 单向依赖 + 契约隔离
```

---

## 二、当前代码分层图谱

### 2.1 现状总览：名义上两层，实际上三层半

当前 `ontology/` 名义上只有 `design/` 和 `application/` 两个顶层子系统，但实际包含了远超两层的内容：

```
                                  ontology/
                                      │
              ┌───────────────────────┼───────────────────────────┐
              │                       │                           │
          design/               application/               (游离模块)
    "定义/版本/构建/摄入"    "运行/编排/服务化/查询"         无明确归属
              │                       │                           │
    ┌─────────┼─────────┐    ┌────────┼────────┐         assistant/
    │         │         │    │        │        │         extraction/
  model/  ingestion/  services/  oms/  runtime/ harness/   branch/
  version/  (摄入)   build/    query/  servit/  team/     cold_start/
  engine/            ingest/   abution/         agent/    computed/
                     pipeline/                             conflict/
                     qa_onto/                              goal/
                                                          health/
                                                          inheritance/
                                                          sharding/
                                                          view/
                                                          action/
```

### 2.2 四层映射表（当前实际归属）

| 目标层 | 当前归属 | 代码路径 | 问题 |
|--------|---------|---------|------|
| **L1 本体设计** | `design/` + 游离模块 | `design/model/`, `design/version/`, `design/engine/`, `branch/`, `conflict/`, `computed/`, `inheritance/`, `view/`, `action/` | ✅ 大部分在 design/ 内，但 branch/ conflict/ 等游离在顶层 |
| **L2 本体构建** | `design/` 内部混放 | `design/ingestion/`, `design/ingestion_split/`, `design/services/build_service.py`, `design/services/ingest_service.py`, `design/services/pipeline_service.py`, `design/services/qa_ontology_builder.py` | ⚠️ 构建逻辑混在设计层内，违反单一职责；ingestion_split 是独立副本 |
| **L3 本体推理** | **散落各处，无统一模块** | `cognition/impl/intent_recognizer.py`, `cognition/impl/explanation_engine.py`, `cognition/impl/knowledge_navigator.py`, `cognition/thought_graph/`, `assistant/rules/type_inference.py`, `assistant/rules/constraint_suggester.py`, `design/services/validation_service.py` | ❌ 完全缺失，推理逻辑分布在 4 个不同模块 |
| **L4 本体应用** | 三套并存 | `ontology/assistant/` (T063), `core/assistant/` (plugin), `core/chat/` (unified), `application/oms/`, `application/runtime/`, `application/servitization/`, `application/query_api/`, `application/team_agent/` | ❌ 三套 AI 助手 + 散乱的 application 子模块 |

---

## 三、核心问题诊断

### 问题 1：L2 构建逻辑深埋 L1 设计层内 ⚠️⚠️ 高

**现状**: `design/services/` 同时包含 `build_service.py`、`ingest_service.py`、`pipeline_service.py`、`qa_ontology_builder.py` 等**构建阶段**服务，与 `version_service.py`、`edit_lock_service.py` 等**设计阶段**服务平级混放。

**根因**: 初始拆分时未区分「设计本体 schema」和「根据 schema 构建实例」这两个不同职责。

**后果**:
- 设计层膨胀（20 个子模块），`design/` 承载了远超「设计」范畴的职责
- 构建流水线 `pipeline_service.py` 依赖摄入子系统，但两者在同一父包内，耦合面无契约约束
- `ingestion_split/` 是一个完整独立的平行摄入系统（新闻/DOM/数据库），与 `design/ingestion/` 功能重叠但实现不同

**量化**: `design/services/` 含 12 个服务，其中 4 个属构建阶段 (33%)。

### 问题 2：L3 推理服务完全缺失 ❌ 最高

**现状**: 项目中无 `reasoning/` 目录，推理能力分散在 4 个独立模块：

| 推理能力 | 实际位置 | 问题 |
|---------|---------|------|
| 意图识别 | `cognition/impl/intent_recognizer.py` | 认知模块，非本体推理 |
| 知识导航 | `cognition/impl/knowledge_navigator.py` | 同上 |
| 解释引擎 | `cognition/impl/explanation_engine.py` | 同上 |
| 思维图谱 | `cognition/thought_graph/` | 独立子模块，与本体推理无关 |
| 类型推断 | `ontology/assistant/rules/type_inference.py` | 耦合在 AI 助手内 |
| 约束建议 | `ontology/assistant/rules/constraint_suggester.py` | 同上 |
| 一致性校验 | `ontology/health/` + `design/services/validation_service.py` | 健康检查模块 |

**后果**:
- 没有统一的推理服务入口，调用方需要知道每个推理能力的具体位置
- AI 助手直接依赖推理规则文件（`assistant/rules/`），无法替换推理策略
- `cognition/` 模块定位为「用户认知引擎」，与「本体推理服务」语义混淆

### 问题 3：L4 三套 AI 助手并存 ❌ 最高

**现状**: （ADR-050 已识别尚未执行）

| 组件 | 路径 | 协议 | 行数 | 状态 |
|------|------|------|------|------|
| T063 本体助手 | `ontology/assistant/` | AG-UI SSE | ~1500 | 活跃 |
| AI 助手框架 | `core/assistant/` | AG-UI + tool-call | ~2000 | 活跃 |
| 统一 Chat | `core/chat/` | AG-UI + CUSTOM 扩展 | ~800 | 新建(ADR-050) |

**问题**: ADR-050 已明确合并方案（`core/chat/` 统一入口），但 `ontology/assistant/` 仍在独立运行，三套代码并存。

### 问题 4：application/ 子模块职责混杂 ⚠️ 中

`application/` 下有 7 个子模块，覆盖了从元数据管理到团队协作的广泛范围：

| 子模块 | 职责 | 应归属层 | 当前状态 |
|--------|------|---------|---------|
| `oms/` | 对象元数据服务（只读缓存） | L3 推理服务（数据层） | application/ |
| `runtime/` | 运行时状态机 + World State | L4 应用（执行层） | application/ |
| `servitization/` | API 服务化部署 | L4 应用（发布层） | application/ |
| `harness/` | 数据集成编排 | L2 构建（数据层） | application/ |
| `team_agent/` | 团队智能体协同 | L4 应用（协作层） | application/ |
| `query_api/` | NL 询查 API | L4 应用（查询层） | application/ |
| `abution_graph/` | 属性图引擎 | L3 推理服务（图计算） | application/ |

**根因**: `application/` 的定义过于宽泛（"运行、编排、服务化、查询"），实际上是一个「不属于 design 的都塞进 application」的垃圾桶模式。

### 问题 5：Contract 模式覆盖不足 ⚠️ 中

当前仅存在 `design/contract/`（L1↔L2 通信），缺失：

| 缺失的契约 | 需要建立 | 原因 |
|-----------|---------|------|
| L2→L3 构建产物契约 | `construction/contract/` | 推理服务需要知道构建产物的结构（实体类型、关系、属性） |
| L3→L4 推理能力契约 | `reasoning/contract/` | AI 助手不直接调用特定推理引擎，而是通过统一接口 |
| L4 内部契约 | `application/contract/` | OMS、runtime、servitization 之间的通信需要明确定义 |

### 问题 6：游离模块归属不清 ⚠️ 中

以下顶级子模块无明确归属：

| 游离模块 | 合适应归属 |
|---------|-----------|
| `branch/`, `conflict/` | L1 设计 |
| `cold_start/` | L1 设计（模板）+ L2 构建（引导） |
| `extraction/` | L2 构建 |
| `computed/`, `inheritance/`, `view/`, `action/` | L1 设计 |
| `goal/`, `health/` | 跨层（设计质量 + 运行监控） |
| `sharding/` | L2 构建（分片策略） |
| `registry/` | 跨层基础设施 |
| `ontology_api/` | L4 应用（CRUD API） |

---

## 四、建议目标架构

### 4.1 四层目录结构

```
odap/biz/core/ontology/
├── __init__.py                     # 顶层入口，组合四层
│
├── design/                         # L1: 本体设计
│   ├── __init__.py
│   ├── contract/                   # ★ 对外契约（L1→L2/L3/L4）
│   │   ├── interface.py            #    OntologyDesignContract（保持不变）
│   │   └── facade.py
│   ├── model/                      # 类型定义（EntityType, Property, Relation）
│   ├── schema/                     # Schema 文档定义
│   ├── version/                    # 版本管理
│   ├── engine/                     # 引擎（验证/审计/快照）
│   ├── branch/                     # 分支与合并 ← 从顶层迁移
│   ├── conflict/                   # 冲突解决 ← 从顶层迁移
│   ├── computed/                   # 计算属性 ← 从顶层迁移
│   ├── inheritance/                # 继承系统 ← 从顶层迁移
│   ├── view/                       # 对象视图 ← 从顶层迁移
│   ├── action/                     # 动作类型 ← 从顶层迁移
│   ├── cold_start/                 # 冷启动模板 ← 从顶层迁移
│   └── services/                   # 设计层服务（仅保留设计相关）
│       ├── version_service.py
│       ├── edit_lock_service.py
│       ├── search_service.py
│       ├── transform_service.py
│       └── validation_service.py   # schema 级验证
│
├── construction/                   # L2: 本体构建 ★ 新建
│   ├── __init__.py
│   ├── contract/                   # ★ 对外契约（L2→L3/L4）
│   │   ├── interface.py            #    BuildResultContract
│   │   └── facade.py
│   ├── ingestion/                  # 数据摄入（从 design/ 迁移）
│   │   ├── api/
│   │   ├── impl/                   #   pdf/word/ocr 处理器
│   │   ├── services/
│   │   └── storage/
│   ├── extraction/                 # 信息抽取（从顶层 migration）
│   ├── pipeline/                   # 构建流水线（从 design/services/ 迁移）
│   │   └── services/
│   │       ├── build_service.py
│   │       ├── ingest_service.py
│   │       ├── pipeline_service.py
│   │       └── qa_ontology_builder.py
│   ├── quality/                    # 构建质量验证（实例级）
│   │   └── services/
│   │       └── entity_resolver.py
│   └── sharding/                   # 分片策略 ← 从顶层迁移
│
├── reasoning/                      # L3: 本体推理 ★ 新建
│   ├── __init__.py
│   ├── contract/                   # ★ 对外契约（L3→L4）
│   │   ├── interface.py            #    ReasoningServiceContract
│   │   └── facade.py
│   ├── inference/                  # 类型推断与约束推导
│   │   ├── type_inference.py       #   ← 从 assistant/rules/ 迁移
│   │   └── constraint_suggester.py #   ← 从 assistant/rules/ 迁移
│   ├── intent/                     # 意图识别
│   │   └── intent_recognizer.py    #   ← 从 cognition/ 迁移
│   ├── navigation/                 # 知识图谱导航
│   │   └── knowledge_navigator.py  #   ← 从 cognition/ 迁移
│   ├── explanation/                # 解释引擎
│   │   └── explanation_engine.py   #   ← 从 cognition/ 迁移
│   ├── consistency/                # 一致性校验
│   │   └── consistency_checker.py   #   ← 从 health/ 迁移
│   ├── thought_graph/              # 思维图谱 ← 从 cognition/ 迁移
│   └── services/
│       └── reasoning_service.py    #    统一推理服务入口
│
├── application/                    # L4: 本体应用
│   ├── __init__.py
│   ├── chat/                       # AI 助手统一入口（ADR-050）
│   │   ├── engine/
│   │   │   └── unified_chat_service.py
│   │   ├── tools/                  #   本体编辑工具（design_tools / write_tools）
│   │   ├── retrieval/              #   RAG 检索引擎（vector/BM25/graph）
│   │   └── renderers/              #   渲染器（chart/temporal/report/thinking）
│   ├── oms/                        # 对象元数据服务（只读缓存）
│   ├── runtime/                    # 运行时引擎（World State / 状态机）
│   ├── servitization/              # API 服务化部署
│   ├── harness/                    # 数据集成编排 → 可能整合到 L2
│   ├── query_api/                  # NL 查询 API
│   └── team_agent/                 # 团队智能体协同
│
├── registry/                       # ★ 跨层基础设施（保持不变）
│   └── TypeRegistry                #    统一类型入口
│
├── health/                         # 健康检查/质量监控（跨层）
├── goal/                           # 目标管理（跨层）
│
└── (删除) assistant/               # → 合并到 application/chat/
```

### 4.2 四层契约矩阵

```
┌────────────┬───────────────┬───────────────────┬─────────────────────────┐
│            │ L1 Design     │ L2 Construction   │ L3 Reasoning            │
├────────────┼───────────────┼───────────────────┼─────────────────────────┤
│ L2 Const.  │ DesignContract│         —         │          —              │
│            │ (已有)        │                   │                         │
├────────────┼───────────────┼───────────────────┼─────────────────────────┤
│ L3 Reason. │ DesignContract│ BuildResultContract│         —              │
│            │ (读 entity)   │ (读构建产物)       │                         │
├────────────┼───────────────┼───────────────────┼─────────────────────────┤
│ L4 App     │ DesignContract│ BuildResultContract│ ReasoningSvcContract   │
│            │ (读 schema)   │ (读实体实例)       │ (调用推理能力)          │
└────────────┴───────────────┴───────────────────┴─────────────────────────┘
```

### 4.3 端到端流程示例

```
用户: "帮我创建一个'武器装备'实体类型，包含名称、口径、射程属性"

  L4 Chat (application/chat/)
    │ tool_call: create_entity_type → L1 DesignContract
    │
    ▼
  L1 Design (design/model/)
    │ 创建 EntityType: "武器装备" + PropertyDefs
    │ 版本管理: 生成 v1.0.1
    │
    ▼
  L2 Construction (construction/ingestion/)
    │ 用户上传武器装备 CSV 数据
    │ pipeline: ingest → extract → resolve → validate
    │ 生成 EntityInstance[]
    │
    ▼
  L3 Reasoning (reasoning/)
    │ consistency_check: "口径" 属性是否有缺失值？
    │ type_inference: 根据已有数据建议加 "制造商" 属性
    │ intent: 用户问 "射程超过100km的装备有哪些"
    │
    ▼
  L4 Chat (application/chat/)
    │ RAG retrieval → 返回 3 个实体
    │ renderer: 生成对比表格
```

---

## 五、迁移路线图

### Phase A: 建立 L3 推理服务（1-2 周）⭐ 最优先

**目标**: 填补最大缺口，建立推理服务统一入口。

1. **创建 `reasoning/` 目录骨架**（contract + inference + intent + navigation + explanation + consistency + services）
2. **定义 `ReasoningServiceContract`** 接口:
   ```python
   class ReasoningServiceContract:
       def infer_type(hint: str, workspace_id: str) -> TypeInferenceResult
       def suggest_constraints(entity_type_id: str) -> List[ConstraintSuggestion]
       def check_consistency(entity_type_id: str) -> ConsistencyReport
       def recognize_intent(query: str, context: dict) -> IntentResult
       def navigate(entity_type_id: str, depth: int) -> KnowledgeGraph
       def explain(entity_type_id: str, question: str) -> Explanation
   ```
3. **迁移推理代码**（不删源文件，先桥接）:
   - `assistant/rules/type_inference.py` → `reasoning/inference/`
   - `assistant/rules/constraint_suggester.py` → `reasoning/inference/`
   - `cognition/impl/intent_recognizer.py` → `reasoning/intent/`
   - `cognition/impl/knowledge_navigator.py` → `reasoning/navigation/`
   - `cognition/impl/explanation_engine.py` → `reasoning/explanation/`
   - `health/` 质量校验 → `reasoning/consistency/`
4. **新增 `UnifiedReasoningService`** 组合所有推理能力

**收益**: 推理能力首次有统一入口，AI 助手通过契约解耦。

### Phase B: 拆分 L2 构建层（1 周）

1. **创建 `construction/` 目录**并定义 `BuildResultContract`
2. **迁移构建服务**: `design/services/build_service.py`, `ingest_service.py`, `pipeline_service.py`, `qa_ontology_builder.py` → `construction/pipeline/services/`
3. **迁移摄入**: `design/ingestion/` → `construction/ingestion/`
4. **整合 ingestion_split**: 评估是合并到 `construction/ingestion/` 还是独立保留。如功能重叠，二选一删除。
5. **迁移 extraction**: 从顶层搬到 `construction/extraction/`

**收益**: 设计层缩小 30%，职责清晰。

### Phase C: 清理 L4（1 周）

1. **执行 ADR-050**: 合并三套 AI 助手为 `application/chat/`
2. **归属游离模块**: branch/conflict/computed/inheritance/view/action → `design/`, cold_start → `design/`
3. **评估 harness/**: 是否应归入 `construction/` 还是留在 `application/`
4. **保留 application/** 保留 OMS、runtime、servitization、query_api、team_agent（各自的 L4 角色明确）

### Phase D: 文档化与 Contract 强化（持续）

1. 更新 `ARCHITECTURE_BIZ.md` 本体章节
2. 补充 3 个缺失契约（L2→L3, L3→L4, L4 内部）
3. 更新架构图（C4 Level 2 → Level 3）

---

## 六、ADR-068: 本体模块四层分层架构

### ADR-068: 将本体模块拆分为四层（Design → Construction → Reasoning → Application）

## Status
Proposed

## Context

当前本体模块 `odap/biz/core/ontology/` 名义上拆分为 `design/` 和 `application/` 两个子系统，实际存在以下问题：

1. **构建逻辑混在设计层内**：`design/services/` 的 12 个服务中有 4 个属于构建阶段（33%），与版本管理、编辑锁等设计阶段服务平级混放
2. **推理服务完全缺失**：意图识别、类型推断、一致性校验等推理能力分散在 `cognition/`、`assistant/rules/`、`health/` 等 4 个不同模块，无统一入口
3. **三套 AI 助手并存**：`ontology/assistant/`（T063）、`core/assistant/`（plugin）、`core/chat/`（unified）功能重叠但协议不同
4. **application/ 职责膨胀**：7 个子模块覆盖元数据、运行时、服务化、数据集成、查询、智能体等，缺乏内部契约
5. **8 个游离模块**（branch, conflict, computed, inheritance, view, action, cold_start, extraction）无明确层级归属

这些问题的根因是初始的两层拆分（design ↔ application）没有覆盖完整的本体生命周期。本体领域存在天然的四阶段流水线（Design → Build → Reason → Apply），当前架构缺失中间两层。

## Decision

将本体模块重组为四层架构：

1. **L1 `design/`** — 本体设计：类型定义、Schema 建模、版本管理、约束规则、编辑锁、分支合并
   - 收纳游离模块：`branch/`, `conflict/`, `computed/`, `inheritance/`, `view/`, `action/`, `cold_start/`
   
2. **L2 `construction/`** — 本体构建：数据摄入、实体解析、关系抽取、流水线构建、分片策略
   - 从 `design/services/` 迁移：`build_service.py`, `ingest_service.py`, `pipeline_service.py`, `qa_ontology_builder.py`
   - 从 `design/ingestion/` 迁移整个摄入子系统
   - 从顶层迁移：`extraction/`, `sharding/`

3. **L3 `reasoning/`** — 本体推理服务：类型推断、约束建议、意图识别、知识导航、解释引擎、一致性校验
   - 新建模块，从 4 个模块收集推理能力
   - 定义统一的 `ReasoningServiceContract` 接口

4. **L4 `application/`** — 本体应用：AI 助手（统一 Chat）、OMS 缓存、运行时引擎、服务化部署、查询 API
   - 执行 ADR-050，合并三套 AI 助手为 `application/chat/`
   - `ontology/assistant/` 并入 `application/chat/`

所有层间通信通过 Contract 接口（Frozen Dataclass Views），禁止直接引用内部实现类。

## Consequences

**变得更容易**:
- 每个层次职责单一，团队可以独立理解和修改
- 构建流水线可以从设计层独立演进（替换摄入策略、优化流水线）
- 推理服务有统一入口，AI 助手通过契约调用，可以替换推理实现（如从本地规则引擎切换为 LLM-based 推理）
- 新成员加入时，四层流水线直观映射到"设计 → 构建 → 推理 → 应用"的认知模型

**变得困难/需要注意**:
- 迁移过程需分阶段执行（Phase A→B→C→D），每阶段约 1-2 周，总工期约 4-6 周
- 迁移期间需保持向后兼容（`__getattr__` 桥接模式），避免破坏现有调用方
- `cognition/` 模块的推理代码迁移后，该模块自身定位需要重新审视（建议保留为「用户级认知」而非「本体推理」）
- `harness/`（数据集成编排）需要与 L2 construction 评估是否有功能重叠，确定最终归属
- 需要补充 3 个新 ADR（L2 构建契约、L3 推理契约、L4 内部契约）

---

## 附录 A: 当前四层映射速查表

| 目标层 | 当前代码路径 | 状态 | 迁移优先级 |
|--------|-------------|------|-----------|
| L1 设计 | `design/model/`, `design/version/`, `design/engine/`, `design/contract/` | ✅ 基本正确 | 收纳游离模块 |
| L2 构建 | `design/ingestion/`, `design/ingestion_split/`, `design/services/{build,ingest,pipeline,qa_ontology}*`, 顶层 `extraction/` | ⚠️ 混在设计层 | **Phase B** |
| L3 推理 | `cognition/{intent,navigation,explanation,thought_graph}`, `assistant/rules/{type_inference,constraint}`, `health/` | ❌ 完全缺失 | **Phase A** ⭐ |
| L4 应用 | `ontology/assistant/`, `core/assistant/`, `core/chat/`, `application/{oms,runtime,servitization,query_api,team_agent,harness,abution_graph}` | ❌ 三套并存 | **Phase C** |

## 附录 B: 相关 ADR 引用

| ADR | 标题 | 与本审计关系 |
|-----|------|------------|
| ADR-046 | 模块化单体架构 | 本审计的架构基础 |
| ADR-048 | AI 助手独立组件化 | L4 应用层组件化 |
| ADR-050 | 统一 AI 助手与智能问答服务 | L4 三合一方案 |
| ADR-051 | 基于 OpenHarness 全能力的 AI 助手架构 | L4 引擎选择 |
| **ADR-068** | **本体模块四层分层架构** | **本审计产出** |

## 附录 C: 审计工具链

- **代码扫描**: `apps/api/odap/biz/core/ontology/` 全部 20 子模块 + `core/assistant/` + `core/chat/` + `core/cognition/`
- **引用分析**: Grep 跨模块 `from odap.biz.core.ontology` 导入
- **API 路由**: 19 个路由前缀 + 2 个 WebSocket 端点
- **前端**: `apps/web/src/modules/ontology/` (47 组件 + 8 页面 + 5 服务 + 4 Store)
