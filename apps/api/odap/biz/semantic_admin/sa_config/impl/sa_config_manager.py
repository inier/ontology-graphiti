"""SaConfigManager impl：业务语义封装。

提供领域语义便捷方法 + 内置常量迁移：
  - get_domain_semantic / set_domain_semantic: 按 code 读写 domain:{code}/semantic_layer
  - ensure_builtin_domains(): 首次启动从 legacy 常量写入 sa_config（幂等）
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from odap.biz.semantic_admin.sa_config.interfaces import ISaConfigStorage
from odap.biz.semantic_admin.sa_config.models import SaConfigEntry
from odap.biz.semantic_admin.sa_config.storage import Storage as SQLiteSaConfigStorage


_BUILTIN_SEMANTIC_SCOPES = {
    "sanguo": "domain:sanguo",
    "xiyou": "domain:xiyou",
    "shared": "domain:shared",
}
_SEMANTIC_KEY = "semantic_layer"


def _load_legacy_const(domain_code: str) -> Optional[Dict[str, Any]]:
    """Legacy 硬编码常量加载路径 —— **已死**，永远返回 None。

    历史：此函数曾在首次启动、DB 尚未落库时，从旧硬编码模块
    `odap.biz.core.ontology.semantic_layer.semantic_config` 加载
    SANGUO_SEMANTIC / XIYOU_SEMANTIC / SHARED_SEMANTIC 三个 dict。

    现状：`semantic_layer` 模块在 flat→3+1 架构迁移中已被物理移除，
    全仓 grep 亦无 `semantic_config` 符号。原实现用 `try/except Exception:
    return None` 静默降级，直接违反 AGENTS.md 规则 14（禁止未经确认的兜底）。

    Stage E 修复：删除静默 try/except，改为显式 return None，并把死因写入
    docstring。函数签名与调用点（第 103/129 行 `legacy = _load_legacy_const(...)`
    → `if legacy: ...`）保持兼容，行为完全等价，但不再是"隐藏的兜底"。

    烧账方向：调用点在 DB 落库路径已稳定的今天，可以直接删除本函数与两处调用；
    此次修复保守起见仅去掉静默降级，物理删除留待后续独立 PR。
    """
    return None


class SaConfigManager:
    def __init__(self, storage: Optional[ISaConfigStorage] = None):
        self.storage: ISaConfigStorage = storage or SQLiteSaConfigStorage()

    def set(
        self,
        scope: str,
        config_key: str,
        value: Any,
        updated_by: str = "system",
    ) -> Dict[str, Any]:
        entry = SaConfigEntry(
            scope=scope,
            config_key=config_key,
            config_value=value if isinstance(value, dict) else {"value": value},
            updated_by=updated_by,
        )
        saved = self.storage.save_config(entry)
        return {
            "id": saved.id,
            "scope": saved.scope,
            "config_key": saved.config_key,
            "config_value": saved.config_value,
            "updated_at": saved.updated_at,
            "updated_by": saved.updated_by,
        }

    def get(
        self, scope: str, config_key: str, default: Any = None
    ) -> Any:
        entry = self.storage.get_config(scope, config_key)
        if entry is None:
            return default
        return entry.config_value

    def delete(self, scope: str, config_key: str) -> bool:
        return self.storage.delete_config(scope, config_key)

    def list(self, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        items = self.storage.list_configs(scope)
        return [
            {
                "id": e.id,
                "scope": e.scope,
                "config_key": e.config_key,
                "config_value": e.config_value,
                "updated_by": e.updated_by,
                "created_at": e.created_at,
                "updated_at": e.updated_at,
            }
            for e in items
        ]

    def get_domain_semantic(self, domain_code: str) -> Optional[Dict[str, Any]]:
        if domain_code in _BUILTIN_SEMANTIC_SCOPES:
            scope = _BUILTIN_SEMANTIC_SCOPES[domain_code]
        else:
            scope = f"domain:{domain_code}"
        value = self.storage.get_value(scope, _SEMANTIC_KEY)
        if value is None and domain_code in _BUILTIN_SEMANTIC_SCOPES:
            legacy = _load_legacy_const(domain_code)
            if legacy:
                self.set(scope, _SEMANTIC_KEY, legacy, updated_by="migration:legacy")
                value = legacy
        return value

    def set_domain_semantic(
        self,
        domain_code: str,
        semantic_dict: Dict[str, Any],
        updated_by: str = "system",
    ) -> Dict[str, Any]:
        scope = (
            _BUILTIN_SEMANTIC_SCOPES[domain_code]
            if domain_code in _BUILTIN_SEMANTIC_SCOPES
            else f"domain:{domain_code}"
        )
        return self.set(scope, _SEMANTIC_KEY, semantic_dict, updated_by=updated_by)

    def ensure_builtin_domains(self, force_overwrite: bool = False) -> Dict[str, Any]:
        migrated: Dict[str, Any] = {}
        for code in ("sanguo", "xiyou", "shared"):
            exists = self.storage.get_config(_BUILTIN_SEMANTIC_SCOPES[code], _SEMANTIC_KEY)
            if exists and not force_overwrite:
                migrated[code] = {"action": "skip", "id": exists.id}
                continue
            legacy = _load_legacy_const(code)
            if not legacy:
                migrated[code] = {"action": "skip", "reason": "no_legacy_const"}
                continue
            written = self.set(
                _BUILTIN_SEMANTIC_SCOPES[code],
                _SEMANTIC_KEY,
                legacy,
                updated_by="migration:legacy_ensure",
            )
            migrated[code] = {"action": "written", "id": written.get("id")}
        return {
            "scopes": list(_BUILTIN_SEMANTIC_SCOPES.values()),
            "migrated": migrated,
        }


__all__ = ["SaConfigManager"]
