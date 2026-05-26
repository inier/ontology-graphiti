"""服务层"""

from .ingest_service import IngestService
from .build_service import OntologyBuilderService, get_builder_service
from .version_service import VersionManagementService
from .validation_service import ValidationService
from .transform_service import OntologyTransformService, get_transform_service
from .qa_ontology_builder import QAOntologyBuilder, get_qa_builder
from .api_version import APIVersionController, get_version_controller

# 别名兼容
OntologyBuildService = OntologyBuilderService

__all__ = [
    "IngestService",
    "OntologyBuildService",
    "OntologyBuilderService",
    "get_builder_service",
    "VersionManagementService",
    "ValidationService",
    "OntologyTransformService",
    "get_transform_service",
    "QAOntologyBuilder",
    "get_qa_builder",
    "APIVersionController",
    "get_version_controller"
]
