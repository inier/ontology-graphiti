"""数据领域：感知 + 仓库 + QA + 知识库

本包刻意不做任何再导出（规则 14）。原先这里是三段 `try: import X / except Exception: pass`，
其中 `odap.biz.data.qa.qa_engine_v2` 根本不存在（真实模块是 `qa_engine`，类名才是 QAEngineV2），
ModuleNotFoundError 被静默吞掉；另外两个虽然能导入，但全仓库没有任何消费者使用包级名字
（实测 `from odap.biz.data import ...` 零命中）。

需要这些类时请直接导入真实路径，例如：
    from odap.biz.data.perception.hub import PerceptionHub
    from odap.biz.data.qa.qa_engine import QAEngineV2
"""

__all__: list = []
