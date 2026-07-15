"""ODAP Root Package

延迟属性解析：`from odap import web` 或 `odap.web.xxx` 时才真正 import 子模块，
避免 odap 根导入触发整个 FastAPI app/openharness.tools 链，
导致纯逻辑模块（如 FCA、规则分类器、关系抽取器）也因 openharness 缺失而无法 import。

test_web_app.py 等需要 `odap.web` 属性存在的代码，显式 `import odap.web` 即可。
"""

from __future__ import annotations as _annotations

__getattr__ = None  # type: ignore[assignment]


def __getattr_impl(name: str):  # noqa: N807
    if name == "web":
        import importlib
        return importlib.import_module("odap.web")
    raise AttributeError(f"module 'odap' has no attribute {name!r}")


__getattr__ = __getattr_impl  # type: ignore[assignment]
del __getattr_impl
