# 本体管理链路重构 - 实现计划

## Task 1: 菜单结构调整
- **Priority**: P0
- **Depends On**: None
- **Description**: 将工作空间菜单从本体管理区移至系统配置区

### SubTask 1.1: 修改前端菜单配置
- 修改 AppLayout.tsx 中的 menuItems
- 将「工作空间」从 ontology-management 移至 system-config

### SubTask 1.2: 验证菜单结构
- 刷新前端验证菜单显示正确

## Task 2: 数据模型增强
- **Priority**: P0
- **Depends On**: None
- **Description**: 增强摄入记录和版本模型，添加处理日志字段

### SubTask 2.1: 扩展 IngestRecord 模型
- 添加 version_id 字段
- 添加 logs 字段 (ProcessLog[])

### SubTask 2.2: 扩展 OntologyVersion 模型
- 添加 ingest_id 字段
- 添加 logs 字段 (ProcessLog[])

### SubTask 2.3: 定义 ProcessLog 模型
- 定义阶段枚举
- 定义日志结构

## Task 3: 后端处理链路实现
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 实现六个阶段的完整处理链路

### SubTask 3.1: 实现数据摄入阶段
- 修改现有摄入接口，添加日志记录
- 实现摄入后自动触发后续阶段

### SubTask 3.2: 实现数据清洗阶段
- 创建 data_cleaning_skill
- 实现去重、标准化逻辑
- 记录清洗日志

### SubTask 3.3: 实现 LLM 归纳阶段
- 创建 llm_extraction_skill
- 实现实体/关系/事件提取
- 记录提取日志

### SubTask 3.4: 实现本体构建阶段
- 创建 ontology_builder_skill
- 实现 OntologyDocument 生成
- 记录构建日志

### SubTask 3.5: 实现版本管理阶段
- 创建/更新 version_manager_skill
- 自动创建版本记录
- 记录版本日志

### SubTask 3.6: 实现图谱生成阶段
- 创建 graph_builder_skill
- 实现 Neo4j 图谱写入
- 记录图谱日志

### SubTask 3.7: 实现审计日志阶段
- 创建 audit_logger_skill
- 集成 graphiti 审计日志
- 构建审计本体

## Task 4: OpenHarness SubAgent 实现
- **Priority**: P0
- **Depends On**: Task 3
- **Description**: 实现编排层的 SubAgent

### SubTask 4.1: 实现 OntologyBuilderAgent
- 协调各阶段执行顺序
- 管理阶段间数据传递
- 处理异常和回退

### SubTask 4.2: 实现 IntentRouterAgent
- 分析用户查询意图
- 决定是否触发本体构建
- 选择处理流程

### SubTask 4.3: 实现 AuditLoggerAgent
- 聚合各阶段日志
- 生成审计报告
- 提供查询接口

## Task 5: OpenHarness Skill 实现
- **Priority**: P0
- **Depends On**: Task 3
- **Description**: 实现具体执行层的 Skill

### SubTask 5.1: 创建 Skill 配置文件
- 在 openharness/.claude/skills/ 下创建各 Skill

### SubTask 5.2: 实现 data_ingestion_skill
- 适配现有摄入接口
- 添加日志输出

### SubTask 5.3: 实现 data_cleaning_skill
- 实现清洗逻辑
- 定义输入输出规范

### SubTask 5.4: 实现 llm_extraction_skill
- 实现 LLM 调用
- 定义提取规范

### SubTask 5.5: 实现 ontology_builder_skill
- 实现文档生成
- 实现验证逻辑

### SubTask 5.6: 实现 version_manager_skill
- 实现版本 CRUD
- 实现版本切换

### SubTask 5.7: 实现 graph_builder_skill
- 实现 Neo4j 操作
- 实现图谱查询

### SubTask 5.8: 实现 audit_logger_skill
- 实现日志存储
- 实现日志查询

## Task 6: 前端链路可视化实现
- **Priority**: P0
- **Depends On**: Task 4, Task 5
- **Description**: 实现前端完整链路展示

### SubTask 6.1: 重构数据摄入页面
- 移除动画，改为真实处理过程展示
- 添加处理日志展示区域
- 添加阶段切换功能

### SubTask 6.2: 实现摄入历史详情页
- 点击摄入历史显示完整链路
- 显示每阶段处理日志
- 支持切换到对应本体版本

### SubTask 6.3: 实现版本关联展示
- 摄入历史显示关联版本
- 版本页面显示来源摄入
- 实现版本切换功能

### SubTask 6.4: 实现图谱可视化
- 与版本关联
- 支持节点详情查看
- 支持图谱操作

### SubTask 6.5: 实现审计日志页面
- 独立审计功能入口
- 支持按阶段筛选
- 支持日志详情查看

## Task 7: 智能问答路由集成
- **Priority**: P1
- **Depends On**: Task 4, Task 5
- **Description**: 实现问答触发本体构建

### SubTask 7.1: 实现认知引擎识别
- 分析用户查询
- 识别需要更新的信息

### SubTask 7.2: 实现自动路由
- 自动触发本体构建
- 显示处理进度

## Task 8: 菜单结构调整
- **Priority**: P0
- **Depends On**: None
- **Description**: 工作空间移至系统配置区

### SubTask 8.1: 修改导航菜单
- 修改 AppLayout.tsx
- 验证菜单显示

## Task Dependencies

```
Task 1 (菜单调整)
    ↓
Task 2 (数据模型) ──────────────────┐
    ↓                                │
Task 3 (后端链路)                   │
    ↓    ↓                          │
Task 4 (SubAgent)  Task 5 (Skill)   │
    ↓    ↓                          │
    └────┴──────────────────────────┤
         ↓                          │
Task 6 (前端可视化) ◄────────────────┘
    ↓
Task 7 (QA路由集成)
```

## Implementation Order

1. **Task 1** - 菜单调整（立即可见）
2. **Task 2** - 数据模型增强（基础依赖）
3. **Task 3** - 后端链路实现（核心功能）
4. **Task 5** - Skill 实现（执行层）
5. **Task 4** - SubAgent 实现（编排层）
6. **Task 6** - 前端可视化（用户体验）
7. **Task 7** - QA路由集成（高级功能）
