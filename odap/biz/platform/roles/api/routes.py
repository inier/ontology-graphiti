from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from .schemas import RoleType, PermissionScope, Permission, RoleCreate, RoleUpdate, Role, UserRoleAssignRequest
from ..services.role_service import get_role_service
from ..opa_sync import RoleOPASync

router = APIRouter(prefix="/api/roles", tags=["roles"])

role_service = get_role_service()
opa_sync = RoleOPASync()


class SkillBinding(BaseModel):
    skill_id: str
    enabled: bool = True


class PolicyBinding(BaseModel):
    policy_id: str
    priority: int = 0
    enabled: bool = True


@router.get("")
async def list_roles(page: int = 1, page_size: int = 50):
    try:
        return role_service.list_roles(page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{role_id}")
async def get_role(role_id: str):
    try:
        result = role_service.get_role(role_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_role(role: RoleCreate):
    try:
        result = role_service.create_role(
            name=role.name,
            description=role.description,
            role_type=role.role_type,
            permissions=role.permissions,
        )
        opa_sync.sync_role_to_opa(result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{role_id}")
async def update_role(role_id: str, role: RoleUpdate):
    try:
        updates = {}
        if role.name is not None:
            updates["name"] = role.name
        if role.description is not None:
            updates["description"] = role.description
        if role.role_type is not None:
            updates["role_type"] = role.role_type
        if role.permissions is not None:
            updates["permissions"] = role.permissions

        result = role_service.update_role(role_id, updates)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        opa_sync.sync_role_to_opa(result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{role_id}")
async def delete_role(role_id: str):
    try:
        result = role_service.delete_role(role_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        opa_sync.remove_role_from_opa(role_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/permissions/all")
async def list_permissions():
    try:
        from ..storage import SQLiteRoleStorage
        storage = SQLiteRoleStorage()
        perms = storage.list_permissions()
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "scope": p.scope.value if hasattr(p.scope, "value") else p.scope,
                "actions": p.actions,
            }
            for p in perms
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{role_id}/users")
async def assign_role_to_user(role_id: str, request: UserRoleAssignRequest):
    try:
        result = role_service.assign_role_to_user(
            role_id=role_id,
            user_id=request.user_id,
            workspace_id=request.workspace_id,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{role_id}/users/{user_id}")
async def revoke_role_from_user(role_id: str, user_id: str, workspace_id: Optional[str] = None):
    try:
        result = role_service.revoke_role_from_user(
            role_id=role_id,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/roles")
async def get_user_roles(user_id: str):
    try:
        return role_service.get_user_roles(user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/workspaces/{workspace_id}/roles")
async def get_user_roles_in_workspace(user_id: str, workspace_id: str):
    try:
        return role_service.get_user_roles_in_workspace(user_id, workspace_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{role_id}/skills")
async def bind_skill(role_id: str, binding: SkillBinding):
    try:
        from ..storage import SQLiteRoleStorage
        storage = SQLiteRoleStorage()
        storage.bind_skill(role_id, binding.skill_id, binding.enabled)
        return {"message": "Skill 绑定成功", "skill_id": binding.skill_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{role_id}/skills/{skill_id}")
async def unbind_skill(role_id: str, skill_id: str):
    try:
        from ..storage import SQLiteRoleStorage
        storage = SQLiteRoleStorage()
        success = storage.unbind_skill(role_id, skill_id)
        if not success:
            raise HTTPException(status_code=404, detail="Skill 绑定不存在")
        return {"message": "Skill 解绑成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{role_id}/skills")
async def get_role_skills(role_id: str):
    try:
        from ..storage import SQLiteRoleStorage
        storage = SQLiteRoleStorage()
        return storage.get_role_skills(role_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{role_id}/policies")
async def bind_policy(role_id: str, binding: PolicyBinding):
    try:
        from ..storage import SQLiteRoleStorage
        storage = SQLiteRoleStorage()
        storage.bind_policy(role_id, binding.policy_id, binding.priority, binding.enabled)
        return {"message": "Policy 绑定成功", "policy_id": binding.policy_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{role_id}/policies/{policy_id}")
async def unbind_policy(role_id: str, policy_id: str):
    try:
        from ..storage import SQLiteRoleStorage
        storage = SQLiteRoleStorage()
        success = storage.unbind_policy(role_id, policy_id)
        if not success:
            raise HTTPException(status_code=404, detail="Policy 绑定不存在")
        return {"message": "Policy 解绑成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{role_id}/policies")
async def get_role_policies(role_id: str):
    try:
        from ..storage import SQLiteRoleStorage
        storage = SQLiteRoleStorage()
        return storage.get_role_policies(role_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
