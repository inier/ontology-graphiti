from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from pydantic import BaseModel
from typing import List, Optional

from .schemas import RoleType, PermissionScope, Permission, RoleCreate, RoleUpdate, Role, UserRoleAssignRequest
from ..services.role_service import get_role_service
from ..opa_sync import RoleOPASync

router = APIRouter(prefix="/api/roles", tags=["roles"])

role_service = get_role_service()
opa_sync = RoleOPASync()


def _audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, service: str = "roles", workspace_id: str = "default"):
    """角色审计便捷函数"""
    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource="roles",
            user=user_id,
            service=service,
            result_status=result_status,
            result_message=result_message,
            details=details or {},
            workspace_id=workspace_id,
        )
    except Exception:
        pass


class SkillBinding(BaseModel):
    skill_id: str
    enabled: bool = True


class PolicyBinding(BaseModel):
    policy_id: str
    priority: int = 0
    enabled: bool = True


@router.get("")
async def list_roles(page: int = 1, page_size: int = 50,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.list_roles(page=page, page_size=page_size)
        _audit("role_list", _uid, "success")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_list_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{role_id}")
async def get_role(role_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.get_role(role_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        _audit("role_get", _uid, "success", details={"role_id": role_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_get_failed", _uid, "failure", str(e), details={"role_id": role_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_role(role: RoleCreate,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.create_role(
            name=role.name,
            description=role.description,
            role_type=role.role_type,
            permissions=role.permissions,
        )
        opa_sync.sync_role_to_opa(result)
        _audit("role_create", _uid, "success", details={"name": role.name})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_create_failed", _uid, "failure", str(e), details={"name": role.name})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{role_id}")
async def update_role(role_id: str, role: RoleUpdate,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
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
        _audit("role_update", _uid, "success", details={"role_id": role_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_update_failed", _uid, "failure", str(e), details={"role_id": role_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{role_id}")
async def delete_role(role_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.delete_role(role_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        opa_sync.remove_role_from_opa(role_id)
        _audit("role_delete", _uid, "success", details={"role_id": role_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_delete_failed", _uid, "failure", str(e), details={"role_id": role_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/permissions/all")
async def list_permissions(user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.list_permissions()
        _audit("permission_list", _uid, "success")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("permission_list_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{role_id}/users")
async def assign_role_to_user(role_id: str, request: UserRoleAssignRequest,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.assign_role_to_user(
            role_id=role_id,
            user_id=request.user_id,
            workspace_id=request.workspace_id,
        )
        if result.get("status") == "error":
            _audit("role_assign_failed", _uid, "failure", result.get("message", ""),
                   details={"role_id": role_id, "target_user_id": request.user_id},
                   workspace_id=request.workspace_id or "default")
            raise HTTPException(status_code=400, detail=result["message"])
        _audit("role_assign", _uid, "success",
               details={"role_id": role_id, "target_user_id": request.user_id},
               workspace_id=request.workspace_id or "default")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_assign_failed", _uid, "failure", str(e),
               details={"role_id": role_id}, workspace_id=request.workspace_id or "default")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{role_id}/users/{user_id}")
async def revoke_role_from_user(role_id: str, user_id: str, workspace_id: Optional[str] = None,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.revoke_role_from_user(
            role_id=role_id,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        _audit("role_revoke", _uid, "success",
               details={"role_id": role_id, "target_user_id": user_id},
               workspace_id=workspace_id or "default")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_revoke_failed", _uid, "failure", str(e),
               details={"role_id": role_id, "target_user_id": user_id},
               workspace_id=workspace_id or "default")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/roles")
async def get_user_roles(user_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.get_user_roles(user_id)
        _audit("user_roles_get", _uid, "success", details={"target_user_id": user_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("user_roles_get_failed", _uid, "failure", str(e), details={"target_user_id": user_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/workspaces/{workspace_id}/roles")
async def get_user_roles_in_workspace(user_id: str, workspace_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.get_user_roles_in_workspace(user_id, workspace_id)
        _audit("user_roles_workspace_get", _uid, "success",
               details={"target_user_id": user_id}, workspace_id=workspace_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("user_roles_workspace_get_failed", _uid, "failure", str(e),
               details={"target_user_id": user_id}, workspace_id=workspace_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{role_id}/skills")
async def bind_skill(role_id: str, binding: SkillBinding,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.bind_skill(role_id, binding.skill_id, binding.enabled)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        _audit("role_bind_skill", _uid, "success",
               details={"role_id": role_id, "skill_id": binding.skill_id})
        return {"message": "Skill 绑定成功", "skill_id": binding.skill_id}
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_bind_skill_failed", _uid, "failure", str(e),
               details={"role_id": role_id, "skill_id": binding.skill_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{role_id}/skills/{skill_id}")
async def unbind_skill(role_id: str, skill_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.unbind_skill(role_id, skill_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        _audit("role_unbind_skill", _uid, "success",
               details={"role_id": role_id, "skill_id": skill_id})
        return {"message": "Skill 解绑成功"}
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_unbind_skill_failed", _uid, "failure", str(e),
               details={"role_id": role_id, "skill_id": skill_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{role_id}/skills")
async def get_role_skills(role_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.get_role_skills(role_id)
        _audit("role_skills_get", _uid, "success", details={"role_id": role_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_skills_get_failed", _uid, "failure", str(e), details={"role_id": role_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{role_id}/policies")
async def bind_policy(role_id: str, binding: PolicyBinding,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.bind_policy(role_id, binding.policy_id, binding.priority, binding.enabled)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        _audit("role_bind_policy", _uid, "success",
               details={"role_id": role_id, "policy_id": binding.policy_id})
        return {"message": "Policy 绑定成功", "policy_id": binding.policy_id}
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_bind_policy_failed", _uid, "failure", str(e),
               details={"role_id": role_id, "policy_id": binding.policy_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{role_id}/policies/{policy_id}")
async def unbind_policy(role_id: str, policy_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.unbind_policy(role_id, policy_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        _audit("role_unbind_policy", _uid, "success",
               details={"role_id": role_id, "policy_id": policy_id})
        return {"message": "Policy 解绑成功"}
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_unbind_policy_failed", _uid, "failure", str(e),
               details={"role_id": role_id, "policy_id": policy_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{role_id}/policies")
async def get_role_policies(role_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = role_service.get_role_policies(role_id)
        _audit("role_policies_get", _uid, "success", details={"role_id": role_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("role_policies_get_failed", _uid, "failure", str(e), details={"role_id": role_id})
        raise HTTPException(status_code=500, detail=str(e))
