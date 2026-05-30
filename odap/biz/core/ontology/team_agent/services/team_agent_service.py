import warnings
warnings.warn(
    "TeamAgentService is deprecated. Use HarnessService instead.",
    DeprecationWarning,
    stacklevel=2,
)
from odap.biz.core.ontology.harness.services.harness_service import HarnessService


class TeamAgentService(HarnessService):
    pass


def get_team_agent_service():
    return TeamAgentService.get_instance()
