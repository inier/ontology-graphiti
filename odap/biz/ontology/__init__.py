"""本体管理引擎模块"""

from .services.ingest_service import IngestService
from .services.build_service import OntologyBuilderService
from .services.version_service import VersionManagementService
from .services.validation_service import ValidationService

# 别名兼容
OntologyBuildService = OntologyBuilderService

__all__ = [
    "IngestService",
    "OntologyBuildService",
    "OntologyBuilderService",
    "VersionManagementService",
    "ValidationService"
]
