# 架构决策记录（ADR）

本目录存放所有架构决策记录（Architecture Decision Records）。

## 索引

### 核心基础设施（P0）

| ADR | 决策标题 | 状态 | 优先级 | 文件 |
|-----|---------|------|--------|------|
| ADR-001 | Agent 基础设施（OpenHarness + LangGraph） | 已接受 | P0 | [ADR-001](ADR-001_agent_基础设施openharness_langgraph.md) |
| ADR-002 | Graphiti 作为双时态知识图谱 | 已接受 | P0 | [ADR-002](ADR-002_graphiti_作为双时态知识图谱.md) |
| ADR-003 | OPA 策略治理引擎（MVP + 生产化） | 已接受 | P0 | [ADR-003](ADR-003_opa_策略治理引擎mvp_生产化.md) |
| ADR-004 | 统一 Skill 体系架构 | 已接受 | P0 | [ADR-004](ADR-004_统一_skill_体系架构.md) |
| ADR-005 | 分层 Agent 架构（OpenHarness 原生 + 领域扩展） | 已接受 | P0 | [ADR-005](ADR-005_分层_agent_架构openharness_原生_领域扩展.md) |
| ADR-006 | OpenHarness 复用策略（完全复用 + 适配复用 + 独立扩展） | 已接受 | P0 | [ADR-006](ADR-006_openharness_复用策略完全复用_适配复用_独立扩展.md) |

### 前端与交互（P0/P1 混合）

| ADR | 决策标题 | 状态 | 优先级 | 文件 |
|-----|---------|------|--------|------|
| ADR-007 | 前端采用 React + Ant Design 技术栈 | 已接受 | P0 | [ADR-007](ADR-007_前端采用_react_ant_design_技术栈.md) |
| ADR-014 | 技能热插拔架构 | 已接受 | P0 | [ADR-014](ADR-014_技能热插拔架构.md) |
| ADR-015 | 可扩展图表系统 | 已接受 | P1 | [ADR-015](ADR-015_可扩展图表系统.md) |
| ADR-020 | 管理员控制台统一界面 | 已接受 | P0 | [ADR-020](ADR-020_管理员控制台统一界面.md) |

### 安全与治理（P0 为主）

| ADR | 决策标题 | 状态 | 优先级 | 文件 |
|-----|---------|------|--------|------|
| ADR-008 | 审计日志完整记录 | 已接受 | P0 | [ADR-008](ADR-008_审计日志完整记录.md) |
| ADR-009 | Markdown 编写 OPA 策略 | 已接受 | P0 | [ADR-009](ADR-009_markdown_编写_opa_策略.md) |
| ADR-028 | OPA 作为统一权限校验引擎 | 已接受 | P0 | [ADR-028](ADR-028_permission_checker_opa_integration.md) |

### 数据与集成（P1）

| ADR | 决策标题 | 状态 | 优先级 | 文件 |
|-----|---------|------|--------|------|
| ADR-012 | 配置组合引擎 | 已接受 | P1 | [ADR-012](ADR-012_配置组合引擎.md) |
| ADR-013 | 多数据源统一接入 | 已接受 | P1 | [ADR-013](ADR-013_多数据源统一接入.md) |
| ADR-018 | 模拟领域数据生成引擎 | 已接受 | P1 | [ADR-018](ADR-018_模拟领域数据生成引擎.md) |
| ADR-021 | 战争实体标准本体库 | 已接受 | P1 | [ADR-021](ADR-021_战争实体标准本体库.md) |
| ADR-022 | 模拟数仓与统一查询服务 | 提议中 | P1 | [ADR-022](ADR-022_模拟数仓与统一查询服务.md) |
| ADR-026 | 采用 MCP 协议作为外部系统集成标准 | 已接受 | P1 | [ADR-026](ADR-026_mcp_protocol_integration.md) |
| ADR-031 | 模拟器 Web 可视化与实时本体热写入架构 | 已接受 | P0 | [ADR-031](ADR-031_simulator_web_visualization_realtime_ontology.md) |
| ADR-032 | 标准化本体文档格式（OntologyDocument） | 已接受 | P0 | [ADR-032](ADR-032_standard_ontology_document_format.md) |

### 平台架构（P0/P1 混合）

| ADR | 决策标题 | 状态 | 优先级 | 文件 |
|-----|---------|------|--------|------|
| ADR-010 | 多模态文档处理可配置 | 已接受 | P1 | [ADR-010](ADR-010_多模态文档处理可配置.md) |
| ADR-011 | 角色配置热生效 | 已接受 | P0 | [ADR-011](ADR-011_角色配置热生效.md) |
| ADR-016 | 完备文档体系 | 已接受 | P1 | [ADR-016](ADR-016_完备文档体系.md) |
| ADR-017 | 原子提交规范 | 已接受 | P0 | [ADR-017](ADR-017_原子提交规范.md) |
| ADR-019 | 多模态文档处理流水线 | 已接受 | P1 | [ADR-019](ADR-019_多模态文档处理流水线.md) |
| ADR-023 | 多工作空间隔离架构 | 已接受 | P0 | [ADR-023](ADR-023_多工作空间隔离架构.md) |
| ADR-024 | 本体驱动分析核心架构 | 已接受 | P0 | [ADR-024](ADR-024_本体驱动分析核心架构.md) |
| ADR-025 | 基于 OpenHarness 实现多智能体协同 | 已接受 | P0 | [ADR-025](ADR-025_openharness_integration.md) |

### 扩展机制（P1）

| ADR | 决策标题 | 状态 | 优先级 | 文件 |
|-----|---------|------|--------|------|
| ADR-027 | Hook 系统作为可扩展性核心架构 | 已接受 | P1 | [ADR-027](ADR-027_hook_system_architecture.md) |
| ADR-029 | 统一工具注册表架构管理 AI Agent 工具 | 已接受 | P1 | [ADR-029](ADR-029_tool_registry_architecture.md) |

### 演进决策（P1）

| ADR | 决策标题 | 状态 | 优先级 | 文件 |
|-----|---------|------|--------|------|
| ADR-030 | Phase 1 推迟引入 OpenHarness，保留现有编排器 | 已接受 | P1 | [ADR-030](ADR-030_phase1_推迟引入openharness_保留现有编排器.md) |
| ADR-033 | 项目目录结构重构（分层模块化 odap/ 包） | 提议 | P0 | [ADR-033](ADR-033_项目目录结构重构.md) |

---

## ADR 模板

新建 ADR 时请使用以下模板：

```markdown
# ADR-XXX: [决策标题]

## 状态
提议 | 已接受 | 已弃用 | 被 ADR-XXX 取代

## 上下文
我们看到的促使此决策的问题是什么？

## 决策
我们提议和/或正在进行的更改是什么？

## 后果
因为此更改，什么变得更容易或更难？

## 可逆性
高 | 中 | 低。说明如何逆转此决策。
```

## 编号规则

- ADR-001 ~ ADR-024：从 `ARCHITECTURE.md` 第 17 章提取的核心架构决策
- ADR-025 ~ ADR-029：从独立 ADR 文件迁移的详细决策（原编号 ADR-006~010）
- ADR-030：Phase 1+ 演进决策（OpenHarness 推迟）
- ADR-031 ~ ADR-032：Phase 3 模拟器增强（Web 可视化 + 标准本体格式）
- ADR-033：Phase 3+ 项目目录结构重构（分层模块化）
- ADR-034 ~ ：后续新增，按时间顺序递增
