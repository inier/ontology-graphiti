import warnings
warnings.warn(
    "odap.biz.core.ontology.team_agent is deprecated. Use odap.biz.core.ontology.harness instead.",
    DeprecationWarning,
    stacklevel=2,
)
from .models import (
    AgentRole, TaskStatus, AgentMessage, SubTask, TeamSession,
    RequirementAnalysis, OntologySuggestion,
)
from .interfaces import ITeamAgentService
from .impl import TeamAgentEngine
from .services import TeamAgentService, get_team_agent_service
from .storage import SQLiteTeamAgentStorage, Storage
