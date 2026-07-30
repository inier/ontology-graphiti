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
    on_failure: str = Field(
        default="skip",
        description="失败容错策略: skip(跳过继续)|abort(中止全部)|degrade(降级返回)",
    )


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
    reasoning: Optional[Dict[str, Any]] = Field(
        default=None, description="chain/nl 模式下的推理链结果（FR-014）"
    )
    warnings: List[str] = Field(
        default_factory=list, description="性能/循环/降级等警告 (FR-008/FR-014)"
    )


# ---------------------------------------------------------------------------
# US3 链式推理 — ChainStep / RuleConflict / ReasoningChain / ChainRequest
# ---------------------------------------------------------------------------

class ChainStep(BaseModel):
    """推理链中的单个步骤（data-model.md §4 子结构）。"""

    step_id: str = Field(..., description="步骤唯一 ID")
    rule_id: str = Field(..., description="触发的规则 ID")
    input: str = Field(..., description="本步输入节点")
    output: str = Field(..., description="本步输出节点")
    duration_ms: int = Field(default=0, ge=0, description="本步耗时毫秒")


class RuleConflict(BaseModel):
    """规则冲突描述（data-model.md §4 子结构）。"""

    rule_a: str = Field(..., description="规则 A ID")
    rule_b: str = Field(..., description="规则 B ID")
    description: str = Field(..., description="冲突说明")


class ReasoningChain(BaseModel):
    """推理链执行结果（data-model.md §4，FR-014 必填）。"""

    chain_id: str = Field(..., description="推理链唯一 ID")
    steps: List[ChainStep] = Field(default_factory=list, description="步骤序列")
    conclusion: str = Field(default="", description="最终结论摘要")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="置信度（0-1）"
    )
    cycle_detected: bool = Field(
        default=False, description="是否检测到循环依赖（FR-014 必填）"
    )
    cycle_path: Optional[List[str]] = Field(
        default=None, description="循环路径（cycle_detected=true 时必填）"
    )
    conflicts: List[RuleConflict] = Field(
        default_factory=list, description="规则冲突列表"
    )


class ChainRequest(BaseModel):
    """链式推理请求（spec FR-004 / SC-003 / US3）。"""

    query: str = Field(..., description="链式推理的起始查询/起点节点")
    rules: List[str] = Field(
        default_factory=list, description="规则 ID 有序列表（传导路径）"
    )
    max_depth: int = Field(
        default=5, ge=1, le=10, description="推理链最大深度（硬上限 10，FR-014）"
    )


class MdlRequest(BaseModel):
    """MDL/DSL 推理请求（spec FR-004 / US3 / Q6 决策：禁止新发明 DSL）。

    query 多行字符串，复用 HE YAML 模板语法引用：
      template: {name}
      entity: {entity}
      params: {json_or_kv}
    """

    query: str = Field(
        ...,
        description=(
            "MDL 查询：多行字符串，首行必须 template: {name}，"
            "次行 entity: {entity}，可选 params: {json|kv}"
        ),
    )


class HybridRequest(BaseModel):
    """混合检索请求：显式编排多个组件。"""

    components: List[SearchComponent] = Field(
        ..., min_length=1, max_length=10, description="编排组件（1-10 个）"
    )
    merge: str = Field(
        default="concat", description="合并策略: concat|interleave|rank"
    )
    limit: int = Field(default=20, ge=1, le=200)


class TimeWindow(BaseModel):
    """时间窗口过滤（FR-015 趋势查询边界）。"""

    start: Optional[str] = Field(default=None, description="起始日期 (YYYY-MM-DD)")
    end: Optional[str] = Field(default=None, description="结束日期 (YYYY-MM-DD)")


class MetricRequest(BaseModel):
    """指标查询请求（spec FR-006 / SC-002 / US2 BI 工具）。"""

    metric: str = Field(..., description="指标名: count|density|trend (TBox 自动派生 Phase 1)")
    object_type: Optional[str] = Field(default=None, description="按对象类型过滤")
    time_window: Optional[TimeWindow] = Field(default=None, description="时间窗口（趋势查询边界）")
    granularity: Optional[str] = Field(
        default=None, description="聚合粒度: day|week|month"
    )
