# NL Ontology Query Service Design

> Date: 2026-06-15
> Status: Draft
> Feature Branch: TBD

## 1. Overview

### 1.1 Problem Statement

ODAP 当前本体查询能力存在以下关键差距：

| 差距 | 现状 | 影响 |
|------|------|------|
| 检索质量 | SQLite/语义地图/模型存储使用简单 `in` 关键词匹配，非语义相似度 | 召回率低，无法理解同义词/近义词 |
| NL→查询转换 | NLDispatcher 仅 5 条回退规则，LLM 5s 超时 | 复杂查询转换失败率高 |
| 意图分类 | 仅 3 条正则规则 | 覆盖面窄，中文查询效果差 |
| RAG 质量 | 无重排序、无查询改写 | 结果排序不优，检索召回不足 |
| 图查询 | 仅支持预定义 neighbors/path/relations | 无法表达复杂图模式（多跳关联、聚合、嵌套过滤） |
| 对话管理 | 纯内存存储 | 进程重启后会话丢失 |
| 可审计性 | 无端到端查询审计 | 无法追踪查询链路 |
| 评估 | 无 QA/检索质量评估体系 | 无法量化改进效果 |

### 1.2 Design Goals

1. **三检索支柱**：BM25 精准关键词 + Vector 语义相似度 + Graph 关联知识推理
2. **五阶段管线**：Understanding → Planning → Execution → Fusion → Generation
3. **100% 可审计**：每次查询从输入到输出的完整链路可追溯
4. **充分复用**：Graphiti search_hybrid、OpenHarness Agent Loop、QueryService、GraphManager
5. **统一对外接口**：REST API + Skill 注册 + CLI 命令
6. **评估体系**：MRR/NDCG/F1 基准测试，量化改进效果
7. **前端增强**：查询建议、结果可视化、审计管理、评估仪表盘

### 1.3 Constraints

- 不重复实现现有功能，在现有组件上增强
- 遵循 biz 6 层架构（api/services/impl/interfaces/models/storage）
- 服务层返回 `Dict[str, Any]`，路由层翻译 HTTPException
- Enum 必须 `(str, Enum)` 双继承
- 容器字段必须 `Field(default_factory=...)`
- SQLite 无连接池，每次 connect/close
- 新增模块必须同步新增测试

---

## 2. Architecture

### 2.1 Overall Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     NL Ontology Query Service                       │
│                                                                     │
│  ┌─────────────┐   ┌──────────────┐   ┌───────────────────────┐   │
│  │  BM25 Pillar │   │ Vector Pillar│   │   Graph Pillar        │   │
│  │  精准关键词   │   │ 语义相似度    │   │  关联知识推理          │   │
│  │  (新增)      │   │ (复用Graphiti│   │ (复用GraphManager     │   │
│  │              │   │  +增强)      │   │  +NL→Cypher新增)      │   │
│  └──────┬───────┘   └──────┬───────┘   └──────────┬────────────┘   │
│         │                  │                       │                │
│         └──────────────────┼───────────────────────┘                │
│                            │                                        │
│  ┌─────────────────────────▼─────────────────────────────────────┐ │
│  │                    五阶段查询管线                               │ │
│  │  Understanding → Planning → Execution → Fusion → Generation   │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  对外统一接口: REST API + Skill 注册 + CLI                     │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Five-Stage Pipeline

| Stage | Responsibility | Input | Output |
|-------|---------------|-------|--------|
| **Understanding** | 意图识别 + 实体提取 + 查询改写 | 自然语言 | `QueryUnderstanding` |
| **Planning** | 选择检索支柱 + 生成查询计划 | `QueryUnderstanding` | `QueryPlan` |
| **Execution** | 并行执行子查询 | `QueryPlan` | 各支柱原始结果 |
| **Fusion** | 多源结果融合 + rerank | 原始结果 | 排序后的统一结果集 |
| **Generation** | LLM 生成回答 + 溯源 | 排序结果 + 原始查询 | 最终回答 + 来源引用 |

### 2.3 Relationship with Existing Components

| Existing Component | Treatment |
|-------------------|-----------|
| `QAEngineV2` | **Refactor**: Split into five-stage pipeline, core logic preserved, eliminate 2680-line monolith |
| `RAGPipeline` | **Refactor**: Four-source retrieval → three-pillar, keyword matching → BM25 |
| `NLDispatcher` | **Merge into** Understanding stage, NL→DSL/Cypher becomes part of Planning |
| `IntentClassifier` | **Enhance**: Expand rule base + Chinese prompt + fine-grained intent |
| `QueryService` | **Preserve**: Unified execution entry for Execution stage |
| `GraphManager` | **Preserve**: Underlying for Graph Pillar |
| `DialogManager` | **Enhance**: Add SQLite persistence |
| `SemanticObjectRetriever` | **Merge into** Vector Pillar |
| `ask_with_tools` | **Delegate to** OpenHarness `GraphitiAgentLoop` |
| `ask_with_oadp` | **Preserve**: ACTION intent branch in `QueryPipeline.query()` |

---

## 3. Three Retrieval Pillars

### 3.1 BM25 Pillar — Precise Keyword Retrieval (New)

**Goal**: Replace simple `in` keyword matching in SQLite/SemanticMap/ModelStorage with professional BM25 ranking.

**Implementation**: `rank_bm25` library (pure Python, no external dependencies)

**File Structure**:
```
odap/biz/data/qa/retrieval/
├── bm25_retriever.py          # BM25Retriever
└── bm25_index.py              # BM25IndexManager (index build + persist + incremental update)
```

**Core Design**:
- **Index Management**: Partitioned by `workspace_id + scenario_id`, supports incremental updates
- **Chinese Tokenization**: Reuse existing `_tokenize_chinese` + optional jieba enhancement
- **Data Source**: Build document corpus from SQLiteIngestStorage / SemanticMapStorage / ModelStorage
- **Persistence**: Serialize index to `data/bm25_indices/{ws_id}_{scenario_id}.pkl`
- **Graphiti Independence**: Works without Neo4j/Graphiti

**Interface**:
```python
class BM25Retriever:
    def search(self, query: str, top_k: int = 10,
               filters: Optional[Dict] = None) -> List[RetrievalResult]
    def build_index(self, workspace_id: str, scenario_id: Optional[str] = None)
    def update_index(self, workspace_id: str, doc: Document)  # Incremental
```

**RetrievalResult** (unified across all pillars):
```python
class RetrievalResult(BaseModel):
    doc_id: str
    content: str
    score: float
    pillar: str                          # "bm25" | "vector" | "graph"
    source: str                          # "sqlite" | "graphiti" | "semantic_map" | "model_storage" | "cypher"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    entities: List[str] = Field(default_factory=list)
    relations: List[str] = Field(default_factory=list)
```

### 3.2 Vector Pillar — Semantic Similarity Retrieval (Reuse Graphiti + Enhance)

**Goal**: Leverage Graphiti's `search_hybrid` as primary path, add query rewriting for better recall.

**Reuse Strategy**:
- **Primary**: `GraphitiClient.search_hybrid(query, top_k)` — vector + full-text hybrid
- **Fallback**: `GraphManager.search(query, limit)` — Neo4j CONTAINS
- **Unavailable**: `BM25Retriever.search()` — pure keyword fallback

**Enhancement**:
```
odap/biz/data/qa/retrieval/
├── vector_retriever.py        # VectorRetriever (wraps Graphiti search_hybrid)
└── query_rewriter.py          # QueryRewriter (HyDE + Multi-Query)
```

**QueryRewriter**:
- **HyDE**: LLM generates hypothetical answer → embed hypothetical answer for retrieval
- **Multi-Query**: LLM decomposes original query into 3-5 sub-queries → retrieve separately → merge
- **Fallback**: Use original query when LLM unavailable

**Interface**:
```python
class VectorRetriever:
    def search(self, query: str, top_k: int = 10,
               rewrite: bool = True) -> List[RetrievalResult]

class QueryRewriter:
    def hyde_rewrite(self, query: str) -> str           # Returns hypothetical answer
    def multi_query(self, query: str) -> List[str]      # Returns sub-query list
```

### 3.3 Graph Pillar — Relational Knowledge Reasoning (Reuse GraphManager + NL→Cypher New)

**Goal**: Support complex graph pattern queries, natural language directly generates Cypher/graph traversal.

**Reuse Strategy**:
- **Simple graph queries**: `GraphManager.get_neighbors()` / `traverse()` — existing
- **Complex graph queries**: New NL→Cypher generator — new
- **Temporal queries**: `GraphManager.query_temporal()` — existing

**New Components**:
```
odap/biz/data/qa/retrieval/
├── graph_retriever.py         # GraphRetriever (unified graph query entry)
└── cypher_generator.py        # NL→Cypher generator
```

**CypherGenerator Design**:
- **LLM Generation**: Based on ontology schema (entity types / relation types) + user query → generate Cypher
- **Schema Injection**: Get current workspace ontology type definitions from `QueryService`, inject into prompt
- **Security Sandbox**: Generated Cypher only allows READ operations (MATCH/RETURN), prohibits WRITE (CREATE/DELETE/SET)
- **Timeout Protection**: Cypher execution 10s timeout
- **Fallback**: Predefined Cypher templates by intent type when LLM unavailable

**Interface**:
```python
class GraphRetriever:
    def search(self, query: str, top_k: int = 10,
               mode: str = "auto") -> List[RetrievalResult]
    # mode: "neighbors" | "traverse" | "cypher" | "auto"

class CypherGenerator:
    def generate(self, nl_query: str, schema: OntologySchema) -> str
    def validate(self, cypher: str) -> bool           # Security check
    def execute(self, cypher: str, params: Dict) -> List[Dict]
```

### 3.4 Unified Retriever

Three pillars expose a unified interface through `UnifiedRetriever`:

```python
class UnifiedRetriever:
    """Three-pillar unified retrieval - single external entry point"""

    def search(self, query: str, plan: QueryPlan) -> RetrievalResultSet:
        """Dispatch to pillars in parallel based on QueryPlan"""

    def search_simple(self, query: str, top_k: int = 10) -> RetrievalResultSet:
        """Simple retrieval - auto-select pillars"""

class RetrievalResultSet(BaseModel):
    results: List[RetrievalResult] = Field(default_factory=list)
    pillar_scores: Dict[str, float] = Field(default_factory=dict)    # Per-pillar contribution
    metadata: Dict[str, Any] = Field(default_factory=dict)           # Traceability metadata
```

---

## 4. Five-Stage Pipeline

### 4.1 File Structure

```
odap/biz/data/qa/
├── pipeline/                          # Five-stage pipeline (new)
│   ├── __init__.py
│   ├── query_pipeline.py              # QueryPipeline orchestrator
│   ├── understanding/                 # Stage 1: Query Understanding
│   │   ├── intent_recognizer.py       #   Intent recognition (enhanced IntentClassifier)
│   │   ├── entity_extractor.py        #   Entity extraction (from NL)
│   │   └── query_rewriter.py          #   Query rewriting (HyDE/Multi-Query)
│   ├── planning/                      # Stage 2: Query Planning
│   │   ├── query_planner.py           #   Generate QueryPlan (select pillars + sub-queries)
│   │   └── plan_templates.py          #   Predefined query plan templates
│   ├── execution/                     # Stage 3: Query Execution
│   │   ├── query_executor.py          #   Parallel sub-query execution
│   │   └── execution_context.py       #   Execution context (workspace/scenario/auth)
│   ├── fusion/                        # Stage 4: Result Fusion
│   │   ├── result_fuser.py            #   Multi-source result fusion
│   │   └── reranker.py               #   Cross-encoder reranking
│   └── generation/                    # Stage 5: Response Generation
│       ├── response_generator.py      #   LLM response generation
│       └── source_tracer.py           #   Source tracing (reuse existing SourceTracer)
├── retrieval/                         # Three-pillar retrieval (Section 3)
│   ├── unified_retriever.py
│   ├── bm25_retriever.py
│   ├── bm25_index.py
│   ├── vector_retriever.py
│   ├── graph_retriever.py
│   └── cypher_generator.py
├── dialog/                            # Dialog management (refactored)
│   ├── dialog_manager.py              #   Enhanced: SQLite persistence
│   └── dialog_storage.py              #   New: dialog persistence storage
├── evaluation/                        # Evaluation system (new)
│   ├── qa_evaluator.py                #   QA quality evaluation (EM/F1/Recall)
│   ├── retrieval_evaluator.py         #   Retrieval quality evaluation (MRR/NDCG)
│   └── benchmark_runner.py            #   Benchmark test runner
└── qa_engine.py                       # Refactored QAEngine (thin orchestration layer)
```

### 4.2 QueryPipeline Core

```python
class QueryPipeline:
    """Five-stage query pipeline - replaces QAEngineV2 core logic"""

    def __init__(self):
        self.understanding = UnderstandingStage()
        self.planning = PlanningStage()
        self.execution = ExecutionStage(UnifiedRetriever())
        self.fusion = FusionStage(Reranker())
        self.generation = GenerationStage()

    async def query(self, request: QueryRequest) -> QueryResponse:
        # Stage 1: Understanding
        understanding = self.understanding.analyze(request.query, request.context)

        # Stage 2: Planning
        plan = self.planning.create_plan(understanding, request.constraints)

        # Stage 3: Execution (parallel)
        raw_results = await self.execution.execute(plan, request.auth_context)

        # Stage 4: Fusion
        fused = self.fusion.merge_and_rerank(raw_results, understanding.query)

        # Stage 5: Generation
        response = await self.generation.generate(
            fused, understanding, request.query, stream=request.stream
        )
        return response

    async def search(self, request: QueryRequest) -> RetrievalResultSet:
        """Pure retrieval - no LLM generation, returns retrieval results only"""
        understanding = self.understanding.analyze(request.query, request.context)
        plan = self.planning.create_plan(understanding, request.constraints)
        raw_results = await self.execution.execute(plan, request.auth_context)
        return self.fusion.merge_and_rerank(raw_results, understanding.query)
```

### 4.3 Data Models

```python
class QueryIntent(str, Enum):
    KEYWORD_LOOKUP = "keyword_lookup"       # 精确查找（BM25 主导）
    SEMANTIC_SEARCH = "semantic_search"     # 语义搜索（Vector 主导）
    GRAPH_TRAVERSE = "graph_traverse"       # 图遍历（Graph 主导）
    COMPLEX_ANALYSIS = "complex_analysis"   # 复杂分析（多支柱协同）
    TEMPORAL_QUERY = "temporal_query"       # 时态查询（Graph 时态子路径）
    ACTION = "action"                       # 执行动作（委托 OpenHarness）

class QueryUnderstanding(BaseModel):
    original_query: str
    intent: QueryIntent
    extracted_entities: List[str] = Field(default_factory=list)
    rewritten_queries: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_reason: Optional[str] = None

class QueryPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pillars: List[str]                      # ["bm25", "vector", "graph"]
    sub_queries: List[SubQuery] = Field(default_factory=list)
    fusion_strategy: str = "weighted"       # "weighted" | "rrf" | "cascade"
    top_k: int = 10

class SubQuery(BaseModel):
    pillar: str                             # "bm25" | "vector" | "graph"
    query: str                              # Actual query for this pillar
    params: Dict[str, Any] = Field(default_factory=dict)
    mode: Optional[str] = None              # For graph: "neighbors" | "traverse" | "cypher"

class QueryResponse(BaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    answer: str
    sources: List[SourceReference] = Field(default_factory=list)
    understanding: QueryUnderstanding
    plan: QueryPlan
    pillar_contributions: Dict[str, float] = Field(default_factory=dict)
    total_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

## 5. External Interfaces

### 5.1 REST API

Enhance existing `/api/qa/` routes:

```python
# Existing (preserved)
POST /api/qa/ask                    # Sync QA (internally uses QueryPipeline)
POST /api/qa/ask/stream             # Streaming QA
POST /api/qa/ask/temporal           # Temporal QA

# New
POST /api/qa/search                 # Pure retrieval (no LLM generation)
POST /api/qa/plan                   # Query plan preview (returns QueryPlan, no execution)
POST /api/qa/explain                # Query explanation (shows NL→query transformation)
POST /api/qa/evaluate               # Run evaluation benchmark
GET  /api/qa/retrieval/pillars      # View three-pillar status and index info

# Audit
GET  /api/qa/audit/{query_id}       # Query single audit detail
GET  /api/qa/audit                  # Query audit list (with filters)
GET  /api/qa/audit/stats            # Audit statistics
```

### 5.2 Skill Registration (Agent-callable)

Register to `odap/tools/SKILL_CATALOG`:

```python
{
    "nl_query": {
        "description": "自然语言本体查询 - 支持关键词/语义/图关联三模式检索",
        "handler": "odap.biz.data.qa.pipeline.query_pipeline.QueryPipeline.query",
        "parameters": {
            "query": {"type": "str", "required": True},
            "mode": {"type": "str", "enum": ["auto", "keyword", "semantic", "graph"]},
            "top_k": {"type": "int", "default": 10},
            "stream": {"type": "bool", "default": False}
        }
    },
    "nl_search": {
        "description": "自然语言纯检索 - 仅返回检索结果，不生成回答",
        "handler": "odap.biz.data.qa.pipeline.query_pipeline.QueryPipeline.search",
        "parameters": {
            "query": {"type": "str", "required": True},
            "mode": {"type": "str", "enum": ["auto", "keyword", "semantic", "graph"]},
            "top_k": {"type": "int", "default": 10}
        }
    },
    "nl_explain": {
        "description": "查询解释 - 展示 NL 如何被理解和转换为查询",
        "handler": "odap.biz.data.qa.pipeline.query_pipeline.QueryPipeline.explain",
        "parameters": {
            "query": {"type": "str", "required": True}
        }
    }
}
```

### 5.3 CLI

Extend `main.py`:

```bash
python main.py query "查找所有与孙悟空有关联的实体" --mode auto --top-k 10
python main.py query "孙悟空的敌人有哪些" --mode graph --explain
python main.py query --eval  # Run evaluation benchmark
```

---

## 6. Audit & Traceability

### 6.1 Audit Data Model

```python
class QueryAuditRecord(BaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)

    # Input
    user_id: str
    workspace_id: str
    scenario_id: Optional[str] = None
    original_query: str

    # Understanding stage
    intent: str
    extracted_entities: List[str] = Field(default_factory=list)
    rewritten_queries: List[str] = Field(default_factory=list)

    # Planning stage
    query_plan: Dict[str, Any] = Field(default_factory=dict)
    selected_pillars: List[str] = Field(default_factory=list)

    # Execution stage
    pillar_results_count: Dict[str, int] = Field(default_factory=dict)
    cypher_generated: Optional[str] = None
    execution_time_ms: Dict[str, float] = Field(default_factory=dict)

    # Fusion stage
    total_results_before_fusion: int = 0
    total_results_after_fusion: int = 0
    rerank_model: Optional[str] = None

    # Generation stage
    response_length: int = 0
    source_count: int = 0
    llm_model: str = ""
    total_time_ms: float = 0.0
```

### 6.2 Audit Write

- Reuse existing `unified_audit.py`, add `QUERY_AUDIT` audit type
- Async write after each query completes (`asyncio.create_task`, non-blocking)
- Audit records stored in SQLite, partitioned by `workspace_id`

### 6.3 OpenHarness Integration for Audit

- Agent calls `nl_query` Skill → `QueryServiceWriteGuard` Hook auto-records audit
- AG-UI protocol layer ensures audit completeness through `agui_handler.py` OPA checkpoint
- `GraphitiMemoryAdapter` writes query history to Graphiti Episode for long-term traceable memory

---

## 7. Evaluation System

### 7.1 Metrics

| Dimension | Metric | Description |
|-----------|--------|-------------|
| **Retrieval** | MRR (Mean Reciprocal Rank) | Mean reciprocal rank of first relevant result |
| | NDCG@K | Normalized Discounted Cumulative Gain |
| | Recall@K | Recall in top-K results |
| **QA** | EM (Exact Match) | Exact match rate |
| | F1 | Precision/Recall harmonic mean |
| | Faithfulness | Answer-source consistency (RAGAS) |
| **E2E** | Latency P50/P95 | Query latency percentiles |
| | Pillar Coverage | Per-pillar usage distribution |

### 7.2 Benchmark Dataset

```python
class BenchmarkDataset(BaseModel):
    name: str
    workspace_id: str
    scenario_id: Optional[str] = None
    cases: List[BenchmarkCase] = Field(default_factory=list)

class BenchmarkCase(BaseModel):
    query: str
    expected_intent: str
    expected_entities: List[str] = Field(default_factory=list)
    relevant_doc_ids: List[str] = Field(default_factory=list)
    reference_answer: Optional[str] = None
```

### 7.3 Benchmark Runner

```python
class BenchmarkRunner:
    def run(self, dataset: BenchmarkDataset) -> EvaluationReport
    def run_retrieval_only(self, dataset) -> RetrievalReport
    def run_qa_only(self, dataset) -> QAReport
```

Storage: `data/evaluation/benchmarks/` + SQLite evaluation results table.

---

## 8. Frontend Enhancements

### 8.1 File Structure

```
frontend/src/modules/qa/
├── pages/
│   ├── QueryPage.tsx                   # New: Unified query page
│   └── EvaluationPage.tsx              # New: Evaluation management page
├── components/
│   ├── QueryInput.tsx                  # Enhanced: Mode selection + query suggestions
│   ├── QueryResultList.tsx             # Enhanced: Pillar source tags + traceability links
│   ├── QueryPlanViewer.tsx             # New: Query plan visualization
│   ├── QueryAuditTimeline.tsx          # New: Audit timeline
│   ├── PillarStatusPanel.tsx           # New: Three-pillar status panel
│   ├── RetrievalResultCard.tsx         # New: Retrieval result card (with pillar tag)
│   ├── CypherPreview.tsx               # New: Cypher preview (Graph mode)
│   └── EvaluationDashboard.tsx         # New: Evaluation dashboard
└── services/
    └── qaApi.ts                        # Enhanced: New API calls
```

### 8.2 Key Interactions

1. **Query Input**: Mode toggle (auto/keyword/semantic/graph), query suggestions, advanced options (top_k, time range, entity type filter)
2. **Result Display**: Per-result pillar tag (BM25/Vector/Graph) + confidence, click-to-trace, graph visualization (G6)
3. **Query Explanation Panel**: Full chain NL→intent→plan→execution, Cypher preview, per-pillar latency
4. **Audit Management**: Timeline view, detail drill-down, statistics dashboard
5. **Evaluation Management**: Dataset CRUD, one-click evaluation, report visualization (MRR/NDCG/F1 trends)

---

## 9. OpenHarness & Graphiti Reuse

### 9.1 OpenHarness Reuse

| Capability | Reuse Method |
|-----------|-------------|
| QueryEngine Agent Loop | `ask_with_tools` delegates to OH, no more self-built ReAct |
| ToolRegistry | `nl_query` / `nl_search` / `nl_explain` registered as OH Tools |
| HookExecutor | UserPromptSubmit Hook injects RAG context |
| Memory (GraphitiMemoryAdapter) | Query history persisted as Graphiti Episode |
| Permission (OPAPermissionBackend) | Write operation audit + query access control |
| AG-UI Protocol | Streaming query results via AG-UI SSE |
| DecisionEngine | Rule-based fallback when LLM unavailable |

### 9.2 Graphiti Reuse

| Capability | Reuse Method |
|-----------|-------------|
| search_hybrid | Vector Pillar primary path (vector + full-text hybrid) |
| add_episode | Query history write + dialog memory persistence |
| query_temporal | Graph Pillar temporal query sub-path |
| Embedder (bge-m3) | Unified vector embedding, shared by BM25 and Vector |
| EntityEdge | Retrieval result standardization (fact + source/target node) |

---

## 10. QAEngineV2 Refactor Strategy

### 10.1 Component Migration Map

| Original Component | Treatment | New Location |
|-------------------|-----------|-------------|
| `QAEngineV2.ask()` | Split into five stages | `QueryPipeline.query()` |
| `RAGPipeline` | Split into three pillars | `retrieval/unified_retriever.py` |
| `MultiHopPlanner/Executor` | Merge into Planning + Execution | `planning/query_planner.py` |
| `DialogManager` | Enhance + persist | `dialog/dialog_manager.py` |
| `TemporalReasoner` | Preserve as Graph Pillar sub-module | `retrieval/graph_retriever.py` |
| `SourceTracer` | Preserve | `generation/source_tracer.py` |
| `ChartRenderer` | Preserve | `generation/chart_renderer.py` |
| `_resolve_coreferences` | Enhance | `understanding/entity_extractor.py` |
| `_needs_clarification` | Merge into Understanding | `understanding/intent_recognizer.py` |
| `ask_with_tools` | Delegate to OpenHarness | Remove, delegate to `GraphitiAgentLoop` |
| `ask_with_oadp` | Preserve | `QueryPipeline.query()` ACTION intent branch |

### 10.2 Backward Compatibility

- `QAEngineV2` becomes a thin orchestration layer, external API signatures unchanged
- Existing `/api/qa/ask` and `/api/qa/ask/stream` continue to work
- New features exposed through new endpoints (`/api/qa/search`, `/api/qa/plan`, etc.)

---

## 11. Implementation Phases

### Phase 1: Foundation (BM25 + Pipeline Skeleton)

- Implement `BM25Retriever` and `BM25IndexManager`
- Create `QueryPipeline` skeleton with five stages
- Implement `UnderstandingStage` (enhanced IntentClassifier + EntityExtractor)
- Implement `PlanningStage` (basic QueryPlanner)
- Add `QueryAuditRecord` and audit write
- Unit tests for all new components

### Phase 2: Vector Enhancement (Query Rewriting + Reranking)

- Implement `QueryRewriter` (HyDE + Multi-Query)
- Implement `VectorRetriever` (wrapping Graphiti search_hybrid)
- Implement `Reranker` (cross-encoder or LLM-based)
- Implement `ResultFuser` (weighted/RRF fusion)
- Integration tests with Graphiti

### Phase 3: Graph Intelligence (NL→Cypher + Graph Retrieval)

- Implement `CypherGenerator` (LLM + template fallback)
- Implement `GraphRetriever` (unified graph query entry)
- Implement `QueryExecutor` (parallel execution)
- Security validation for Cypher sandbox
- Integration tests with Neo4j

### Phase 4: Frontend + Evaluation

- Implement frontend query page and components
- Implement evaluation system (BenchmarkRunner + evaluators)
- Implement audit management UI
- End-to-end tests

### Phase 5: Skill Registration + CLI + Polish

- Register `nl_query` / `nl_search` / `nl_explain` to SKILL_CATALOG
- Implement CLI commands
- QAEngineV2 refactor completion
- Performance optimization
- Documentation
