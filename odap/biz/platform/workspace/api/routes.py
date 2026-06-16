"""API路由"""

import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Any, List, Optional
from ..services.workspace_service import WorkspaceService
from ..services.isolation_service import IsolationService
from ..services.scenario_service import ScenarioService
from ..services.sample_data_service import SampleDataService
from ..impl.import_export import ImportExportManager
from .schemas import (
    CreateWorkspaceRequest, UpdateWorkspaceRequest, WorkspaceResponse, WorkspaceDetailResponse, WorkspaceListResponse,
    CreateIsolationPolicyRequest, IsolationPolicyResponse, ResourceUsageResponse,
    ExportWorkspaceRequest, ImportWorkspaceRequest, ImportExportResponse, ImportExportStatusResponse, ImportExportListResponse,
    SuccessResponse, ErrorResponse,
    WorkspaceType, WorkspaceStatus, IsolationLevel, ImportExportStatus,
    CreateScenarioRequest, UpdateScenarioRequest, ScenarioResponse, ScenarioListResponse,
    OntologyVersionResponse, SwitchVersionRequest,
    BindOntologyRequest, OntologyBindingResponse, OntologyBindingListResponse,
    UpdateIsolationLevelRequest,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspace"])

logger = logging.getLogger(__name__)

# 服务实例
workspace_service = WorkspaceService()
isolation_service = IsolationService()
scenario_service = ScenarioService()
sample_data_service = SampleDataService()
import_export_manager = ImportExportManager()
from odap.biz.core.ontology.design.services.version_service import OntologyVersionManager
version_manager = OntologyVersionManager()


# 工作空间相关路由
@router.post("", response_model=WorkspaceResponse)
async def create_workspace(request: CreateWorkspaceRequest,
    user=Depends(get_current_user)):
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{workspace_id}/isolation")
async def update_isolation_level(workspace_id: str, request: UpdateIsolationLevelRequest,
    user=Depends(get_current_user)):
    try:
        result = workspace_service.update_isolation_level(workspace_id, request.isolation_level.value)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/export")
async def export_workspace_v2(workspace_id: str, request: ExportWorkspaceRequest = None,
    user=Depends(get_current_user)):
    try:
        if request is None:
            request = ExportWorkspaceRequest(workspace_id=workspace_id)
        result = workspace_service.export_workspace(
            workspace_id=workspace_id,
            export_path=request.export_path if request else None,
            include_resources=request.include_resources if request else True,
            include_data=request.include_data if request else False,
            created_by=request.created_by if request else "system",
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/import")
async def import_workspace_v2(workspace_id: str, request: ImportWorkspaceRequest,
    user=Depends(get_current_user)):
    try:
        result = workspace_service.import_workspace(
            import_path=request.import_path,
            workspace_name=request.workspace_name,
            overwrite=request.overwrite,
            created_by=request.created_by,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/scenarios/{scenario_id}/activate")
async def activate_scenario(workspace_id: str, scenario_id: str,
    user=Depends(get_current_user)):
    try:
        result = scenario_service.activate_scenario(workspace_id, scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
async def get_workspace(workspace_id: str,
    user=Depends(get_current_user)):
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
async def update_workspace(workspace_id: str, request: UpdateWorkspaceRequest,
    user=Depends(get_current_user)):
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
async def delete_workspace(workspace_id: str,
    user=Depends(get_current_user)):
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


@router.get("/{workspace_id}/deletion-preview")
async def get_workspace_deletion_preview(workspace_id: str,
    user=Depends(get_current_user)):
    """获取工作空间删除预览（将级联删除的资源类型及数量）"""
    try:
        result = workspace_service.get_workspace_deletion_preview(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/sample-data")
async def generate_sample_data(workspace_id: str,
    user=Depends(get_current_user)):
    """为工作空间生成示例数据"""
    try:
        workspace = workspace_service.get_workspace(workspace_id)
        if workspace.get("status") == "error":
            raise HTTPException(status_code=404, detail="Workspace not found")
        result = sample_data_service.generate_sample_data(workspace_id)
        return result
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/activate", response_model=SuccessResponse)
async def activate_workspace(workspace_id: str,
    user=Depends(get_current_user)):
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
async def deactivate_workspace(workspace_id: str,
    user=Depends(get_current_user)):
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
async def add_member(workspace_id: str, user_id: str,
    user=Depends(get_current_user)):
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
async def remove_member(workspace_id: str, user_id: str,
    user=Depends(get_current_user)):
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
async def create_isolation_policy(request: CreateIsolationPolicyRequest,
    user=Depends(get_current_user)):
    """创建隔离策略"""
    try:
        result = isolation_service.create_isolation_policy(
            workspace_id=request.workspace_id,
            isolation_level=request.isolation_level,
            resource_quota=request.resource_quota,
            network_policy=request.network_policy
        )
        return IsolationPolicyResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/isolation/policies/{workspace_id}", response_model=IsolationPolicyResponse)
async def get_isolation_policy(workspace_id: str,
    user=Depends(get_current_user)):
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
async def get_resource_usage(workspace_id: str,
    user=Depends(get_current_user)):
    """获取资源使用情况"""
    try:
        result = isolation_service.get_resource_usage(workspace_id)
        return ResourceUsageResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/isolation/enforce/{workspace_id}", response_model=SuccessResponse)
async def enforce_isolation(workspace_id: str,
    user=Depends(get_current_user)):
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
async def export_workspace(request: ExportWorkspaceRequest,
    user=Depends(get_current_user)):
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-export/import", response_model=ImportExportResponse)
async def import_workspace(request: ImportWorkspaceRequest,
    user=Depends(get_current_user)):
    """导入工作空间"""
    try:
        result = workspace_service.import_workspace(
            import_path=request.import_path,
            workspace_name=request.workspace_name,
            overwrite=request.overwrite,
            created_by=request.created_by
        )
        return ImportExportResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/import-export/records/{record_id}", response_model=ImportExportStatusResponse)
async def get_import_export_record(record_id: str,
    user=Depends(get_current_user)):
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
    status: Optional[ImportExportStatus] = None,
    user=Depends(get_current_user)):
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-export/records/{record_id}/cancel", response_model=SuccessResponse)
async def cancel_import_export(record_id: str,
    user=Depends(get_current_user)):
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
async def create_scenario(workspace_id: str, request: CreateScenarioRequest,
    user=Depends(get_current_user)):
    """创建场景"""
    try:
        result = scenario_service.create_scenario(
            workspace_id=workspace_id,
            name=request.name,
            description=request.description,
            ontology_id=request.ontology_id,
            status=request.status or "draft",
            tags=request.tags
        )
        return ScenarioResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/scenarios", response_model=ScenarioListResponse)
async def get_scenarios(
    workspace_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user=Depends(get_current_user)):
    """获取工作空间下的所有场景"""
    try:
        scenarios = scenario_service.get_scenarios_by_workspace(workspace_id, page, page_size)
        return ScenarioListResponse(
            scenarios=[ScenarioResponse(**s) for s in scenarios],
            workspace_id=workspace_id,
            total=len(scenarios)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(workspace_id: str, scenario_id: str,
    user=Depends(get_current_user)):
    """获取场景详情"""
    try:
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario:
            from odap.biz.shared.stores import scenario_store
            scenario = scenario_store.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        scenario_ws = scenario.get("workspace_id", "")
        if scenario_ws and scenario_ws != workspace_id and scenario_ws != "default":
            raise HTTPException(status_code=404, detail="Scenario not found")
        return ScenarioResponse(**scenario)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{workspace_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(workspace_id: str, scenario_id: str, request: UpdateScenarioRequest,
    user=Depends(get_current_user)):
    """更新场景"""
    try:
        # 检查场景是否存在且属于该工作空间
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario:
            from odap.biz.shared.stores import scenario_store
            scenario = scenario_store.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        scenario_ws = scenario.get("workspace_id", "")
        if scenario_ws and scenario_ws != workspace_id and scenario_ws != "default":
            raise HTTPException(status_code=404, detail="Scenario not found")
        if scenario_ws == "default":
            scenario["workspace_id"] = workspace_id
        
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
async def delete_scenario(workspace_id: str, scenario_id: str,
    user=Depends(get_current_user)):
    """删除场景"""
    try:
        # 检查场景是否存在且属于该工作空间
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario:
            from odap.biz.shared.stores import scenario_store
            scenario = scenario_store.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        scenario_ws = scenario.get("workspace_id", "")
        if scenario_ws and scenario_ws != workspace_id and scenario_ws != "default":
            raise HTTPException(status_code=404, detail="Scenario not found")
        if scenario_ws == "default":
            scenario["workspace_id"] = workspace_id
        
        success = scenario_service.delete_scenario(scenario_id)
        if not success:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return SuccessResponse(message="Scenario deleted")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/scenarios/{scenario_id}/build-graph")
async def build_graph_for_scenario(workspace_id: str, scenario_id: str,
    user=Depends(get_current_user)):
    """从场景数据构建图谱"""
    try:
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


@router.post("/{workspace_id}/scenarios/{scenario_id}/ontologies/{ontology_id}", response_model=OntologyBindingResponse)
async def bind_ontology_to_scenario(workspace_id: str, scenario_id: str, ontology_id: str, request: BindOntologyRequest = None,
    user=Depends(get_current_user)):
    """绑定本体到场景"""
    try:
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        if scenario.get("workspace_id") != workspace_id and scenario.get("workspace_id") != "default":
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        bound_by = request.bound_by if request else "system"
        result = scenario_service.bind_ontology(scenario_id, ontology_id, bound_by)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return OntologyBindingResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workspace_id}/scenarios/{scenario_id}/ontologies/{ontology_id}", response_model=SuccessResponse)
async def unbind_ontology_from_scenario(workspace_id: str, scenario_id: str, ontology_id: str,
    user=Depends(get_current_user)):
    """解绑本体"""
    try:
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        if scenario.get("workspace_id") != workspace_id and scenario.get("workspace_id") != "default":
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        result = scenario_service.unbind_ontology(scenario_id, ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return SuccessResponse(message=result.get("message"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/scenarios/{scenario_id}/ontologies", response_model=OntologyBindingListResponse)
async def get_scenario_ontologies(workspace_id: str, scenario_id: str,
    user=Depends(get_current_user)):
    """获取场景绑定的所有本体"""
    try:
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        if scenario.get("workspace_id") != workspace_id and scenario.get("workspace_id") != "default":
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        result = scenario_service.get_scenario_ontologies(scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return OntologyBindingListResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 本体版本相关路由
@router.get("/{workspace_id}/scenarios/{scenario_id}/versions", response_model=List[OntologyVersionResponse])
async def get_scenario_versions(workspace_id: str, scenario_id: str,
    user=Depends(get_current_user)):
    """获取场景绑定本体的版本列表"""
    try:
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario:
            try:
                from odap.biz.integration.frontend_compat.api.routes import scenario_store as compat_store
                scenario = compat_store.get_scenario(scenario_id)
            except HTTPException:
                raise
            except Exception as e:
                logger.debug("Fallback source failed: %s", e)
        if not scenario:
            try:
                from odap.biz.shared.stores import scenario_store as global_scenario_store
                scenario = global_scenario_store.get_scenario(scenario_id)
            except HTTPException:
                raise
            except Exception as e:
                logger.debug("Fallback source failed: %s", e)
        if not scenario:
            return []
        
        scenario_ws = scenario.get("workspace_id", "")
        if scenario_ws and scenario_ws != workspace_id and scenario_ws != "default":
            return []
        if scenario_ws == "default":
            scenario["workspace_id"] = workspace_id
        
        ontology_id = scenario.get("ontology_id")
        if not ontology_id:
            return []
        
        all_versions = await version_manager.list_by_ontology(ontology_id)
        return [OntologyVersionResponse(**v.to_dict()) for v in all_versions]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/scenarios/{scenario_id}/commit-version", response_model=OntologyVersionResponse)
async def commit_scenario_version(workspace_id: str, scenario_id: str, message: str = "",
    user=Depends(get_current_user)):
    """手动提交版本：锁定当前版本 + 创建新版本"""
    try:
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario:
            try:
                from odap.biz.integration.frontend_compat.api.routes import scenario_store as compat_store
                scenario = compat_store.get_scenario(scenario_id)
            except HTTPException:
                raise
            except Exception as e:
                logger.debug("Fallback source failed: %s", e)
        if not scenario:
            try:
                from odap.biz.shared.stores import scenario_store as global_scenario_store
                scenario = global_scenario_store.get_scenario(scenario_id)
            except HTTPException:
                raise
            except Exception as e:
                logger.debug("Fallback source failed: %s", e)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        scenario_ws = scenario.get("workspace_id", "")
        if scenario_ws and scenario_ws != workspace_id and scenario_ws != "default":
            raise HTTPException(status_code=404, detail="Scenario not found")
        if scenario_ws == "default":
            scenario["workspace_id"] = workspace_id

        ontology_id = scenario.get("ontology_id")
        if not ontology_id:
            raise HTTPException(status_code=400, detail="Scenario is not bound to an ontology")

        new_version = await version_manager.commit(ontology_id, message=message or "")
        return OntologyVersionResponse(**new_version.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/data-conflicts")
async def scan_data_conflicts(workspace_id: str,
    user=Depends(get_current_user)):
    """扫描数据冲突（同名实体不同ID）"""
    try:
        from odap.biz.core.ontology.design.services.ingest_service import IngestService
        svc = IngestService()
        result = svc.scan_data_conflicts()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/data-conflicts/repair")
async def repair_data_conflicts(workspace_id: str, dry_run: bool = True,
    user=Depends(get_current_user)):
    """修复数据冲突（合并同名实体为确定性ID）"""
    try:
        from odap.biz.core.ontology.design.services.ingest_service import IngestService
        svc = IngestService()
        result = svc.repair_data_conflicts(dry_run=dry_run)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/scenarios/{scenario_id}/switch-version", response_model=SuccessResponse)
async def switch_scenario_version(workspace_id: str, scenario_id: str, request: SwitchVersionRequest,
    user=Depends(get_current_user)):
    """切换场景使用的本体版本"""
    try:
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario:
            try:
                from odap.biz.integration.frontend_compat.api.routes import scenario_store as compat_store
                scenario = compat_store.get_scenario(scenario_id)
            except HTTPException:
                raise
            except Exception as e:
                logger.debug("Fallback source failed: %s", e)
        if not scenario:
            try:
                from odap.biz.shared.stores import scenario_store as global_scenario_store
                scenario = global_scenario_store.get_scenario(scenario_id)
            except HTTPException:
                raise
            except Exception as e:
                logger.debug("Fallback source failed: %s", e)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        scenario_ws = scenario.get("workspace_id", "")
        if scenario_ws and scenario_ws != workspace_id and scenario_ws != "default":
            raise HTTPException(status_code=404, detail="Scenario not found")
        if scenario_ws == "default":
            scenario["workspace_id"] = workspace_id
        
        ontology_id = scenario.get("ontology_id")
        if not ontology_id:
            raise HTTPException(status_code=400, detail="Scenario is not bound to an ontology")
        
        if request.version_id == "latest":
            new_version_id = None
        else:
            version = await version_manager.get(request.version_id)
            if not version or version.ontology_id != ontology_id:
                raise HTTPException(status_code=404, detail="Version not found or does not belong to the bound ontology")
            new_version_id = request.version_id
        
        result = scenario_service.update_scenario(scenario_id, {"current_ontology_version": new_version_id})
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        return SuccessResponse(message=f"Switched to version {request.version_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/scenarios/{scenario_id}/versions/{version_id}/data")
async def get_version_data(workspace_id: str, scenario_id: str, version_id: str,
    user=Depends(get_current_user)):
    """获取指定版本的本体数据"""
    try:
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario:
            try:
                from odap.biz.integration.frontend_compat.api.routes import scenario_store as compat_store
                scenario = compat_store.get_scenario(scenario_id)
            except HTTPException:
                raise
            except Exception as e:
                logger.debug("Fallback source failed: %s", e)
        if not scenario:
            try:
                from odap.biz.shared.stores import scenario_store as global_scenario_store
                scenario = global_scenario_store.get_scenario(scenario_id)
            except HTTPException:
                raise
            except Exception as e:
                logger.debug("Fallback source failed: %s", e)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        scenario_ws = scenario.get("workspace_id", "")
        if scenario_ws and scenario_ws != workspace_id and scenario_ws != "default":
            raise HTTPException(status_code=404, detail="Scenario not found")
        if scenario_ws == "default":
            scenario["workspace_id"] = workspace_id
        
        ontology_id = scenario.get("ontology_id")
        if not ontology_id:
            raise HTTPException(status_code=400, detail="Scenario is not bound to an ontology")
        
        if version_id == "latest":
            raise HTTPException(status_code=400, detail="此端点仅支持指定版本ID，使用 entities/relations API 获取最新数据")
        
        version = await version_manager.get(version_id)
        if not version or version.ontology_id != ontology_id:
            raise HTTPException(status_code=404, detail="Version not found or does not belong to the bound ontology")
        
        doc = await version_manager.get_doc(version_id)
        if doc:
            return {
                "version_id": version_id,
                "entities": [e.to_dict() for e in doc.entities],
                "relations": [r.to_dict() for r in doc.relations],
                "events": [e.to_dict() for e in doc.events]
            }
        
        return {
            "version_id": version_id,
            "entities": [],
            "relations": [],
            "events": []
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 场景兼容路由（前端 /api/scenarios/{id}/... 调用） ====================

# 独立的场景路由器，兼容前端 /api/scenarios/{scenario_id}/entities 等路径
scenario_compat_router = APIRouter(prefix="/api/scenarios", tags=["scenario-compat"])


@scenario_compat_router.get("/{scenario_id}/entities")
async def get_scenario_entities_compat(scenario_id: str, workspace_id: str = None,
    user=Depends(get_current_user)):
    """获取场景下的实体列表（兼容前端 /api/scenarios/{id}/entities）"""
    try:
        entities = []

        # 1. 从本体模型服务获取
        try:
            from odap.biz.core.ontology.design.model.services.model_service import ModelService
            ms = ModelService()
            entity_types_result = ms.list_entity_types(page_size=200)
            for et in entity_types_result.get("entity_types", []):
                instances_result = ms.list_instances(
                    type_id=et["type_id"],
                    workspace_id=workspace_id or "default",
                    page_size=100,
                )
                instances = instances_result.get("instances", [])
                # 同时查 default workspace
                if not instances:
                    instances_result = ms.list_instances(
                        type_id=et["type_id"],
                        workspace_id="default",
                        page_size=100,
                    )
                    instances = instances_result.get("instances", [])
                for inst in instances:
                    props = inst.get("properties") or {}
                    if isinstance(props, str):
                        try:
                            import json
                            props = json.loads(props)
                        except Exception as e:
                            logger.debug("Fallback source failed: %s", e)
                            props = {}
                    entities.append({
                        "entity_id": inst.get("instance_id", ""),
                        "name": props.get("name", ""),
                        "type": et.get("name", ""),
                        "type_display": et.get("display_name", ""),
                        "properties": props,
                    })
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Model storage query failed: {e}")

        # 2. 从 QueryService 获取（替代直接 GraphManager 导入）
        try:
            from odap.infra.query import get_query_service
            qs = get_query_service()
            qs_result = qs.execute(
                workspace_id=workspace_id or "default",
                query=".entity list()",
                limit=500,
            )
            for e in qs_result.rows:
                if isinstance(e, dict):
                    entities.append({
                        "entity_id": e.get("entity_id") or e.get("id") or e.get("uuid", ""),
                        "name": e.get("name", ""),
                        "type": e.get("type") or e.get("entity_type", ""),
                        "type_display": e.get("type", ""),
                        "properties": e.get("properties") or e,
                    })
        except Exception as e:
            logger.debug("Fallback source failed: %s", e)

        return {"entities": entities, "total": len(entities)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@scenario_compat_router.get("/{scenario_id}/relations")
async def get_scenario_relations_compat(scenario_id: str, workspace_id: str = None,
    user=Depends(get_current_user)):
    """获取场景下的关系列表（兼容前端 /api/scenarios/{id}/relations）"""
    try:
        nodes = []
        edges = []

        # 从 QueryService 获取（替代直接 GraphManager 导入）
        try:
            from odap.infra.query import get_query_service
            qs = get_query_service()

            entity_result = qs.execute(
                workspace_id=workspace_id or "default",
                query=".entity list()",
                limit=500,
            )
            all_entities = entity_result.rows

            topo_result = qs.execute(
                workspace_id=workspace_id or "default",
                query=".topo relations()",
                limit=500,
            )
            all_relations = topo_result.rows

            for e in all_entities:
                if isinstance(e, dict):
                    nodes.append({
                        "id": e.get("entity_id") or e.get("id") or e.get("uuid", ""),
                        "label": e.get("name", ""),
                        "type": e.get("type") or e.get("entity_type", ""),
                        "properties": e.get("properties") or {},
                    })

            for r in all_relations:
                if isinstance(r, dict):
                    edges.append({
                        "id": r.get("relation_id") or r.get("id", ""),
                        "source": r.get("source_id") or r.get("from", ""),
                        "target": r.get("target_id") or r.get("to", ""),
                        "label": r.get("relation_type") or r.get("type", ""),
                        "properties": r.get("properties") or {},
                    })
        except Exception as e:
            logger.debug("Fallback source failed: %s", e)

        return {"nodes": nodes, "edges": edges}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@scenario_compat_router.get("/{scenario_id}/timeline")
async def get_scenario_timeline_compat(scenario_id: str, workspace_id: str = None,
    user=Depends(get_current_user)):
    """获取场景时间线（兼容前端 /api/scenarios/{id}/timeline）"""
    try:
        events = []
        # 从本体模型服务获取事件
        try:
            from odap.biz.core.ontology.design.model.services.model_service import ModelService
            ms = ModelService()
            entity_types_result = ms.list_entity_types(page_size=200)
            entity_types = entity_types_result.get("entity_types", [])
            event_type = next((t for t in entity_types if "event" in t.get("name", "").lower()
                              or "事件" in t.get("display_name", "")), None)
            if event_type:
                instances_result = ms.list_instances(
                    type_id=event_type["type_id"],
                    workspace_id=workspace_id or "default",
                    page_size=100,
                )
                instances = instances_result.get("instances", [])
                if not instances:
                    instances_result = ms.list_instances(
                        type_id=event_type["type_id"],
                        workspace_id="default",
                        page_size=100,
                    )
                    instances = instances_result.get("instances", [])
                for inst in instances:
                    props = inst.get("properties") or {}
                    if isinstance(props, str):
                        try:
                            import json
                            props = json.loads(props)
                        except Exception as e:
                            logger.debug("Fallback source failed: %s", e)
                            props = {}
                    events.append({
                        "event_id": inst.get("instance_id", ""),
                        "name": props.get("name", ""),
                        "year": props.get("year"),
                        "category": props.get("category", ""),
                        "description": props.get("description", ""),
                    })
                events.sort(key=lambda e: e.get("year") or 0)
        except Exception as e:
            logger.debug("Fallback source failed: %s", e)

        return {"events": events}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
