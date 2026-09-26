"""集成领域：OpenHarness + MCP + Hook + 前端兼容

本包刻意不做任何再导出（规则 14）。原先这里是五段 `try: import / except Exception: pass`，
全仓库没有任何消费者使用包级名字（实测 `from odap.biz.integration import ...` 零命中）。

这里风险最高的一处是 `from .openharness_agent import router as openharness_router`：
路由导入被静默吞掉就意味着整段 API 表面消失，而应用照常启动、/docs 照常返回。
实际路由注册一律走 web/router_registry.py 里的完整子模块路径且不带 try/except，
导入失败会在启动时直接炸出来，不依赖本文件。

请直接导入真实路径，例如：
    from odap.biz.integration.mcp_adapter import MCPService
    from odap.biz.integration.hook_system import HookService
"""

__all__: list = []
