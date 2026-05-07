# 存储结构重新设计 - 任务列表

## Task 1: 审查现有架构文档
- **Priority**: P0
- **Depends On**: None
- **Description**: 审查 docs 目录下的架构文档，设计文档和 ADR

### SubTask 1.1: 审查核心架构文档
- 审查 ARCHITECTURE.md
- 审查 ARCHITECTURE_REVIEW_20260423.md
- 审查 ADR-048_本体管理引擎架构决策.md

### SubTask 1.2: 审查存储相关 ADR
- 审查 ADR-002_graphiti_作为双时态知识图谱.md
- 审查 ADR-023_多工作空间隔离架构.md
- 审查 ADR-042_audit_log_storage_query.md

### SubTask 1.3: 审查现有数据模型
- 检查 odap/biz/ontology/models/ 下的模型定义
- 检查 odap/infra/security/ 下的审计模型

## Task 2: 设计数据模型
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 设计完整的数据模型和关系

### SubTask 2.1: 定义 Workspace 模型
- id, name, description, created_at, updated_at, config

### SubTask 2.2: 定义 Scenario 模型
- id, workspace_id, name, description, current_version_id, created_at, updated_at

### SubTask 2.3: 定义 IngestRecord 模型
- id, scenario_id, version_id, source, status, original_content, extracted_data, build_status, created_at, updated_at

### SubTask 2.4: 定义 OntologyVersion 模型
- id, scenario_id, version_number, parent_version_id, status, entity_count, relation_count, created_at, created_by

### SubTask 2.5: 定义 OntologyDocument 模型（MongoDB）
- document_id, version_id, entities, relations, events, metadata

### SubTask 2.6: 定义关系映射
- Workspace → Scenario (1:N via workspace_id)
- Scenario → OntologyVersion (1:N via scenario_id)
- OntologyVersion → IngestRecord (1:N via version_id)

## Task 3: 设计存储方案
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 确定存储介质选择和配置

### SubTask 3.1: SQLite 存储方案
- 工作空间表、场景表、摄入记录表、版本表
- 索引策略：主键索引、foreign key 索引、created_at 索引
- 路径：/app/data/ontology.db

### SubTask 3.2: MongoDB 存储方案
- ontology_documents 集合（完整本体文档）
- 索引策略：document_id, version_id, created_at
- 数据库：ontology

### SubTask 3.3: Neo4j 存储方案
- Entity 节点（实体）
- Relation 边（关系）
- AuditEvent 节点（审计日志）
- 索引策略：id 属性索引

### SubTask 3.4: 存储接口设计
- 统一存储接口抽象
- 工厂模式创建存储实例

## Task 4: 编写存储结构设计文档
- **Priority**: P0
- **Depends On**: Task 2, Task 3
- **Description**: 编写完整的设计文档

### SubTask 4.1: 编写数据模型图
- ER 图
- 实体关系说明

### SubTask 4.2: 编写存储方案对比
- 各存储介质优缺点对比
- 选择依据

### SubTask 4.3: 编写数据迁移策略
- 从现有存储迁移到新结构
- 数据验证和完整性检查

### SubTask 4.4: 编写实施路径
- 分阶段实施计划
- 回滚策略

## Task 5: 清理过时文档
- **Priority**: P1
- **Depends On**: Task 4
- **Description**: 清理 docs 目录下的过时文档

### SubTask 5.1: 识别过时文档
- 识别与新设计冲突的文档
- 识别重复的文档
- 识别已废弃的 ADR

### SubTask 5.2: 整理文档结构
- 移动到 archive 目录
- 更新文档索引
- 创建新文档的引用关系

## Task 6: 实现存储层代码
- **Priority**: P0
- **Depends On**: Task 4
- **Description**: 实现新的存储层代码

### SubTask 6.1: 实现 SQLite 存储
- 创建 /app/data/ 目录（如果不存在）
- 实现 WorkspaceStorage, ScenarioStorage
- 实现 IngestRecordStorage, OntologyVersionStorage

### SubTask 6.2: 实现 MongoDB 存储
- 实现 OntologyDocumentStorage
- 实现版本文档的 CRUD

### SubTask 6.3: 实现 Neo4j 存储
- 实现 GraphStorage（实体和关系）
- 实现审计日志存储

### SubTask 6.4: 实现存储工厂
- 根据配置创建合适的存储实例
- 处理连接失败回退

## Task 7: 验证和测试
- **Priority**: P0
- **Depends On**: Task 6
- **Description**: 验证新存储架构

### SubTask 7.1: 单元测试
- 测试各存储的 CRUD 操作
- 测试关系维护

### SubTask 7.2: 集成测试
- 测试完整的数据流程
- 测试数据持久化

### SubTask 7.3: 性能测试
- 测试查询性能
- 验证索引有效性

## Task Dependencies

```
Task 1 (审查文档)
    ↓
Task 2 (设计数据模型)
    ↓
Task 3 (设计存储方案) ───┐
    ↓                    │
Task 4 (编写设计文档) ◄──┘
    ↓
Task 5 (清理文档)
    ↓
Task 6 (实现存储层)
    ↓
Task 7 (验证测试)
```

## Implementation Order

1. **Task 1** - 审查文档（基础）
2. **Task 2** - 设计数据模型（核心）
3. **Task 3** - 设计存储方案（核心）
4. **Task 4** - 编写设计文档（交付物）
5. **Task 5** - 清理文档（可选）
6. **Task 6** - 实现存储层（实施）
7. **Task 7** - 验证测试（质量保障）