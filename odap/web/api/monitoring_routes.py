"""性能监控路由"""

from fastapi import APIRouter, Depends

from odap.infra.security.jwt_auth import get_current_user, verify_admin
from odap.infra.monitoring import performance_monitor

monitoring_router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


@monitoring_router.get("/performance")
async def get_performance_metrics(user=Depends(get_current_user)):
    """获取性能监控指标"""
    return performance_monitor.get_all_stats()


@monitoring_router.post("/performance/reset")
async def reset_performance_metrics(user=Depends(verify_admin)):
    """重置性能监控指标"""
    performance_monitor.reset()
    return {"message": "Performance metrics reset successfully"}
