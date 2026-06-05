"""WebSocket 事件总线 — 从 infra 层重新导出

保持向后兼容：odap.web.ws.event_bus 仍可导入，
但实际定义在 odap.infra.events.event_bus 中。
"""
from odap.infra.events.event_bus import DomainEventBus, get_event_bus, event_bus  # noqa: F401

__all__ = ['DomainEventBus', 'get_event_bus', 'event_bus']
