"""语义管理顶级域（Semantic Admin Domain）。

子服务（分阶段）：
- usl_manager: 统一语义层管理器（Iter 1 生效）
- ol_pipeline: 本体学习流水线（Iter 2）
- candidate_store: 候选术语仓库（Iter 2）
- quality_gate: 质量门禁（Iter 3）
- approval_workflow: 审批工作流（Iter 3）
- usl_writeback: USL -> 本体写回（Iter 4）
- sa_config: 动态语义配置（Iter 1+）
"""

from __future__ import annotations

from odap.biz.semantic_admin.usl_manager.services.usl_manager_service import UslManagerService
from odap.biz.semantic_admin.usl_manager.storage.sqlite_usl_storage import SQLiteUslStorage
from odap.biz.semantic_admin.ol_pipeline.services.pipeline_service import PipelineService
from odap.biz.semantic_admin.candidate_store.services.candidate_service import CandidateService
from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import SQLiteCandidateStorage
from odap.biz.semantic_admin.quality_gate.services.quality_gate_service import QualityGateService
from odap.biz.semantic_admin.quality_gate.services.dashboard_query_service import DashboardQueryService
from odap.biz.semantic_admin.approval_workflow.services.approval_service import ApprovalService
from odap.biz.semantic_admin.usl_writeback.services.writeback_service import WritebackService
from odap.biz.semantic_admin.sa_config.services.sa_config_service import SaConfigService

__all__ = [
    "UslManagerService",
    "SQLiteUslStorage",
    "PipelineService",
    "CandidateService",
    "SQLiteCandidateStorage",
    "QualityGateService",
    "DashboardQueryService",
    "ApprovalService",
    "WritebackService",
    "SaConfigService",
]
