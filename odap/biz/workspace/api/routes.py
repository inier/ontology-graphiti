"""API路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from ..services.workspace_service import WorkspaceService
from ..services.isolation_service import IsolationService
from ..services.scenario_service import ScenarioService
from ..impl.import_export import ImportExportManager
from .schemas import (
    CreateWorkspaceRequest, UpdateWorkspaceRequest, WorkspaceResponse, WorkspaceDetailResponse, WorkspaceListResponse,
    CreateIsolationPolicyRequest, IsolationPolicyResponse, ResourceUsageResponse,
    ExportWorkspaceRequest, ImportWorkspaceRequest, ImportExportResponse, ImportExportStatusResponse, ImportExportListResponse,
    SuccessResponse, ErrorResponse,
    WorkspaceType, WorkspaceStatus, IsolationLevel, ImportExportStatus,
    CreateScenarioRequest, UpdateScenarioRequest, ScenarioResponse, ScenarioListResponse
)

router = APIRouter(prefix="/api/workspaces", tags=["workspace"])

# 服务实例
workspace_service = WorkspaceService()
isolation_service = IsolationService()
scenario_service = ScenarioService()
import_export_manager = ImportExportManager()


# 工作空间相关路由
@router.post("", response_model=WorkspaceResponse)
async def create_workspace(request: CreateWorkspaceRequest):
    """创建工作空间"""
    try:
        result = workspace_service.create_workspace(
            name=request.name,
            description=request.description,
            workspace_type=request.type,
            config=request.config,
            owner=request.owner
        )
        return WorkspaceResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
async def get_workspace(workspace_id: str):
    """获取工作空间详情"""
    try:
        result = workspace_service.get_workspace(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return WorkspaceDetailResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(workspace_id: str, request: UpdateWorkspaceRequest):
    """更新工作空间"""
    try:
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.status is not None:
            updates["status"] = request.status
        if request.config is not None:
            updates["config"] = request.config
        if request.tags is not None:
            updates["tags"] = request.tags
        
        result = workspace_service.update_workspace(workspace_id, updates)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return WorkspaceResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workspace_id}", response_model=SuccessResponse)
async def delete_workspace(workspace_id: str):
    """删除工作空间"""
    try:
        result = workspace_service.delete_workspace(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return SuccessResponse(message=result.get("message"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    type: Optional[WorkspaceType] = None,
    status: Optional[WorkspaceStatus] = None
):
    """列出工作空间"""
    try:
        filters = {}
        if type:
            filters["type"] = type.value
        if status:
            filters["status"] = status.value
        result = workspace_service.list_workspaces(filters, page, page_size)
        return WorkspaceListResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/activate", response_model=SuccessResponse)
async def activate_workspace(workspace_id: str):
    """激活工作空间"""
    try:
        result = workspace_service.activate_workspace(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return SuccessResponse(message="Workspace activated")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/deactivate", response_model=SuccessResponse)
async def deactivate_workspace(workspace_id: str):
    """停用工作空间"""
    try:
        result = workspace_service.deactivate_workspace(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return SuccessResponse(message="Workspace deactivated")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/members/{user_id}", response_model=SuccessResponse)
async def add_member(workspace_id: str, user_id: str):
    """添加成员"""
    try:
        result = workspace_service.add_member(workspace_id, user_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return SuccessResponse(message="Member added")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workspace_id}/members/{user_id}", response_model=SuccessResponse)
async def remove_member(workspace_id: str, user_id: str):
    """移除成员"""
    try:
        result = workspace_service.remove_member(workspace_id, user_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return SuccessResponse(message="Member removed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 隔离相关路由
@router.post("/isolation/policies", response_model=IsolationPolicyResponse)
async def create_isolation_policy(request: CreateIsolationPolicyRequest):
    """创建隔离策略"""
    try:
        result = isolation_service.create_isolation_policy(
            workspace_id=request.workspace_id,
            isolation_level=request.isolation_level,
            resource_quota=request.resource_quota,
            network_policy=request.network_policy
        )
        return IsolationPolicyResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/isolation/policies/{workspace_id}", response_model=IsolationPolicyResponse)
async def get_isolation_policy(workspace_id: str):
    """获取隔离策略"""
    try:
        result = isolation_service.get_isolation_policy(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return IsolationPolicyResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/isolation/resource-usage/{workspace_id}", response_model=ResourceUsageResponse)
async def get_resource_usage(workspace_id: str):
    """获取资源使用情况"""
    try:
        result = isolation_service.get_resource_usage(workspace_id)
        return ResourceUsageResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/isolation/enforce/{workspace_id}", response_model=SuccessResponse)
async def enforce_isolation(workspace_id: str):
    """执行隔离"""
    try:
        result = isolation_service.enforce_isolation(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return SuccessResponse(message=result.get("message"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 导入导出相关路由
@router.post("/import-export/export", response_model=ImportExportResponse)
async def export_workspace(request: ExportWorkspaceRequest):
    """导出工作空间"""
    try:
        result = workspace_service.export_workspace(
            workspace_id=request.workspace_id,
            export_path=request.export_path,
            include_resources=request.include_resources,
            include_data=request.include_data,
            created_by=request.created_by
        )
        return ImportExportResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-export/import", response_model=ImportExportResponse)
async def import_workspace(request: ImportWorkspaceRequest):
    """导入工作空间"""
    try:
        result = workspace_service.import_workspace(
            import_path=request.import_path,
            workspace_name=request.workspace_name,
            overwrite=request.overwrite,
            created_by=request.created_by
        )
        return ImportExportResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/import-export/records/{record_id}", response_model=ImportExportStatusResponse)
async def get_import_export_record(record_id: str):
    """获取导入导出记录"""
    try:
        record = import_export_manager.get_import_export_record(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        return ImportExportStatusResponse(
            record_id=record.id,
            operation=record.operation,
            status=record.status.value,
            progress=record.progress,
            start_time=record.start_time.isoformat(),
            end_time=record.end_time.isoformat() if record.end_time else None,
            duration_seconds=record.duration_seconds
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/import-export/records", response_model=ImportExportListResponse)
async def list_import_export_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    workspace_id: Optional[str] = None,
    operation: Optional[str] = None,
    status: Optional[ImportExportStatus] = None
):
    """列出导入导出记录"""
    try:
        records = import_export_manager.list_import_export_records(
            workspace_id=workspace_id,
            operation=operation,
            status=status,
            page=page,
            page_size=page_size
        )
        
        record_list = []
        for record in records:
            record_list.append({
                "record_id": record.id,
                "workspace_id": record.workspace_id,
                "operation": record.operation,
                "status": record.status.value,
                "progress": record.progress,
                "start_time": record.start_time.isoformat(),
                "end_time": record.end_time.isoformat() if record.end_time else None
            })
        
        return ImportExportListResponse(
            records=record_list,
            page=page,
            page_size=page_size,
            total=len(record_list)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-export/records/{record_id}/cancel", response_model=SuccessResponse)
async def cancel_import_export(record_id: str):
    """取消导入导出"""
    try:
        success = import_export_manager.cancel_import_export(record_id)
        if not success:
            raise HTTPException(status_code=400, detail="Cannot cancel operation")
        return SuccessResponse(message="Operation cancelled")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 场景相关路由
@router.post("/{workspace_id}/scenarios", response_model=ScenarioResponse)
async def create_scenario(workspace_id: str, request: CreateScenarioRequest):
    """创建场景"""
    try:
        result = scenario_service.create_scenario(
            workspace_id=workspace_id,
            name=request.name,
            description=request.description,
            ontology_id=request.ontology_id
        )
        return ScenarioResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/scenarios", response_model=ScenarioListResponse)
async def get_scenarios(workspace_id: str):
    """获取工作空间下的所有场景"""
    try:
        scenarios = scenario_service.get_scenarios_by_workspace(workspace_id)
        return ScenarioListResponse(
            scenarios=[ScenarioResponse(**s) for s in scenarios],
            workspace_id=workspace_id,
            total=len(scenarios)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(workspace_id: str, scenario_id: str):
    """获取场景详情"""
    try:
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario or scenario.get("workspace_id") != workspace_id:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return ScenarioResponse(**scenario)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{workspace_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(workspace_id: str, scenario_id: str, request: UpdateScenarioRequest):
    """更新场景"""
    try:
        # 检查场景是否存在且属于该工作空间
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario or scenario.get("workspace_id") != workspace_id:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.ontology_id is not None:
            updates["ontology_id"] = request.ontology_id
        
        result = scenario_service.update_scenario(scenario_id, updates)
        return ScenarioResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workspace_id}/scenarios/{scenario_id}", response_model=SuccessResponse)
async def delete_scenario(workspace_id: str, scenario_id: str):
    """删除场景"""
    try:
        # 检查场景是否存在且属于该工作空间
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario or scenario.get("workspace_id") != workspace_id:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        success = scenario_service.delete_scenario(scenario_id)
        if not success:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return SuccessResponse(message="Scenario deleted")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/scenarios/{scenario_id}/build-graph")
async def build_graph_for_scenario(workspace_id: str, scenario_id: str):
    """从场景数据构建图谱"""
    try:
        # 检查场景是否存在且属于该工作空间
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario or scenario.get("workspace_id") != workspace_id:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        result = scenario_service.build_graph_from_scenario(scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
