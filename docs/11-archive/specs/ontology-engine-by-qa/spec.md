# 智能问答驱动的本体管理引擎 - 规格说明书

## Why
当前系统缺少通过智能问答自动驱动本体构建与更新的能力。用户提出复杂问题时（如"请分析美伊战争走势"），系统需要自动完成意图分析、本体检索、联网信息获取、本体更新及智能回复的全流程。前端需要实时展示处理进度，提供良好的用户体验。

## What Changes
- **数据摄入模块重构**：实现多类型数据摄入，统一转换为 OntologyDocument 格式
- **本体与图谱管理系统**：建立数据到本体的转换算法，集成 graphiti 图谱构建，实现版本管理
- **本体构建可视化系统**：设计并实现前端界面，展示从原始信息到本体定义的全链路
- **API 交互规范化**：制定统一 API 标准，更新 API 文档
- **设计文档同步**：更新相关设计文档和 ADR
- **代码管理规范**：模块化开发，清晰提交规范
- **自动化测试体系**：构建完整测试机制

## Impact
- Affected capabilities:
  - 智能问答系统
  - 本体管理系统
  - 数据摄入系统
  - 前端可视化界面
- Affected code:
  - `/odap/biz/ontology/` - 本体管理核心模块
  - `/odap/biz/qa/` - 智能问答模块
  - `/frontend/src/modules/` - 前端界面
  - `/app/main.py` - API 路由整合

## ADDED Requirements

### Requirement: 智能问答驱动本体构建
系统 SHALL 在用户提出复杂问题时，自动触发联网搜索、本体更新和智能回复的全流程处理。

#### Scenario: 用户提问触发本体更新
- **Given**: 用户在问答界面输入"请分析美伊战争走势"
- **When**: 系统识别问题需要最新信息
- **Then**:
  1. 系统显示"正在分析您的问题..."
  2. 系统显示联网搜索进度
  3. 系统显示本体更新进度
  4. 系统显示回答生成进度
  5. 系统展示最终回答

### Requirement: 多类型数据摄入
系统 SHALL 支持结构化、半结构化和非结构化数据的统一摄入，所有数据必须转换为 OntologyDocument 标准格式。

#### Scenario: 多种数据源摄入
- **Given**: 系统接收到多种格式的数据
- **When**: 数据摄入模块处理数据
- **Then**: 所有数据被转换为标准的 OntologyDocument 格式

### Requirement: 本体构建可视化
系统 SHALL 提供前端界面，清晰展示：原始信息 → 转化过程 → 本体定义 → 图谱构建 的全链路进度。

#### Scenario: 本体构建进度展示
- **Given**: 本体构建任务进行中
- **When**: 前端请求构建进度
- **Then**: 返回包含各阶段状态的进度信息

### Requirement: 本体版本管理
系统 SHALL 实现版本与场景绑定的本体 ID 管理，支持历史版本查看与恢复。

#### Scenario: 本体版本回溯
- **Given**: 用户选择历史版本
- **When**: 用户请求恢复历史版本
- **Then**: 系统恢复指定的本体版本

### Requirement: API 标准化
系统 SHALL 定义所有 API 的输入输出规范，包括数据类型、格式和示例。

#### Scenario: API 文档完整性
- **Given**: 开发者需要集成 API
- **When**: 开发者查看 API 文档
- **Then**: 文档包含完整的接口说明、参数详情和返回值定义

## MODIFIED Requirements

### Requirement: 新闻摄入功能
新闻摄入功能需要与本体构建流程集成，支持智能问答触发的联网搜索内容处理。

**Previous**: 独立的新闻摄入 API
**Updated**: 与本体构建流程深度集成的新闻摄入模块

### Requirement: 本体语义网络
本体图谱改名为本体语义网络，支持展示本体图结构，点击节点展示该节点信息。

**Previous**: 仅有静态图展示
**Updated**: 支持交互式节点点击查看详情

## REMOVED Requirements

### Requirement: 旧版本体构建流程
**Reason**: 需要被新的智能问答驱动流程替代
**Migration**: 迁移到新的多阶段可视化构建流程

## Technical Architecture

### Core Components

1. **QA Intent Analyzer** - 意图分析与路由
2. **Data Ingestion Pipeline** - 多类型数据摄入管道
3. **Ontology Builder** - 本体构建引擎
4. **Graphiti Integration** - 图谱构建集成
5. **Version Manager** - 版本管理系统
6. **Progress Tracker** - 进度跟踪系统
7. **Frontend UI** - 前端可视化界面

### Data Flow

```
用户提问 → 意图分析 → 联网搜索 → 数据摄入 → 本体构建 → 图谱更新 → 智能回复
     ↓           ↓          ↓          ↓          ↓          ↓
  [进度展示] ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
```

### OntologyDocument 标准格式

参考 `/odap/biz/ontology/models/ontology.py` 中的定义：
- id: 本体文档唯一标识
- name: 本体名称
- description: 本体描述
- status: 本体状态 (draft/validated/published/deprecated)
- version: 版本号
- entities: 实体列表
- relations: 关系列表
- properties: 属性列表
- validation_rules: 验证规则列表
- created_at/updated_at: 时间戳
- created_by/updated_by: 操作者

## Performance Requirements

- 系统响应时间不超过 5 秒（不含联网搜索时间）
- 联网搜索超时时间：30 秒
- 本体构建超时时间：60 秒
- 支持至少 10 个并发请求
- 前端进度更新频率：每秒 1 次