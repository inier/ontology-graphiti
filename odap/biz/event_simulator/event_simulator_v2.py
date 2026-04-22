"""
事件模拟器 v2 - Event Simulator
WR-10: 事件模拟器 (模板管理 + 时间控制 + 与推演集成)

功能：
- 事件模板管理
- 自动/手动事件生成
- 时间控制（加速、减速、暂停、跳转）
- 事件序列编排
- 与推演引擎集成
"""

import sys
import os
import json
import time
import random
import threading
import asyncio
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid
import hashlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class EventStatus(Enum):
    """事件状态"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class EventPriority(Enum):
    """事件优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TimeControlMode(Enum):
    """时间控制模式"""
    REAL_TIME = "real_time"
    FAST_FORWARD = "fast_forward"
    SLOW_MOTION = "slow_motion"
    PAUSED = "paused"
    JUMP_TO = "jump_to"


@dataclass
class EventParameter:
    """事件参数定义"""
    name: str
    type: str
    description: str = ""
    default: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    options: List[Any] = None
    required: bool = True


@dataclass
class EventTemplateV2:
    """事件模板 v2"""
    template_id: str
    name: str
    description: str
    event_type: str
    category: str
    parameters: List[EventParameter] = field(default_factory=list)
    default_values: Dict[str, Any] = field(default_factory=dict)
    probability: float = 1.0
    cooldown_seconds: float = 0
    max_instances: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    version: str = "1.0.0"
    enabled: bool = True

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "event_type": self.event_type,
            "category": self.category,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "default": p.default,
                    "required": p.required
                }
                for p in self.parameters
            ],
            "probability": self.probability,
            "cooldown_seconds": self.cooldown_seconds,
            "max_instances": self.max_instances,
            "version": self.version,
            "enabled": self.enabled
        }


@dataclass
class GeneratedEventV2:
    """生成的事件 v2"""
    event_id: str
    template_id: str
    template_name: str
    event_type: str
    timestamp: str
    scheduled_time: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    status: EventStatus = EventStatus.PENDING
    priority: EventPriority = EventPriority.NORMAL
    source: str = "manual"
    correlation_id: Optional[str] = None
    execution_time_ms: float = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class EventSequence:
    """事件序列"""
    sequence_id: str
    name: str
    description: str
    events: List[Dict[str, Any]]
    trigger_condition: Optional[str] = None
    loop_count: int = 1
    enabled: bool = True


@dataclass
class TimeState:
    """时间状态"""
    mode: TimeControlMode
    current_time: datetime
    start_time: datetime
    speed: float = 1.0
    simulation_start: datetime = None
    is_running: bool = False
    tick_count: int = 0

    def __post_init__(self):
        if not self.simulation_start:
            self.simulation_start = datetime.now(timezone.utc)


class EventTemplateManager:
    """事件模板管理器"""

    def __init__(self):
        self._templates: Dict[str, EventTemplateV2] = {}
        self._categories: Dict[str, List[str]] = {}
        self._type_index: Dict[str, List[str]] = {}
        self._lock = threading.RLock()

    def register_template(self, template: EventTemplateV2) -> bool:
        """注册事件模板"""
        with self._lock:
            self._templates[template.template_id] = template

            if template.category not in self._categories:
                self._categories[template.category] = []
            self._categories[template.category].append(template.template_id)

            if template.event_type not in self._type_index:
                self._type_index[template.event_type] = []
            self._type_index[template.event_type].append(template.template_id)

            return True

    def get_template(self, template_id: str) -> Optional[EventTemplateV2]:
        """获取模板"""
        return self._templates.get(template_id)

    def list_templates(self, category: str = None,
                      event_type: str = None,
                      enabled_only: bool = True) -> List[EventTemplateV2]:
        """列出模板"""
        templates = list(self._templates.values())

        if enabled_only:
            templates = [t for t in templates if t.enabled]

        if category:
            templates = [t for t in templates if t.category == category]

        if event_type:
            templates = [t for t in templates if t.event_type == event_type]

        return templates

    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self._categories.keys())

    def get_by_type(self, event_type: str) -> List[EventTemplateV2]:
        """按类型获取模板"""
        template_ids = self._type_index.get(event_type, [])
        return [self._templates[tid] for tid in template_ids if tid in self._templates]

    def update_template(self, template_id: str,
                       updates: Dict[str, Any]) -> Optional[EventTemplateV2]:
        """更新模板"""
        with self._lock:
            template = self._templates.get(template_id)
            if not template:
                return None

            for key, value in updates.items():
                if hasattr(template, key):
                    setattr(template, key, value)

            template.updated_at = datetime.now(timezone.utc).isoformat()
            return template

    def delete_template(self, template_id: str) -> bool:
        """删除模板"""
        with self._lock:
            if template_id in self._templates:
                del self._templates[template_id]
                return True
            return False


class TimeController:
    """时间控制器"""

    def __init__(self):
        self._state = TimeState(
            mode=TimeControlMode.REAL_TIME,
            current_time=datetime.now(timezone.utc),
            start_time=datetime.now(timezone.utc)
        )
        self._listeners: List[Callable] = []
        self._lock = threading.RLock()

    def get_current_time(self) -> datetime:
        """获取当前模拟时间"""
        with self._lock:
            if self._state.mode == TimeControlMode.PAUSED:
                return self._state.current_time

            elapsed = datetime.now(timezone.utc) - self._state.simulation_start
            simulated_elapsed = elapsed * self._state.speed
            return self._state.start_time + simulated_elapsed

    def set_speed(self, speed: float):
        """设置模拟速度"""
        with self._lock:
            self._state.speed = max(0.1, min(100.0, speed))
            if speed == 0:
                self._state.mode = TimeControlMode.PAUSED
            elif speed > 1.0:
                self._state.mode = TimeControlMode.FAST_FORWARD
            elif speed < 1.0:
                self._state.mode = TimeControlMode.SLOW_MOTION
            else:
                self._state.mode = TimeControlMode.REAL_TIME

            self._notify_listeners()

    def pause(self):
        """暂停"""
        with self._lock:
            self._state.mode = TimeControlMode.PAUSED
            self._notify_listeners()

    def resume(self):
        """恢复"""
        with self._lock:
            self._state.mode = TimeControlMode.REAL_TIME
            self._state.simulation_start = datetime.now(timezone.utc)
            self._notify_listeners()

    def jump_to(self, target_time: datetime):
        """跳转到指定时间"""
        with self._lock:
            self._state.current_time = target_time
            self._state.start_time = target_time
            self._state.simulation_start = datetime.now(timezone.utc)
            self._state.mode = TimeControlMode.JUMP_TO
            self._notify_listeners()

    def jump_forward(self, delta: timedelta):
        """快进"""
        with self._lock:
            new_time = self._state.current_time + delta
            self.jump_to(new_time)

    def register_listener(self, listener: Callable):
        """注册时间变化监听器"""
        self._listeners.append(listener)

    def _notify_listeners(self):
        """通知监听器"""
        for listener in self._listeners:
            try:
                listener(self._state)
            except Exception:
                pass

    def get_state(self) -> Dict[str, Any]:
        """获取时间状态"""
        with self._lock:
            return {
                "mode": self._state.mode.value,
                "current_time": self._state.current_time.isoformat(),
                "start_time": self._state.start_time.isoformat(),
                "speed": self._state.speed,
                "is_running": self._state.is_running,
                "tick_count": self._state.tick_count
            }


class EventGenerator:
    """事件生成器"""

    def __init__(self, template_manager: EventTemplateManager):
        self._template_manager = template_manager
        self._instance_count: Dict[str, int] = {}
        self._last_triggered: Dict[str, datetime] = {}
        self._lock = threading.RLock()

    def can_generate(self, template_id: str) -> tuple[bool, str]:
        """检查是否可以生成事件"""
        template = self._template_manager.get_template(template_id)
        if not template:
            return False, "Template not found"

        if not template.enabled:
            return False, "Template is disabled"

        current_count = self._instance_count.get(template_id, 0)
        if current_count >= template.max_instances:
            return False, f"Max instances ({template.max_instances}) reached"

        last_time = self._last_triggered.get(template_id)
        if last_time and template.cooldown_seconds > 0:
            elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
            if elapsed < template.cooldown_seconds:
                return False, f"Cooldown not elapsed ({elapsed:.1f}s < {template.cooldown_seconds}s)"

        if random.random() > template.probability:
            return False, f"Probability check failed ({template.probability})"

        return True, "OK"

    def generate(self, template_id: str, parameters: Dict[str, Any] = None,
                scheduled_time: datetime = None) -> Optional[GeneratedEventV2]:
        """生成事件"""
        with self._lock:
            can_gen, reason = self.can_generate(template_id)
            if not can_gen:
                return None

            template = self._template_manager.get_template(template_id)
            if not template:
                return None

            event_data = self._resolve_parameters(template, parameters)

            event = GeneratedEventV2(
                event_id=str(uuid.uuid4()),
                template_id=template_id,
                template_name=template.name,
                event_type=template.event_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
                scheduled_time=scheduled_time.isoformat() if scheduled_time else None,
                data=event_data,
                priority=EventPriority.NORMAL,
                source="generated"
            )

            self._instance_count[template_id] = self._instance_count.get(template_id, 0) + 1
            self._last_triggered[template_id] = datetime.now(timezone.utc)

            return event

    def _resolve_parameters(self, template: EventTemplateV2,
                          parameters: Dict[str, Any]) -> Dict[str, Any]:
        """解析参数"""
        resolved = template.default_values.copy()
        if parameters:
            resolved.update(parameters)

        for param in template.parameters:
            if param.name not in resolved and param.default is not None:
                resolved[param.name] = param.default

        return resolved

    def reset(self, template_id: str = None):
        """重置生成计数"""
        with self._lock:
            if template_id:
                self._instance_count[template_id] = 0
                self._last_triggered.pop(template_id, None)
            else:
                self._instance_count.clear()
                self._last_triggered.clear()


class EventSimulatorV2:
    """
    事件模拟器 v2
    完整的事件模拟系统
    """

    def __init__(self):
        self._template_manager = EventTemplateManager()
        self._time_controller = TimeController()
        self._event_generator = EventGenerator(self._template_manager)
        self._event_queue: List[GeneratedEventV2] = []
        self._event_history: List[GeneratedEventV2] = []
        self._sequences: Dict[str, EventSequence] = {}
        self._handlers: Dict[str, Callable] = {}
        self._running_events: Dict[str, GeneratedEventV2] = {}
        self._lock = threading.RLock()
        self._max_history = 10000
        self._simulation_loop: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._setup_default_templates()

    def _setup_default_templates(self):
        """设置默认模板"""
        radar_event = EventTemplateV2(
            template_id="radar_detection",
            name="雷达探测事件",
            description="模拟雷达探测到目标",
            event_type="radar.detected",
            category="intelligence",
            parameters=[
                EventParameter(name="radar_id", type="string", description="雷达ID"),
                EventParameter(name="target_id", type="string", description="目标ID"),
                EventParameter(name="distance", type="float", description="距离(km)", min_value=0, max_value=500),
                EventParameter(name="bearing", type="float", description="方位角(度)", min_value=0, max_value=360),
            ],
            default_values={"radar_id": "RADAR-01", "distance": 100, "bearing": 180},
            probability=0.8,
            cooldown_seconds=5
        )
        self._template_manager.register_template(radar_event)

        threat_event = EventTemplateV2(
            template_id="threat_alert",
            name="威胁警报",
            description="系统检测到潜在威胁",
            event_type="security.threat",
            category="security",
            parameters=[
                EventParameter(name="threat_level", type="string", description="威胁级别", options=["low", "medium", "high", "critical"]),
                EventParameter(name="source", type="string", description="威胁源"),
            ],
            default_values={"threat_level": "medium"},
            probability=0.3,
            cooldown_seconds=10
        )
        self._template_manager.register_template(threat_event)

        comm_event = EventTemplateV2(
            template_id="communication",
            name="通信事件",
            description="通信系统事件",
            event_type="communication.event",
            category="operations",
            parameters=[
                EventParameter(name="sender", type="string", description="发送方"),
                EventParameter(name="receiver", type="string", description="接收方"),
                EventParameter(name="message_type", type="string", description="消息类型"),
            ],
            probability=0.9
        )
        self._template_manager.register_template(comm_event)

    def register_handler(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        self._handlers[event_type] = handler

    def add_template(self, template: EventTemplateV2) -> bool:
        """添加模板"""
        return self._template_manager.register_template(template)

    def generate_event(self, template_id: str, parameters: Dict[str, Any] = None,
                      scheduled_time: datetime = None) -> Optional[GeneratedEventV2]:
        """生成事件"""
        event = self._event_generator.generate(template_id, parameters, scheduled_time)
        if event:
            with self._lock:
                self._event_queue.append(event)
        return event

    def schedule_event(self, template_id: str, parameters: Dict[str, Any] = None,
                      delay_seconds: float = 0) -> Optional[GeneratedEventV2]:
        """调度事件"""
        scheduled_time = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        return self.generate_event(template_id, parameters, scheduled_time)

    def execute_sequence(self, sequence_id: str, parameters: Dict[str, Any] = None):
        """执行事件序列"""
        sequence = self._sequences.get(sequence_id)
        if not sequence:
            return False

        for i in range(sequence.loop_count):
            for event_spec in sequence.events:
                template_id = event_spec.get("template_id")
                event_params = event_spec.get("parameters", {})
                delay = event_spec.get("delay_seconds", 0)

                if parameters:
                    event_params.update(parameters)

                self.schedule_event(template_id, event_params, delay)

        return True

    def register_sequence(self, sequence: EventSequence) -> bool:
        """注册事件序列"""
        with self._lock:
            self._sequences[sequence.sequence_id] = sequence
            return True

    def get_next_event(self) -> Optional[GeneratedEventV2]:
        """获取下一个待处理事件"""
        with self._lock:
            if not self._event_queue:
                return None

            self._event_queue.sort(key=lambda e: (
                e.priority.value,
                e.scheduled_time or e.timestamp
            ), reverse=True)

            return self._event_queue.pop(0)

    def process_event(self, event: GeneratedEventV2) -> bool:
        """处理事件"""
        event.status = EventStatus.RUNNING

        with self._lock:
            self._running_events[event.event_id] = event

        start_time = time.perf_counter()

        try:
            handler = self._handlers.get(event.event_type)
            if handler:
                result = handler(event)
                event.result = result if result else {}
                event.status = EventStatus.COMPLETED
            else:
                event.result = {"message": "No handler registered"}
                event.status = EventStatus.COMPLETED

        except Exception as e:
            event.status = EventStatus.FAILED
            event.error = str(e)

        event.execution_time_ms = (time.perf_counter() - start_time) * 1000

        with self._lock:
            if event.event_id in self._running_events:
                del self._running_events[event.event_id]
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]

        return event.status == EventStatus.COMPLETED

    def cancel_event(self, event_id: str) -> bool:
        """取消事件"""
        with self._lock:
            for i, event in enumerate(self._event_queue):
                if event.event_id == event_id:
                    event.status = EventStatus.CANCELLED
                    self._event_queue.pop(i)
                    return True

            if event_id in self._running_events:
                self._running_events[event_id].status = EventStatus.CANCELLED
                return True

        return False

    def get_queue(self) -> List[GeneratedEventV2]:
        """获取事件队列"""
        with self._lock:
            return self._event_queue.copy()

    def get_history(self, limit: int = 100) -> List[GeneratedEventV2]:
        """获取历史事件"""
        with self._lock:
            return self._event_history[-limit:]

    def get_templates(self, category: str = None) -> List[Dict[str, Any]]:
        """获取模板列表"""
        templates = self._template_manager.list_templates(category=category)
        return [t.to_dict() for t in templates]

    def get_time_state(self) -> Dict[str, Any]:
        """获取时间状态"""
        return self._time_controller.get_state()

    def set_simulation_speed(self, speed: float):
        """设置模拟速度"""
        self._time_controller.set_speed(speed)

    def pause_simulation(self):
        """暂停模拟"""
        self._time_controller.pause()

    def resume_simulation(self):
        """恢复模拟"""
        self._time_controller.resume()

    def jump_to_time(self, target_time: datetime):
        """跳转到指定时间"""
        self._time_controller.jump_to(target_time)

    def start_simulation_loop(self, tick_interval_ms: int = 1000):
        """启动模拟循环"""
        if self._simulation_loop and self._simulation_loop.is_alive():
            return

        self._stop_event.clear()

        def loop():
            while not self._stop_event.is_set():
                event = self.get_next_event()
                if event:
                    self.process_event(event)

                self._time_controller._state.tick_count += 1
                time.sleep(tick_interval_ms / 1000)

        self._simulation_loop = threading.Thread(target=loop, daemon=True)
        self._simulation_loop.start()

    def stop_simulation_loop(self):
        """停止模拟循环"""
        self._stop_event.set()
        if self._simulation_loop:
            self._simulation_loop.join(timeout=5)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = len(self._event_history)
            completed = sum(1 for e in self._event_history if e.status == EventStatus.COMPLETED)
            failed = sum(1 for e in self._event_history if e.status == EventStatus.FAILED)
            cancelled = sum(1 for e in self._event_history if e.status == EventStatus.CANCELLED)

            by_type: Dict[str, int] = {}
            for e in self._event_history:
                by_type[e.event_type] = by_type.get(e.event_type, 0) + 1

            return {
                "total_events": total,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "pending": len(self._event_queue),
                "running": len(self._running_events),
                "by_type": by_type,
                "queue_size": len(self._event_queue),
                "templates_count": len(self._template_manager._templates)
            }


_global_event_simulator: Optional[EventSimulatorV2] = None


def get_event_simulator() -> EventSimulatorV2:
    """获取全局事件模拟器"""
    global _global_event_simulator
    if _global_event_simulator is None:
        _global_event_simulator = EventSimulatorV2()
    return _global_event_simulator


if __name__ == "__main__":
    simulator = get_event_simulator()

    print("=" * 60)
    print("事件模拟器 v2 测试")
    print("=" * 60)

    print("\n1. 模板列表:")
    templates = simulator.get_templates()
    for t in templates:
        print(f"   - {t['name']} ({t['event_type']})")

    print("\n2. 生成事件:")
    event = simulator.generate_event("radar_detection", {"distance": 150, "bearing": 90})
    if event:
        print(f"   事件已生成: {event.event_id}")
        print(f"   类型: {event.event_type}")

    print("\n3. 注册处理器:")
    def radar_handler(event):
        print(f"   处理雷达事件: {event.data}")
        return {"processed": True}

    simulator.register_handler("radar.detected", radar_handler)

    print("\n4. 处理事件:")
    events = simulator.get_history(limit=10)
    if events:
        simulator.process_event(events[-1])

    print("\n5. 时间控制:")
    simulator.set_simulation_speed(2.0)
    time_state = simulator.get_time_state()
    print(f"   模式: {time_state['mode']}")
    print(f"   速度: {time_state['speed']}x")

    print("\n6. 统计信息:")
    stats = simulator.get_statistics()
    print(f"   总事件数: {stats['total_events']}")
    print(f"   完成: {stats['completed']}")
    print(f"   待处理: {stats['pending']}")

    print("\n" + "=" * 60)
    print("事件模拟器 v2 测试完成")
    print("=" * 60)