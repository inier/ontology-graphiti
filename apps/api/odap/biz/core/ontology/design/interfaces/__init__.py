"""接口定义"""

from .audit import IDataIngestAudit
from .builder import IOntologyBuilder
from ..engine.interfaces.version_manager import VersionManager as IVersionManager
from .validation import IValidationEngine
from .dashboard import IAuditDashboard

__all__ = [
    "IDataIngestAudit",
    "IOntologyBuilder",
    "IVersionManager",
    "IValidationEngine",
    "IAuditDashboard"
]
