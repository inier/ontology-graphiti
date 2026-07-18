"""Decision 接口层 — 所有抽象定义

ADR-065 舱壁先行：此目录下的接口是 decision 对外部依赖的唯一接触点。
"""

from odap.biz.decision.interfaces.idecision_oms_service import IDecisionOMSService
from odap.biz.decision.interfaces.isemantic_retriever import ISemanticRetriever

__all__ = [
    "IDecisionOMSService",
    "ISemanticRetriever",
]
