"""本体管理引擎模块"""

from .services.ingest_service import IngestService
from .services.build_service import OntologyBuilderService
from .services.version_service import OntologyVersionManager
from .services.validation_service import ValidationService

OntologyBuildService = OntologyBuilderService
VersionManagementService = OntologyVersionManager

__all__ = [
    "IngestService",
    "OntologyBuildService",
    "OntologyBuilderService",
    "OntologyVersionManager",
    "VersionManagementService",
    "ValidationService"
]
