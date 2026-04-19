"""事件模拟器API"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from ..services.simulator_service import EventSimulatorService

router = APIRouter(prefix="/api/event-simulator", tags=["event-simulator"])

service = EventSimulatorService()


@router.post("/templates")
async def create_template(
    name: str,
    event_type: str,
    description: str = "",
    schema: Optional[Dict[str, Any]] = None
):
    """创建模板"""
    try:
        return service.create_template(name, event_type, description, schema)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def list_templates():
    """列出模板"""
    try:
        return {"templates": service.list_templates()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events/generate")
async def generate_event(template_id: str, data: Optional[Dict[str, Any]] = None):
    """生成事件"""
    try:
        return service.generate_event(template_id, data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
async def list_events(limit: int = 100):
    """列出事件"""
    try:
        return {"events": service.list_events(limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/time-control")
async def set_time_control(speed: float = 1.0, is_paused: bool = False):
    """设置时间控制"""
    try:
        return service.set_time_control(speed, is_paused)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/time-control")
async def get_time_control():
    """获取时间控制"""
    try:
        return service.get_time_control()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
