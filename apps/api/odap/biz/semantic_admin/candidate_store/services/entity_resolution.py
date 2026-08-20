"""候选实体解析（USL 术语字典驱动的确定性去重）。

本体论原则（严格）：
- 候选去重必须基于 USL 统一语义层的**精确字典查表**（UslTermResolver），
  而非字符相似度阈值 / 向量近似 / LLM 语义判断。
- 两个候选「语义相等」当且仅当它们归一化到**同一个 canonical 术语**。
- 归一化是确定性的：同义词 → canonical 精确映射，未命中则保持原词（不猜测）。

判定规则：
- resolve(canonical_a) == resolve(canonical_b) 且均命中 USL → 判定重复。
- 未命中 USL 的候选（词不在字典内）**不参与判重**（宁可不判，不误判）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import (
    UslTermResolver,
)

logger = logging.getLogger(__name__)


class EntityResolver:
    """候选实体解析器（USL 字典精确查表）"""

    def __init__(self, term_resolver: Optional[UslTermResolver] = None):
        self.term_resolver = term_resolver or UslTermResolver()

    def load_usl_terms(self, domain_id: str, terms: List[Dict[str, Any]]) -> None:
        """加载领域 USL 术语，构建精确映射表"""
        self.term_resolver.load_terms(domain_id, terms)

    def resolve_duplicates(
        self,
        candidates: List[Dict[str, Any]],
        domain_id: str = "",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        """检测候选列表中的重复项（USL 字典精确判定）。

        Args:
            candidates: 候选 dict 列表（含 canonical + workspace_id）
            domain_id: USL 领域 ID（术语字典作用域）
            workspace_id: 隔离边界

        Returns:
            {
                "duplicate_groups": [{canonical, candidate_ids, size}],
                "duplicate_count": int,
                "unresolved_count": int,   # 未命中 USL 的候选数（不参与判重）
                "workspace_id": str,
            }
        """
        # 1. 按 workspace 过滤
        ws_cands = [
            c for c in candidates
            if str(c.get("workspace_id", "default")) == workspace_id
        ]

        # 2. 归一化每个候选的 canonical（精确字典查表）
        canonical_groups: Dict[str, List[str]] = {}
        unresolved_count = 0

        for cand in ws_cands:
            cid = str(cand.get("id") or cand.get("candidate_id") or "")
            raw = str(cand.get("canonical") or cand.get("term") or "").strip()
            if not raw or not cid:
                continue

            resolved = self.term_resolver.canonical_of(raw, domain_id=domain_id)
            if resolved is None:
                # 真正未命中 USL（词不在字典内）→ 不参与判重，单独计数
                unresolved_count += 1
                continue

            canonical_groups.setdefault(resolved, []).append(cid)

        # 3. 聚合重复组（同 canonical 且 >1 候选）
        duplicate_groups = [
            {
                "canonical": canonical,
                "candidate_ids": sorted(ids),
                "size": len(ids),
            }
            for canonical, ids in canonical_groups.items()
            if len(ids) > 1
        ]

        return {
            "duplicate_groups": duplicate_groups,
            "duplicate_count": len(duplicate_groups),
            "unresolved_count": unresolved_count,
            "workspace_id": workspace_id,
        }

    def is_duplicate(
        self, canonical_a: str, canonical_b: str, domain_id: str = ""
    ) -> bool:
        """判断两个候选词是否重复（USL 精确判定）。

        两者都命中 USL 且归一化到同一 canonical → 重复；否则 False。
        """
        a = (canonical_a or "").strip()
        b = (canonical_b or "").strip()
        if not a or not b or a == b:
            return a == b and bool(a)
        ra = self.term_resolver.canonical_of(a, domain_id)
        rb = self.term_resolver.canonical_of(b, domain_id)
        if ra is None or rb is None:
            # 任一方未命中 USL → 不判重（宁可不判，不误判）
            return False
        return ra == rb


_instance: Optional[EntityResolver] = None


def get_entity_resolver() -> EntityResolver:
    """获取候选实体解析器单例"""
    global _instance
    if _instance is None:
        _instance = EntityResolver()
    return _instance


# 向后兼容别名（原 TwoStageEntityResolver 命名已被测试/文档引用）
TwoStageEntityResolver = EntityResolver


__all__ = [
    "EntityResolver",
    "TwoStageEntityResolver",
    "get_entity_resolver",
]
