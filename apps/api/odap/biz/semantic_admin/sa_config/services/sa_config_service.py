"""SaConfigService：编排层，严格 Dict[str, Any] 返回。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from odap.biz.semantic_admin.sa_config.impl import SaConfigManager


class SaConfigService:
    def __init__(self, manager: Optional[SaConfigManager] = None):
        self.manager = manager or SaConfigManager()

    def set_config(
        self,
        scope: str,
        config_key: str,
        value: Any,
        updated_by: str = "system",
    ) -> Dict[str, Any]:
        try:
            if not scope or not config_key:
                return {"status": "error", "message": "scope/config_key 不能为空"}
            r = self.manager.set(scope, config_key, value, updated_by=updated_by)
            return {"status": "ok", **r}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"set_config 失败: {e}"}

    def get_config(
        self,
        scope: str,
        config_key: str,
        default: Any = None,
    ) -> Dict[str, Any]:
        try:
            if not scope or not config_key:
                return {"status": "error", "message": "scope/config_key 不能为空"}
            value = self.manager.get(scope, config_key, default)
            return {
                "status": "ok",
                "scope": scope,
                "config_key": config_key,
                "config_value": value,
            }
        except Exception as e:
            return {"status": "error", "message": f"get_config 失败: {e}"}

    def delete_config(self, scope: str, config_key: str) -> Dict[str, Any]:
        try:
            if not scope or not config_key:
                return {"status": "error", "message": "scope/config_key 不能为空"}
            removed = self.manager.delete(scope, config_key)
            return {
                "status": "ok",
                "scope": scope,
                "config_key": config_key,
                "deleted": removed,
            }
        except Exception as e:
            return {"status": "error", "message": f"delete_config 失败: {e}"}

    def list_configs(self, scope: Optional[str] = None) -> Dict[str, Any]:
        try:
            items: List[Dict[str, Any]] = self.manager.list(scope)
            return {"status": "ok", "items": items, "count": len(items)}
        except Exception as e:
            return {"status": "error", "message": f"list_configs 失败: {e}"}

    def get_domain_semantic(self, domain_code: str) -> Dict[str, Any]:
        try:
            if not domain_code:
                return {"status": "error", "message": "domain_code 不能为空"}
            value = self.manager.get_domain_semantic(domain_code)
            return {
                "status": "ok",
                "domain_code": domain_code,
                "semantic": value,
            }
        except Exception as e:
            return {"status": "error", "message": f"get_domain_semantic 失败: {e}"}

    def set_domain_semantic(
        self,
        domain_code: str,
        semantic: Dict[str, Any],
        updated_by: str = "system",
    ) -> Dict[str, Any]:
        try:
            if not domain_code:
                return {"status": "error", "message": "domain_code 不能为空"}
            if not isinstance(semantic, dict):
                return {"status": "error", "message": "semantic 必须是 dict"}
            r = self.manager.set_domain_semantic(
                domain_code, semantic, updated_by=updated_by
            )
            return {"status": "ok", **r}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"set_domain_semantic 失败: {e}"}

    def ensure_builtin_domains(self, force_overwrite: bool = False) -> Dict[str, Any]:
        try:
            r = self.manager.ensure_builtin_domains(force_overwrite=force_overwrite)
            return {"status": "ok", **r}
        except Exception as e:
            return {"status": "error", "message": f"ensure_builtin_domains 失败: {e}"}


_sa_config_service_singleton: Optional[SaConfigService] = None


def get_sa_config_service() -> SaConfigService:
    global _sa_config_service_singleton
    if _sa_config_service_singleton is None:
        _sa_config_service_singleton = SaConfigService()
    return _sa_config_service_singleton


__all__ = ["SaConfigService", "get_sa_config_service"]
