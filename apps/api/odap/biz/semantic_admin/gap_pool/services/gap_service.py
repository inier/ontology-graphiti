"""GapService —— 缺口池编排层（规则 2：返回 dict；规则 6：routes→services→storage）。"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..models.gap import GapStatus
from ..storage.sqlite_gap_storage import SQLiteGapStorage

logger = logging.getLogger(__name__)


class GapService:
    def __init__(self, storage: Optional[SQLiteGapStorage] = None):
        self.storage = storage or SQLiteGapStorage()
        self._candidate_service_factory = None

    def record_signal(self, source, expression: str, *,
                      workspace_id: Optional[str] = None,
                      domain_id: Optional[str] = None,
                      ref: Optional[str] = None,
                      detail: Optional[str] = None,
                      attribution: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            gap = self.storage.record_signal(
                source=source, expression=expression,
                workspace_id=workspace_id, domain_id=domain_id,
                ref=ref, detail=detail, attribution=attribution,
            )
            return {"status": "ok", "gap": gap}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:  # 规则14：显式失败，不静默
            logger.warning("record_signal 失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"记录缺口信号失败: {e}"}

    def _candidate_service(self):
        if self._candidate_service_factory is not None:
            return self._candidate_service_factory()
        from odap.biz.semantic_admin.candidate_store.services import CandidateService
        return CandidateService()

    def list_gaps(self, **filters) -> Dict[str, Any]:
        try:
            items, total = self.storage.list_gaps(**filters)
            return {"status": "ok", "items": items, "total": total}
        except Exception as e:
            logger.warning("list_gaps 失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"查询缺口失败: {e}"}

    def get_gap(self, gap_id: str) -> Dict[str, Any]:
        gap = self.storage.get_gap(gap_id)
        if not gap:
            return {"status": "error", "message": f"缺口 {gap_id} 不存在",
                    "code": "GAP_NOT_FOUND_404"}
        return {"status": "ok", "gap": gap}

    def promote(self, gap_id: str, *, actor: str,
                domain_id: Optional[str] = None,
                workspace_id: Optional[str] = None) -> Dict[str, Any]:
        gap = self.storage.get_gap(gap_id)
        if not gap:
            return {"status": "error", "message": f"缺口 {gap_id} 不存在",
                    "code": "GAP_NOT_FOUND_404"}
        if gap["status"] == GapStatus.PROMOTED.value and gap.get("promoted_candidate_id"):
            return {"status": "ok", "candidate_id": gap["promoted_candidate_id"],
                    "already_promoted": True}
        cs = self._candidate_service()
        payload = {
            "expression": gap["expression"],
            "workspace_id": workspace_id or gap.get("workspace_id"),
            "domain_id": domain_id or gap.get("domain_id"),
            "gap_id": gap_id,
            "triggered_by": actor,
        }
        # ADR-088 D9 归因透传：content 层 attribution 的 target_kind 传给
        # create_candidate_from_gap 的 semantic_type；无归因时不传（候选侧
        # 维持"对象类型"默认，行为不变）。不触碰审批链。
        target_kind = self._content_target_kind(gap)
        if target_kind:
            payload["semantic_type"] = target_kind
        r = cs.create_candidate_from_gap(payload)
        if r.get("status") != "ok":
            return r
        cid = r["candidate_id"]
        self.storage.update_status(gap_id, GapStatus.PROMOTED.value,
                                   promoted_candidate_id=cid)
        return {"status": "ok", "candidate_id": cid}

    def dismiss(self, gap_id: str, *, reason: str, actor: str) -> Dict[str, Any]:
        gap = self.storage.get_gap(gap_id)
        if not gap:
            return {"status": "error", "message": f"缺口 {gap_id} 不存在",
                    "code": "GAP_NOT_FOUND_404"}
        self.storage.update_status(gap_id, GapStatus.REJECTED.value,
                                   dismiss_reason=reason or "")
        return {"status": "ok", "id": gap_id, "actor": actor}

    @staticmethod
    def _content_target_kind(gap: Dict[str, Any]) -> Optional[str]:
        """从 occurrence 时间线找最近的 content 层归因 target_kind（无则 None）。

        attribution_counts 只存 {layer: count}，target_kind 在 occurrence 的
        attribution 键里；倒序扫描（最近优先），sources 截断 50 条内的最新归因
        足够 promote 场景使用。无归因 / 仅 tool·schema 层 → None，不造数。
        """
        for occ in reversed(gap.get("sources_json") or []):
            attr = occ.get("attribution") or {}
            if attr.get("layer") == "content" and attr.get("target_kind"):
                return str(attr["target_kind"])
        return None

    def on_candidate_resolved(self, candidate_id: str, outcome: str,
                              *, term_id: Optional[str] = None) -> None:
        """侧道回调：候选终态推进 gap 状态机。无对应 gap 则 no-op，绝不 raise。"""
        try:
            gap = self.storage.get_by_candidate_id(candidate_id)
            if not gap:
                return
            if outcome == "adopted":
                self.storage.update_status(gap["id"], GapStatus.ADOPTED.value,
                                           resolved_term_id=term_id)
            elif outcome == "rejected":
                self.storage.update_status(gap["id"], GapStatus.REJECTED.value)
        except Exception as e:
            logger.warning("on_candidate_resolved 失败(candidate=%s): %s",
                           candidate_id, e)

    def resolve_check(self, gap_id: str) -> Dict[str, Any]:
        gap = self.storage.get_gap(gap_id)
        if not gap:
            return {"status": "error", "message": f"缺口 {gap_id} 不存在",
                    "code": "GAP_NOT_FOUND_404"}
        sources = gap.get("source_counts_json") or {}
        is_term_gap = bool(sources.get("term_resolve_miss"))
        if not is_term_gap:
            return {"status": "ok", "resolvable": False, "via": "none",
                    "detail": "非术语类缺口，resolve-check 语义弱，不假装能判定"}
        try:
            from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import (
                load_resolver_from_storage,
            )
            resolver = load_resolver_from_storage(gap.get("domain_id") or "")
            # emit=False：resolve-check 是只读判定，不得发信号——否则会 heat+1
            # 并把已 dismiss 的缺口复活（终审 M1）。读侧绝不写。
            canonical = resolver.canonical_of(gap["expression"],
                                              gap.get("domain_id") or "",
                                              emit=False)
            if canonical:
                return {"status": "ok", "resolvable": True, "via": "term",
                        "detail": f"已可解析为 canonical={canonical}"}
            return {"status": "ok", "resolvable": False, "via": "term",
                    "detail": "USL 字典仍未命中"}
        except Exception as e:
            logger.warning("resolve_check 失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"resolve-check 失败: {e}"}

    def stats(self) -> Dict[str, Any]:
        try:
            from .gap_emitter import get_emit_failures
            by_status = self.storage.count_by_status()
            adopted = by_status.get("adopted", 0)
            rejected = by_status.get("rejected", 0)
            denom = adopted + rejected
            return {
                "status": "ok",
                "total": sum(by_status.values()),
                "by_status": by_status,
                "by_source": self.storage.count_by_source(),
                "by_layer": self.storage.count_by_layer(),
                "emit_failures": get_emit_failures(),
                "top_heat": self.storage.top_heat(10),
                "adoption_rate": (adopted / denom) if denom else None,
            }
        except Exception as e:
            logger.warning("stats 失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"统计失败: {e}"}
