"""仿真领域：事件 + 沙箱 + 反馈 + 可视化 + 推演

ADR-065: interfaces/ 提供 IOMSService/IModelService/IRuntimeService/IHookService 抽象接口。
这四个契约是本包对外的稳定面，保持无保护的直接导入——导入失败就该在启动时炸出来。

其余子模块不再做包级再导出（规则 14）：原先五段 `try: import / except Exception: pass`
没有任何消费者（实测 `from odap.biz.simulation import ...` 零命中），只会把真实的导入故障
吞成"名字不存在"，直到很远的调用点才以 AttributeError 暴露。请直接导入真实路径，例如：
    from odap.biz.simulation.feedback.loop import FeedbackLoop
    from odap.biz.simulation.visualization.visualization_engine import VisualizationEngineV2
    from odap.biz.simulation.simulation_deduction.services import DeductionService
"""

from odap.biz.simulation.interfaces import (
    IOMSService, IModelService, IRuntimeService, IHookService,
)

__all__ = [
    "IOMSService", "IModelService", "IRuntimeService", "IHookService",
]
