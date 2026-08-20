"""验证 reasoning 包可正常导入（pyDatalog 环境）"""
from odap.biz.core.ontology.reasoning import (
    get_reasoning_service_v2,
    DatalogEngine,
    RuleLoader,
    HybridStrategy,
    BusinessRule,
)
from odap.biz.core.ontology.reasoning.engines.deterministic.temporal_algebra import (
    relation, Interval, ALLEN_RELATIONS,
)
from odap.biz.core.ontology.reasoning.rules.storage import SQLiteRuleStorage

print("import OK")
print("allen relations:", len(ALLEN_RELATIONS))
print("relation(1,2)-(3,4):", relation(Interval(1, 2), Interval(3, 4)))
