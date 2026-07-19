"""
L2 Construction Pipeline — 构建流水线服务 (Phase 1 桥接).

当前从 L1 design/services/ 重新导出。
Phase 2 会将实现迁移到此位置，届时这些 wrapper 变为实际实现。
"""

# build_service
from odap.biz.core.ontology.design.services.build_service import (
    OntologyBuilderService,
    get_builder_service,
)

# ingest_service
from odap.biz.core.ontology.design.services.ingest_service import (
    IngestService,
    get_ingest_service,
)

# pipeline_service
from odap.biz.core.ontology.design.services.pipeline_service import (
    PipelineService,
    get_pipeline_service,
)

# qa_ontology_builder
from odap.biz.core.ontology.design.services.qa_ontology_builder import (
    QAOntologyBuilder,
    QABuildProgress,
    QABuildStatus,
    get_qa_builder,
)

__all__ = [
    "OntologyBuilderService", "get_builder_service",
    "IngestService", "get_ingest_service",
    "PipelineService", "get_pipeline_service",
    "QAOntologyBuilder", "QABuildProgress", "QABuildStatus", "get_qa_builder",
]
