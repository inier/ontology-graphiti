"""snapshot_writer —— 演进 diff 的历史积累写钩子入口。

规则 14：侧道可观测。钩子失败 → logger.warning + 计数，绝不阻塞/回滚主写。
惰性导入 storage 规避循环导入。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_hook_failures = 0
_storage_singleton = None


def get_hook_failures() -> int:
    return _hook_failures


def _get_storage():
    global _storage_singleton
    if _storage_singleton is None:
        from ..storage.sqlite_drift_storage import SQLiteDriftStorage
        _storage_singleton = SQLiteDriftStorage()
    return _storage_singleton


def _bump() -> None:
    global _hook_failures
    _hook_failures += 1


def record_indicator_snapshot(*, indicator_id: str, ontology_id: Optional[str],
                              definition: Dict[str, Any], change_op: str,
                              captured_version_id: Optional[str] = None) -> None:
    try:
        _get_storage().append_indicator_snapshot({
            "indicator_id": indicator_id, "ontology_id": ontology_id,
            "definition_json": definition or {}, "change_op": change_op,
            "captured_version_id": captured_version_id,
        })
    except Exception as e:
        _bump()
        logger.warning("record_indicator_snapshot 失败(indicator=%s): %s", indicator_id, e)


def record_term_history(*, term_id: str, domain_id: Optional[str], op: str,
                        before: Optional[Dict[str, Any]] = None,
                        after: Optional[Dict[str, Any]] = None) -> None:
    try:
        _get_storage().append_term_history({
            "term_id": term_id, "domain_id": domain_id, "op": op,
            "before_json": before, "after_json": after,
        })
    except Exception as e:
        _bump()
        logger.warning("record_term_history 失败(term=%s): %s", term_id, e)
