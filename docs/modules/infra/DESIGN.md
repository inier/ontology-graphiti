# Infrastructure 基础设施模块 - 设计文档

> **优先级**: P0 | **相关 ADR**: ADR-002, ADR-003

**版本**: 1.0.0 | **日期**: 2026-04-16

---

## 1. 模块概述

基础设施模块包含系统运行所需的核心底层组件。

**核心组件**:

| 组件 | 位置 | 职责 |
|------|------|------|
| Graph | `odap/infra/graph/` | 知识图谱管理 |
| OPA | `odap/infra/opa/` | 策略引擎 |
| Events | `odap/infra/events/` | 事件系统 |
| LLM | `odap/infra/llm/` | LLM 接口封装 |
| Resilience | `odap/infra/resilience/` | 容错机制 |
| Config | `odap/infra/config/` | 配置管理 |

---

## 2. 核心架构

```
odap/infra/
├── graph/          # 知识图谱基础设施
│   ├── graph_service.py    # GraphManager
│   └── __init__.py
├── opa/           # OPA 策略引擎
│   ├── opa_service.py
│   └── opa_policy.rego
├── events/        # 事件系统
├── llm/          # LLM 接口
├── resilience/   # 容错机制
└── config/       # 配置管理
```

---

## 3. 相关文档

- [ADR-002: Graphiti 作为双时态知识图谱](../../adr/ADR-002_graphiti_作为双时态知识图谱.md)
- [ADR-003: OPA 策略治理引擎](../../adr/ADR-003_opa_策略治理引擎mvp_生产化.md)
- [Graphiti Client 模块](../graphiti_client/DESIGN.md)
