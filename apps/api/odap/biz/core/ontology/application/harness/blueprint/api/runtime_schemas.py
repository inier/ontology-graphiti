from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, Any, Optional


class DictResponse(BaseModel):
    """Flexible response model that accepts arbitrary dict shapes from service layer.

    Uses ``extra="allow"`` to remain backward compatible with all existing
    service-layer dicts while still being a proper Pydantic model (eliminates
    ``response_model=dict`` usage).
    """
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = None
    message: Optional[str] = None


class StartExecutionRequest(BaseModel):
    execution_id: str = Field(..., min_length=1)
    blueprint_id: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # 是否启用 ADR-074 数据流默认处理器（data_source->采集 / transform->HE抽取 / ontology->构建）。
    # 默认 True：HTTP 触发的蓝图执行默认走真实能力；测试/自定义场景可显式关闭。
    use_default_handlers: bool = True
