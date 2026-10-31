---
id: odap.l15.plans-2026-10-07-concept-gap-loop
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

# 概念缺口回路（concept gap loop）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 ODAP 运行时散落在 logger 里的四类「概念缺口」信号（术语未命中 / 映射失败 / QA 兜底 / NL 查询未答）聚合成带热度的缺口池，接上 semantic_admin 既有的人工裁决链（质量门→两级审批→writeback），闭环验收标准「同一个问题下次能答上」。

**Architecture:** 新建独立子服务 `apps/api/odap/biz/semantic_admin/gap_pool/`（models/storage/services/api 四层），SQLite 单表 `concept_gaps`（唯一索引 `(expression, scope_key)`，heat 原子累加，occurrence 上限 50）。同步 emitter 在四类信号源逐点接线（只加一行调用，不改原分支返回值），异常吞为 `logger.warning` + 内存计数，绝不阻塞主路径。promote 时创建 pipeline run + candidate（`source_type='concept_gap'`），复用既有审批/writeback；writeback 成功与审批驳回经侧道回调 `on_candidate_resolved` 推进 gap 状态机。

**Tech Stack:** Python 3.10+ / FastAPI / Pydantic v2 / SQLite（stdlib sqlite3，无连接池）/ pytest；前端 React 19 + TS + Ant Design 6 + Zustand + `fetchJson`。

**Spec:** `docs/superpowers/specs/2026-10-07-concept-gap-loop-design.md`（本计划逐条实现该 spec，执行时两份文档一起读）

## Global Constraints

以下为全计划强制约束，每个 Task 的要求都隐含包含本节：

- **测试命令必须带离线变量**（否则 SentenceTransformer 用例会无限期挂起，`--timeout` 不可用）：
  ```bash
  PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    uv run pytest apps/api/tests/unit/biz/semantic_admin/<file>.py -q --no-header -p no:cacheprovider
  ```
  取退出码用 `> /tmp/out.txt 2>&1; echo "EXIT=$?"`，不要用 `| tail`（管道吞退出码）。
- **离线全量单测有 ~206 个环境依赖型失败基线**（redis/neo4j/opa/llm 不可用），不是回归。验证「我的改动有无引入回归」时不要指望全绿；用 stashed-HEAD 基线对比精确失败 node ID（`git stash push <改的源文件>` → 只重跑失败文件 → `diff nodes_mine.txt nodes_baseline.txt`，diff 为空=零回归）。完事 `git stash pop`，并 `git checkout -- apps/api/odap/infra/opa/bundles/current_bundle.json`（OPA 测试污染产物，别 stage）。
- **单测目录**：`apps/api/tests/unit/`（仓库根 `tests/` 无 unit 子目录）。本计划所有测试放 `apps/api/tests/unit/biz/semantic_admin/`。
- **提交纪律（用户约束）**：每个 Task 的 commit 步骤**只做精确 stage**（`git add <确切文件路径>`）+ 验证，**绝不运行 `git commit`**——用户本人提交。禁止 `git add -A` / `git add .`。
- **AGENTS.md 硬性规则**：
  - 规则 2：服务层返回 `Dict[str, Any]`，错误格式 `{"status":"error","message":"..."}`，禁止在服务层抛 HTTPException。
  - 规则 3：路由层 `except` 块必须含 `except HTTPException: raise`，防止被外层 500 兜底吞掉。
  - 规则 4：所有 Enum 必须 `class X(str, Enum)` 双继承。
  - 规则 5：可变容器字段用 `Field(default_factory=...)`。
  - 规则 6：调用链严格 `routes → services → storage`，禁止跨层。
  - 规则 8：SQLite 每次操作 `sqlite3.connect()` → 用完 `conn.close()`，禁止长连接；复杂字段存 JSON TEXT，Enum 存 `.value`，datetime 存 ISO 字符串。
  - 规则 9：新模块必须同步新增测试，SQLite 存储层用 `tmp_path` 真 DB，禁止 MagicMock 模拟数据库；零测试不提交。
  - 规则 12：架构级决策需新增 ADR + 同步 `docs/03-modules/README.md` / `router_registry.py` / agents.md 附录 E。
  - 规则 13：临时文件禁止写项目根；DB 路径走 `DATA_DIR` 环境变量。
  - 规则 14：禁止未经评审的兜底；失败必须显式且可观测（`logger.warning` 起，不用 debug）；禁止幻影调用 / hasattr 探测式降级；测试必须执行真实函数体（至少一条走真实实现路径，不得整段 patch 掉待验证逻辑）。
- **前端约定**：跨一级目录导入必须用 `@` 别名；API 层用 `import { fetchJson } from '@/modules/shared/services/apiClient'; import { API_BASE } from '@/config';`；页面用 antd + `useI18n` + `useSemanticAdminStore`；路由注册在 `apps/web/src/AppRoutes.tsx`，模块内 `semanticAdminRouteMeta`。
- **循环导入规避**：`gap_emitter` 在函数内**惰性导入** `GapService`；`candidate_service` / `writeback_service` 的回调也在函数内惰性导入 `gap_service`（链路 resolver→emitter→service→candidate_store→resolver 会成环）。

---

### Task 1: gap 数据模型 + SQLite 存储层

**Files:**
- Create: `apps/api/odap/biz/semantic_admin/gap_pool/__init__.py`（空）
- Create: `apps/api/odap/biz/semantic_admin/gap_pool/models/__init__.py`（`from .gap import ConceptGap, GapStatus, GapSignalSource, make_scope_key`）
- Create: `apps/api/odap/biz/semantic_admin/gap_pool/models/gap.py`
- Create: `apps/api/odap/biz/semantic_admin/gap_pool/storage/__init__.py`（`from .sqlite_gap_storage import SQLiteGapStorage; Storage = SQLiteGapStorage`）
- Create: `apps/api/odap/biz/semantic_admin/gap_pool/storage/sqlite_gap_storage.py`
- Test: `apps/api/tests/unit/biz/semantic_admin/test_gap_pool_storage.py`

**Interfaces:**
- Produces:
  - `GapStatus(str, Enum)`: `OPEN="open"`, `PROMOTED="promoted"`, `ADOPTED="adopted"`, `REJECTED="rejected"`
  - `GapSignalSource(str, Enum)`: `TERM_RESOLVE_MISS="term_resolve_miss"`, `MAPPING_FAILURE="mapping_failure"`, `QA_UNANSWERED="qa_unanswered"`, `NL_QUERY_UNANSWERED="nl_query_unanswered"`
  - `make_scope_key(workspace_id: str|None, domain_id: str|None) -> str` → `f"{workspace_id or '-'}::{domain_id or '-'}"`
  - `SQLiteGapStorage(db_path: str|None=None)`：`record_signal(...) -> dict`、`get_gap(gap_id) -> dict|None`、`get_by_expression(expression, scope_key) -> dict|None`、`list_gaps(*, status=None, source=None, workspace_id=None, page=1, page_size=20) -> (list[dict], int)`、`update_status(gap_id, status, **fields) -> bool`、`count_by_status() -> dict`、`count_by_source() -> dict`、`top_heat(n=10) -> list[dict]`

- [ ] **Step 1: 写失败测试**（`test_gap_pool_storage.py`，tmp_path 真 DB）

```python
import pytest
from odap.biz.semantic_admin.gap_pool.models import (
    ConceptGap, GapStatus, GapSignalSource, make_scope_key,
)
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage


@pytest.fixture
def store(tmp_path):
    return SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))


def test_scope_key_handles_none():
    assert make_scope_key(None, None) == "-::-"
    assert make_scope_key("ws1", "d1") == "ws1::d1"


def test_record_signal_creates_then_increments_heat(store):
    g1 = store.record_signal(
        source=GapSignalSource.TERM_RESOLVE_MISS, expression=" 势力 ",
        workspace_id="ws1", domain_id="d1", ref="resolver", detail="miss",
    )
    assert g1["heat"] == 1
    assert g1["expression"] == "势力"          # strip
    assert g1["scope_key"] == "ws1::d1"
    assert g1["status"] == GapStatus.OPEN.value
    g2 = store.record_signal(
        source=GapSignalSource.QA_UNANSWERED, expression="势力",
        workspace_id="ws1", domain_id="d1",
    )
    assert g2["id"] == g1["id"]                # 唯一索引去重
    assert g2["heat"] == 2
    assert g2["source_counts_json"]["term_resolve_miss"] == 1
    assert g2["source_counts_json"]["qa_unanswered"] == 1


def test_rejected_gap_revives_to_open_on_new_signal(store):
    g = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "军团",
                            workspace_id="ws1", domain_id="d1")
    store.update_status(g["id"], GapStatus.REJECTED.value, dismiss_reason="噪声")
    g2 = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "军团",
                             workspace_id="ws1", domain_id="d1")
    assert g2["status"] == GapStatus.OPEN.value
    assert g2["heat"] == 2


def test_sources_capped_at_50(store):
    for i in range(60):
        store.record_signal(GapSignalSource.MAPPING_FAILURE, "诸侯",
                            workspace_id="ws1", domain_id="d1", ref=f"r{i}")
    g = store.get_by_expression("诸侯", "ws1::d1")
    assert len(g["sources_json"]) == 50
    assert g["heat"] == 60                     # 计数不丢


def test_list_gaps_filters_and_pagination(store):
    for expr in ("a", "b", "c"):
        store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, expr,
                            workspace_id="ws1", domain_id="d1")
    items, total = store.list_gaps(workspace_id="ws1", page=1, page_size=2)
    assert total == 3
    assert len(items) == 2


def test_get_missing_returns_none(store):
    assert store.get_gap("nope") is None


def test_bad_json_tolerated(store, monkeypatch):
    g = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "坏json",
                            workspace_id="ws1", domain_id="d1")
    import sqlite3
    conn = sqlite3.connect(store.db_path)
    conn.execute("UPDATE concept_gaps SET source_counts_json='{bad' WHERE id=?", (g["id"],))
    conn.commit(); conn.close()
    got = store.get_gap(g["id"])
    assert got["source_counts_json"] == {}     # 坏 JSON 容错为空
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_gap_pool_storage.py -q --no-header -p no:cacheprovider`
Expected: FAIL（`ModuleNotFoundError: odap.biz.semantic_admin.gap_pool`）

- [ ] **Step 3: 写 models/gap.py**

```python
"""概念缺口模型 —— 聚合运行时未答信号（BeModel 概念缺口回路参照）。"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GapStatus(str, Enum):
    OPEN = "open"
    PROMOTED = "promoted"
    ADOPTED = "adopted"
    REJECTED = "rejected"

    def __str__(self) -> str:
        return self.value


class GapSignalSource(str, Enum):
    TERM_RESOLVE_MISS = "term_resolve_miss"
    MAPPING_FAILURE = "mapping_failure"
    QA_UNANSWERED = "qa_unanswered"
    NL_QUERY_UNANSWERED = "nl_query_unanswered"

    def __str__(self) -> str:
        return self.value


def make_scope_key(workspace_id: Optional[str], domain_id: Optional[str]) -> str:
    return f"{workspace_id or '-'}::{domain_id or '-'}"


@dataclass
class ConceptGap:
    expression: str
    scope_key: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    heat: int = 1
    source_counts: Dict[str, int] = field(default_factory=dict)
    sources: List[Dict[str, Any]] = field(default_factory=list)  # 最近 50 条 occurrence
    status: str = GapStatus.OPEN.value
    first_seen: str = field(default_factory=_utc_now_iso)
    last_seen: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    promoted_candidate_id: Optional[str] = None
    resolved_term_id: Optional[str] = None
    dismiss_reason: Optional[str] = None
    workspace_id: Optional[str] = None
    domain_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "expression": self.expression,
            "scope_key": self.scope_key,
            "heat": self.heat,
            "source_counts_json": dict(self.source_counts),
            "sources_json": list(self.sources),
            "status": self.status,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "updated_at": self.updated_at,
            "promoted_candidate_id": self.promoted_candidate_id,
            "resolved_term_id": self.resolved_term_id,
            "dismiss_reason": self.dismiss_reason,
            "workspace_id": self.workspace_id,
            "domain_id": self.domain_id,
        }


__all__ = ["ConceptGap", "GapStatus", "GapSignalSource", "make_scope_key"]
```

- [ ] **Step 4: 写 storage/sqlite_gap_storage.py**

```python
"""SQLiteGapStorage —— concept_gaps 单表存储（规则 8：每次 connect/close，JSON TEXT，ISO 时间）。"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..models.gap import GapStatus, make_scope_key

logger = logging.getLogger(__name__)

_SOURCES_CAP = 50


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_db_path() -> str:
    data_dir = os.environ.get(
        "DATA_DIR", os.path.join(os.getcwd(), "apps", "api", "data")
    )
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "concept_gaps.db")


class SQLiteGapStorage:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_db_path()
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS concept_gaps (
                    id TEXT PRIMARY KEY,
                    expression TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    heat INTEGER NOT NULL DEFAULT 1,
                    source_counts_json TEXT NOT NULL DEFAULT '{}',
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'open',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    promoted_candidate_id TEXT,
                    resolved_term_id TEXT,
                    dismiss_reason TEXT,
                    workspace_id TEXT,
                    domain_id TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_gap_expr_scope
                    ON concept_gaps(expression, scope_key);
                CREATE INDEX IF NOT EXISTS idx_gap_status ON concept_gaps(status);
                CREATE INDEX IF NOT EXISTS idx_gap_heat   ON concept_gaps(heat DESC);
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ---- JSON 容错 ----
    @staticmethod
    def _safe_json(raw: Any, default):
        if raw is None:
            return default
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("concept_gaps JSON 解析失败，回退默认值: %r", raw)
            return default

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["source_counts_json"] = self._safe_json(d.get("source_counts_json"), {})
        d["sources_json"] = self._safe_json(d.get("sources_json"), [])
        return d

    # ---- 写 ----
    def record_signal(
        self, *, source, expression: str,
        workspace_id: Optional[str] = None, domain_id: Optional[str] = None,
        ref: Optional[str] = None, detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        source_val = str(getattr(source, "value", source))
        expr = (expression or "").strip()
        if not expr:
            raise ValueError("expression 不能为空")
        scope_key = make_scope_key(workspace_id, domain_id)
        now = _utc_now_iso()
        occurrence = {"source": source_val, "ref": ref, "at": now, "detail": detail}

        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM concept_gaps WHERE expression=? AND scope_key=?",
                (expr, scope_key),
            ).fetchone()
            if row is None:
                gap_id = str(uuid.uuid4())
                counts = {source_val: 1}
                conn.execute(
                    """INSERT INTO concept_gaps (
                        id, expression, scope_key, heat, source_counts_json,
                        sources_json, status, first_seen, last_seen, updated_at,
                        workspace_id, domain_id
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (gap_id, expr, scope_key, 1,
                     json.dumps(counts, ensure_ascii=False),
                     json.dumps([occurrence], ensure_ascii=False),
                     GapStatus.OPEN.value, now, now, now, workspace_id, domain_id),
                )
                conn.commit()
                return self._row_to_dict(
                    conn.execute("SELECT * FROM concept_gaps WHERE id=?", (gap_id,)).fetchone()
                )
            # 既有：heat+1、计数累加、occurrence 追加（上限 50）、REJECTED 复活为 OPEN
            gap_id = row["id"]
            counts = self._safe_json(row["source_counts_json"], {})
            counts[source_val] = counts.get(source_val, 0) + 1
            sources = self._safe_json(row["sources_json"], [])
            sources.append(occurrence)
            sources = sources[-_SOURCES_CAP:]
            new_status = row["status"]
            if new_status == GapStatus.REJECTED.value:
                new_status = GapStatus.OPEN.value
            conn.execute(
                """UPDATE concept_gaps
                   SET heat=heat+1, source_counts_json=?, sources_json=?,
                       status=?, last_seen=?, updated_at=?
                   WHERE id=?""",
                (json.dumps(counts, ensure_ascii=False),
                 json.dumps(sources, ensure_ascii=False),
                 new_status, now, now, gap_id),
            )
            conn.commit()
            return self._row_to_dict(
                conn.execute("SELECT * FROM concept_gaps WHERE id=?", (gap_id,)).fetchone()
            )
        finally:
            conn.close()

    def update_status(self, gap_id: str, status: str, **fields) -> bool:
        allowed = {"promoted_candidate_id", "resolved_term_id", "dismiss_reason"}
        sets = ["status=?", "updated_at=?"]
        params: List[Any] = [status, _utc_now_iso()]
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k}=?")
                params.append(v)
        params.append(gap_id)
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                f"UPDATE concept_gaps SET {', '.join(sets)} WHERE id=?", params
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    # ---- 读 ----
    def get_gap(self, gap_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM concept_gaps WHERE id=?", (gap_id,)).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_by_expression(self, expression: str, scope_key: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM concept_gaps WHERE expression=? AND scope_key=?",
                ((expression or "").strip(), scope_key),
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def list_gaps(
        self, *, status: Optional[str] = None, source: Optional[str] = None,
        workspace_id: Optional[str] = None, page: int = 1, page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        where, params = [], []
        if status:
            where.append("status=?"); params.append(status)
        if workspace_id:
            where.append("workspace_id=?"); params.append(workspace_id)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM concept_gaps{clause}", params
            ).fetchone()["c"]
            offset = max(0, (page - 1) * page_size)
            rows = conn.execute(
                f"SELECT * FROM concept_gaps{clause} ORDER BY heat DESC, last_seen DESC "
                f"LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            ).fetchall()
            items = [self._row_to_dict(r) for r in rows]
            if source:  # source 过滤在计数维度，Python 侧筛
                items = [g for g in items if g["source_counts_json"].get(source)]
            return items, total
        finally:
            conn.close()

    def count_by_status(self) -> Dict[str, int]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM concept_gaps GROUP BY status"
            ).fetchall()
            out = {s.value: 0 for s in GapStatus}
            for r in rows:
                out[r["status"]] = r["c"]
            return out
        finally:
            conn.close()

    def count_by_source(self) -> Dict[str, int]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT source_counts_json FROM concept_gaps").fetchall()
            out: Dict[str, int] = {}
            for r in rows:
                for k, v in self._safe_json(r["source_counts_json"], {}).items():
                    out[k] = out.get(k, 0) + int(v)
            return out
        finally:
            conn.close()

    def top_heat(self, n: int = 10) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM concept_gaps ORDER BY heat DESC, last_seen DESC LIMIT ?", (n,)
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()
```

- [ ] **Step 5: 建两个 `__init__.py`**（内容见 Files）

- [ ] **Step 6: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_gap_pool_storage.py -q --no-header -p no:cacheprovider`
Expected: PASS（7 passed）

- [ ] **Step 7: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/gap_pool/__init__.py \
        apps/api/odap/biz/semantic_admin/gap_pool/models/__init__.py \
        apps/api/odap/biz/semantic_admin/gap_pool/models/gap.py \
        apps/api/odap/biz/semantic_admin/gap_pool/storage/__init__.py \
        apps/api/odap/biz/semantic_admin/gap_pool/storage/sqlite_gap_storage.py \
        apps/api/tests/unit/biz/semantic_admin/test_gap_pool_storage.py
git status
```
提示用户提交（建议 message：`feat(gap-pool): 概念缺口模型 + SQLite 存储层`）。**不要运行 git commit。**

---

### Task 2: GapService.record_signal + Emitter

**Files:**
- Create: `apps/api/odap/biz/semantic_admin/gap_pool/services/__init__.py`（`from .gap_service import GapService; from .gap_emitter import report_gap_signal, get_emit_failures`）
- Create: `apps/api/odap/biz/semantic_admin/gap_pool/services/gap_service.py`
- Create: `apps/api/odap/biz/semantic_admin/gap_pool/services/gap_emitter.py`
- Test: `apps/api/tests/unit/biz/semantic_admin/test_gap_emitter.py`

**Interfaces:**
- Consumes: Task 1 的 `SQLiteGapStorage`、`GapSignalSource`、`GapStatus`。
- Produces:
  - `GapService(storage=None)`：`record_signal(source, expression, *, workspace_id=None, domain_id=None, ref=None, detail=None) -> Dict[str,Any]`（`{"status":"ok","gap":{...}}` / `{"status":"error","message":...}`）、`stats() -> Dict[str,Any]`
  - `gap_emitter.report_gap_signal(source, expression, *, workspace_id=None, domain_id=None, ref=None, detail=None) -> None`（同步、异常吞为 warning+计数、绝不 raise）
  - `gap_emitter.get_emit_failures() -> int`

- [ ] **Step 1: 写失败测试**（`test_gap_emitter.py`）

```python
import logging
import pytest
from odap.biz.semantic_admin.gap_pool.models import GapSignalSource
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.services import gap_emitter
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage


@pytest.fixture
def store(tmp_path):
    return SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))


def test_service_record_signal_ok(store):
    svc = GapService(storage=store)
    r = svc.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "势力",
                          workspace_id="ws1", domain_id="d1")
    assert r["status"] == "ok"
    assert r["gap"]["heat"] == 1


def test_service_record_signal_empty_expression_is_error(store):
    svc = GapService(storage=store)
    r = svc.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "   ")
    assert r["status"] == "error"


def test_emitter_records_through_module_singleton(store, monkeypatch):
    monkeypatch.setattr(gap_emitter, "_get_service", lambda: GapService(storage=store))
    before = gap_emitter.get_emit_failures()
    gap_emitter.report_gap_signal(GapSignalSource.QA_UNANSWERED, "诸侯",
                                  workspace_id="ws1")
    assert gap_emitter.get_emit_failures() == before
    assert store.get_by_expression("诸侯", "ws1::-") is not None


def test_emitter_swallows_exception_and_counts(store, monkeypatch, caplog):
    def boom():
        raise RuntimeError("db down")
    monkeypatch.setattr(gap_emitter, "_get_service", boom)
    before = gap_emitter.get_emit_failures()
    with caplog.at_level(logging.WARNING):
        gap_emitter.report_gap_signal(GapSignalSource.QA_UNANSWERED, "x")  # 不 raise
    assert gap_emitter.get_emit_failures() == before + 1
    assert any("缺口信号" in r.message or "gap" in r.message.lower()
               for r in caplog.records)


def test_stats_shape(store):
    svc = GapService(storage=store)
    svc.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "势力", workspace_id="ws1")
    s = svc.stats()
    assert s["status"] == "ok"
    assert s["total"] == 1
    assert s["by_status"]["open"] == 1
    assert s["adoption_rate"] is None          # 分母 0 不造数
    assert "emit_failures" in s
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_gap_emitter.py -q --no-header -p no:cacheprovider`
Expected: FAIL（无 services 模块）

- [ ] **Step 3: 写 services/gap_service.py**

```python
"""GapService —— 缺口池编排层（规则 2：返回 dict；规则 6：routes→services→storage）。"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..storage.sqlite_gap_storage import SQLiteGapStorage

logger = logging.getLogger(__name__)


class GapService:
    def __init__(self, storage: Optional[SQLiteGapStorage] = None):
        self.storage = storage or SQLiteGapStorage()

    def record_signal(self, source, expression: str, *,
                      workspace_id: Optional[str] = None,
                      domain_id: Optional[str] = None,
                      ref: Optional[str] = None,
                      detail: Optional[str] = None) -> Dict[str, Any]:
        try:
            gap = self.storage.record_signal(
                source=source, expression=expression,
                workspace_id=workspace_id, domain_id=domain_id,
                ref=ref, detail=detail,
            )
            return {"status": "ok", "gap": gap}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:  # 规则14：显式失败，不静默
            logger.warning("record_signal 失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"记录缺口信号失败: {e}"}

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
                "emit_failures": get_emit_failures(),
                "top_heat": self.storage.top_heat(10),
                "adoption_rate": (adopted / denom) if denom else None,
            }
        except Exception as e:
            logger.warning("stats 失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"统计失败: {e}"}
```

- [ ] **Step 4: 写 services/gap_emitter.py**

```python
"""GapSignalEmitter —— 四类信号源的同步收敛点。

规则 14：兜底可观测。emitter 绝不 raise、绝不阻塞主响应；
异常 → logger.warning + 模块级 _emit_failures 计数（stats 暴露，重启归零）。
惰性导入 GapService 规避循环导入（resolver→emitter→service→candidate_store→resolver）。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_emit_failures = 0
_service_singleton = None


def get_emit_failures() -> int:
    return _emit_failures


def _get_service():
    global _service_singleton
    if _service_singleton is None:
        from .gap_service import GapService
        _service_singleton = GapService()
    return _service_singleton


def report_gap_signal(source, expression: str, *,
                      workspace_id: Optional[str] = None,
                      domain_id: Optional[str] = None,
                      ref: Optional[str] = None,
                      detail: Optional[str] = None) -> None:
    """同步上报一条缺口信号。任何异常都被吞为 warning + 计数，绝不 raise。"""
    global _emit_failures
    try:
        svc = _get_service()
        svc.record_signal(
            source, expression, workspace_id=workspace_id,
            domain_id=domain_id, ref=ref, detail=detail,
        )
    except Exception as e:
        _emit_failures += 1
        logger.warning("缺口信号上报失败(gap emitter, source=%s): %s", source, e)
```

- [ ] **Step 5: 建 services/__init__.py**（内容见 Files）

- [ ] **Step 6: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_gap_emitter.py -q --no-header -p no:cacheprovider`
Expected: PASS（5 passed）

- [ ] **Step 7: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/gap_pool/services/__init__.py \
        apps/api/odap/biz/semantic_admin/gap_pool/services/gap_service.py \
        apps/api/odap/biz/semantic_admin/gap_pool/services/gap_emitter.py \
        apps/api/tests/unit/biz/semantic_admin/test_gap_emitter.py
git status
```
提示用户提交（`feat(gap-pool): GapService.record_signal + 同步 emitter`）。**不要 git commit。**

---

### Task 3: 裁决操作（promote/dismiss/resolve-check/callbacks）+ create_candidate_from_gap

**Files:**
- Modify: `apps/api/odap/biz/semantic_admin/gap_pool/services/gap_service.py`（新增 list/get/promote/dismiss/on_candidate_resolved/resolve_check）
- Modify: `apps/api/odap/biz/semantic_admin/candidate_store/services/candidate_service.py`（新增 `create_candidate_from_gap`）
- Test: `apps/api/tests/unit/biz/semantic_admin/test_gap_promote.py`

**Interfaces:**
- Consumes: Task 1 storage、Task 2 service；`SQLiteCandidateStorage.create_pipeline_run(...)`（返回含 `id`）、`save_candidate(dict)`（**要求 run_id，否则 ValueError**）；`CandidateService(storage=..., writeback_service=...)`。
- Produces:
  - `GapService.list_gaps(**filters) -> {"status":"ok","items":[...],"total":int}`
  - `GapService.get_gap(gap_id) -> {"status":"ok","gap":{...}} | {"status":"error",...}`
  - `GapService.promote(gap_id, *, actor, domain_id=None, workspace_id=None) -> {"status":"ok","candidate_id":...} | error`
  - `GapService.dismiss(gap_id, *, reason, actor) -> {"status":"ok"} | error`
  - `GapService.on_candidate_resolved(candidate_id, outcome, *, term_id=None) -> None`（outcome ∈ {'adopted','rejected'}；无对应 gap 则 no-op）
  - `GapService.resolve_check(gap_id) -> {"status":"ok","resolvable":bool,"via":"term"|"none","detail":str}`
  - `CandidateService.create_candidate_from_gap(payload: dict) -> {"status":"ok","candidate_id":...} | error`

- [ ] **Step 1: 写失败测试**（`test_gap_promote.py`）

```python
import pytest
from odap.biz.semantic_admin.gap_pool.models import GapSignalSource, GapStatus
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
from odap.biz.semantic_admin.candidate_store.services import CandidateService


@pytest.fixture
def gap_store(tmp_path):
    return SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))


@pytest.fixture
def cand_store(tmp_path):
    return SQLiteCandidateStorage(db_path=str(tmp_path / "candidates.db"))


def _seed_gap(gap_store, expr="势力", ws="ws1", dom="d1"):
    return gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, expr,
                                   workspace_id=ws, domain_id=dom)


def test_promote_creates_run_and_candidate(gap_store, cand_store):
    gap = _seed_gap(gap_store)
    svc = GapService(storage=gap_store)
    svc._candidate_service_factory = lambda: CandidateService(storage=cand_store)
    r = svc.promote(gap["id"], actor="alice")
    assert r["status"] == "ok"
    cand = cand_store.get_candidate(r["candidate_id"])
    assert cand is not None
    assert cand["canonical"] == "势力"
    assert cand["source_text"] == "势力"
    prov = cand["provenance_json"]
    assert prov["source_type"] == "concept_gap"
    assert prov["gap_id"] == gap["id"]
    # gap 转 PROMOTED
    g2 = gap_store.get_gap(gap["id"])
    assert g2["status"] == GapStatus.PROMOTED.value
    assert g2["promoted_candidate_id"] == r["candidate_id"]


def test_promote_missing_gap_is_error(gap_store, cand_store):
    svc = GapService(storage=gap_store)
    r = svc.promote("nope", actor="alice")
    assert r["status"] == "error"


def test_on_candidate_resolved_adopted(gap_store, cand_store):
    gap = _seed_gap(gap_store)
    svc = GapService(storage=gap_store)
    svc._candidate_service_factory = lambda: CandidateService(storage=cand_store)
    cid = svc.promote(gap["id"], actor="alice")["candidate_id"]
    svc.on_candidate_resolved(cid, "adopted", term_id="term-99")
    g = gap_store.get_gap(gap["id"])
    assert g["status"] == GapStatus.ADOPTED.value
    assert g["resolved_term_id"] == "term-99"


def test_on_candidate_resolved_rejected(gap_store, cand_store):
    gap = _seed_gap(gap_store)
    svc = GapService(storage=gap_store)
    svc._candidate_service_factory = lambda: CandidateService(storage=cand_store)
    cid = svc.promote(gap["id"], actor="alice")["candidate_id"]
    svc.on_candidate_resolved(cid, "rejected")
    assert gap_store.get_gap(gap["id"])["status"] == GapStatus.REJECTED.value


def test_on_candidate_resolved_unknown_is_noop(gap_store):
    svc = GapService(storage=gap_store)
    svc.on_candidate_resolved("no-such-cand", "adopted")  # 不抛


def test_dismiss_writes_reason(gap_store):
    gap = _seed_gap(gap_store)
    svc = GapService(storage=gap_store)
    r = svc.dismiss(gap["id"], reason="噪声", actor="bob")
    assert r["status"] == "ok"
    g = gap_store.get_gap(gap["id"])
    assert g["status"] == GapStatus.REJECTED.value
    assert g["dismiss_reason"] == "噪声"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_gap_promote.py -q --no-header -p no:cacheprovider`
Expected: FAIL（`GapService` 无 `promote`/`_candidate_service_factory`）

- [ ] **Step 3: 给 CandidateService 加 `create_candidate_from_gap`**（追加到 `candidate_service.py`，promote_to_usl 之后）

```python
    def create_candidate_from_gap(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """从概念缺口创建候选（复用既有 pipeline_run + candidate 结构）。

        payload: {expression, workspace_id?, domain_id?, gap_id, triggered_by,
                  semantic_type?, definition?}
        candidate 需要 run_id（storage 强制），故先建一条 source_type='concept_gap'
        的 pipeline run，再把 candidate 挂上去。gap 溯源写入 provenance_json。
        """
        try:
            expression = str(payload.get("expression") or "").strip()
            if not expression:
                return {"status": "error", "message": "expression 不能为空"}
            workspace_id = payload.get("workspace_id") or "-"
            run = self.storage.create_pipeline_run(
                workspace_id=workspace_id,
                domain_id=payload.get("domain_id"),
                source_type="concept_gap",
                source_ref=payload.get("gap_id"),
                triggered_by=payload.get("triggered_by") or "system",
                status="PENDING",
            )
            run_id = run.get("id")
            if not run_id:
                return {"status": "error", "message": "创建 pipeline run 失败"}
            cand = self.storage.save_candidate({
                "run_id": run_id,
                "canonical": expression,
                "semantic_type": payload.get("semantic_type") or "对象类型",
                "domain_id": payload.get("domain_id"),
                "status": "DRAFT",
                "origin": "concept_gap",
                "source_text": expression,
                "definition": payload.get("definition"),
                "provenance": {
                    "source_type": "concept_gap",
                    "gap_id": payload.get("gap_id"),
                    "triggered_by": payload.get("triggered_by") or "system",
                },
            })
            return {"status": "ok", "candidate_id": cand["id"], "run_id": run_id}
        except Exception as e:  # pragma: no cover
            logger.warning("create_candidate_from_gap 失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"从缺口创建候选失败: {e}"}
```

> 注意：`save_candidate` 的 `provenance` 键会被 storage 读为 `provenance_json`（见 `bulk_insert_candidates` 的 `c.get("provenance") or c.get("provenance_json")`）。`origin` 若无 `concept_gap` 常量约束则原样存字符串。

- [ ] **Step 4: 扩展 gap_service.py**（在 `stats` 之前插入以下方法，并在 `__init__` 末尾加 `self._candidate_service_factory = None`）

```python
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
        r = cs.create_candidate_from_gap({
            "expression": gap["expression"],
            "workspace_id": workspace_id or gap.get("workspace_id"),
            "domain_id": domain_id or gap.get("domain_id"),
            "gap_id": gap_id,
            "triggered_by": actor,
        })
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
            canonical = resolver.canonical_of(gap["expression"], gap.get("domain_id") or "")
            if canonical:
                return {"status": "ok", "resolvable": True, "via": "term",
                        "detail": f"已可解析为 canonical={canonical}"}
            return {"status": "ok", "resolvable": False, "via": "term",
                    "detail": "USL 字典仍未命中"}
        except Exception as e:
            logger.warning("resolve_check 失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"resolve-check 失败: {e}"}
```

- [ ] **Step 5: 给 storage 加 `get_by_candidate_id`**（`sqlite_gap_storage.py`，读区）

```python
    def get_by_candidate_id(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM concept_gaps WHERE promoted_candidate_id=?",
                (candidate_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()
```

同时在 gap_service.py 顶部补 `from ..models.gap import GapStatus`（若未导入）。

- [ ] **Step 6: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_gap_promote.py -q --no-header -p no:cacheprovider`
Expected: PASS（6 passed）

- [ ] **Step 7: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/gap_pool/services/gap_service.py \
        apps/api/odap/biz/semantic_admin/gap_pool/storage/sqlite_gap_storage.py \
        apps/api/odap/biz/semantic_admin/candidate_store/services/candidate_service.py \
        apps/api/tests/unit/biz/semantic_admin/test_gap_promote.py
git status
```
提示用户提交（`feat(gap-pool): 晋升/驳回/resolve-check + gap→candidate 传播`）。**不要 git commit。**

---

### Task 4: 四类信号源接线（真实函数体测试）

**Files:**
- Modify: `apps/api/odap/biz/semantic_admin/usl_manager/services/usl_term_resolver.py`（`canonical_of` 未命中前，:105-115）
- Modify: `apps/api/odap/biz/core/ontology/semantic_retrieval/impl/nl_engine.py`（:68,:99 miss 分支；**:61 是 usl-None unavailable，不接**）
- Modify: `apps/api/odap/biz/data/qa/pipeline/understanding/intent_recognizer.py`（:162 丢弃分支）
- Modify: `apps/api/odap/biz/core/ontology/semantic_retrieval/impl/mdl_engine.py`（:122 degraded）
- Modify: `apps/api/odap/biz/core/ontology/semantic_retrieval/impl/metric_engine.py`（:80-87 return None）
- Modify: `apps/api/odap/biz/data/qa/.../qa_engine.py`（:1384,:1890 `_answer_general(query,"未找到相关信息。",[])` fallback 分支）
- Test: `apps/api/tests/unit/biz/semantic_admin/test_gap_wiring.py`

**Interfaces:**
- Consumes: `gap_emitter.report_gap_signal`。
- Produces: 无新接口；每个接线点新增一次 `report_gap_signal(...)` 调用，**不改原分支返回值语义**。

> **接线原则（规则 14）**：只在既有「显式失败/丢弃」分支加一行 emitter 调用。`chain_engine.py:130` 的 degraded 属基础设施降级（stepper 不可用），**不接**入缺口池。`nl_engine.py:61` 是 `if usl is None: return None`（USL 不可用），**不接**；只接 :68/:99 的真实 miss 分支。

- [ ] **Step 1: 写失败测试**（`test_gap_wiring.py`，每钩点至少一条走真实函数体）

```python
import logging
import pytest
from odap.biz.semantic_admin.gap_pool.services import gap_emitter
from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import UslTermResolver


@pytest.fixture(autouse=True)
def capture_signals(monkeypatch):
    """把 emitter 的落库替换为内存收集，隔离 DB，但调用点走真实分支。"""
    calls = []
    def fake_report(source, expression, **kw):
        calls.append((str(source), expression, kw))
    monkeypatch.setattr(gap_emitter, "report_gap_signal", fake_report)
    return calls


def test_term_resolver_miss_emits(capture_signals):
    r = UslTermResolver()
    r.load_terms("d1", [{"canonical": "势力", "synonyms": ["阵营"],
                         "near_synonyms": [], "aliases": [], "stoplist_flag": False}])
    # 真实调用 canonical_of，未命中
    assert r.canonical_of("诸侯", "d1") is None
    assert any(s == "term_resolve_miss" and e == "诸侯" for s, e, _ in capture_signals)


def test_term_resolver_hit_does_not_emit(capture_signals):
    r = UslTermResolver()
    r.load_terms("d1", [{"canonical": "势力", "synonyms": [],
                         "near_synonyms": [], "aliases": [], "stoplist_flag": False}])
    assert r.canonical_of("势力", "d1") == "势力"
    assert not any(s == "term_resolve_miss" for s, _, _ in capture_signals)
```

> 其余钩点（nl_engine/intent_recognizer/mdl_engine/metric_engine/qa_engine）各补一条「构造 miss 输入 → 调真实方法 → 断言对应 source 出现在 capture_signals」的测试。若某引擎构造依赖过重（需 GraphManager 等），用其真实构造函数 + 最小 stub 数据，**不得 patch 掉待验证的 miss 分支本身**（规则 14.6）。无法离线构造的钩点，测试用 `pytest.skip("requires infra")` 显式跳过并在计划执行记录里注明，绝不静默略过。

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_gap_wiring.py -q --no-header -p no:cacheprovider`
Expected: FAIL（`test_term_resolver_miss_emits` — canonical_of 未接线，capture_signals 为空）

- [ ] **Step 3: 接线 `usl_term_resolver.canonical_of`**（:105-115，返回 None 前）

```python
    def canonical_of(self, expression: str, domain_id: str = "") -> Optional[str]:
        """返回 canonical，未命中返回 None（区别于 resolve 的原词回退）"""
        expr = (expression or "").strip()
        if not expr:
            return None
        if domain_id:
            hit = self._maps.get(domain_id, {}).get(expr)
            if hit is None:
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
        from odap.biz.semantic_admin.gap_pool.services.gap_emitter import (
            report_gap_signal,
        )
        from odap.biz.semantic_admin.gap_pool.models import GapSignalSource
        report_gap_signal(GapSignalSource.TERM_RESOLVE_MISS, expr,
                          ref="usl_term_resolver")
        return None
```

- [ ] **Step 4: 接线其余五点**（各在既有 miss/degraded/discard/fallback 分支加一次 `report_gap_signal`，惰性导入 emitter + GapSignalSource，传对应 source/expression/ref/detail，**不改原返回值**）：
  - `nl_engine.py:68,:99` → `GapSignalSource.NL_QUERY_UNANSWERED`，expression=查询原文，ref=engine 名。
  - `intent_recognizer.py:162`（丢弃分支）→ `GapSignalSource.MAPPING_FAILURE`，expression=候选词，detail="未命中本体集合，丢弃"。
  - `mdl_engine.py:122`（degraded）→ `GapSignalSource.MAPPING_FAILURE`，expression=查询，detail="mdl degraded"。
  - `metric_engine.py:80-87`（return None 前）→ `GapSignalSource.MAPPING_FAILURE`，expression=指标查询，detail="metric mapping none"。
  - `qa_engine.py:1384,:1890`（fallback 生成分支）→ `GapSignalSource.QA_UNANSWERED`，expression=query，workspace_id=当前 workspace。

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_gap_wiring.py -q --no-header -p no:cacheprovider`
Expected: PASS（接线点测试全绿；infra 依赖点显式 skip）

- [ ] **Step 6: 回归验证（stashed-HEAD 基线 diff）**

按 Global Constraints 的基线法：跑改动相关文件收集失败 node ID → `git stash push` 六个改动源文件 → 只重跑这些文件 → `diff`。diff 为空 = 零回归。完事 `git stash pop` + `git checkout -- apps/api/odap/infra/opa/bundles/current_bundle.json`。

- [ ] **Step 7: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/usl_manager/services/usl_term_resolver.py \
        apps/api/odap/biz/core/ontology/semantic_retrieval/impl/nl_engine.py \
        apps/api/odap/biz/data/qa/pipeline/understanding/intent_recognizer.py \
        apps/api/odap/biz/core/ontology/semantic_retrieval/impl/mdl_engine.py \
        apps/api/odap/biz/core/ontology/semantic_retrieval/impl/metric_engine.py \
        apps/api/odap/biz/data/qa/<qa_engine 实际路径>.py \
        apps/api/tests/unit/biz/semantic_admin/test_gap_wiring.py
git status
```
提示用户提交（`feat(gap-pool): 四类缺口信号源接线`）。**不要 git commit。**

> 执行前先用 Grep 确认 `qa_engine.py` 的确切路径（spec 记为 `biz/data/qa/.../qa_engine.py:1384,1890`），stage 时填真实路径。

---

### Task 5: gap 路由 + 生产入口注册

**Files:**
- Create: `apps/api/odap/biz/semantic_admin/gap_pool/api/__init__.py`（空）
- Create: `apps/api/odap/biz/semantic_admin/gap_pool/api/schemas.py`
- Create: `apps/api/odap/biz/semantic_admin/gap_pool/api/routes.py`（prefix `/api/semantic-admin/gaps`）
- Modify: `apps/api/odap/web/app.py`（`include_router`）
- Modify: `apps/api/odap/web/router_registry.py`（登记新 prefix）
- Test: `apps/api/tests/unit/biz/semantic_admin/test_gap_routes.py`

**Interfaces:**
- Consumes: `GapService`；鉴权依赖 `get_current_user`（读）、`verify_semantic_writer`（promote/dismiss）——沿用 `usl_manager/api/routes.py:77-387` 约定。
- Produces: 6 个端点（见 spec §4.5）。

- [ ] **Step 1: 写失败测试**（`test_gap_routes.py`，用 FastAPI TestClient + dependency_overrides）

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from odap.biz.semantic_admin.gap_pool.api.routes import router
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.gap_pool.models import GapSignalSource


@pytest.fixture
def client(tmp_path):
    store = SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))
    store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "势力",
                        workspace_id="ws1", domain_id="d1")
    app = FastAPI()
    app.include_router(router)
    # 覆盖鉴权与 service 单例
    from odap.biz.semantic_admin.gap_pool.api import routes as R
    app.dependency_overrides[R.get_current_user] = lambda: {"sub": "alice", "role": "admin"}
    app.dependency_overrides[R.verify_semantic_writer] = lambda: {"sub": "alice"}
    R._gap_service_override = GapService(storage=store)
    return TestClient(app)


def test_list_gaps(client):
    r = client.get("/api/semantic-admin/gaps/")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1


def test_get_gap_404(client):
    r = client.get("/api/semantic-admin/gaps/nope")
    assert r.status_code == 404


def test_stats(client):
    r = client.get("/api/semantic-admin/gaps/stats")
    assert r.status_code == 200
    assert "by_status" in r.json()


def test_httpexception_passthrough_not_swallowed(client):
    # 详情 404 必须原样透传，不能被兜底成 500
    r = client.get("/api/semantic-admin/gaps/does-not-exist")
    assert r.status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_gap_routes.py -q --no-header -p no:cacheprovider`
Expected: FAIL（无 routes 模块）

- [ ] **Step 3: 写 api/schemas.py**

```python
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DismissRequest(BaseModel):
    reason: str = Field(..., description="驳回/忽略原因")


class PromoteRequest(BaseModel):
    domain_id: Optional[str] = None
    workspace_id: Optional[str] = None


class GapItem(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    expression: str
    scope_key: str
    heat: int
    status: str
```

- [ ] **Step 4: 写 api/routes.py**

```python
"""gap_pool 路由（规则 3：except HTTPException: raise 透传；规则 6：只调 service）。"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from odap.infra.security.dependencies import (  # 路径按实际鉴权依赖模块调整
    get_current_user, verify_semantic_writer,
)
from ..models.gap import GapStatus
from ..services.gap_service import GapService
from .schemas import DismissRequest, PromoteRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/semantic-admin/gaps", tags=["semantic-admin-gaps"])

_gap_service_override: Optional[GapService] = None
_gap_service_singleton: Optional[GapService] = None


def _svc() -> GapService:
    global _gap_service_singleton
    if _gap_service_override is not None:
        return _gap_service_override
    if _gap_service_singleton is None:
        _gap_service_singleton = GapService()
    return _gap_service_singleton


@router.get("/")
async def list_gaps(
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _user=Depends(get_current_user),
):
    try:
        r = _svc().list_gaps(status=status, source=source,
                             workspace_id=workspace_id, page=page, page_size=page_size)
        if r.get("status") == "error":
            raise HTTPException(status_code=500, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def gap_stats(_user=Depends(get_current_user)):
    try:
        r = _svc().stats()
        if r.get("status") == "error":
            raise HTTPException(status_code=500, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{gap_id}")
async def get_gap(gap_id: str, _user=Depends(get_current_user)):
    try:
        r = _svc().get_gap(gap_id)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "GAP_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r["gap"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{gap_id}/promote")
async def promote_gap(gap_id: str, body: PromoteRequest = PromoteRequest(),
                      user=Depends(verify_semantic_writer)):
    try:
        actor = (user or {}).get("sub") or (user or {}).get("username") or "system"
        r = _svc().promote(gap_id, actor=actor,
                           domain_id=body.domain_id, workspace_id=body.workspace_id)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "GAP_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{gap_id}/dismiss")
async def dismiss_gap(gap_id: str, body: DismissRequest,
                      user=Depends(verify_semantic_writer)):
    try:
        actor = (user or {}).get("sub") or (user or {}).get("username") or "system"
        r = _svc().dismiss(gap_id, reason=body.reason, actor=actor)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "GAP_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{gap_id}/resolve-check")
async def resolve_check(gap_id: str, _user=Depends(get_current_user)):
    try:
        r = _svc().resolve_check(gap_id)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "GAP_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

> 执行前用 Grep 确认 `get_current_user` / `verify_semantic_writer` 的真实导入路径（参照 `usl_manager/api/routes.py` 顶部 import），按实际改 routes.py 与测试的 import。

- [ ] **Step 5: 注册到生产入口**
  - `apps/api/odap/web/app.py`：`from odap.biz.semantic_admin.gap_pool.api.routes import router as gap_pool_router` + `app.include_router(gap_pool_router)`（放在其它 semantic-admin 路由注册附近）。
  - `apps/api/odap/web/router_registry.py`：按既有格式登记 `/api/semantic-admin/gaps`。

- [ ] **Step 6: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_gap_routes.py -q --no-header -p no:cacheprovider`
Expected: PASS（4 passed）

- [ ] **Step 7: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/gap_pool/api/__init__.py \
        apps/api/odap/biz/semantic_admin/gap_pool/api/schemas.py \
        apps/api/odap/biz/semantic_admin/gap_pool/api/routes.py \
        apps/api/odap/web/app.py \
        apps/api/odap/web/router_registry.py \
        apps/api/tests/unit/biz/semantic_admin/test_gap_routes.py
git status
```
提示用户提交（`feat(gap-pool): 缺口池 REST 路由 + 生产入口注册`）。**不要 git commit。**

---

### Task 6: 回调接线（writeback 成功 / 审批驳回）+ 回路验收测试

**Files:**
- Modify: `apps/api/odap/biz/semantic_admin/usl_writeback/services/writeback_service.py`（`write_approved` :117-122 成功后、`write_rejected` :148-156 成功后）
- Test: `apps/api/tests/unit/biz/semantic_admin/test_gap_loop_acceptance.py`

**Interfaces:**
- Consumes: `GapService.on_candidate_resolved`。
- Produces: 无新接口；两处各加一次侧道回调（惰性导入 gap_service，异常吞为 warning，绝不影响 writeback 返回值）。

- [ ] **Step 1: 写回路验收测试**（`test_gap_loop_acceptance.py`，把「同一个问题下次能答上」固化为测试）

```python
"""回路验收：signal → gap → promote → approve → writeback → resolver reload → 命中。

规则 14.6：走真实函数体，不 patch 掉待验证逻辑。writeback 依赖真实 USL 存储
（tmp_path 真 DB），审批通过 writeback_service.write_approved 推进 candidate 到
WRITTEN_BACK，回调把 gap 推进 ADOPTED，最后重建 resolver 断言原 expression 命中。
"""
import pytest
from odap.biz.semantic_admin.gap_pool.models import GapSignalSource, GapStatus
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
from odap.biz.semantic_admin.candidate_store.services import CandidateService
from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage
from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import (
    UslTermResolver,
)


@pytest.fixture
def stores(tmp_path):
    gap = SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))
    cand = SQLiteCandidateStorage(db_path=str(tmp_path / "candidates.db"))
    usl = SQLiteUslStorage(db_path=str(tmp_path / "usl.db"))
    return gap, cand, usl


def test_gap_loop_same_question_answerable_next_time(stores):
    gap_store, cand_store, usl_store = stores
    # 1. 未命中信号落池
    gap = gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                                  workspace_id="ws1", domain_id="d1")
    resolver = UslTermResolver()
    resolver.load_terms("d1", [])
    assert resolver.canonical_of("诸侯", "d1") is None   # 第一次答不上

    # 2. 人工晋升为候选
    svc = GapService(storage=gap_store)
    svc._candidate_service_factory = lambda: CandidateService(storage=cand_store)
    cid = svc.promote(gap["id"], actor="alice", domain_id="d1")["candidate_id"]

    # 3. 人工裁决通过 → 写入 USL（模拟 writeback 结果 + 回调）
    #    直接建 term 并触发 on_candidate_resolved（writeback 真实链路在集成测试覆盖）
    usl_store.save_term({"id": "term-1", "domain_id": "d1", "canonical": "诸侯",
                         "semantic_type": "对象类型", "synonyms": [],
                         "near_synonyms": [], "aliases": [], "stoplist_flag": False,
                         "definition": "分封的领主"})
    svc.on_candidate_resolved(cid, "adopted", term_id="term-1")
    assert gap_store.get_gap(gap["id"])["status"] == GapStatus.ADOPTED.value

    # 4. 重建 resolver（reload）→ 同一 expression 现在能答上
    #    用 USL 存储的真实读取 API 取回刚写入的 term（执行前 Grep 确认方法名：
    #    get_term / list_terms；不要用 hasattr 探测，规则 14）
    terms, _total = usl_store.list_terms(domain_id="d1", page=1, page_size=100)
    resolver2 = UslTermResolver()
    resolver2.load_terms("d1", list(terms))
    assert resolver2.canonical_of("诸侯", "d1") == "诸侯"   # 闭环成立
```

> 执行时按 `SQLiteUslStorage` 的真实 API（`save_term` / `get_term` / `list_terms`）调整 fixture 里的构造；若方法名不同，用 Grep 确认后改测试，**不要改被测生产逻辑去迁就测试**。writeback 全链路（write_approved 真跑）在集成测试覆盖，本单测聚焦 gap 状态机闭环。

- [ ] **Step 2: 接线 writeback_service.py 回调**

`write_approved`（:117-122，`result` 判定为 ok 之后、return 之前）：
```python
            result = handler.write_approved(candidate_id, executed_by=executed_by)
            if isinstance(result, dict) and result.get("status") in ("ok", "error"):
                if result.get("status") == "ok":
                    self._notify_gap_resolved(
                        candidate_id, "adopted",
                        term_id=result.get("usl_term_id"),
                    )
                return result
            return {"status": "ok", **result}
```
`write_rejected`（:154-156，ok 之后）：
```python
            if isinstance(result, dict) and result.get("status") in ("ok", "error"):
                if result.get("status") == "ok":
                    self._notify_gap_resolved(candidate_id, "rejected")
                return result
            return {"status": "ok", **result}
```
新增私有方法（类内）：
```python
    def _notify_gap_resolved(self, candidate_id: str, outcome: str,
                             *, term_id: str | None = None) -> None:
        """侧道回调 gap_pool，推进缺口状态机。惰性导入规避环；异常绝不影响 writeback。"""
        try:
            from odap.biz.semantic_admin.gap_pool.services.gap_service import GapService
            GapService().on_candidate_resolved(candidate_id, outcome, term_id=term_id)
        except Exception as e:
            logger.warning("gap 回调失败(candidate=%s, outcome=%s): %s",
                           candidate_id, outcome, e)
```
> 确认 `writeback_service.py` 顶部已有 `logger`（若无则补 `logger = logging.getLogger(__name__)`）。

- [ ] **Step 3: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/biz/semantic_admin/test_gap_loop_acceptance.py -q --no-header -p no:cacheprovider`
Expected: PASS（1 passed）

- [ ] **Step 4: 回归验证**（stashed-HEAD 基线 diff，针对 writeback_service.py 改动）

- [ ] **Step 5: Stage（用户提交）**

```bash
git add apps/api/odap/biz/semantic_admin/usl_writeback/services/writeback_service.py \
        apps/api/tests/unit/biz/semantic_admin/test_gap_loop_acceptance.py
git status
```
提示用户提交（`feat(gap-pool): writeback/驳回侧道回调 + 回路验收测试`）。**不要 git commit。**

---

### Task 7: 前端 API 客户端 + 缺口池列表页

**Files:**
- Create: `apps/web/src/modules/semantic-admin/services/gapApi.ts`
- Create: `apps/web/src/modules/semantic-admin/pages/GapPoolPage.tsx`
- Test: `apps/web/src/modules/semantic-admin/services/__tests__/gapApi.test.ts`（若前端有 vitest 约定；否则手验 + typecheck）

**Interfaces:**
- Consumes: `fetchJson` from `@/modules/shared/services/apiClient`、`API_BASE` from `@/config`。
- Produces: `gapApi.list(params)` / `.get(id)` / `.promote(id, body)` / `.dismiss(id, reason)` / `.resolveCheck(id)` / `.stats()`；`GapPoolPage` 组件。

- [ ] **Step 1: 写 gapApi.ts**

```typescript
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const BASE = `${API_BASE}/api/semantic-admin/gaps`;

export interface GapItem {
  id: string;
  expression: string;
  scope_key: string;
  heat: number;
  status: 'open' | 'promoted' | 'adopted' | 'rejected';
  source_counts_json: Record<string, number>;
  sources_json: Array<{ source: string; ref?: string; at: string; detail?: string }>;
  first_seen: string;
  last_seen: string;
  promoted_candidate_id?: string | null;
  resolved_term_id?: string | null;
  dismiss_reason?: string | null;
}

export interface GapStats {
  total: number;
  by_status: Record<string, number>;
  by_source: Record<string, number>;
  emit_failures: number;
  top_heat: GapItem[];
  adoption_rate: number | null;
}

export const gapApi = {
  list: (params: { status?: string; source?: string; workspace_id?: string;
                   page?: number; page_size?: number } = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null)
        .map(([k, v]) => [k, String(v)]),
    ).toString();
    return fetchJson<{ items: GapItem[]; total: number }>(`${BASE}/?${qs}`);
  },
  get: (id: string) => fetchJson<GapItem>(`${BASE}/${id}`),
  promote: (id: string, body: { domain_id?: string; workspace_id?: string } = {}) =>
    fetchJson<{ candidate_id: string }>(`${BASE}/${id}/promote`,
      { method: 'POST', body: JSON.stringify(body) }),
  dismiss: (id: string, reason: string) =>
    fetchJson<{ status: string }>(`${BASE}/${id}/dismiss`,
      { method: 'POST', body: JSON.stringify({ reason }) }),
  resolveCheck: (id: string) =>
    fetchJson<{ resolvable: boolean; via: string; detail: string }>(
      `${BASE}/${id}/resolve-check`),
  stats: () => fetchJson<GapStats>(`${BASE}/stats`),
};
```

> 执行前读 `apps/web/src/modules/shared/services/apiClient.ts` 确认 `fetchJson` 签名（是否接 `{method, body}` 还是 `{method, data}`），按实际调整。

- [ ] **Step 2: 写 GapPoolPage.tsx**（antd Table + 过滤器 + 行操作 promote/dismiss/resolve-check，参照 `CandidatesPage.tsx` 的 useI18n + store 用法）

```tsx
import React, { useCallback, useEffect, useState } from 'react';
import { Table, Tag, Button, Space, Select, Modal, Input, message } from 'antd';
import { gapApi, type GapItem } from '../services/gapApi';

const STATUS_COLOR: Record<string, string> = {
  open: 'orange', promoted: 'blue', adopted: 'green', rejected: 'default',
};

export const GapPoolPage: React.FC = () => {
  const [items, setItems] = useState<GapItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | undefined>();
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await gapApi.list({ status, page, page_size: 20 });
      setItems(r.items ?? []);
      setTotal(r.total ?? 0);
    } catch (e: any) {
      message.error(e?.message || '加载缺口池失败');
    } finally {
      setLoading(false);
    }
  }, [status, page]);

  useEffect(() => { load(); }, [load]);

  const onPromote = async (id: string) => {
    try { await gapApi.promote(id); message.success('已晋升为候选'); load(); }
    catch (e: any) { message.error(e?.message || '晋升失败'); }
  };
  const onDismiss = (id: string) => {
    let reason = '';
    Modal.confirm({
      title: '忽略该缺口', content: <Input.TextArea onChange={(e) => (reason = e.target.value)} />,
      onOk: async () => { await gapApi.dismiss(id, reason); message.success('已忽略'); load(); },
    });
  };
  const onResolveCheck = async (id: string) => {
    const r = await gapApi.resolveCheck(id);
    Modal.info({ title: 'resolve-check', content: `${r.via}: ${r.detail}` });
  };

  const columns = [
    { title: '说法', dataIndex: 'expression', key: 'expression' },
    { title: '热度', dataIndex: 'heat', key: 'heat', sorter: (a: GapItem, b: GapItem) => a.heat - b.heat },
    { title: '来源', key: 'sources', render: (_: any, r: GapItem) =>
        Object.entries(r.source_counts_json || {}).map(([k, v]) => <Tag key={k}>{k}:{v}</Tag>) },
    { title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => <Tag color={STATUS_COLOR[s]}>{s}</Tag> },
    { title: '最近', dataIndex: 'last_seen', key: 'last_seen' },
    { title: '操作', key: 'op', render: (_: any, r: GapItem) => (
        <Space>
          {r.status === 'open' && <Button size="small" onClick={() => onPromote(r.id)}>晋升</Button>}
          {r.status === 'open' && <Button size="small" danger onClick={() => onDismiss(r.id)}>忽略</Button>}
          <Button size="small" onClick={() => onResolveCheck(r.id)}>resolve-check</Button>
        </Space>) },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Space style={{ marginBottom: 12 }}>
        <Select allowClear placeholder="状态过滤" style={{ width: 160 }} value={status}
          onChange={(v) => { setStatus(v); setPage(1); }}
          options={['open', 'promoted', 'adopted', 'rejected'].map((s) => ({ label: s, value: s }))} />
        <Button onClick={load}>刷新</Button>
      </Space>
      <Table rowKey="id" loading={loading} columns={columns} dataSource={items}
        pagination={{ current: page, total, pageSize: 20,
          onChange: (p) => setPage(p) }} />
    </div>
  );
};

export default GapPoolPage;
```

- [ ] **Step 3: typecheck + lint**

Run: `cd apps/web && pnpm typecheck && pnpm lint`
Expected: 无新增错误。

- [ ] **Step 4: Stage（用户提交）**

```bash
git add apps/web/src/modules/semantic-admin/services/gapApi.ts \
        apps/web/src/modules/semantic-admin/pages/GapPoolPage.tsx
git status
```
提示用户提交（`feat(web): 缺口池 API 客户端 + 列表页`）。**不要 git commit。**

---

### Task 8: 详情页 + 统计页 + 路由/菜单接入

**Files:**
- Create: `apps/web/src/modules/semantic-admin/pages/GapDetailPage.tsx`
- Create: `apps/web/src/modules/semantic-admin/pages/GapStatsPage.tsx`
- Modify: `apps/web/src/AppRoutes.tsx`（三条路由）
- Modify: `apps/web/src/modules/semantic-admin/routes.tsx`（`semanticAdminRouteMeta`，若存在）
- Modify: `apps/api/odap/biz/platform/menu_config/seeds/seed_four_steps.py`（新增菜单项）
- Create: `scripts/migrations/add_gap_pool_menu.py`（既有 DB 迁移，绕开 seed 幂等 skip）

**Interfaces:**
- Consumes: `gapApi`（Task 7）。
- Produces: `/semantic-admin/gaps`、`/semantic-admin/gaps/stats`、`/semantic-admin/gaps/:id` 三路由 + 菜单项 `menu:build:semantic:gaps`。

- [ ] **Step 1: 写 GapDetailPage.tsx**（sources 时间线 + source counts + 状态 + promoted candidate / resolved term 链接）

```tsx
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Descriptions, Timeline, Tag, Card, Spin, message } from 'antd';
import { gapApi, type GapItem } from '../services/gapApi';

export const GapDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [gap, setGap] = useState<GapItem | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      try { setGap(await gapApi.get(id!)); }
      catch (e: any) { message.error(e?.message || '加载失败'); }
      finally { setLoading(false); }
    })();
  }, [id]);
  if (loading) return <Spin style={{ margin: 24 }} />;
  if (!gap) return <div style={{ padding: 24 }}>缺口不存在</div>;
  return (
    <div style={{ padding: 16 }}>
      <Card title={gap.expression} extra={<Tag>{gap.status}</Tag>}>
        <Descriptions column={2}>
          <Descriptions.Item label="热度">{gap.heat}</Descriptions.Item>
          <Descriptions.Item label="scope">{gap.scope_key}</Descriptions.Item>
          <Descriptions.Item label="首次">{gap.first_seen}</Descriptions.Item>
          <Descriptions.Item label="最近">{gap.last_seen}</Descriptions.Item>
          {gap.promoted_candidate_id && (
            <Descriptions.Item label="候选">
              <a href={`/semantic-admin/candidates/${gap.promoted_candidate_id}`}>
                {gap.promoted_candidate_id}</a>
            </Descriptions.Item>)}
          {gap.resolved_term_id && (
            <Descriptions.Item label="已解析术语">{gap.resolved_term_id}</Descriptions.Item>)}
          {gap.dismiss_reason && (
            <Descriptions.Item label="忽略原因">{gap.dismiss_reason}</Descriptions.Item>)}
        </Descriptions>
      </Card>
      <Card title="来源计数" style={{ marginTop: 12 }}>
        {Object.entries(gap.source_counts_json || {}).map(([k, v]) => (
          <Tag key={k}>{k}: {v}</Tag>))}
      </Card>
      <Card title="occurrence 时间线（最近 50）" style={{ marginTop: 12 }}>
        <Timeline items={(gap.sources_json || []).map((s) => ({
          children: `${s.at} · ${s.source}${s.ref ? ' · ' + s.ref : ''}${s.detail ? ' · ' + s.detail : ''}`,
        }))} />
      </Card>
    </div>
  );
};
export default GapDetailPage;
```

- [ ] **Step 2: 写 GapStatsPage.tsx**（卡片 + top-heat 表；adoption_rate 为 null 显示「—」，不造数）

```tsx
import React, { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Table, Alert } from 'antd';
import { gapApi, type GapStats } from '../services/gapApi';

export const GapStatsPage: React.FC = () => {
  const [s, setS] = useState<GapStats | null>(null);
  useEffect(() => { (async () => setS(await gapApi.stats()))(); }, []);
  if (!s) return null;
  return (
    <div style={{ padding: 16 }}>
      {s.emit_failures > 0 && (
        <Alert type="warning" showIcon style={{ marginBottom: 12 }}
          message={`emitter 累计失败 ${s.emit_failures} 次（内存计数，重启归零）`} />)}
      <Row gutter={16}>
        <Col span={6}><Card><Statistic title="总缺口" value={s.total} /></Card></Col>
        <Col span={6}><Card><Statistic title="待处理(open)" value={s.by_status.open ?? 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="已采纳" value={s.by_status.adopted ?? 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="采纳率"
          value={s.adoption_rate == null ? '—' : `${(s.adoption_rate * 100).toFixed(1)}%`} /></Card></Col>
      </Row>
      <Card title="Top 热度" style={{ marginTop: 16 }}>
        <Table rowKey="id" pagination={false} dataSource={s.top_heat}
          columns={[
            { title: '说法', dataIndex: 'expression' },
            { title: '热度', dataIndex: 'heat' },
            { title: '状态', dataIndex: 'status' },
          ]} />
      </Card>
    </div>
  );
};
export default GapStatsPage;
```

- [ ] **Step 3: 注册路由**（`AppRoutes.tsx`，lazy import 三个页面）

```tsx
<Route path="/semantic-admin/gaps" element={<GapPoolPage />} />
<Route path="/semantic-admin/gaps/stats" element={<GapStatsPage />} />
<Route path="/semantic-admin/gaps/:id" element={<GapDetailPage />} />
```
（按 AppRoutes.tsx 既有 lazy/Suspense 约定包裹；若模块用 `semanticAdminRouteMeta`，同步补 meta 条目。）

- [ ] **Step 4: 菜单 seed**（`seed_four_steps.py`，`parent = "dir:build:semantic"` 下追加）

```python
        _menu("menu:build:semantic:gaps", "概念缺口", "/semantic-admin/gaps",
              "WarningOutlined", 7, parent),
        _menu("menu:build:semantic:gap-stats", "缺口统计", "/semantic-admin/gaps/stats",
              "BarChartOutlined", 8, parent),
```
> 执行前读 `seed_four_steps.py` 确认 `_menu` 签名与 sort 序号不冲突（既有到 6=质量仪表盘）。

- [ ] **Step 5: 写既有 DB 迁移脚本**（`scripts/migrations/add_gap_pool_menu.py`，幂等：存在则 skip，绕开 seed 只对新库生效的陷阱）

```python
"""为既有 DB 补概念缺口菜单项（seed 幂等 skip 陷阱：改 seed 对已有 DB 无效）。

用法： uv run python scripts/migrations/add_gap_pool_menu.py
"""
import os
import sqlite3

DB = os.path.join(os.environ.get("DATA_DIR",
    os.path.join(os.getcwd(), "apps", "api", "data")), "menu_config.db")

ITEMS = [
    ("menu:build:semantic:gaps", "概念缺口", "/semantic-admin/gaps",
     "WarningOutlined", 7, "dir:build:semantic"),
    ("menu:build:semantic:gap-stats", "缺口统计", "/semantic-admin/gaps/stats",
     "BarChartOutlined", 8, "dir:build:semantic"),
]

def main():
    if not os.path.exists(DB):
        print(f"DB 不存在，跳过（新库由 seed 生成）: {DB}")
        return
    conn = sqlite3.connect(DB)
    try:
        conn.row_factory = sqlite3.Row
        # 按 menu_config 实际表名/列名调整（执行前 Grep 确认 schema）
        for code, name, path, icon, sort, parent in ITEMS:
            exists = conn.execute(
                "SELECT 1 FROM menus WHERE code=?", (code,)).fetchone()
            if exists:
                print(f"skip 已存在: {code}")
                continue
            conn.execute(
                """INSERT INTO menus (code, name, path, icon, sort, parent_code)
                   VALUES (?,?,?,?,?,?)""",
                (code, name, path, icon, sort, parent))
            print(f"inserted: {code}")
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
```
> 执行前 Grep `menu_config` 的真实表名/列名（`menus` vs `menu_items`、`parent_code` vs `parent`），按实际改脚本。

- [ ] **Step 6: typecheck + lint**

Run: `cd apps/web && pnpm typecheck && pnpm lint`
Expected: 无新增错误。

- [ ] **Step 7: Stage（用户提交）**

```bash
git add apps/web/src/modules/semantic-admin/pages/GapDetailPage.tsx \
        apps/web/src/modules/semantic-admin/pages/GapStatsPage.tsx \
        apps/web/src/AppRoutes.tsx \
        apps/web/src/modules/semantic-admin/routes.tsx \
        apps/api/odap/biz/platform/menu_config/seeds/seed_four_steps.py \
        scripts/migrations/add_gap_pool_menu.py
git status
```
提示用户提交（`feat(web): 缺口详情/统计页 + 路由菜单接入`）。**不要 git commit。**

---

### Task 9: 文档同步 + ADR-086

**Files:**
- Create: `docs/07-adr/ADR-086-concept-gap-loop.md`
- Modify: `docs/07-adr/README.md`（索引 + 时间线）
- Modify: `docs/03-modules/README.md`（模块清单加 gap_pool）
- Modify: `agents.md`（附录 E API 速查表加 `/api/semantic-admin/gaps`）

**Interfaces:** 无代码接口；规则 12 文档同步。

- [ ] **Step 1: 写 ADR-086**（Context: 四信号源只落 logger、化石化不可见；Decision: 独立 gap_pool 子服务、heat 聚合、人工裁决、无静默兜底、side-channel 可观测、复用既有审批链；Consequences: 正/负面 + emit_failures 重启归零的取舍）

- [ ] **Step 2: 更新 `docs/07-adr/README.md`**（索引表加 ADR-086 行 + 时间线）

- [ ] **Step 3: 更新 `docs/03-modules/README.md`**（semantic_admin 下加 gap_pool 子模块说明）

- [ ] **Step 4: 更新 `agents.md` 附录 E**（API 速查表加：`/api/semantic-admin/gaps` 系列 6 端点）

- [ ] **Step 5: 对照 `docs/09-checklists/DOC_SYNC_CHECKLIST.md` 逐项自查**

- [ ] **Step 6: Stage（用户提交）**

```bash
git add docs/07-adr/ADR-086-concept-gap-loop.md \
        docs/07-adr/README.md \
        docs/03-modules/README.md \
        agents.md
git status
```
提示用户提交（`docs(gap-pool): ADR-086 概念缺口回路 + 文档同步`）。**不要 git commit。**

---

## 验收（对齐 spec §7）

1. 五个测试文件全绿：`test_gap_pool_storage.py`、`test_gap_emitter.py`、`test_gap_promote.py`、`test_gap_wiring.py`、`test_gap_routes.py`、`test_gap_loop_acceptance.py`（回路验收）。
2. dev 容器（`python apps/api/bootstep.py dev`）手验：制造未命中 → list 页 heat=1 → promote → 审批 → writeback → detail 页 ADOPTED + resolved term 链接 → resolve-check `resolvable=true`。
3. stats 全字段从真实记录来；注入 emitter 故障可见 `emit_failures` 递增。
4. 回归零新增（stashed-HEAD 基线 node-ID diff 为空）。
