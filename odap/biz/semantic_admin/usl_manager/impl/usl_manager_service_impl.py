"""USL Manager - UslManagerServiceImpl（仓储 ABC 实现）。

依赖 SQLiteUslStorage 实例。
职责：
- 接收 Pydantic Model（或 dict payload），序列化为 Storage 可持久化 dict
- 调用 Storage CRUD
- 把 Storage 返回的 dict 反序列化为 Pydantic Model（或 None）
- 所有业务级错误 raise ValueError（例如引用不存在的 domain_id）

AGENTS.md 规则：
- impl 层 raise ValueError("描述")，不抛 HTTPException
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from ..interfaces import UslRepository
from ..models import (
    DataType,
    HierarchyRel,
    SemanticType,
    UslCardinality,
    UslDisjointPair,
    UslDomain,
    UslHierarchy,
    UslPropertySpec,
    UslTerm,
)
from ..storage import SQLiteUslStorage


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UslManagerServiceImpl(UslRepository):
    """UslRepository 仓储实现（基于 SQLiteUslStorage）。"""

    def __init__(self, storage: Optional[SQLiteUslStorage] = None) -> None:
        self.storage: SQLiteUslStorage = storage or SQLiteUslStorage()

    # ----------------------------------------------------------------
    # 内部校验工具
    # ----------------------------------------------------------------

    def _ensure_domain_exists(self, domain_id: str, ctx: str = "") -> None:
        """校验领域 ID 存在，否则 raise ValueError。"""
        if not domain_id:
            raise ValueError(f"{ctx}: domain_id 不能为空")
        if not self.storage.get_domain(domain_id):
            raise ValueError(f"{ctx}: 领域不存在 ({domain_id})")

    # =================================================================
    # Domain
    # =================================================================

    def save_domain(self, domain: UslDomain) -> UslDomain:
        d = domain.model_dump()
        d["updated_at"] = _utc_now_iso()
        saved = self.storage.save_domain(d)
        return UslDomain(**saved)

    def get_domain(self, domain_id: str) -> Optional[UslDomain]:
        row = self.storage.get_domain(domain_id)
        return UslDomain(**row) if row else None

    def get_domain_by_code(self, code: str) -> Optional[UslDomain]:
        row = self.storage.get_domain_by_code(code)
        return UslDomain(**row) if row else None

    def list_domains(
        self, page: int = 1, page_size: int = 50
    ) -> Tuple[List[UslDomain], int]:
        rows, total = self.storage.list_domains(page=page, page_size=page_size)
        return [UslDomain(**r) for r in rows], total

    def delete_domain(self, domain_id: str) -> bool:
        return self.storage.delete_domain(domain_id)

    # =================================================================
    # Term
    # =================================================================

    def save_term(self, term: UslTerm) -> UslTerm:
        self._ensure_domain_exists(
            term.domain_id, ctx=f"save_term(canonical={term.canonical})"
        )
        d = term.model_dump()
        # Pydantic -> 存储格式：Enum -> value
        if isinstance(d.get("semantic_type"), SemanticType):
            d["semantic_type"] = d["semantic_type"].value
        d["updated_at"] = _utc_now_iso()
        saved = self.storage.save_term(d)
        return UslTerm(**saved)

    def get_term(self, term_id: str) -> Optional[UslTerm]:
        row = self.storage.get_term(term_id)
        return UslTerm(**row) if row else None

    def list_terms(
        self,
        domain_id: Optional[str] = None,
        semantic_type: Optional[str] = None,
        synonym_keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Tuple[List[UslTerm], int]:
        # 如果 semantic_type 是 Enum 转 value
        st_value: Optional[str] = None
        if semantic_type is not None:
            if isinstance(semantic_type, SemanticType):
                st_value = semantic_type.value
            else:
                # 校验合法性，非法值 raise ValueError
                valid = {e.value for e in SemanticType}
                if str(semantic_type) not in valid:
                    raise ValueError(
                        f"非法 semantic_type: {semantic_type}，"
                        f"有效取值: {sorted(valid)}"
                    )
                st_value = str(semantic_type)
        rows, total = self.storage.list_terms(
            domain_id=domain_id,
            semantic_type=st_value,
            synonym_keyword=synonym_keyword,
            page=page,
            page_size=page_size,
        )
        return [UslTerm(**r) for r in rows], total

    def delete_term(self, term_id: str) -> bool:
        return self.storage.delete_term(term_id)

    # =================================================================
    # Hierarchy
    # =================================================================

    def save_hierarchy(self, hierarchy: UslHierarchy) -> UslHierarchy:
        self._ensure_domain_exists(hierarchy.domain_id, ctx="save_hierarchy")
        d = hierarchy.model_dump()
        if isinstance(d.get("rel_type"), HierarchyRel):
            d["rel_type"] = d["rel_type"].value
        saved = self.storage.save_hierarchy(d)
        return UslHierarchy(**saved)

    def get_hierarchy(self, hierarchy_id: str) -> Optional[UslHierarchy]:
        row = self.storage.get_hierarchy(hierarchy_id)
        return UslHierarchy(**row) if row else None

    def list_hierarchies(
        self,
        domain_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[UslHierarchy], int]:
        rows, total = self.storage.list_hierarchies(
            domain_id=domain_id,
            page=page,
            page_size=page_size,
        )
        return [UslHierarchy(**r) for r in rows], total

    def delete_hierarchy(self, hierarchy_id: str) -> bool:
        return self.storage.delete_hierarchy(hierarchy_id)

    # =================================================================
    # PropertySpec
    # =================================================================

    def save_property_spec(self, spec: UslPropertySpec) -> UslPropertySpec:
        self._ensure_domain_exists(
            spec.domain_id, ctx=f"save_property_spec({spec.for_term}.{spec.prop_name})"
        )
        d = spec.model_dump()
        if isinstance(d.get("data_type"), DataType):
            d["data_type"] = d["data_type"].value
        saved = self.storage.save_property_spec(d)
        return UslPropertySpec(**saved)

    def get_property_spec(self, spec_id: str) -> Optional[UslPropertySpec]:
        row = self.storage.get_property_spec(spec_id)
        return UslPropertySpec(**row) if row else None

    def list_property_specs(
        self,
        domain_id: Optional[str] = None,
        for_term: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[UslPropertySpec], int]:
        rows, total = self.storage.list_property_specs(
            domain_id=domain_id,
            for_term=for_term,
            page=page,
            page_size=page_size,
        )
        return [UslPropertySpec(**r) for r in rows], total

    def delete_property_spec(self, spec_id: str) -> bool:
        return self.storage.delete_property_spec(spec_id)

    # =================================================================
    # DisjointPair
    # =================================================================

    def save_disjoint_pair(self, pair: UslDisjointPair) -> UslDisjointPair:
        self._ensure_domain_exists(
            pair.domain_id, ctx=f"save_disjoint_pair({pair.term_a}|{pair.term_b})"
        )
        d = pair.model_dump()
        saved = self.storage.save_disjoint_pair(d)
        return UslDisjointPair(**saved)

    def get_disjoint_pair(self, pair_id: str) -> Optional[UslDisjointPair]:
        row = self.storage.get_disjoint_pair(pair_id)
        return UslDisjointPair(**row) if row else None

    def list_disjoint_pairs(
        self,
        domain_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[UslDisjointPair], int]:
        rows, total = self.storage.list_disjoint_pairs(
            domain_id=domain_id,
            page=page,
            page_size=page_size,
        )
        return [UslDisjointPair(**r) for r in rows], total

    def delete_disjoint_pair(self, pair_id: str) -> bool:
        return self.storage.delete_disjoint_pair(pair_id)

    # =================================================================
    # Cardinality
    # =================================================================

    def save_cardinality(self, card: UslCardinality) -> UslCardinality:
        self._ensure_domain_exists(
            card.domain_id, ctx=f"save_cardinality({card.rel_name})"
        )
        d = card.model_dump()
        saved = self.storage.save_cardinality(d)
        return UslCardinality(**saved)

    def get_cardinality(self, card_id: str) -> Optional[UslCardinality]:
        row = self.storage.get_cardinality(card_id)
        return UslCardinality(**row) if row else None

    def list_cardinalities(
        self,
        domain_id: Optional[str] = None,
        rel_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[UslCardinality], int]:
        rows, total = self.storage.list_cardinalities(
            domain_id=domain_id,
            rel_name=rel_name,
            page=page,
            page_size=page_size,
        )
        return [UslCardinality(**r) for r in rows], total

    def delete_cardinality(self, card_id: str) -> bool:
        return self.storage.delete_cardinality(card_id)


__all__ = ["UslManagerServiceImpl"]
