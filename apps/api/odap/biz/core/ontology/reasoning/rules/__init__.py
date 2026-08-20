"""推理规则模型与存储（ADR-075 §3）。

BusinessRule 为确定性推理引擎的规则载体（TBox），
规则随本体版本管理，支持版本级回滚快照。
"""

from .models import BusinessRule, RulePriority
from .storage import SQLiteRuleStorage, get_rule_storage

__all__ = [
    "BusinessRule",
    "RulePriority",
    "SQLiteRuleStorage",
    "get_rule_storage",
]
