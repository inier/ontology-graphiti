"""SQLiteDriftStorage —— 四表存储（规则 8：每次 connect/close、JSON TEXT、ISO 时间）。

报告完成后不可变：本存储不提供 update_report；save_report_with_findings 事务性写入。
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_db_path() -> str:
    data_dir = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "apps", "api", "data"))
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "drift_scan.db")


class SQLiteDriftStorage:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_db_path()
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS drift_scan_reports (
                    id TEXT PRIMARY KEY,
                    trigger TEXT NOT NULL,
                    ontology_id TEXT,
                    scope_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL DEFAULT 'ok',
                    error TEXT,
                    source_errors_json TEXT NOT NULL DEFAULT '{}',
                    counts_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS drift_findings (
                    id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    subject TEXT NOT NULL,
                    subject_label TEXT,
                    field TEXT,
                    old_value_json TEXT,
                    new_value_json TEXT,
                    sides_json TEXT,
                    version_ref_json TEXT,
                    at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_finding_report ON drift_findings(report_id);
                CREATE TABLE IF NOT EXISTS indicator_caliber_snapshots (
                    id TEXT PRIMARY KEY,
                    indicator_id TEXT NOT NULL,
                    ontology_id TEXT,
                    definition_json TEXT NOT NULL DEFAULT '{}',
                    captured_at TEXT NOT NULL,
                    captured_version_id TEXT,
                    change_op TEXT NOT NULL DEFAULT 'update'
                );
                CREATE INDEX IF NOT EXISTS idx_ind_snap ON indicator_caliber_snapshots(indicator_id, captured_at);
                CREATE TABLE IF NOT EXISTS usl_term_history (
                    id TEXT PRIMARY KEY,
                    term_id TEXT NOT NULL,
                    domain_id TEXT,
                    op TEXT NOT NULL,
                    before_json TEXT,
                    after_json TEXT,
                    at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_term_hist ON usl_term_history(term_id, at);
                """
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _safe_json(raw: Any, default):
        if raw is None:
            return default
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("drift JSON 解析失败，回退默认: %r", raw)
            return default

    @staticmethod
    def _dumps(v: Any) -> Optional[str]:
        if v is None:
            return None
        return json.dumps(v, ensure_ascii=False)

    def _report_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["scope_json"] = self._safe_json(d.get("scope_json"), {})
        d["source_errors_json"] = self._safe_json(d.get("source_errors_json"), {})
        d["counts_json"] = self._safe_json(d.get("counts_json"), {})
        return d

    def _finding_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["old_value_json"] = self._safe_json(d.get("old_value_json"), None)
        d["new_value_json"] = self._safe_json(d.get("new_value_json"), None)
        d["sides_json"] = self._safe_json(d.get("sides_json"), None)
        d["version_ref_json"] = self._safe_json(d.get("version_ref_json"), None)
        return d

    # ---- report + findings ----
    def save_report_with_findings(self, report: Dict[str, Any],
                                  findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO drift_scan_reports (
                    id, trigger, ontology_id, scope_json, started_at, finished_at,
                    status, error, source_errors_json, counts_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (report["id"], report["trigger"], report.get("ontology_id"),
                 self._dumps(report.get("scope_json", {})) or "{}",
                 report.get("started_at") or _utc_now_iso(),
                 report.get("finished_at"), report.get("status", "ok"), report.get("error"),
                 self._dumps(report.get("source_errors_json", {})) or "{}",
                 self._dumps(report.get("counts_json", {})) or "{}"),
            )
            for f in findings:
                conn.execute(
                    """INSERT OR REPLACE INTO drift_findings (
                        id, report_id, kind, source, subject, subject_label, field,
                        old_value_json, new_value_json, sides_json, version_ref_json, at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (f.get("id") or str(uuid.uuid4()), f["report_id"], f["kind"],
                     f.get("source", ""), f["subject"], f.get("subject_label"),
                     f.get("field"), self._dumps(f.get("old_value_json")),
                     self._dumps(f.get("new_value_json")), self._dumps(f.get("sides_json")),
                     self._dumps(f.get("version_ref_json")), f.get("at") or _utc_now_iso()),
                )
            conn.commit()
            return report
        finally:
            conn.close()

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM drift_scan_reports WHERE id=?",
                               (report_id,)).fetchone()
            return self._report_row(row) if row else None
        finally:
            conn.close()

    def list_reports(self, *, trigger: Optional[str] = None, status: Optional[str] = None,
                     page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        where, params = [], []
        if trigger:
            where.append("trigger=?")
            params.append(trigger)
        if status:
            where.append("status=?")
            params.append(status)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM drift_scan_reports{clause}", params).fetchone()["c"]
            offset = max(0, (page - 1) * page_size)
            rows = conn.execute(
                f"SELECT * FROM drift_scan_reports{clause} ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset)).fetchall()
            return [self._report_row(r) for r in rows], total
        finally:
            conn.close()

    def latest_report(self) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM drift_scan_reports ORDER BY started_at DESC LIMIT 1").fetchone()
            return self._report_row(row) if row else None
        finally:
            conn.close()

    def list_findings(self, report_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM drift_findings WHERE report_id=? ORDER BY kind, source, subject",
                (report_id,)).fetchall()
            return [self._finding_row(r) for r in rows]
        finally:
            conn.close()

    # ---- indicator snapshots ----
    def append_indicator_snapshot(self, snap: Dict[str, Any]) -> Dict[str, Any]:
        rec = {
            "id": snap.get("id") or str(uuid.uuid4()),
            "indicator_id": snap["indicator_id"], "ontology_id": snap.get("ontology_id"),
            "definition_json": self._dumps(snap.get("definition_json", {})) or "{}",
            "captured_at": snap.get("captured_at") or _utc_now_iso(),
            "captured_version_id": snap.get("captured_version_id"),
            "change_op": snap.get("change_op", "update"),
        }
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO indicator_caliber_snapshots (
                    id, indicator_id, ontology_id, definition_json, captured_at,
                    captured_version_id, change_op) VALUES (?,?,?,?,?,?,?)""",
                (rec["id"], rec["indicator_id"], rec["ontology_id"], rec["definition_json"],
                 rec["captured_at"], rec["captured_version_id"], rec["change_op"]))
            conn.commit()
            return rec
        finally:
            conn.close()

    def list_indicator_snapshots(self, indicator_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM indicator_caliber_snapshots WHERE indicator_id=? ORDER BY captured_at",
                (indicator_id,)).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["definition_json"] = self._safe_json(d.get("definition_json"), {})
                out.append(d)
            return out
        finally:
            conn.close()

    def list_all_indicator_ids(self) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT DISTINCT indicator_id FROM indicator_caliber_snapshots").fetchall()
            return [r["indicator_id"] for r in rows]
        finally:
            conn.close()

    # ---- term history ----
    def append_term_history(self, hist: Dict[str, Any]) -> Dict[str, Any]:
        rec = {
            "id": hist.get("id") or str(uuid.uuid4()),
            "term_id": hist["term_id"], "domain_id": hist.get("domain_id"),
            "op": hist["op"], "before_json": self._dumps(hist.get("before_json")),
            "after_json": self._dumps(hist.get("after_json")),
            "at": hist.get("at") or _utc_now_iso(),
        }
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO usl_term_history (
                    id, term_id, domain_id, op, before_json, after_json, at)
                   VALUES (?,?,?,?,?,?,?)""",
                (rec["id"], rec["term_id"], rec["domain_id"], rec["op"],
                 rec["before_json"], rec["after_json"], rec["at"]))
            conn.commit()
            return rec
        finally:
            conn.close()

    def list_term_history(self, term_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM usl_term_history WHERE term_id=? ORDER BY at", (term_id,)).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["before_json"] = self._safe_json(d.get("before_json"), None)
                d["after_json"] = self._safe_json(d.get("after_json"), None)
                out.append(d)
            return out
        finally:
            conn.close()

    def list_all_term_ids(self) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT DISTINCT term_id FROM usl_term_history").fetchall()
            return [r["term_id"] for r in rows]
        finally:
            conn.close()
