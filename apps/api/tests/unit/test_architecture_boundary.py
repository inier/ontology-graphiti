"""
Architecture Boundary Guard Test

Enforces separation between Design and Application ontology subsystems.
Rules:
 1. Application code MUST NOT import from `odap.biz.core.ontology.design.*`
    EXCEPT through `odap.biz.core.ontology.design.contract.*`.
 2. Design code MUST NOT depend on `application/`.
 3. The contract layer is the only allowed bridge.
 4. Cross-cutting access (read-only ontology queries) goes via design/contract
    or via `odap.infra.query` (the unified semantic query service).
"""
import re
from collections import Counter
from pathlib import Path

# 由本文件位置反推仓库根（tests/unit/x.py → parents[4]）。
# 曾经这里写死 e:\DEMO\AI\ontology-graphiti 且 ONTOLOGY_DIR 少了 apps/api 两级，
# 搬迁后目录不存在 → 两个扫描型用例静默扫 0 个文件"通过"，两个存在性用例报错。
ROOT = Path(__file__).resolve().parents[4]
ONTOLOGY_DIR = ROOT / "apps" / "api" / "odap" / "biz" / "core" / "ontology"
DESIGN_DIR = ONTOLOGY_DIR / "design"
APPLICATION_DIR = ONTOLOGY_DIR / "application"
CONTRACT_DIR = DESIGN_DIR / "contract"

# Application files must NOT use absolute imports of design internals
ABSOLUTE_DESIGN_INTERNAL_IMPORT = re.compile(
    r"from\s+odap\.biz\.core\.ontology\.design\."
    r"(model|engine|version|ingestion|schema|ingestion_split|mock_data|impl|services|storage|interfaces|models)\b"
)

# Design files must NOT use absolute imports of application
ABSOLUTE_APPLICATION_IMPORT = re.compile(
    r"from\s+odap\.biz\.core\.ontology\.application\b"
)

# Design files must NOT reach into application/ via relative paths (..runtime, ..oms, etc.)
RELATIVE_DESIGN_TO_APPLICATION = re.compile(
    r"from\s+\.\.(runtime|servitization|team_agent|oms|abution_graph|harness|api|query_api)\b"
)

# 已知层债棘轮（只减不增，治理方式与 ADR-080 C4 的 ignore_imports 一致）。
#
# 成因：契约层 OntologyDesignContract 目前只暴露只读视图（get_entity_type /
# list_versions / get_ontology ...），没有任何审计写入能力，于是 application/
# 想记审计只能 reach-in design.engine.impl.audit_recorder_impl。
# 这是 2026-09-11 修好本文件写死的旧 ROOT（此前扫描 0 个文件、伪绿灯）后才暴露的
# 存量违规，不是新引入的。
#
# 修法需要先做一个架构决策，故此处冻结现状而不擅自改契约面：
#   (a) 给 OntologyDesignContract 增加 record_audit —— 会改动 ADR-080 治理的公共接口；
#   (b) 改走 odap/infra/security/unified_audit（AGENTS.md 规定的统一审计写入路径）。
# 债还清后必须同步删除对应条目：数量对不上（多或少）都会让用例变红。
KNOWN_APPLICATION_DESIGN_DEBT = {
    "apps/api/odap/biz/core/ontology/application/chat/tools/execution_tool.py": 2,
}


def collect_python_files(directory: Path):
    # 目录不存在必须报错而不是返回空列表：返回 [] 会让调用方的
    # `assert not violations` 在扫描 0 个文件的情况下"通过"（规则 14：禁止静默降级）。
    assert directory.is_dir(), f"架构守卫目标目录不存在（布局已变更？）: {directory}"
    return list(directory.rglob("*.py"))


def test_application_does_not_import_design_internals():
    """Application MUST NOT import design internals — use design.contract only.

    KNOWN_APPLICATION_DESIGN_DEBT 里登记的存量债按"只减不增"棘轮放行；
    数量对不上（新增违规 / 债已还清却没删条目）都会变红。
    """
    app_files = collect_python_files(APPLICATION_DIR)
    found = []

    for f in app_files:
        try:
            content = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        # 统一成正斜杠相对路径，Windows / POSIX 下 key 一致，棘轮才可移植
        rel = f.relative_to(ROOT).as_posix()
        for match in ABSOLUTE_DESIGN_INTERNAL_IMPORT.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            found.append((rel, line_num, match.group(0).strip()))

    observed = Counter(rel for rel, _, _ in found)
    budget = Counter(KNOWN_APPLICATION_DESIGN_DEBT)

    over = {k: v for k, v in observed.items() if v > budget.get(k, 0)}
    stale = {k: v for k, v in budget.items() if observed.get(k, 0) < v}

    details = "\n".join(f"  {rel}:{ln}: {text}" for rel, ln, text in found)
    problems = []
    if over:
        problems.append(
            "超出棘轮额度的新违规（application 不得 reach-in design 内部）：\n"
            + "\n".join(f"  {k}: {v} 处（额度 {budget.get(k, 0)}）" for k, v in sorted(over.items()))
            + "\n  正解：改用 odap.biz.core.ontology.design.contract.get_design_contract()"
        )
    if stale:
        problems.append(
            "棘轮条目已过期（债还清了，必须同步删掉条目，否则额度会被后来者复用）：\n"
            + "\n".join(f"  {k}: 登记 {v} 处，实际 {observed.get(k, 0)} 处" for k, v in sorted(stale.items()))
        )

    assert not problems, (
        "Application code MUST NOT import from design internals.\n\n"
        + "\n\n".join(problems)
        + ("\n\n全部命中：\n" + details if details else "")
    )


def test_design_does_not_import_application():
    """Design MUST NOT depend on application/ (downstream is forbidden)."""
    design_files = collect_python_files(DESIGN_DIR)
    violations = []

    for f in design_files:
        try:
            content = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for match in ABSOLUTE_APPLICATION_IMPORT.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                f"  {f.relative_to(ROOT)}:{line_num}: {match.group(0).strip()}"
            )

        for match in RELATIVE_DESIGN_TO_APPLICATION.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                f"  {f.relative_to(ROOT)}:{line_num}: {match.group(0).strip()}"
            )

    assert not violations, (
        "Design code MUST NOT depend on application/ (upstream may not import downstream).\n\n"
        "Violations:\n" + "\n".join(violations)
    )


def test_contract_layer_exposes_factory():
    """The contract package must export get_design_contract()."""
    init_file = CONTRACT_DIR / "__init__.py"
    assert init_file.exists(), f"Contract init missing: {init_file}"

    content = init_file.read_text(encoding="utf-8")
    assert "get_design_contract" in content, (
        "Contract layer must expose get_design_contract() factory"
    )
    assert "OntologyDesignContract" in content, (
        "Contract layer must expose OntologyDesignContract interface"
    )


def test_contract_interface_defines_immutable_views():
    """View types exposed via contract must be @dataclass(frozen=True)."""
    interface_file = CONTRACT_DIR / "interface.py"
    assert interface_file.exists(), f"Interface file missing: {interface_file}"

    content = interface_file.read_text(encoding="utf-8")
    view_classes = [
        "EntityTypeView",
        "RelationTypeView",
        "PropertyView",
        "OntologyVersionView",
        "OntologyDocumentView",
    ]
    for cls in view_classes:
        # Find "@dataclass(...)" decorator and the class header that follows
        # The class may have multi-line decorator (e.g., @dataclass(...)
        # plus nested @field stuff). We just check that "frozen" appears
        # in the same "decorator block" before the class.
        class_idx = content.find(f"class {cls}")
        assert class_idx > 0, f"View class {cls} not found in interface.py"
        # Look back at most 500 chars for the @dataclass decorator
        prefix = content[max(0, class_idx - 500):class_idx]
        last_dataclass = prefix.rfind("@dataclass")
        assert last_dataclass >= 0, (
            f"View class {cls} is missing @dataclass decorator"
        )
        decorator_text = prefix[last_dataclass:]
        assert "frozen" in decorator_text, (
            f"View class {cls} MUST be @dataclass(frozen=True). "
            f"Found decorator: {decorator_text[:120]!r}"
        )
