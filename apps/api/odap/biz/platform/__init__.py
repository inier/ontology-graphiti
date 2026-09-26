"""平台领域：工作空间 + 角色 + 技能 + 工具注册 + 会话

本包刻意不做任何再导出（规则 14）。原先这里是五段 `try: import / except Exception: pass`
（含三个 `import *`），全仓库没有任何消费者使用包级名字（实测 `from odap.biz.platform import ...`
零命中）；路由注册也一律走完整子模块路径（见 web/router_registry.py），不依赖这里的再导出。
这些 except 只会把真实的导入故障吞掉，直到很远的调用点才以 AttributeError 暴露。

请直接导入真实路径，例如：
    from odap.biz.platform.tool_registry.registry import ToolRegistry
    from odap.biz.platform.session_memory.session_store import SessionStore
"""

__all__: list = []
