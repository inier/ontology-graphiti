"""Graphiti 主应用"""

from contextlib import asynccontextmanager
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
from odap.biz.openharness_agent.api.routes import router as agent_router
from odap.biz.agent_management.api.routes import router as agent_mgmt_router
from odap.biz.knowledge_base.api.routes import router as kb_router
from odap.biz.ontology.oms.routes import router as oms_router
from odap.infra.object_service.routes import router as osv2_router
from odap.biz.action_service.routes import router as action_router
from odap.biz.perception.routes import router as perception_router
from odap.biz.decision_pipeline.routes import router as decision_pipeline_router
from odap.biz.simulation_sandbox.routes import router as sandbox_router
from odap.biz.business.api.routes import router as business_router
from odap.infra.opa.routes import router as policy_router
from odap.biz.session_memory.api.routes import router as session_memory_router
from odap.biz.data_warehouse.api.routes import router as data_warehouse_router
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
        from odap.biz.workspace.services.workspace_service import WorkspaceService
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
                from odap.biz.workspace.services.scenario_service import ScenarioService
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
            "/api/agent"
        ]
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    integration = get_openharness_integration()
    status_info = integration.get_status()
    
    return {
        "status": "healthy",
        "openharness_v1": harness is not None,
        "openharness_v2": status_info,
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
