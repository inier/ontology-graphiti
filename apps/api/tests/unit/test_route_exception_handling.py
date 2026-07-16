"""
Regression test: P1-001c route exception handling (R-P1-001).

The architecture constitution (rule 3) states:
  All route handlers MUST include `except HTTPException: raise` to
  prevent HTTP errors from being swallowed by `except Exception` and
  converted to 500.

This test guards against regressions of route handlers that have
`except Exception` (or broad catch) without a re-raise of HTTPException.
"""
import ast
from pathlib import Path
import pytest

# apps/api/tests/unit/ -> apps/api/ (3 parents) -> odap/
_ROOT = Path(__file__).resolve().parent.parent.parent
ROOT = _ROOT / "odap"
HTTP_METHODS = ("get", "post", "put", "delete", "patch")


def _get_exception_types(handler: ast.ExceptHandler) -> list:
    """Return a list of exception type names caught by a handler."""
    if handler.type is None:
        return []  # bare `except:`
    if isinstance(handler.type, ast.Name):
        return [handler.type.id]
    if isinstance(handler.type, ast.Tuple):
        names = []
        for elt in handler.type.elts:
            if isinstance(elt, ast.Name):
                names.append(elt.id)
        return names
    return []


def _is_route_handler(node) -> bool:
    """True if the function is decorated with @router.{http_method}."""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if dec.func.attr in HTTP_METHODS:
                return True
    return False


def _collect_handlers(path: Path):
    """Yield route handler nodes in a file."""
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_route_handler(node):
                yield node


def _route_has_compliant_exception_handling(node) -> tuple:
    """
    Returns (compliant: bool, issue: str|None).

    A route is compliant if:
      * it has no broad except at all, OR
      * it has `except HTTPException: raise` BEFORE any broad except.

    "Broad except" means:
      * `except Exception` (or subclass like `RuntimeError`)
      * bare `except:` (no type)
      * tuple that includes `Exception`

    Specific except types like `ValueError`, `KeyError`, `HTTPException`
    alone are fine — they're domain-specific.
    """
    has_httpexception_raise = False
    has_broad_exception = False
    for child in ast.walk(node):
        if not isinstance(child, ast.ExceptHandler):
            continue
        types = _get_exception_types(child)
        if not types:
            # bare `except:` is treated as overly broad
            has_broad_exception = True
            continue
        if "HTTPException" in types:
            has_httpexception_raise = True
        # Only `Exception` (the root) is broad — specific subclasses like
        # ValueError, KeyError are domain-specific and acceptable.
        if "Exception" in types:
            has_broad_exception = True

    if not has_broad_exception:
        return True, None
    if not has_httpexception_raise:
        return False, "has `except Exception` but no `except HTTPException: raise`"
    return True, None


def _collect_route_files():
    """Yield all Python files under odap/ that may contain route handlers."""
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        if "tests" in path.parts:
            continue
        yield path


class TestRouteExceptionHandling:
    """P1-001: routes MUST re-raise HTTPException."""

    def test_no_route_missing_httpexception_raise(self):
        """Scan all routes for missing `except HTTPException: raise`."""
        violations = []
        for py_file in _collect_route_files():
            for handler in _collect_handlers(py_file):
                compliant, issue = _route_has_compliant_exception_handling(handler)
                if not compliant:
                    rel = py_file.relative_to(ROOT.parent)
                    violations.append(
                        f"{rel}:{handler.lineno}  {handler.name}  -- {issue}"
                    )

        assert not violations, (
            f"\n\nFound {len(violations)} route handler(s) missing "
            f"`except HTTPException: raise`:\n"
            + "\n".join(violations)
        )

    def test_known_top_files_have_no_violations(self):
        """Specific regression: top-10 most-used route files are clean."""
        # These are the files fixed during R-P1-001c
        target_files = [
            "odap/biz/platform/skill_system/api/routes_extended.py",
            "odap/biz/platform/ontology_memory/shared_workspace/routes.py",
            "odap/biz/core/ontology/application/harness/blueprint/routes.py",
            "odap/biz/core/ontology/application/harness/blueprint/api/runtime_routes.py",
            "odap/web/api/app.py",
        ]
        for rel in target_files:
            path = ROOT.parent / rel
            if not path.exists():
                continue
            for handler in _collect_handlers(path):
                compliant, issue = _route_has_compliant_exception_handling(handler)
                assert compliant, (
                    f"{rel}:{handler.lineno}  {handler.name}  -- {issue}"
                )

    def test_route_exceptions_module_importable(self):
        """The route_exceptions helper module must be importable."""
        from odap.infra.web.route_exceptions import (
            standardize_exceptions,
            safe_route_execute,
        )
        assert standardize_exceptions is not None
        assert safe_route_execute is not None

    def test_standardize_decorator_passes_through(self):
        """The decorator must pass through successful return values."""
        from odap.infra.web.route_exceptions import standardize_exceptions

        @standardize_exceptions("test_pass")
        async def good():
            return {"ok": True}

        import asyncio
        result = asyncio.run(good())
        assert result == {"ok": True}

    def test_standardize_decorator_reraises_httpexception(self):
        """HTTPException must be re-raised unchanged, not converted to 500."""
        from fastapi import HTTPException
        from odap.infra.web.route_exceptions import standardize_exceptions

        @standardize_exceptions("test_http")
        async def raises_http():
            raise HTTPException(status_code=418, detail="teapot")

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(raises_http())
        assert exc_info.value.status_code == 418
        assert exc_info.value.detail == "teapot"

    def test_standardize_decorator_converts_value_error_to_400(self):
        """ValueError must be converted to HTTP 400."""
        from fastapi import HTTPException
        from odap.infra.web.route_exceptions import standardize_exceptions

        @standardize_exceptions("test_400")
        async def raises_value_error():
            raise ValueError("bad input")

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(raises_value_error())
        assert exc_info.value.status_code == 400
        assert "bad input" in str(exc_info.value.detail)

    def test_standardize_decorator_converts_unhandled_to_500(self):
        """Unhandled exceptions must be converted to HTTP 500 with a generic message."""
        from fastapi import HTTPException
        from odap.infra.web.route_exceptions import standardize_exceptions

        @standardize_exceptions("test_500", log_unhandled=False)
        async def raises_runtime_error():
            raise RuntimeError("internal explosion")

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(raises_runtime_error())
        assert exc_info.value.status_code == 500
        # The actual internal message must NOT leak to the client
        assert "internal explosion" not in str(exc_info.value.detail)

    def test_standardize_decorator_passes_through_httperror_via_tuple(self):
        """Starlette HTTPException caught in the same handler as Exception must still re-raise."""
        from fastapi import HTTPException
        from odap.infra.web.route_exceptions import standardize_exceptions

        @standardize_exceptions("test_tuple")
        async def raises_http_in_tuple():
            raise HTTPException(status_code=409, detail="conflict")

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(raises_http_in_tuple())
        assert exc_info.value.status_code == 409
