"""路由注册工具

提供统一的路由注册辅助函数，简化应用启动时的路由配置
"""

from typing import List, Optional
from fastapi import FastAPI, APIRouter


def register_routers(app: FastAPI, routers: List[tuple], prefix: Optional[str] = None) -> None:
    """批量注册路由

    Args:
        app: FastAPI 应用实例
        routers: 路由元组列表，每项为 (router, prefix) 或 (router,)
        prefix: 全局路由前缀，可选
    """
    for router_config in routers:
        if isinstance(router_config, tuple):
            router = router_config[0]
            router_prefix = router_config[1] if len(router_config) > 1 else None
        else:
            router = router_config
            router_prefix = None

        if router_prefix:
            app.include_router(router, prefix=router_prefix)
        elif prefix:
            app.include_router(router, prefix=prefix)
        else:
            app.include_router(router)


def create_router_registry() -> List[tuple]:
    """创建默认路由注册表

    Returns:
        路由元组列表
    """
    from odap.biz.core.ontology.api.routes import router as ingest_router
    from odap.biz.platform.workspace.api.routes import router as workspace_router
    from odap.biz.platform.roles.api.routes import router as roles_router
    from odap.infra.security import audit_router
    from odap.biz.platform.skill_system.api.routes import router as skill_router
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

    return [
        (ingest_router, "/api/ontology/ingest"),
        (workspace_router, "/api/workspaces"),
        (roles_router, "/api/roles"),
        (audit_router, "/api/audit"),
        (skill_router, "/api/skills"),
        (hook_router, "/api/hooks"),
        (mcp_router, "/api/mcp"),
        (event_router, "/api/events"),
        (frontend_router, "/api/frontend"),
        (agent_router, "/api/agent"),
        (agent_mgmt_router, "/api/management"),
        (kb_router, "/api/knowledge"),
        (oms_router, "/api/ontology"),
        (osv2_router, "/api/objects"),
        (action_router, "/api/actions"),
        (perception_router, "/api/perception"),
        (decision_pipeline_router, "/api/decision"),
        (sandbox_router, "/api/sandbox"),
        (business_router, "/api/business"),
        (policy_router, "/api/policies"),
        (session_memory_router, "/api/sessions"),
        (data_warehouse_router, "/api/data"),
        (query_router, "/api/query"),
        (qa_router, "/api/qa"),
        (cognition_router, "/api/cognition"),
        (feedback_router, "/api/feedback"),
    ]


DEFAULT_ROUTER_REGISTRY = create_router_registry()
