# 存储结构系统性重新设计规范

## Why

当前项目的数据存储存在以下问题：
1. **存储职责不清** - SQLite、MongoDB、Neo4j 的使用边界模糊
2. **数据未持久化** - SQLite 数据存储在 `/tmp/`，容器重启丢失
3. **数据不同步** - 各存储之间没有关联关系维护
4. **文档过时** - docs 目录下存在大量过时的设计文档

## What Changes

### 1. 核心设计原则：分层存储

根据数据特点选择最合适的存储介质：

| 数据特点 | 推荐存储 | 理由 |
|---------|---------|------|
| 结构化元数据、需快速查询 | **SQLite** | 索引支持好，查询快 |
| 半结构化文档、嵌套结构 | **MongoDB** | 文档型，灵活存储 |
| 图结构数据、关系查询 | **Neo4j** | 原生图存储 |

### 2. 数据实体存储划分

| 实体 | 存储介质 | 说明 |
|-----|---------|------|
| **Workspace**（工作空间） | SQLite | 工作空间元数据 |
| **Scenario**（场景） | SQLite | 场景配置 |
| **IngestRecord**（摄入记录） | SQLite | 摄入历史主表 |
| **OntologyVersion**（本体版本） | SQLite | 版本元数据（version_number, status, counts） |
| **OntologyDocument**（本体文档） | MongoDB | 完整定义（entities, relations, events, constraints） |
| **GraphStore**（图存储） | Neo4j via Graphiti | 图谱实体实例和关系实例（利用 Graphiti 时态图特性） |
| **AuditLog**（审计日志） | Neo4j via Graphiti | 审计事件记录、关系追溯、时序查询（利用 Graphiti 时态图特性） |

### 3. 关键区分：本体定义 vs 图谱实例

```
本体定义（Ontology Definition）
├── 存储位置：SQLite（元数据）+ MongoDB（完整文档）
├── 内容：实体类型定义、关系类型定义、约束定义、属性schema
└── 用途：模板、Schema、版本管理

图谱实例（Graph Instance）
├── 存储位置：Neo4j
├── 内容：实体实例、关系实例
└── 用途：运行时数据、图查询
```

### 4. 核心关系定义

- **Workspace → Scenario**: 1:N（一个工作空间包含多个场景）
- **Scenario → OntologyVersion**: 1:N（一个场景可发布多个版本）
- **OntologyVersion → IngestRecord**: 1:N（一个版本可由多次摄入生成）
- **OntologyVersion → OntologyDocument**: 1:1（每个版本对应一个完整文档）
- **OntologyVersion → GraphStore**: 1:1（每个版本对应一个图谱快照）

### 5. 存储介质选择原则

| 查询类型 | 推荐存储 | 原因 |
|---------|---------|------|
| 条件过滤/分页/排序 | **SQLite** | 关系型索引优化 |
| 全文检索/嵌套查询 | **MongoDB** | 文档索引强大 |
| 图关系查询/路径分析 | **Neo4j** | 原生图存储 |
| 时序追溯/版本比对 | **Neo4j** | 时序关系强大 |

## Impact

### 受影响的规格
- 本体管理链路重构
- 审计日志系统

### 受影响的代码
- `odap/biz/ontology/storage/` - 存储层重构
- `odap/infra/security/` - 审计日志存储
- `docs/` - 文档清理

## ADDED Requirements

### Requirement: 存储介质职责划分

系统 SHALL 明确划分各存储介质的职责：

| 存储 | 职责 | 数据类型 | 操作方式 |
|-----|------|---------|---------|
| **SQLite** | 工作空间、场景、摄入记录、版本元数据 | 结构化元数据 | 直接 SQL |
| **MongoDB** | 本体文档（完整实体/关系/事件定义） | 半结构化文档 | PyMongo |
| **Neo4j** | 图谱实例、审计日志 | 图数据、时序数据 | **通过 Graphiti** |

#### Scenario: 数据摄入完整流程
- **WHEN** 用户创建摄入记录
- **THEN** 摄入元数据写入 SQLite，本体文档写入 MongoDB，图谱实例写入 Neo4j

### Requirement: 关系完整性维护

系统 SHALL 维护以下关系：
- Workspace ↔ Scenario（1:N）
- Scenario ↔ OntologyVersion（1:N）
- OntologyVersion ↔ IngestRecord（1:N）
- OntologyVersion ↔ OntologyDocument（1:1）
- OntologyVersion ↔ GraphStore（1:1）

### Requirement: 数据持久化路径

系统 SHALL 将所有持久化数据存储在 `/app/data/` 目录下：
- SQLite: `/app/data/ontology.db`
- MongoDB: `ontology` 数据库
- Neo4j: 图谱数据（由 Neo4j 自行管理）

## MODIFIED Requirements

### Requirement: 存储配置

原有配置为分散定义，现改为统一配置：
- SQLite: `/app/data/ontology.db`
- MongoDB: `ontology` 数据库
- Neo4j: 图谱数据

## REMOVED Requirements

### Requirement: 临时存储

**Reason**: `/tmp/` 路径用于临时数据，容器重启会丢失，不适合生产环境
**Migration**: 将所有数据路径迁移到 `/app/data/`

## 设计原则

1. **单一数据源** - 每个实体有且只有一个主存储
2. **读写分离** - 写入主存储，读取可从多个存储优化
3. **关系驱动** - 使用关系型数据库维护实体关系
4. **图优化** - 复杂关系查询使用 Neo4j
5. **Schema 与 Instance 分离** - 本体定义与图谱实例分开存储

## 交付物

1. **存储结构设计文档** - 完整的数据模型、关系定义、存储方案
2. **数据模型图** - ER 图和实体关系说明
3. **实施路径** - 具体的迁移和实现步骤
4. **文档清理报告** - 过时文档清单和处理建议