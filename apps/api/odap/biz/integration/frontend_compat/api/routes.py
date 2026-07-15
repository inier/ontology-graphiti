"""前端API兼容层 - 路由聚合入口

仅保留真正做跨服务聚合的端点，1:1 重复原生服务层的端点已删除。
前端应直接调用原生 /api/ 路由获取基础 CRUD 能力。
"""

from fastapi import APIRouter

router = APIRouter(tags=["frontend-compat"])

from odap.biz.integration.frontend_compat.api.ontology_routes import router as ontology_router
from odap.biz.integration.frontend_compat.api.agent_routes import router as agent_router
from odap.biz.integration.frontend_compat.api.simulation_routes import router as simulation_router

router.include_router(ontology_router)
router.include_router(agent_router)
router.include_router(simulation_router)
