"""OntoFlow Goal-driven 演化 (FR-037)

OntoFlow 是 Palantir OntoFlow 范式的 ODAP 实现：把"业务目标 (Goal)"作为
本体演化的第一类公民，通过 ChangeProposal → ImpactAnalysis 闭环治理本体的
结构性变更。

核心实体:
- Goal: 业务目标 (proposed/approved/rejected/in-progress/achieved/abandoned)
- ChangeProposal: 针对 Goal 的结构化变更提案 (JSON Patch 格式)
- ImpactAnalysis: 变更影响分析 (受影响类型 + breaking changes + 迁移成本)
"""
