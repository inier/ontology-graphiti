"""Semantic Retrieval 请求/响应 schema (spec 008 / data-model.md)。

仅定义对外契约的 Pydantic 模型，不包含业务逻辑。Constitution I：保持简单。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 分项检索类型枚举（字符串字面量，避免引入 Enum 增加耦合）
# ---------------------------------------------------------------------------
RETRIEVAL_TYPES = ("chain", "nl", "mdl", "graph", "metric")


class SearchComponent(BaseModel):
    """混合检索中的一个组件编排单元。"""

    type: str = Field(..., description="检索类型: chain|nl|mdl|graph|metric")
    params: Dict[str, Any] = Field(default_factory=dict, description="该组件的入参")


class SearchRequest(BaseModel):
    """统一/分项检索请求。

    - 统一检索：仅提供 `query`，`mode="auto"`（默认）由路由器自动选择。
    - 分项检索：`mode` 显式指定 chain|nl|mdl|graph|metric。
    - 混合检索：使用 HybridRequest（见下），不使用本模型。
    """

    query: str = Field(..., description="自然语言或结构化查询")
    mode: str = Field(default="auto", description="auto|chain|nl|mdl|graph|metric")
    limit: int = Field(default=20, ge=1, le=200, description="返回上限")
    top_k: Optional[int] = Field(default=None, ge=1, le=200, description="候选召回数")
    context: Dict[str, Any] = Field(
        default_factory=dict, description="附加上下文（如 entity_id / time_window）"
    )


class ComponentResult(BaseModel):
    """单个检索组件的执行结果。"""

    type: str = Field(..., description="产生该结果的检索类型")
    status: str = Field(
        default="ok", description="ok|skipped|degraded|error"
    )
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = Field(default=0)
    explain: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SearchResult(BaseModel):
    """统一/分项/混合检索的统一响应。"""

    query: str = Field(..., description="原始查询")
    mode: str = Field(..., description="实际执行的模式")
    total: int = Field(default=0, description="合并后总条数")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="合并后结果集")
    components: List[ComponentResult] = Field(
        default_factory=list, description="各组件明细（混合检索时 >1）"
    )
    explain: Optional[Dict[str, Any]] = None


class HybridRequest(BaseModel):
    """混合检索请求：显式编排多个组件。"""

    components: List[SearchComponent] = Field(
        ..., min_length=1, max_length=10, description="编排组件（1-10 个）"
    )
    merge: str = Field(
        default="concat", description="合并策略: concat|interleave|rank"
    )
    limit: int = Field(default=20, ge=1, le=200)


class MetricRequest(BaseModel):
    """指标查询请求（spec FR-006 / SC-002）。"""

    metric: str = Field(..., description="指标名: instance_count|relation_density|...")
    object_type: Optional[str] = Field(default=None, description="按对象类型过滤")
    time_window: Optional[str] = Field(default=None, description="时间窗口")
    granularity: Optional[str] = Field(
        default=None, description="聚合粒度: day|week|month"
    )
