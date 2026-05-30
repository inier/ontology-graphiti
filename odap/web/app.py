"""Graphiti 主应用"""

import os
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from odap.infra.middleware.exception_handler import register_exception_handler
from odap.biz.core.ontology.api.routes import router as ingest_router
from odap.biz.platform.workspace.api.routes import router as workspace_router
from odap.biz.platform.roles.api.routes import router as roles_router
from odap.infra.security import audit_router
from odap.infra.security.auth_routes import router as auth_router
from odap.biz.platform.skill_system.api.routes import router as skill_router
from odap.biz.platform.skill_system.api.routes_extended import router as skill_ext_router
from odap.biz.integration.hook_system.api.routes import router as hook_router
from odap.biz.integration.mcp_adapter.api.routes import router as mcp_router
from odap.biz.simulation.event_simulator.api.routes import router as event_router
from odap.biz.integration.frontend_compat.api.routes import router as frontend_router
from odap.biz.integration.openharness_agent.api.routes import router as agent_router
from odap.biz.management.agent_management.api.routes import router as agent_mgmt_router
from odap.biz.data.knowledge_base.api.routes import router as kb_router
from odap.biz.core.ontology.oms.routes import router as oms_router
from odap.infra.object_service.routes import router as osv2_router
from odap.biz.decision.action_service.routes import router as action_router
from odap.biz.data.perception.routes import router as perception_router
from odap.biz.decision.decision_pipeline.routes import router as decision_pipeline_router
from odap.biz.simulation.simulation_sandbox.routes import router as sandbox_router
from odap.biz.management.business.api.routes import router as business_router
from odap.infra.opa.routes import router as policy_router
from odap.biz.platform.session_memory.api.routes import router as session_memory_router
from odap.biz.data.data_warehouse.api.routes import router as data_warehouse_router
from odap.infra.query.routes import router as query_router
from odap.biz.data.qa.api.routes import router as qa_router
from odap.biz.core.cognition.api.routes import router as cognition_router
from odap.biz.simulation.feedback.api.routes import router as feedback_router
from odap.biz.simulation.simulation_deduction.api.routes import router as deduction_router
from odap.biz.data.semantic_map.api.routes import router as semantic_map_router
from odap.biz.core.ontology.runtime.api.routes import router as runtime_router
from odap.biz.core.ontology.harness.api.routes import router as harness_router
from odap.biz.platform.ontology_memory.api.routes import router as ontology_memory_router
from odap.biz.platform.ontology_memory.graph_sync.routes import router as memory_sync_router
from odap.biz.platform.ontology_memory.shared_workspace.routes import router as shared_memory_router
from odap.biz.core.ontology.servitization.api.routes import router as servitization_router
from odap.biz.core.ontology.servitization.api.deployment_routes import router as deployment_router
from odap.biz.core.ontology.servitization.catalog.routes import router as catalog_router
from odap.biz.core.ontology.harness.blueprint.routes import router as blueprint_designer_router
from odap.biz.core.ontology.harness.blueprint.api.runtime_routes import router as blueprint_runtime_router
from odap.biz.core.cognition.thought_graph.api.routes import router as thought_router
from odap.biz.core.ontology.runtime.state_machine.api.routes import router as state_machine_router
from odap.biz.core.ontology.abution_graph.api.routes import router as abution_graph_router
from odap.biz.platform.ontology_memory.api.decay_routes import router as decay_router
from odap.biz.platform.ontology_memory.shared_workspace.api.consensus_routes import router as consensus_router
from odap.infra.security import security_config
from odap.infra.openharness import create_harness
from odap.infra.openharness.v2_adapter import initialize_openharness, get_openharness_integration
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

harness = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global harness

    harness = create_harness()
    if harness:
        logger.info(f"OpenHarness v1 初始化成功，可用工具: {len(harness.list_available_tools())}")
    else:
        logger.warning("OpenHarness v1 不可用")

    async def _deferred_init():
        try:
            await asyncio.wait_for(initialize_openharness(), timeout=15.0)
            logger.info("OpenHarness v2 Agent 初始化成功")
        except asyncio.TimeoutError:
            logger.warning("OpenHarness v2 Agent 初始化超时（15s），跳过")
        except Exception as e:
            logger.warning(f"OpenHarness v2 Agent 初始化失败: {e}")

    asyncio.create_task(_deferred_init())

    try:
        from odap.biz.platform.workspace.services.workspace_service import WorkspaceService
        workspace_service = WorkspaceService()

        existing = workspace_service.list_workspaces(filters={}, page=1, page_size=100)
        if existing.get("workspaces") and len(existing.get("workspaces", [])) > 0:
            logger.info(f"工作空间已存在，共 {len(existing['workspaces'])} 个")
        else:
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

    yield

    logger.info("应用关闭中...")


app = FastAPI(
    title="Graphiti API",
    description="Graphiti 知识图谱管理系统 - 集成 OpenHarness Agent",
    version="2.0.0",
    lifespan=lifespan
)

# 配置 CORS
_cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
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
app.add_middleware(AuditMiddleware)

# 注册路由
app.include_router(ingest_router)
app.include_router(workspace_router)
app.include_router(roles_router)
app.include_router(audit_router)
app.include_router(auth_router)
app.include_router(skill_router)
app.include_router(skill_ext_router)
app.include_router(hook_router)
app.include_router(mcp_router)
app.include_router(event_router)
app.include_router(frontend_router)
app.include_router(agent_router)
app.include_router(agent_mgmt_router)
app.include_router(kb_router)
app.include_router(oms_router)
app.include_router(osv2_router)
app.include_router(action_router)
app.include_router(perception_router)
app.include_router(decision_pipeline_router)
app.include_router(sandbox_router)
app.include_router(business_router)
app.include_router(policy_router)
app.include_router(session_memory_router)
app.include_router(data_warehouse_router)
app.include_router(query_router)
app.include_router(qa_router)
app.include_router(cognition_router)
app.include_router(feedback_router)
app.include_router(deduction_router)
app.include_router(semantic_map_router)
app.include_router(runtime_router)
app.include_router(harness_router)
app.include_router(ontology_memory_router)
app.include_router(memory_sync_router)
app.include_router(shared_memory_router)
app.include_router(servitization_router)
app.include_router(deployment_router)
app.include_router(catalog_router)
app.include_router(blueprint_designer_router)
app.include_router(blueprint_runtime_router)
app.include_router(thought_router)
app.include_router(state_machine_router)
app.include_router(abution_graph_router)
app.include_router(decay_router)
app.include_router(consensus_router)

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
        "openharness_v1": harness is not None,
        "openharness_v2": status_info,
        "graphiti": graphiti_status,
        "version": "2.0.0"
    }

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
