"""OntoFlow Goal - 领域模型层"""
from .goal import Goal, GoalStatus
from .impact import ImpactAnalysis, ImpactCost, RiskLevel
from .proposal import ChangeProposal, ProposalStatus

__all__ = [
    "Goal",
    "GoalStatus",
    "ChangeProposal",
    "ProposalStatus",
    "ImpactAnalysis",
    "ImpactCost",
    "RiskLevel",
]
