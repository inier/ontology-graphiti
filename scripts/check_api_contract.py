#!/usr/bin/env python3
"""F13 三方契约对账：前端调用 / OpenAPI 契约 / 后端实际路由。

用法：
    python scripts/check_api_contract.py                     # 输出对账矩阵（默认 scope=/api/v1）
    python scripts/check_api_contract.py --include-legacy    # 全量（含 /api/... 历史端点）
    python scripts/check_api_contract.py --strict            # 存在阻断级偏差时返回 1
    python scripts/check_api_contract.py --out-dir build/contract

数据来源（三方各自读取真实载体，不做任何猜测；扫描实现见 `api_contract_scanner.py`）：
    前端  apps/web/src/**/*.ts(x) 里的 API 路径字面量（含 `${API_BASE}` 模板串与相对端点常量）
    契约  docs/02-architecture/openapi-v2.yaml 的 servers[].url + paths
    后端  实际 FastAPI 应用的路由表（app.openapi()；导入失败则退回 AST 扫描 APIRouter 前缀）

对账结论分三级：
    BLOCKING  契约要求但后端缺失 / 前端调用但后端缺失 / 契约声明的方法未实现
    WARN      后端已实现但契约漏登记 / 路径参数名不一致
    INFO      后端已实现但前端尚未接入

注意：本脚本只做静态对账并出报告，不改任何代码；退出码默认 0，仅 --strict 时对 BLOCKING 返回 1。
本脚本不打印 emoji，异常不吞（失败必须带具体原因）。
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_contract_scanner import (  # noqa: E402 - 脚本同目录导入
    ROOT,
    SPEC,
    WEB_SRC,
    Endpoint,
    _param_token,
    scan_backend,
    scan_frontend,
    scan_spec,
)

DEFAULT_OUT = ROOT / "docs" / "09-checklists"


# --------------------------------------------------------------------------- 对账

def reconcile(front: dict[str, Endpoint], spec: dict[str, Endpoint],
              backend: dict[str, Endpoint], scope: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(set(front) | set(spec) | set(backend)):
        if scope and not path.startswith(scope):
            continue
        in_front, in_spec, in_backend = path in front, path in spec, path in backend
        spec_methods = spec[path].methods.get("spec", set()) if in_spec else set()
        back_methods = backend[path].methods.get("backend", set()) if in_backend else set()
        missing_methods = sorted(spec_methods - back_methods)

        names = {src: table[path].params.get(src, ()) for src, table, flag in
                 (("frontend", front, in_front), ("spec", spec, in_spec), ("backend", backend, in_backend))
                 if flag}
        distinct = {frozenset(_param_token(n) for n in v) for v in names.values()}
        param_mismatch = len(distinct) > 1

        if in_spec and not in_backend:
            status, level, action = "spec_only", "BLOCKING", "后端未实现契约端点，需补齐实现"
        elif in_front and not in_backend:
            status, level, action = "frontend_only", "BLOCKING", "前端调用了不存在的端点，需后端补齐或前端下线"
        elif missing_methods:
            status, level, action = "method_missing", "BLOCKING", f"契约声明的方法未实现：{','.join(missing_methods)}"
        elif in_backend and not in_spec:
            status, level, action = "backend_not_in_spec", "WARN", "后端已实现但契约未登记，需补契约"
        elif param_mismatch:
            status, level, action = "param_name_mismatch", "WARN", "路径参数名三方不一致，前端拼接易错"
        elif in_backend and not in_front:
            status, level, action = "frontend_not_called", "INFO", "前端尚未接入（本轮可不处理）"
        else:
            status, level, action = "ok", "OK", "-"

        rows.append({
            "status": status,
            "level": level,
            "path": path,
            "methods_spec": ",".join(sorted(spec_methods)).upper() or "-",
            "methods_backend": ",".join(sorted(back_methods)).upper() or "-",
            "in_frontend": "Y" if in_front else "N",
            "in_spec": "Y" if in_spec else "N",
            "in_backend": "Y" if in_backend else "N",
            "params_frontend": ",".join(sorted(names.get("frontend", ()))) or "-",
            "params_spec": ",".join(sorted(names.get("spec", ()))) or "-",
            "params_backend": ",".join(sorted(names.get("backend", ()))) or "-",
            "action": action,
        })
    return rows


def write_reports(rows: list[dict[str, str]], out_dir: Path, scope: str, backend_mode: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0].keys()) if rows else ["status", "level", "path"]
    csv_path = out_dir / "api-contract-matrix.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    order = {"BLOCKING": 0, "WARN": 1, "INFO": 2, "OK": 3}
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["level"]] = counts.get(row["level"], 0) + 1
    lines = [
        "# API 契约对账矩阵（F13）",
        "",
        f"- 对账范围：`{scope or '全量'}`；后端路由来源：`{backend_mode}`；共 {len(rows)} 条路径。",
        f"- 结论：BLOCKING {counts.get('BLOCKING', 0)} / WARN {counts.get('WARN', 0)}"
        f" / INFO {counts.get('INFO', 0)} / OK {counts.get('OK', 0)}",
        "- 口径：前端=源码中的 API 路径字面量；契约=openapi-v2.yaml；后端=实际路由表。",
        "",
    ]
    for level, title in (("BLOCKING", "阻断级偏差（必须处理）"), ("WARN", "需登记/对齐"), ("INFO", "后端已就绪待前端接入")):
        subset = [r for r in rows if r["level"] == level]
        lines.append(f"## {title}")
        lines.append("")
        if not subset:
            lines.append("无。")
        else:
            lines.append("| 方法(契约) | 方法(后端) | 路径 | 前端 | 契约 | 后端 | 参数(契约/后端) | 处理 |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for row in sorted(subset, key=lambda r: (order[r["level"]], r["status"], r["path"])):
                lines.append(
                    f"| {row['methods_spec']} | {row['methods_backend']} | `{row['path']}` | "
                    f"{row['in_frontend']} | {row['in_spec']} | {row['in_backend']} | "
                    f"{row['params_spec']} / {row['params_backend']} | {row['action']} |"
                )
        lines.append("")
    (out_dir / "api-contract-matrix.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] 报告已生成：{csv_path.relative_to(ROOT)}")
    print(f"[OK] 报告已生成：{(out_dir / 'api-contract-matrix.md').relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="前端 / OpenAPI 契约 / 后端路由三方对账（F13）")
    parser.add_argument("--scope", default="/api/v1", help="只对账该前缀下的路径（默认 /api/v1）")
    parser.add_argument("--include-legacy", action="store_true", help="全量对账（含 /api/... 历史端点）")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT), help="报告输出目录")
    parser.add_argument("--strict", action="store_true", help="存在 BLOCKING 偏差时返回退出码 1")
    args = parser.parse_args(argv)

    if not WEB_SRC.is_dir():
        print(f"[ERROR] 前端源码目录不存在：{WEB_SRC}")
        return 2
    if not SPEC.is_file():
        print(f"[ERROR] 契约文件不存在：{SPEC}")
        return 2

    front = scan_frontend(WEB_SRC)
    spec = scan_spec(SPEC)
    backend, mode = scan_backend()
    scope = "" if args.include_legacy else args.scope.rstrip("/")
    rows = reconcile(front, spec, backend, scope)
    write_reports(rows, Path(args.out_dir), scope, mode)

    blocking = [r for r in rows if r["level"] == "BLOCKING"]
    for row in blocking:
        print(f"[BLOCKING] {row['status']}: {row['path']} — {row['action']}")
    if not blocking:
        print("\nPASSED: 无阻断级契约偏差")
        return 0
    if args.strict:
        print(f"\nFAILED: {len(blocking)} 条阻断级契约偏差")
        return 1
    print(f"\nWARN: {len(blocking)} 条阻断级偏差未处理（加 --strict 则返回退出码 1）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
