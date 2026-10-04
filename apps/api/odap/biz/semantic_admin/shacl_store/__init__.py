"""SHACL 治理持久化（ADR-085 S4a）。

本模块承载 SHACL/公理治理的派生持久化：
  · sa_shacl_shape    — 版本键控形状派生缓存（ADR-077 裁决 1 操作化）
  · sa_derived_axiom  — L6 AxiomDeriver 公理持久化（停止丢弃）

S4b 的 sa_axiom_violation 违规队列将并入本模块（同属 SHACL 治理关注点）。
"""
