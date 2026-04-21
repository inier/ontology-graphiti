"""接口定义"""

from .audit import IDataIngestAudit
from .builder import IOntologyBuilder
from .version import IVersionManager
from .validation import IValidationEngine
from .dashboard import IAuditDashboard

__all__ = [
    "IDataIngestAudit",
    "IOntologyBuilder",
    "IVersionManager",
    "IValidationEngine",
    "IAuditDashboard"
]
