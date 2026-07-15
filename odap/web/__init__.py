"""Web Layer

延迟属性解析：`odap.web.app` 被访问时才真正 import app 模块，
避免 import odap.web → router_registry.create_router_registry() → 加载所有路由 → openharness.tools 缺包。

对于需要 odap.web.app 属性存在的场景（test_web_app.py 、odap.web.app attribute assertion 等），
显式 `from odap.web import app` 即可。
"""

from __future__ import annotations as _annotations

__getattr__ = None  # type: ignore[assignment]


def __getattr_impl(name: str):  # noqa: N807
    if name == "app":
        import importlib
        return importlib.import_module("odap.web.app")
    if name == "api":
        import importlib
        return importlib.import_module("odap.web.api")
    if name == "gateway":
        import importlib
        return importlib.import_module("odap.web.gateway")
    if name == "ws":
        import importlib
        return importlib.import_module("odap.web.ws")
    raise AttributeError(f"module 'odap.web' has no attribute {name!r}")


__getattr__ = __getattr_impl  # type: ignore[assignment]
del __getattr_impl
