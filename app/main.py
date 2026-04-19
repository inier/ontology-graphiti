"""Graphiti 主应用"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from odap.biz.ontology_management_engine.api.routes import router as ontology_router
from odap.biz.workspace_management.api.routes import router as workspace_router
from odap.biz.audit_logging.api.routes import router as audit_router
from odap.biz.skill_system.api.routes import router as skill_router
from odap.biz.hook_system.api.routes import router as hook_router
from odap.biz.mcp_adapter.api.routes import router as mcp_router
from odap.biz.event_simulator.api.routes import router as event_router

app = FastAPI(
    title="Graphiti API",
    description="Graphiti 知识图谱管理系统",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(ontology_router)
app.include_router(workspace_router)
app.include_router(audit_router)
app.include_router(skill_router)
app.include_router(hook_router)
app.include_router(mcp_router)
app.include_router(event_router)

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Graphiti API",
        "version": "1.0.0",
        "endpoints": [
            "/api/ontology-management",
            "/api/workspace",
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