import warnings
warnings.warn(
    "odap.biz.core.ontology.team_agent is deprecated. Use odap.biz.core.ontology.harness instead.",
    DeprecationWarning,
    stacklevel=2,
)
from odap.biz.core.ontology.harness.models import (
    AgentRole, AgentMessage, SubTask, StageStatus as TaskStatus,
    RequirementAnalysis, OntologySuggestion,
    HarnessStage, HITLRiskLevel, StageResult, HITLConfirmation,
    AgentTask, HarnessSession, BlueprintNode, BlueprintEdge, OntologyBlueprint,
)


class TeamSession(HarnessSession):
    pass
