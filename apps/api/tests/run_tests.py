"""ODAP 统一自动化测试运行器

支持多种测试模式与报告输出，覆盖后端 pytest 与前端 vitest。

用法::

    python run_tests.py smoke          # 冒烟测试（核心功能，<60s）
    python run_tests.py unit           # 后端单元测试
    python run_tests.py regression     # 回归测试（核心业务路径）
    python run_tests.py integration    # 集成测试（需外部服务）
    python run_tests.py e2e            # 端到端测试（需后端运行）
    python run_tests.py perf           # 性能基准测试
    python run_tests.py frontend       # 前端测试
    python run_tests.py full           # 全量测试（unit + frontend）
    python run_tests.py all            # 全部测试（含 integration/e2e/perf）
    python run_tests.py --help

选项::
    --no-coverage      跳过覆盖率统计
    --no-html          跳过 HTML 报告生成
    --junit-xml        输出 JUnit XML 报告（默认开启）
    --parallel N       并行进程数（默认自动）
    --keep-going       失败后继续运行后续阶段
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent
REPORT_DIR = PROJECT_ROOT / "test-reports"


# ---------------------------------------------------------------------------
# 阶段结果数据结构
# ---------------------------------------------------------------------------


@dataclass
class StageResult:
    """单个测试阶段的执行结果。"""

    name: str
    command: str
    exit_code: int
    duration_sec: float
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    coverage_percent: Optional[float] = None
    junit_xml: Optional[str] = None
    stdout_tail: str = ""

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors


@dataclass
class TestRunSummary:
    """整次测试运行的汇总。"""

    started_at: str
    finished_at: str = ""
    total_duration_sec: float = 0.0
    stages: list = field(default_factory=list)
    overall_success: bool = True
    mode: str = ""

    def add(self, stage: StageResult) -> None:
        self.stages.append(stage)
        if not stage.success:
            self.overall_success = False


# ---------------------------------------------------------------------------
# 命令构建
# ---------------------------------------------------------------------------


def _python() -> str:
    return sys.executable


def _ensure_report_dir() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _parse_pytest_terminal(stdout: str) -> dict:
    """从 pytest 终端输出末尾解析通过/失败/跳过数。"""
    stats = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    if not stdout:
        return stats
    last_lines = stdout.strip().splitlines()[-30:]
    for line in last_lines:
        # 形如 "189 passed in 64.37s" 或 "5434 passed, 12 failed, 3 skipped"
        for key in stats:
            for token in line.replace(",", " ").split():
                if token.isdigit() and key in line.lower():
                    # 仅当该 token 紧跟/前跟关键字的情形
                    pass
        # 简化解析：在最后一行找 "N passed", "N failed", "N skipped", "N errors"
        lower = line.lower()
        for key in stats:
            idx = lower.find(key)
            while idx > 0:
                # 向前找数字
                j = idx - 1
                while j >= 0 and (lower[j].isdigit() or lower[j].isspace()):
                    j -= 1
                num_str = line[j + 1 : idx].strip()
                if num_str.isdigit():
                    stats[key] = max(stats[key], int(num_str))
                    break
                idx = lower.find(key, idx + 1)
    return stats


def _has_pytest_cov() -> bool:
    """检测 pytest-cov 插件是否可用。"""
    try:
        import pytest_cov  # noqa: F401
        return True
    except ImportError:
        return False


def _has_pytest_xdist() -> bool:
    """检测 pytest-xdist 插件是否可用。"""
    try:
        import xdist  # noqa: F401
        return True
    except ImportError:
        return False


def build_pytest_command(
    mode: str,
    *,
    coverage: bool,
    junit_xml: bool,
    parallel: Optional[int],
) -> list:
    """构建 pytest 命令行。"""
    cmd = [_python(), "-m", "pytest"]

    if mode == "smoke":
        cmd += ["-m", "smoke", "tests/"]
    elif mode == "unit":
        cmd += ["tests/unit/"]
    elif mode == "regression":
        cmd += ["-m", "regression", "tests/unit/"]
    elif mode == "integration":
        cmd += ["tests/integration/", "-m", "integration"]
    elif mode == "e2e":
        cmd += ["tests/e2e/", "-m", "e2e"]
    elif mode == "perf":
        cmd += ["tests/perf/", "-m", "perf"]
    else:
        cmd += ["tests/unit/"]

    # 并行（仅当安装了 pytest-xdist 时生效；未安装时忽略）
    if parallel and parallel > 1 and _has_pytest_xdist():
        cmd += ["-n", str(parallel)]

    # JUnit XML
    if junit_xml:
        xml_path = REPORT_DIR / f"junit-{mode}.xml"
        cmd += [f"--junitxml={xml_path}"]

    # 覆盖率（仅在 pytest-cov 可用时启用）
    if coverage and _has_pytest_cov():
        cmd += [
            f"--cov=odap",
            "--cov-report=term-missing",
            f"--cov-report=xml:{REPORT_DIR / f'coverage-{mode}.xml'}",
            f"--cov-report=html:{REPORT_DIR / f'coverage-{mode}-html'}",
        ]
    elif coverage:
        print("[warn] pytest-cov 未安装，跳过覆盖率统计。安装: pip install pytest-cov")

    return cmd


def build_frontend_command(coverage: bool) -> list:
    """构建前端 vitest 命令。"""
    cmd = ["npm", "run", "test"]
    if coverage:
        cmd = ["npm", "run", "test:coverage"]
    return cmd


# ---------------------------------------------------------------------------
# 阶段执行
# ---------------------------------------------------------------------------


def _extract_coverage(stdout: str) -> Optional[float]:
    """从输出中提取总覆盖率百分比。"""
    if not stdout:
        return None
    for line in stdout.splitlines():
        s = line.strip()
        if "TOTAL" in s and "%" in s:
            # 形如 "TOTAL ... 85%"
            try:
                return float(s.rsplit("%", 1)[0].split()[-1])
            except (ValueError, IndexError):
                continue
        if s.startswith("All files") and "%" in s:
            try:
                return float(s.rsplit("%", 1)[0].split()[-1])
            except (ValueError, IndexError):
                continue
    return None


def run_stage(
    name: str,
    command: list,
    *,
    cwd: Optional[Path] = None,
    junit_xml: Optional[str] = None,
    env: Optional[dict] = None,
) -> StageResult:
    """执行单个测试阶段并返回结果。"""
    cmd_str = " ".join(str(c) for c in command)
    print(f"\n{'=' * 70}")
    print(f"[{name}] 运行: {cmd_str}")
    print(f"{'=' * 70}")

    start = time.time()
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    # Windows 上 npm/node 等命令需要 shell 模式才能解析
    use_shell = command[0] in ("npm", "npx", "node", "pnpm", "yarn") if command else False

    try:
        result = subprocess.run(
            command,
            cwd=str(cwd or PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=proc_env,
            timeout=3600,
            shell=use_shell,
        )
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        return StageResult(
            name=name,
            command=cmd_str,
            exit_code=124,
            duration_sec=duration,
            stdout_tail="TIMEOUT after 3600s",
        )
    except FileNotFoundError as e:
        duration = time.time() - start
        return StageResult(
            name=name,
            command=cmd_str,
            exit_code=127,
            duration_sec=duration,
            stdout_tail=f"命令未找到: {e}",
        )

    duration = time.time() - start
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    combined = stdout + "\n" + stderr

    # 打印末尾输出（便于实时查看，安全处理 Windows GBK 控制台编码）
    tail = "\n".join(combined.splitlines()[-40:])
    try:
        print(tail)
    except UnicodeEncodeError:
        # Windows 控制台 GBK 编码无法输出部分 Unicode 字符，降级为 ASCII
        print(tail.encode("ascii", errors="replace").decode("ascii"))

    stats = _parse_pytest_terminal(combined)
    coverage = _extract_coverage(combined)

    return StageResult(
        name=name,
        command=cmd_str,
        exit_code=result.returncode,
        duration_sec=duration,
        passed=stats["passed"],
        failed=stats["failed"],
        skipped=stats["skipped"],
        errors=stats["errors"],
        coverage_percent=coverage,
        junit_xml=junit_xml,
        stdout_tail=tail,
    )


# ---------------------------------------------------------------------------
# HTML 报告
# ---------------------------------------------------------------------------


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>ODAP 测试报告 - {started_at}</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 24px; color: #222; }}
  h1 {{ color: #1677ff; }}
  h2 {{ margin-top: 32px; border-bottom: 2px solid #1677ff; padding-bottom: 6px; }}
  .summary {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0; }}
  .card {{ padding: 16px 24px; border-radius: 8px; color: #fff; min-width: 120px; text-align: center; }}
  .card.pass {{ background: #52c41a; }}
  .card.fail {{ background: #ff4d4f; }}
  .card.skip {{ background: #faad14; }}
  .card.total {{ background: #1677ff; }}
  .card .num {{ font-size: 28px; font-weight: bold; }}
  .card .label {{ font-size: 12px; opacity: 0.9; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
  th, td {{ border: 1px solid #e8e8e8; padding: 8px 12px; text-align: left; }}
  th {{ background: #fafafa; }}
  tr.ok {{ background: #f6ffed; }}
  tr.bad {{ background: #fff2f0; }}
  code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 12px; }}
  .status-ok {{ color: #52c41a; font-weight: bold; }}
  .status-bad {{ color: #ff4d4f; font-weight: bold; }}
  pre {{ background: #fafafa; padding: 12px; border-radius: 6px; overflow-x: auto; max-height: 200px; font-size: 12px; }}
</style>
</head>
<body>
<h1>ODAP 自动化测试报告</h1>
<p>模式: <code>{mode}</code> &nbsp;|&nbsp; 开始: {started_at} &nbsp;|&nbsp; 结束: {finished_at} &nbsp;|&nbsp; 耗时: {duration} &nbsp;|&nbsp;
   状态: <span class="{status_class}">{status_text}</span></p>

<div class="summary">
  <div class="card total"><div class="num">{total}</div><div class="label">总计</div></div>
  <div class="card pass"><div class="num">{passed}</div><div class="label">通过</div></div>
  <div class="card fail"><div class="num">{failed}</div><div class="label">失败</div></div>
  <div class="card skip"><div class="num">{skipped}</div><div class="label">跳过</div></div>
  <div class="card fail"><div class="num">{errors}</div><div class="label">错误</div></div>
</div>

<h2>阶段明细</h2>
<table>
<tr><th>阶段</th><th>状态</th><th>通过</th><th>失败</th><th>跳过</th><th>错误</th><th>覆盖率</th><th>耗时(s)</th><th>JUnit XML</th></tr>
{stage_rows}
</table>

<h2>失败阶段输出</h2>
{failure_details}

</body>
</html>
"""


def _fmt_duration(sec: float) -> str:
    if sec < 60:
        return f"{sec:.1f}s"
    m, s = divmod(int(sec), 60)
    return f"{m}m{s:02d}s"


def generate_html_report(summary: TestRunSummary) -> Path:
    """生成 HTML 测试报告。"""
    total = sum(s.total for s in summary.stages)
    passed = sum(s.passed for s in summary.stages)
    failed = sum(s.failed for s in summary.stages)
    skipped = sum(s.skipped for s in summary.stages)
    errors = sum(s.errors for s in summary.stages)

    stage_rows = []
    failure_details = []
    for s in summary.stages:
        row_class = "ok" if s.success else "bad"
        status = '<span class="status-ok">PASS</span>' if s.success else '<span class="status-bad">FAIL</span>'
        cov = f"{s.coverage_percent:.1f}%" if s.coverage_percent is not None else "-"
        junit = f'<code>{s.junit_xml}</code>' if s.junit_xml else "-"
        stage_rows.append(
            f'<tr class="{row_class}"><td>{s.name}</td><td>{status}</td>'
            f"<td>{s.passed}</td><td>{s.failed}</td><td>{s.skipped}</td><td>{s.errors}</td>"
            f"<td>{cov}</td><td>{s.duration_sec:.1f}</td><td>{junit}</td></tr>"
        )
        if not s.success:
            failure_details.append(f"<h3>{s.name}</h3><pre>{s.stdout_tail}</pre>")

    html = _HTML_TEMPLATE.format(
        mode=summary.mode,
        started_at=summary.started_at,
        finished_at=summary.finished_at,
        duration=_fmt_duration(summary.total_duration_sec),
        status_class="status-ok" if summary.overall_success else "status-bad",
        status_text="全部通过" if summary.overall_success else "存在失败",
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=errors,
        stage_rows="\n".join(stage_rows),
        failure_details="\n".join(failure_details) or "<p>无失败阶段</p>",
    )

    html_path = REPORT_DIR / "report.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


def generate_json_report(summary: TestRunSummary) -> Path:
    """生成 JSON 测试报告（便于 CI 解析）。"""
    json_path = REPORT_DIR / "report.json"
    data = {
        "mode": summary.mode,
        "started_at": summary.started_at,
        "finished_at": summary.finished_at,
        "total_duration_sec": summary.total_duration_sec,
        "overall_success": summary.overall_success,
        "totals": {
            "passed": sum(s.passed for s in summary.stages),
            "failed": sum(s.failed for s in summary.stages),
            "skipped": sum(s.skipped for s in summary.stages),
            "errors": sum(s.errors for s in summary.stages),
        },
        "stages": [asdict(s) for s in summary.stages],
    }
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


MODES = {
    "smoke": "冒烟测试（核心功能快速验证）",
    "unit": "后端单元测试",
    "regression": "回归测试（核心业务路径）",
    "integration": "集成测试（需外部服务）",
    "e2e": "端到端测试（需后端运行）",
    "perf": "性能基准测试",
    "frontend": "前端测试（vitest）",
    "full": "全量测试（unit + frontend）",
    "all": "全部测试（unit + integration + e2e + perf + frontend）",
}


def _build_stages(mode: str, args) -> list:
    """根据模式返回待执行的阶段配置列表。

    每项为 (stage_name, command, cwd, junit_xml_name)。
    """
    stages = []
    parallel = args.parallel

    if mode == "smoke":
        cmd = build_pytest_command(
            "smoke",
            coverage=args.coverage,
            junit_xml=args.junit_xml,
            parallel=parallel,
        )
        stages.append(("smoke", cmd, PROJECT_ROOT, f"junit-smoke.xml"))
    elif mode == "unit":
        cmd = build_pytest_command(
            "unit", coverage=args.coverage, junit_xml=args.junit_xml, parallel=parallel
        )
        stages.append(("unit", cmd, PROJECT_ROOT, f"junit-unit.xml"))
    elif mode == "regression":
        cmd = build_pytest_command(
            "regression",
            coverage=args.coverage,
            junit_xml=args.junit_xml,
            parallel=parallel,
        )
        stages.append(("regression", cmd, PROJECT_ROOT, f"junit-regression.xml"))
    elif mode == "integration":
        cmd = build_pytest_command(
            "integration",
            coverage=False,
            junit_xml=args.junit_xml,
            parallel=parallel,
        )
        stages.append(("integration", cmd, PROJECT_ROOT, f"junit-integration.xml"))
    elif mode == "e2e":
        cmd = build_pytest_command(
            "e2e", coverage=False, junit_xml=args.junit_xml, parallel=parallel
        )
        stages.append(("e2e", cmd, PROJECT_ROOT, f"junit-e2e.xml"))
    elif mode == "perf":
        cmd = build_pytest_command(
            "perf", coverage=False, junit_xml=args.junit_xml, parallel=parallel
        )
        stages.append(("perf", cmd, PROJECT_ROOT, f"junit-perf.xml"))
    elif mode == "frontend":
        cmd = build_frontend_command(coverage=args.coverage)
        stages.append(("frontend", cmd, PROJECT_ROOT / "frontend", None))
    elif mode == "full":
        cmd = build_pytest_command(
            "unit", coverage=args.coverage, junit_xml=args.junit_xml, parallel=parallel
        )
        stages.append(("unit", cmd, PROJECT_ROOT, f"junit-unit.xml"))
        fe_cmd = build_frontend_command(coverage=args.coverage)
        stages.append(("frontend", fe_cmd, PROJECT_ROOT / "frontend", None))
    elif mode == "all":
        for m, junit_name in [
            ("unit", "junit-unit.xml"),
            ("integration", "junit-integration.xml"),
            ("e2e", "junit-e2e.xml"),
            ("perf", "junit-perf.xml"),
        ]:
            cmd = build_pytest_command(
                m,
                coverage=(args.coverage and m == "unit"),
                junit_xml=args.junit_xml,
                parallel=parallel,
            )
            stages.append((m, cmd, PROJECT_ROOT, junit_name))
        fe_cmd = build_frontend_command(coverage=args.coverage)
        stages.append(("frontend", fe_cmd, PROJECT_ROOT / "frontend", None))

    return stages


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ODAP 统一自动化测试运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(f"  {k:<14}{v}" for k, v in MODES.items()),
    )
    parser.add_argument(
        "mode",
        choices=list(MODES.keys()),
        help="测试模式",
    )
    parser.add_argument(
        "--no-coverage",
        action="store_false",
        dest="coverage",
        default=True,
        help="跳过覆盖率统计",
    )
    parser.add_argument(
        "--no-html",
        action="store_false",
        dest="html",
        default=True,
        help="跳过 HTML 报告生成",
    )
    parser.add_argument(
        "--no-junit-xml",
        action="store_false",
        dest="junit_xml",
        default=True,
        help="跳过 JUnit XML 报告",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=None,
        help="并行进程数（需要 pytest-xdist）",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="失败后继续运行后续阶段",
    )

    args = parser.parse_args()

    _ensure_report_dir()

    summary = TestRunSummary(
        started_at=datetime.now().isoformat(timespec="seconds"),
        mode=args.mode,
    )

    stages = _build_stages(args.mode, args)
    if not stages:
        print(f"未知模式: {args.mode}")
        return 2

    print(f"\nODAP 测试运行器 — 模式: {args.mode} ({MODES[args.mode]})")
    print(f"阶段数: {len(stages)}")
    print(f"报告目录: {REPORT_DIR}")

    overall_start = time.time()
    for stage_name, command, cwd, junit_name in stages:
        junit_path = str(REPORT_DIR / junit_name) if junit_name else None
        result = run_stage(
            stage_name,
            command,
            cwd=cwd,
            junit_xml=junit_path,
        )
        result.junit_xml = junit_name
        summary.add(result)

        if not result.success and not args.keep_going:
            print(f"\n阶段 [{stage_name}] 失败，停止后续阶段（使用 --keep-going 可继续）")
            break

    summary.total_duration_sec = time.time() - overall_start
    summary.finished_at = datetime.now().isoformat(timespec="seconds")

    # 生成报告
    json_path = generate_json_report(summary)
    print(f"\nJSON 报告: {json_path}")

    if args.html:
        html_path = generate_html_report(summary)
        print(f"HTML 报告: {html_path}")

    # 汇总打印
    print(f"\n{'=' * 70}")
    print("测试汇总")
    print(f"{'=' * 70}")
    print(f"{'阶段':<14}{'状态':<8}{'通过':<8}{'失败':<8}{'跳过':<8}{'错误':<8}{'耗时(s)':<10}")
    for s in summary.stages:
        status = "PASS" if s.success else "FAIL"
        print(
            f"{s.name:<14}{status:<8}{s.passed:<8}{s.failed:<8}{s.skipped:<8}{s.errors:<8}{s.duration_sec:<10.1f}"
        )
    print(f"\n总耗时: {_fmt_duration(summary.total_duration_sec)}")
    print(f"总体状态: {'全部通过' if summary.overall_success else '存在失败'}")

    return 0 if summary.overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
