#!/usr/bin/env python3
"""溯源证据链门禁脚本（F8 / AC-36 / AC-37 / AC-38 / AC-39）。

用法：
    python scripts/verify_provenance.py --self-test          # 自检（无外部依赖）
    python scripts/verify_provenance.py --trace-id <trace_id> # 校验指定问答溯源
    python scripts/verify_provenance.py --all                 # 校验库内全部溯源
    python scripts/verify_provenance.py --all --db <path>      # 指定 odap_main.db

校验规则（与运行时共用 `validate_provenance` 唯一实现）：
    R1 trace_id 唯一且形如 urn:odap:trace:<ULID>
    R2 六步齐全（intent/map/guard/retrieve/compose/gate）
    R3 每条 evidence.ref 可解析
    R4 tbox_version 与当前 TBox 快照哈希一致

退出码：0 = 通过；1 = 存在违规；2 = 运行环境/参数错误。
本脚本不打印 emoji，不吞异常（失败必须带具体原因）。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_API_DIR = _ROOT / "apps" / "api"
for _p in (str(_API_DIR), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load_modules():
    """延迟导入：只有真正执行校验时才拉 odap 包（--help 保持轻量）。"""
    from odap.biz.core.ontology.orchestration.contracts import Evidence, Step, StepProv
    from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver
    from odap.biz.core.ontology.orchestration.provenance import (
        Provenance,
        ProvenanceBuilder,
        validate_provenance,
    )
    from odap.biz.core.ontology.orchestration.repositories.trace_repo import QaTraceRepository
    from odap.biz.core.ontology.orchestration.tbox import TBoxCatalog

    return {
        "Evidence": Evidence,
        "Step": Step,
        "StepProv": StepProv,
        "DefaultEvidenceResolver": DefaultEvidenceResolver,
        "Provenance": Provenance,
        "ProvenanceBuilder": ProvenanceBuilder,
        "validate_provenance": validate_provenance,
        "QaTraceRepository": QaTraceRepository,
        "TBoxCatalog": TBoxCatalog,
    }


def _print_violations(label: str, violations) -> None:
    print(f"[FAIL] {label}")
    for violation in violations:
        step = f" step={violation.step}" if violation.step else ""
        print(f"  - {violation.rule}{step}: {violation.detail}")


def run_self_test() -> int:
    """无外部依赖的自检：正例通过 + 四类反例逐个被抓住。"""
    import tempfile

    mods = _load_modules()
    Evidence = mods["Evidence"]
    StepProv = mods["StepProv"]
    ProvenanceBuilder = mods["ProvenanceBuilder"]
    validate_provenance = mods["validate_provenance"]
    QaTraceRepository = mods["QaTraceRepository"]

    tbox_version = "sha256:selftest-tbox-snapshot"
    # 26 字符 Crockford Base32 ULID（R1 要求），与 odap.common.ids.new_trace_id 一致
    builder = ProvenanceBuilder("urn:odap:trace:01J9ZK8P3Q7N2M4R5T6V7W8X9A")
    for step in ("intent", "map", "guard", "retrieve", "compose", "gate"):
        builder.add(
            step,
            StepProv(
                component=f"SelfTest-{step}",
                evidence=[Evidence(kind="decision", ref="decision:contract_ok")],
            ),
        )
    provenance = builder.build(
        tbox_version=tbox_version, contract_ok=True,
        citations=[Evidence(kind="decision", ref="decision:contract_ok")],
    )

    failures = 0
    good = validate_provenance(provenance, resolver=None, expected_tbox_version=tbox_version)
    if good:
        failures += 1
        _print_violations("正例本应通过却报违规", good)
    else:
        print("[OK] 正例：六步齐全 + 版本锚定一致 → 通过")

    # 生成器一致性：odap.common.ids.new_trace_id() 产出必须能被 R1 接受
    from odap.common.ids import new_trace_id

    generated = new_trace_id()
    v = validate_provenance(
        provenance.model_copy(update={"trace_id": generated}), resolver=None,
        expected_tbox_version=tbox_version,
    )
    if any(x.rule == "R1" for x in v):
        failures += 1
        print(f"[FAIL] new_trace_id() 产出未被 R1 接受：{generated}")
    else:
        print(f"[OK] 生成器一致：new_trace_id() → {generated}")

    # 反例 1：缺步
    missing = provenance.model_copy(
        update={"steps": [s for s in provenance.steps if s.step != "guard"]}
    )
    v = validate_provenance(missing, resolver=None, expected_tbox_version=tbox_version)
    if not any(x.rule == "R2" for x in v):
        failures += 1
        print("[FAIL] 缺步未被 R2 抓住")
    else:
        print("[OK] 反例：缺 guard 步 → R2 违规")

    # 反例 2：不可解析证据
    from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

    resolver = DefaultEvidenceResolver()
    bad_ref = provenance.model_copy(
        update={
            "steps": [
                s.model_copy(update={
                    "evidence": [Evidence(kind="decision", ref="decision:not_a_real_decision")]
                }) if s.step == "gate" else s
                for s in provenance.steps
            ]
        }
    )
    v = validate_provenance(bad_ref, resolver=resolver, expected_tbox_version=tbox_version)
    if not any(x.rule == "R3" for x in v):
        failures += 1
        print("[FAIL] 不可解析证据未被 R3 抓住")
    else:
        print("[OK] 反例：未知 decision ref → R3 违规")

    # 反例 3：版本锚定不一致
    v = validate_provenance(provenance, resolver=None, expected_tbox_version="sha256:other")
    if not any(x.rule == "R4" for x in v):
        failures += 1
        print("[FAIL] tbox_version 不一致未被 R4 抓住")
    else:
        print("[OK] 反例：tbox_version 不一致 → R4 违规")

    # 反例 4：trace_id 格式非法
    v = validate_provenance(
        provenance.model_copy(update={"trace_id": "trace-123"}), resolver=None,
        expected_tbox_version=tbox_version,
    )
    if not any(x.rule == "R1" for x in v):
        failures += 1
        print("[FAIL] 非法 trace_id 未被 R1 抓住")
    else:
        print("[OK] 反例：trace_id 格式非法 → R1 违规")

    # 存储往返 + 主键唯一性（R1 的存储级保证）
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "odap_main.db")
        repo = QaTraceRepository(db_path=db_path)
        repo.save(
            {
                "trace_id": provenance.trace_id,
                "query": "上个季度退货率最高的三个品类是什么",
                "workspace_id": "ws-selftest",
                "user_id": "u-qa",
                "intent": {"intent_type": "metric_query", "confidence": 0.95},
                "created_at": "2026-10-17T00:00:00+00:00",
            },
            provenance,
        )
        reloaded = repo.get_provenance(provenance.trace_id)
        if reloaded is None or len(reloaded.steps) != 6:
            failures += 1
            print("[FAIL] 溯源落库往返失败（步骤数不为 6）")
        else:
            print("[OK] 存储往返：qa_traces + qa_provenance 6 步可还原")
        try:
            repo.save(
                {
                    "trace_id": provenance.trace_id,
                    "query": "重复写入",
                    "created_at": "2026-10-17T00:00:01+00:00",
                },
                provenance,
            )
            failures += 1
            print("[FAIL] 重复 trace_id 未被拒绝（R1 唯一性破坏）")
        except Exception:
            print("[OK] 重复 trace_id 被存储层拒绝（R1 唯一性成立）")

    if failures:
        print(f"\nself-test FAILED: {failures} 项未达预期")
        return 1
    print("\nself-test PASSED: R1~R4 校验与存储往返全部符合预期")
    return 0


def run_live(db_path: str | None, trace_id: str | None, workspace_id: str = "") -> int:
    mods = _load_modules()
    repo = mods["QaTraceRepository"](db_path=db_path)
    catalog = mods["TBoxCatalog"]()
    resolver = mods["DefaultEvidenceResolver"](catalog=catalog)

    if trace_id:
        trace_ids = [trace_id]
    else:
        trace_ids = _list_trace_ids(db_path)

    if not trace_ids:
        print("[FAIL] 未找到任何溯源记录（qa_traces 为空）。请先执行问答产生 trace。")
        return 1

    expected_tbox = ""
    try:
        expected_tbox = catalog.snapshot_hash(workspace_id)
    except Exception as exc:  # noqa: BLE001 - TBox 不可读则 R4 无法复核，必须显式失败
        print(f"[FAIL] TBox 快照不可读，无法做版本锚定（R4）：{type(exc).__name__}: {exc}")
        return 1

    total_violations = 0
    for tid in trace_ids:
        provenance = repo.get_provenance(tid)
        if provenance is None:
            print(f"[FAIL] trace 不存在：{tid}")
            total_violations += 1
            continue
        violations = mods["validate_provenance"](
            provenance, resolver=resolver, expected_tbox_version=expected_tbox
        )
        if violations:
            _print_violations(f"trace {tid}", violations)
            total_violations += len(violations)
        else:
            print(f"[OK] trace {tid}: 六步齐全、证据可解析、版本锚定一致")

    if total_violations:
        print(f"\nFAILED: {total_violations} 条溯源违规")
        return 1
    print(f"\nPASSED: {len(trace_ids)} 条溯源全部通过")
    return 0


def _list_trace_ids(db_path: str | None) -> list[str]:
    import sqlite3

    from odap.infra.storage.schema_v2 import default_db_path, ensure_v2_schema

    path = ensure_v2_schema(db_path or default_db_path())
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("SELECT trace_id FROM qa_traces ORDER BY created_at DESC").fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 ODAP 问答溯源证据链（AC-36~AC-39）")
    parser.add_argument("--self-test", action="store_true", help="运行自检（无外部依赖）")
    parser.add_argument("--trace-id", default=None, help="校验指定 trace_id")
    parser.add_argument("--all", action="store_true", help="校验库内全部 trace")
    parser.add_argument("--db", default=None, help="odap_main.db 路径")
    parser.add_argument("--workspace-id", default="", help="TBox 快照所属 workspace")
    args = parser.parse_args(argv)

    try:
        if args.self_test:
            return run_self_test()
        if args.trace_id or args.all:
            return run_live(args.db, args.trace_id, args.workspace_id)
    except Exception as exc:  # noqa: BLE001 - 门禁脚本必须给出明确失败原因
        print(f"[ERROR] 校验过程异常：{type(exc).__name__}: {exc}")
        return 2

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
