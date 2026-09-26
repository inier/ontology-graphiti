"""推演子领域：DeductionService + 路由。

不做包级再导出（规则 14）。原先两段 `try: import / except Exception: pass` 无消费者，
且 `from .simulation_deduction.services import ...` 写在本包 __init__ 里会与子模块自身的
导入形成环。请直接导入真实路径：
    from odap.biz.simulation.simulation_deduction.services import DeductionService
    from odap.biz.simulation.simulation_deduction.api import router
"""

__all__: list = []
