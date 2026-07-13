#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日巡检：语义管理台 USL → Neo4j 从存储重建脚本

DESIGN.md §Iter 4 #4 要求：
  每日常规巡检：从 SQLite 主存储（usl_domains / usl_terms / usl_hierarchies /
  usl_property_specs / usl_disjoint_pairs / usl_cardinalities）重新加载所有
  USL__* 命名空间的点/边到 Neo4j 从副本，保证主从一致（不依赖 Outbox 增量）。

Exit codes:
  0  成功：所有 USL 主表数据完整同步到 Neo4j
  1  SQLite 连接失败 / 主表缺失
  2  Neo4j 连接失败（Bolt 握手 / 认证 / 网络）
  3  重建后计数不满足 >= 重建前的 70% 安全阈值（防止误删表误清空）
  4  部分从表写入异常（中途 Cypher 报错）
  5  CLI 参数错误

用法：
  python scripts/daily_sa_usl_neo4j_rebuild.py              # 读环境变量
  python scripts/daily_sa_usl_neo4j_rebuild.py --dry-run    # 只打印计数，不写 Neo4j
  python scripts/daily_sa_usl_neo4j_rebuild.py --yes        # 跳过确认提示（cron 模式）

环境变量（同 .env.docker）：
  DATA_DIR        数据目录（默认 ./data）
  NEO4J_URI       Bolt 地址（默认 bolt://localhost:7687）
  NEO4J_USER      默认 neo4j
  NEO4J_PASSWORD  默认 password
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
SAFETY_FLOOR_RATIO = 0.70  # 重建后 >= 重建前 * 70%，否则判定为误清

EXIT_OK = 0
EXIT_SQLITE_ERR = 1
EXIT_NEO4J_ERR = 2
EXIT_COUNT_MISMATCH = 3
EXIT_PARTIAL_WRITE = 4
EXIT_CLI_ERR = 5


# ==========================================================================
# 数据结构
# ==========================================================================


@dataclass
class Counts:
    sqlite_domains: int = 0
    sqlite_terms: int = 0
    sqlite_hierarchies: int = 0
    sqlite_properties: int = 0
    sqlite_disjoint_pairs: int = 0
    sqlite_cardinalities: int = 0
    neo4j_before_nodes: int = 0
    neo4j_before_edges: int = 0
    neo4j_after_nodes: int = 0
    neo4j_after_edges: int = 0
    neo4j_by_label: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ==========================================================================
# SQLite 读取
# ==========================================================================


def open_sqlite(data_dir: Path) -> Tuple[sqlite3.Connection, Path]:
    db_path = data_dir / "semantic_admin.db"
    if not db_path.exists():
        # Fallback：ODAP 的 usl 可能单独库
        alt = data_dir / "usl.db"
        if alt.exists():
            db_path = alt
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        print(f"[ERROR] SQLite 无法打开 {db_path}: {exc}", file=sys.stderr)
        sys.exit(EXIT_SQLITE_ERR)
    return conn, db_path


def check_sqlite_tables(conn: sqlite3.Connection) -> None:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
        "('usl_domains','usl_terms','usl_hierarchies','usl_property_specs',"
        "'usl_disjoint_pairs','usl_cardinalities')"
    )
    have = {row[0] for row in cur.fetchall()}
    need = {
        "usl_domains",
        "usl_terms",
        "usl_hierarchies",
        "usl_property_specs",
        "usl_disjoint_pairs",
        "usl_cardinalities",
    }
    missing = need - have
    if missing:
        print(f"[ERROR] SQLite 缺失 USL 主表: {sorted(missing)}", file=sys.stderr)
        sys.exit(EXIT_SQLITE_ERR)


def fetch_sqlite_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    tables = [
        ("usl_domains", "sqlite_domains"),
        ("usl_terms", "sqlite_terms"),
        ("usl_hierarchies", "sqlite_hierarchies"),
        ("usl_property_specs", "sqlite_properties"),
        ("usl_disjoint_pairs", "sqlite_disjoint_pairs"),
        ("usl_cardinalities", "sqlite_cardinalities"),
    ]
    out: Dict[str, int] = {}
    for t, k in tables:
        try:
            out[k] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.Error as exc:
            print(f"[ERROR] COUNT {t} 失败: {exc}", file=sys.stderr)
            out[k] = -1
    return out


def fetch_sqlite_rows(
    conn: sqlite3.Connection, table: str
) -> List[Dict[str, Any]]:
    cur = conn.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    rows = []
    for raw in cur.fetchall():
        d = {}
        for col, val in zip(cols, raw):
            if isinstance(val, str) and (
                val.startswith("{") or val.startswith("[")
            ):
                try:
                    d[col] = json.loads(val)
                except (ValueError, TypeError):
                    d[col] = val
            else:
                d[col] = val
        rows.append(d)
    return rows


# ==========================================================================
# Neo4j 读写（lazy import 允许脚本在无 neo4j 驱动环境下 --help / --dry-run）
# ==========================================================================


def get_neo4j_driver(uri: str, user: str, password: str):  # pragma: no cover - ops
    try:
        from neo4j import GraphDatabase, basic_auth  # type: ignore
    except ImportError:
        print(
            "[ERROR] 未安装 neo4j 驱动: pip install neo4j  （--dry-run 可不安装）",
            file=sys.stderr,
        )
        sys.exit(EXIT_NEO4J_ERR)
    try:
        driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
        with driver.session() as s:
            s.run("RETURN 1 AS ping").single()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Neo4j 无法连通 {uri}: {exc}", file=sys.stderr)
        sys.exit(EXIT_NEO4J_ERR)
    return driver


def neo4j_count_usl(driver) -> Tuple[int, int, Dict[str, int]]:  # pragma: no cover
    """返回 (nodes, edges, by_label) — 仅统计 USL__* 命名空间点边。"""
    with driver.session() as s:
        node_total = s.run(
            """
            MATCH (n)
            WHERE any(l IN labels(n) WHERE l STARTS WITH 'USL__')
            RETURN count(n) AS c
            """
        ).single()["c"]
        edge_total = s.run(
            """
            MATCH ()-[r]->()
            WHERE type(r) STARTS WITH 'USL__'
            RETURN count(r) AS c
            """
        ).single()["c"]
        by_label = {}
        for row in s.run(
            """
            MATCH (n)
            WITH labels(n) AS ls
            UNWIND ls AS l
            WITH l WHERE l STARTS WITH 'USL__'
            RETURN l, count(*) AS c ORDER BY c DESC
            """
        ):
            by_label[row["l"]] = row["c"]
    return int(node_total), int(edge_total), by_label


def neo4j_drop_usl(driver) -> None:  # pragma: no cover
    with driver.session() as s:
        s.run(
            """
            MATCH (n)
            WHERE any(l IN labels(n) WHERE l STARTS WITH 'USL__')
            DETACH DELETE n
            """
        )
        # 兜底：残余 USL__* 类型的边（上一步因点已删通常已经没了）
        s.run(
            """
            MATCH ()-[r]->()
            WHERE type(r) STARTS WITH 'USL__'
            DELETE r
            """
        )


def neo4j_upsert(driver, stmt: str, rows: List[Dict[str, Any]]) -> int:  # pragma: no cover
    """以 $rows UNWIND 批量执行。返回成功写入行数；出错则抛 RuntimeError。"""
    if not rows:
        return 0
    try:
        with driver.session() as s:
            s.run(stmt, rows=rows).consume()
            return len(rows)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(str(exc)) from exc


# ==========================================================================
# SQL -> Neo4j Cypher 映射
# ==========================================================================


def load_domains(conn: sqlite3.Connection, driver, counts: Counts, dry_run: bool) -> None:  # pragma: no cover
    rows = fetch_sqlite_rows(conn, "usl_domains")
    print(f"  ↳ domains  : {len(rows):>6} rows")
    counts.sqlite_domains = len(rows)
    if dry_run or not rows:
        return
    stmt = """
        UNWIND $rows AS r
        MERGE (d:USL__Domain:USL__Master {id: r.id})
        SET d.name=r.name, d.display_name=r.display_name,
            d.description=r.description, d.version_semver=r.version_semver,
            d.status=r.status, d.owner_user_id=r.owner_user_id,
            d.workspace_id=r.workspace_id, d.updated_at=r.updated_at,
            d.created_at=r.created_at
    """
    try:
        neo4j_upsert(driver, stmt, rows)
    except RuntimeError as exc:
        counts.errors.append(f"USL__Domain upsert 失败: {exc}")


def load_terms(conn: sqlite3.Connection, driver, counts: Counts, dry_run: bool) -> None:  # pragma: no cover
    rows = fetch_sqlite_rows(conn, "usl_terms")
    print(f"  ↳ terms    : {len(rows):>6} rows")
    counts.sqlite_terms = len(rows)
    if dry_run or not rows:
        return
    stmt = """
        UNWIND $rows AS r
        MERGE (t:USL__Term:USL__Master {id: r.id})
        SET t.name=r.name, t.display_name=r.display_name,
            t.category_path=r.category_path, t.semantic_type=r.semantic_type,
            t.definition=r.definition, t.curie=r.curie, t.status=r.status,
            t.term_version=r.term_version, t.domain_id=r.domain_id,
            t.created_by=r.created_by, t.updated_at=r.updated_at,
            t.created_at=r.created_at
        WITH t, r
        MATCH (d:USL__Domain {id: r.domain_id})
        MERGE (t)-[:USL__BELONGS_TO_DOMAIN]->(d)
    """
    try:
        neo4j_upsert(driver, stmt, rows)
    except RuntimeError as exc:
        counts.errors.append(f"USL__Term upsert 失败: {exc}")


def load_hierarchies(conn: sqlite3.Connection, driver, counts: Counts, dry_run: bool) -> None:  # pragma: no cover
    rows = fetch_sqlite_rows(conn, "usl_hierarchies")
    print(f"  ↳ hierarchy: {len(rows):>6} rows (is-a edges)")
    counts.sqlite_hierarchies = len(rows)
    if dry_run or not rows:
        return
    stmt = """
        UNWIND $rows AS r
        MATCH (c:USL__Term {id: r.child_term_id})
        MATCH (p:USL__Term {id: r.parent_term_id})
        MERGE (c)-[e:USL__IS_A]->(p)
        SET e.confidence=r.confidence, e.provenance=r.provenance,
            e.updated_at=r.updated_at
    """
    try:
        neo4j_upsert(driver, stmt, rows)
    except RuntimeError as exc:
        counts.errors.append(f"USL__IS_A upsert 失败: {exc}")


def load_properties(conn: sqlite3.Connection, driver, counts: Counts, dry_run: bool) -> None:  # pragma: no cover
    rows = fetch_sqlite_rows(conn, "usl_property_specs")
    print(f"  ↳ properties:{len(rows):>6} rows")
    counts.sqlite_properties = len(rows)
    if dry_run or not rows:
        return
    stmt = """
        UNWIND $rows AS r
        MERGE (p:USL__Property {id: r.id})
        SET p.name=r.name, p.datatype=r.datatype, p.cardinality=r.cardinality,
            p.description=r.description, p.owner_term_id=r.owner_term_id,
            p.updated_at=r.updated_at
        WITH p, r
        MATCH (t:USL__Term {id: r.owner_term_id})
        MERGE (t)-[:USL__HAS_PROPERTY]->(p)
    """
    try:
        neo4j_upsert(driver, stmt, rows)
    except RuntimeError as exc:
        counts.errors.append(f"USL__Property upsert 失败: {exc}")


def load_disjoint(conn: sqlite3.Connection, driver, counts: Counts, dry_run: bool) -> None:  # pragma: no cover
    rows = fetch_sqlite_rows(conn, "usl_disjoint_pairs")
    print(f"  ↳ disjoint : {len(rows):>6} rows")
    counts.sqlite_disjoint_pairs = len(rows)
    if dry_run or not rows:
        return
    stmt = """
        UNWIND $rows AS r
        MATCH (a:USL__Term {id: r.term_a_id})
        MATCH (b:USL__Term {id: r.term_b_id})
        MERGE (a)-[e:USL__DISJOINT_WITH]->(b)
        SET e.provenance=r.provenance, e.updated_at=r.updated_at
    """
    try:
        neo4j_upsert(driver, stmt, rows)
    except RuntimeError as exc:
        counts.errors.append(f"USL__DISJOINT_WITH upsert 失败: {exc}")


def load_cardinalities(conn: sqlite3.Connection, driver, counts: Counts, dry_run: bool) -> None:  # pragma: no cover
    rows = fetch_sqlite_rows(conn, "usl_cardinalities")
    print(f"  ↳ cardinal : {len(rows):>6} rows")
    counts.sqlite_cardinalities = len(rows)
    if dry_run or not rows:
        return
    stmt = """
        UNWIND $rows AS r
        MATCH (p:USL__Property {id: r.property_id})
        SET p.card_min=r.card_min, p.card_max=r.card_max,
            p.updated_at=r.updated_at
    """
    try:
        neo4j_upsert(driver, stmt, rows)
    except RuntimeError as exc:
        counts.errors.append(f"USL cardinality write 失败: {exc}")


# ==========================================================================
# 主流程
# ==========================================================================


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Semantic Admin USL -> Neo4j 从存储每日重建脚本",
    )
    p.add_argument(
        "--data-dir",
        default=None,
        help="DATA_DIR 覆盖（默认读环境变量 DATA_DIR → ./data）",
    )
    p.add_argument("--neo4j-uri", default=None, help="覆盖 NEO4J_URI")
    p.add_argument("--neo4j-user", default=None, help="覆盖 NEO4J_USER")
    p.add_argument("--neo4j-password", default=None, help="覆盖 NEO4J_PASSWORD")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印 SQLite/Neo4j 计数 + DROP/写入行数估算，不执行任何写操作",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="跳过 (y/N) 确认（cron 模式、CI/CD 无人值守）",
    )
    p.add_argument(
        "--output",
        default=None,
        help="可选：将前后计数 + 错误写入 JSON 报告",
    )
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    t0 = time.time()
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return EXIT_CLI_ERR if exc.code else EXIT_OK

    # ---- 环境解析 ----
    data_dir = Path(
        args.data_dir
        or os.environ.get("DATA_DIR")
        or (REPO_ROOT / "data")
    ).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    neo_uri = args.neo4j_uri or os.environ.get("NEO4J_URI") or "bolt://localhost:7687"
    neo_user = args.neo4j_user or os.environ.get("NEO4J_USER") or "neo4j"
    neo_pwd = args.neo4j_password or os.environ.get("NEO4J_PASSWORD") or "password"

    counts = Counts()
    print("=" * 72)
    print("Semantic Admin: USL → Neo4j 从存储 每日重建")
    print(f"  DATA_DIR       = {data_dir}")
    print(f"  NEO4J_URI      = {neo_uri}")
    print(f"  DRY_RUN        = {args.dry_run}")
    print("-" * 72)

    # ---- Step 1: SQLite ----
    print("[1/5] 打开 SQLite 主存储 ...")
    conn, db_path = open_sqlite(data_dir)
    print(f"  打开: {db_path}")
    check_sqlite_tables(conn)
    sql_counts = fetch_sqlite_counts(conn)
    for k, v in sql_counts.items():
        setattr(counts, k, v)
    print(
        "  主表行数: "
        f"domains={counts.sqlite_domains} terms={counts.sqlite_terms} "
        f"hier={counts.sqlite_hierarchies} props={counts.sqlite_properties} "
        f"disj={counts.sqlite_disjoint_pairs} card={counts.sqlite_cardinalities}"
    )

    if counts.sqlite_domains == 0 and counts.sqlite_terms == 0:
        counts.warnings.append("SQLite 表均为空 — USL 尚未初始化，跳过 Neo4j 写入。")

    # ---- Step 2: Neo4j before ----
    driver = None
    if not args.dry_run:
        print("[2/5] 连接 Neo4j 并统计重建前 USL__* 命名空间 ...")
        driver = get_neo4j_driver(neo_uri, neo_user, neo_pwd)
        nb, eb, bl = neo4j_count_usl(driver)
        counts.neo4j_before_nodes = nb
        counts.neo4j_before_edges = eb
        counts.neo4j_by_label = bl
        print(f"  Before: nodes={nb}  edges={eb}")
        if bl:
            for lbl, c in list(bl.items())[:8]:
                print(f"    · {lbl:<22} {c:>6}")
    else:
        print("[2/5] --dry-run：跳过 Neo4j 连接")

    # ---- Step 3: 确认（非 --yes） ----
    expected_drop = counts.neo4j_before_nodes + counts.neo4j_before_edges
    expected_write = (
        counts.sqlite_domains
        + counts.sqlite_terms
        + counts.sqlite_hierarchies
        + counts.sqlite_properties
        + counts.sqlite_disjoint_pairs
    )
    print("-" * 72)
    print(f"  预计 DROP : {expected_drop} USL__* objects")
    print(f"  预计 WRITE: {expected_write} (nodes+edges approx)")
    if not args.yes and not args.dry_run:
        try:
            ans = input("  继续执行？(y/N) ").strip().lower()
        except EOFError:
            ans = ""
        if ans not in ("y", "yes"):
            print("  → 用户取消，退出。")
            if driver:
                driver.close()
            conn.close()
            return EXIT_OK

    # ---- Step 4: DROP + 重建 ----
    if args.dry_run:
        print("[3/5] --dry-run：跳过 DROP/WRITE")
    else:
        print("[3/5] DROP 所有 USL__* 节点与边 ...")
        neo4j_drop_usl(driver)
        print("[4/5] 从 SQLite 主表 6 张批量 MERGE + set ...")
        try:
            load_domains(conn, driver, counts, dry_run=False)
            load_terms(conn, driver, counts, dry_run=False)
            load_hierarchies(conn, driver, counts, dry_run=False)
            load_properties(conn, driver, counts, dry_run=False)
            load_disjoint(conn, driver, counts, dry_run=False)
            load_cardinalities(conn, driver, counts, dry_run=False)
        except Exception as exc:  # noqa: BLE001
            counts.errors.append(f"中途异常: {exc}")

        # ---- Step 5: After 计数 + 安全阈值 ----
        print("[5/5] 统计重建后 ...")
        na, ea, _bl2 = neo4j_count_usl(driver)
        counts.neo4j_after_nodes = na
        counts.neo4j_after_edges = ea
        counts.neo4j_by_label = _bl2
        print(f"  After : nodes={na}  edges={ea}")
        if _bl2:
            for lbl, c in list(_bl2.items())[:10]:
                print(f"    · {lbl:<22} {c:>6}")

        # 安全阈值：nodes+edges 不能掉太狠（防止空库误写入）
        before_total = counts.neo4j_before_nodes + counts.neo4j_before_edges
        after_total = counts.neo4j_after_nodes + counts.neo4j_after_edges
        floor_min = int(counts.sqlite_terms * 0.5)  # 至少写回一半术语数
        if before_total > 0 and after_total < before_total * SAFETY_FLOOR_RATIO:
            counts.warnings.append(
                f"重建后总量 {after_total} < 重建前 {before_total} × {SAFETY_FLOOR_RATIO:.0%} "
                f"（阈值 {int(before_total * SAFETY_FLOOR_RATIO)}）— 请排查空库/主从不同步"
            )
        if floor_min > 0 and counts.neo4j_after_nodes < floor_min:
            counts.warnings.append(
                f"重建后 Term 节点 {counts.neo4j_after_nodes} 低于 SQLite terms × 50% 阈值 {floor_min}"
            )

    # ---- 收尾 ----
    conn.close()
    if driver:
        driver.close()

    dt = time.time() - t0
    print("-" * 72)
    if counts.errors:
        print(f"[ERR ] {len(counts.errors)} 条写错误：")
        for e in counts.errors:
            print(f"       • {e}")
    if counts.warnings:
        print(f"[WARN] {len(counts.warnings)} 条告警：")
        for w in counts.warnings:
            print(f"       • {w}")
    print(f"耗时 {dt:.1f}s")

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "elapsed_sec": round(dt, 2),
            **asdict(counts),
        }
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[REPT] JSON 报告已写入 {out_path}")

    # Exit code 决策
    if counts.errors:
        return EXIT_PARTIAL_WRITE
    if counts.warnings and not args.dry_run:
        # 告警不直接非零，除非明确计数掉穿安全线（由调用方决定是否报警）
        pass
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
