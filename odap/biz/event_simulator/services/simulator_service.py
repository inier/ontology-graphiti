"""事件模拟器服务"""

from typing import Dict, Any, List
from datetime import datetime
import random
from ..models.event import EventTemplate, GeneratedEvent, TimeControl


class EventSimulatorService:
    """事件模拟器服务"""
    
    def __init__(self):
        self._templates: Dict[str, EventTemplate] = {}
        self._events: List[GeneratedEvent] = []
        self._time_control = TimeControl()
    
    def create_template(self, name: str, event_type: str, 
                      description: str = "", 
                      schema: Dict[str, Any] = None) -> Dict[str, Any]:
        """创建模板"""
        template = EventTemplate(
            name=name,
            event_type=event_type,
            description=description,
            schema=schema or {}
        )
        self._templates[template.id] = template
        
        return {
            "template_id": template.id,
            "name": template.name,
            "event_type": template.event_type
        }
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """列出模板"""
        return [
            {
                "template_id": t.id,
                "name": t.name,
                "event_type": t.event_type
            }
            for t in self._templates.values()
        ]
    
    def generate_event(self, template_id: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成事件"""
        template = self._templates.get(template_id)
        if not template:
            return {"status": "error", "message": "Template not found"}
        
        event = GeneratedEvent(
            template_id=template_id,
            event_type=template.event_type,
            data=data or {}
        )
        self._events.append(event)
        
        return {
            "event_id": event.id,
            "template_id": event.template_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat()
        }
    
    def list_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出事件"""
        return [
            {
                "event_id": e.id,
                "event_type": e.event_type,
                "timestamp": e.timestamp.isoformat()
            }
            for e in self._events[-limit:]
        ]
    
    def set_time_control(self, speed: float = 1.0, is_paused: bool = False) -> Dict[str, Any]:
        """设置时间控制"""
        self._time_control.simulation_speed = speed
        self._time_control.is_paused = is_paused
        
        return {
            "simulation_speed": self._time_control.simulation_speed,
            "is_paused": self._time_control.is_paused
        }
    
    def get_time_control(self) -> Dict[str, Any]:
        """获取时间控制"""
        return {
            "simulation_speed": self._time_control.simulation_speed,
            "current_time": self._time_control.current_time.isoformat(),
            "is_paused": self._time_control.is_paused
        }
