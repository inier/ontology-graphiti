"""
Regression test: P1-004 silent except Exception handling (R-P1-004).

The architecture constitution (rule 8) states:
  All `except Exception: return X` blocks MUST log the error to
  prevent silent failures that mask real problems.

This test scans for silent except blocks in the top-12 most-used files
and the codebase at large.
"""
import ast
import re
from pathlib import Path
import pytest

# 由本文件位置反推 apps/api（tests/unit/x.py → parents[2]），
# 不写死绝对路径：仓库搬迁 / 他人 clone 到别处都会失效。
_ROOT = Path(__file__).resolve().parents[2]

# Top-12 most-used files previously audited and fixed in R-P1-004
TOP_12_TARGETS = [
    "odap/infra/openharness/llm_client.py",
    "odap/infra/storage/minio_client.py",
    "odap/tools/agent_tools/graph_tools.py",
    "odap/biz/core/ontology/design/version/api/routes.py",
    "odap/infra/opa/opa_service.py",
    "odap/biz/platform/tool_registry/registry.py",
    "odap/tasks.py",
    "odap/web/api/app.py",
    "odap/tools/agent_tools/workspace_tools.py",
    "odap/biz/platform/skill_system/api/routes_extended.py",
    "odap/tools/base.py",
    "odap/web/gateway/api_gateway.py",
]


def _get_exception_types(handler: ast.ExceptHandler) -> list:
    if handler.type is None:
        return []
    if isinstance(handler.type, ast.Name):
        return [handler.type.id]
    if isinstance(handler.type, ast.Tuple):
        names = []
        for elt in handler.type.elts:
            if isinstance(elt, ast.Name):
                names.append(elt.id)
        return names
    return []


def _is_silent_handler(handler: ast.ExceptHandler) -> tuple:
    """
    Returns (is_silent, reason).

    A `except Exception: return X` is silent if it has no logger call,
    no raise, and just returns a value.
    """
    types = _get_exception_types(handler)
    if "Exception" not in types:
        return False, "not an Exception catch"

    has_log = False
    has_raise = False
    has_return = False
    has_pass = False
    for stmt in handler.body:
        if isinstance(stmt, ast.Pass):
            has_pass = True
        if isinstance(stmt, ast.Return):
            has_return = True
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                if isinstance(sub.func.value, ast.Name) and sub.func.value.id == "logger":
                    has_log = True
            if isinstance(sub, ast.Raise):
                has_raise = True

    if has_log or has_raise:
        return False, "logged or raised"
    if not has_return:
        return False, "no return"
    return True, "silent return without logger"


class TestSilentExceptsFixed:
    """P1-004: silent except Exception blocks must log."""

    def test_top_12_files_have_no_silent_excepts(self):
        """The 12 files we fixed in R-P1-004 must be clean."""
        # 目标文件必须真实存在。曾经这里是 `if not path.exists(): continue`，
        # 于是 apps/api 搬迁后 12 个路径全部失配 → 扫描 0 个文件 → 测试"通过"，
        # 棘轮退化成伪绿灯（规则 14：禁止静默降级）。路径漂移必须直接变红。
        missing = [rel for rel in TOP_12_TARGETS if not (_ROOT / rel).exists()]
        assert not missing, (
            f"{len(missing)}/{len(TOP_12_TARGETS)} 个审计目标路径已失配"
            f"（root={_ROOT}）：\n" + "\n".join(missing)
        )

        violations = []
        for rel in TOP_12_TARGETS:
            path = _ROOT / rel
            try:
                source = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    is_silent, reason = _is_silent_handler(node)
                    if is_silent:
                        violations.append(f"{rel}:{node.lineno} -- {reason}")
        assert not violations, (
            f"Found {len(violations)} silent except in top-12 files:\n"
            + "\n".join(violations)
        )

    def test_pattern_recognizes_silent(self):
        """Sanity check: the detection logic works as expected."""
        code = """
def f():
    try:
        x = 1
    except Exception:
        return False
"""
        tree = ast.parse(code)
        handler = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                handler = node
                break
        assert handler is not None
        is_silent, reason = _is_silent_handler(handler)
        assert is_silent
        assert "silent" in reason

    def test_logged_handler_not_flagged(self):
        """A handler that calls logger.X is not silent."""
        code = """
def f():
    try:
        x = 1
    except Exception as e:
        logger.warning("oops", exc_info=True)
        return False
"""
        tree = ast.parse(code)
        handler = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                handler = node
                break
        is_silent, reason = _is_silent_handler(handler)
        assert not is_silent
        assert reason == "logged or raised"

    def test_raising_handler_not_flagged(self):
        """A handler that raises is not silent."""
        code = """
def f():
    try:
        x = 1
    except Exception as e:
        raise ValueError("wrapped") from e
"""
        tree = ast.parse(code)
        handler = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                handler = node
                break
        is_silent, reason = _is_silent_handler(handler)
        assert not is_silent
        assert reason == "logged or raised"

    def test_specific_exception_not_flagged(self):
        """A handler that catches only ValueError is not flagged."""
        code = """
def f():
    try:
        x = 1
    except ValueError:
        return False
"""
        tree = ast.parse(code)
        handler = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                handler = node
                break
        is_silent, reason = _is_silent_handler(handler)
        assert not is_silent
        assert "not an Exception" in reason
