"""
本体业务 (Ontology Business) — 顶层入口

本模块拆分为两个隔离子系统:
  - design/    (本体设计): 定义、版本、构建、摄入
  - application/ (本体应用): 运行、编排、服务化、查询

两个子系统之间 MUST 通过 design/contract/ 进行通信。
This module is split into two isolated subsystems:
  - design/    (Design): definition, versioning, building, ingestion
  - application/ (Application): runtime, orchestration, servitization, queries

The two subsystems MUST communicate only through `design/contract/`.
"""

from .design.contract import (
    OntologyDesignContract,
    EntityTypeView,
    RelationTypeView,
    PropertyView,
    OntologyVersionView,
    OntologyDocumentView,
    get_design_contract,
)

# 兼容旧导入路径: services/ 已经迁移到 design/services/
# 保持外部 API 兼容，让旧的 from odap.biz.core.ontology import X 仍可工作
def __getattr__(name):
    """延迟导入: 兼容旧路径 odap.biz.core.ontology.services.*"""
    _legacy_map = {
        "IngestService": "odap.biz.core.ontology.design.services.ingest_service",
        "OntologyBuilderService": "odap.biz.core.ontology.design.services.build_service",
        "OntologyVersionManager": "odap.biz.core.ontology.design.services.version_service",
        "ValidationService": "odap.biz.core.ontology.design.services.validation_service",
    }
    if name in _legacy_map:
        import importlib
        module = importlib.import_module(_legacy_map[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

OntologyBuildService = None  # deprecated alias, use OntologyBuilderService
VersionManagementService = None  # deprecated alias, use OntologyVersionManager

__all__ = [
    # Public contract types
    "OntologyDesignContract",
    "EntityTypeView",
    "RelationTypeView",
    "PropertyView",
    "OntologyVersionView",
    "OntologyDocumentView",
    "get_design_contract",
    # Legacy class re-exports (lazy)
    "IngestService",
    "OntologyBuilderService",
    "OntologyVersionManager",
    "ValidationService",
]
