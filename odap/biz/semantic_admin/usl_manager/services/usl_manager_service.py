"""USL Manager - UslManagerService 编排层。

AGENTS.md 规则 2（严格遵守）：
1. 100% 返回 Dict[str, Any]
2. 错误格式固定为 {"status": "error", "message": "..."}
3. 永远不抛 HTTPException（由 routes 层翻译）
4. 类型转换：
   - Pydantic Model → 扁平 dict（通过 model_dump）
   - Enum 字段 → .value（Impl 层已处理，此处返回的 dict 内已是字符串）
   - datetime → isoformat 字符串（Storage 返回的已是字符串）

Impl 层会 raise ValueError（业务校验失败），此处捕获并转为 error dict。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..impl import UslManagerServiceImpl
from ..models import (
    UslCardinality,
    UslDisjointPair,
    UslDomain,
    UslHierarchy,
    UslPropertySpec,
    UslTerm,
)
from ..storage import SQLiteUslStorage


logger = logging.getLogger(__name__)


# =====================================================================
# 内部工具
# =====================================================================


def _paged_response(
    items: List[Dict[str, Any]],
    total: int,
    page: int,
    page_size: int,
    item_key: str = "items",
) -> Dict[str, Any]:
    """标准分页响应：{items, total, page, page_size}。"""
    return {
        item_key: items,
        "total": int(total),
        "page": int(page),
        "page_size": int(page_size),
    }


class UslManagerService:
    """统一语义层编排服务。

    对外 API：每个方法都返回 Dict[str, Any]。
    成功：返回扁平 dict（或分页 dict）。
    失败：返回 {"status": "error", "message": "..."}。
    """

    def __init__(
        self,
        repository: Optional[UslManagerServiceImpl] = None,
        storage: Optional[SQLiteUslStorage] = None,
    ) -> None:
        self.storage = storage or SQLiteUslStorage()
        self.repository = repository or UslManagerServiceImpl(storage=self.storage)

    # =================================================================
    # Domain
    # =================================================================

    def create_domain(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # code 必填
            code = str(payload.get("code", "")).strip()
            if not code:
                return {"status": "error", "message": "code 不能为空"}
            if not payload.get("display_name"):
                payload["display_name"] = code
            domain = UslDomain(**payload)
            saved = self.repository.save_domain(domain)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("create_domain failed")
            return {"status": "error", "message": f"创建领域失败: {e}"}

    def get_domain(self, domain_id: str) -> Dict[str, Any]:
        try:
            d = self.repository.get_domain(domain_id)
            if not d:
                return {"status": "error", "message": f"领域不存在: {domain_id}"}
            return d.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("get_domain failed")
            return {"status": "error", "message": f"查询领域失败: {e}"}

    def get_domain_by_code(self, code: str) -> Dict[str, Any]:
        try:
            d = self.repository.get_domain_by_code(code)
            if not d:
                return {"status": "error", "message": f"领域 code 不存在: {code}"}
            return d.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("get_domain_by_code failed")
            return {"status": "error", "message": f"查询领域失败: {e}"}

    def list_domains(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        try:
            domains, total = self.repository.list_domains(
                page=page, page_size=page_size
            )
            items = [d.model_dump(mode="json") for d in domains]
            return _paged_response(items, total, page, page_size)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("list_domains failed")
            return {"status": "error", "message": f"列出领域失败: {e}"}

    def update_domain(self, domain_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            current = self.repository.get_domain(domain_id)
            if not current:
                return {"status": "error", "message": f"领域不存在: {domain_id}"}
            # 合并：payload 覆盖 current（id/code 不可改）
            merged = current.model_dump(mode="json")
            for k in ("display_name", "description", "en_mapping"):
                if k in payload and payload[k] is not None:
                    merged[k] = payload[k]
            updated = UslDomain(**merged)
            saved = self.repository.save_domain(updated)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("update_domain failed")
            return {"status": "error", "message": f"更新领域失败: {e}"}

    def delete_domain(self, domain_id: str) -> Dict[str, Any]:
        try:
            current = self.repository.get_domain(domain_id)
            if not current:
                return {"status": "error", "message": f"领域不存在: {domain_id}"}
            ok = self.repository.delete_domain(domain_id)
            return {"status": "ok", "deleted": ok, "id": domain_id}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("delete_domain failed")
            return {"status": "error", "message": f"删除领域失败: {e}"}

    # =================================================================
    # Term
    # =================================================================

    def create_term(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not payload.get("domain_id"):
                return {"status": "error", "message": "domain_id 不能为空"}
            if not str(payload.get("canonical", "")).strip():
                return {"status": "error", "message": "canonical 不能为空"}
            term = UslTerm(**payload)
            saved = self.repository.save_term(term)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("create_term failed")
            return {"status": "error", "message": f"创建术语失败: {e}"}

    def get_term(self, term_id: str) -> Dict[str, Any]:
        try:
            t = self.repository.get_term(term_id)
            if not t:
                return {"status": "error", "message": f"术语不存在: {term_id}"}
            return t.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("get_term failed")
            return {"status": "error", "message": f"查询术语失败: {e}"}

    def list_terms(
        self,
        domain_id: Optional[str] = None,
        semantic_type: Optional[str] = None,
        synonym_keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        try:
            terms, total = self.repository.list_terms(
                domain_id=domain_id,
                semantic_type=semantic_type,
                synonym_keyword=synonym_keyword,
                page=page,
                page_size=page_size,
            )
            items = [t.model_dump(mode="json") for t in terms]
            return _paged_response(items, total, page, page_size)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("list_terms failed")
            return {"status": "error", "message": f"列出术语失败: {e}"}

    def update_term(self, term_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            current = self.repository.get_term(term_id)
            if not current:
                return {"status": "error", "message": f"术语不存在: {term_id}"}
            merged = current.model_dump(mode="json")
            allowed_keys = (
                "semantic_type",
                "synonyms",
                "near_synonyms",
                "aliases",
                "stoplist_flag",
                "definition",
            )
            for k in allowed_keys:
                if k in payload and payload[k] is not None:
                    merged[k] = payload[k]
            updated = UslTerm(**merged)
            saved = self.repository.save_term(updated)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("update_term failed")
            return {"status": "error", "message": f"更新术语失败: {e}"}

    def delete_term(self, term_id: str) -> Dict[str, Any]:
        try:
            current = self.repository.get_term(term_id)
            if not current:
                return {"status": "error", "message": f"术语不存在: {term_id}"}
            ok = self.repository.delete_term(term_id)
            return {"status": "ok", "deleted": ok, "id": term_id}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("delete_term failed")
            return {"status": "error", "message": f"删除术语失败: {e}"}

    # =================================================================
    # Hierarchy
    # =================================================================

    def create_hierarchy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not payload.get("domain_id"):
                return {"status": "error", "message": "domain_id 不能为空"}
            if not payload.get("parent_term") or not payload.get("child_term"):
                return {
                    "status": "error",
                    "message": "parent_term / child_term 不能为空",
                }
            h = UslHierarchy(**payload)
            saved = self.repository.save_hierarchy(h)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("create_hierarchy failed")
            return {"status": "error", "message": f"创建层级失败: {e}"}

    def get_hierarchy(self, hierarchy_id: str) -> Dict[str, Any]:
        try:
            h = self.repository.get_hierarchy(hierarchy_id)
            if not h:
                return {"status": "error", "message": f"层级不存在: {hierarchy_id}"}
            return h.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("get_hierarchy failed")
            return {"status": "error", "message": f"查询层级失败: {e}"}

    def list_hierarchies(
        self,
        domain_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Dict[str, Any]:
        try:
            items_raw, total = self.repository.list_hierarchies(
                domain_id=domain_id,
                page=page,
                page_size=page_size,
            )
            items = [h.model_dump(mode="json") for h in items_raw]
            return _paged_response(items, total, page, page_size)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("list_hierarchies failed")
            return {"status": "error", "message": f"列出层级失败: {e}"}

    def update_hierarchy(
        self, hierarchy_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            current = self.repository.get_hierarchy(hierarchy_id)
            if not current:
                return {"status": "error", "message": f"层级不存在: {hierarchy_id}"}
            merged = current.model_dump(mode="json")
            for k in ("rel_type", "parent_term", "child_term", "confidence"):
                if k in payload and payload[k] is not None:
                    merged[k] = payload[k]
            updated = UslHierarchy(**merged)
            saved = self.repository.save_hierarchy(updated)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("update_hierarchy failed")
            return {"status": "error", "message": f"更新层级失败: {e}"}

    def delete_hierarchy(self, hierarchy_id: str) -> Dict[str, Any]:
        try:
            current = self.repository.get_hierarchy(hierarchy_id)
            if not current:
                return {"status": "error", "message": f"层级不存在: {hierarchy_id}"}
            ok = self.repository.delete_hierarchy(hierarchy_id)
            return {"status": "ok", "deleted": ok, "id": hierarchy_id}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("delete_hierarchy failed")
            return {"status": "error", "message": f"删除层级失败: {e}"}

    # =================================================================
    # PropertySpec
    # =================================================================

    def create_property_spec(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not payload.get("domain_id"):
                return {"status": "error", "message": "domain_id 不能为空"}
            if not payload.get("for_term") or not payload.get("prop_name"):
                return {"status": "error", "message": "for_term / prop_name 不能为空"}
            spec = UslPropertySpec(**payload)
            saved = self.repository.save_property_spec(spec)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("create_property_spec failed")
            return {"status": "error", "message": f"创建属性规约失败: {e}"}

    def get_property_spec(self, spec_id: str) -> Dict[str, Any]:
        try:
            s = self.repository.get_property_spec(spec_id)
            if not s:
                return {"status": "error", "message": f"属性规约不存在: {spec_id}"}
            return s.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("get_property_spec failed")
            return {"status": "error", "message": f"查询属性规约失败: {e}"}

    def list_property_specs(
        self,
        domain_id: Optional[str] = None,
        for_term: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Dict[str, Any]:
        try:
            specs, total = self.repository.list_property_specs(
                domain_id=domain_id,
                for_term=for_term,
                page=page,
                page_size=page_size,
            )
            items = [s.model_dump(mode="json") for s in specs]
            return _paged_response(items, total, page, page_size)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("list_property_specs failed")
            return {"status": "error", "message": f"列出属性规约失败: {e}"}

    def update_property_spec(
        self, spec_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            current = self.repository.get_property_spec(spec_id)
            if not current:
                return {"status": "error", "message": f"属性规约不存在: {spec_id}"}
            merged = current.model_dump(mode="json")
            for k in ("data_type", "unit", "required_flag", "description"):
                if k in payload and payload[k] is not None:
                    merged[k] = payload[k]
            updated = UslPropertySpec(**merged)
            saved = self.repository.save_property_spec(updated)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("update_property_spec failed")
            return {"status": "error", "message": f"更新属性规约失败: {e}"}

    def delete_property_spec(self, spec_id: str) -> Dict[str, Any]:
        try:
            current = self.repository.get_property_spec(spec_id)
            if not current:
                return {"status": "error", "message": f"属性规约不存在: {spec_id}"}
            ok = self.repository.delete_property_spec(spec_id)
            return {"status": "ok", "deleted": ok, "id": spec_id}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("delete_property_spec failed")
            return {"status": "error", "message": f"删除属性规约失败: {e}"}

    # =================================================================
    # DisjointPair
    # =================================================================

    def create_disjoint_pair(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not payload.get("domain_id"):
                return {"status": "error", "message": "domain_id 不能为空"}
            if not payload.get("term_a") or not payload.get("term_b"):
                return {"status": "error", "message": "term_a / term_b 不能为空"}
            if payload["term_a"] == payload["term_b"]:
                return {"status": "error", "message": "term_a 与 term_b 不能相同"}
            pair = UslDisjointPair(**payload)
            saved = self.repository.save_disjoint_pair(pair)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("create_disjoint_pair failed")
            return {"status": "error", "message": f"创建不相交对失败: {e}"}

    def get_disjoint_pair(self, pair_id: str) -> Dict[str, Any]:
        try:
            p = self.repository.get_disjoint_pair(pair_id)
            if not p:
                return {"status": "error", "message": f"不相交对不存在: {pair_id}"}
            return p.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("get_disjoint_pair failed")
            return {"status": "error", "message": f"查询不相交对失败: {e}"}

    def list_disjoint_pairs(
        self,
        domain_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Dict[str, Any]:
        try:
            pairs, total = self.repository.list_disjoint_pairs(
                domain_id=domain_id,
                page=page,
                page_size=page_size,
            )
            items = [p.model_dump(mode="json") for p in pairs]
            return _paged_response(items, total, page, page_size)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("list_disjoint_pairs failed")
            return {"status": "error", "message": f"列出不相交对失败: {e}"}

    def update_disjoint_pair(
        self, pair_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            current = self.repository.get_disjoint_pair(pair_id)
            if not current:
                return {"status": "error", "message": f"不相交对不存在: {pair_id}"}
            merged = current.model_dump(mode="json")
            if "term_a" in payload and payload["term_a"] is not None:
                merged["term_a"] = payload["term_a"]
            if "term_b" in payload and payload["term_b"] is not None:
                merged["term_b"] = payload["term_b"]
            if merged["term_a"] == merged["term_b"]:
                return {"status": "error", "message": "term_a 与 term_b 不能相同"}
            if "reason" in payload and payload["reason"] is not None:
                merged["reason"] = payload["reason"]
            updated = UslDisjointPair(**merged)
            saved = self.repository.save_disjoint_pair(updated)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("update_disjoint_pair failed")
            return {"status": "error", "message": f"更新不相交对失败: {e}"}

    def delete_disjoint_pair(self, pair_id: str) -> Dict[str, Any]:
        try:
            current = self.repository.get_disjoint_pair(pair_id)
            if not current:
                return {"status": "error", "message": f"不相交对不存在: {pair_id}"}
            ok = self.repository.delete_disjoint_pair(pair_id)
            return {"status": "ok", "deleted": ok, "id": pair_id}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("delete_disjoint_pair failed")
            return {"status": "error", "message": f"删除不相交对失败: {e}"}

    # =================================================================
    # Cardinality
    # =================================================================

    def create_cardinality(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not payload.get("domain_id"):
                return {"status": "error", "message": "domain_id 不能为空"}
            if (
                not payload.get("rel_name")
                or not payload.get("domain_term")
                or not payload.get("range_term")
            ):
                return {
                    "status": "error",
                    "message": "rel_name / domain_term / range_term 不能为空",
                }
            card = UslCardinality(**payload)
            saved = self.repository.save_cardinality(card)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("create_cardinality failed")
            return {"status": "error", "message": f"创建基数约束失败: {e}"}

    def get_cardinality(self, card_id: str) -> Dict[str, Any]:
        try:
            c = self.repository.get_cardinality(card_id)
            if not c:
                return {"status": "error", "message": f"基数约束不存在: {card_id}"}
            return c.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("get_cardinality failed")
            return {"status": "error", "message": f"查询基数约束失败: {e}"}

    def list_cardinalities(
        self,
        domain_id: Optional[str] = None,
        rel_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Dict[str, Any]:
        try:
            cards, total = self.repository.list_cardinalities(
                domain_id=domain_id,
                rel_name=rel_name,
                page=page,
                page_size=page_size,
            )
            items = [c.model_dump(mode="json") for c in cards]
            return _paged_response(items, total, page, page_size)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("list_cardinalities failed")
            return {"status": "error", "message": f"列出基数约束失败: {e}"}

    def update_cardinality(
        self, card_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            current = self.repository.get_cardinality(card_id)
            if not current:
                return {"status": "error", "message": f"基数约束不存在: {card_id}"}
            merged = current.model_dump(mode="json")
            for k in ("rel_name", "domain_term", "range_term", "min_card", "max_card"):
                if k in payload and payload[k] is not None:
                    merged[k] = payload[k]
            updated = UslCardinality(**merged)
            saved = self.repository.save_cardinality(updated)
            return saved.model_dump(mode="json")
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("update_cardinality failed")
            return {"status": "error", "message": f"更新基数约束失败: {e}"}

    def delete_cardinality(self, card_id: str) -> Dict[str, Any]:
        try:
            current = self.repository.get_cardinality(card_id)
            if not current:
                return {"status": "error", "message": f"基数约束不存在: {card_id}"}
            ok = self.repository.delete_cardinality(card_id)
            return {"status": "ok", "deleted": ok, "id": card_id}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("delete_cardinality failed")
            return {"status": "error", "message": f"删除基数约束失败: {e}"}

    # =================================================================
    # Role Assignments
    # =================================================================

    def assign_role(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            saved = self.storage.assign_role(payload)
            return saved
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("assign_role failed")
            return {"status": "error", "message": f"分配角色失败: {e}"}

    def get_role_assignment(
        self, workspace_id: str, user_id: str
    ) -> Dict[str, Any]:
        try:
            assignment = self.storage.get_role_assignment(workspace_id, user_id)
            if not assignment:
                return {
                    "status": "error",
                    "message": (
                        f"未找到角色分配: workspace_id={workspace_id!r}, "
                        f"user_id={user_id!r}"
                    ),
                }
            return assignment
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("get_role_assignment failed")
            return {"status": "error", "message": f"查询角色分配失败: {e}"}

    def list_role_assignments(
        self,
        *,
        workspace_id: Optional[str] = None,
        ws_role: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        try:
            items, total = self.storage.list_role_assignments(
                workspace_id=workspace_id,
                ws_role=ws_role,
                user_id=user_id,
                page=page,
                page_size=page_size,
            )
            return _paged_response(items, total, page, page_size)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("list_role_assignments failed")
            return {"status": "error", "message": f"列出角色分配失败: {e}"}

    def remove_role_assignment(self, assignment_id: str) -> Dict[str, Any]:
        try:
            ok = self.storage.delete_role_assignment(assignment_id)
            return {"status": "ok", "deleted": bool(ok), "id": assignment_id}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("remove_role_assignment failed")
            return {"status": "error", "message": f"删除角色分配失败: {e}"}


__all__ = ["UslManagerService"]
