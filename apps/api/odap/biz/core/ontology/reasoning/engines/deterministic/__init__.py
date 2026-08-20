"""确定性推理引擎（ADR-075）。

pyDatalog 0.17.4 封装：
- fact_loader         Neo4j ABox → Datalog facts
- rule_loader         规则白名单校验 + Datalog 编译
- datalog_engine      pyDatalog 目标化查询执行器
- trace_builder       推导过程 → rule_trace 结构化输出
- temporal_algebra    Allen 13 区间关系时态推理（纯 Python 零依赖）
"""
