"""集成领域：OpenHarness + MCP + Hook + 前端兼容"""

try:
    from odap.biz.integration.openharness_agent import router as openharness_router
except Exception:
    pass

try:
    from odap.biz.integration.mcp_adapter import MCPService
except Exception:
    pass

try:
    from odap.biz.integration.mcp_adapter.mcp_server_manager import MCPServerManagerV2
except Exception:
    pass

try:
    from odap.biz.integration.hook_system import HookService
except Exception:
    pass

try:
    from odap.biz.integration.hook_system.hook_manager_enhanced import EnhancedHookManager
except Exception:
    pass

__all__ = []
