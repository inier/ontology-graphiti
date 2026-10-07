"""UslTermResolver — USL 术语精确字典查表（确定性同义词泛化）。

本体论原则：同义词泛化必须通过 USL 术语字典的**精确查表**完成，
禁止字符相似度阈值 / 向量近似 / LLM 语义判断（这些都引入不确定性）。

原理：
- 预加载某领域（domain_id）的全部 UslTerm，构建 精确映射表：
    { expression -> canonical }
  其中 expression ∈ {canonical, synonyms, near_synonyms, aliases}。
- resolve(expression) 做 O(1) 精确命中，命中返回 canonical；未命中返回原词（不猜测）。
- 停用词（stoplist_flag=True）不参与映射。

这保证：同一 expression 在任何时候解析结果**确定且唯一**，无阈值、无概率。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class UslTermResolver:
    """USL 术语精确解析器（同义词 → canonical 归一化）"""

    def __init__(self):
        self._maps: Dict[str, Dict[str, str]] = {}          # domain_id -> {expr -> canonical}
        self._loaded_domains: Dict[str, List[Dict]] = {}    # domain_id -> raw terms

    def load_terms(self, domain_id: str, terms: List[Dict[str, Any]]) -> None:
        """加载领域术语，构建精确映射表。

        Args:
            domain_id: 领域 ID
            terms: UslTerm 的 dict 列表（model_dump 结果）
        """
        mapping: Dict[str, str] = {}
        raw: List[Dict] = []
        for t in terms:
            raw.append(t)
            # 停用词不参与映射
            if t.get("stoplist_flag"):
                continue
            canonical = str(t.get("canonical", "")).strip()
            if not canonical:
                continue
            # 收集所有表达（canonical + synonyms + near_synonyms + aliases）
            expressions = [canonical]
            for key in ("synonyms", "near_synonyms", "aliases"):
                for expr in (t.get(key) or []):
                    e = str(expr).strip()
                    if e:
                        expressions.append(e)
            for e in expressions:
                # 精确映射：同表达只保留一个 canonical（首个 wins，确定性）
                if e not in mapping:
                    mapping[e] = canonical

        self._maps[domain_id] = mapping
        self._loaded_domains[domain_id] = raw

    def resolve(self, expression: str, domain_id: str = "") -> str:
        """将表达精确归一化为 canonical。

        Args:
            expression: 待解析表达（词/短语）
            domain_id: 领域 ID（空则查询全部已加载领域）

        Returns:
            canonical（命中）；原词（未命中，不猜测）
        """
        expr = (expression or "").strip()
        if not expr:
            return ""

        if domain_id:
            mapping = self._maps.get(domain_id, {})
            return mapping.get(expr, expr)

        # 全领域：按加载顺序首个命中
        for mapping in self._maps.values():
            if expr in mapping:
                return mapping[expr]
        return expr

    def resolve_all(self, expressions: List[str], domain_id: str = "") -> List[str]:
        """批量归一化（保持顺序，去重保序）"""
        seen: List[str] = []
        for e in expressions:
            canonical = self.resolve(e, domain_id)
            if canonical and canonical not in seen:
                seen.append(canonical)
        return seen

    def is_known_term(self, expression: str, domain_id: str = "") -> bool:
        """判断表达是否为已知术语（canonical 或同义词）"""
        expr = (expression or "").strip()
        if not expr:
            return False
        if domain_id:
            return expr in self._maps.get(domain_id, {})
        return any(expr in m for m in self._maps.values())

    def canonical_of(self, expression: str, domain_id: str = "",
                     *, emit: bool = True) -> Optional[str]:
        """返回 canonical，未命中返回 None（区别于 resolve 的原词回退）。

        emit=True（默认）：未命中时发 TERM_RESOLVE_MISS 缺口信号——运行时归因路径。
        emit=False：只读查询、不发信号——供 resolve-check 等「读侧判定」调用，
        避免读操作反向污染 heat 排名 / 复活已裁决缺口（ADR-086 终审 M1 回归守卫）。
        """
        expr = (expression or "").strip()
        if not expr:
            return None
        if domain_id:
            hit = self._maps.get(domain_id, {}).get(expr)
            if hit is None and emit:
                from odap.biz.semantic_admin.gap_pool.services.gap_emitter import (
                    report_gap_signal,
                )
                from odap.biz.semantic_admin.gap_pool.models import GapSignalSource
                report_gap_signal(GapSignalSource.TERM_RESOLVE_MISS, expr,
                                  domain_id=domain_id, ref="usl_term_resolver")
            return hit
        for mapping in self._maps.values():
            if expr in mapping:
                return mapping[expr]
        if emit:
            from odap.biz.semantic_admin.gap_pool.services.gap_emitter import (
                report_gap_signal,
            )
            from odap.biz.semantic_admin.gap_pool.models import GapSignalSource
            report_gap_signal(GapSignalSource.TERM_RESOLVE_MISS, expr,
                              ref="usl_term_resolver")
        return None

    def clear(self) -> None:
        self._maps.clear()
        self._loaded_domains.clear()


def load_resolver_from_storage(
    domain_id: str, storage=None
) -> UslTermResolver:
    """便捷工厂：从 SQLiteUslStorage 加载领域术语构建 resolver。

    供 QA 链路使用，保证与 USL 存储一致。
    """
    from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage
    storage = storage or SQLiteUslStorage()
    terms, _ = storage.list_terms(domain_id=domain_id, page=1, page_size=100000)
    resolver = UslTermResolver()
    resolver.load_terms(domain_id, terms)
    return resolver


__all__ = ["UslTermResolver", "load_resolver_from_storage"]
