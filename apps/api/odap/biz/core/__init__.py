"""核心领域：本体 + 认知 + Agent"""

# 注意（Stage A.2）：此处曾执行 `from odap.biz.core.ontology import *`，
# 会把整个 ontology.__all__ 喷进 odap.biz.core 命名空间，并在 import odap.biz.core 时
# 触发 ontology 包（540 文件）的 eager 级联加载。经全仓核实无任何代码通过
# `from odap.biz.core import <ontology符号>` 消费这些名字，故移除该 star 再导出。
# 需要 ontology 能力请走唯一对外门面：
#     from odap.biz.core.ontology.public import OntologyService, get_oms_service, ...

# 同理移除 cognition 的 `try: import / except Exception: pass` 再导出（规则 14）：
# 模块与 UserCognitionEngine / get_cognition_engine 都真实存在，但全仓无任何
# `from odap.biz.core import <cognition符号>` 消费者，__all__ 也只声明 DomainSwarm。
# 那段 except 唯一的作用是把将来的导入故障吞掉。需要时请直接导入：
#     from odap.biz.core.cognition.user_cognition_engine import get_cognition_engine

from odap.biz.core.agent import DomainSwarm

__all__ = ['DomainSwarm']
