import warnings
warnings.warn(
    "TeamAgentEngine is deprecated. Use HarnessService instead.",
    DeprecationWarning,
    stacklevel=2,
)
from odap.biz.core.ontology.harness.services.harness_service import HarnessService as TeamAgentEngine
