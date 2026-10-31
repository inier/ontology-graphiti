---
id: odap.l15.plans-2026-10-07-semantic-drift-detection
status: reference
owner: architect
version: ''
layer: L15
concern: design-spec-record
lifecycle: historical
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: superpowers 实施计划存档，计划已执行，保留为执行留痕
governance_evidence: docs/superpowers/specs/ 存在同名 design 文档（spec/plan 成对）
---

# 语义漂移检测（semantic drift detection）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 ODAP 补上「语义漂移」可见性——术语分叉现状扫描（同一说法原文挂到 ≥2 个 USL 术语）+ 三来源口径演进字段级 diff（相邻版本 doc_snapshot / indicator 口径快照序 / USL 术语历史序），报告落库为不可变证据，支持手动 + 本体 commit 后侧道自动双触发，配 semantic-admin 漂移页。纪律：**只报告真实数据，counts 全为 `len(findings)`，不产任何比例/推断，无 LLM 参与**。

**Architecture:** 新建独立子服务 `apps/api/odap/biz/semantic_admin/drift_scan/`（models/storage/services/api）。scanners 为纯函数（fork_scan / diff_version_snapshots / diff_indicator_snapshots / diff_term_history）；snapshot_writer 提供 indicator/term 写钩子入口（侧道，失败 warning+计数不阻塞主写）；drift_service.run_scan 事务性写 report + N findings；自动触发经 `asyncio.create_task` 从 commit 侧道调度，异常落 failed report 不传播 commit 路径。四表 SQLite：drift_scan_reports / drift_findings / indicator_caliber_snapshots / usl_term_history。

**Tech Stack:** Python 3.10+ / FastAPI / SQLite（stdlib sqlite3，无连接池）/ pytest / asyncio；前端 React 19 + TS + Ant Design 6 + `fetchJson`。

**Spec:** `docs/superpowers/specs/2026-10-07-semantic-drift-detection-design.md`（本计划逐条实现该 spec，执行时两份文档一起读）

## Global Constraints

以下为全计划强制约束，每个 Task 的要求都隐含包含本节（与子项目 1 计划一致）：

- **测试命令必须带离线变量**（否则挂起，`--timeout` 不可用）：
  ```bash
  PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    uv run pytest apps/api/tests/unit/biz/semantic_admin/<file>.py -q --no-header -p no:cacheprovider
  ```
  取退出码用 `> /tmp/out.txt 2>&1; echo "EXIT=$?"`，不要 `| tail`。
- **离线全量单测有 ~206 个环境依赖型失败基线**，不是回归。验证改动用 stashed-HEAD 基线对比精确失败 node ID（`git stash push <改的源文件>` → 只重跑失败文件 → `diff`，为空=零回归）；完事 `git stash pop` + `git checkout -- apps/api/odap/infra/opa/bundles/current_bundle.json`。
- **单测目录**：`apps/api/tests/unit/biz/semantic_admin/`（仓库根 `tests/` 无 unit 子目录）。
- **提交纪律（用户约束）**：commit 步骤**只精确 stage**（`git add <确切路径>`）+ 验证，**绝不运行 `git commit`**；禁止 `git add -A` / `git add .`。
- **AGENTS.md 硬性规则**：规则 2（服务层返回 dict，错误 `{"status":"error","message":...}`）、规则 3（路由 `except HTTPException: raise`）、规则 4（Enum `(str, Enum)`）、规则 5（容器字段 `default_factory`）、规则 6（routes→services→storage）、规则 8（SQLite connect/close、JSON TEXT、Enum `.value`、ISO 时间）、规则 9（新模块必测、存储层用 tmp_path 真 DB、禁 MagicMock 模拟 DB）、规则 12（ADR + 文档同步）、规则 13（DB 走 `DATA_DIR`，禁写项目根）、规则 14（失败显式可观测、禁幻影调用/hasattr 探测式降级、测试走真实函数体）。
- **前端约定**：跨一级目录用 `@` 别名；`import { fetchJson } from '@/modules/shared/services/apiClient'; import { API_BASE } from '@/config';`；页面 antd + `useI18n` + `useSemanticAdminStore`；路由注册 `apps/web/src/AppRoutes.tsx`。
- **漂移纪律（spec §2）**：报告完成后**不可变**（无 update 接口）；counts 全为 `len(findings)`；单源失败必记 `source_errors` 且跳过该源 findings，≥1 源成功→status=ok，全失败→status=failed；**不产任何比例/推断**；actions/events 不进演进 diff（运行时数据）。
- **循环导入规避**：`snapshot_writer` / `drift_service` 在函数内惰性导入被钩模块的存储；commit 钩子惰性导入 drift_service。

---

### Task 1: drift 数据模型 + 四表 SQLite 存储层

**Files:**
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/__init__.py`（空）
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/models/__init__.py`（`from .drift import DriftReport, DriftFinding, DriftKind, EvolutionSource`）
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/models/drift.py`
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/storage/__init__.py`（`from .sqlite_drift_storage import SQLiteDriftStorage; Storage = SQLiteDriftStorage`）
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/storage/sqlite_drift_storage.py`
- Test: `apps/api/tests/unit/biz/semantic_admin/test_drift_storage.py`

**Interfaces:**
- Produces:
  - `DriftKind(str, Enum)`: `FORK="fork"`, `EVOLUTION="evolution"`
  - `EvolutionSource(str, Enum)`: `VERSION_SNAPSHOT="version_snapshot"`, `INDICATOR_CALIBER="indicator_caliber"`, `USL_TERM="usl_term"`
  - `DriftReport` / `DriftFinding` dataclass（`to_dict()`）
  - `SQLiteDriftStorage(db_path=None)`：`save_report_with_findings(report: dict, findings: list[dict]) -> dict`、`get_report(id) -> dict|None`、`list_reports(*, trigger=None, status=None, page=1, page_size=20) -> (list[dict], int)`、`latest_report() -> dict|None`、`list_findings(report_id) -> list[dict]`、`append_indicator_snapshot(dict) -> dict`、`list_indicator_snapshots(indicator_id) -> list[dict]`、`append_term_history(dict) -> dict`、`list_term_history(term_id) -> list[dict]`、`count_hook_failures() -> int`（读模块级计数）

- [ ] **Step 1: 写失败测试**（`test_drift_storage.py`，tmp_path 真 DB）

```python
import pytest
from odap.biz.semantic_admin.drift_scan.models import DriftKind, EvolutionSource
from odap.biz.semantic_admin.drift_scan.storage import SQLiteDriftStorage


@pytest.fixture
def store(tmp_path):
    return SQLiteDriftStorage(db_path=str(tmp_path / "drift.db"))


def test_save_report_with_findings_atomic(store):
    rep = {"id": "r1", "trigger": "manual", "status": "ok",
           "scope_json": {"ontology_id": "o1"}, "counts_json": {"forks": 1, "evolutions": 0},
           "source_errors_json": {}}
    fnd = [{"id": "f1", "report_id": "r1", "kind": DriftKind.FORK.value,
            "source": "", "subject": "诸侯", "subject_label": "诸侯",
            "sides_json": [{"term_id": "t1"}, {"term_id": "t2"}]}]
    out = store.save_report_with_findings(rep, fnd)
    assert out["id"] == "r1"
    assert len(store.list_findings("r1")) == 1


def test_report_immutable_no_update_api(store):
    rep = {"id": "r2", "trigger": "manual", "status": "ok", "counts_json": {},
           "scope_json": {}, "source_errors_json": {}}
    store.save_report_with_findings(rep, [])
    # 存储层不暴露 update_report；再 save 同 id 走 INSERT OR REPLACE 但服务层从不调用
    assert store.get_report("r2")["status"] == "ok"


def test_list_reports_filter_and_paging(store):
    for i in range(3):
        store.save_report_with_findings(
            {"id": f"r{i}", "trigger": "manual" if i < 2 else "commit",
             "status": "ok", "counts_json": {}, "scope_json": {}, "source_errors_json": {}}, [])
    items, total = store.list_reports(trigger="manual", page=1, page_size=10)
    assert total == 2


def test_indicator_snapshot_append_and_order(store):
    store.append_indicator_snapshot({"id": "s1", "indicator_id": "ind1",
        "ontology_id": "o1", "definition_json": {"formula": "a"}, "change_op": "create"})
    store.append_indicator_snapshot({"id": "s2", "indicator_id": "ind1",
        "ontology_id": "o1", "definition_json": {"formula": "b"}, "change_op": "update"})
    rows = store.list_indicator_snapshots("ind1")
    assert len(rows) == 2
    assert rows[0]["captured_at"] <= rows[1]["captured_at"]


def test_term_history_append(store):
    store.append_term_history({"id": "h1", "term_id": "t1", "domain_id": "d1",
        "op": "update", "before_json": {"canonical": "旧"}, "after_json": {"canonical": "新"}})
    assert len(store.list_term_history("t1")) == 1


def test_bad_json_tolerated(store):
    store.save_report_with_findings(
        {"id": "r3", "trigger": "manual", "status": "ok",
         "counts_json": {}, "scope_json": {}, "source_errors_json": {}}, [])
    import sqlite3
    conn = sqlite3.connect(store.db_path)
    conn.execute("UPDATE drift_scan_reports SET counts_json='{bad' WHERE id='r3'")
    conn.commit(); conn.close()
    assert store.get_report("r3")["counts_json"] == {}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_storage.py -q --no-header -p no:cacheprovider`
Expected: FAIL（无 drift_scan 模块）

- [ ] **Step 3: 写 models/drift.py**

```python
"""语义漂移模型 —— 报告与发现（BeModel 语义漂移两条检测线参照）。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DriftKind(str, Enum):
    FORK = "fork"
    EVOLUTION = "evolution"

    def __str__(self) -> str:
        return self.value


class EvolutionSource(str, Enum):
    VERSION_SNAPSHOT = "version_snapshot"
    INDICATOR_CALIBER = "indicator_caliber"
    USL_TERM = "usl_term"

    def __str__(self) -> str:
        return self.value


@dataclass
class DriftFinding:
    kind: str
    subject: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    report_id: str = ""
    source: str = ""                      # evolution 来源；fork 为空
    subject_label: str = ""
    field_name: Optional[str] = None      # 字段级 diff 的字段；__added__/__removed__
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    sides: Optional[List[Dict[str, Any]]] = None    # fork 两侧证据
    version_ref: Optional[Dict[str, Any]] = None    # {version_a,version_b} 或 {prev_at,cur_at}
    at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "report_id": self.report_id, "kind": self.kind,
            "source": self.source, "subject": self.subject,
            "subject_label": self.subject_label, "field": self.field_name,
            "old_value_json": self.old_value, "new_value_json": self.new_value,
            "sides_json": self.sides, "version_ref_json": self.version_ref, "at": self.at,
        }


@dataclass
class DriftReport:
    trigger: str                          # manual | commit
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ontology_id: Optional[str] = None
    scope: Dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=_utc_now_iso)
    finished_at: Optional[str] = None
    status: str = "ok"                    # ok | failed
    error: Optional[str] = None
    source_errors: Dict[str, str] = field(default_factory=dict)
    counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "trigger": self.trigger, "ontology_id": self.ontology_id,
            "scope_json": self.scope, "started_at": self.started_at,
            "finished_at": self.finished_at, "status": self.status, "error": self.error,
            "source_errors_json": self.source_errors, "counts_json": self.counts,
        }


__all__ = ["DriftReport", "DriftFinding", "DriftKind", "EvolutionSource"]
```

- [ ] **Step 4: 写 storage/sqlite_drift_storage.py**

```python
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

_hook_failures = 0


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
                 self._dumps(report.get("scope_json", {})) or "{}", report["started_at"],
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
            where.append("trigger=?"); params.append(trigger)
        if status:
            where.append("status=?"); params.append(status)
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

    # ---- hook failure counter ----
    def bump_hook_failure(self) -> None:
        global _hook_failures
        _hook_failures += 1

    def count_hook_failures(self) -> int:
        return _hook_failures
```

- [ ] **Step 5: 建两个 `__init__.py`**（内容见 Files）

- [ ] **Step 6: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_storage.py -q --no-header -p no:cacheprovider`
Expected: PASS（6 passed）

- [ ] **Step 7: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/drift_scan/__init__.py \
        apps/api/odap/biz/semantic_admin/drift_scan/models/__init__.py \
        apps/api/odap/biz/semantic_admin/drift_scan/models/drift.py \
        apps/api/odap/biz/semantic_admin/drift_scan/storage/__init__.py \
        apps/api/odap/biz/semantic_admin/drift_scan/storage/sqlite_drift_storage.py \
        apps/api/tests/unit/biz/semantic_admin/test_drift_storage.py
git status
```
提示用户提交（`feat(drift-scan): 漂移模型 + 四表 SQLite 存储层`）。**不要 git commit。**

---

### Task 2: snapshot_writer + indicator/term 写钩子接线

**Files:**
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/services/__init__.py`（`from .snapshot_writer import record_indicator_snapshot, record_term_history, get_hook_failures; from .drift_service import DriftService`）
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/services/snapshot_writer.py`
- Modify: `apps/api/odap/biz/core/ontology/ontology_api/services/ontology_service.py`（`create_indicator_type` :892 / `update_indicator_type` :927 成功分支；级联删除点 :159 前先取 before）
- Modify: `apps/api/odap/biz/semantic_admin/usl_manager/services/usl_manager_service.py`（`create_term` :180 / `update_term` :231 / `delete_term` :257 成功后）
- Test: `apps/api/tests/unit/biz/semantic_admin/test_drift_snapshot_writer.py`

**Interfaces:**
- Consumes: `SQLiteDriftStorage`。
- Produces:
  - `snapshot_writer.record_indicator_snapshot(*, indicator_id, ontology_id, definition, change_op, captured_version_id=None) -> None`（侧道，异常 warning+计数不 raise）
  - `snapshot_writer.record_term_history(*, term_id, domain_id, op, before=None, after=None) -> None`
  - `snapshot_writer.get_hook_failures() -> int`

- [ ] **Step 1: 写失败测试**（`test_drift_snapshot_writer.py`）

```python
import pytest
from odap.biz.semantic_admin.drift_scan.services import snapshot_writer
from odap.biz.semantic_admin.drift_scan.storage import SQLiteDriftStorage


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = SQLiteDriftStorage(db_path=str(tmp_path / "drift.db"))
    monkeypatch.setattr(snapshot_writer, "_get_storage", lambda: s)
    return s


def test_record_indicator_snapshot(store):
    snapshot_writer.record_indicator_snapshot(
        indicator_id="ind1", ontology_id="o1",
        definition={"formula": "a/b"}, change_op="create")
    rows = store.list_indicator_snapshots("ind1")
    assert len(rows) == 1
    assert rows[0]["definition_json"]["formula"] == "a/b"


def test_record_term_history_update_before_after(store):
    snapshot_writer.record_term_history(
        term_id="t1", domain_id="d1", op="update",
        before={"canonical": "旧"}, after={"canonical": "新"})
    rows = store.list_term_history("t1")
    assert rows[0]["before_json"]["canonical"] == "旧"
    assert rows[0]["after_json"]["canonical"] == "新"


def test_hook_failure_swallowed_and_counted(store, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(snapshot_writer, "_get_storage", boom)
    before = snapshot_writer.get_hook_failures()
    snapshot_writer.record_indicator_snapshot(   # 不 raise
        indicator_id="x", ontology_id="o", definition={}, change_op="create")
    assert snapshot_writer.get_hook_failures() == before + 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_snapshot_writer.py -q --no-header -p no:cacheprovider`
Expected: FAIL（无 snapshot_writer）

- [ ] **Step 3: 写 services/snapshot_writer.py**

```python
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
```

- [ ] **Step 4: 接线 indicator 写钩子**（`ontology_service.py`）
  - `create_indicator_type`（:892）成功 return 前：
    ```python
        from odap.biz.semantic_admin.drift_scan.services.snapshot_writer import (
            record_indicator_snapshot,
        )
        record_indicator_snapshot(
            indicator_id=<新 indicator id>, ontology_id=ontology_id,
            definition=<indicator 定义 dict>, change_op="create")
    ```
  - `update_indicator_type`（:927）成功 return 前：同上，`change_op="update"`，definition 取更新后的定义。
  - 级联删除点（:159 调 `storage.delete_indicator_types_by_ontology` 之前）：先 `before = self.storage.list_indicator_types(ontology_id)`（按真实方法名 Grep 确认），删除后对每条 `record_indicator_snapshot(..., change_op="delete", definition=item)`。
  > 执行前 Grep `ontology_service.py` 确认 create/update_indicator_type 的真实返回结构与 indicator id/definition 字段名，按实填参，**不要猜字段名**（规则 14 禁幻影）。

- [ ] **Step 5: 接线 term 写钩子**（`usl_manager_service.py`）
  - `create_term`（:180）成功后：`record_term_history(term_id=<id>, domain_id=<dom>, op="create", after=<term dict>)`
  - `update_term`（:231）成功后：先取 before（更新前的 term dict），`op="update", before=..., after=...`
  - `delete_term`（:257）成功后：`op="delete", before=<被删 term dict>`
  > update/delete 的 before 必须在改动/删除**之前**取。Grep 确认 service 内已有的 get_term 调用，复用其结果，不额外造读取。

- [ ] **Step 6: 跑测试确认通过 + 回归验证**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_snapshot_writer.py -q --no-header -p no:cacheprovider`
Expected: PASS（3 passed）
再按 Global Constraints 基线法验证 `ontology_service.py` / `usl_manager_service.py` 改动零回归。

- [ ] **Step 7: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/drift_scan/services/__init__.py \
        apps/api/odap/biz/semantic_admin/drift_scan/services/snapshot_writer.py \
        apps/api/odap/biz/core/ontology/ontology_api/services/ontology_service.py \
        apps/api/odap/biz/semantic_admin/usl_manager/services/usl_manager_service.py \
        apps/api/tests/unit/biz/semantic_admin/test_drift_snapshot_writer.py
git status
```
提示用户提交（`feat(drift-scan): snapshot_writer + indicator/term 写钩子`）。**不要 git commit。**

> 注：`services/__init__.py` 导入了 `DriftService`（Task 5 才创建）。为避免 Task 2 阶段 import 失败，本 Task 先只在 `__init__.py` 写 snapshot_writer 的三行导出，`DriftService` 导出留到 Task 5 补。执行时按此顺序。

---

### Task 3: fork 扫描算法（纯函数）

**Files:**
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/services/scanners.py`（本 Task 只写 `fork_scan`）
- Test: `apps/api/tests/unit/biz/semantic_admin/test_drift_fork_scanner.py`

**Interfaces:**
- Consumes: UslTerm dict 列表（`model_dump` 结果，含 canonical/synonyms/near_synonyms/aliases/stoplist_flag/domain_id/semantic_type/id）。
- Produces: `fork_scan(terms: list[dict], scope: dict) -> list[dict]`（返回 finding dict 列表，kind=fork，subject=expression，sides_json=各侧证据；不含 report_id，由 service 补）。

- [ ] **Step 1: 写失败测试**（`test_drift_fork_scanner.py`，真 UslTerm 对象）

```python
import pytest
from odap.biz.semantic_admin.usl_manager.models.usl_term import UslTerm, SemanticType
from odap.biz.semantic_admin.drift_scan.services.scanners import fork_scan


def _term(id, canonical, dom="d1", **kw):
    return UslTerm(id=id, domain_id=dom, canonical=canonical,
                   semantic_type=SemanticType.OBJECT_TYPE, **kw).model_dump()


def test_fork_detected_when_expression_maps_to_two_terms():
    terms = [
        _term("t1", "势力", synonyms=["阵营"]),
        _term("t2", "军团", synonyms=["阵营"]),   # “阵营” 同时挂 t1/t2
    ]
    findings = fork_scan(terms, scope={"domain_id": "d1"})
    assert len(findings) == 1
    f = findings[0]
    assert f["kind"] == "fork"
    assert f["subject"] == "阵营"
    sides = {s["term_id"] for s in f["sides_json"]}
    assert sides == {"t1", "t2"}


def test_stoplist_excluded():
    terms = [
        _term("t1", "势力", synonyms=["的"]),
        _term("t2", "军团", synonyms=["的"], stoplist_flag=True),
    ]
    # t2 停用词整体不参与；“的” 只挂 t1 → 无 fork
    assert fork_scan(terms, scope={}) == []


def test_empty_and_whitespace_excluded():
    terms = [_term("t1", "势力", synonyms=["", "  "]), _term("t2", "军团", aliases=[""])]
    assert fork_scan(terms, scope={}) == []


def test_single_term_expression_no_false_positive():
    terms = [_term("t1", "势力", synonyms=["阵营"]), _term("t2", "人物")]
    assert fork_scan(terms, scope={}) == []


def test_canonical_collision_is_fork():
    terms = [_term("t1", "势力", dom="d1"), _term("t2", "势力", dom="d2")]
    findings = fork_scan(terms, scope={})
    assert len(findings) == 1
    assert findings[0]["subject"] == "势力"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_fork_scanner.py -q --no-header -p no:cacheprovider`
Expected: FAIL（无 scanners 模块）

- [ ] **Step 3: 写 services/scanners.py 的 fork_scan**

```python
"""scanners —— 漂移扫描纯函数（无 LLM、无推断、无副作用）。"""
from __future__ import annotations

from typing import Any, Dict, List

from ..models.drift import DriftKind


def _expressions_of(term: Dict[str, Any]) -> List[str]:
    """展开一个术语的全部说法原文（canonical + synonyms + near_synonyms + aliases）。"""
    out: List[str] = []
    canonical = str(term.get("canonical") or "").strip()
    if canonical:
        out.append(canonical)
    for key in ("synonyms", "near_synonyms", "aliases"):
        for e in (term.get(key) or []):
            es = str(e).strip()
            if es:
                out.append(es)
    return out


def fork_scan(terms: List[Dict[str, Any]], scope: Dict[str, Any]) -> List[Dict[str, Any]]:
    """术语分叉扫描：同一说法原文挂到 ≥2 个 distinct term 即分叉。

    排除 stoplist_flag=True 的术语与空串/纯空白表达。
    返回 finding dict 列表（不含 report_id，由 service 补）。
    """
    expr_map: Dict[str, List[Dict[str, Any]]] = {}
    for t in terms:
        if t.get("stoplist_flag"):
            continue
        side = {
            "term_id": t.get("id"), "canonical": t.get("canonical"),
            "domain_id": t.get("domain_id"), "semantic_type": str(t.get("semantic_type") or ""),
            "from_list": [],
        }
        for expr in _expressions_of(t):
            entry = expr_map.setdefault(expr, [])
            # 记录该 side 从哪个列表命中（证据可追溯）
            hit_from = "canonical" if expr == str(t.get("canonical") or "").strip() else "synonym"
            side_copy = dict(side)
            side_copy["from_list"] = [hit_from]
            entry.append(side_copy)

    findings: List[Dict[str, Any]] = []
    for expr, sides in expr_map.items():
        distinct = {s["term_id"] for s in sides if s.get("term_id")}
        if len(distinct) >= 2:
            # 每个 term 合并成一侧（去重 term_id）
            merged: Dict[str, Dict[str, Any]] = {}
            for s in sides:
                tid = s.get("term_id")
                if tid is None:
                    continue
                if tid not in merged:
                    merged[tid] = dict(s)
                else:
                    merged[tid]["from_list"] = sorted(
                        set(merged[tid]["from_list"]) | set(s["from_list"]))
            findings.append({
                "kind": DriftKind.FORK.value, "source": "", "subject": expr,
                "subject_label": expr, "sides_json": list(merged.values()),
            })
    findings.sort(key=lambda f: f["subject"])
    return findings
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_fork_scanner.py -q --no-header -p no:cacheprovider`
Expected: PASS（5 passed）

- [ ] **Step 5: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/drift_scan/services/scanners.py \
        apps/api/tests/unit/biz/semantic_admin/test_drift_fork_scanner.py
git status
```
提示用户提交（`feat(drift-scan): 术语分叉扫描纯函数`）。**不要 git commit。**

---

### Task 4: 三来源演进 diff（纯函数）

**Files:**
- Modify: `apps/api/odap/biz/semantic_admin/drift_scan/services/scanners.py`（新增 `diff_version_snapshots` / `diff_indicator_snapshots` / `diff_term_history` + 通用 `_diff_fields`）
- Test: `apps/api/tests/unit/biz/semantic_admin/test_drift_evolution_diff.py`

**Interfaces:**
- Consumes: 解析后的 snapshot dict / indicator 快照行 / term 历史行。
- Produces:
  - `diff_version_snapshots(snap_a: dict, snap_b: dict, *, version_a: str, version_b: str) -> list[dict]`（entities 按 entity_id join，relations 按 relation_id，rules 按 rule_id，constraints 按 constraint_id；新增/删除记 `field='__added__'/'__removed__'`；actions/events 不 diff）
  - `diff_indicator_snapshots(rows: list[dict]) -> list[dict]`（按 captured_at 序相邻 diff definition_json；create/delete op 记 `__added__`/`__removed__`）
  - `diff_term_history(rows: list[dict]) -> list[dict]`（按 at 序相邻 diff before/after 的 canonical/synonyms/near_synonyms/aliases/definition/semantic_type/stoplist_flag）
  - 所有 finding：kind=evolution，source=对应 EvolutionSource.value，version_ref_json（① `{version_a,version_b}`；②③ `{prev_at,cur_at}`）

- [ ] **Step 1: 写失败测试**（`test_drift_evolution_diff.py`）

```python
import pytest
from odap.biz.semantic_admin.drift_scan.services.scanners import (
    diff_version_snapshots, diff_indicator_snapshots, diff_term_history,
)
from odap.biz.semantic_admin.drift_scan.models import EvolutionSource


def test_version_diff_field_change():
    a = {"entities": [{"entity_id": "e1", "name": "势力", "name_en": "force"}],
         "relations": [], "rules": [], "constraints": []}
    b = {"entities": [{"entity_id": "e1", "name": "势力", "name_en": "faction"}],
         "relations": [], "rules": [], "constraints": []}
    fs = diff_version_snapshots(a, b, version_a="v1", version_b="v2")
    assert len(fs) == 1
    assert fs[0]["field"] == "name_en"
    assert fs[0]["old_value_json"] == "force"
    assert fs[0]["new_value_json"] == "faction"
    assert fs[0]["version_ref_json"] == {"version_a": "v1", "version_b": "v2"}
    assert fs[0]["source"] == EvolutionSource.VERSION_SNAPSHOT.value


def test_version_diff_added_removed_entity():
    a = {"entities": [{"entity_id": "e1", "name": "势力"}], "relations": [], "rules": [], "constraints": []}
    b = {"entities": [{"entity_id": "e2", "name": "人物"}], "relations": [], "rules": [], "constraints": []}
    fs = diff_version_snapshots(a, b, version_a="v1", version_b="v2")
    fields = {f["field"] for f in fs}
    assert "__removed__" in fields and "__added__" in fields


def test_version_diff_no_change_is_empty():
    a = {"entities": [{"entity_id": "e1", "name": "势力"}], "relations": [], "rules": [], "constraints": []}
    assert diff_version_snapshots(a, a, version_a="v1", version_b="v2") == []


def test_indicator_diff_across_snapshots():
    rows = [
        {"indicator_id": "i1", "captured_at": "2026-01-01T00:00:00",
         "definition_json": {"formula": "a/b"}, "change_op": "create"},
        {"indicator_id": "i1", "captured_at": "2026-02-01T00:00:00",
         "definition_json": {"formula": "a/c"}, "change_op": "update"},
    ]
    fs = diff_indicator_snapshots(rows)
    assert len(fs) == 1
    assert fs[0]["field"] == "formula"
    assert fs[0]["old_value_json"] == "a/b" and fs[0]["new_value_json"] == "a/c"
    assert fs[0]["source"] == EvolutionSource.INDICATOR_CALIBER.value
    assert fs[0]["version_ref_json"] == {"prev_at": "2026-01-01T00:00:00",
                                         "cur_at": "2026-02-01T00:00:00"}


def test_indicator_single_snapshot_no_diff():
    rows = [{"indicator_id": "i1", "captured_at": "2026-01-01T00:00:00",
             "definition_json": {"formula": "a"}, "change_op": "create"}]
    assert diff_indicator_snapshots(rows) == []


def test_term_history_diff():
    rows = [
        {"term_id": "t1", "at": "2026-01-01T00:00:00", "op": "create",
         "before_json": None, "after_json": {"canonical": "势力", "synonyms": []}},
        {"term_id": "t1", "at": "2026-02-01T00:00:00", "op": "update",
         "before_json": {"canonical": "势力", "synonyms": []},
         "after_json": {"canonical": "势力", "synonyms": ["阵营"]}},
    ]
    fs = diff_term_history(rows)
    assert len(fs) == 1
    assert fs[0]["field"] == "synonyms"
    assert fs[0]["source"] == EvolutionSource.USL_TERM.value
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_evolution_diff.py -q --no-header -p no:cacheprovider`
Expected: FAIL（无三个 diff 函数）

- [ ] **Step 3: 给 scanners.py 追加 diff 函数**

```python
from ..models.drift import EvolutionSource  # 追加到文件顶部 import

_ENTITY_FIELDS = ("name", "name_en", "aliases", "basic_properties",
                  "statistical_properties", "capabilities", "constraints")
_RELATION_FIELDS = ("source_entity", "target_entity", "relation_type", "properties")
_RULE_FIELDS = ("condition", "consequence", "priority")
_CONSTRAINT_FIELDS = ("constraint_type", "description", "scope",
                      "violation_consequence", "legal_basis")
_TERM_FIELDS = ("canonical", "synonyms", "near_synonyms", "aliases",
                "definition", "semantic_type", "stoplist_flag")


def _index_by(items, key):
    out = {}
    for it in (items or []):
        k = it.get(key)
        if k is not None:
            out[k] = it
    return out


def _diff_bodies(idx_a, idx_b, fields, *, kind_source, version_ref, label_fn):
    """通用字段级 diff：返回 finding dict 列表（新增/删除/字段变更）。"""
    findings = []
    for k, b in idx_b.items():
        if k not in idx_a:
            findings.append({
                "kind": DriftKind.EVOLUTION.value, "source": kind_source,
                "subject": str(k), "subject_label": label_fn(b),
                "field": "__added__", "old_value_json": None, "new_value_json": b,
                "version_ref_json": version_ref,
            })
            continue
        a = idx_a[k]
        for fld in fields:
            av, bv = a.get(fld), b.get(fld)
            if av != bv:
                findings.append({
                    "kind": DriftKind.EVOLUTION.value, "source": kind_source,
                    "subject": str(k), "subject_label": label_fn(b),
                    "field": fld, "old_value_json": av, "new_value_json": bv,
                    "version_ref_json": version_ref,
                })
    for k, a in idx_a.items():
        if k not in idx_b:
            findings.append({
                "kind": DriftKind.EVOLUTION.value, "source": kind_source,
                "subject": str(k), "subject_label": label_fn(a),
                "field": "__removed__", "old_value_json": a, "new_value_json": None,
                "version_ref_json": version_ref,
            })
    return findings


def diff_version_snapshots(snap_a: Dict[str, Any], snap_b: Dict[str, Any], *,
                           version_a: str, version_b: str) -> List[Dict[str, Any]]:
    """相邻版本 doc_snapshot 字段级 diff（entities/relations/rules/constraints）。

    actions/events 为运行时数据，明示不进 diff。
    """
    vref = {"version_a": version_a, "version_b": version_b}
    src = EvolutionSource.VERSION_SNAPSHOT.value
    out: List[Dict[str, Any]] = []
    out += _diff_bodies(_index_by(snap_a.get("entities"), "entity_id"),
                        _index_by(snap_b.get("entities"), "entity_id"),
                        _ENTITY_FIELDS, kind_source=src, version_ref=vref,
                        label_fn=lambda x: x.get("name") or x.get("entity_id"))
    out += _diff_bodies(_index_by(snap_a.get("relations"), "relation_id"),
                        _index_by(snap_b.get("relations"), "relation_id"),
                        _RELATION_FIELDS, kind_source=src, version_ref=vref,
                        label_fn=lambda x: x.get("relation_id"))
    out += _diff_bodies(_index_by(snap_a.get("rules"), "rule_id"),
                        _index_by(snap_b.get("rules"), "rule_id"),
                        _RULE_FIELDS, kind_source=src, version_ref=vref,
                        label_fn=lambda x: x.get("description") or x.get("rule_id"))
    out += _diff_bodies(_index_by(snap_a.get("constraints"), "constraint_id"),
                        _index_by(snap_b.get("constraints"), "constraint_id"),
                        _CONSTRAINT_FIELDS, kind_source=src, version_ref=vref,
                        label_fn=lambda x: x.get("description") or x.get("constraint_id"))
    return out


def diff_indicator_snapshots(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """indicator 口径快照按 captured_at 序相邻 diff definition_json 键级。"""
    src = EvolutionSource.INDICATOR_CALIBER.value
    ordered = sorted(rows or [], key=lambda r: r.get("captured_at") or "")
    out: List[Dict[str, Any]] = []
    for prev, cur in zip(ordered, ordered[1:]):
        vref = {"prev_at": prev.get("captured_at"), "cur_at": cur.get("captured_at")}
        pid = cur.get("indicator_id") or prev.get("indicator_id")
        pdef, cdef = prev.get("definition_json") or {}, cur.get("definition_json") or {}
        op = cur.get("change_op", "update")
        if op == "delete":
            out.append({"kind": DriftKind.EVOLUTION.value, "source": src,
                        "subject": str(pid), "subject_label": str(pid),
                        "field": "__removed__", "old_value_json": pdef,
                        "new_value_json": None, "version_ref_json": vref})
            continue
        if prev.get("change_op") == "create" and op == "create":
            continue
        for fld in sorted(set(pdef) | set(cdef)):
            if pdef.get(fld) != cdef.get(fld):
                out.append({"kind": DriftKind.EVOLUTION.value, "source": src,
                            "subject": str(pid), "subject_label": str(pid),
                            "field": fld, "old_value_json": pdef.get(fld),
                            "new_value_json": cdef.get(fld), "version_ref_json": vref})
    return out


def diff_term_history(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """USL 术语历史按 at 序相邻 diff before/after 的关键字段。"""
    src = EvolutionSource.USL_TERM.value
    ordered = sorted(rows or [], key=lambda r: r.get("at") or "")
    out: List[Dict[str, Any]] = []
    for prev, cur in zip(ordered, ordered[1:]):
        vref = {"prev_at": prev.get("at"), "cur_at": cur.get("at")}
        tid = cur.get("term_id") or prev.get("term_id")
        before = cur.get("before_json") or prev.get("after_json") or {}
        after = cur.get("after_json") or {}
        if cur.get("op") == "delete":
            out.append({"kind": DriftKind.EVOLUTION.value, "source": src,
                        "subject": str(tid), "subject_label": str(before.get("canonical") or tid),
                        "field": "__removed__", "old_value_json": before,
                        "new_value_json": None, "version_ref_json": vref})
            continue
        for fld in _TERM_FIELDS:
            if before.get(fld) != after.get(fld):
                out.append({"kind": DriftKind.EVOLUTION.value, "source": src,
                            "subject": str(tid),
                            "subject_label": str(after.get("canonical") or tid),
                            "field": fld, "old_value_json": before.get(fld),
                            "new_value_json": after.get(fld), "version_ref_json": vref})
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_evolution_diff.py -q --no-header -p no:cacheprovider`
Expected: PASS（6 passed）

- [ ] **Step 5: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/drift_scan/services/scanners.py \
        apps/api/tests/unit/biz/semantic_admin/test_drift_evolution_diff.py
git status
```
提示用户提交（`feat(drift-scan): 三来源口径演进字段级 diff`）。**不要 git commit。**

---

### Task 5: DriftService（run_scan / list / get / on_ontology_committed）+ commit 侧道自动触发

**Files:**
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/services/drift_service.py`
- Modify: `apps/api/odap/biz/semantic_admin/drift_scan/services/__init__.py`（补 `from .drift_service import DriftService`）
- Modify: `apps/api/odap/biz/core/ontology/ontology_api/services/ontology_service.py`（`commit_schema_version` 成功 return 前加侧道触发）
- Test: `apps/api/tests/unit/biz/semantic_admin/test_drift_auto_trigger.py`

**Interfaces:**
- Consumes: `SQLiteDriftStorage`、scanners、`UslTermResolver`/USL 存储（取全量 term）、version 存储（取相邻 doc_snapshot）。
- Produces:
  - `DriftService(storage=None)`：`run_scan(*, scope=None, trigger="manual", ontology_id=None) -> {"status":"ok","report_id":...}`、`list_reports(**filters)`、`get_report(id)`、`latest_report()`、`on_ontology_committed(ontology_id) -> None`（`asyncio.create_task` 侧道，异常不传播）
  - `run_scan` 内单源失败 → `source_errors[source]=err`，跳过该源 findings；≥1 源成功→status=ok；全失败→status=failed + error。

- [ ] **Step 1: 写失败测试**（`test_drift_auto_trigger.py`，真 run_scan + 真 scanners）

```python
import asyncio
import pytest
from odap.biz.semantic_admin.drift_scan.services import DriftService
from odap.biz.semantic_admin.drift_scan.storage import SQLiteDriftStorage


@pytest.fixture
def store(tmp_path):
    return SQLiteDriftStorage(db_path=str(tmp_path / "drift.db"))


def _seed_terms(store, monkeypatch):
    # 注入一对 fork 术语 + 一条 indicator 快照变更
    terms = [
        {"id": "t1", "canonical": "势力", "domain_id": "d1", "semantic_type": "对象类型",
         "synonyms": ["阵营"], "near_synonyms": [], "aliases": [], "stoplist_flag": False},
        {"id": "t2", "canonical": "军团", "domain_id": "d1", "semantic_type": "对象类型",
         "synonyms": ["阵营"], "near_synonyms": [], "aliases": [], "stoplist_flag": False},
    ]
    monkeypatch.setattr(DriftService, "_load_terms", lambda self, scope: terms)
    monkeypatch.setattr(DriftService, "_load_version_pairs", lambda self, oid: [])
    store.append_indicator_snapshot({"indicator_id": "i1", "ontology_id": "o1",
        "definition_json": {"formula": "a/b"}, "change_op": "create",
        "captured_at": "2026-01-01T00:00:00"})
    store.append_indicator_snapshot({"indicator_id": "i1", "ontology_id": "o1",
        "definition_json": {"formula": "a/c"}, "change_op": "update",
        "captured_at": "2026-02-01T00:00:00"})


def test_run_scan_produces_expected_findings_exactly(store, monkeypatch):
    _seed_terms(store, monkeypatch)
    svc = DriftService(storage=store)
    r = svc.run_scan(scope={"domain_id": "d1"}, trigger="manual", ontology_id="o1")
    assert r["status"] == "ok"
    rep = store.get_report(r["report_id"])
    assert rep["status"] == "ok"
    # 恰好 1 fork + 1 indicator 演进，不多不少
    assert rep["counts_json"]["forks"] == 1
    assert rep["counts_json"]["evolutions"] == 1
    assert rep["source_errors_json"] == {}


def test_run_scan_records_source_error_on_partial_failure(store, monkeypatch):
    _seed_terms(store, monkeypatch)
    def boom(self, oid):
        raise RuntimeError("version store down")
    monkeypatch.setattr(DriftService, "_load_version_pairs", boom)
    svc = DriftService(storage=store)
    r = svc.run_scan(scope={}, trigger="manual", ontology_id="o1")
    rep = store.get_report(r["report_id"])
    assert rep["status"] == "ok"                       # ≥1 源成功
    assert "version_snapshot" in rep["source_errors_json"]


def test_on_ontology_committed_schedules_scan(store, monkeypatch):
    _seed_terms(store, monkeypatch)
    svc = DriftService(storage=store)
    monkeypatch.setattr(DriftService, "_instance_for_hook", lambda oid: svc, raising=False)
    svc.on_ontology_committed("o1")
    # 让 create_task 有机会跑完
    loop = asyncio.new_event_loop()
    loop.run_until_complete(asyncio.sleep(0.05))
    loop.close()
    import time; time.sleep(0.1)
    items, total = store.list_reports(trigger="commit")
    assert total >= 1
```

> `on_ontology_committed` 用 `asyncio.create_task`；测试需在事件循环内触发或提供同步 fallback。执行时若 `create_task` 在无 loop 环境报错，`on_ontology_committed` 应捕获「无 running loop」并退化为**同步执行一次 run_scan**（记录 warning，不静默丢弃）——此退化属规则 14 可观测兜底，须在 ADR-087 注明。测试据实调整。

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_auto_trigger.py -q --no-header -p no:cacheprovider`
Expected: FAIL（无 DriftService）

- [ ] **Step 3: 写 services/drift_service.py**

```python
"""DriftService —— 漂移扫描编排（规则 2/6；报告不可变；source_errors 显式）。"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..models.drift import DriftReport, EvolutionSource
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

    def _load_version_pairs(self, ontology_id: Optional[str]) -> List[Tuple[Dict, str, str]]:
        """返回 [(snap_a_parsed, snap_b_parsed, version_a, version_b)] 相邻 committed 版本对。

        规则 14：直接调用版本管理器的真实方法，禁止 hasattr 探测式降级。
        执行前用 Grep 确认 OntologyVersionManager 取版本列表的真实方法名与返回
        结构（dataclass 还是 dict），据实调整下面两行；方法名错了就让它抛异常，
        由 run_scan 记入 source_errors（失败显式），不要静默返回空。
        """
        from odap.biz.core.ontology.design.services.version_service import (
            OntologyVersionManager,
        )
        vm = OntologyVersionManager.get_instance()
        versions = vm.list_versions(ontology_id)   # ← Grep 确认真实方法名后据实改
        # 只取含 doc_snapshot 的 committed 版本，按 created_at 序相邻配对
        with_snap = []
        for v in versions:
            snap = v.get("doc_snapshot") if isinstance(v, dict) else getattr(v, "doc_snapshot", None)
            vid = v.get("version_id") if isinstance(v, dict) else getattr(v, "version_id", None)
            if snap:
                with_snap.append((vid, snap))
        pairs = []
        for (vid_a, snap_a), (vid_b, snap_b) in zip(with_snap, with_snap[1:]):
            pa = json.loads(snap_a) if isinstance(snap_a, str) else snap_a
            pb = json.loads(snap_b) if isinstance(snap_b, str) else snap_b
            pairs.append((pa, pb, vid_a, vid_b))
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
        evolutions = 0

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

        evolutions = len([f for f in findings if f["kind"] == "evolution"])
        # 全源失败判定：四个源全部记错 → failed
        all_sources = {"fork", EvolutionSource.VERSION_SNAPSHOT.value,
                       EvolutionSource.INDICATOR_CALIBER.value, EvolutionSource.USL_TERM.value}
        all_failed = all_sources.issubset(source_errors.keys())
        report.counts = {"forks": forks, "evolutions": evolutions, "total": len(findings)}
        report.source_errors = source_errors
        report.finished_at = _utc_now_iso()
        report.status = "failed" if all_failed else "ok"
        if all_failed:
            report.error = "所有漂移来源均扫描失败"

        for f in findings:
            f["report_id"] = report.id
        self.storage.save_report_with_findings(report.to_dict(), findings)
        if report.status == "failed":
            return {"status": "error", "message": report.error, "report_id": report.id}
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
        return {"status": "ok", "report": rep, "findings": findings, "grouped": grouped}

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
            logger.warning("drift 自动触发无事件循环，退化同步执行 ontology=%s", ontology_id)
            try:
                self.run_scan(scope={"ontology_id": ontology_id},
                              trigger="commit", ontology_id=ontology_id)
            except Exception as e:
                logger.warning("drift 同步自动扫描失败 ontology=%s: %s", ontology_id, e)

    async def _auto_scan(self, ontology_id: str) -> None:
        try:
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self.run_scan(scope={"ontology_id": ontology_id},
                                      trigger="commit", ontology_id=ontology_id),
            )
        except Exception as e:
            logger.warning("drift 自动扫描 task 失败 ontology=%s: %s", ontology_id, e, exc_info=True)
```

- [ ] **Step 4: 补 services/__init__.py**（加 `from .drift_service import DriftService`）

- [ ] **Step 5: 接线 commit 侧道触发**（`ontology_service.py:257` 成功 return 之前）

```python
            # 语义漂移侧道自动扫描（规则 14：异常绝不传播 commit 路径）
            try:
                from odap.biz.semantic_admin.drift_scan.services import DriftService
                DriftService().on_ontology_committed(ontology_id)
            except Exception as drift_exc:
                logger.warning("drift 自动触发调度失败 ontology=%s: %s",
                               ontology_id, drift_exc)

            return {
                "version_id": current_working["version_id"] if current_working else new_version_id,
                ...
            }
```

- [ ] **Step 6: 跑测试确认通过 + 回归验证**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_auto_trigger.py -q --no-header -p no:cacheprovider`
Expected: PASS（3 passed）
再按基线法验证 `ontology_service.py` 改动零回归。

- [ ] **Step 7: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/drift_scan/services/drift_service.py \
        apps/api/odap/biz/semantic_admin/drift_scan/services/__init__.py \
        apps/api/odap/biz/core/ontology/ontology_api/services/ontology_service.py \
        apps/api/tests/unit/biz/semantic_admin/test_drift_auto_trigger.py
git status
```
提示用户提交（`feat(drift-scan): DriftService run_scan + commit 侧道自动触发`）。**不要 git commit。**

> 执行前 Grep 确认 `OntologyVersionManager` 取版本列表的真实方法名（`list_versions` vs 其它）与返回结构（dataclass vs dict），按实改 `_load_version_pairs`，不要留 `hasattr` 探测式降级（规则 14）。

---

### Task 6: drift 路由 + 生产入口注册

**Files:**
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/api/__init__.py`（空）
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/api/schemas.py`
- Create: `apps/api/odap/biz/semantic_admin/drift_scan/api/routes.py`（prefix `/api/semantic-admin/drift`）
- Modify: `apps/api/odap/web/app.py`（`include_router`）
- Modify: `apps/api/odap/web/router_registry.py`
- Test: `apps/api/tests/unit/biz/semantic_admin/test_drift_routes.py`

**Interfaces:**
- Consumes: `DriftService`；鉴权 `get_current_user`（扫描对语义资产只读，spec §2）。
- Produces: `POST /scan`、`GET /reports`、`GET /reports/{id}`、`GET /reports/latest`。

- [ ] **Step 1: 写失败测试**（`test_drift_routes.py`）

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from odap.biz.semantic_admin.drift_scan.api.routes import router
from odap.biz.semantic_admin.drift_scan.services import DriftService
from odap.biz.semantic_admin.drift_scan.storage import SQLiteDriftStorage


@pytest.fixture
def client(tmp_path):
    store = SQLiteDriftStorage(db_path=str(tmp_path / "drift.db"))
    app = FastAPI()
    app.include_router(router)
    from odap.biz.semantic_admin.drift_scan.api import routes as R
    app.dependency_overrides[R.get_current_user] = lambda: {"sub": "alice", "role": "admin"}
    R._drift_service_override = DriftService(storage=store)
    # 避免真扫描依赖：monkeypatch run_scan 到最小实现
    store.save_report_with_findings(
        {"id": "r1", "trigger": "manual", "status": "ok", "started_at": "2026-01-01T00:00:00",
         "scope_json": {}, "source_errors_json": {}, "counts_json": {"forks": 0, "evolutions": 0}}, [])
    return TestClient(app)


def test_list_reports(client):
    r = client.get("/api/semantic-admin/drift/reports")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_get_report_404(client):
    r = client.get("/api/semantic-admin/drift/reports/nope")
    assert r.status_code == 404


def test_get_report_ok(client):
    r = client.get("/api/semantic-admin/drift/reports/r1")
    assert r.status_code == 200
    assert "report" in r.json()


def test_latest(client):
    r = client.get("/api/semantic-admin/drift/reports/latest")
    assert r.status_code == 200
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_routes.py -q --no-header -p no:cacheprovider`
Expected: FAIL（无 routes）

- [ ] **Step 3: 写 api/schemas.py**

```python
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ScanRequest(BaseModel):
    ontology_id: Optional[str] = None
    domain_id: Optional[str] = None
```

- [ ] **Step 4: 写 api/routes.py**

```python
"""drift_scan 路由（规则 3：except HTTPException: raise；规则 6：只调 service）。"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from odap.infra.security.dependencies import get_current_user  # 按实际鉴权模块调整
from ..services.drift_service import DriftService
from .schemas import ScanRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/semantic-admin/drift", tags=["semantic-admin-drift"])

_drift_service_override: Optional[DriftService] = None
_drift_service_singleton: Optional[DriftService] = None


def _svc() -> DriftService:
    global _drift_service_singleton
    if _drift_service_override is not None:
        return _drift_service_override
    if _drift_service_singleton is None:
        _drift_service_singleton = DriftService()
    return _drift_service_singleton


@router.post("/scan")
async def trigger_scan(body: ScanRequest = ScanRequest(), _user=Depends(get_current_user)):
    try:
        scope = {k: v for k, v in {"ontology_id": body.ontology_id,
                                   "domain_id": body.domain_id}.items() if v}
        r = _svc().run_scan(scope=scope, trigger="manual", ontology_id=body.ontology_id)
        if r.get("status") == "error" and not r.get("report_id"):
            raise HTTPException(status_code=500, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports")
async def list_reports(trigger: Optional[str] = Query(None),
                       status: Optional[str] = Query(None),
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                       _user=Depends(get_current_user)):
    try:
        r = _svc().list_reports(trigger=trigger, status=status, page=page, page_size=page_size)
        if r.get("status") == "error":
            raise HTTPException(status_code=500, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/latest")
async def latest_report(_user=Depends(get_current_user)):
    try:
        return _svc().latest_report()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}")
async def get_report(report_id: str, _user=Depends(get_current_user)):
    try:
        r = _svc().get_report(report_id)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "REPORT_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

> `/reports/latest` 必须声明在 `/reports/{report_id}` **之前**，否则 `latest` 被当作 report_id 匹配。

- [ ] **Step 5: 注册生产入口**（`web/app.py` include_router + `router_registry.py` 登记 `/api/semantic-admin/drift`）

- [ ] **Step 6: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_drift_routes.py -q --no-header -p no:cacheprovider`
Expected: PASS（4 passed）

- [ ] **Step 7: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/drift_scan/api/__init__.py \
        apps/api/odap/biz/semantic_admin/drift_scan/api/schemas.py \
        apps/api/odap/biz/semantic_admin/drift_scan/api/routes.py \
        apps/api/odap/web/app.py \
        apps/api/odap/web/router_registry.py \
        apps/api/tests/unit/biz/semantic_admin/test_drift_routes.py
git status
```
提示用户提交（`feat(drift-scan): 漂移 REST 路由 + 生产入口注册`）。**不要 git commit。**

---

### Task 7: 前端 driftApi + 漂移页 + 路由/菜单接入

**Files:**
- Create: `apps/web/src/modules/semantic-admin/services/driftApi.ts`
- Create: `apps/web/src/modules/semantic-admin/pages/DriftPage.tsx`
- Modify: `apps/web/src/AppRoutes.tsx`（`/semantic-admin/drift`）
- Modify: `apps/web/src/modules/semantic-admin/routes.tsx`（meta，若存在）
- Modify: `apps/api/odap/biz/platform/menu_config/seeds/seed_four_steps.py`
- Create: `scripts/migrations/add_drift_menu.py`

**Interfaces:**
- Consumes: `fetchJson` / `API_BASE`。
- Produces: `driftApi.scan(body)` / `.listReports(params)` / `.getReport(id)` / `.latest()`；`DriftPage` 组件；菜单项 `menu:build:semantic:drift`。

- [ ] **Step 1: 写 driftApi.ts**

```typescript
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const BASE = `${API_BASE}/api/semantic-admin/drift`;

export interface DriftFinding {
  id: string; kind: 'fork' | 'evolution'; source: string;
  subject: string; subject_label?: string; field?: string | null;
  old_value_json?: any; new_value_json?: any;
  sides_json?: Array<Record<string, any>> | null;
  version_ref_json?: Record<string, any> | null;
}
export interface DriftReport {
  id: string; trigger: 'manual' | 'commit'; status: 'ok' | 'failed';
  started_at: string; finished_at?: string | null; ontology_id?: string | null;
  counts_json: Record<string, number>;
  source_errors_json: Record<string, string>;
}

export const driftApi = {
  scan: (body: { ontology_id?: string; domain_id?: string } = {}) =>
    fetchJson<{ report_id: string; status: string }>(`${BASE}/scan`,
      { method: 'POST', body: JSON.stringify(body) }),
  listReports: (params: { trigger?: string; status?: string; page?: number; page_size?: number } = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]),
    ).toString();
    return fetchJson<{ items: DriftReport[]; total: number }>(`${BASE}/reports?${qs}`);
  },
  getReport: (id: string) =>
    fetchJson<{ report: DriftReport; findings: DriftFinding[];
                grouped: Record<string, DriftFinding[]> }>(`${BASE}/reports/${id}`),
  latest: () => fetchJson<{ report: DriftReport | null }>(`${BASE}/reports/latest`),
};
```

> 执行前读 `apiClient.ts` 确认 `fetchJson` 的 method/body 传参形式，按实调整。

- [ ] **Step 2: 写 DriftPage.tsx**（扫描按钮 + 报告列表 + 双栏详情 + source_errors banner）

```tsx
import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Col, Row, Select, Space, Table, Tag, message } from 'antd';
import { driftApi, type DriftReport, type DriftFinding } from '../services/driftApi';

export const DriftPage: React.FC = () => {
  const [reports, setReports] = useState<DriftReport[]>([]);
  const [selected, setSelected] = useState<{ report: DriftReport; grouped: Record<string, DriftFinding[]> } | null>(null);
  const [loading, setLoading] = useState(false);

  const loadReports = useCallback(async () => {
    setLoading(true);
    try { const r = await driftApi.listReports({ page_size: 50 }); setReports(r.items ?? []); }
    catch (e: any) { message.error(e?.message || '加载报告失败'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { loadReports(); }, [loadReports]);

  const onScan = async () => {
    try { await driftApi.scan({}); message.success('扫描完成'); loadReports(); }
    catch (e: any) { message.error(e?.message || '扫描失败'); }
  };
  const openReport = async (id: string) => {
    const r = await driftApi.getReport(id);
    setSelected({ report: r.report, grouped: r.grouped ?? {} });
  };

  const forks = selected?.grouped?.['fork'] ?? [];
  const evoKeys = Object.keys(selected?.grouped ?? {}).filter((k) => k.startsWith('evolution:'));
  const sourceErrors = selected?.report?.source_errors_json ?? {};

  return (
    <div style={{ padding: 16 }}>
      <Space style={{ marginBottom: 12 }}>
        <Button type="primary" onClick={onScan}>立即扫描</Button>
        <Button onClick={loadReports}>刷新</Button>
      </Space>
      <Table rowKey="id" loading={loading} dataSource={reports}
        pagination={{ pageSize: 10 }}
        onRow={(r) => ({ onClick: () => openReport(r.id) })}
        columns={[
          { title: '触发', dataIndex: 'trigger', render: (t: string) => <Tag>{t}</Tag> },
          { title: '开始', dataIndex: 'started_at' },
          { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={s === 'ok' ? 'green' : 'red'}>{s}</Tag> },
          { title: 'forks', render: (_: any, r: DriftReport) => r.counts_json?.forks ?? 0 },
          { title: 'evolutions', render: (_: any, r: DriftReport) => r.counts_json?.evolutions ?? 0 },
          { title: 'source_errors', render: (_: any, r: DriftReport) =>
              Object.keys(r.source_errors_json || {}).length
                ? <Tag color="orange">{Object.keys(r.source_errors_json).length} 源失败</Tag> : '—' },
        ]} />

      {selected && (
        <Card title={`报告 ${selected.report.id}`} style={{ marginTop: 16 }}>
          {Object.keys(sourceErrors).length > 0 && (
            <Alert type="warning" showIcon style={{ marginBottom: 12 }}
              message="部分来源扫描失败" description={
                <ul>{Object.entries(sourceErrors).map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul>} />)}
          <Row gutter={16}>
            <Col span={12}>
              <Card size="small" title={`术语分叉（${forks.length}）`}>
                {forks.map((f) => (
                  <div key={f.id} style={{ marginBottom: 8 }}>
                    <b>{f.subject}</b>
                    <ul>{(f.sides_json ?? []).map((s: any, i: number) => (
                      <li key={i}>{s.canonical}（{s.term_id}, {s.domain_id}, {s.from_list?.join('/')}）</li>))}
                    </ul>
                  </div>))}
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" title="口径演进">
                {evoKeys.map((k) => (
                  <div key={k}>
                    <Tag color="blue">{k.replace('evolution:', '')}</Tag>
                    {(selected.grouped[k] ?? []).map((f) => (
                      <div key={f.id} style={{ marginLeft: 8 }}>
                        {f.subject_label || f.subject} · <code>{f.field}</code>:
                        {' '}{JSON.stringify(f.old_value_json)} → {JSON.stringify(f.new_value_json)}
                      </div>))}
                  </div>))}
              </Card>
            </Col>
          </Row>
        </Card>)}
    </div>
  );
};
export default DriftPage;
```

- [ ] **Step 3: 注册路由 + 菜单 seed + 迁移脚本**
  - `AppRoutes.tsx`：`<Route path="/semantic-admin/drift" element={<DriftPage />} />`
  - `seed_four_steps.py`（`parent = "dir:build:semantic"`）：`_menu("menu:build:semantic:drift", "语义漂移", "/semantic-admin/drift", "LineChartOutlined", 9, parent)`
  - `scripts/migrations/add_drift_menu.py`：仿 Task 8（子项目 1）的迁移脚本，插入 `menu:build:semantic:drift`（幂等 skip；执行前 Grep 确认 menu 表名/列名）。

- [ ] **Step 4: typecheck + lint**

Run: `cd apps/web && pnpm typecheck && pnpm lint`
Expected: 无新增错误。

- [ ] **Step 5: Stage（用户提交）**

```bash
git add apps/web/src/modules/semantic-admin/services/driftApi.ts \
        apps/web/src/modules/semantic-admin/pages/DriftPage.tsx \
        apps/web/src/AppRoutes.tsx \
        apps/web/src/modules/semantic-admin/routes.tsx \
        apps/api/odap/biz/platform/menu_config/seeds/seed_four_steps.py \
        scripts/migrations/add_drift_menu.py
git status
```
提示用户提交（`feat(web): 漂移页 + driftApi + 路由菜单接入`）。**不要 git commit。**

---

### Task 8: 文档同步 + ADR-087

**Files:**
- Create: `docs/07-adr/ADR-087-semantic-drift-detection.md`
- Modify: `docs/07-adr/README.md`（索引 + 时间线）
- Modify: `docs/03-modules/README.md`（模块清单加 drift_scan）
- Modify: `agents.md`（附录 E 加 `/api/semantic-admin/drift`）

**Interfaces:** 无代码接口；规则 12 文档同步。

- [ ] **Step 1: 写 ADR-087**（Context: 无任何漂移可见性、indicator/term 无历史；Decision: 独立 drift_scan 子服务、fork 判定规则、三来源演进 diff、报告不可变证据、source_errors 显式、侧道自动触发含无-loop 同步退化、只报告真实数据无比例推断；Consequences: ②③来源「版本」退化为快照时间序的语义差异、演进 diff 从第二个快照起可用）

- [ ] **Step 2: 更新 `docs/07-adr/README.md`**（索引 + 时间线加 ADR-087）

- [ ] **Step 3: 更新 `docs/03-modules/README.md`**（semantic_admin 下加 drift_scan）

- [ ] **Step 4: 更新 `agents.md` 附录 E**（API 速查表加 `/api/semantic-admin/drift` 4 端点）

- [ ] **Step 5: 对照 `docs/09-checklists/DOC_SYNC_CHECKLIST.md` 逐项自查**

- [ ] **Step 6: Stage（用户提交）**

```bash
git add docs/07-adr/ADR-087-semantic-drift-detection.md \
        docs/07-adr/README.md \
        docs/03-modules/README.md \
        agents.md
git status
```
提示用户提交（`docs(drift-scan): ADR-087 语义漂移检测 + 文档同步`）。**不要 git commit。**

---

## 验收（对齐 spec §7）

1. 五个测试文件全绿：`test_drift_storage.py`、`test_drift_snapshot_writer.py`、`test_drift_fork_scanner.py`、`test_drift_evolution_diff.py`、`test_drift_auto_trigger.py`、`test_drift_routes.py`。
2. 种子数据（两个含已知字段变更的版本 + 一对 fork 术语 + 一次 indicator 更新 + 一次 term 改名）→ 扫描报告 findings 与这些变更**恰好一致、不多不少**；source_errors 注入故障可见。
3. commit 后自动触发产出 `trigger=commit` 报告；漂移页双栏 + source_errors banner 在 dev 容器（`python apps/api/bootstep.py dev`）手验可见。
4. 回归零新增（stashed-HEAD 基线 node-ID diff 为空）。
5. 报告不可变（无 update 接口）、counts 全为 `len(findings)`、无任何比例/推断、无 LLM 参与——纪律核查通过。
