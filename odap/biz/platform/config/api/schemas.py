"""配置管理 API 请求/响应模型"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ConfigItemUpdate(BaseModel):
    key: str
    value: str = ""


class UpdateConfigRequest(BaseModel):
    items: List[ConfigItemUpdate]
    test_connection: bool = False


class ConfigItemResponse(BaseModel):
    key: str
    display_value: Optional[str] = None
    value_type: str = "string"
    label: str = ""
    description: str = ""
    is_sensitive: bool = False
    is_required: bool = False
    default_value: Optional[str] = None
    choices: List[str] = Field(default_factory=list)
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    sort_order: int = 0
    group: str = ""
    has_value: bool = False


class ServiceConfigResponse(BaseModel):
    category: str
    label: str = ""
    description: str = ""
    icon: str = ""
    items: List[ConfigItemResponse] = Field(default_factory=list)
    connection_status: str = "unknown"
    last_tested_at: Optional[str] = None
    last_error: Optional[str] = None


class ConfigValidationResultResponse(BaseModel):
    category: str
    success: bool = False
    message: str = ""
    response_time_ms: int = 0
    tested_at: str = ""


class UpdateConfigResponse(BaseModel):
    status: str
    saved_count: int = 0
    revision_number: int = 0
    validation_results: List[ConfigValidationResultResponse] = Field(default_factory=list)
    message: Optional[str] = None


class TestConnectionRequest(BaseModel):
    categories: List[str] = Field(default_factory=list)
    items: Optional[List[ConfigItemUpdate]] = None


class RollbackRequest(BaseModel):
    revision_number: int


class ImportConfigRequest(BaseModel):
    items: List[ConfigItemUpdate]


class ConfigHistoryResponse(BaseModel):
    revisions: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class ConfigStatusItem(BaseModel):
    category: str
    label: str = ""
    connection_status: str = "unknown"
    item_count: int = 0
    configured_count: int = 0
    required_count: int = 0
