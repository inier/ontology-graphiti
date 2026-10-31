"""USL 术语表加载（expression → term 索引）。

只负责「把术语表读进内存并建别名索引」，不含任何意图判定逻辑。
加载失败**不抛异常**，而是把原因写进 `load_error` —— 上层据此返回澄清帧，
绝不静默降级成「猜一个意图」。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

#: 参与别名索引的字段（canonical 单独加，剩下三个是同一术语的不同写法）
_ALIAS_KEYS = ("synonyms", "near_synonyms", "aliases")


class UslDictionary:
    """USL 术语表（expression → term），带加载错误显式记录。"""

    def __init__(self, loader: Optional[Callable[[], List[Dict[str, Any]]]] = None):
        self._loader = loader or _default_loader
        self._map: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
        self.load_error: Optional[str] = None

    def load(self) -> Dict[str, Dict[str, Any]]:
        if self._loaded:
            return self._map
        self._loaded = True
        try:
            terms = self._loader() or []
        except Exception as exc:  # noqa: BLE001 - 词典不可用必须显式记录
            self.load_error = f"{type(exc).__name__}: {exc}"
            logger.warning("USL 词典加载失败（将返回澄清）：%s", self.load_error)
            return self._map
        for term in terms:
            self._index_term(term)
        return self._map

    def _index_term(self, term: Dict[str, Any]) -> None:
        if term.get("stoplist_flag"):
            return
        canonical = str(term.get("canonical") or "").strip()
        if not canonical:
            return
        entry = {
            "canonical": canonical,
            "semantic_type": str(term.get("semantic_type") or ""),
            "domain_id": str(term.get("domain_id") or ""),
        }
        for expression in [canonical] + _collect_aliases(term):
            key = expression.strip()
            if key and key not in self._map:
                self._map[key] = entry


def _collect_aliases(term: Dict[str, Any]) -> List[str]:
    aliases: List[str] = []
    for key in _ALIAS_KEYS:
        aliases.extend(str(x) for x in (term.get(key) or []) if x)
    return aliases


def _default_loader() -> List[Dict[str, Any]]:
    from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage

    rows, _total = SQLiteUslStorage().list_terms(page=1, page_size=500)
    return rows


__all__ = ["UslDictionary"]
