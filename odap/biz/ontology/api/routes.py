from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from ..services.ingest_service import IngestService
from ..services.build_service import get_builder_service

router = APIRouter(prefix="/api/ontology/ingest", tags=["ingest"])

# 创建全局摄入服务实例
ingest_service = IngestService()

# 数据模型
class NewsIngestRequest(BaseModel):
    data: Optional[str] = Field(default=None, description="新闻URL或检索关键词")
    event_context: str = Field(default="", description="事件背景")
    max_sources: int = Field(default=5, description="最大检索来源数")
    scenario_id: Optional[str] = Field(default=None, description="场景ID")

class ManualIngestRequest(BaseModel):
    data: Union[str, Dict[str, Any]] = Field(..., description="文本或表单数据")
    scenario_id: Optional[str] = Field(default=None, description="场景ID")

class JsonIngestRequest(BaseModel):
    data: str = Field(..., description="JSON字符串")
    scenario_id: Optional[str] = Field(default=None, description="场景ID")

class NaturalLanguageIngestRequest(BaseModel):
    data: str = Field(..., description="自然语言文本")
    scenario_id: Optional[str] = Field(default=None, description="场景ID")

class RandomEventsRequest(BaseModel):
    data: Dict[str, Any] = Field(..., description="随机事件参数")
    scenario_id: Optional[str] = Field(default=None, description="场景ID")

class IngestResponse(BaseModel):
    ingest_id: str = Field(..., description="摄入ID")
    status: str = Field(..., description="状态")
    source_details: Optional[Dict[str, Any]] = Field(default=None, description="数据源详细信息")
    original_content: Optional[str] = Field(default=None, description="原始内容")
    extracted_data: Optional[Dict[str, Any]] = Field(default=None, description="提取的数据")

class IngestStatusResponse(BaseModel):
    id: str
    source: str
    status: str
    record_count: int
    processed_count: int
    failed_count: int
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    errors: Optional[List[Dict[str, Any]]] = None

# API 路由
@router.post("", response_model=IngestResponse)
async def ingest_data(request: Dict[str, Any]):
    """数据摄入通用接口"""
    source_type = request.get("source_type")
    data = request.get("data")
    
    if source_type == "news":
        event_context = request.get("event_context", "")
        max_sources = request.get("max_sources", 5)
        scenario_id = request.get("scenario_id")
        # 自动判断是URL还是搜索关键词
        is_url = data.startswith(('http://', 'https://')) if data else False
        if is_url:
            ingest_id = await ingest_service.ingest_from_url(data, event_context, scenario_id)
        else:
            ingest_id = await ingest_service.ingest_from_news(data, event_context, max_sources, scenario_id)
    elif source_type == "manual":
        form_data = data or request.get("form_data", {})
        scenario_id = request.get("scenario_id")
        ingest_id = await ingest_service.ingest_from_manual(form_data, scenario_id)
    elif source_type == "json":
        json_data = data or request.get("json_data")
        scenario_id = request.get("scenario_id")
        ingest_id = await ingest_service.ingest_from_json(json_data, scenario_id)
    elif source_type == "natural_language":
        text = data or request.get("text")
        scenario_id = request.get("scenario_id")
        ingest_id = await ingest_service.ingest_from_natural_language(text, scenario_id)
    elif source_type == "random":
        parties = request.get("parties") or (isinstance(data, dict) and data.get("parties"))
        scenario_context = request.get("scenario_context") or (isinstance(data, dict) and data.get("scenario_context"))
        count = request.get("count", 1) or (isinstance(data, dict) and data.get("count", 1))
        scenario_id = request.get("scenario_id")
        ingest_id = await ingest_service.generate_random_events(parties, scenario_context, count, scenario_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid source type")
    
    ingest_record = ingest_service.get_ingest_status(ingest_id)
    status = ingest_record.get("status")
    return IngestResponse(
        ingest_id=ingest_id,
        status=status,
        source_details=ingest_record.get("source_details"),
        original_content=ingest_record.get("original_content"),
        extracted_data=ingest_record.get("extracted_data")
    )

@router.post("/news", response_model=IngestResponse)
async def ingest_from_news(request: NewsIngestRequest):
    """从新闻摄入数据

    支持两种输入模式:
    1. URL模式: 直接传入新闻网页URL，使用免费网页抓取方案
    2. 检索模式: 传入关键词，使用搜索引擎检索（需要API Key）
    """
    if not request.data:
        raise HTTPException(status_code=400, detail="必须提供 data 参数")
    
    # 自动判断是URL还是搜索关键词
    is_url = request.data.startswith(('http://', 'https://'))
    if is_url:
        ingest_id = await ingest_service.ingest_from_url(
            request.data,
            request.event_context,
            request.scenario_id
        )
    else:
        ingest_id = await ingest_service.ingest_from_news(
            request.data,
            request.event_context,
            request.max_sources,
            request.scenario_id
        )

    ingest_record = ingest_service.get_ingest_status(ingest_id)
    status = ingest_record.get("status")
    return IngestResponse(
        ingest_id=ingest_id,
        status=status,
        source_details=ingest_record.get("source_details"),
        original_content=ingest_record.get("original_content"),
        extracted_data=ingest_record.get("extracted_data")
    )

@router.post("/manual", response_model=IngestResponse)
async def ingest_from_manual(request: ManualIngestRequest):
    """从手动输入摄入数据"""
    ingest_id = await ingest_service.ingest_from_manual(
        request.data,
        request.scenario_id
    )
    ingest_record = ingest_service.get_ingest_status(ingest_id)
    status = ingest_record.get("status")
    return IngestResponse(
        ingest_id=ingest_id,
        status=status,
        source_details=ingest_record.get("source_details"),
        original_content=ingest_record.get("original_content"),
        extracted_data=ingest_record.get("extracted_data")
    )

@router.post("/json", response_model=IngestResponse)
async def ingest_from_json(request: JsonIngestRequest):
    """从 JSON 摄入数据"""
    ingest_id = await ingest_service.ingest_from_json(
        request.data,
        request.scenario_id
    )
    ingest_record = ingest_service.get_ingest_status(ingest_id)
    status = ingest_record.get("status")
    return IngestResponse(
        ingest_id=ingest_id,
        status=status,
        source_details=ingest_record.get("source_details"),
        original_content=ingest_record.get("original_content"),
        extracted_data=ingest_record.get("extracted_data")
    )

@router.post("/natural-language", response_model=IngestResponse)
async def ingest_from_natural_language(request: NaturalLanguageIngestRequest):
    """从自然语言摄入数据"""
    ingest_id = await ingest_service.ingest_from_natural_language(
        request.data,
        request.scenario_id
    )
    ingest_record = ingest_service.get_ingest_status(ingest_id)
    status = ingest_record.get("status")
    return IngestResponse(
        ingest_id=ingest_id,
        status=status,
        source_details=ingest_record.get("source_details"),
        original_content=ingest_record.get("original_content"),
        extracted_data=ingest_record.get("extracted_data")
    )

@router.post("/random", response_model=IngestResponse)
async def generate_random_events(request: RandomEventsRequest):
    """生成随机事件"""
    ingest_id = await ingest_service.generate_random_events(
        request.data.get("parties"),
        request.data.get("scenario_context"),
        request.data.get("count", 1),
        request.scenario_id
    )
    ingest_record = ingest_service.get_ingest_status(ingest_id)
    status = ingest_record.get("status")
    return IngestResponse(
        ingest_id=ingest_id,
        status=status,
        source_details=ingest_record.get("source_details"),
        original_content=ingest_record.get("original_content"),
        extracted_data=ingest_record.get("extracted_data")
    )

# 构建相关 API
@router.get("/builds/{build_id}", response_model=Dict[str, Any])
async def get_build_status(build_id: str):
    """获取构建状态"""
    # 从摄入记录中查找构建信息
    ingest_records = ingest_service.get_ingest_history(100)
    for record in ingest_records:
        if 'builds' in record:
            for build in record['builds']:
                if build['build_id'] == build_id:
                    return {
                        "build_id": build['build_id'],
                        "status": build['status'],
                        "document_id": build['document_id'],
                        "version_info": build['version_info'],
                        "ingest_id": record['id']
                    }
    raise HTTPException(status_code=404, detail="Build not found")


@router.get("/builds", response_model=List[Dict[str, Any]])
async def get_build_history(limit: int = 50):
    """获取构建历史"""
    builds = []
    ingest_records = ingest_service.get_ingest_history(limit)
    for record in ingest_records:
        if 'builds' in record:
            for build in record['builds']:
                builds.append({
                    "build_id": build['build_id'],
                    "status": build['status'],
                    "document_id": build['document_id'],
                    "version_info": build['version_info'],
                    "ingest_id": record['id'],
                    "ingest_source": record['source'],
                    "ingest_time": record['start_time']
                })
    return builds


@router.post("/versions/rollback", response_model=Dict[str, Any])
async def rollback_version(version_id: str, scenario_id: str = "default"):
    """回滚到指定版本"""
    builder_service = get_builder_service()
    result = await builder_service.rollback_version(version_id, scenario_id)
    return result


@router.get("/versions", response_model=List[Dict[str, Any]])
async def get_versions(scenario_id: Optional[str] = None, limit: int = 50):
    """获取版本列表"""
    try:
        from odap.biz.ontology.storage.mongodb_storage import MongoDBStorage
        storage = MongoDBStorage()
        versions = storage.get_versions(scenario_id, limit)
        return versions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取版本列表失败: {str(e)}")


@router.get("/documents/list", response_model=List[Dict[str, Any]])
async def get_ontology_documents(scenario_id: Optional[str] = None, limit: int = 100):
    """获取本体文档列表"""
    documents = ingest_service.get_ontology_documents(scenario_id, limit)
    return [doc.to_dict() for doc in documents]


@router.get("/documents/{doc_id}", response_model=Dict[str, Any])
async def get_ontology_document(doc_id: str):
    """获取本体文档详情"""
    doc = ingest_service.get_ontology_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc.to_dict()


# 先定义根路径，再定义带参数的路径
@router.get("", response_model=List[IngestStatusResponse])
async def get_ingest_history(limit: int = 100):
    """获取摄入历史"""
    return ingest_service.get_ingest_history(limit)


@router.get("/{ingest_id}", response_model=IngestStatusResponse)
async def get_ingest_status(ingest_id: str):
    """获取摄入状态"""
    status = ingest_service.get_ingest_status(ingest_id)
    if not status:
        raise HTTPException(status_code=404, detail="Ingest record not found")
    return status