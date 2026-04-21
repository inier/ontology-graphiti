"""API路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from ..services.ingest_service import DataIngestService
from ..services.build_service import OntologyBuildService
from ..services.version_service import VersionManagementService
from ..services.validation_service import ValidationService
from ..impl.dashboard import AuditDashboard
from .schemas import (
    IngestRequest, IngestResponse, IngestStatusResponse, IngestListResponse,
    CreateOntologyRequest, UpdateOntologyRequest, OntologyResponse, OntologyListResponse, BuildFromIngestResponse,
    CreateVersionRequest, VersionResponse, VersionListResponse, RollbackVersionRequest, CompareVersionsRequest, MergeVersionsRequest,
    CreateValidationRuleRequest, ValidationRuleResponse, ValidationRuleListResponse, ValidateOntologyRequest, ValidationResultResponse, FixValidationIssueRequest,
    DashboardSummaryResponse, PerformanceMetricsResponse, ErrorTrendsResponse, TopIssuesResponse
)

router = APIRouter(prefix="/api/ontology-management", tags=["ontology-management"])

# 服务实例
ingest_service = DataIngestService()
build_service = OntologyBuildService()
version_service = VersionManagementService()
validation_service = ValidationService()
dashboard = AuditDashboard()


# 数据摄入相关路由
@router.post("/ingest", response_model=IngestResponse)
async def ingest_data(request: IngestRequest):
    """摄入数据"""
    try:
        ingest_id = ingest_service.ingest_data(
            source=request.source,
            source_details=request.source_details,
            data=request.data
        )
        return IngestResponse(ingest_id=ingest_id, status="started")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingest/{ingest_id}", response_model=IngestStatusResponse)
async def get_ingest_status(ingest_id: str):
    """获取摄入状态"""
    try:
        status = ingest_service.get_ingest_status(ingest_id)
        if status.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Ingest not found")
        return IngestStatusResponse(**status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingest", response_model=IngestListResponse)
async def list_ingest_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None
):
    """列出摄入任务"""
    try:
        filters = {}
        if status:
            filters["status"] = status
        result = ingest_service.list_ingest_jobs(filters, page, page_size)
        return IngestListResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 本体构建相关路由
@router.post("/ontologies", response_model=OntologyResponse)
async def create_ontology(request: CreateOntologyRequest):
    """创建本体"""
    try:
        ontology = build_service.create_ontology(
            name=request.name,
            description=request.description
        )
        return OntologyResponse(
            ontology_id=ontology.id,
            name=ontology.name,
            description=ontology.description,
            status=ontology.status.value,
            version=ontology.version,
            entity_count=len(ontology.entities),
            relation_count=len(ontology.relations),
            created_at=ontology.created_at.isoformat(),
            updated_at=ontology.updated_at.isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontologies/{ontology_id}", response_model=OntologyResponse)
async def get_ontology(ontology_id: str):
    """获取本体"""
    try:
        ontology = build_service.get_ontology(ontology_id)
        if not ontology:
            raise HTTPException(status_code=404, detail="Ontology not found")
        return OntologyResponse(
            ontology_id=ontology.id,
            name=ontology.name,
            description=ontology.description,
            status=ontology.status.value,
            version=ontology.version,
            entity_count=len(ontology.entities),
            relation_count=len(ontology.relations),
            created_at=ontology.created_at.isoformat(),
            updated_at=ontology.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/ontologies/{ontology_id}", response_model=OntologyResponse)
async def update_ontology(ontology_id: str, request: UpdateOntologyRequest):
    """更新本体"""
    try:
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.entities is not None:
            updates["entities"] = request.entities
        if request.relations is not None:
            updates["relations"] = request.relations
        if request.properties is not None:
            updates["properties"] = request.properties
        if request.status is not None:
            updates["status"] = request.status
        
        ontology = build_service.update_ontology(ontology_id, updates)
        if not ontology:
            raise HTTPException(status_code=404, detail="Ontology not found")
        
        return OntologyResponse(
            ontology_id=ontology.id,
            name=ontology.name,
            description=ontology.description,
            status=ontology.status.value,
            version=ontology.version,
            entity_count=len(ontology.entities),
            relation_count=len(ontology.relations),
            created_at=ontology.created_at.isoformat(),
            updated_at=ontology.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontologies", response_model=OntologyListResponse)
async def list_ontologies(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None
):
    """列出本体"""
    try:
        filters = {}
        if status:
            filters["status"] = status
        result = build_service.list_ontologies(filters, page, page_size)
        return OntologyListResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ontologies/build-from-ingest", response_model=BuildFromIngestResponse)
async def build_from_ingest(ingest_id: str):
    """从数据摄入构建本体"""
    try:
        result = build_service.build_from_ingest(ingest_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return BuildFromIngestResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 版本管理相关路由
@router.post("/versions", response_model=VersionResponse)
async def create_version(request: CreateVersionRequest):
    """创建版本"""
    try:
        result = version_service.create_version(
            ontology_id=request.ontology_id,
            version_number=request.version_number,
            parent_version_id=request.parent_version_id,
            change_summary=request.change_summary
        )
        return VersionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{version_id}", response_model=VersionResponse)
async def get_version(version_id: str):
    """获取版本"""
    try:
        result = version_service.get_version(version_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return VersionResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontologies/{ontology_id}/versions", response_model=VersionListResponse)
async def list_versions(
    ontology_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    """列出版本"""
    try:
        result = version_service.list_versions(ontology_id, None, page, page_size)
        return VersionListResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/rollback", response_model=VersionResponse)
async def rollback_version(request: RollbackVersionRequest):
    """回滚版本"""
    try:
        result = version_service.rollback_version(
            ontology_id=request.ontology_id,
            target_version_id=request.target_version_id
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return VersionResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/compare")
async def compare_versions(request: CompareVersionsRequest):
    """对比版本"""
    try:
        result = version_service.compare_versions(
            source_version_id=request.source_version_id,
            target_version_id=request.target_version_id
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/merge", response_model=VersionResponse)
async def merge_versions(request: MergeVersionsRequest):
    """合并版本"""
    try:
        result = version_service.merge_versions(
            ontology_id=request.ontology_id,
            source_version_id=request.source_version_id,
            target_version_id=request.target_version_id,
            conflict_resolution=request.conflict_resolution
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return VersionResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 验证相关路由
@router.post("/validation/rules", response_model=ValidationRuleResponse)
async def create_validation_rule(request: CreateValidationRuleRequest):
    """创建验证规则"""
    try:
        result = validation_service.add_validation_rule(request.model_dump())
        return ValidationRuleResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validation/rules/{rule_id}", response_model=ValidationRuleResponse)
async def get_validation_rule(rule_id: str):
    """获取验证规则"""
    try:
        result = validation_service.get_validation_rule(rule_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return ValidationRuleResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validation/rules", response_model=ValidationRuleListResponse)
async def list_validation_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    enabled: Optional[bool] = None
):
    """列出验证规则"""
    try:
        filters = {}
        if enabled is not None:
            filters["enabled"] = enabled
        result = validation_service.list_validation_rules(filters, page, page_size)
        return ValidationRuleListResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validation/validate", response_model=ValidationResultResponse)
async def validate_ontology(request: ValidateOntologyRequest):
    """验证本体"""
    try:
        result = validation_service.validate_ontology(
            ontology_id=request.ontology_id,
            rules=request.rules
        )
        return ValidationResultResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validation/results/{result_id}", response_model=ValidationResultResponse)
async def get_validation_result(result_id: str):
    """获取验证结果"""
    try:
        result = validation_service.get_validation_result(result_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return ValidationResultResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validation/fix")
async def fix_validation_issue(request: FixValidationIssueRequest):
    """修复验证问题"""
    try:
        result = validation_service.fix_validation_issue(
            issue_id=request.issue_id,
            fix_action=request.fix_action
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 审计仪表盘相关路由
@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary():
    """获取仪表盘摘要"""
    try:
        return DashboardSummaryResponse(
            ingest_summary=dashboard.get_ingest_summary(),
            ontology_summary=dashboard.get_ontology_summary(),
            validation_summary=dashboard.get_validation_summary(),
            version_summary=dashboard.get_version_summary()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics():
    """获取性能指标"""
    try:
        metrics = dashboard.get_performance_metrics()
        return PerformanceMetricsResponse(**metrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/error-trends", response_model=ErrorTrendsResponse)
async def get_error_trends():
    """获取错误趋势"""
    try:
        trends = dashboard.get_error_trends()
        return ErrorTrendsResponse(trends=trends)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/top-issues", response_model=TopIssuesResponse)
async def get_top_issues(limit: int = Query(10, ge=1, le=50)):
    """获取Top问题"""
    try:
        issues = dashboard.get_top_issues(limit)
        return TopIssuesResponse(issues=issues)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
