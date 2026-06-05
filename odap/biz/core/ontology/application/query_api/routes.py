import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from ..services.ingest_service import IngestService

logger = logging.getLogger("ontology_routes")

from ..services.build_service import get_builder_service
from ..services.pipeline_service import get_pipeline_service

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

class TavilyIngestRequest(BaseModel):
    data: str = Field(..., description="搜索关键词")
    event_context: str = Field(default="", description="事件背景")
    max_sources: int = Field(default=5, description="最大检索来源数")
    search_depth: str = Field(default="basic", description="搜索深度: basic 或 advanced")
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
    source_details: Optional[Dict[str, Any]] = None
    status: str
    record_count: int
    processed_count: int
    failed_count: int
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    original_content: Optional[str] = None
    created_by: Optional[str] = None
    errors: Optional[List[Dict[str, Any]]] = None
    extracted_data: Optional[Dict[str, Any]] = None
    builds: Optional[List[Dict[str, Any]]] = None
    build_status: Optional[str] = Field(default=None, description="构建状态: none/pending/completed/failed/partial")

# API 路由
@router.post("", response_model=IngestResponse)
async def ingest_data(request: Dict[str, Any],
    user=Depends(get_current_user)):
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
    elif source_type == "tavily":
        event_context = request.get("event_context", "")
        max_sources = request.get("max_sources", 5)
        search_depth = request.get("search_depth", "basic")
        scenario_id = request.get("scenario_id")
        ingest_id = await ingest_service.ingest_from_tavily(data, event_context, max_sources, search_depth, scenario_id)
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
async def ingest_from_news(request: NewsIngestRequest,
    user=Depends(get_current_user)):
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
async def ingest_from_manual(request: ManualIngestRequest,
    user=Depends(get_current_user)):
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
async def ingest_from_json(request: JsonIngestRequest,
    user=Depends(get_current_user)):
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
async def ingest_from_natural_language(request: NaturalLanguageIngestRequest,
    user=Depends(get_current_user)):
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
async def generate_random_events(request: RandomEventsRequest,
    user=Depends(get_current_user)):
    """生成随机事件

    支持多种类型的随机事件生成：
    - military: 军事战争事件（进攻、巡逻、增援、撤退等）
    - business: 商业事件（投资、并购、产品发布等）
    - tech: 科技事件（技术突破、研发成果等）
    - healthcare: 医疗健康事件（新药研发、临床试验等）
    """
    generator_type = request.data.get("generator_type", "military")
    workspace_id = request.data.get("workspace_id", "default")
    ingest_id = await ingest_service.generate_random_events(
        request.data.get("parties"),
        request.data.get("scenario_context"),
        request.data.get("count", 1),
        request.scenario_id,
        generator_type,
        workspace_id
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

@router.get("/random/generators")
async def get_random_generator_types(user=Depends(get_current_user)):
    """获取所有可用的随机事件生成器类型"""
    return {
        "types": ingest_service.get_random_generator_types()
    }

@router.post("/tavily", response_model=IngestResponse)
async def ingest_from_tavily(request: TavilyIngestRequest,
    user=Depends(get_current_user)):
    """使用 Tavily API 摄入数据
    
    Tavily 是一个专门用于搜索和检索高质量内容的 API，
    特别适合用于新闻和文档检索。
    
    使用前请确保在 .env 文件中配置了 TAVILY_API_KEY
    获取 Key 地址: https://tavily.com
    """
    if not request.data:
        raise HTTPException(status_code=400, detail="必须提供 data 参数")
    
    if request.search_depth not in ["basic", "advanced"]:
        raise HTTPException(status_code=400, detail="search_depth 必须是 'basic' 或 'advanced'")
    
    # 检查 Tavily API Key 是否配置
    import os
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key or tavily_key == "your_tavily_api_key_here":
        raise HTTPException(
            status_code=400, 
            detail="请先配置 TAVILY_API_KEY 环境变量，获取地址: https://tavily.com"
        )
    
    ingest_id = await ingest_service.ingest_from_tavily(
        request.data,
        request.event_context,
        request.max_sources,
        request.search_depth,
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
async def get_build_status(build_id: str,
    user=Depends(get_current_user)):
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
async def get_build_history(limit: int = 50,
    user=Depends(get_current_user)):
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
async def rollback_version(version_id: str, scenario_id: str = "default",
    user=Depends(get_current_user)):
    """回滚到指定版本"""
    builder_service = get_builder_service()
    result = await builder_service.rollback_version(version_id, scenario_id)
    return result


@router.get("/versions", response_model=List[Dict[str, Any]])
async def get_versions(scenario_id: Optional[str] = None, limit: int = 50,
    user=Depends(get_current_user)):
    """获取版本列表"""
    try:
        versions = ingest_service.list_all_versions()
        return versions
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取版本列表失败: {str(e)}")


@router.get("/documents/list", response_model=List[Dict[str, Any]])
async def get_ontology_documents(scenario_id: Optional[str] = None, limit: int = 100,
    user=Depends(get_current_user)):
    """获取本体文档列表"""
    documents = ingest_service.get_ontology_documents(scenario_id, limit)
    return [doc.to_dict() for doc in documents]


@router.get("/documents/{doc_id}", response_model=Dict[str, Any])
async def get_ontology_document(doc_id: str,
    user=Depends(get_current_user)):
    """获取本体文档详情"""
    doc = ingest_service.get_ontology_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc.to_dict()


# 先定义根路径，再定义带参数的路径
@router.get("", response_model=List[IngestStatusResponse])
async def get_ingest_history(limit: int = 100, scenario_id: str = None,
    user=Depends(get_current_user)):
    """获取摄入历史，可按场景ID过滤"""
    return ingest_service.get_ingest_history(limit, scenario_id)


@router.get("/{ingest_id}", response_model=IngestStatusResponse)
async def get_ingest_status(ingest_id: str,
    user=Depends(get_current_user)):
    """获取摄入状态"""
    status = ingest_service.get_ingest_status(ingest_id)
    if not status:
        raise HTTPException(status_code=404, detail="Ingest record not found")
    return status


@router.get("/{ingest_id}/logs", response_model=List[Dict[str, Any]])
async def get_ingest_logs(ingest_id: str,
    user=Depends(get_current_user)):
    """获取摄入记录的处理日志（管道每阶段的记录）"""
    logs = ingest_service.get_process_logs(ingest_id)
    return logs


@router.get("/{ingest_id}/build-history", response_model=Dict[str, Any])
async def get_ingest_build_history(ingest_id: str,
    user=Depends(get_current_user)):
    """获取摄入记录的构建历史"""
    history = ingest_service.get_build_history(ingest_id)
    if not history:
        raise HTTPException(status_code=404, detail="Build history not found")
    return history


@router.get("/{ingest_id}/full", response_model=Dict[str, Any])
async def get_full_ingest_record(ingest_id: str,
    user=Depends(get_current_user)):
    """获取完整的摄入记录（包含状态、日志、构建历史）"""
    status = ingest_service.get_ingest_status(ingest_id)
    if not status:
        raise HTTPException(status_code=404, detail="Ingest record not found")

    logs = ingest_service.get_process_logs(ingest_id)
    build_history = ingest_service.get_build_history(ingest_id)

    return {
        **status,
        "logs": logs,
        "builds": build_history if build_history else []
    }


@router.post("/{ingest_id}/build", response_model=Dict[str, Any])
async def run_build_pipeline(ingest_id: str, scenario_id: Optional[str] = None,
    user=Depends(get_current_user)):
    """运行本体构建管道，包含所有6个阶段：数据采集、数据清洗、LLM归纳、本体构建、版本管理、图谱生成"""
    # 检查摄入记录是否存在
    status = ingest_service.get_ingest_status(ingest_id)
    if not status:
        raise HTTPException(status_code=404, detail="Ingest record not found")
    
    build_id = f"build-{ingest_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    import uuid
    ingest_service.save_build_history({
        "id": str(uuid.uuid4()),
        "ingest_id": ingest_id,
        "build_id": build_id,
        "version_id": None,
        "document_id": None,
        "entity_count": 0,
        "relation_count": 0,
        "event_count": 0,
        "status": "pending",
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "duration_seconds": 0.0
    })
    
    # 立即返回响应，表示构建已启动
    result = {
        "build_id": build_id,
        "status": "pending",
        "message": "Build started, check status via /api/ontology/ingest/{id}/full"
    }
    
    # 异步在后台执行构建
    async def run_build_async():
        try:
            # 获取管道服务
            pipeline_service = get_pipeline_service()
            
            # 获取摄入记录的原始内容
            ingest_status = ingest_service.get_ingest_status(ingest_id)
            source_details = {
                "content": ingest_status.get("original_content", "")
            }
            
            # 运行管道
            context = await pipeline_service.run(
                ingest_id,
                scenario_id or "default",
                source=ingest_status.get("source", "manual"),
                source_details=source_details
            )
            
            # 构建完成后更新构建历史
            end_time = datetime.now()
            # 修复日期时间不一致问题 - 使用相同的解析方式
            start_time_str = status.get('start_time')
            if start_time_str:
                # 处理带时区和不带时区的时间
                if start_time_str.endswith('Z'):
                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                else:
                    start_time = datetime.fromisoformat(start_time_str)
            else:
                start_time = datetime.now()
            duration_seconds = (end_time - start_time).total_seconds()
            
            build_record = {
                "id": str(uuid.uuid4()),
                "ingest_id": ingest_id,
                "build_id": build_id,
                "version_id": context.version_id,
                "document_id": context.document_id,
                "entity_count": context.stage_results.get("ontology", {}).get("entity_count", 0),
                "relation_count": context.stage_results.get("ontology", {}).get("relation_count", 0),
                "event_count": context.stage_results.get("llm", {}).get("event_count", 0),
                "status": "completed" if context.success else "failed",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration_seconds
            }
            ingest_service.save_build_history(build_record)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Build pipeline failed: {str(e)}")
            try:
                build_record = {
                    "id": str(uuid.uuid4()),
                    "ingest_id": ingest_id,
                    "build_id": build_id,
                    "version_id": None,
                    "document_id": None,
                    "entity_count": 0,
                    "relation_count": 0,
                    "event_count": 0,
                    "status": "failed",
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "duration_seconds": 0.0
                }
                ingest_service.save_build_history(build_record)
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Build history save failed: {e}")
    
    # 启动异步任务
    import asyncio
    asyncio.create_task(run_build_async())
    
    return result