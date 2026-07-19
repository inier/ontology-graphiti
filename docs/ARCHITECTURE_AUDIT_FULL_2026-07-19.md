# ODAP 本体驱动分析决策平台 — 全栈架构审计与优化方案

> 审计日期：2026-07-19
> 审计范围：本体四层架构（设计L1 → 构建L2 → 推理+AI → 应用L3）
> 审计目标：确认各层功能合理性，制定优化方案，确保交付高质量代码

---

## 目录

1. [总体架构概览](#1-总体架构概览)
2. [领域1：本体设计层（L1）+ 数据摄入链路](#2-领域1本体设计层l1--数据摄入链路)
3. [领域2：本体构建层（L2）+ 图谱构建链路](#3-领域2本体构建层l2--图谱构建链路)
4. [领域3：本体推理服务（+AI）— 全平台统一数据检索](#4-领域3本体推理服务ai--全平台统一数据检索)
5. [领域4：本体应用层（L3）— AI助手 + 决策推演](#5-领域4本体应用层l3--ai助手--决策推演)
6. [领域5：整体质量保证与测试验证](#6-领域5整体质量保证与测试验证)
7. [优先级汇总与实施路线图](#7-优先级汇总与实施路线图)

---

## 1. 总体架构概览

### 1.1 当前架构图（按 ADR-068 3+1 分层）

```
┌─────────────────────────────────────────────────────────────┐
│                    L3 Application (应用层)                    │
│  chat/ | oms/ | runtime/ | harness/ | servitization/        │
│  query_api/ | team_agent/ | intent/ | navigation/           │
│  explanation/ | thought_graph/ | abution_graph/             │
├─────────────────────────────────────────────────────────────┤
│                    +AI Reasoning (推理技术层)                 │
│  contract/ (仅接口) | inference/ (空壳)                      │
│  consistency/ (空壳) | services/ (空壳)                      │
├─────────────────────────────────────────────────────────────┤
│                    L2 Construction (构建层)                   │
│  contract/ (已实现) | ingestion/ (空壳)                      │
│  extraction/ (空壳) | pipeline/ (空壳)                       │
│  quality/ (空壳) | sharding/ (空壳)                          │
├─────────────────────────────────────────────────────────────┤
│                    L1 Design (设计层)                         │
│  model/ | version/ | engine/ | contract/                    │
│  ingestion/ + ingestion_split/ (双系统)                      │
│  services/ (12个服务) | schema/ | mock_data/                 │
└─────────────────────────────────────────────────────────────┘

实际功能分布：
  L1 实现最完整（~80%），但有构建逻辑混入
  L2 仅有接口定义（~15%），实际功能在 L1 services/ 和 data/ 中
  +AI 仅有契约（~5%），无任何实现
  L3 实现最丰富（~70%），但三套AI助手并存
```

### 1.2 核心发现汇总

| 层级 | 状态 | 核心问题 |
|------|------|---------|
| L1 设计层 | 功能完整但混乱 | 双Ingestion系统、指标定义缺失、构建逻辑混入 |
| L2 构建层 | **严重空壳** | 6个子目录为空，六步流水线未实现，溯源/审计断裂 |
| +AI 推理层 | **仅有接口** | 无任何实现，检索分散在5个模块 |
| L3 应用层 | 功能丰富但冗余 | 三套AI助手、GenBI/决策推演缺失 |

---

## 2. 领域1：本体设计层（L1）+ 数据摄入链路

### 2.1 现状分析

#### 已实现功能 ✅

| 组件 | 文件 | 状态 |
|------|------|------|
| 本体模型定义 | `design/model/models/` | ✅ EntityType/Property/Relation/Constraint |
| 版本管理 | `design/version/` | ✅ 版本CRUD + 历史 |
| 验证引擎 | `design/engine/` | ✅ 验证 + 审计记录器 |
| 设计契约 | `design/contract/` | ✅ DesignContract (Frozen Views) |
| 文件摄入 | `design/ingestion/` | ✅ PDF/Word/OCR/CSV/JSON |
| 非结构化采集 | `design/ingestion_split/` | ✅ 新闻/手动输入/事件生成器 |
| 本体文档格式 | `design/schema/` | ✅ OntologyDocument (ADR-032) |

#### 问题清单

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| P1-1 | **双 IngestService 并存** | P0 | 两套摄入服务有不同接口、不同存储、无统一调度 |
| P1-2 | **ingestion_split 命名混乱** | P0 | `ingestion/` vs `ingestion_split/` 不反映实际分工 |
| P1-3 | **Property 缺少语义标注** | P0 | 无 semantic_type/tags/domain，跨本体对齐不可行 |
| P1-4 | **MetricDefinition 模型缺失** | P0 | 无法定义指标、公式、与Property关联 |
| P1-5 | **EntityType 缺少业务分类** | P1 | 无 domain/category/tags，无法领域分组 |
| P1-6 | **原始数据存储四地分散** | P1 | SQLite/MinIO/Neo4j/Graphiti 各自管理，无统一DataLake |
| P1-7 | **SemanticMap 与本体定义未双向同步** | P1 | 本体定义变更时不自动更新语义地图 |
| P1-8 | **知识库提取链路重复** | P1 | HE/LLM/Regex 三条路径可能提取同一文档三次 |

### 2.2 优化方案

#### 短期（1-2周，P0）

| 任务 | 内容 | 验收标准 |
|------|------|---------|
| **统一IngestService** | 在 `construction/ingestion/services/` 创建 UnifiedIngestionService，合并两套服务 | 单一入口支持所有摄入方式 |
| **扩展Property语义字段** | 添加 `semantic_type`, `tags`, `unit`, `domain` 字段（Optional，向后兼容） | 可标注属性的语义类型和领域 |
| **扩展EntityType业务字段** | 添加 `domain`, `category`, `tags` 字段 | 可按领域分类实体类型 |
| **创建DataLakeWriter** | `infra/storage/data_lake_writer.py` 统一写入抽象 | 所有数据通过统一入口写入 |

#### 中期（3-4周，P1）

| 任务 | 内容 |
|------|------|
| **实现MetricDefinition模型** | `design/model/models/metric.py` + MetricBinding + MetricService |
| **语义注册系统** | `common/semantic_registry.py` — SemanticType, Tag, Domain注册 |
| **DataCatalog实现** | 元数据目录，记录数据源→提取→实体→存储完整链路 |
| **Construction层目录充实** | 将 `design/services/` 中的构建服务迁移到 `construction/` |

#### 长期（5-8周，P2）

| 任务 | 内容 |
|------|------|
| **统一DataLake API** | 屏蔽SQLite/MinIO/Neo4j/Graphiti存储差异 |
| **自动指标发现** | 基于semantic_type=measure自动推荐指标 |
| **闭环反馈系统** | 质量回写 + 使用热度 + 冲突修复建议 |

---

## 3. 领域2：本体构建层（L2）+ 图谱构建链路

### 3.1 现状分析

#### 已实现功能 ✅

| 组件 | 状态 |
|------|------|
| BuildResultContract (接口) | ✅ 定义完成 |
| Bridge (写操作桥接) | ✅ 代理到 design/services/ |
| Hyper-Extract 知识提取 | ✅ HEAdapter + 双通道写入 |
| ProvenanceTracker | ✅ 仅在 HE 层使用 |
| AuditRecorderImpl | ✅ 构建过程未完全集成 |
| KnowledgeBase build_graph | ✅ HE/LLM/Regex 三级提取 |

#### 问题清单

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| P2-1 | **Construction层6个子目录全为空壳** | P0 | 违反ADR-068分层原则，构建功能仍在design/ |
| P2-2 | **六步构建流水线未实现** | P0 | 缺少实体标准化、关系验证、一致性检查、人工审核 |
| P2-3 | **溯源链断裂** | P0 | ProvenanceTracker仅在HE层使用，构建/写入未记录 |
| P2-4 | **审计集成不充分** | P0 | 构建关键操作(标准化/审核/写入)未记录审计 |
| P2-5 | **质量门禁缺失** | P0 | quality/目录为空，无构建前/中/后质量检查 |
| P2-6 | **回滚能力弱** | P1 | 仅支持版本级全量回滚，无增量和实体级回滚 |
| P2-7 | **分片策略缺失** | P1 | 大数据量构建无并行处理 |
| P2-8 | **事务性缺失** | P1 | 步骤5失败时步骤1-4的变更不会回滚 |

### 3.2 优化方案：完整六步构建流水线

```
构建输入: 原始数据 (NL/Document/JSON/URL/DB/KB)
                          │
  ┌───────────────────────┼──── 质量门禁: 前置校验 ────────────────┐
  │                        │                                       │
  │  Step1         Step2         Step3         Step4              │
  │  实体标准化  →  关系验证  →  一致性检查  →  人工审核           │
  │  (去重/同义词)  (类型兼容)    (冲突/冗余)    (确认/修正/拒绝)    │
  │     │             │             │             │                │
  │     ▼             ▼             ▼             ▼                │
  │  AuditLog      AuditLog      AuditLog      AuditLog           │
  │  Provenance    Provenance    Provenance    Provenance          │
  │                          │                                     │
  │  ┌───────────────────────┼──── 质量门禁: 构建后验证 ──────────┐│
  │  │                        │                                   ││
  │  │  Step5          Step6                                      ││
  │  │  写入Graphiti → 版本快照                                    ││
  │  │  (batch_id标记)  (完整状态保存)                              ││
  │  │     │             │                                         ││
  │  │     ▼             ▼                                         ││
  │  │  AuditLog + Provenance + Rollback支持                      ││
  │  └────────────────────────────────────────────────────────────┘│
  └────────────────────────────────────────────────────────────────┘

横向贯穿能力:
  ProvenanceTracker: 原始文档→提取记录→构建操作→图谱实体→审计日志
  AuditRecorder:     每一步操作独立审计记录
  RollbackManager:   版本级/pipeline级/batch级三级回滚
```

#### 实施路线图

| Phase | 任务 | 工期 | 优先级 |
|-------|------|------|--------|
| Phase 2-1 | 创建 `construction/provenance/` (溯源链编织 + 查询) | 2天 | P0 |
| Phase 2-2 | 创建 `construction/quality/` (三级门禁 + 10条规则) | 2天 | P0 |
| Phase 2-3 | 创建 `construction/rollback/` (三级回滚) | 2天 | P0 |
| Phase 2-4 | 实现六步流水线处理器 | 8天 | P0 |
| Phase 2-5 | 集成审计到每步操作 | 2天 | P0 |
| Phase 2-6 | Construction 层目录充实 + 代码迁移 | 5天 | P1 |
| Phase 2-7 | 分片策略 + 性能优化 | 3天 | P1 |

---

## 4. 领域3：本体推理服务（+AI）— 全平台统一数据检索

> **这是本次审计的核心焦点**。本体推理服务的定位是全平台统一对外提供的数据检索服务。

### 4.1 现状分析

#### 4.1.1 Reasoning 层现状 — 仅有契约

**路径**: `apps/api/odap/biz/core/ontology/reasoning/`

```python
# contract/interface.py — 唯一有代码的文件
class ReasoningServiceContract:
    """所有方法都抛出 NotImplementedError"""
    def infer_types(data_sample, workspace_id) -> TypeInferenceResult: raise NotImplementedError
    def suggest_constraints(entity_type_id) -> List[ConstraintSuggestion]: raise NotImplementedError
    def check_schema_consistency(ontology_id) -> ConsistencyReport: raise NotImplementedError
    def check_instance_consistency(entity_type_id, instance_ids) -> ConsistencyReport: raise NotImplementedError
    def get_reasoning_capabilities() -> List[str]: raise NotImplementedError
```

**结论：推理层仅有接口定义，零实现。所有检索功能分散在其他模块。**

#### 4.1.2 分散的检索服务（5个独立模块）

| # | 模块 | 路径 | 核心方法 | 返回格式 |
|---|------|------|---------|---------|
| 1 | **QueryService** | `infra/query/service.py` | `execute(dsl)` | `QueryResult(source, rows, total)` |
| 2 | **NLDispatcher** | `ontology/application/query_api/nl_dispatcher.py` | `dispatch(nl_query)` | `{status, intent, rows, ...}` |
| 3 | **KnowledgeBase RAG** | `data/knowledge_base/services/knowledge_base_service.py` | `rag_query()` | `{answer, sources, ...}` |
| 4 | **QARetrieverTool** | `core/chat/tools/qa_retriever_tool.py` | `execute(query)` | `ToolResult(output)` |
| 5 | **GraphManager** | `infra/graph/graph_service.py` | `search/search_hybrid/traverse` | `List[Dict]` / `Dict` |

#### 4.1.3 QueryService 五源查询详细分析

```
QueryService 当前支持 5 种数据源:

.source              → 读什么数据                  → 底层实现
────────────────────────────────────────────────────────────────
.schema              → 本体类型定义（对象/关系/动作）→ OMS SQLite
.entity              → 运行时实体实例               → GraphManager (Neo4j/Graphiti)
.topo                → 拓扑关系 + 图遍历           → GraphManager
.temporal            → 双时态数据                  → Graphiti
.unstructured        → 非结构化文档/向量检索        → SemanticObjectRetriever
```

**关键设计亮点**：
- ✅ 五源统一DSL查询语法（`.source with(filters) action(params)`）
- ✅ Agent Safe 模式（只允许读SCHEMA/ENTITY，拦截写操作）
- ✅ 协议化设计（Protocol + 可插拔实现）
- ✅ 异步支持（`execute_async` 在 thread pool 中运行）

**关键设计问题**：
- ❌ 无溯源信息返回（结果不知道来自哪个文档/提取/构建）
- ❌ 无置信度/质量分（所有结果平等对待）
- ❌ 无跨源联邦查询（一次只能查一个源）
- ❌ 无结果格式化/排序/分页（按源原始顺序返回）
- ❌ Schema源只查OMS，不返回Property详情和指标定义

#### 4.1.4 NLDispatcher 分析

```
POST /api/ontology/query/nl  →  NLDispatcher.dispatch()
    → IntentClassifier.classify(nl_query)
    → 4条路径:
        STRUCTURED   → NL→DSL(LLM优先+关键词回退) → QueryService.execute()
        UNSTRUCTURED → .unstructured with(query) → QueryService.execute()
        HYBRID       → STRUCTURED + UNSTRUCTURED 并行 → result_merger
        ACTION       → ontology_app_skill 调度
```

**关键设计亮点**：
- ✅ NL→DSL 转换（LLM优先 + 关键词回退 + 5s超时保护）
- ✅ 四种意图分类
- ✅ HYBRID 双路并行 + 结果合并

**关键设计问题**：
- ❌ STRUCTURED失败时降级为UNSTRUCTURED，丢失了结构化查询精度
- ❌ 结果合并简单拼接，无去重/排序/置信度加权
- ❌ 不返回每条结果的溯源信息
- ❌ LLM DSL转换依赖外部LLM可用性

#### 4.1.5 溯源能力 — **核心缺失**

**问题**：当前检索结果完全无法溯源。用户查询得到实体/关系后，无法知道：

1. **这个实体来自哪个原始文档？** → 无 `source_document_id`
2. **实体是通过什么方法提取的？** → 无 `extraction_method`
3. **提取的置信度是多少？** → 无 `confidence_score`
4. **实体的属性对应哪个本体定义？** → 无 `ontology_property_id`
5. **数据的构建/更新时间？** → 无 `build_transaction_id`

**已存在的溯源基础**（但未与检索服务集成）：
- `ProvenanceTracker` (hyper_extract/impl/provenance_tracker.py) — 仅在HE层使用
- `AuditRecorderImpl` (design/engine/impl/audit_recorder_impl.py) — 仅在ingestion使用

### 4.2 目标架构：统一推理服务

#### 4.2.1 核心设计

```
                    UnifiedReasoningService
                    (reasoning/services/)
                           │
          ┌────────────────┼────────────────┐
          │                 │                │
    RetrieveEngine    ReasonEngine     TraceEngine
    (统一检索)        (AI推理)          (溯源追溯)
          │                 │                │
    ┌─────┼─────┐    ┌─────┼─────┐    ┌─────┼─────┐
    │     │     │    │     │     │    │     │     │
  Schema Entity Doc   Type  Consis  Sem   Prove- Audit
  Source Source Source Infer Check  Search nance  Log
                    (调用+AI推理层)
```

#### 4.2.2 统一检索API设计

```python
# reasoning/services/unified_retrieve.py

@dataclass(frozen=True)
class RetrieveRequest:
    """统一检索请求"""
    query: str                          # 自然语言查询
    workspace_id: str
    ontology_ids: List[str] = field(default_factory=list)
    source_types: List[str] = field(default_factory=lambda: ["schema", "entity", "document"])
    retrieval_mode: str = "hybrid"      # hybrid / bm25 / vector / graph
    top_k: int = 20
    include_provenance: bool = True     # ★ 是否返回溯源信息
    include_metrics: bool = False       # ★ 是否返回关联指标
    include_semantics: bool = False     # ★ 是否返回语义标注

@dataclass(frozen=True)
class RetrieveResult:
    """统一检索结果"""
    items: List[RetrievedItem]
    total: int
    query_intent: str                   # structured / unstructured / hybrid
    execution_time_ms: float
    provenance_summary: ProvenanceSummary  # ★ 溯源摘要

@dataclass(frozen=True)
class RetrievedItem:
    """单个检索结果"""
    # 基本信息
    id: str
    name: str
    type: str                           # entity / property / relation / document / metric
    score: float                        # 相关性分数 (0-1)
    
    # ★ 溯源链 (4级)
    provenance: Optional[ProvenanceChain] = None
    
    # 本体关联
    ontology_id: Optional[str] = None
    ontology_property_id: Optional[str] = None  # 如果是属性值，关联到哪个Property
    
    # 指标关联
    metric_ids: List[str] = field(default_factory=list)
    
    # 语义标注
    semantic_type: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    domain: Optional[str] = None
    
    # 原始数据
    raw_data: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ProvenanceChain:
    """4级溯源链"""
    # Level 0: 图谱实体
    graph_entity_id: str
    graph_entity_type: str
    
    # Level 1: 构建操作
    build_pipeline_run_id: Optional[str] = None
    build_step: Optional[str] = None       # normalization / relation_validation / ...
    build_timestamp: Optional[str] = None
    build_operator: Optional[str] = None   # 构建操作者
    
    # Level 2: 提取记录
    extraction_session_id: Optional[str] = None
    extraction_method: Optional[str] = None # HE / LLM / Regex
    extraction_confidence: Optional[float] = None  # 0-1
    
    # Level 3: 原始文档/数据源
    source_document_id: Optional[str] = None
    source_document_name: Optional[str] = None
    source_document_type: Optional[str] = None
    source_text_snippet: Optional[str] = None    # 原始文本片段
    source_url: Optional[str] = None
    
    # 本体定义关联
    ontology_definition_id: Optional[str] = None
    ontology_property_id: Optional[str] = None
    metric_definition_id: Optional[str] = None
```

#### 4.2.3 跨源联邦查询

```python
class UnifiedRetrieveEngine:
    """统一检索引擎 — 支持跨源联邦查询"""
    
    async def retrieve(self, request: RetrieveRequest) -> RetrieveResult:
        """主入口：一次查询，跨多源检索，统一返回"""
        
        # 1. 意图分类
        intent = await self._classify_intent(request.query)
        
        # 2. 并行多源检索
        tasks = []
        if "schema" in request.source_types:
            tasks.append(self._retrieve_schema(request))
        if "entity" in request.source_types:
            tasks.append(self._retrieve_entity(request))
        if "document" in request.source_types:
            tasks.append(self._retrieve_document(request))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. 跨源融合：去重 + 排序 + 置信度加权
        merged = self._merge_cross_source(results, request)
        
        # 4. ★ 填充溯源信息
        if request.include_provenance:
            merged = await self._enrich_provenance(merged)
        
        # 5. ★ 填充指标关联
        if request.include_metrics:
            merged = await self._enrich_metrics(merged)
        
        # 6. ★ 填充语义标注
        if request.include_semantics:
            merged = await self._enrich_semantics(merged)
        
        return RetrieveResult(
            items=merged[:request.top_k],
            total=len(merged),
            query_intent=intent,
            execution_time_ms=...,
            provenance_summary=self._build_provenance_summary(merged),
        )
    
    async def _retrieve_schema(self, request) -> List[RetrievedItem]:
        """检索本体类型定义，关联Property和Metric"""
        # 查询 OMS + TypeRegistry
        types = self._query_service.execute(workspace_id, ".schema with(...)")
        items = []
        for t in types:
            item = RetrievedItem(id=t.id, name=t.name, type="entity_type", ...)
            # ★ 关联Property定义
            item.ontology_property_ids = t.get("property_ids", [])
            # ★ 关联指标定义
            item.metric_ids = self._metric_service.get_metrics_for_type(t.id)
            items.append(item)
        return items
    
    async def _enrich_provenance(self, items: List[RetrievedItem]) -> List[RetrievedItem]:
        """★ 填充溯源信息"""
        for item in items:
            if item.type == "entity":
                chain = ProvenanceLinker().link_chain(item.id)
                item.provenance = chain
            elif item.type == "document":
                item.provenance = ProvenanceChain(
                    source_document_id=item.id,
                    source_document_name=item.name,
                )
        return items
```

### 4.3 优化方案

#### 短期（1-2周，P0）— 快速见效

| # | 任务 | 内容 | 验收标准 |
|---|------|------|---------|
| S3-1 | **实现UnifiedRetrieveEngine** | 在 `reasoning/services/unified_retrieve.py` 创建统一检索入口，封装 QueryService + KnowledgeBase RAG + GraphManager | 一个接口调用支持5种数据源 |
| S3-2 | **扩展QueryResult添加溯源字段** | 在 `QueryResult.rows` 中每个item添加 `provenance_chain` 字段 | 检索结果可追溯到原始文档ID |
| S3-3 | **创建ProvenanceLinker** | 在 `provenance/provenance_linker.py` 实现4级溯源链编织 | 从图谱实体→构建→提取→原始文档 |
| S3-4 | **统一NL检索API** | 新增 `POST /api/reasoning/retrieve` 端点，合并NLDispatcher+QueryService | 一个端点支持所有NL查询 |

#### 中期（3-4周，P1）— 架构优化

| # | 任务 | 内容 | 验收标准 |
|---|------|------|---------|
| M3-1 | **实现跨源联邦查询** | `retrieve()` 支持一次查询并行检索 schema+entity+document | 多源结果合并去重排序 |
| M3-2 | **实现指标关联填充** | `_enrich_metrics()` 自动关联Property→Metric | 检索结果包含关联指标定义 |
| M3-3 | **实现语义标注填充** | `_enrich_semantics()` 自动填充semantic_type/tags/domain | 检索结果包含完整语义信息 |
| M3-4 | **实现ReasoningServiceContract** | 填充 `reasoning/services/unified_reasoning.py` | infer_types/suggest_constraints可用 |
| M3-5 | **实现一致性校验** | `check_schema_consistency()` + `check_instance_consistency()` | Schema和实例级一致性检查可用 |

#### 长期（5-8周，P2）— 能力增强

| # | 任务 | 内容 |
|---|------|------|
| L3-1 | **结果缓存优化** | 热点查询结果缓存，TTL 5min |
| L3-2 | **检索质量评估** | 自动评估检索结果相关性/覆盖率 |
| L3-3 | **个性化检索** | 基于用户角色/历史查询优化排序 |
| L3-4 | **实时索引更新** | 本体定义变更时自动更新检索索引 |

---

## 5. 领域4：本体应用层（L3）— AI助手 + 决策推演

### 5.1 现状分析

#### 三套AI助手并存

| # | 系统 | 路径 | 引擎 | 协议 | 工具数 | 状态 |
|---|------|------|------|------|--------|------|
| 1 | **UnifiedChatService** | `application/chat/engine/` | OpenHarness QueryEngine | AG-UI SSE | 17 (16 BaseTools + QARetriever) | ✅ ADR-069/070 |
| 2 | **ChatService** | `core/assistant/` | OH + 降级ChatService | AG-UI + 自定义SSE | 16 BaseTools | ⚠️ Phase 2主路径 |
| 3 | **OntologyAssistant** | `ontology/assistant/` | 独立 | AG-UI | 本体专用工具 | ⚠️ 待合并 |

#### 核心问题

| # | 问题 | 严重度 |
|---|------|--------|
| P4-1 | **三套系统未完全统一** | P0 |
| P4-2 | **GenBI能力缺失** | P0 |
| P4-3 | **决策推演缺失** | P0 |
| P4-4 | **多方案模拟推演缺失** | P0 |
| P4-5 | **执行策略引擎缺失**（自动/审批/定时） | P0 |
| P4-6 | **AIChatPanel单体组件** | P1 |
| P4-7 | **跨领域知识融合差** | P1 |

### 5.2 优化方案

#### 统一AI助手架构

```
POST /api/chat/message (唯一入口)
        │
        ▼
UnifiedChatService (OpenHarness 原生引擎)
        │
        ├── Agent Loop (ReAct 模式)
        │     ├── Think → Act → Observe → Reflect
        │     └── max_turns=8 (auto_compact)
        │
        ├── 工具集 (25+ tools)
        │     ├── 查询工具: EntitySearch, RelationQuery, TemporalQuery, SchemaQuery
        │     ├── 设计工具: GetOntologyContext, CheckCompleteness, SuggestProperties
        │     ├── 写入工具: AddProperty, UpdateProperty, CreateObjectType (需OPA授权)
        │     ├── RAG工具: QARetrieverTool (三支柱: BM25+Vector+Graph)
        │     ├── ★ GenBI工具: GenerateChart, GenerateReport, AnalyzeMetric
        │     ├── ★ 推演工具: SimulateScenario, CompareOptions, ForecastTrend
        │     └── ★ 执行工具: ExecuteAction, ScheduleTask, RequestApproval
        │
        ├── Persona 系统
        │     ├── assistant: 通用助手
        │     ├── qa: QA引擎
        │     ├── ontology-designer: 本体设计
        │     ├── ★ analyst: 数据分析/GenBI
        │     └── ★ strategist: 决策推演
        │
        └── 输出渲染器
              ├── THINKING: 思考过程
              ├── SOURCES: 引用的文档/实体/指标溯源
              ├── CHART: 图表渲染
              ├── TEMPORAL: 时序分析
              ├── REPORT: 报告生成
              ├── ★ OPTIONS: 多方案对比
              └── ★ ACTION_PLAN: 执行建议
```

#### 新增能力

##### GenBI 能力

```python
class GenBITool(BaseTool):
    """自然语言 → 图表/报表"""
    async def execute(self, input: GenBIInput) -> ToolResult:
        # 1. NL → 指标查询 (调用 UnifiedRetrieveEngine)
        metrics_data = await self.retrieve_engine.retrieve(
            RetrieveRequest(query=input.query, include_metrics=True)
        )
        # 2. 选择合适的图表类型
        chart_type = self._recommend_chart(metrics_data, input.hint)
        # 3. 生成图表配置
        chart_config = self._build_chart_config(metrics_data, chart_type)
        # 4. 返回图表渲染数据
        return ToolResult(output=json.dumps({
            "chart_type": chart_type,
            "chart_config": chart_config,
            "provenance": metrics_data.provenance_summary,  # ★ 溯源
        }))
```

##### 决策推演能力

```python
class SimulateScenarioTool(BaseTool):
    """多方案模拟推演"""
    async def execute(self, input: SimulateInput) -> ToolResult:
        # 1. 加载本体规则和约束
        rules = await self._load_ontology_rules(input.ontology_id)
        # 2. 初始化仿真状态
        state = WorldState(ontology_id=input.ontology_id)
        # 3. 运行多个方案
        scenarios = []
        for scenario_def in input.scenarios:
            result = await self._simulate_scenario(state, scenario_def, rules)
            scenarios.append({
                "name": scenario_def.name,
                "result": result,
                "risk_score": self._assess_risk(result),
                "provenance": result.provenance,  # ★ 推演过程可溯源
            })
        # 4. 多方案对比
        comparison = self._compare_scenarios(scenarios)
        return ToolResult(output=json.dumps({
            "scenarios": scenarios,
            "comparison": comparison,
            "recommendation": self._recommend(scenarios),
        }))
```

##### 执行策略引擎

```python
class ExecutionStrategyEngine:
    """支持三种执行模式"""
    
    # 自动执行
    async def auto_execute(self, action: Action, context: ExecutionContext):
        if not self._check_permissions(action, context):
            raise PermissionDenied
        if not self._validate_preconditions(action, context):
            raise PreconditionFailed
        result = await self._execute(action, context)
        await self._record_audit(action, result, "auto")
        return result
    
    # 审批执行
    async def approval_execute(self, action: Action, context: ExecutionContext):
        approval = await self._request_approval(action, context)
        if approval.status != "approved":
            return ExecutionResult(skipped=True, reason="审批未通过")
        return await self.auto_execute(action, context)
    
    # 定时执行
    async def schedule_execute(self, action: Action, context: ExecutionContext, schedule: Schedule):
        job_id = await self._scheduler.add_job(
            func=self.auto_execute,
            trigger=schedule.to_cron(),
            args=(action, context),
        )
        return ExecutionResult(scheduled=True, job_id=job_id)
```

---

## 6. 领域5：整体质量保证与测试验证

### 6.1 测试策略

```
┌──────────────────────────────────────────────────────────┐
│                    测试金字塔                              │
├──────────────────────────────────────────────────────────┤
│                                                           │
│                 ┌─────────────┐                           │
│                 │  E2E Tests  │  关键用户流程             │
│                 │  (10-20)    │  - 从摄入到问答全流程      │
│                 └──────┬──────┘  - 多角色权限验证         │
│                        │                                  │
│            ┌───────────┼───────────┐                      │
│            │   Integration Tests  │  跨模块集成            │
│            │      (50-100)        │  - API→Service→DB     │
│            │                      │  - Graph构建+检索      │
│            └──────────┬───────────┘  - 溯源链完整性        │
│                       │                                   │
│     ┌─────────────────┼─────────────────┐                 │
│     │          Unit Tests (200+)        │  单元测试         │
│     │  - Service逻辑  - Tool执行        │  - 模型验证       │
│     │  - 解析器       - 门禁规则       │  - 契约检查       │
│     └──────────────────────────────────┘                   │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### 6.2 质量门禁（每层必过）

| 门禁 | 检查项 | 阻塞条件 |
|------|--------|---------|
| **代码质量** | lint (ruff/eslint) + type check (mypy/tsc) | 任何错误 |
| **单元测试** | `pytest` 覆盖率 > 80% | 覆盖率 < 80% |
| **集成测试** | 关键API端点全绿 | 任何失败 |
| **契约测试** | Contract接口一致性 | 接口变更未更新 |
| **溯源验证** | 4级溯源链完整性 | 溯源链断裂 |
| **审计日志** | 关键操作有审计记录 | 审计记录缺失 |

### 6.3 功能验证清单

#### L1 设计层验证

- [ ] 创建本体 → 定义EntityType → 添加Property(含semantic_type/tags) → 版本发布
- [ ] 定义Metric → 绑定Property → 验证公式正确性
- [ ] 文件上传 → 自动解析 → 结构化存储 → 溯源记录生成
- [ ] 新闻采集 → LLM归纳 → 本体文档生成

#### L2 构建层验证

- [ ] 数据摄入 → 实体标准化(去重验证) → 关系验证(断链检测) → 一致性检查(冲突报告)
- [ ] 人工审核流程: 提交→前端通知→审核确认→写入
- [ ] 溯源链完整性: 图谱实体 → 构建记录 → 提取记录 → 原始文档
- [ ] 审计日志: 每步操作可查询
- [ ] Pipeline回滚: 正常回滚 + 异常回滚 + 实体级回滚
- [ ] 质量门禁: 前置拦截 + 中置降级 + 后置修复建议

#### L3 推理服务验证

- [ ] 结构化查询: `.entity with(type='装备') list()` 返回正确结果并带溯源
- [ ] 非结构化查询: NL→DSL→QueryService 返回正确结果
- [ ] 混合查询: HYBRID模式双路并行+结果合并
- [ ] 溯源追溯: 从搜索结果追溯到原始文档
- [ ] 指标关联: 查询实体时自动关联Metric定义
- [ ] 一致性校验: Schema和实例级检查

#### L4 应用层验证

- [ ] AI对话: 自然语言问答 + 工具调用
- [ ] GenBI: NL → 图表渲染
- [ ] 决策推演: 多方案对比 + 风险评估
- [ ] 执行策略: 自动执行 + 审批执行 + 定时任务
- [ ] 跨领域问答: 关联多个本体的知识

---

## 7. 优先级汇总与实施路线图

### 7.1 总优先级矩阵

| 优先级 | 任务数 | 核心目标 |
|--------|--------|---------|
| **P0 — 阻塞发布** | 18项 | 补全核心能力，保障功能可用 |
| **P1 — 影响体验** | 12项 | 架构优化，提升质量 |
| **P2 — 锦上添花** | 8项 | 能力增强，性能优化 |

### 7.2 P0 任务清单（必须立即执行）

| # | 任务 | 所属领域 | 工期 |
|---|------|---------|------|
| P0-1 | 统一 IngestService | L1 设计层 | 2天 |
| P0-2 | 扩展 Property 语义字段 | L1 设计层 | 1天 |
| P0-3 | 创建 MetricDefinition 模型 | L1 设计层 | 2天 |
| P0-4 | Construction 层 provenance/ 实现 | L2 构建层 | 2天 |
| P0-5 | Construction 层 quality/ 实现 | L2 构建层 | 2天 |
| P0-6 | Construction 层 rollback/ 实现 | L2 构建层 | 2天 |
| P0-7 | 六步流水线处理器实现 | L2 构建层 | 8天 |
| P0-8 | 统一审计集成 | L2 构建层 | 2天 |
| P0-9 | 实现 UnifiedRetrieveEngine | L3 推理层 | 3天 |
| P0-10 | 扩展 QueryResult 添加溯源字段 | L3 推理层 | 1天 |
| P0-11 | 创建 ProvenanceLinker (4级溯源链) | L3 推理层 | 2天 |
| P0-12 | 统一 NL 检索 API | L3 推理层 | 1天 |
| P0-13 | 实现 ReasoningServiceContract | L3 推理层 | 3天 |
| P0-14 | 合并三套AI助手为 UnifiedChatService | L4 应用层 | 5天 |
| P0-15 | 实现 GenBI 工具 | L4 应用层 | 3天 |
| P0-16 | 实现决策推演工具 | L4 应用层 | 5天 |
| P0-17 | 实现执行策略引擎 | L4 应用层 | 3天 |
| P0-18 | 端到端测试 + 回归测试 | L5 质量 | 3天 |

**P0总工期**: 约 50 人天（可按并行团队缩短）

### 7.3 推荐执行顺序

```
Week 1-2: 基础补全
  Sprint 1: P0-1~P0-3 (L1 设计层)
  Sprint 2: P0-4~P0-6 (L2 基础设施)

Week 3-4: 构建链路
  Sprint 3: P0-7 (六步流水线, 核心工作量)
  Sprint 4: P0-8~P0-12 (审计+推理检索+溯源)

Week 5-6: 推理+应用
  Sprint 5: P0-13~P0-14 (推理服务+AI助手统一)
  Sprint 6: P0-15~P0-17 (GenBI+决推演+执行策略)

Week 7: 质量验证
  Sprint 7: P0-18 (端到端测试+回归)
```

### 7.4 关键验收标准

| 维度 | 验收标准 |
|------|---------|
| **可溯源** | 检索结果包含4级溯源链（原始文档→提取→构建→图谱） |
| **可审计** | 构建流水线6步每步有审计记录 |
| **可回溯** | 支持版本级/pipeline级/batch级三级回滚 |
| **功能完整** | L1设计→L2构建→L3推理→L4应用 全链路可用 |
| **质量保证** | 单元测试覆盖率 > 80%，集成测试全绿 |
| **协议统一** | 全平台使用统一AG-UI + CUSTOM扩展 |

---

## 附录A：关键文件索引

| 文件 | 路径 | 说明 |
|------|------|------|
| ADR-068 | `docs/07-adr/ADR-068_本体模块四层分层架构.md` | 四层架构决策 |
| ADR-069 | `docs/07-adr/ADR-069_统一AI助手与智能问答服务.md` | 统一AI助手 |
| ADR-070 | `docs/07-adr/ADR-070_基于OpenHarness全能力的AI助手架构.md` | OpenHarness全能力 |
| Design Contract | `odap/biz/core/ontology/design/contract/interface.py` | L1设计契约 |
| Construction Contract | `odap/biz/core/ontology/construction/contract/interface.py` | L2构建契约 |
| Reasoning Contract | `odap/biz/core/ontology/reasoning/contract/interface.py` | +AI推理契约 |
| QueryService | `odap/infra/query/service.py` | 统一查询服务 |
| NLDispatcher | `odap/biz/core/ontology/application/query_api/nl_dispatcher.py` | NL查询调度 |
| UnifiedChatService | `odap/biz/core/chat/engine/unified_chat_service.py` | 统一对话引擎 |
| QARetrieverTool | `odap/biz/core/chat/tools/qa_retriever_tool.py` | RAG检索工具 |
| ProvenanceTracker | `odap/biz/data/hyper_extract/impl/provenance_tracker.py` | 溯源追踪 |
| AuditRecorderImpl | `odap/biz/core/ontology/design/engine/impl/audit_recorder_impl.py` | 审计记录器 |
| KnowledgeBaseService | `odap/biz/data/knowledge_base/services/knowledge_base_service.py` | 知识库服务 |
| GraphManager | `odap/infra/graph/graph_service.py` | 图管理器 |
| PipelineService | `odap/biz/core/ontology/design/services/pipeline_service.py` | 构建流水线 |

## 附录B：ADR-XXX（待创建）

本审计报告建议创建以下新ADR：

1. **ADR-073**: UnifiedRetrieveEngine设计 — 统一检索入口 + 跨源联邦 + 溯源链
2. **ADR-074**: ProvenanceChain设计 — 4级溯源链数据模型与存储
3. **ADR-075**: 六步构建流水线设计 — 每步的输入/输出/审计/溯源规范
4. **ADR-076**: 质量门禁体系设计 — 前置/中置/后置三级门禁规则
5. **ADR-077**: GenBI能力设计 — NL→图表→报表的完整链路
6. **ADR-078**: 决策推演引擎设计 — 多方案模拟+对比+风险评估
7. **ADR-079**: 执行策略引擎设计 — 自动/审批/定时三种模式
