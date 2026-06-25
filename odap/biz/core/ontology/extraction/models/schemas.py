"""Extraction API request/response schemas."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ExtractionType(str, Enum):
    DATABASE = "database"
    NATURAL_LANGUAGE = "natural_language"
    KNOWLEDGE_BASE = "knowledge_base"


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"


class DatabaseConnectionRequest(BaseModel):
    """数据库连接请求"""
    db_type: str = Field(..., description="数据库类型: mysql/postgresql/sqlite")
    host: str = "localhost"
    port: int = 0
    database: str = Field(..., description="数据库名或文件路径")
    username: Optional[str] = None
    password: Optional[str] = None


class DatabaseTestConnectionResponse(BaseModel):
    """数据库连接测试响应"""
    status: str
    message: str = ""
    table_count: int = 0
    schema_name: str = ""


class DatabaseExtractionRequest(BaseModel):
    """数据库抽取请求"""
    ontology_id: str = Field(..., description="目标本体ID")
    db_type: str
    host: str = "localhost"
    port: int = 0
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    table_filter: List[str] = Field(default_factory=list)
    use_llm_enrichment: bool = False


class NLExtractionRequest(BaseModel):
    """自然语言提取请求"""
    ontology_id: str = Field(..., description="目标本体ID")
    text: str = Field(..., min_length=1, description="自然语言需求描述")
    auto_search: bool = False
    source_type: str = Field(default="text", description="来源类型: text/document/knowledge_base")
    template_id: Optional[str] = Field(default=None, description="指定 HE 模板 ID")
    method: Optional[str] = Field(default=None, description="HE 提取方法: graph_rag/light_rag/auto")


class ExtractionSessionResponse(BaseModel):
    """抽取会话响应"""
    session_id: str
    ontology_id: str
    extraction_type: str
    status: ExtractionStatus = ExtractionStatus.PENDING
    message: str = ""
    result_data: Optional[Dict[str, Any]] = None
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = ""
    template_used: Optional[str] = Field(default=None, description="使用的 HE 模板名称")
    provenance_summary: Optional[Dict[str, Any]] = Field(default=None, description="溯源摘要")


class ExtractionConfirmRequest(BaseModel):
    """抽取确认请求"""
    selected_type_ids: List[str] = Field(default_factory=list, description="选择导入的类型ID，空=全部导入")
    merge_strategy: str = "skip"  # skip / overwrite / rename


class KBExtractionRequest(BaseModel):
    """知识库提取请求"""
    ontology_id: str = Field(..., description="目标本体ID")
    kb_id: str = Field(..., description="知识库ID")
    document_ids: Optional[List[str]] = Field(default=None, description="指定文档ID列表，空=全部文档")
    template_id: Optional[str] = Field(default=None, description="指定 HE 模板 ID")
    method: Optional[str] = Field(default=None, description="HE 提取方法: graph_rag/light_rag/auto")
    batch_size: int = Field(default=10, description="批量处理文档数")
