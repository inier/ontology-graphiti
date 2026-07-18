"""NL 本体查询服务 - 核心数据模型"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── 查询意图 ──────────────────────────────────────────────────────────

class QueryIntent(str, Enum):
    """查询意图枚举"""
    KEYWORD_LOOKUP = "keyword_lookup"       # 精确查找（BM25 主导）
    SEMANTIC_SEARCH = "semantic_search"     # 语义搜索（Vector 主导）
    GRAPH_TRAVERSE = "graph_traverse"       # 图遍历（Graph 主导）
    COMPLEX_ANALYSIS = "complex_analysis"   # 复杂分析（多支柱协同）
    TEMPORAL_QUERY = "temporal_query"       # 时态查询（Graph 时态子路径）
    ACTION = "action"                       # 执行动作（委托 OpenHarness）


# ── 检索支柱 ──────────────────────────────────────────────────────────

class RetrievalPillar(str, Enum):
    """检索支柱枚举"""
    BM25 = "bm25"       # 精准关键词
    VECTOR = "vector"   # 语义相似度
    GRAPH = "graph"     # 图关联推理


# ── 查询理解 ──────────────────────────────────────────────────────────

class QueryUnderstanding(BaseModel):
    """Stage 1 输出: 查询理解结果"""
    original_query: str
    intent: QueryIntent = QueryIntent.SEMANTIC_SEARCH
    extracted_entities: List[str] = Field(default_factory=list)
    rewritten_queries: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_reason: Optional[str] = None


# ── 查询计划 ──────────────────────────────────────────────────────────

class SubQuery(BaseModel):
    """子查询"""
    pillar: str                             # "bm25" | "vector" | "graph"
    query: str                              # 该支柱的实际查询
    params: Dict[str, Any] = Field(default_factory=dict)
    mode: Optional[str] = None              # graph 模式: "neighbors" | "traverse" | "cypher"


class FusionStrategy(str, Enum):
    """融合策略"""
    WEIGHTED = "weighted"   # 加权融合
    RRF = "rrf"             # Reciprocal Rank Fusion
    CASCADE = "cascade"     # 级联（先 BM25，不够再 Vector，再 Graph）


class QueryPlan(BaseModel):
    """Stage 2 输出: 查询计划"""
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pillars: List[str] = Field(default_factory=list)
    sub_queries: List[SubQuery] = Field(default_factory=list)
    fusion_strategy: FusionStrategy = FusionStrategy.WEIGHTED
    top_k: int = 10


# ── 检索结果 ──────────────────────────────────────────────────────────

class RetrievalResult(BaseModel):
    """统一检索结果（三支柱通用）"""
    doc_id: str
    content: str
    score: float
    pillar: str                              # "bm25" | "vector" | "graph"
    source: str                              # "sqlite" | "graphiti" | "semantic_map" | "model_storage" | "cypher"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    entities: List[str] = Field(default_factory=list)
    relations: List[str] = Field(default_factory=list)


class RetrievalResultSet(BaseModel):
    """检索结果集"""
    results: List[RetrievalResult] = Field(default_factory=list)
    pillar_scores: Dict[str, float] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── 来源引用 ──────────────────────────────────────────────────────────

class SourceReference(BaseModel):
    """来源引用"""
    doc_id: str
    content: str
    score: float
    pillar: str
    source: str
    entity_id: Optional[str] = None


# ── 查询请求/响应 ─────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """查询请求"""
    query: str
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    user_id: str = "anonymous"
    agent_id: Optional[str] = None
    mode: str = "auto"                      # "auto" | "keyword" | "semantic" | "graph"
    top_k: int = 10
    stream: bool = False
    context: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """查询响应"""
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    answer: str = ""
    sources: List[SourceReference] = Field(default_factory=list)
    understanding: Optional[QueryUnderstanding] = None
    plan: Optional[QueryPlan] = None
    pillar_contributions: Dict[str, float] = Field(default_factory=dict)
    total_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── 审计记录 ──────────────────────────────────────────────────────────

class QueryAuditRecord(BaseModel):
    """查询审计记录 - 五阶段全链路追踪"""
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)

    # 输入
    user_id: str = ""
    workspace_id: str = ""
    scenario_id: Optional[str] = None
    original_query: str = ""

    # Understanding 阶段
    intent: str = ""
    extracted_entities: List[str] = Field(default_factory=list)
    rewritten_queries: List[str] = Field(default_factory=list)

    # Planning 阶段
    query_plan: Dict[str, Any] = Field(default_factory=dict)
    selected_pillars: List[str] = Field(default_factory=list)

    # Execution 阶段
    pillar_results_count: Dict[str, int] = Field(default_factory=dict)
    cypher_generated: Optional[str] = None
    execution_time_ms: Dict[str, float] = Field(default_factory=dict)

    # Fusion 阶段
    total_results_before_fusion: int = 0
    total_results_after_fusion: int = 0
    rerank_model: Optional[str] = None

    # Generation 阶段
    response_length: int = 0
    source_count: int = 0
    llm_model: str = ""
    total_time_ms: float = 0.0
