"""路由注册工具

提供统一的路由注册辅助函数，简化应用启动时的路由配置。
所有路由的导入和注册集中在此文件管理，app.py 只需调用 register_routers()。
"""

from typing import List, Optional
from fastapi import FastAPI


def register_routers(app: FastAPI, routers: List[tuple], prefix: Optional[str] = None) -> None:
    """批量注册路由

    Args:
        app: FastAPI 应用实例
        routers: 路由元组列表，每项为 (router,) 或 (router, prefix)
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

    所有路由统一在此函数中导入和配置，作为单一事实来源。
    路由自带 prefix 的使用 (router,) 格式，无需额外指定前缀。

    Returns:
        路由元组列表
    """
    # ── 工作空间与角色 ──
    from odap.biz.platform.workspace.api.routes import router as workspace_router
    from odap.biz.platform.workspace.api.routes import scenario_compat_router
    from odap.biz.platform.roles.api.routes import router as roles_router

    # ── 安全与认证 ──
    from odap.infra.security import audit_router
    from odap.infra.security.auth_routes import router as auth_router
    from odap.infra.security.data_classification_routes import router as data_classification_router

    # ── 技能与钩子 ──
    from odap.biz.platform.skill_system.api.routes import router as skill_router
    from odap.biz.platform.skill_system.api.routes_extended import router as skill_ext_router
    from odap.biz.integration.hook_system.api.routes import router as hook_router

    # ── 集成适配 ──
    from odap.biz.integration.mcp_adapter.api.routes import router as mcp_router
    from odap.biz.integration.frontend_compat.api.routes import router as frontend_router
    from odap.biz.integration.openharness_agent.api.routes import router as agent_router

    # ── 渠道管理 ──
    from odap.biz.integration.channel_management.api.routes import router as channel_router

    # ── 智能体 ──
    from odap.biz.core.agent.api.routes import router as agent_dispatch_router
    from odap.biz.core.agent.api.decision_routes import router as agent_decision_router
    from odap.biz.management.agent_management.api.routes import router as agent_mgmt_router
    from odap.infra.openharness.agui.agui_handler import router as agui_router

    # ── 知识库 ──
    from odap.biz.data.knowledge_base.api.routes import router as kb_router

    # ── Hyper-Extract 知识提取（ADR-066） ──
    from odap.biz.data.hyper_extract.api.routes import router as he_router

    # ── 本体 - OMS 与查询 ──
    from odap.biz.core.ontology.application.oms.routes import router as oms_router
    from odap.biz.core.ontology.application.query_api.nl_routes import router as ontology_nl_router
    from odap.biz.core.ontology.application.query_api.routes import router as ontology_ingest_router

    # ── 本体 - TypeRegistry（统一类型定义读写入口） ──
    from odap.biz.core.ontology.registry.api.routes import router as registry_router

    # ── 对象服务 ──
    from odap.infra.object_service.routes import router as osv2_router

    # ── 决策 ──
    from odap.biz.decision.action_service.routes import router as action_router
    from odap.biz.decision.decision_pipeline.routes import router as decision_pipeline_router
    from odap.biz.decision.decision_recommendation.api.routes import router as decision_recommendation_router

    # ── 感知 ──
    from odap.biz.data.perception.routes import router as perception_router

    # ── 仿真 ──
    from odap.biz.simulation.event_simulator.api.routes import router as event_router
    from odap.biz.simulation.simulation_sandbox.routes import router as sandbox_router
    from odap.biz.simulation.simulation_sandbox.api.routes import router as sandbox_api_router
    from odap.biz.simulation.simulation_sandbox.api.parallel_routes import router as parallel_router
    from odap.biz.simulation.feedback.api.routes import router as feedback_router
    from odap.biz.simulation.simulation_deduction.api.routes import router as deduction_router

    # ── 业务管理 ──
    from odap.biz.management.business.api.routes import router as business_router

    # ── 策略 ──
    from odap.infra.opa.routes import router as policy_router
    from odap.infra.opa.markdown_routes import router as markdown_policy_router

    # ── 会话记忆 ──
    from odap.biz.platform.session_memory.api.routes import router as session_memory_router

    # ── 数据仓库 ──
    from odap.biz.data.data_warehouse.api.routes import router as data_warehouse_router

    # ── 查询 ──
    from odap.infra.query.routes import router as query_router

    # ── QA ──
    from odap.biz.data.qa.api.routes import router as qa_router
    from odap.biz.data.qa.api.nl_routes import router as qa_nl_router

    # ── AI 助手 (统一) ──
    from odap.biz.core.assistant.api.routes import router as assistant_router

    # ── 统一对话服务 (ADR-050, Phase A 并行) ──
    from odap.biz.core.chat.api.routes import router as unified_chat_router

    # ── 本体 - AI 辅助设计 ──
    from odap.biz.core.ontology.assistant.api.routes import router as ontology_assistant_router

    # ── 认知 ──
    from odap.biz.core.cognition.api.routes import router as cognition_router
    from odap.biz.core.cognition.thought_graph.api.routes import router as thought_router

    # ── 语义地图 ──
    from odap.biz.data.semantic_map.api.routes import router as semantic_map_router

    # ── 语义管理 - 统一语义层（USL Iter 1）──
    from odap.biz.semantic_admin.usl_manager.api.routes import router as semantic_admin_usl_router

    # ── 语义管理 - OL Pipeline + Candidates（Iter 2 6 层流水线 + HITL）──
    from odap.biz.semantic_admin.ol_pipeline.api.routes import router as semantic_admin_pipeline_router

    # ── 语义管理 - QualityGate 16 指标评估 + Dashboard（Iter 2 C1/C2/C3）──
    from odap.biz.semantic_admin.quality_gate.api.routes import router as semantic_admin_quality_gate_router

    # ── 语义管理 - 2 级审批工作流（Iter 2 D1~D5）──
    from odap.biz.semantic_admin.approval_workflow.api.routes import router as semantic_admin_approval_router

    # ── 语义管理 - Candidate CRUD（FR-018/019 List/详情/Modify/软删/批量/导出/Promote）──
    from odap.biz.semantic_admin.candidate_store.api.routes import router as semantic_admin_candidate_router

    # ── 语义管理 - 动态配置（sa_config，内置常量落库）──
    from odap.biz.semantic_admin.sa_config.api.routes import router as semantic_admin_sa_config_router
    from odap.biz.semantic_admin.usl_writeback.api.routes import router as semantic_admin_writeback_router

    # ── 本体 - 运行时 ──
    from odap.biz.core.ontology.application.runtime.api.routes import router as runtime_router
    from odap.biz.core.ontology.application.runtime.state_machine.api.routes import router as state_machine_router

    # ── 本体 - 视图 ──
    from odap.biz.core.ontology.view.api.routes import router as object_view_router

    # ── 本体 - Harness ──
    from odap.biz.core.ontology.application.harness.api.routes import router as harness_router
    from odap.biz.core.ontology.application.harness.blueprint.routes import router as blueprint_designer_router
    from odap.biz.core.ontology.application.harness.blueprint.api.runtime_routes import router as blueprint_runtime_router

    # ── 本体 - 记忆 ──
    from odap.biz.platform.ontology_memory.api.routes import router as ontology_memory_router
    from odap.biz.platform.ontology_memory.api.decay_routes import router as decay_router
    from odap.biz.platform.ontology_memory.graph_sync.routes import router as memory_sync_router
    from odap.biz.platform.ontology_memory.shared_workspace.routes import router as shared_memory_router
    from odap.biz.platform.ontology_memory.shared_workspace.api.consensus_routes import router as consensus_router

    # ── 本体 - 服务化 ──
    from odap.biz.core.ontology.application.servitization.api.routes import router as servitization_router
    from odap.biz.core.ontology.application.servitization.api.deployment_routes import router as deployment_router
    from odap.biz.core.ontology.application.servitization.catalog.routes import router as catalog_router

    # ── 本体 - 动作 ──
    from odap.biz.core.ontology.action.api.routes import router as action_type_router

    # ── 本体 - 消歧图 ──
    from odap.biz.core.ontology.application.abution_graph.api.routes import router as abution_graph_router

    # ── 国际化 ──
    from odap.biz.platform.i18n.api.routes import router as i18n_router

    # ── 本体 - 设计 ──
    from odap.biz.core.ontology.design.model.api.routes import router as ontology_model_router
    from odap.biz.core.ontology.design.engine.api.routes import router as ontology_engine_router
    from odap.biz.core.ontology.design.ingestion.api.routes import router as ingestion_router
    from odap.biz.core.ontology.design.version.api.routes import router as ontology_version_router

    # ── 本体 - 冲突/分支/冷启动/继承/计算 ──
    from odap.biz.core.ontology.conflict.api.routes import router as conflict_router
    from odap.biz.core.ontology.branch.api.routes import router as branch_router
    from odap.biz.core.ontology.cold_start.api.routes import router as cold_start_router
    from odap.biz.core.ontology.inheritance.api.routes import router as inheritance_router
    from odap.biz.core.ontology.computed.api.routes import router as computed_router

    # ── 本体 - 核心 API ──
    from odap.biz.core.ontology.ontology_api.api import router as ontology_api_router
    from odap.biz.core.ontology.extraction.api import router as extraction_router
    from odap.biz.core.ontology.goal.api.routes import router as goal_router

    # ── 工具注册 ──
    from odap.biz.platform.tool_registry.api.routes import router as tool_registry_router

    # ── 撤销 ──
    from odap.biz.platform.undo.api.routes import router as undo_router

    # ── 配置管理 ──
    from odap.biz.platform.config.api.routes import router as config_router

    # ── MinIO 对象存储管理 ──
    from odap.biz.platform.minio_admin.api.routes import router as minio_admin_router

    # ── 菜单配置 ──
    from odap.biz.platform.menu_config.api.routes import router as menu_config_router

    # ── 统一数据摄入 ──
    from odap.biz.data.ingest.api.routes import router as unified_ingest_router

    # ── Web 数据采集 ──
    from odap.biz.data.web_crawl.api.routes import router as web_collection_router

    # ── WebSocket 与监控 ──
    from odap.web.ws.routes import ws_router
    from odap.web.api.monitoring_routes import monitoring_router

    return [
        # 工作空间与角色
        (workspace_router,),
        (scenario_compat_router,),
        (roles_router,),

        # 安全与认证
        (audit_router,),
        (auth_router,),
        (data_classification_router,),

        # 技能与钩子
        (skill_router,),
        (skill_ext_router,),
        (hook_router,),

        # 集成适配
        (mcp_router,),
        (frontend_router,),
        (agent_router,),

        # 渠道管理
        (channel_router,),

        # 智能体
        (agent_dispatch_router,),
        (agent_decision_router,),
        (agent_mgmt_router,),
        (agui_router,),

        # 知识库
        (kb_router,),

        # Hyper-Extract 知识提取（ADR-066）
        (he_router,),

        # 本体 - OMS 与查询
        (oms_router,),
        (ontology_nl_router,),
        (ontology_ingest_router,),

        # 本体 - TypeRegistry
        (registry_router,),

        # 对象服务
        (osv2_router,),

        # 决策
        (action_router,),
        (decision_pipeline_router,),
        (decision_recommendation_router,),

        # 感知
        (perception_router,),

        # 仿真
        (event_router,),
        (sandbox_router,),
        (sandbox_api_router,),
        (parallel_router,),
        (feedback_router,),
        (deduction_router,),

        # 业务管理
        (business_router,),

        # 策略
        (policy_router,),
        (markdown_policy_router,),

        # 会话记忆
        (session_memory_router,),

        # 数据仓库
        (data_warehouse_router,),

        # 查询
        (query_router,),

        # QA
        (qa_router,),
        (qa_nl_router,),

        # AI 助手
        (assistant_router,),
        (unified_chat_router,),          # ADR-050: 统一对话服务 (Phase A 并行)
        (ontology_assistant_router,),

        # 认知
        (cognition_router,),
        (thought_router,),

        # 语义地图
        (semantic_map_router,),

        # 语义管理 - 统一语义层（USL Iter 1）
        (semantic_admin_usl_router,),

        # 语义管理 - OL Pipeline + Candidates（Iter 2 6 层流水线 + HITL）
        (semantic_admin_pipeline_router,),

        # 语义管理 - QualityGate 16 指标评估 + Dashboard（Iter 2 C1/C2/C3）
        (semantic_admin_quality_gate_router,),

        # 语义管理 - 2 级审批工作流（Iter 2 D1~D5）
        (semantic_admin_approval_router,),

        # 语义管理 - Candidate CRUD（FR-018/019）
        (semantic_admin_candidate_router,),

        # 语义管理 - 动态配置（sa_config，内置常量落库）
        (semantic_admin_sa_config_router,),
        (semantic_admin_writeback_router,),

        # 本体 - 运行时
        (runtime_router,),
        (state_machine_router,),

        # 本体 - 视图
        (object_view_router,),

        # 本体 - Harness
        (harness_router,),
        (blueprint_designer_router,),
        (blueprint_runtime_router,),

        # 本体 - 记忆
        (ontology_memory_router,),
        (decay_router,),
        (memory_sync_router,),
        (shared_memory_router,),
        (consensus_router,),

        # 本体 - 服务化
        (servitization_router,),
        (deployment_router,),
        (catalog_router,),

        # 本体 - 动作
        (action_type_router,),

        # 本体 - 消歧图
        (abution_graph_router,),

        # 国际化
        (i18n_router,),

        # 本体 - 设计
        (ontology_model_router,),
        (ontology_engine_router,),
        (ingestion_router,),
        (ontology_version_router,),

        # 本体 - 冲突/分支/冷启动/继承/计算
        (conflict_router,),
        (branch_router,),
        (cold_start_router,),
        (inheritance_router,),
        (computed_router,),

        # 本体 - 核心 API
        (ontology_api_router,),
        (extraction_router,),
        (goal_router,),

        # 工具注册
        (tool_registry_router,),

        # 撤销
        (undo_router,),

        # 配置管理
        (config_router,),

        # MinIO 对象存储管理
        (minio_admin_router,),

        # 菜单配置
        (menu_config_router,),

        # 统一数据摄入
        (unified_ingest_router,),

        # Web 数据采集
        (web_collection_router,),

        # WebSocket 与监控
        (ws_router,),
        (monitoring_router,),
    ]


DEFAULT_ROUTER_REGISTRY = create_router_registry()
