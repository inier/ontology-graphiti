"""
本体业务 (Ontology Business) — 顶层入口

3+1 分层架构 (ADR-068):
  - design/        (L1 本体设计): 类型/Schema/版本/约束/分支
  - construction/  (L2 本体构建): 摄入/抽取/流水线/分片
  - reasoning/     (+AI 推理能力层): 类型推断/约束建议/一致性校验
  - application/   (L3 本体应用): Chat/OMS/运行时/服务化/查询
  - common/        (共享类型): 跨层枚举与常量

各层之间 MUST 通过 Contract (Frozen Dataclass Views) 进行只读通信。
写入操作走独立的 Bridge 路径。

迁移状态: Phase 0-2 已完成，Phase 3 进行中。
  _legacy_map 将在下一大版本移除。
  新代码请直接从新层导入:
    from odap.biz.core.ontology.common import IntentType
    from odap.biz.core.ontology.construction import BuildResultContract
    from odap.biz.core.ontology.reasoning import ReasoningServiceContract
    from odap.biz.core.ontology.application.chat import UnifiedChatService
"""

import warnings

# 共享类型 (跨层无依赖)
from .common.types import IntentType  # noqa: E402

# L1 Design Contract (只读)
from .design.contract import (  # noqa: E402
    OntologyDesignContract,
    EntityTypeView,
    RelationTypeView,
    PropertyView,
    OntologyVersionView,
    OntologyDocumentView,
    get_design_contract,
)


def __getattr__(name):
    """延迟导入: 兼容旧路径 (DEPRECATED — Phase 3).

    这些旧导入路径将在下一大版本移除。
    请使用新层的直接导入路径。
    """
    _legacy_map = {
        "IngestService": "odap.biz.core.ontology.design.services.ingest_service",
        "OntologyBuilderService": "odap.biz.core.ontology.design.services.build_service",
        "OntologyVersionManager": "odap.biz.core.ontology.design.services.version_service",
        "ValidationService": "odap.biz.core.ontology.design.services.validation_service",
        "ModelService": "odap.biz.core.ontology.design.model.services.model_service",
        "ModelRepository": "odap.biz.core.ontology.design.model.interfaces.model_repository",
        "PipelineService": "odap.biz.core.ontology.design.services.pipeline_service",
        "QAOntologyBuilder": "odap.biz.core.ontology.design.services.qa_ontology_builder",
        "OMSService": "odap.biz.core.ontology.application.oms.services.oms_service",
        "OMSStorage": "odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage",
        "BuildResultContract": "odap.biz.core.ontology.construction.contract",
        "ReasoningServiceContract": "odap.biz.core.ontology.reasoning.contract",
    }
    if name in _legacy_map:
        warnings.warn(
            f"Importing {name} from odap.biz.core.ontology is deprecated. "
            f"Use direct import: from {_legacy_map[name].rsplit('.', 1)[0]} import {name}",
            DeprecationWarning, stacklevel=2,
        )
        import importlib
        try:
            module = importlib.import_module(_legacy_map[name])
            return getattr(module, name)
        except (ImportError, AttributeError):
            module_path = _legacy_map[name].rsplit(".", 1)[0]
            module = importlib.import_module(module_path)
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


OntologyBuildService = None  # deprecated
VersionManagementService = None  # deprecated

__all__ = [
    "IntentType",
    "OntologyDesignContract", "EntityTypeView", "RelationTypeView",
    "PropertyView", "OntologyVersionView", "OntologyDocumentView",
    "get_design_contract",
    "IngestService", "OntologyBuilderService", "OntologyVersionManager",
    "ValidationService", "ModelService", "PipelineService",
    "QAOntologyBuilder", "OMSService",
]
