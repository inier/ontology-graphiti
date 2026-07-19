"""MetricDefinition — 指标定义模型。

指标是对本体 Property 的高级抽象，支持:
- 数值聚合（SUM/AVG/COUNT/...）
- 自定义公式计算
- 多 Property 组合
- 与 Property 双向绑定
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class AggregationFunction(str, Enum):
    """聚合函数"""
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT_DISTINCT = "count_distinct"
    RATIO = "ratio"
    CUSTOM = "custom"


class MetricBinding(BaseModel):
    """指标与本体属性的绑定关系。

    定义指标计算所需的数据来源。
    """
    source_entity_type_id: str = Field(..., description="来源实体类型ID")
    source_property_id: str = Field(..., description="来源属性ID")
    aggregation: AggregationFunction = Field(
        default=AggregationFunction.COUNT,
        description="聚合方式"
    )
    filter_condition: Optional[str] = Field(
        default=None,
        description="过滤条件（OPA表达式），如 'status == \"active\"'"
    )
    weight: float = Field(default=1.0, description="权重系数")
    alias: str = Field(default="", description="在公式中的别名")


class MetricDefinition(BaseModel):
    """指标定义模型。

    指标是本体 Property 的高级语义抽象。通过 MetricBinding 关联
    到底层 Property，支持数值聚合和自定义公式。
    """
    metric_id: str = Field(..., description="指标唯一ID")
    name: str = Field(..., description="指标名称（中文），如 '势力人口'")
    name_en: str = Field(default="", description="指标英文名，如 'FactionPopulation'")
    description: str = Field(default="", description="指标描述")

    # 领域信息
    domain: str = Field(default="", description="领域，如 military/economy")
    tags: List[str] = Field(default_factory=list, description="标签列表")

    # 计算绑定
    bindings: List[MetricBinding] = Field(
        default_factory=list,
        description="指标依赖的属性绑定列表"
    )
    formula: Optional[str] = Field(
        default=None,
        description="自定义公式（使用 alias 引用绑定），如 'A.avg + B.avg * 0.5'"
    )

    # 输出配置
    unit: str = Field(default="", description="单位，如 '万人', '%', '元'")
    precision: int = Field(default=2, description="数值精度（小数位数）")
    trend_direction: str = Field(default="neutral", description="趋势方向: up/down/neutral")

    # 版本
    version: str = Field(default="1.0.0", description="指标版本")
    ontology_id: Optional[str] = Field(default=None, description="所属本体ID")

    class Config:
        use_enum_values = True


__all__ = [
    "AggregationFunction",
    "MetricBinding",
    "MetricDefinition",
]
