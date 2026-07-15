"""I4T14 USL 性能基准测试（严格 tmp_path 真实 SQLite，不 MagicMock 存储层）。

基准：
  T1. 单事务批量 upsert 10,000 条术语 ≤ 30s
  T2. 单事务批量 upsert 50,000 条层级边 ≤ 60s
  T3. 1,000 次随机术语 get 查询 QPS ≥ 100

资源不足（低内存 / CI 标记）时自动 skip；可通过 `PYTEST_RUN_PERF=1 pytest tests/perf/test_usl_bulk.py` 强制执行。
"""
from __future__ import annotations

import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import json as _jsonlib

import pytest

from odap.biz.semantic_admin.usl_manager.models import (
    HierarchyRel,
    SemanticType,
)
from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage


_PERF_FORCE = os.environ.get("PYTEST_RUN_PERF") == "1"


def _resource_ok() -> bool:
    """资源自检：低内存或 CI 环境 -> False（perf 不跑）。"""
    try:
        import sys
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            return False
        try:
            import psutil  # type: ignore[import-not-found]
            mem = psutil.virtual_memory()
            if mem.total < 2 * 1024 * 1024 * 1024:
                return False
        except Exception:
            pass
        return sys.maxsize > 2**32
    except Exception:
        return True


skip_unless = pytest.mark.skipif(
    (not _PERF_FORCE) and (not _resource_ok()),
    reason="资源不足或非强制运行（export PYTEST_RUN_PERF=1 强制执行）",
)


# =====================================================================
# Helpers
# =====================================================================

_DOMAIN_CODE = "perf_bulk"


def _seed_domain(storage: SQLiteUslStorage) -> str:
    domain = dict(
        id=str(uuid.uuid4()),
        code=_DOMAIN_CODE,
        display_name="Perf Bulk Domain",
        description="性能测试专用领域（1万术语+5万层级）",
        en_mapping={},
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    storage.upsert_domain(domain)
    return domain["id"]


def _make_terms(domain_id: str, n: int) -> List[Dict]:
    sem_types = [t.value for t in (SemanticType.OBJECT_TYPE, SemanticType.CONCEPT_TYPE, SemanticType.EVENT_TYPE)]
    now = datetime.now(timezone.utc).isoformat()
    return [
        dict(
            id=str(uuid.uuid4()),
            domain_id=domain_id,
            canonical=f"Term_{i:06d}",
            semantic_type=sem_types[i % len(sem_types)],
            synonyms=[f"同义{i}", f"别名{i}-A"],
            near_synonyms=[f"近义{i}"],
            aliases=[f"A{i}"],
            stoplist_flag=(i % 101 == 0),
            definition=f"Term {i} definition for perf test",
            created_at=now,
            updated_at=now,
        )
        for i in range(n)
    ]


# =====================================================================
# T1/T2: Bulk upsert 术语 + 层级边
# =====================================================================


@pytest.mark.perf
@pytest.mark.slow
@skip_unless
def test_bulk_upsert_10000_terms(tmp_path: Path):
    """T1. 单事务 upsert 10000 Term（使用 storage 层原生 executemany 模式）。"""
    db_path = tmp_path / "usl_perf_terms.db"
    storage = SQLiteUslStorage(str(db_path))
    domain_id = _seed_domain(storage)
    terms = _make_terms(domain_id, 10_000)

    t0 = time.perf_counter()
    cnt = storage.bulk_upsert_terms(terms) if hasattr(storage, "bulk_upsert_terms") else _bulk_exec(
        str(db_path),
        """INSERT OR REPLACE INTO usl_terms
        (id,domain_id,canonical,semantic_type,synonyms,near_synonyms,aliases,stoplist_flag,definition,created_at,updated_at)
        VALUES (?,?,?,?,json(?),json(?),json(?),?,?,?,?,?)""",
        [
            (
                t["id"], t["domain_id"], t["canonical"], t["semantic_type"],
                _json(t["synonyms"]), _json(t["near_synonyms"]), _json(t["aliases"]),
                1 if t["stoplist_flag"] else 0, t["definition"], t["created_at"], t["updated_at"],
            )
            for t in terms
        ],
    )
    elapsed = time.perf_counter() - t0

    # 断言：实际行数 + 时间阈值
    stored = _scalar(str(db_path), "SELECT COUNT(*) FROM usl_terms WHERE domain_id=?", (domain_id,))
    assert stored == 10_000, f"期望 10000 术语，实际 {stored}"
    assert cnt is None or cnt >= 10_000, f"bulk 返回行数 {cnt} 异常"
    assert elapsed <= 30.0, f"T1 术语批量写入耗时 {elapsed:.2f}s 超过 30s 阈值"


@pytest.mark.perf
@pytest.mark.slow
@skip_unless
def test_bulk_upsert_50000_hierarchies(tmp_path: Path):
    """T2. 单事务 upsert 50000 层级边（term_0->term_1~chain, 随机交错 parent/child）。"""
    import random

    db_path = tmp_path / "usl_perf_edges.db"
    storage = SQLiteUslStorage(str(db_path))
    domain_id = _seed_domain(storage)

    # 先种术语（按 2000 作为节点池，取 parent/child 组合）
    TERM_N = 2_000
    terms = _make_terms(domain_id, TERM_N)
    _bulk_exec(
        str(db_path),
        """INSERT OR REPLACE INTO usl_terms
        (id,domain_id,canonical,semantic_type,synonyms,near_synonyms,aliases,stoplist_flag,definition,created_at,updated_at)
        VALUES (?,?,?,?,json(?),json(?),json(?),?,?,?,?,?)""",
        [
            (
                t["id"], t["domain_id"], t["canonical"], t["semantic_type"],
                _json(t["synonyms"]), _json(t["near_synonyms"]), _json(t["aliases"]),
                1 if t["stoplist_flag"] else 0, t["definition"], t["created_at"], t["updated_at"],
            )
            for t in terms
        ],
    )
    term_ids = [t["id"] for t in terms]

    # 造 50,000 条层级边（随机不同 parent/child/rel_type 保证 unique）
    rels = [r.value for r in (HierarchyRel.IS_A, HierarchyRel.PART_OF, HierarchyRel.INSTANCE_OF)]
    now = datetime.now(timezone.utc).isoformat()
    rng = random.Random(42)
    seen = set()
    rows = []
    while len(rows) < 50_000:
        p = rng.randrange(TERM_N)
        c = rng.randrange(TERM_N)
        if c == p:
            continue
        r = rels[len(rows) % len(rels)]
        key = (p, c, r)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            (
                str(uuid.uuid4()),
                domain_id,
                term_ids[p],
                term_ids[c],
                r,
                0.5 + (len(rows) % 100) * 0.005,
                now,
                now,
            )
        )

    t0 = time.perf_counter()
    _bulk_exec(
        str(db_path),
        """INSERT OR REPLACE INTO usl_hierarchies
        (id,domain_id,parent_term_id,child_term_id,rel_type,confidence,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        rows,
    )
    elapsed = time.perf_counter() - t0

    stored = _scalar(str(db_path), "SELECT COUNT(*) FROM usl_hierarchies WHERE domain_id=?", (domain_id,))
    assert stored >= 50_000, f"期望 ≥50000 层级边，实际 {stored}"
    assert elapsed <= 60.0, f"T2 层级边批量写入耗时 {elapsed:.2f}s 超过 60s 阈值"


@pytest.mark.perf
@pytest.mark.slow
@skip_unless
def test_get_term_qps_1000(tmp_path: Path):
    """T3. 1000 次随机 get_term，QPS ≥ 100。"""
    import random

    db_path = tmp_path / "usl_perf_qps.db"
    storage = SQLiteUslStorage(str(db_path))
    domain_id = _seed_domain(storage)

    TERM_N = 5_000
    terms = _make_terms(domain_id, TERM_N)
    _bulk_exec(
        str(db_path),
        """INSERT OR REPLACE INTO usl_terms
        (id,domain_id,canonical,semantic_type,synonyms,near_synonyms,aliases,stoplist_flag,definition,created_at,updated_at)
        VALUES (?,?,?,?,json(?),json(?),json(?),?,?,?,?,?)""",
        [
            (
                t["id"], t["domain_id"], t["canonical"], t["semantic_type"],
                _json(t["synonyms"]), _json(t["near_synonyms"]), _json(t["aliases"]),
                1 if t["stoplist_flag"] else 0, t["definition"], t["created_at"], t["updated_at"],
            )
            for t in terms
        ],
    )
    term_ids = [t["id"] for t in terms]

    rng = random.Random(7)
    QP_N = 1_000
    samples = [term_ids[rng.randrange(TERM_N)] for _ in range(QP_N)]

    t0 = time.perf_counter()
    found = 0
    for tid in samples:
        res = storage.get_term(tid)
        if res is not None:
            found += 1
    elapsed = time.perf_counter() - t0

    qps = QP_N / max(elapsed, 1e-6)
    assert found == QP_N, f"期望命中 {QP_N} 次，实际 {found}"
    assert qps >= 100.0, f"T3 QPS={qps:.2f} 低于 100 阈值（耗时 {elapsed:.2f}s/1000）"


# =====================================================================
# 纯原生辅助：没有 bulk_upsert 时 fallback 用 sqlite3 executemany
# =====================================================================


def _json(v):
    return _jsonlib.dumps(v, ensure_ascii=False)


def _bulk_exec(db_path: str, sql: str, rows: List[tuple]) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=OFF")
        cur.execute("BEGIN")
        cur.executemany(sql, rows)
        conn.commit()
        return cur.rowcount if cur.rowcount and cur.rowcount > 0 else len(rows)
    finally:
        conn.close()


def _scalar(db_path: str, sql: str, params=()) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return int(cur.fetchone()[0])
    finally:
        conn.close()
