# 架构决策记录 (ADR)

## ADR-001: 智能问答驱动的本体构建架构

**日期**: 2026-04-26
**状态**: 已接受
**决策者**: 开发团队

### 背景

当前系统缺少通过智能问答自动驱动本体构建与更新的能力。用户提出复杂问题时，系统需要自动完成意图分析、本体检索、联网信息获取、本体更新及智能回复的全流程。

### 决策

采用 **QA-Driven Ontology Building** 架构，实现以下核心组件：

1. **QA Intent Analyzer** - 意图分析与路由
2. **Data Ingestion Pipeline** - 多类型数据摄入管道
3. **Ontology Builder** - 本体构建引擎
4. **Graphiti Integration** - 图谱构建集成
5. **Version Manager** - 版本管理系统
6. **Progress Tracker** - 进度跟踪系统
7. **Frontend UI** - 前端可视化界面

### 论证

**优点**:
- 模块化设计，便于维护和扩展
- 支持多种数据格式统一摄入
- 进度可视化，提升用户体验
- 版本管理，支持历史回溯

**缺点**:
- 增加了系统复杂度
- 需要维护多个服务间的协调

### 后果

- 新增 `odap/biz/ontology/services/` 目录包含核心服务
- 新增 `frontend/src/modules/ontology/components/` 目录包含UI组件
- API 路由统一管理

---

## ADR-002: 数据存储策略

**日期**: 2026-04-26
**状态**: 已接受

### 背景

系统需要支持 MongoDB 存储，但需要处理 MongoDB 不可用的情况。

### 决策

采用 **Fallback Strategy**:
- 主要存储: MongoDB
- 备选存储: SQLite (审计日志) / 内存存储 (本体数据)

### 实现

```python
def get_audit_channel() -> AuditChannel:
    try:
        return MongoDBAuditChannel()
    except Exception as e:
        print(f"MongoDB 审计通道初始化失败，使用 SQLite 备选: {e}")
        from .audit_sqlite_channel import SQLiteAuditChannel
        return SQLiteAuditChannel()
```

---

## ADR-003: OntologyDocument 标准格式

**日期**: 2026-04-26
**状态**: 已接受

### 背景

需要统一多类型数据的摄入格式。

### 决策

所有摄入数据必须转换为 `OntologyDocument` 标准格式：

```python
class OntologyDocument:
    doc_id: str                    # 文档唯一标识
    doc_type: str                  # 文档类型
    source: DataSource             # 数据来源
    meta: DocumentMeta            # 元数据
    entities: List[OntologyEntity]    # 实体列表
    relations: List[OntologyRelation]  # 关系列表
    events: List[OntologyEvent]       # 事件列表
```

---

## ADR-004: API 版本控制

**日期**: 2026-04-26
**状态**: 已接受

### 背景

需要确保 API 升级的兼容性。

### 决策

- 当前版本: V2
- 版本控制: URL路径前缀 (`/api/v2/`)
- 废弃策略: 旧版本标记为 deprecated，提供迁移指南

---

## ADR-005: 前端可视化架构

**日期**: 2026-04-26
**状态**: 已接受

### 背景

需要展示本体构建全链路过程。

### 决策

**三栏式布局**:
- 左侧 (25%): 原始数据展示
- 中间 (40%): 转化过程展示
- 右侧 (35%): 本体定义展示

**技术选型**:
- React + TypeScript
- Ant Design 组件库
- @antv/g6 图可视化
- WebSocket 进度更新