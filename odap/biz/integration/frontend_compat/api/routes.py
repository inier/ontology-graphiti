"""前端API兼容层 - 路由聚合入口

将原 routes.py 拆分为按功能域划分的子路由模块，本文件仅负责聚合。
所有 URL 路径保持与拆分前完全一致。
"""

from fastapi import APIRouter

router = APIRouter(tags=["frontend-compat"])

# 导入子路由（各子路由已自带 /api/compat 前缀）
from odap.biz.integration.frontend_compat.api.ontology_routes import router as ontology_router
from odap.biz.integration.frontend_compat.api.qa_routes import router as qa_router
from odap.biz.integration.frontend_compat.api.agent_routes import router as agent_router
from odap.biz.integration.frontend_compat.api.simulation_routes import router as simulation_router
from odap.biz.integration.frontend_compat.api.workspace_routes import router as workspace_router

# 聚合子路由
router.include_router(ontology_router)
router.include_router(qa_router)
router.include_router(agent_router)
router.include_router(simulation_router)
router.include_router(workspace_router)
