"""Simulation 接口层 — 所有抽象定义

ADR-065 舱壁先行：此目录下的接口是 simulation 对外部依赖的唯一接触点。
"""

from odap.biz.simulation.interfaces.ioms_service import IOMSService
from odap.biz.simulation.interfaces.imodel_service import IModelService
from odap.biz.simulation.interfaces.iruntime_service import IRuntimeService
from odap.biz.simulation.interfaces.ihook_service import IHookService

__all__ = [
    "IOMSService",
    "IModelService",
    "IRuntimeService",
    "IHookService",
]
