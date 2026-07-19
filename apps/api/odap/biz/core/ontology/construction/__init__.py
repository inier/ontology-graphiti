"""L2 Construction — 本体构建层。

子模块:
- contract/    — BuildResultContract (只读 Frozen Views)
- ingestion/   — 统一摄入子系统
- extraction/  — 信息抽取
- pipeline/    — 六步构建流水线
- quality/     — 质量门禁
- provenance/  — 溯源追踪
- rollback/    — 回滚机制
- sharding/    — 分片策略

遵循 ADR-068 四层架构。
"""

from .contract import (
    BuildResultContract,
    EntityInstanceView,
    RelationInstanceView,
    BuildStatusView,
    QualityReportView,
    IngestionSourceView,
)
from .contract.bridge import get_ingest_service, get_builder_service, get_pipeline_service

from .provenance.provenance_linker import ProvenanceChain, ProvenanceLinker, get_provenance_linker
from .provenance.provenance_query import ProvenanceQuery, get_provenance_query

from .quality.gate import QualityGate, GateLevel, GateAction, GateResult, get_quality_gate
from .quality.reporter import QualityReport

from .rollback.rollback_manager import RollbackLevel, RollbackStatus, RollbackRecord, ConstructionRollbackManager, get_rollback_manager

__all__ = [
    "BuildResultContract",
    "EntityInstanceView",
    "RelationInstanceView",
    "BuildStatusView",
    "QualityReportView",
    "IngestionSourceView",
    "get_ingest_service",
    "get_builder_service",
    "get_pipeline_service",
    "ProvenanceChain", "ProvenanceLinker", "get_provenance_linker",
    "ProvenanceQuery", "get_provenance_query",
    "QualityGate", "GateLevel", "GateAction", "GateResult", "get_quality_gate",
    "QualityReport",
    "RollbackLevel", "RollbackStatus", "RollbackRecord",
    "ConstructionRollbackManager", "get_rollback_manager",
]
