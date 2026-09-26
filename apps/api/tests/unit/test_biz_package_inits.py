"""biz 包 __init__ 的幻影导入 / 静默吞异常回归测试。

背景：odap/biz 下几乎每个领域的 __init__.py 都曾是一整墙
`try: from ... import X / except Exception: pass`，配一个空的 `__all__ = []`。
这个形态有两个后果：

  1. 幻影模块可以长期存活 —— `odap.biz.data.qa.qa_engine_v2` 根本不存在
     （真实模块是 qa_engine，QAEngineV2 是其中的类），ModuleNotFoundError 被吞掉，
     包照常导入成功，没人发现。
  2. 真实的导入故障也会被吞 —— 例如 openharness 路由导入失败会让整段 API 表面
     消失，而应用照常启动。

经全仓核实这些包级名字零消费者（`from odap.biz.<domain> import ...` 全部零命中），
路由注册也一律走 web/router_registry.py 的完整子模块路径且不带 try/except，
因此已整体移除。本文件负责防止复发。
"""

import ast
import importlib
import pathlib

import pytest

import odap

BIZ_ROOT = pathlib.Path(odap.__file__).parent / "biz"


def _bare_except_pass_blocks(tree: ast.AST):
    """找出所有 `except ...: pass`（handler 体只有 Pass）的 Try 节点。"""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                wraps_import = any(
                    isinstance(stmt, (ast.Import, ast.ImportFrom)) for stmt in node.body
                )
                found.append((node.lineno, wraps_import))
    return found


# ---------------------------------------------------------------------------
# 防复发棘轮：biz/**/__init__.py 中不允许再有 except-pass
# ---------------------------------------------------------------------------

class TestNoSilentImportSwallow:
    def test_no_bare_except_pass_in_any_biz_package_init(self):
        """零容忍棘轮。

        刻意只扫 __init__.py：包初始化处的 `except: pass` 只会把导入故障藏起来，
        没有任何正当用途；业务代码里的异常处理不在此约束范围内。
        """
        init_files = sorted(BIZ_ROOT.rglob("__init__.py"))
        assert init_files, f"未找到任何 biz __init__.py，扫描根目录是否失效: {BIZ_ROOT}"

        violations = []
        for path in init_files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for lineno, wraps_import in _bare_except_pass_blocks(tree):
                kind = "导入" if wraps_import else "语句"
                violations.append(f"{path.relative_to(BIZ_ROOT.parent)}:{lineno} ({kind}被静默吞掉)")

        assert not violations, (
            "biz 包 __init__.py 中检测到 `except ...: pass` 静默吞异常（违反 AGENTS.md 规则 14）：\n  "
            + "\n  ".join(violations)
            + "\n包级再导出要么直接导入（失败即炸），要么删掉；不要吞。"
        )

    def test_scan_actually_covers_the_changed_packages(self):
        """守卫：棘轮必须真的覆盖到本次清理的那几个包，否则形同虚设。"""
        relative = {
            str(p.relative_to(BIZ_ROOT)).replace("\\", "/")
            for p in BIZ_ROOT.rglob("__init__.py")
        }
        for expected in (
            "data/__init__.py",
            "simulation/__init__.py",
            "simulation/simulation_deduction/__init__.py",
            "platform/__init__.py",
            "integration/__init__.py",
            "core/__init__.py",
        ):
            assert expected in relative, f"棘轮未覆盖 biz/{expected}"


# ---------------------------------------------------------------------------
# 幻影模块本身
# ---------------------------------------------------------------------------

class TestPhantomQaEngineV2:
    def test_phantom_module_does_not_exist(self):
        """qa_engine_v2 从来就不存在 —— 别让它被"恢复"成一条看似合理的导入。"""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("odap.biz.data.qa.qa_engine_v2")

    def test_real_class_lives_in_qa_engine(self):
        """真实位置：模块名 qa_engine，类名 QAEngineV2（命名错位是幻影的成因）。"""
        from odap.biz.data.qa.qa_engine import QAEngineV2

        assert QAEngineV2.__name__ == "QAEngineV2"

    def test_biz_data_package_no_longer_reexports_it(self):
        import odap.biz.data as data_pkg

        assert not hasattr(data_pkg, "QAEngineV2")
        assert data_pkg.__all__ == []


# ---------------------------------------------------------------------------
# 清理不得过度：真实能力必须仍可从真实路径导入
# ---------------------------------------------------------------------------

class TestRealPathsStillImportable:
    @pytest.mark.parametrize("module_path,attr", [
        ("odap.biz.data.perception.hub", "PerceptionHub"),
        ("odap.biz.data.data_warehouse.query_service", "QueryService"),
        ("odap.biz.simulation.feedback.loop", "FeedbackLoop"),
        ("odap.biz.simulation.visualization.visualization_engine", "VisualizationEngineV2"),
        ("odap.biz.simulation.simulation_deduction.services", "DeductionService"),
        ("odap.biz.simulation.simulation_deduction.api", "router"),
        ("odap.biz.platform.tool_registry.registry", "ToolRegistry"),
        ("odap.biz.platform.session_memory.session_store", "SessionStore"),
        ("odap.biz.integration.mcp_adapter", "MCPService"),
        ("odap.biz.integration.mcp_adapter.mcp_server_manager", "MCPServerManagerV2"),
        ("odap.biz.integration.hook_system", "HookService"),
        ("odap.biz.integration.hook_system.hook_manager_enhanced", "EnhancedHookManager"),
        ("odap.biz.core.cognition.user_cognition_engine", "get_cognition_engine"),
    ])
    def test_symbol_reachable_at_real_path(self, module_path, attr):
        module = importlib.import_module(module_path)
        assert hasattr(module, attr), f"{module_path}.{attr} 不可达 —— 清理时误删了真实能力"

    def test_integration_routers_reachable_via_registry_paths(self):
        """路由注册走的是这些完整路径，必须保持可用（AGENTS.md 规则 1）。"""
        for module_path in (
            "odap.biz.integration.openharness_agent.api.routes",
            "odap.biz.integration.mcp_adapter.api.routes",
            "odap.biz.integration.hook_system.api.routes",
            "odap.biz.integration.frontend_compat.api.routes",
        ):
            module = importlib.import_module(module_path)
            assert hasattr(module, "router"), f"{module_path} 缺少 router"


# ---------------------------------------------------------------------------
# ADR-065 契约不得被误删
# ---------------------------------------------------------------------------

class TestSimulationContractsPreserved:
    def test_interfaces_still_exported_from_package(self):
        """这四个是 simulation 包对外的稳定面，属于有意保留的无保护直接导入。"""
        import odap.biz.simulation as sim_pkg

        for name in ("IOMSService", "IModelService", "IRuntimeService", "IHookService"):
            assert hasattr(sim_pkg, name), f"ADR-065 契约 {name} 被误删"
            assert name in sim_pkg.__all__

    def test_domain_packages_import_cleanly(self):
        """移除再导出后，各领域包本身仍必须能干净导入。"""
        for module_path in (
            "odap.biz.data",
            "odap.biz.simulation",
            "odap.biz.simulation.simulation_deduction",
            "odap.biz.platform",
            "odap.biz.integration",
        ):
            assert importlib.import_module(module_path) is not None

        # simulation 刻意保留 ADR-065 四个契约，其余包声明的再导出应为零
        for module_path in (
            "odap.biz.data",
            "odap.biz.simulation.simulation_deduction",
            "odap.biz.platform",
            "odap.biz.integration",
        ):
            module = importlib.import_module(module_path)
            assert module.__all__ == [], f"{module_path} 声明了再导出但本文件假定其为零"
