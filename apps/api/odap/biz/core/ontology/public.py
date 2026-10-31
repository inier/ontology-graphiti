"""core.ontology 唯一对外公共 API 门面 (Public Facade).

背景（见架构诊断报告 Stage B）：
    core/ontology 有 540 个 .py 文件、22 个顶级子目录，外部存在 ~162 处
    直接伸进内部实现（design.*/construction.*/application.*/reasoning.* 的
    impl/storage/services 深层路径）的 reach-in 导入，导致内部任何重构都会
    打断外部消费者。

本模块的职责：
    为 core.ontology 提供**唯一稳定的对外 API 面**。其他 biz 域 / infra /
    tools / web 只应从本模块导入 ontology 能力：

        from odap.biz.core.ontology.public import OntologyService, get_oms_service

    禁止再 reach-in 到内部实现路径。内部重构时只需维护本文件的 _PUBLIC_MAP，
    外部消费者无感。

设计要点：
    1. 采用 PEP 562 惰性 __getattr__：导入本模块本身零级联开销，
       不会把 540 文件的 ontology 包拖进 import-time，也规避循环导入。
    2. _PUBLIC_MAP 是「符号 → 真实内部路径」的唯一映射表。
    3. 与 odap.biz.core.ontology.__init__ 的 _legacy_map（DEPRECATED 兼容入口）
       并存：__init__ 是旧路径兼容层，本模块是**推荐的新入口**（不带弃用警告）。
    4. TYPE_CHECKING 块为 IDE / 类型检查器提供静态可见性。

约定：
    - 新增对外符号 → 加到 _PUBLIC_MAP + __all__ + TYPE_CHECKING 块。
    - 标注 TRANSITIONAL 的符号是过渡暴露（存储实现），Stage D 后应改为
      Repository 接口，不再直接外露。
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

# ─────────────────────────────────────────────────────────────────────────
# 符号 → (真实模块路径, 模块内属性名)
# 所有路径均以「真实外部消费者已在用的、运行期可解析的导入路径」为准。
# ─────────────────────────────────────────────────────────────────────────
_PUBLIC_MAP: dict[str, tuple[str, str]] = {
    # ── 核心服务（最高频）──
    "OntologyService": (
        "odap.biz.core.ontology.ontology_api.services.ontology_service",
        "OntologyService",
    ),
    "get_oms_service": (
        "odap.biz.core.ontology.application.oms.services",
        "get_oms_service",
    ),
    "OMSService": (
        "odap.biz.core.ontology.application.oms.services",
        "OMSService",
    ),

    # ── L1 设计层公共契约（ADR-071，跨边界唯一合法入口）──
    "OntologyDesignContract": (
        "odap.biz.core.ontology.design.contract", "OntologyDesignContract",
    ),
    "get_design_contract": (
        "odap.biz.core.ontology.design.contract", "get_design_contract",
    ),
    "DesignContractFacade": (
        "odap.biz.core.ontology.design.contract", "DesignContractFacade",
    ),
    "EntityTypeView": (
        "odap.biz.core.ontology.design.contract", "EntityTypeView",
    ),
    "RelationTypeView": (
        "odap.biz.core.ontology.design.contract", "RelationTypeView",
    ),
    "PropertyView": (
        "odap.biz.core.ontology.design.contract", "PropertyView",
    ),
    "OntologyVersionView": (
        "odap.biz.core.ontology.design.contract", "OntologyVersionView",
    ),
    "OntologyDocumentView": (
        "odap.biz.core.ontology.design.contract", "OntologyDocumentView",
    ),

    # ── L1 设计层服务 / Schema ──
    "ModelService": (
        "odap.biz.core.ontology.design.model.services.model_service", "ModelService",
    ),
    "OntologyVersionManager": (
        "odap.biz.core.ontology.design.services.version_service", "OntologyVersionManager",
    ),
    "SearchService": (
        "odap.biz.core.ontology.design.services.search_service", "SearchService",
    ),
    "deterministic_entity_id": (
        "odap.biz.core.ontology.design.schema.document", "deterministic_entity_id",
    ),
    "OntologyDocumentIO": (
        "odap.biz.core.ontology.design.ingestion_split.document_io", "OntologyDocumentIO",
    ),
    "ENTITY_TYPES": (
        "odap.biz.core.ontology.design.schema.domain", "ENTITY_TYPES",
    ),
    "ROLES": (
        "odap.biz.core.ontology.design.schema.domain", "ROLES",
    ),
    "DOMAIN_CONFIG": (
        "odap.biz.core.ontology.design.schema.domain", "DOMAIN_CONFIG",
    ),

    # ── L2 构建层服务（construction.pipeline 是 design.services 的 L2 桥接）──
    "IngestService": (
        "odap.biz.core.ontology.construction.pipeline.services", "IngestService",
    ),
    "get_ingest_service": (
        "odap.biz.core.ontology.construction.pipeline.services", "get_ingest_service",
    ),
    "PipelineService": (
        "odap.biz.core.ontology.construction.pipeline.services", "PipelineService",
    ),
    "get_pipeline_service": (
        "odap.biz.core.ontology.construction.pipeline.services", "get_pipeline_service",
    ),
    "OntologyBuilderService": (
        "odap.biz.core.ontology.construction.pipeline.services", "OntologyBuilderService",
    ),
    "get_builder_service": (
        "odap.biz.core.ontology.construction.pipeline.services", "get_builder_service",
    ),
    "QAOntologyBuilder": (
        "odap.biz.core.ontology.construction.pipeline.services", "QAOntologyBuilder",
    ),
    "get_qa_builder": (
        "odap.biz.core.ontology.construction.pipeline.services", "get_qa_builder",
    ),
    # ── 构建流水线内部类型（Stage E 死导入修复补入）──
    # 消费者：biz/data/perception/hub.py 需要 OntologyPipeline / LLMExtractionStageHandler /
    # PipelineContext 三个具体名字。construction.pipeline.services 只再导出了 PipelineService
    # 别名，未导出这三个，故直接映射到 L1 design.services.pipeline_service。
    "OntologyPipeline": (
        "odap.biz.core.ontology.design.services.pipeline_service", "OntologyPipeline",
    ),
    "LLMExtractionStageHandler": (
        "odap.biz.core.ontology.design.services.pipeline_service", "LLMExtractionStageHandler",
    ),
    "PipelineContext": (
        "odap.biz.core.ontology.design.services.pipeline_service", "PipelineContext",
    ),
    "BuildResultContract": (
        "odap.biz.core.ontology.construction.contract", "BuildResultContract",
    ),

    # ── +AI 推理层公共契约（ADR-072）──
    "ReasoningServiceContract": (
        "odap.biz.core.ontology.reasoning.contract", "ReasoningServiceContract",
    ),

    # ── TypeRegistry（统一类型定义读写入口）──
    "TypeRegistry": (
        "odap.biz.core.ontology.registry", "TypeRegistry",
    ),
    "get_type_registry": (
        "odap.biz.core.ontology.registry", "get_type_registry",
    ),

    # ── 共享类型（跨层无依赖）──
    "IntentType": (
        "odap.biz.core.ontology.common.types", "IntentType",
    ),
    "ProcessingStatus": (
        "odap.biz.core.ontology.common.types", "ProcessingStatus",
    ),

    # ── L3 应用层：被外部 reach-in 的通用能力，正式提升为公共 API ──
    "DocumentParser": (
        "odap.biz.core.ontology.extraction.impl.document_parser", "DocumentParser",
    ),
    "safe_eval": (
        "odap.biz.core.ontology.application.runtime.state_machine.impl.expression_evaluator",
        "safe_eval",
    ),
    "HealthStatus": (
        "odap.biz.core.ontology.application.servitization.services.deployment_executor",
        "HealthStatus",
    ),
    "OntologyRuntimeService": (
        "odap.biz.core.ontology.application.runtime.services.runtime_service",
        "OntologyRuntimeService",
    ),

    # ── TRANSITIONAL：存储实现，Stage D 后应改为 Repository 接口，勿新增依赖 ──
    # 注：对外暴露干净名 OMSStorage，映射到真实类 SQLiteOMSStorage
    #     （旧 __init__._legacy_map 的 OMSStorage 条目指向不存在的别名，实为坏映射）
    "OMSStorage": (
        "odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage", "SQLiteOMSStorage",
    ),
    # Stage E 死导入修复补入：semantic_map/api/routes.py 使用具体类名 SQLiteOMSStorage
    "SQLiteOMSStorage": (
        "odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage", "SQLiteOMSStorage",
    ),
    "SQLiteModelStorage": (
        "odap.biz.core.ontology.design.model.storage.sqlite_model_storage", "SQLiteModelStorage",
    ),
    "SQLiteIngestStorage": (
        "odap.biz.core.ontology.design.storage.sqlite_ingest_storage", "SQLiteIngestStorage",
    ),

    # ═════════════════════════════════════════════════════════════════════
    # Stage D 扩充：补齐全部「非 router、非死导入」的外部 reach-in 符号，
    # 使本门面成为 core.ontology 完整对外 API 面。每条映射的源模块均已核实
    # 存在、且符号为该模块顶层名（AST 校验），运行期 getattr 必然可解析。
    # ═════════════════════════════════════════════════════════════════════

    # ── L1 设计层文档 Schema 类型（design.schema.document）──
    "ActionStatus": ("odap.biz.core.ontology.design.schema.document", "ActionStatus"),
    "DocType": ("odap.biz.core.ontology.design.schema.document", "DocType"),
    "DocumentMeta": ("odap.biz.core.ontology.design.schema.document", "DocumentMeta"),
    "EntityType": ("odap.biz.core.ontology.design.schema.document", "EntityType"),
    "OntologyAction": ("odap.biz.core.ontology.design.schema.document", "OntologyAction"),
    "OntologyConstraint": ("odap.biz.core.ontology.design.schema.document", "OntologyConstraint"),
    "OntologyDocument": ("odap.biz.core.ontology.design.schema.document", "OntologyDocument"),
    "OntologyDocumentSchema": ("odap.biz.core.ontology.design.schema.document", "OntologyDocumentSchema"),
    "OntologyEntity": ("odap.biz.core.ontology.design.schema.document", "OntologyEntity"),
    "OntologyEvent": ("odap.biz.core.ontology.design.schema.document", "OntologyEvent"),
    "OntologyRelation": ("odap.biz.core.ontology.design.schema.document", "OntologyRelation"),
    "OntologyRule": ("odap.biz.core.ontology.design.schema.document", "OntologyRule"),
    "OntologyValidationError": ("odap.biz.core.ontology.design.schema.document", "OntologyValidationError"),
    "SourceInfo": ("odap.biz.core.ontology.design.schema.document", "SourceInfo"),
    "SourceType": ("odap.biz.core.ontology.design.schema.document", "SourceType"),
    "TemporalInfo": ("odap.biz.core.ontology.design.schema.document", "TemporalInfo"),
    "VersionRef": ("odap.biz.core.ontology.design.schema.document", "VersionRef"),

    # ── L1 设计层领域常量（design.schema.domain）──
    "ONTOLOGY_LAST_UPDATED": ("odap.biz.core.ontology.design.schema.domain", "ONTOLOGY_LAST_UPDATED"),
    "ONTOLOGY_VERSION": ("odap.biz.core.ontology.design.schema.domain", "ONTOLOGY_VERSION"),

    # ── L1 设计层摄入器（design.ingestion_split）──
    "ConflictEventGenerator": ("odap.biz.core.ontology.design.ingestion_split", "ConflictEventGenerator"),
    "FreeNewsIngester": ("odap.biz.core.ontology.design.ingestion_split", "FreeNewsIngester"),
    "ManualInputHandler": ("odap.biz.core.ontology.design.ingestion_split", "ManualInputHandler"),
    "NewsIngester": ("odap.biz.core.ontology.design.ingestion_split", "NewsIngester"),

    # ── L1 设计层服务（search / edit-lock / mock-data）──
    "OHWebSearchProvider": ("odap.biz.core.ontology.design.services.search_service", "OHWebSearchProvider"),
    "get_edit_lock_service": ("odap.biz.core.ontology.design.services.edit_lock_service", "get_edit_lock_service"),
    "load_simulation_data": ("odap.biz.core.ontology.design.mock_data.data_generator", "load_simulation_data"),

    # ── 语义检索（semantic_retrieval）──
    "RetrievalService": ("odap.biz.core.ontology.semantic_retrieval.services.retrieval_service", "RetrievalService"),
    "SearchRequest": ("odap.biz.core.ontology.semantic_retrieval.models.schemas", "SearchRequest"),

    # ── 本体约束编排层（ADR-094 / F6 / F8）──
    "QaPipeline": ("odap.biz.core.ontology.orchestration.pipeline", "QaPipeline"),
    "AnswerEnvelope": ("odap.biz.core.ontology.orchestration.contracts", "AnswerEnvelope"),
    "Provenance": ("odap.biz.core.ontology.orchestration.provenance", "Provenance"),
    "validate_provenance": (
        "odap.biz.core.ontology.orchestration.provenance", "validate_provenance",
    ),
    "TBoxCatalog": ("odap.biz.core.ontology.orchestration.tbox", "TBoxCatalog"),
    "DefaultEvidenceResolver": (
        "odap.biz.core.ontology.orchestration.evidence", "DefaultEvidenceResolver",
    ),
    "QaTraceRepository": (
        "odap.biz.core.ontology.orchestration.repositories.trace_repo", "QaTraceRepository",
    ),

    # ── Goal 驱动的结构变更提案（缺口 → ChangeProposal，ADR-090 子项目 D）──
    # 消费者：odap.biz.semantic_admin.gap_pool.services.gap_service（C3 门面唯一合法入口）
    "create_schema_proposal": (
        "odap.biz.core.ontology.goal.services.schema_proposal",
        "create_schema_proposal",
    ),
    "get_goal_storage": (
        "odap.biz.core.ontology.goal.storage",
        "get_goal_storage",
    ),

    # ── 助手能力（assistant.rules / assistant.tools）──
    "TypeInferenceEngine": ("odap.biz.core.ontology.assistant.rules.type_inference", "TypeInferenceEngine"),
    "completeness_check": ("odap.biz.core.ontology.assistant.tools.completeness_check", "completeness_check"),

    # ── TRANSITIONAL 存储实现补充（Stage E 后应改 Repository 接口）──
    "SQLiteActionStorage": ("odap.biz.core.ontology.action.storage.sqlite_action_storage", "SQLiteActionStorage"),
    "SQLiteOntologyStorage": ("odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage", "SQLiteOntologyStorage"),
    "Storage": ("odap.biz.core.ontology.design.model.storage", "Storage"),
}


__all__ = list(_PUBLIC_MAP.keys())


def __getattr__(name: str) -> Any:
    """PEP 562 惰性解析：按需从真实内部路径加载公共符号。

    这样 `import odap.biz.core.ontology.public` 本身不触发任何重模块加载，
    只有真正取用某符号时才 import 对应内部模块。
    """
    target = _PUBLIC_MAP.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr = target
    module = importlib.import_module(module_path)
    try:
        return getattr(module, attr)
    except AttributeError:
        raise AttributeError(
            f"public facade: {module_path!r} 不再导出 {attr!r}；"
            f"内部重构后请同步更新 core/ontology/public.py 的 _PUBLIC_MAP"
        ) from None


def __dir__() -> list[str]:
    return sorted(__all__)


# ─────────────────────────────────────────────────────────────────────────
# 静态可见性（仅供 IDE / 类型检查器；运行期不执行导入）
# ─────────────────────────────────────────────────────────────────────────
if TYPE_CHECKING:  # pragma: no cover
    from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService
    from odap.biz.core.ontology.application.oms.services import OMSService, get_oms_service
    from odap.biz.core.ontology.design.contract import (
        OntologyDesignContract,
        get_design_contract,
        DesignContractFacade,
        EntityTypeView,
        RelationTypeView,
        PropertyView,
        OntologyVersionView,
        OntologyDocumentView,
    )
    from odap.biz.core.ontology.design.model.services.model_service import ModelService
    from odap.biz.core.ontology.design.services.version_service import OntologyVersionManager
    from odap.biz.core.ontology.design.services.search_service import SearchService
    from odap.biz.core.ontology.design.schema.document import deterministic_entity_id
    from odap.biz.core.ontology.design.ingestion_split.document_io import OntologyDocumentIO
    from odap.biz.core.ontology.design.schema.domain import ENTITY_TYPES, ROLES, DOMAIN_CONFIG
    from odap.biz.core.ontology.construction.pipeline.services import (
        IngestService,
        get_ingest_service,
        PipelineService,
        get_pipeline_service,
        OntologyBuilderService,
        get_builder_service,
        QAOntologyBuilder,
        get_qa_builder,
    )
    from odap.biz.core.ontology.design.services.pipeline_service import (
        OntologyPipeline,
        LLMExtractionStageHandler,
        PipelineContext,
    )
    from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import (
        SQLiteOMSStorage,
    )
    from odap.biz.core.ontology.construction.contract import BuildResultContract
    from odap.biz.core.ontology.reasoning.contract import ReasoningServiceContract
    from odap.biz.core.ontology.registry import TypeRegistry, get_type_registry
    from odap.biz.core.ontology.common.types import IntentType, ProcessingStatus
    from odap.biz.core.ontology.extraction.impl.document_parser import DocumentParser
    from odap.biz.core.ontology.application.runtime.state_machine.impl.expression_evaluator import (
        safe_eval,
    )
    from odap.biz.core.ontology.application.servitization.services.deployment_executor import (
        HealthStatus,
    )
    from odap.biz.core.ontology.application.runtime.services.runtime_service import (
        OntologyRuntimeService,
    )
    from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import (
        SQLiteOMSStorage as OMSStorage,
    )
    from odap.biz.core.ontology.design.model.storage.sqlite_model_storage import SQLiteModelStorage
    from odap.biz.core.ontology.design.storage.sqlite_ingest_storage import SQLiteIngestStorage

    # ── Stage D 扩充符号（与 _PUBLIC_MAP 保持一致）──
    from odap.biz.core.ontology.design.schema.document import (
        ActionStatus,
        DocType,
        DocumentMeta,
        EntityType,
        OntologyAction,
        OntologyConstraint,
        OntologyDocument,
        OntologyDocumentSchema,
        OntologyEntity,
        OntologyEvent,
        OntologyRelation,
        OntologyRule,
        OntologyValidationError,
        SourceInfo,
        SourceType,
        TemporalInfo,
        VersionRef,
    )
    from odap.biz.core.ontology.design.schema.domain import (
        ONTOLOGY_LAST_UPDATED,
        ONTOLOGY_VERSION,
    )
    from odap.biz.core.ontology.design.ingestion_split import (
        ConflictEventGenerator,
        FreeNewsIngester,
        ManualInputHandler,
        NewsIngester,
    )
    from odap.biz.core.ontology.design.services.search_service import OHWebSearchProvider
    from odap.biz.core.ontology.design.services.edit_lock_service import get_edit_lock_service
    from odap.biz.core.ontology.design.mock_data.data_generator import load_simulation_data
    from odap.biz.core.ontology.semantic_retrieval.services.retrieval_service import RetrievalService
    from odap.biz.core.ontology.semantic_retrieval.models.schemas import SearchRequest
    from odap.biz.core.ontology.goal.services.schema_proposal import create_schema_proposal
    from odap.biz.core.ontology.goal.storage import get_goal_storage
    from odap.biz.core.ontology.assistant.rules.type_inference import TypeInferenceEngine
    from odap.biz.core.ontology.assistant.tools.completeness_check import completeness_check
    from odap.biz.core.ontology.action.storage.sqlite_action_storage import SQLiteActionStorage
    from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
        SQLiteOntologyStorage,
    )
    from odap.biz.core.ontology.design.model.storage import Storage
