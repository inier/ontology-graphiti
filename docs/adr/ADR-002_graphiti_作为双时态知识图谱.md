# ADR-002: Graphiti 作为双时态知识图谱

> **来源**: `docs/ARCHITECTURE.md` 第 17 章

---


**状态**: 已接受

**上下文**: 需要支撑"当时发生了什么"的历史回溯和时间区间查询

**决策**: Graphiti 作为 Memory 层，Neo4j 作为底层图数据库

**后果**:
- ✅ 原生支持双时态（valid_time + transaction_time）
- ✅ Episode 设计天然匹配战场事件流
- ✅ 支持时序推理和 RAG 增强
- ❌ Graphiti 相对新兴，社区较小
- ❌ 需适配 OpenHarness Memory 接口

**可逆性**: 中。替换为纯 Neo4j 或其他图数据库需重写记忆层。

---