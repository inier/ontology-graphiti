"""
L2 Construction — 写操作桥接 (Bridge).

Construction 的写入操作（ingestion、pipeline 执行）
通过此桥接暴露，不通过 BuildResultContract（只读）。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from odap.biz.core.ontology.construction.pipeline.services import IngestService
    from odap.biz.core.ontology.construction.pipeline.services import OntologyBuilderService
    from odap.biz.core.ontology.construction.pipeline.services import PipelineService


def get_ingest_service():
    """获取摄入服务实例（写操作桥接）"""
    from odap.biz.core.ontology.construction.pipeline.services import IngestService
    return IngestService()


def get_builder_service():
    """获取构建服务实例（写操作桥接）"""
    from odap.biz.core.ontology.design.services.build_service import (
        get_builder_service as _get,
    )
    return _get()


def get_pipeline_service():
    """获取流水线服务实例（写操作桥接）"""
    from odap.biz.core.ontology.design.services.pipeline_service import (
        get_pipeline_service as _get,
    )
    return _get()


__all__ = ["get_ingest_service", "get_builder_service", "get_pipeline_service"]
