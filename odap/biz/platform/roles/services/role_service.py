"""角色服务层"""

import uuid
from typing import Dict, Any, List, Optional

from ..api.schemas import Role, RoleType, Permission
from ..storage.sqlite_role_storage import SQLiteRoleStorage


class RoleService:
    """角色服务"""

    def __init__(self):
        self.storage = SQLiteRoleStorage()

    def create_role(
        self,
        name: str,
        description: str,
        role_type: RoleType,
        permissions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        from datetime import datetime
        resolved_perms = []
        for perm_id in (permissions or []):
            perm = self.storage.get_permission(perm_id)
            if perm:
                resolved_perms.append(perm)
        now = datetime.now()
        role = Role(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            role_type=role_type,
            permissions=resolved_perms,
            created_at=now,
            updated_at=now,
        )

        self.storage.save_role(role)
        return self._role_to_dict(role)

    def get_role(self, role_id: str) -> Optional[Dict[str, Any]]:
        """获取角色"""
        role = self.storage.get_role(role_id)
        if not role:
            return {"status": "error", "message": "Role not found"}
        return self._role_to_dict(role)

    def update_role(
        self,
        role_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新角色"""
        role = self.storage.get_role(role_id)
        if not role:
            return {"status": "error", "message": "Role not found"}

        if "name" in updates:
            role.name = updates["name"]
        if "description" in updates:
            role.description = updates["description"]
        if "role_type" in updates:
            role.role_type = updates["role_type"]
        if "permissions" in updates:
            perm_ids = updates["permissions"]
            resolved = []
            for pid in perm_ids:
                if isinstance(pid, str):
                    perm = self.storage.get_permission(pid)
                    if perm:
                        resolved.append(perm)
                elif isinstance(pid, Permission):
                    resolved.append(pid)
            role.permissions = resolved

        self.storage.save_role(role)
        return self._role_to_dict(role)

    def delete_role(self, role_id: str) -> Dict[str, Any]:
        """删除角色"""
        success = self.storage.delete_role(role_id)
        if not success:
            return {"status": "error", "message": "Role not found"}
        return {"status": "success", "message": "Role deleted"}

    def list_roles(
        self,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """列出角色"""
        roles = self.storage.list_roles()

        start = (page - 1) * page_size
        end = start + page_size
        paginated_roles = roles[start:end]

        return {
            "roles": [self._role_to_dict(r) for r in paginated_roles],
            "total": len(roles),
            "page": page,
            "page_size": page_size
        }

    def assign_role_to_user(
        self,
        role_id: str,
        user_id: str,
        workspace_id: Optional[str] = None,
        bound_by: str = "system",
    ) -> Dict[str, Any]:
        role = self.storage.get_role(role_id)
        if not role:
            return {"status": "error", "message": "Role not found"}

        success = self.storage.assign_role_to_user(role_id, user_id, workspace_id, bound_by)
        if not success:
            return {"status": "error", "message": "Role already assigned to user in this context"}
        return {"status": "success", "message": "Role assigned to user"}

    def revoke_role_from_user(
        self,
        role_id: str,
        user_id: str,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        success = self.storage.revoke_role_from_user(role_id, user_id, workspace_id)
        if not success:
            return {"status": "error", "message": "Role binding not found"}
        return {"status": "success", "message": "Role revoked from user"}

    def get_user_roles(self, user_id: str) -> List[Dict[str, Any]]:
        roles = self.storage.get_user_roles(user_id)
        return [self._role_to_dict(r) for r in roles]

    def get_user_roles_in_workspace(self, user_id: str, workspace_id: str) -> List[Dict[str, Any]]:
        roles = self.storage.get_user_roles_in_workspace(user_id, workspace_id)
        return [self._role_to_dict(r) for r in roles]

    def _role_to_dict(self, role: Role) -> Dict[str, Any]:
        return {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "role_type": role.role_type.value if hasattr(role.role_type, "value") else role.role_type,
            "permissions": [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "scope": p.scope.value if hasattr(p.scope, "value") else p.scope,
                    "actions": p.actions,
                }
                for p in role.permissions
            ],
            "created_at": role.created_at.isoformat() if hasattr(role.created_at, "isoformat") else role.created_at,
            "updated_at": role.updated_at.isoformat() if hasattr(role.updated_at, "isoformat") else role.updated_at,
        }


_role_service_instance = None


def get_role_service() -> RoleService:
    """获取角色服务实例（单例）"""
    global _role_service_instance
    if _role_service_instance is None:
        _role_service_instance = RoleService()
    return _role_service_instance
