from fastapi import APIRouter, HTTPException, Header, Depends
from odap.infra.security.jwt_auth import get_current_user

from ..services.model_service import ModelService
from .schemas import (
    BatchImportRequest,
    CreateDocumentRequest,
    CreateEntityTypeRequest,
    CreateInstanceRequest,
    UpdateEntityTypeRequest,
    UpdateInstanceRequest,
)
from odap.biz.core.ontology.design.services.edit_lock_service import get_edit_lock_service

router = APIRouter(prefix="/api/ontology/model", tags=["ontology-model"])

model_service = ModelService()


def _check_edit_lock(ontology_id: str, user_id: str):
    """检查编辑锁，如果本体被其他用户锁定则抛出 423"""
    lock_service = get_edit_lock_service()
    lock_status = lock_service.get_lock_status(ontology_id)
    if lock_status and lock_status.get("user_id") != user_id:
        raise HTTPException(
            status_code=423,
            detail={
                "message": "本体正在被其他用户编辑",
                "locked_by": lock_status.get("user_id"),
                "locked_at": lock_status.get("acquired_at"),
            },
        )


@router.post("/entity-types")
async def create_entity_type(request: CreateEntityTypeRequest,
    user=Depends(get_current_user)):
    try:
        result = model_service.create_entity_type(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity-types")
async def list_entity_types(page: int = 1, page_size: int = 20, name: str = None, classification_level: str = None,
    user=Depends(get_current_user)):
    try:
        filters = {}
        if name:
            filters["name"] = name
        if classification_level:
            filters["classification_level"] = classification_level
        return model_service.list_entity_types(filters or None, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity-types/{type_id}")
async def get_entity_type(type_id: str,
    user=Depends(get_current_user)):
    try:
        result = model_service.get_entity_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/entity-types/{type_id}")
async def update_entity_type(type_id: str, request: UpdateEntityTypeRequest, x_user_id: str = Header(default=""),
    user=Depends(get_current_user)):
    try:
        _check_edit_lock(type_id, x_user_id)
        data = request.model_dump(exclude_none=True)
        result = model_service.update_entity_type(type_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/entity-types/{type_id}")
async def delete_entity_type(type_id: str, x_user_id: str = Header(default=""),
    user=Depends(get_current_user)):
    try:
        _check_edit_lock(type_id, x_user_id)
        result = model_service.delete_entity_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances")
async def create_instance(request: CreateInstanceRequest,
    user=Depends(get_current_user)):
    try:
        data = request.model_dump()
        # 将顶层 name/description 合并到 properties 中
        props = data.get("properties", {})
        if data.get("name") is not None:
            props["name"] = data.pop("name")
        if data.get("description") is not None:
            props["description"] = data.pop("description")
        data["properties"] = props
        result = model_service.create_instance(data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances")
async def list_instances(type_id: str = None, workspace_id: str = None, page: int = 1, page_size: int = 20,
    user=Depends(get_current_user)):
    try:
        return model_service.list_instances(type_id, workspace_id, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances/{instance_id}")
async def get_instance(instance_id: str,
    user=Depends(get_current_user)):
    try:
        result = model_service.get_instance(instance_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/instances/{instance_id}")
async def update_instance(instance_id: str, request: UpdateInstanceRequest, x_user_id: str = Header(default=""),
    user=Depends(get_current_user)):
    try:
        _check_edit_lock(instance_id, x_user_id)
        data = request.model_dump(exclude_none=True)
        result = model_service.update_instance(instance_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str, x_user_id: str = Header(default=""),
    user=Depends(get_current_user)):
    try:
        _check_edit_lock(instance_id, x_user_id)
        result = model_service.delete_instance(instance_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances/batch")
async def batch_import(request: BatchImportRequest,
    user=Depends(get_current_user)):
    try:
        return model_service.batch_import(request.instances)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{ontology_id}")
async def get_document(ontology_id: str,
    user=Depends(get_current_user)):
    try:
        result = model_service.get_document(ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents")
async def create_document(request: CreateDocumentRequest,
    user=Depends(get_current_user)):
    try:
        data = request.model_dump()
        result = model_service.create_document(data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{ontology_id}/export")
async def export_document(ontology_id: str,
    user=Depends(get_current_user)):
    try:
        result = model_service.export_document(ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 带 document_id 路径段的兼容路由 ====================
# 前端 ontologyApi 使用 /api/ontology/model/{documentId}/entity-types 格式
# 后端原路由为 /api/ontology/model/entity-types（无 documentId 段）
# 以下路由将 document_id 作为可选路径参数，委托给原有逻辑

@router.get("/{document_id}/entity-types")
async def list_entity_types_by_doc(document_id: str, page: int = 1, page_size: int = 20,
    name: str = None, classification_level: str = None,
    user=Depends(get_current_user)):
    """按文档ID列出实体类型（兼容前端 /api/ontology/model/{docId}/entity-types）"""
    try:
        filters = {}
        if name:
            filters["name"] = name
        if classification_level:
            filters["classification_level"] = classification_level
        return model_service.list_entity_types(filters or None, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/entity-types/{type_id}")
async def get_entity_type_by_doc(document_id: str, type_id: str,
    user=Depends(get_current_user)):
    """按文档ID获取实体类型详情"""
    try:
        result = model_service.get_entity_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/entity-types")
async def create_entity_type_by_doc(document_id: str, request: CreateEntityTypeRequest,
    user=Depends(get_current_user)):
    """按文档ID创建实体类型"""
    try:
        result = model_service.create_entity_type(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{document_id}/entity-types/{type_id}")
async def update_entity_type_by_doc(document_id: str, type_id: str, request: UpdateEntityTypeRequest,
    x_user_id: str = Header(default=""), user=Depends(get_current_user)):
    """按文档ID更新实体类型"""
    try:
        _check_edit_lock(type_id, x_user_id)
        data = request.model_dump(exclude_none=True)
        result = model_service.update_entity_type(type_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}/entity-types/{type_id}")
async def delete_entity_type_by_doc(document_id: str, type_id: str,
    x_user_id: str = Header(default=""), user=Depends(get_current_user)):
    """按文档ID删除实体类型"""
    try:
        _check_edit_lock(type_id, x_user_id)
        result = model_service.delete_entity_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/entity-types/{type_id}/instances")
async def list_instances_by_doc(document_id: str, type_id: str,
    page: int = 1, page_size: int = 20, workspace_id: str = None,
    user=Depends(get_current_user)):
    """按文档ID和类型ID列出实例"""
    try:
        return model_service.list_instances(type_id, workspace_id, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/entity-types/{type_id}/instances")
async def create_instance_by_doc(document_id: str, type_id: str, request: CreateInstanceRequest,
    user=Depends(get_current_user)):
    """按文档ID和类型ID创建实例"""
    try:
        data = request.model_dump()
        data["type_id"] = type_id
        # 将顶层 name/description 合并到 properties 中
        props = data.get("properties", {})
        if data.get("name") is not None:
            props["name"] = data.pop("name")
        if data.get("description") is not None:
            props["description"] = data.pop("description")
        data["properties"] = props
        result = model_service.create_instance(data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/entity-types/{type_id}/instances/batch")
async def batch_import_by_doc(document_id: str, type_id: str, request: BatchImportRequest,
    user=Depends(get_current_user)):
    """按文档ID和类型ID批量导入实例"""
    try:
        instances = request.instances
        for inst in instances:
            if isinstance(inst, dict):
                inst["type_id"] = type_id
        return model_service.batch_import(instances)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}")
async def load_ontology_document(document_id: str,
    user=Depends(get_current_user)):
    """加载本体文档（兼容前端 /api/ontology/model/{docId}）

    当 document_id 为 "default" 或文档不存在时，返回空结构而非 404，
    前端在未选择具体文档时使用 "default" 作为默认值。
    """
    try:
        result = model_service.get_document(document_id)
        if result.get("status") == "error":
            # 返回空结构而非 404，兼容前端默认请求
            return {
                "document_id": document_id,
                "name": "",
                "description": "",
                "version": "0.1",
                "entity_types": [],
                "created_at": "",
                "updated_at": "",
            }
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/export")
async def export_document_by_id(document_id: str, format: str = "json",
    user=Depends(get_current_user)):
    """导出本体文档（兼容前端 /api/ontology/model/{docId}/export）"""
    try:
        result = model_service.export_document(document_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
