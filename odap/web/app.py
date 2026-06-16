"""Graphiti 主应用"""

import os
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from odap.infra.middleware.exception_handler import register_exception_handler
from odap.web.router_registry import register_routers, DEFAULT_ROUTER_REGISTRY
from odap.infra.security import security_config
from odap.infra.openharness.engine_adapter import initialize_openharness, get_openharness_integration
from odap.infra.config_composer import get_config
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _schedule_deferred_openharness_init() -> None:
    """调度 OpenHarness v2 延迟初始化（带超时保护）"""
    async def _deferred_init():
        try:
            await asyncio.wait_for(initialize_openharness(), timeout=15.0)
            logger.info("OpenHarness v2 Agent 初始化成功")
        except asyncio.TimeoutError:
            logger.warning("OpenHarness v2 Agent 初始化超时（15s），跳过")
        except Exception as e:
            logger.warning(f"OpenHarness v2 Agent 初始化失败: {e}")
    asyncio.create_task(_deferred_init())


def _ensure_default_workspace_and_scenario() -> None:
    """确保存在默认工作空间与场景（首次启动）"""
    try:
        from odap.biz.platform.workspace.services.workspace_service import WorkspaceService
        workspace_service = WorkspaceService()

        existing = workspace_service.list_workspaces(filters={}, page=1, page_size=100)
        if existing.get("workspaces") and len(existing.get("workspaces", [])) > 0:
            logger.info(f"工作空间已存在，共 {len(existing['workspaces'])} 个")
            return

        default_workspace = workspace_service.create_workspace(
            name="测试工作空间",
            description="系统默认工作空间，用于测试和演示"
        )
        logger.info(f"✓ 默认工作空间已创建: {default_workspace.get('workspace_id')}")

        try:
            from odap.biz.platform.workspace.services.scenario_service import ScenarioService
            scenario_service = ScenarioService()
            default_scenario = scenario_service.create_scenario(
                workspace_id=default_workspace.get("workspace_id"),
                name="默认场景",
                description="与默认工作空间关联的场景"
            )
            logger.info(f"✓ 默认场景已创建: {default_scenario.get('scenario_id')}")
        except Exception as scene_err:
            logger.warning(f"创建默认场景失败: {scene_err}")
    except Exception as e:
        logger.error(f"初始化默认工作空间失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _schedule_deferred_openharness_init()
    _ensure_default_workspace_and_scenario()
    yield

    integration = get_openharness_integration()
    await integration.shutdown()
    logger.info("应用关闭中...")


app = FastAPI(
    title="Graphiti API",
    description="Graphiti 知识图谱管理系统 - 集成 OpenHarness Agent",
    version="2.0.0",
    lifespan=lifespan
)

# 配置 CORS
_cors_origins_str = get_config("general.cors_origins", "http://localhost:3000,http://localhost:8000")
_cors_origins: List[str] = [origin.strip() for origin in _cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

register_exception_handler(app)

from odap.infra.middleware.audit_middleware import AuditMiddleware
from odap.infra.middleware.performance_middleware import PerformanceMiddleware, GzipMiddleware
app.add_middleware(GzipMiddleware)
app.add_middleware(PerformanceMiddleware)
app.add_middleware(AuditMiddleware)

# 统一注册所有路由（路由配置集中在 router_registry.py 管理）
register_routers(app, DEFAULT_ROUTER_REGISTRY)

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Graphiti API",
        "version": "2.0.0",
        "features": [
            "知识图谱管理",
            "工作空间管理",
            "OpenHarness Agent",
            "审计日志",
            "技能系统",
            "事件模拟"
        ],
        "endpoints": [
            "/api/ontology-management",
            "/api/workspace",
            "/api/roles",
            "/api/audit",
            "/api/skill",
            "/api/hook",
            "/api/mcp",
            "/api/event-simulator",
            "/api/agent",
            "/api/agent-management"
        ]
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    integration = get_openharness_integration()
    status_info = integration.get_status()

    from odap.infra.graph.graph_service import GraphManager, GRAPHITI_AVAILABLE
    gm = GraphManager()
    graphiti_status = {
        "graphiti_core_installed": GRAPHITI_AVAILABLE,
        "graph_mode": gm._mode,
        "connected": gm._connected,
        "use_fallback": gm._use_fallback,
    }

    return {
        "status": "healthy",
        "openharness": {
            "available": status_info.get("openharness_available", False),
            "engine_type": status_info.get("engine_type", "unknown"),
            "agent_loop_initialized": status_info.get("agent_loop_initialized", False),
            "tools_count": status_info.get("tools_count", 0),
            "tools": status_info.get("tools", []),
        },
        "graphiti": graphiti_status,
        "version": "2.0.0"
    }
