"""
InheritanceService 编排层 (T370)

- 业务校验（循环、深度）
- 类型转换（Edge / Mixin → dict）
- 调用链：routes → services → impl → storage
- 错误返回 {"status": "error", "message": "..."}
- 禁止抛 HTTPException
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from odap.infra.security.audit_helper import storage_audit

from ..impl import (
    InheritanceRepositoryImpl,
    InheritanceResolver,
    TypePropertyProvider,
    validate_inheritance_chain,
    validate_mixin_conflicts,
)
from ..interfaces.inheritance_repository import InheritanceRepository
from ..models.inheritance import InheritanceEdge
from ..models.mixin import Mixin

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


class _EntityTypePropertyProvider(TypePropertyProvider):
    """
    从 ObjectType 存储读取属性名。
    复用 odap.biz.core.ontology.design.model 存储。
    """

    def __init__(self, model_storage=None):
        self._storage = model_storage

    def get_property_names(self, type_id: str) -> List[str]:
        if self._storage is None:
            try:
                from odap.biz.core.ontology.design.model.storage.sqlite_model_storage import (
                    SQLiteModelStorage,
                )
                self._storage = SQLiteModelStorage()
            except Exception:
                return []
        et = self._storage.get_entity_type(type_id)
        if not et:
            return []
        return [p.get("name", "") for p in (et.get("properties", []) or []) if p.get("name")]

    def get_property_value(self, type_id: str, property_name: str) -> Any:
        if self._storage is None:
            try:
                from odap.biz.core.ontology.design.model.storage.sqlite_model_storage import (
                    SQLiteModelStorage,
                )
                self._storage = SQLiteModelStorage()
            except Exception:
                return None
        et = self._storage.get_entity_type(type_id)
        if not et:
            return None
        for p in et.get("properties", []) or []:
            if p.get("name") == property_name:
                return p.get("default_value")
        return None


class InheritanceService:
    """继承 + Mixin 编排服务"""

    def __init__(
        self,
        repository: InheritanceRepository = None,
        property_provider: Optional[TypePropertyProvider] = None,
    ):
        self._repo = repository or InheritanceRepositoryImpl()
        self._provider = property_provider

    # ---------- edges ----------

    def add_edge(
        self,
        child_id: str,
        parent_id: str,
        discriminator: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        action = "inheritance.add_edge"
        try:
            if not child_id or not parent_id:
                _audit_failure(action, msg="child_id/parent_id required",
                                details={"child_id_len": len(child_id or ""),
                                         "parent_id_len": len(parent_id or "")})
                return {"status": "error", "message": "child_type_id and parent_type_id are required"}
            if child_id == parent_id:
                _audit_failure(action, msg="child == parent",
                                details={"child_id_len": len(child_id or "")})
                return {"status": "error", "message": "child and parent cannot be the same"}
            # 校验：若添加会形成环则拒绝
            existing = self._repo.list_edges()
            # 模拟新边加入后的图
            new_edge = InheritanceEdge(
                child_type_id=child_id,
                parent_type_id=parent_id,
                depth=1,
                discriminator=discriminator or {},
            )
            simulated = list(existing) + [new_edge.model_dump()]
            validation = validate_inheritance_chain(
                [InheritanceEdge(**e) for e in simulated]
            )
            if not validation.is_valid:
                _audit_failure(action,
                                msg=f"validation failed: {len(validation.errors)} errors",
                                details={"child_id_len": len(child_id or ""),
                                         "parent_id_len": len(parent_id or ""),
                                         "error_count": len(validation.errors),
                                         "warning_count": len(validation.warnings)})
                return {
                    "status": "error",
                    "message": "validation failed",
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                }
            saved = self._repo.save_edge(new_edge.model_dump())
            edge_id = saved.get("id", "")
            _audit_success(action, resource=edge_id,
                            details={"edge_id": edge_id,
                                     "child_id_len": len(child_id or ""),
                                     "parent_id_len": len(parent_id or ""),
                                     "depth": int(saved.get("depth", 1)),
                                     "has_discriminator": bool(discriminator)})
            return self._edge_to_dict(saved)
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"child_id_len": len(child_id or ""),
                                     "parent_id_len": len(parent_id or "")})
            return {"status": "error", "message": f"add_edge failed: {exc}"}

    def remove_edge(self, child_id: str, parent_id: str) -> Dict[str, Any]:
        action = "inheritance.remove_edge"
        try:
            deleted = self._repo.delete_edge_by_pair(child_id, parent_id)
            if not deleted:
                _audit_failure(action, msg="edge not found",
                                details={"child_id_len": len(child_id or ""),
                                         "parent_id_len": len(parent_id or "")})
                return {"status": "error", "message": "Inheritance edge not found"}
            _audit_success(action,
                            details={"child_id_len": len(child_id or ""),
                                     "parent_id_len": len(parent_id or ""),
                                     "deleted": True})
            return {"status": "ok", "child_type_id": child_id, "parent_type_id": parent_id}
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"child_id_len": len(child_id or ""),
                                     "parent_id_len": len(parent_id or "")})
            return {"status": "error", "message": f"remove_edge failed: {exc}"}

    def get_edge(self, edge_id: str) -> Dict[str, Any]:
        action = "inheritance.get_edge"
        try:
            edge = self._repo.get_edge(edge_id)
            if not edge:
                _audit_failure(action, msg="edge not found", resource=edge_id,
                                details={"edge_id": edge_id})
                return {"status": "error", "message": "Inheritance edge not found"}
            _audit_success(action, resource=edge_id,
                            details={"edge_id": edge_id,
                                     "child_id_len": len(str(edge.get("child_type_id", "") or "")),
                                     "parent_id_len": len(str(edge.get("parent_type_id", "") or ""))})
            return self._edge_to_dict(edge)
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=edge_id,
                            details={"edge_id": edge_id})
            return {"status": "error", "message": f"get_edge failed: {exc}"}

    def list_edges(
        self, child_id: str = None, parent_id: str = None
    ) -> Dict[str, Any]:
        action = "inheritance.list_edges"
        try:
            edges = self._repo.list_edges(child_id=child_id, parent_id=parent_id)
            _audit_success(action,
                            details={"has_child_filter": bool(child_id),
                                     "has_parent_filter": bool(parent_id),
                                     "count": len(edges or [])})
            return {
                "edges": [self._edge_to_dict(e) for e in edges],
                "count": len(edges),
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"list_edges failed: {exc}"}

    def list_by_parent(self, parent_id: str) -> Dict[str, Any]:
        return self.list_edges(parent_id=parent_id)

    def list_by_child(self, child_id: str) -> Dict[str, Any]:
        return self.list_edges(child_id=child_id)

    # ---------- mixins ----------

    def add_mixin(self, data: Dict[str, Any]) -> Dict[str, Any]:
        action = "inheritance.add_mixin"
        try:
            if not data.get("name"):
                _audit_failure(action, msg="name required",
                                details={"properties_count": len(data.get("properties", []) or [])})
                return {"status": "error", "message": "name is required"}
            mixin_id = data.get("id") or str(uuid.uuid4())
            mixin = Mixin(
                id=mixin_id,
                name=data["name"],
                description=data.get("description", ""),
                properties=data.get("properties", []),
                target_type_ids=data.get("target_type_ids", []),
            )
            saved = self._repo.save_mixin(mixin.model_dump())
            _audit_success(action, resource=mixin_id,
                            details={"mixin_id": mixin_id,
                                     "properties_count": len(mixin.properties or []),
                                     "target_type_count": len(mixin.target_type_ids or [])})
            return self._mixin_to_dict(saved)
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"add_mixin failed: {exc}"}

    def update_mixin(self, mixin_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        action = "inheritance.update_mixin"
        try:
            existing = self._repo.get_mixin(mixin_id)
            if not existing:
                _audit_failure(action, msg="mixin not found", resource=mixin_id,
                                details={"mixin_id": mixin_id})
                return {"status": "error", "message": "Mixin not found"}
            existing.update({k: v for k, v in data.items() if k != "id"})
            existing["id"] = mixin_id
            self._repo.save_mixin(existing)
            _audit_success(action, resource=mixin_id,
                            details={"mixin_id": mixin_id,
                                     "properties_count": len(existing.get("properties", []) or []),
                                     "target_type_count": len(existing.get("target_type_ids", []) or [])})
            return self._mixin_to_dict(existing)
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=mixin_id,
                            details={"mixin_id": mixin_id})
            return {"status": "error", "message": f"update_mixin failed: {exc}"}

    def remove_mixin(self, mixin_id: str) -> Dict[str, Any]:
        action = "inheritance.remove_mixin"
        try:
            deleted = self._repo.delete_mixin(mixin_id)
            if not deleted:
                _audit_failure(action, msg="mixin not found", resource=mixin_id,
                                details={"mixin_id": mixin_id})
                return {"status": "error", "message": "Mixin not found"}
            _audit_success(action, resource=mixin_id,
                            details={"mixin_id": mixin_id, "deleted": True})
            return {"status": "ok", "mixin_id": mixin_id}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=mixin_id,
                            details={"mixin_id": mixin_id})
            return {"status": "error", "message": f"remove_mixin failed: {exc}"}

    def get_mixin(self, mixin_id: str) -> Dict[str, Any]:
        action = "inheritance.get_mixin"
        try:
            m = self._repo.get_mixin(mixin_id)
            if not m:
                _audit_failure(action, msg="mixin not found", resource=mixin_id,
                                details={"mixin_id": mixin_id})
                return {"status": "error", "message": "Mixin not found"}
            _audit_success(action, resource=mixin_id,
                            details={"mixin_id": mixin_id,
                                     "properties_count": len(m.get("properties", []) or [])})
            return self._mixin_to_dict(m)
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=mixin_id,
                            details={"mixin_id": mixin_id})
            return {"status": "error", "message": f"get_mixin failed: {exc}"}

    def list_mixins(self) -> Dict[str, Any]:
        action = "inheritance.list_mixins"
        try:
            items = self._repo.list_mixins()
            _audit_success(action, details={"count": len(items or [])})
            return {
                "mixins": [self._mixin_to_dict(m) for m in items],
                "count": len(items),
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"list_mixins failed: {exc}"}

    def attach_mixin_to_type(self, mixin_id: str, type_id: str) -> Dict[str, Any]:
        action = "inheritance.attach_mixin_to_type"
        try:
            if not self._repo.get_mixin(mixin_id):
                _audit_failure(action, msg="mixin not found", resource=mixin_id,
                                details={"mixin_id": mixin_id,
                                         "type_id_len": len(type_id or "")})
                return {"status": "error", "message": "Mixin not found"}
            ok = self._repo.attach_mixin_to_type(mixin_id, type_id)
            if not ok:
                _audit_failure(action, msg="attach failed", resource=mixin_id,
                                details={"mixin_id": mixin_id,
                                         "type_id_len": len(type_id or "")})
                return {"status": "error", "message": "Attach failed"}
            _audit_success(action, resource=mixin_id,
                            details={"mixin_id": mixin_id,
                                     "type_id_len": len(type_id or "")})
            return {"status": "ok", "mixin_id": mixin_id, "type_id": type_id}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=mixin_id,
                            details={"mixin_id": mixin_id})
            return {"status": "error", "message": f"attach_mixin_to_type failed: {exc}"}

    def detach_mixin_from_type(self, mixin_id: str, type_id: str) -> Dict[str, Any]:
        action = "inheritance.detach_mixin_from_type"
        try:
            if not self._repo.get_mixin(mixin_id):
                _audit_failure(action, msg="mixin not found", resource=mixin_id,
                                details={"mixin_id": mixin_id,
                                         "type_id_len": len(type_id or "")})
                return {"status": "error", "message": "Mixin not found"}
            ok = self._repo.detach_mixin_from_type(mixin_id, type_id)
            if not ok:
                _audit_failure(action, msg="detach failed", resource=mixin_id,
                                details={"mixin_id": mixin_id,
                                         "type_id_len": len(type_id or "")})
                return {"status": "error", "message": "Detach failed"}
            _audit_success(action, resource=mixin_id,
                            details={"mixin_id": mixin_id,
                                     "type_id_len": len(type_id or "")})
            return {"status": "ok", "mixin_id": mixin_id, "type_id": type_id}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=mixin_id,
                            details={"mixin_id": mixin_id})
            return {"status": "error", "message": f"detach_mixin_from_type failed: {exc}"}

    # ---------- resolve / validate ----------

    def resolve_type(self, type_id: str) -> Dict[str, Any]:
        action = "inheritance.resolve_type"
        try:
            provider = self._provider or _EntityTypePropertyProvider()
            resolver = InheritanceResolver(self._repo, provider)
            all_props = resolver.resolve_all_properties(type_id)
            _audit_success(action,
                            details={"type_id_len": len(type_id or ""),
                                     "property_count": len(all_props or {})})
            return {
                "type_id": type_id,
                "properties": {
                    name: [p.to_dict() for p in chain]
                    for name, chain in all_props.items()
                },
                "count": len(all_props),
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"type_id_len": len(type_id or "")})
            return {"status": "error", "message": f"resolve_type failed: {exc}"}

    def validate_type(self, type_id: str) -> Dict[str, Any]:
        action = "inheritance.validate_type"
        try:
            edges_data = self._repo.list_edges()
            edges = [InheritanceEdge(**e) for e in edges_data]
            chain_result = validate_inheritance_chain(edges)
            # Mixin 冲突：需 type 的 properties
            provider = self._provider or _EntityTypePropertyProvider()
            type_props = provider.get_property_names(type_id)
            # 父类属性
            parent_chain: List[str] = []
            cur = type_id
            visited: set = set()
            while cur and cur not in visited:
                visited.add(cur)
                es = self._repo.list_edges(child_id=cur)
                if not es:
                    break
                cur = es[0].get("parent_type_id", "")
                if cur:
                    parent_chain.append(cur)
            parent_props: List[str] = []
            for p in parent_chain:
                parent_props.extend(provider.get_property_names(p))
            mixins_data = self._repo.list_mixins_for_type(type_id)
            from ..models.mixin import Mixin as _Mixin

            mixins = [_Mixin(**m) for m in mixins_data]
            mixin_result = validate_mixin_conflicts(
                type_id, mixins, type_props, parent_props
            )
            combined_errors = chain_result.errors + mixin_result.errors
            combined_warnings = chain_result.warnings + mixin_result.warnings
            is_valid = len(combined_errors) == 0
            _audit_success(action,
                            details={"type_id_len": len(type_id or ""),
                                     "edge_count": len(edges_data),
                                     "mixin_count": len(mixins_data),
                                     "type_props_count": len(type_props),
                                     "parent_props_count": len(parent_props),
                                     "is_valid": is_valid,
                                     "error_count": len(combined_errors),
                                     "warning_count": len(combined_warnings)})
            return {
                "type_id": type_id,
                "is_valid": is_valid,
                "errors": combined_errors,
                "warnings": combined_warnings,
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"type_id_len": len(type_id or "")})
            return {"status": "error", "message": f"validate_type failed: {exc}"}

    # ---------- 类型转换 ----------

    @staticmethod
    def _edge_to_dict(edge: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": edge.get("id", ""),
            "child_type_id": edge.get("child_type_id", ""),
            "parent_type_id": edge.get("parent_type_id", ""),
            "depth": edge.get("depth", 1),
            "discriminator": edge.get("discriminator", {}) or {},
            "created_at": edge.get("created_at", ""),
        }

    @staticmethod
    def _mixin_to_dict(mixin: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": mixin.get("id", ""),
            "name": mixin.get("name", ""),
            "description": mixin.get("description", ""),
            "properties": list(mixin.get("properties", []) or []),
            "target_type_ids": list(mixin.get("target_type_ids", []) or []),
            "created_at": mixin.get("created_at", ""),
        }
