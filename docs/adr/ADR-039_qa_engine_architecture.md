# ADR-039: 问答引擎架构

## 状态
已接受

## 上下文

ODAP 平台需要一个问答引擎（M-12），作为用户与知识图谱的主要交互界面。核心需求：

1. **自然语言提问**：用户无需学习查询语言，直接用自然语言提问
2. **RAG 增强**：从 Graphiti 双时态知识图谱检索事实，结合 LLM 生成答案
3. **双时态推理**：支持"当时发生了什么"类时间感知问题
4. **溯源追踪**：每个答案附带来源节点/边，支持跳转验证
5. **多轮对话**：维护会话上下文，支持追问和澄清
6. **复杂问题升级**：超出 QA 能力时，升级到 Intelligence Agent 处理

### 架构选择

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A. 单体 QA Pipeline** | 查询理解→检索→生成→溯源 线性流水线 | 简单、易调试 | 不支持工具调用、无法升级到 Agent |
| **B. QA + Agent 双层** | 简单问题走 QA Pipeline，复杂问题升级到 Agent | 分层处理、资源效率高 | 需要准确的路由判断 |
| **C. 纯 Agent 驱动** | 所有问题都通过 Agent ReAct 循环处理 | 统一架构、工具灵活 | 延迟高、成本高、简单问题浪费 |

## 决策

**采用方案 B：QA + Agent 双层架构**。

### 架构设计

```
用户提问
    │
    ▼
QueryUnderstanding（查询理解）
    ├── 意图分类（简单查询 / 复杂分析 / 工具调用）
    ├── 时间表达式解析
    └── 实体识别
    │
    ├── 简单查询 ──▶ RetrievalOrchestrator ──▶ AnswerGenerator ──▶ SourceTracker
    │                   │                         │                   │
    │                   ▼                         ▼                   ▼
    │               Graphiti.search()         LLM.generate()     溯源链路
    │               三层降级检索
    │
    └── 复杂分析 ──▶ Intelligence Agent（ReAct 循环 + 工具调用）
                         │
                         ▼
                     Agent Response → SourceTracker
```

### 核心组件

| 组件 | 职责 |
|------|------|
| QAEngine | 入口协调器，管理会话和路由 |
| QueryUnderstanding | 意图分类 + 时间解析 + 实体识别 |
| RetrievalOrchestrator | 三层降级检索（向量→关键词→内存） |
| AnswerGenerator | LLM 生成 + Prompt 工程 |
| SourceTracker | 答案→源 Episode/Entity 溯源 |
| DialogManager | 多轮上下文管理（窗口 + 摘要） |
| TemporalQueryParser | "上周"/"事件发生时"→双时态查询参数 |

### 路由策略

| 意图 | 路由目标 | 判断依据 |
|------|---------|---------|
| 简单事实查询 | QA Pipeline | 单实体、无推理链 |
| 关系查询 | QA Pipeline | 实体间关系、路径 |
| 时间查询 | QA Pipeline + TemporalQueryParser | 含时间表达式 |
| 复杂分析 | Intelligence Agent | 需多步推理/工具调用 |
| 需决策 | Commander Agent | 涉及行动方案 |

## 后果

### 变得更容易

- **简单问题快速响应**：QA Pipeline 不经过 Agent 循环，延迟低
- **成本可控**：简单查询仅需 1 次 LLM 调用（生成），复杂查询才走 ReAct
- **可扩展**：新增意图类型只需扩展 QueryUnderstanding

### 变得更难

- **路由准确性**：意图分类错误会导致简单问题走 Agent（浪费）或复杂问题走 QA（质量差）
- **双路径维护**：QA Pipeline 和 Agent 路径需分别维护和测试
- **溯源统一**：QA 溯源（Graphiti 检索结果）和 Agent 溯源（ReAct 步骤）格式不同，需统一展示

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| 意图分类准确率不足 | 置信度阈值 + 人工确认 + 自动学习 |
| Agent 升级延迟过高 | 流式输出 + 超时降级到 QA |
| 溯源格式不统一 | SourceTracker 统一输出 SourceTrace 结构 |

## 可逆性

**中**。QA Pipeline 和 Agent 是两个独立路径，可以分别演进。如果 QA Pipeline 能力增强（如支持工具调用），可以逐步收敛到单路径。但双层架构的接口（QueryUnderstanding 路由、DialogManager 共享）修改成本中等。

## 关联

- 关联 ADR-002（Graphiti 知识图谱）
- 关联 ADR-005（分层 Agent 架构）
- 关联 M-12 DESIGN.md
- 影响 WR-13（问答引擎）
