import warnings
warnings.warn(
    "SQLiteTeamAgentStorage is deprecated. Use SQLiteHarnessStorage instead.",
    DeprecationWarning,
    stacklevel=2,
)
from odap.biz.core.ontology.application.harness.storage.sqlite_harness_storage import SQLiteHarnessStorage as SQLiteTeamAgentStorage
