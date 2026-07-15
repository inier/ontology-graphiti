"""Object View - ViewService 编排层 (T410)

服务层规范（AGENTS.md 规则 2）：
- 必须返回 Dict[str, Any]，禁止抛 HTTPException
- 错误格式: {"status": "error", "message": "..."}
- 成功格式: 扁平 dict
- 类型转换: Enum→.value, datetime→.isoformat(), BaseModel→扁平 dict
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from odap.infra.security.audit_helper import storage_audit

from ..impl import ViewQueryEngineImpl, ViewRepositoryImpl
from ..interfaces import ViewQueryContext, ViewQueryResult
from ..models import ObjectView, ViewPermission
from ..storage import SQLiteViewStorage

logger = logging.getLogger(__name__)

_AUDIT_SERVICE = "ontology_design"


def _audit_success(action: str, resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="success",
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


def _audit_failure(action: str, msg: str = "", resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="failure",
            result_message=(msg or "")[:200],
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


class ViewService:
    """视图与权限编排服务"""

    def __init__(
        self,
        repository: ViewRepositoryImpl = None,
        engine: ViewQueryEngineImpl = None,
        storage: SQLiteViewStorage = None,
    ):
        self.storage = storage or SQLiteViewStorage()
        self.repository = repository or ViewRepositoryImpl(storage=self.storage)
        self.engine = engine or ViewQueryEngineImpl(
            permission_provider=self._permission_provider_default
        )

    def set_opa_check(self, opa_check) -> None:
        """注入 OPA 校验函数"""
        self.engine.set_opa_check(opa_check)

    def set_data_loader(self, data_loader) -> None:
        """注入数据加载器"""
        self.engine.set_data_loader(data_loader)

    # ---------- ObjectView CRUD ----------

    def create_view(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """创建视图"""
        action = "view.create_view"
        try:
            view = self._build_view(payload, new_id=True)
            self.repository.save(view)
            _audit_success(action, resource=view.id,
                            details={"view_id": view.id,
                                     "base_type_id_len": len(view.base_type_id or ""),
                                     "role_len": len(view.role or ""),
                                     "projected_count": len(view.projected_properties or []),
                                     "enabled": view.enabled})
            return self._view_to_dict(view)
        except ValueError as exc:
            _audit_failure(action, msg=str(exc),
                            details={"base_type_id_len": len(payload.get("base_type_id", "") or "")})
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            logger.exception("create_view failed")
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"create_view failed: {exc}"}

    def get_view(self, view_id: str) -> Dict[str, Any]:
        """获取视图"""
        action = "view.get_view"
        try:
            view = self.repository.get(view_id)
            if not view:
                _audit_failure(action, msg="view not found", resource=view_id,
                                details={"view_id": view_id})
                return {"status": "error", "message": f"view not found: {view_id}"}
            _audit_success(action, resource=view_id,
                            details={"view_id": view_id,
                                     "base_type_id_len": len(view.base_type_id or ""),
                                     "role_len": len(view.role or "")})
            return self._view_to_dict(view)
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=view_id,
                            details={"view_id": view_id})
            return {"status": "error", "message": f"get_view failed: {exc}"}

    def list_views(
        self,
        base_type: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列出视图；支持 base_type / role 过滤"""
        action = "view.list_views"
        try:
            if base_type:
                views = self.repository.list_by_base_type(base_type)
            elif role:
                views = self.repository.list_by_role(role)
            else:
                views = self.repository.list()
            _audit_success(action,
                            details={"has_base_type_filter": bool(base_type),
                                     "has_role_filter": bool(role),
                                     "count": len(views)})
            return {
                "views": [self._view_to_dict(v) for v in views],
                "count": len(views),
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"list_views failed: {exc}"}

    def update_view(self, view_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """更新视图（部分字段）"""
        action = "view.update_view"
        try:
            existing = self.repository.get(view_id)
            if not existing:
                _audit_failure(action, msg="view not found", resource=view_id,
                                details={"view_id": view_id})
                return {"status": "error", "message": f"view not found: {view_id}"}
            merged = self._merge_view(existing, payload)
            self.repository.save(merged)
            _audit_success(action, resource=view_id,
                            details={"view_id": view_id,
                                     "projected_count": len(merged.projected_properties or []),
                                     "enabled": merged.enabled})
            return self._view_to_dict(merged)
        except ValueError as exc:
            _audit_failure(action, msg=str(exc), resource=view_id,
                            details={"view_id": view_id})
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=view_id,
                            details={"view_id": view_id})
            return {"status": "error", "message": f"update_view failed: {exc}"}

    def delete_view(self, view_id: str) -> Dict[str, Any]:
        """删除视图"""
        action = "view.delete_view"
        try:
            ok = self.repository.delete(view_id)
            if not ok:
                _audit_failure(action, msg="view not found", resource=view_id,
                                details={"view_id": view_id})
                return {"status": "error", "message": f"view not found: {view_id}"}
            _audit_success(action, resource=view_id,
                            details={"view_id": view_id, "deleted": True})
            return {"view_id": view_id, "deleted": True}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=view_id,
                            details={"view_id": view_id})
            return {"status": "error", "message": f"delete_view failed: {exc}"}

    # ---------- 查询 ----------

    def query_view(
        self, view_id: str, context_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行视图查询"""
        action = "view.query_view"
        try:
            view = self.repository.get(view_id)
            if not view:
                _audit_failure(action, msg="view not found", resource=view_id,
                                details={"view_id": view_id})
                return {"status": "error", "message": f"view not found: {view_id}"}
            context = self._build_context(context_payload)
            result: ViewQueryResult = self.engine.query(view, context)
            _audit_success(action, resource=view_id,
                            details={"view_id": view_id,
                                     "role_len": len(context_payload.get("role", "") or ""),
                                     "total_count": int(result.total_count),
                                     "truncated": bool(result.truncated)})
            return self._result_to_dict(result)
        except Exception as exc:
            from ..impl import AccessDeniedError

            if isinstance(exc, AccessDeniedError):
                _audit_failure(action, msg=f"AccessDenied: {exc}", resource=view_id,
                                details={"view_id": view_id, "denied": True})
                return {"status": "error", "message": str(exc)}
            _audit_failure(action, msg=str(exc), resource=view_id,
                            details={"view_id": view_id})
            return {"status": "error", "message": f"query_view failed: {exc}"}

    # ---------- 权限管理 ----------

    def attach_permission(
        self, view_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """为视图添加/更新角色权限"""
        action = "view.attach_permission"
        try:
            view = self.repository.get(view_id)
            if not view:
                _audit_failure(action, msg="view not found", resource=view_id,
                                details={"view_id": view_id})
                return {"status": "error", "message": f"view not found: {view_id}"}
            perm = self._build_perm(view_id, payload)
            self.repository.save_permission(perm)
            _audit_success(action, resource=perm.id,
                            details={"view_id": view_id,
                                     "role_len": len(perm.role or ""),
                                     "can_export": perm.can_export,
                                     "can_share": perm.can_share})
            return self._perm_to_dict(perm)
        except ValueError as exc:
            _audit_failure(action, msg=str(exc), resource=view_id,
                            details={"view_id": view_id})
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=view_id,
                            details={"view_id": view_id})
            return {"status": "error", "message": f"attach_permission failed: {exc}"}

    def detach_permission(self, perm_id: str) -> Dict[str, Any]:
        """删除权限"""
        action = "view.detach_permission"
        try:
            ok = self.repository.delete_permission(perm_id)
            if not ok:
                _audit_failure(action, msg="permission not found", resource=perm_id,
                                details={"perm_id": perm_id})
                return {
                    "status": "error",
                    "message": f"permission not found: {perm_id}",
                }
            _audit_success(action, resource=perm_id,
                            details={"perm_id": perm_id, "deleted": True})
            return {"perm_id": perm_id, "deleted": True}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=perm_id,
                            details={"perm_id": perm_id})
            return {"status": "error", "message": f"detach_permission failed: {exc}"}

    def get_permissions(self, view_id: str) -> Dict[str, Any]:
        """列出视图权限"""
        action = "view.get_permissions"
        try:
            perms = self.repository.get_permissions(view_id)
            _audit_success(action, resource=view_id,
                            details={"view_id": view_id, "count": len(perms)})
            return {
                "permissions": [self._perm_to_dict(p) for p in perms],
                "count": len(perms),
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=view_id,
                            details={"view_id": view_id})
            return {"status": "error", "message": f"get_permissions failed: {exc}"}

    # ---------- 内部工具 ----------

    def _permission_provider_default(
        self, view_id: str, role: str
    ) -> Optional[Dict[str, Any]]:
        """默认权限提供器：从仓储查找并转 dict"""
        perms = self.repository.get_permissions(view_id)
        for p in perms:
            if p.role == role:
                return {
                    "redaction_rules": dict(p.redaction_rules),
                    "can_export": p.can_export,
                    "can_share": p.can_share,
                }
        return None

    @staticmethod
    def _build_view(payload: Dict[str, Any], new_id: bool) -> ObjectView:
        """从 payload 构造 ObjectView；进行字段校验"""
        name = payload.get("name")
        base_type_id = payload.get("base_type_id")
        role = payload.get("role")
        if not name:
            raise ValueError("name is required")
        if not base_type_id:
            raise ValueError("base_type_id is required")
        if not role:
            raise ValueError("role is required")
        if int(payload.get("row_limit", 100)) < 0:
            raise ValueError("row_limit must be >= 0")
        view_id = payload.get("id") if not new_id else None
        return ObjectView(
            id=view_id or payload.get("id") or _new_id(),
            name=name,
            description=payload.get("description", "") or "",
            base_type_id=base_type_id,
            role=role,
            projected_properties=payload.get("projected_properties", []) or [],
            filters=payload.get("filters", {}) or {},
            row_limit=int(payload.get("row_limit", 100)),
            sort_order=payload.get("sort_order", []) or [],
            enabled=bool(payload.get("enabled", True)),
            created_by=payload.get("created_by", "system"),
        )

    @staticmethod
    def _merge_view(existing: ObjectView, payload: Dict[str, Any]) -> ObjectView:
        """合并更新字段；不传则保留原值"""
        merged = {
            "id": existing.id,
            "name": payload.get("name", existing.name),
            "description": payload.get("description", existing.description),
            "base_type_id": payload.get("base_type_id", existing.base_type_id),
            "role": payload.get("role", existing.role),
            "projected_properties": payload.get(
                "projected_properties", list(existing.projected_properties)
            ),
            "filters": payload.get("filters", dict(existing.filters)),
            "row_limit": int(payload.get("row_limit", existing.row_limit)),
            "sort_order": payload.get("sort_order", list(existing.sort_order)),
            "enabled": payload.get("enabled", existing.enabled),
            "created_by": existing.created_by,
        }
        return ViewService._build_view(merged, new_id=False)

    @staticmethod
    def _build_perm(view_id: str, payload: Dict[str, Any]) -> ViewPermission:
        """从 payload 构造 ViewPermission"""
        role = payload.get("role")
        if not role:
            raise ValueError("role is required")
        return ViewPermission(
            view_id=view_id,
            role=role,
            can_export=bool(payload.get("can_export", False)),
            can_share=bool(payload.get("can_share", False)),
            redaction_rules=payload.get("redaction_rules", {}) or {},
        )

    @staticmethod
    def _build_context(payload: Dict[str, Any]) -> ViewQueryContext:
        """从 payload 构造 ViewQueryContext"""
        return ViewQueryContext(
            user_id=payload.get("user_id", ""),
            ws_id=payload.get("ws_id", ""),
            role=payload.get("role", ""),
        )

    @staticmethod
    def _view_to_dict(view: ObjectView) -> Dict[str, Any]:
        """ObjectView → 扁平 dict"""
        return {
            "id": view.id,
            "name": view.name,
            "description": view.description,
            "base_type_id": view.base_type_id,
            "role": view.role,
            "projected_properties": list(view.projected_properties),
            "filters": dict(view.filters),
            "row_limit": int(view.row_limit),
            "sort_order": list(view.sort_order),
            "enabled": bool(view.enabled),
            "created_by": view.created_by,
            "created_at": view.created_at.isoformat(),
            "updated_at": view.updated_at.isoformat(),
        }

    @staticmethod
    def _perm_to_dict(perm: ViewPermission) -> Dict[str, Any]:
        """ViewPermission → 扁平 dict"""
        return {
            "id": perm.id,
            "view_id": perm.view_id,
            "role": perm.role,
            "can_export": bool(perm.can_export),
            "can_share": bool(perm.can_share),
            "redaction_rules": dict(perm.redaction_rules),
            "created_at": perm.created_at.isoformat(),
        }

    @staticmethod
    def _result_to_dict(result: ViewQueryResult) -> Dict[str, Any]:
        """ViewQueryResult → 扁平 dict"""
        return {
            "rows": [dict(r) for r in result.rows],
            "total_count": int(result.total_count),
            "truncated": bool(result.truncated),
        }


def _new_id() -> str:
    """生成 UUID 字符串"""
    import uuid
    return str(uuid.uuid4())
