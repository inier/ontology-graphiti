"""Graphiti 主应用"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from odap.biz.ontology.api.routes import router as ingest_router
from odap.biz.workspace.api.routes import router as workspace_router
from odap.biz.roles.api.routes import router as roles_router
from odap.infra.security import audit_router
from odap.biz.skill_system.api.routes import router as skill_router
from odap.biz.hook_system.api.routes import router as hook_router
from odap.biz.mcp_adapter.api.routes import router as mcp_router
from odap.biz.event_simulator.api.routes import router as event_router
from odap.biz.frontend_compat.api.routes import router as frontend_router
from odap.infra.security import security_config

app = FastAPI(
    title="Graphiti API",
    description="Graphiti 知识图谱管理系统",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=security_config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(ingest_router)
app.include_router(workspace_router)
app.include_router(roles_router)
app.include_router(audit_router)
app.include_router(skill_router)
app.include_router(hook_router)
app.include_router(mcp_router)
app.include_router(event_router)
app.include_router(frontend_router)

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Graphiti API",
        "version": "1.0.0",
        "endpoints": [
            "/api/ontology-management",
            "/api/workspace",
            "/api/roles",
            "/api/audit",
            "/api/skill",
            "/api/hook",
            "/api/mcp",
            "/api/event-simulator"
        ]
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}

# 添加性能监控端点
from fastapi import APIRouter
from odap.infra.monitoring import performance_monitor

monitoring_router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

@monitoring_router.get("/performance")
async def get_performance_metrics():
    """获取性能监控指标"""
    return performance_monitor.get_all_stats()

@monitoring_router.post("/performance/reset")
async def reset_performance_metrics():
    """重置性能监控指标"""
    performance_monitor.reset()
    return {"message": "Performance metrics reset successfully"}

app.include_router(monitoring_router)