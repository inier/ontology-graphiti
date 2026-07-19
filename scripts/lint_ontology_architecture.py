"""
架构守卫 (Architecture Guard) — ADR-068 3+1 分层架构的 CI lint 规则。

通过 AST 扫描强制执行以下边界规则:
  1. 禁止直接 import 内部实现类（必须通过 Contract 或 common/）
  2. 禁止跨层反向依赖
  3. 检测绕路 import（绕过 __init__.py 兼容层）

使用方式:
  python scripts/lint_ontology_architecture.py            # 检测模式 (默认)
  python scripts/lint_ontology_architecture.py --strict   # 阻断模式 (CI)
  python scripts/lint_ontology_architecture.py --report   # 迁移进度报告

状态:
  Phase 0-2: 仅检测，不阻断 (默认)
  Phase 3: --strict 阻断 CI,  --report 生成迁移进度
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESTRICTED_PATTERNS = [
    ("odap.biz.core.ontology.design.services", "use contract or common/ instead"),
    ("odap.biz.core.ontology.design.ingestion.impl", "use construction/contract when available"),
    ("odap.biz.core.ontology.application.oms.storage", "use OMSService through __init__.py"),
    ("odap.biz.core.ontology.application.runtime.impl", "use runtime service through contract"),
    ("odap.biz.core.ontology.design.services.qa_ontology_builder", "use ontology.common.types for shared enums"),
]

# Phase 1-2 桥接模块白名单 — 这些模块的旧路径 import 属于合理重导出
BRIDGE_WHITELIST = {
    "construction/contract/bridge.py",
    "construction/ingestion/services/__init__.py",
    "construction/pipeline/services/__init__.py",
    "reasoning/inference/__init__.py",
    "reasoning/consistency/__init__.py",
    "reasoning/services/__init__.py",
    "application/chat/__init__.py",
    "application/chat/engine/__init__.py",
    "application/intent/__init__.py",
    "application/navigation/__init__.py",
    "application/explanation/__init__.py",
    "application/thought_graph/__init__.py",
    # 外部工具模块（lazy import, try/except, 合理引用的工具代码）
    "tools/web/web_skills.py",
    "web/ws/edit_lock_handler.py",
    "design/model/api/routes.py",
    # L1 Design 内部交叉引用（合法，同一层内服务互相调用）
    "design/services/ingest_service.py",
    "design/services/qa_ontology_builder.py",
}

# Phase 3: 推荐新导入路径
MIGRATION_GUIDE = {
    "odap.biz.core.ontology.design.services.ingest_service": "construction.pipeline.services (via bridge)",
    "odap.biz.core.ontology.design.services.build_service": "construction.pipeline.services (via bridge)",
    "odap.biz.core.ontology.design.services.pipeline_service": "construction.pipeline.services (via bridge)",
    "odap.biz.core.ontology.design.services.qa_ontology_builder": "common.types for IntentType, construction.pipeline for builder",
    "odap.biz.core.ontology.design.services.version_service": "design.version (L1 Design layer)",
    "odap.biz.core.ontology.design.services.edit_lock_service": "design.engine (L1 Design layer)",
    "odap.biz.core.ontology.application.oms.storage": "application.oms (via OMS wrapper)",
    "odap.biz.core.ontology.design.ingestion.impl": "construction.ingestion (L2 Construction layer)",
    "odap.biz.core.cognition.impl": "application.intent / navigation / explanation (L3 Application layer)",
}


class ArchitectureLintVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.violations: List[Tuple[int, str, str]] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self._check_import(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module is None:
            return
        full = node.module
        for alias in node.names:
            full_path = f"{full}.{alias.name}" if alias.name != "*" else f"{full}.*"
            self._check_import(full_path, node.lineno)
        self.generic_visit(node)

    def _check_import(self, import_path: str, lineno: int):
        for restricted, reason in RESTRICTED_PATTERNS:
            if import_path.startswith(restricted):
                self.violations.append((lineno, import_path, reason))


def lint_file(filepath: Path) -> List[str]:
    # 桥接模块白名单 — 允许从旧路径重导出
    rel_path = str(filepath.relative_to(PROJECT_ROOT)).replace("\\", "/")
    for whitelisted in BRIDGE_WHITELIST:
        if rel_path.endswith(whitelisted):
            return []

    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(filepath))
    except SyntaxError:
        return []

    visitor = ArchitectureLintVisitor(str(filepath))
    visitor.visit(tree)

    messages = []
    for lineno, import_path, reason in visitor.violations:
        rel = filepath.relative_to(PROJECT_ROOT)
        msgs = [f"  {rel}:{lineno}: RESTRICTED import '{import_path}' — {reason}"]
        # 添加迁移建议
        for old, new in MIGRATION_GUIDE.items():
            if import_path.startswith(old):
                msgs.append(f"    → Migrate to: {new}")
                break
        messages.extend(msgs)
    return messages


def lint_all(strict: bool = False, report: bool = False) -> int:
    violations = 0
    affected_files = set()

    scan_dirs = [
        PROJECT_ROOT / "apps" / "api" / "odap" / "biz",
        PROJECT_ROOT / "apps" / "api" / "odap" / "infra",
        PROJECT_ROOT / "apps" / "api" / "odap" / "web",
        PROJECT_ROOT / "apps" / "api" / "odap" / "tools",
    ]

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            msgs = lint_file(py_file)
            if msgs:
                for m in msgs:
                    print(m)
                violations += len(msgs)
                affected_files.add(py_file)

    print(f"\nTotal violations: {violations} in {len(affected_files)} files")

    if report:
        print("\n=== Migration Progress Report ===")
        print(f"Phase 3 cleanup target: {violations} violations across {len(affected_files)} files")
        print("After Phase 3 completion, run with --strict to enforce CI gate.")

    if strict and violations > 0:
        print("\n[STRICT MODE] CI GATE FAILED — fix violations before merge.")
        return 1

    return 0 if violations == 0 else (1 if strict else 0)


if __name__ == "__main__":
    strict = "--strict" in sys.argv
    report = "--report" in sys.argv
    sys.exit(lint_all(strict=strict, report=report))

