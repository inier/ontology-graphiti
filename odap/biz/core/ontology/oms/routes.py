from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from .schemas import (
    ObjectTypeDefinition, OntologySchemaCreate, OntologySchemaUpdate,
    ActionTypeDefinition, ActionTypeCreate, ActionTypeUpdate,
)
from .storage.sqlite_oms_storage import SQLiteOMSStorage

router = APIRouter(prefix="/api/ontology/oms", tags=["ontology-metadata"])

storage = SQLiteOMSStorage()


# ── Object Type CRUD ──

@router.get("/object-types", response_model=List[ObjectTypeDefinition])
async def list_object_types(active_only: bool = Query(True)):
    return storage.list_object_types(active_only=active_only)


@router.get("/object-types/{type_id}", response_model=ObjectTypeDefinition)
async def get_object_type(type_id: str):
    obj = storage.get_object_type(type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="对象类型不存在")
    return obj


@router.post("/object-types", response_model=ObjectTypeDefinition)
async def create_object_type(data: OntologySchemaCreate):
    return storage.create_object_type(data.model_dump())


@router.put("/object-types/{type_id}", response_model=ObjectTypeDefinition)
async def update_object_type(type_id: str, data: OntologySchemaUpdate):
    updated = storage.update_object_type(type_id, data.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="对象类型不存在")
    return updated


@router.delete("/object-types/{type_id}")
async def delete_object_type(type_id: str):
    success = storage.delete_object_type(type_id)
    if not success:
        raise HTTPException(status_code=404, detail="对象类型不存在")
    return {"message": "对象类型删除成功"}


# ── Action Type CRUD ──

@router.get("/action-types", response_model=List[ActionTypeDefinition])
async def list_action_types(target_type: Optional[str] = Query(None)):
    return storage.list_action_types(target_type=target_type)


@router.get("/action-types/{action_type_id}", response_model=ActionTypeDefinition)
async def get_action_type(action_type_id: str):
    act = storage.get_action_type(action_type_id)
    if not act:
        raise HTTPException(status_code=404, detail="动作类型不存在")
    return act


@router.post("/action-types", response_model=ActionTypeDefinition)
async def create_action_type(data: ActionTypeCreate):
    return storage.create_action_type(data.model_dump())


@router.put("/action-types/{action_type_id}", response_model=ActionTypeDefinition)
async def update_action_type(action_type_id: str, data: ActionTypeUpdate):
    updated = storage.update_action_type(action_type_id, data.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="动作类型不存在")
    return updated


@router.delete("/action-types/{action_type_id}")
async def delete_action_type(action_type_id: str):
    success = storage.delete_action_type(action_type_id)
    if not success:
        raise HTTPException(status_code=404, detail="动作类型不存在")
    return {"message": "动作类型删除成功"}


# ── Binding ──

@router.post("/object-types/{type_id}/actions/{action_type_id}")
async def bind_action(type_id: str, action_type_id: str):
    success = storage.bind_action_to_object_type(type_id, action_type_id)
    if not success:
        raise HTTPException(status_code=400, detail="绑定失败，请检查对象类型和动作类型是否存在")
    return {"message": "绑定成功"}


@router.delete("/object-types/{type_id}/actions/{action_type_id}")
async def unbind_action(type_id: str, action_type_id: str):
    success = storage.unbind_action_from_object_type(type_id, action_type_id)
    if not success:
        raise HTTPException(status_code=400, detail="解绑失败")
    return {"message": "解绑成功"}
