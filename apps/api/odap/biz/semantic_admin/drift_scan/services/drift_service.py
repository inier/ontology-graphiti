"""DriftService —— 漂移扫描编排（规则 2/6/14；报告不可变；source_errors 显式）。"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..models.drift import DriftKind, DriftReport, EvolutionSource
from ..storage.sqlite_drift_storage import SQLiteDriftStorage
from . import scanners

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DriftService:
    def __init__(self, storage: Optional[SQLiteDriftStorage] = None):
        self.storage = storage or SQLiteDriftStorage()

    # ---- 数据装载（可被测试 monkeypatch；生产走真实存储）----
    def _load_terms(self, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage
        usl = SQLiteUslStorage()
        domain_id = scope.get("domain_id")
        result = usl.list_terms(domain_id=domain_id, page=1, page_size=10000)
        items = result[0] if isinstance(result, tuple) else result
        return list(items or [])

    def _load_version_pairs(
        self, ontology_id: Optional[str],
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any], Optional[str], Optional[str]]]:
        """返回 [(snap_a, snap_b, version_a, version_b)] 相邻 committed 版本对。

        快照结构为 commit_schema_version 写入的真实 schema_snapshot
        （object_types/link_types/action_types/process_types/rule_types/
        function_types/indicator_types 七大类型分类）。

        规则 6：跨模块经 OntologyService 服务方法，不直取其 storage。
        规则 14：失败显式抛异常，由 run_scan 记入 source_errors；
        禁止 hasattr 探测式降级，禁止静默返回空。
        """
        # 函数内导入避免循环依赖
        from odap.biz.core.ontology.ontology_api.services.ontology_service import (
            OntologyService,
        )
        res = OntologyService().list_schema_versions(ontology_id)
        if not isinstance(res, dict) or res.get("status") == "error":
            raise RuntimeError(
                (res or {}).get("message", "list_schema_versions failed"))
        versions = res.get("versions", []) or []
        committed = [v for v in versions
                     if v.get("is_stable") and v.get("schema_snapshot")]
        # 存储层返回降序，diff 需按 created_at 升序相邻配对
        committed.sort(key=lambda v: v.get("created_at") or "")
        pairs: List[Tuple[Dict[str, Any], Dict[str, Any], Optional[str], Optional[str]]] = []
        for a, b in zip(committed, committed[1:]):
            sa, sb = a["schema_snapshot"], b["schema_snapshot"]
            if isinstance(sa, str):
                sa = json.loads(sa)      # storage 已解析为 dict；防御性处理
            if isinstance(sb, str):
                sb = json.loads(sb)
            pairs.append((sa, sb, a.get("version_id"), b.get("version_id")))
        return pairs

    # ---- 主扫描 ----
    def run_scan(self, *, scope: Optional[Dict[str, Any]] = None,
                 trigger: str = "manual",
                 ontology_id: Optional[str] = None) -> Dict[str, Any]:
        scope = scope or {}
        report = DriftReport(trigger=trigger, ontology_id=ontology_id, scope=scope)
        findings: List[Dict[str, Any]] = []
        source_errors: Dict[str, str] = {}
        forks = 0

        # 源 1：fork
        try:
            terms = self._load_terms(scope)
            fork_findings = scanners.fork_scan(terms, scope)
            forks = len(fork_findings)
            findings += fork_findings
        except Exception as e:
            source_errors["fork"] = str(e)
            logger.warning("drift fork 扫描失败: %s", e, exc_info=True)

        # 源 2：version_snapshot 演进
        try:
            for snap_a, snap_b, va, vb in self._load_version_pairs(ontology_id):
                findings += scanners.diff_version_snapshots(snap_a, snap_b,
                                                            version_a=va, version_b=vb)
        except Exception as e:
            source_errors[EvolutionSource.VERSION_SNAPSHOT.value] = str(e)
            logger.warning("drift version 演进 diff 失败: %s", e, exc_info=True)

        # 源 3：indicator_caliber 演进
        try:
            for ind_id in self.storage.list_all_indicator_ids():
                rows = self.storage.list_indicator_snapshots(ind_id)
                findings += scanners.diff_indicator_snapshots(rows)
        except Exception as e:
            source_errors[EvolutionSource.INDICATOR_CALIBER.value] = str(e)
            logger.warning("drift indicator 演进 diff 失败: %s", e, exc_info=True)

        # 源 4：usl_term 演进
        try:
            for term_id in self.storage.list_all_term_ids():
                rows = self.storage.list_term_history(term_id)
                findings += scanners.diff_term_history(rows)
        except Exception as e:
            source_errors[EvolutionSource.USL_TERM.value] = str(e)
            logger.warning("drift term 演进 diff 失败: %s", e, exc_info=True)

        evolutions = len([f for f in findings
                          if f["kind"] == DriftKind.EVOLUTION.value])
        # 全源失败判定：四个源全部记错 → failed
        all_sources = {"fork", EvolutionSource.VERSION_SNAPSHOT.value,
                       EvolutionSource.INDICATOR_CALIBER.value,
                       EvolutionSource.USL_TERM.value}
        all_failed = all_sources.issubset(source_errors.keys())
        report.counts = {"forks": forks, "evolutions": evolutions,
                         "total": len(findings)}
        report.source_errors = source_errors
        report.finished_at = _utc_now_iso()
        report.status = "failed" if all_failed else "ok"
        if all_failed:
            report.error = "所有漂移来源均扫描失败"

        for f in findings:
            f["report_id"] = report.id
        self.storage.save_report_with_findings(report.to_dict(), findings)
        if report.status == "failed":
            return {"status": "error", "message": report.error,
                    "report_id": report.id}
        return {"status": "ok", "report_id": report.id}

    # ---- 查询 ----
    def list_reports(self, **filters) -> Dict[str, Any]:
        try:
            items, total = self.storage.list_reports(**filters)
            return {"status": "ok", "items": items, "total": total}
        except Exception as e:
            logger.warning("list_reports 失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"查询报告失败: {e}"}

    def get_report(self, report_id: str) -> Dict[str, Any]:
        rep = self.storage.get_report(report_id)
        if not rep:
            return {"status": "error", "message": f"报告 {report_id} 不存在",
                    "code": "REPORT_NOT_FOUND_404"}
        findings = self.storage.list_findings(report_id)
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for f in findings:
            key = f["kind"] if f["kind"] == "fork" else f"evolution:{f.get('source')}"
            grouped.setdefault(key, []).append(f)
        return {"status": "ok", "report": rep, "findings": findings,
                "grouped": grouped}

    def latest_report(self) -> Dict[str, Any]:
        rep = self.storage.latest_report()
        if not rep:
            return {"status": "ok", "report": None}
        return self.get_report(rep["id"])

    # ---- 自动触发（侧道）----
    @classmethod
    def _instance_for_hook(cls, ontology_id: str) -> "DriftService":
        return cls()

    def on_ontology_committed(self, ontology_id: str) -> None:
        """commit 后侧道自动扫描。异常绝不传播 commit 路径（规则 14）。"""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._auto_scan(ontology_id))
        except RuntimeError:
            # 无 running loop：退化为同步执行一次（可观测兜底，ADR-087 注明）
            logger.warning(
                "drift 自动触发无事件循环，退化同步执行 ontology=%s", ontology_id)
            try:
                self.run_scan(scope={"ontology_id": ontology_id},
                              trigger="commit", ontology_id=ontology_id)
            except Exception as e:
                logger.warning("drift 同步自动扫描失败 ontology=%s: %s",
                               ontology_id, e)

    async def _auto_scan(self, ontology_id: str) -> None:
        try:
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self.run_scan(scope={"ontology_id": ontology_id},
                                      trigger="commit",
                                      ontology_id=ontology_id),
            )
        except Exception as e:
            logger.warning("drift 自动扫描 task 失败 ontology=%s: %s",
                           ontology_id, e, exc_info=True)
