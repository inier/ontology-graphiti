"""USL Manager - UslRepository 抽象接口（ABC）。

定义 6 类实体的 CRUD + 分页查询抽象方法：
- UslDomain        语义领域
- UslTerm          规范术语
- UslHierarchy     层级关系
- UslPropertySpec  属性规约
- UslDisjointPair  不相交术语对
- UslCardinality   关系基数约束
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from ..models import (
    UslCardinality,
    UslDisjointPair,
    UslDomain,
    UslHierarchy,
    UslPropertySpec,
    UslTerm,
)


class UslRepository(ABC):
    """统一语义层仓储抽象基类。"""

    # ================================================================
    # UslDomain CRUD + 分页
    # ================================================================

    @abstractmethod
    def save_domain(self, domain: UslDomain) -> UslDomain:
        """保存或更新领域（upsert，UNIQUE(code) 冲突则 UPDATE）。"""
        raise NotImplementedError

    @abstractmethod
    def get_domain(self, domain_id: str) -> Optional[UslDomain]:
        """根据 ID 获取领域；不存在返回 None。"""
        raise NotImplementedError

    @abstractmethod
    def get_domain_by_code(self, code: str) -> Optional[UslDomain]:
        """根据 code 字段获取领域；不存在返回 None。"""
        raise NotImplementedError

    @abstractmethod
    def list_domains(
        self,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[UslDomain], int]:
        """分页列出领域，返回 (列表, 总数)。"""
        raise NotImplementedError

    @abstractmethod
    def delete_domain(self, domain_id: str) -> bool:
        """删除领域（级联删除该领域下所有术语/层级/属性/不相交/基数）；返回是否成功。"""
        raise NotImplementedError

    # ================================================================
    # UslTerm CRUD + 分页 + 过滤
    # ================================================================

    @abstractmethod
    def save_term(self, term: UslTerm) -> UslTerm:
        """保存或更新术语（upsert，UNIQUE(domain_id, canonical)）。"""
        raise NotImplementedError

    @abstractmethod
    def get_term(self, term_id: str) -> Optional[UslTerm]:
        """根据 ID 获取术语；不存在返回 None。"""
        raise NotImplementedError

    @abstractmethod
    def list_terms(
        self,
        domain_id: Optional[str] = None,
        semantic_type: Optional[str] = None,
        synonym_keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Tuple[List[UslTerm], int]:
        """分页列出术语，支持 semantic_type 过滤 + 同义词模糊搜索。"""
        raise NotImplementedError

    @abstractmethod
    def delete_term(self, term_id: str) -> bool:
        """删除术语；返回是否成功。"""
        raise NotImplementedError

    # ================================================================
    # UslHierarchy CRUD + 列表
    # ================================================================

    @abstractmethod
    def save_hierarchy(self, hierarchy: UslHierarchy) -> UslHierarchy:
        """保存或更新层级关系（upsert）。"""
        raise NotImplementedError

    @abstractmethod
    def get_hierarchy(self, hierarchy_id: str) -> Optional[UslHierarchy]:
        """根据 ID 获取层级；不存在返回 None。"""
        raise NotImplementedError

    @abstractmethod
    def list_hierarchies(
        self,
        domain_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[UslHierarchy], int]:
        """分页列出层级关系。"""
        raise NotImplementedError

    @abstractmethod
    def delete_hierarchy(self, hierarchy_id: str) -> bool:
        """删除层级关系；返回是否成功。"""
        raise NotImplementedError

    # ================================================================
    # UslPropertySpec CRUD + 列表
    # ================================================================

    @abstractmethod
    def save_property_spec(self, spec: UslPropertySpec) -> UslPropertySpec:
        """保存或更新属性规约（upsert，UNIQUE(domain_id, for_term, prop_name)）。"""
        raise NotImplementedError

    @abstractmethod
    def get_property_spec(self, spec_id: str) -> Optional[UslPropertySpec]:
        """根据 ID 获取属性规约；不存在返回 None。"""
        raise NotImplementedError

    @abstractmethod
    def list_property_specs(
        self,
        domain_id: Optional[str] = None,
        for_term: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[UslPropertySpec], int]:
        """分页列出属性规约，支持 for_term 过滤。"""
        raise NotImplementedError

    @abstractmethod
    def delete_property_spec(self, spec_id: str) -> bool:
        """删除属性规约；返回是否成功。"""
        raise NotImplementedError

    # ================================================================
    # UslDisjointPair CRUD + 列表
    # ================================================================

    @abstractmethod
    def save_disjoint_pair(self, pair: UslDisjointPair) -> UslDisjointPair:
        """保存或更新不相交对（upsert，UNIQUE(domain_id, term_a, term_b)）。"""
        raise NotImplementedError

    @abstractmethod
    def get_disjoint_pair(self, pair_id: str) -> Optional[UslDisjointPair]:
        """根据 ID 获取不相交对；不存在返回 None。"""
        raise NotImplementedError

    @abstractmethod
    def list_disjoint_pairs(
        self,
        domain_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[UslDisjointPair], int]:
        """分页列出不相交对。"""
        raise NotImplementedError

    @abstractmethod
    def delete_disjoint_pair(self, pair_id: str) -> bool:
        """删除不相交对；返回是否成功。"""
        raise NotImplementedError

    # ================================================================
    # UslCardinality CRUD + 列表
    # ================================================================

    @abstractmethod
    def save_cardinality(self, card: UslCardinality) -> UslCardinality:
        """保存或更新基数约束。

        upsert，UNIQUE(domain_id, rel_name, domain_term, range_term)。
        """
        raise NotImplementedError

    @abstractmethod
    def get_cardinality(self, card_id: str) -> Optional[UslCardinality]:
        """根据 ID 获取基数约束；不存在返回 None。"""
        raise NotImplementedError

    @abstractmethod
    def list_cardinalities(
        self,
        domain_id: Optional[str] = None,
        rel_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[UslCardinality], int]:
        """分页列出基数约束，支持 rel_name 过滤。"""
        raise NotImplementedError

    @abstractmethod
    def delete_cardinality(self, card_id: str) -> bool:
        """删除基数约束；返回是否成功。"""
        raise NotImplementedError


__all__ = ["UslRepository"]
