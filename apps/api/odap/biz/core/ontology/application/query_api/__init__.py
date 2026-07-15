"""
查询 API 模块（包含：数据摄入路由 + 自然语言查询路由）。

为保持向后兼容，`routes` 模块（实际是摄入 API）使用延迟导入，
避免在 import 阶段就触发历史遗留的相对路径问题。
"""
__all__ = ['router', 'nl_router']


def __getattr__(name):
    if name == 'router':
        from .routes import router
        return router
    if name == 'nl_router':
        from .nl_routes import router
        return router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
