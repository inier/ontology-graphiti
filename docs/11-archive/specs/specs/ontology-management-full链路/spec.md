# 本体管理链路重构 - 规格说明书

## Why

当前本体管理功能存在以下核心问题：
1. 菜单结构不合理（工作空间应归入系统配置）
2. 本体构建流程未完整可视化，仅有动画缺乏实际处理过程和审计日志
3. 各环节（摄入→清洗→LLM归纳→本体构建→版本管理→图谱生成）未与本体版本关联
4. 缺乏完整的处理日志和可审计性
5. 智能问答与本体构建流程未统一调度
6. OpenHarness 的 SubAgent 和 Skill 规划不明确

## What Changes

### 1. 菜单结构调整
- 将「工作空间」从「本体管理区」移至「系统配置区」

### 2. 本体构建全链路可视化
实现六个阶段的完整可视化，每个阶段必须包含：
- 实际处理过程（不是动画，而是真实数据）
- 每一步的处理日志（可审计）
- 与本体版本的关联
- 可切换查看不同版本的处理详情

### 3. 功能可用性
- 数据摄入：点击摄入历史可查看详情，可切换到对应本体版本
- 数据清洗：显示清洗日志，与本体版本关联
- LLM归纳：显示提取的实体/关系/事件，与本体版本关联
- 本体构建：显示生成的 OntologyDocument，可验证
- 版本管理：创建版本记录，可切换版本
- 图谱生成：构建 Neo4j 图谱，可查看和操作

### 4. 审计日志集成
- 利用 graphiti 存储审计日志
- 构建审计本体
- 提供独立的审计功能页面

### 5. 智能问答路由
- 用户认知引擎识别必要信息
- 自动路由到本体构建流程

### 6. OpenHarness 架构规划
- SubAgent: 负责复杂决策和编排
- Skill: 负责单一职责的具体执行

## Impact

### Affected capabilities:
- 本体管理系统
- 智能问答系统
- 审计日志系统
- 前端可视化界面
- OpenHarness 自动化管理

### Affected code:
- `/frontend/src/modules/` - 前端界面重构
- `/odap/biz/ontology/` - 本体管理核心模块
- `/odap/biz/qa/` - 智能问答模块
- `/odap/infra/openharness/` - SubAgent 和 Skill 定义

## ADDED Requirements

### Requirement: 菜单结构调整
系统 SHALL 将「工作空间」菜单项从「本体管理区」移至「系统配置区」。

#### Scenario: 菜单结构验证
- **Given**: 用户打开系统导航
- **When**: 用户查看菜单项
- **Then**:
  - 「工作空间」显示在「系统配置区」
  - 「本体管理区」仅包含：本体语义网络、数据摄入、版本管理

### Requirement: 本体构建全链路可视化
系统 SHALL 完整展示六个阶段的处理过程，每个阶段必须包含实际数据和审计日志。

#### Scenario: 数据摄入触发全链路
- **Given**: 用户执行数据摄入操作
- **When**: 摄入数据后
- **Then**:
  1. 显示「数据摄入」阶段详情（原始数据、数据源信息）
  2. 自动进入「数据清洗」阶段，显示清洗日志
  3. 自动进入「LLM归纳」阶段，显示提取的实体/关系/事件
  4. 自动进入「本体构建」阶段，显示生成的 OntologyDocument
  5. 自动进入「版本管理」阶段，创建版本记录
  6. 自动进入「图谱生成」阶段，构建图谱

#### Scenario: 查看历史处理详情
- **Given**: 用户点击某条摄入历史
- **When**: 查看历史处理详情
- **Then**:
  - 显示该摄入对应的完整处理链路
  - 可切换到该摄入产生的本体版本
  - 显示每个阶段的处理日志

### Requirement: 摄入历史与版本关联
系统 SHALL 实现摄入历史与本体版本的关联，支持版本切换。

#### Scenario: 摄入历史查看版本
- **Given**: 用户点击摄入历史
- **When**: 查看摄入详情
- **Then**:
  - 显示该摄入关联的本体版本
  - 提供「切换到该版本」按钮
  - 显示该版本的实体/关系统计

### Requirement: 处理日志审计
系统 SHALL 记录并展示每个阶段的处理日志，支持审计追溯。

#### Scenario: 查看处理日志
- **Given**: 用户在本体构建过程中
- **When**: 查看当前处理阶段
- **Then**:
  - 实时显示该阶段的处理日志
  - 日志包含：时间戳、阶段名称、操作详情、结果状态

### Requirement: 智能问答路由
系统 SHALL 通过用户认知引擎识别必要信息，自动路由到本体构建流程。

#### Scenario: QA 触发本体更新
- **Given**: 用户在问答界面提问
- **When**: 系统识别需要本体更新
- **Then**:
  1. 显示「正在分析您的问题...」
  2. 识别需要更新的信息类型
  3. 自动触发本体构建流程
  4. 显示构建进度和结果

### Requirement: OpenHarness SubAgent 规划
系统 SHALL 定义清晰的 SubAgent 职责划分。

#### SubAgent 列表:
1. **OntologyBuilderAgent** - 本体构建编排
   - 协调各阶段执行
   - 管理阶段间数据传递
   - 处理异常和回退

2. **IntentRouterAgent** - 意图路由
   - 分析用户查询意图
   - 决定是否触发本体构建
   - 选择合适的处理流程

3. **AuditLoggerAgent** - 审计日志
   - 记录所有处理操作
   - 生成审计报告
   - 追溯处理历史

### Requirement: OpenHarness Skill 规划
系统 SHALL 定义清晰的 Skill 职责划分。

#### Skill 列表:
1. **data_ingestion_skill** - 数据摄入
   - 执行多类型数据摄入
   - 数据格式转换

2. **data_cleaning_skill** - 数据清洗
   - 去重、标准化
   - 缺失值处理

3. **llm_extraction_skill** - LLM 提取
   - 实体识别
   - 关系抽取
   - 事件建模

4. **ontology_builder_skill** - 本体构建
   - 生成 OntologyDocument
   - 验证结构

5. **version_manager_skill** - 版本管理
   - 创建版本
   - 版本切换

6. **graph_builder_skill** - 图谱构建
   - Neo4j 图谱生成
   - 图谱查询

7. **audit_logger_skill** - 审计日志
   - 记录操作日志
   - 生成审计报告

### Requirement: 审计本体构建
系统 SHALL 利用 graphiti 存储审计日志，并构建独立的审计本体。

#### Scenario: 审计日志记录
- **Given**: 本体构建过程执行
- **When**: 各阶段处理时
- **Then**:
  - 记录操作到 graphiti 审计日志
  - 构建审计本体（事件类型、操作者、时间戳等）
  - 提供独立的审计查询页面

## MODIFIED Requirements

### Requirement: 数据摄入功能
**Previous**: 独立的数据摄入，仅有动画展示
**Updated**: 必须触发完整本体构建链路，并记录处理日志

### Requirement: 本体语义网络
**Previous**: 静态图展示
**Updated**: 与版本关联，可切换版本，支持节点详情

### Requirement: 版本管理
**Previous**: 仅版本列表展示
**Updated**: 与摄入历史关联，支持从摄入历史切换版本

### Requirement: 智能问答
**Previous**: 独立的问答功能
**Updated**: 集成用户认知引擎，可路由到本体构建

## REMOVED Requirements

### Requirement: 单独的本体构建菜单
**Reason**: 本体构建流程已融入数据摄入页面
**Migration**: 通过数据摄入触发的完整链路

## Technical Architecture

### Frontend Menu Structure

```
本体管理区:
├── 本体语义网络 - 图谱可视化，与版本关联
├── 数据摄入 - 触发完整链路，查看历史和处理日志
└── 版本管理 - 版本列表，切换版本

系统配置区:
├── 审计日志 - 独立审计功能
├── 工作空间 - 工作空间管理
└── ... (其他配置项)

用户操作区:
├── 智能问答 - 集成认知引擎，可触发本体构建
└── ... (其他操作项)
```

### Backend Processing Pipeline

```
数据摄入请求
    ↓
[Skill: data_ingestion_skill]
    ↓ 原始数据 + 摄入日志
[Skill: data_cleaning_skill]
    ↓ 清洗后数据 + 清洗日志
[Skill: llm_extraction_skill]
    ↓ 结构化信息 + 提取日志
[SubAgent: OntologyBuilderAgent]
    ↓ OntologyDocument + 构建日志
[Skill: version_manager_skill]
    ↓ 版本记录 + 版本日志
[Skill: graph_builder_skill]
    ↓ 图谱数据 + 图谱日志
[SubAgent: AuditLoggerAgent]
    ↓ 审计日志存储
```

### Data Models

#### IngestRecord (增强)
```typescript
interface IngestRecord {
  id: string;
  source: string;
  source_details: Record<string, any>;
  status: string;
  record_count: number;
  processed_count: number;
  failed_count: number;
  start_time: string;
  end_time?: string;
  version_id?: string;  // 关联的本体版本
  logs: ProcessLog[];   // 处理日志
  original_content?: string;
}

interface ProcessLog {
  timestamp: string;
  stage: 'collection' | 'cleaning' | 'llm' | 'ontology' | 'version' | 'graph';
  operation: string;
  details: Record<string, any>;
  status: 'pending' | 'processing' | 'completed' | 'failed';
}
```

#### OntologyVersion (增强)
```typescript
interface OntologyVersion {
  id: string;
  version_id: string;
  scenario_id: string;
  created_at: string;
  status: 'building' | 'completed' | 'failed';
  document_id: string;
  entity_count: number;
  relation_count: number;
  ingest_id: string;  // 关联的摄入记录
  logs: ProcessLog[];  // 该版本的完整处理日志
}
```

### OpenHarness Agent/Skill Mapping

| 阶段 | 类型 | 名称 | 职责 |
|------|------|------|------|
| 数据摄入 | Skill | data_ingestion_skill | 多类型数据摄入 |
| 数据清洗 | Skill | data_cleaning_skill | 数据标准化 |
| LLM归纳 | Skill | llm_extraction_skill | 实体/关系/事件提取 |
| 本体构建 | SubAgent | OntologyBuilderAgent | 协调构建流程 |
| 版本管理 | Skill | version_manager_skill | 版本CRUD |
| 图谱生成 | Skill | graph_builder_skill | Neo4j操作 |
| 意图路由 | SubAgent | IntentRouterAgent | QA意图分析 |
| 审计日志 | SubAgent | AuditLoggerAgent | 日志记录审计 |

## Performance Requirements

- 处理日志实时更新：延迟 < 1秒
- 阶段切换响应时间 < 2秒
- 审计日志查询响应 < 3秒
- 支持至少 5 个并发构建任务
