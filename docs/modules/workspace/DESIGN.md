# 工作空间管理模块 (Workspace Manager) - 设计文档

> **模块 ID**: M-04 | **优先级**: P0 | **相关 ADR**: ADR-023, ADR-041
> **版本**: 2.0.0 | **日期**: 2026-04-19 | **架构层**: L1 基础设施层

---

## 1. 模块概述

### 1.1 模块定位

工作空间管理模块是 ODAP 平台的**多场景隔离基石**，实现工作空间的创建/删除/切换，确保不同业务场景间的本体、Skill、策略、数据完全隔离。通过工作空间机制，平台从"战争分析专属系统"演进为"通用本体驱动平台"。

### 1.2 核心价值

| 维度 | 价值 | 说明 |
|------|------|------|
| **场景隔离** | 数据级隔离 | 每个工作空间独立的本体、图谱、Skill 配置、策略 |
| **快速场景化** | 一键实例化 | 新场景只需创建工作空间，自动初始化完整运行环境 |
| **场景复用** | 导入/导出 | 完整场景打包，支持跨环境迁移 |
| **配置隔离** | 独立配置 | 每个工作空间有独立的 OPA 策略集和 Skill 注册表 |

### 1.3 架构位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ L6  用户交互层 (Web SPA)                                                     │
│     工作空间切换器 / 管理面板                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ L5  API 网关                                                                 │
│     /api/workspaces/*  路由                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ L4  应用服务层                                                                │
│     WorkspaceService (业务逻辑)                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ ★ L1  基础设施层 ★                                                            │
│     WorkspaceManager (核心)                                                   │
│         ├── WorkspaceStore (持久化)                                            │
│         ├── WorkspaceIsolator (资源隔离)                                       │
│         └── WorkspaceExporter (导入/导出)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心概念模型

### 2.1 工作空间模型

```python
class Workspace:
    """工作空间 - 场景隔离的基本单元"""
    id: str                    # 唯一标识 (UUID)
    name: str                  # 空间名称
    description: str           # 空间描述
    domain: str                # 领域标识 (e.g. "military", "finance", "healthcare")
    status: WorkspaceStatus    # 状态: ACTIVE / ARCHIVED / DELETED
    config: WorkspaceConfig    # 空间级配置
    resource_limits: ResourceLimits  # 资源限制
    created_at: datetime       # 创建时间
    updated_at: datetime       # 更新时间
    created_by: str            # 创建者
    tags: list[str]            # 标签

class WorkspaceStatus(str, Enum):
    ACTIVE = "active"          # 活跃
    ARCHIVED = "archived"      # 已归档
    DELETED = "deleted"        # 已删除（软删除）

class WorkspaceConfig:
    """工作空间级配置"""
    ontology_version: str      # 当前使用的本体版本
    skill_set: list[str]       # 已启用的 Skill ID 列表
    opa_bundle: str            # OPA 策略 Bundle 标识
    llm_provider: str          # LLM 提供者配置
    embedding_model: str       # Embedding 模型
    custom_settings: dict      # 自定义配置（JSON）

class ResourceLimits:
    """资源限制"""
    max_nodes: int             # 最大节点数 (default: 100000)
    max_edges: int             # 最大边数 (default: 500000)
    max_skills: int            # 最大 Skill 数 (default: 50)
    max_agents: int            # 最大 Agent 数 (default: 10)
    max_concurrent_sims: int   # 最大并发推演数 (default: 5)
    storage_mb: int            # 存储限额 MB (default: 5120)
```

### 2.2 工作空间上下文

```python
class WorkspaceContext:
    """
    工作空间上下文 - 运行时环境绑定

    每个请求/Agent 操作都关联到一个 WorkspaceContext，
    所有基础设施层组件通过 Context 确定资源边界。
    """
    workspace_id: str
    workspace: Workspace
    neo4j_database: str        # Neo4j 数据库名 (ws_{id前8位})
    opa_bundle_path: str       # OPA Bundle 路径
    skill_registry_scope: str  # Skill 注册表作用域

    @classmethod
    async def create(cls, workspace_id: str) -> "WorkspaceContext":
        """创建上下文，加载工作空间配置"""
        ...

    async def get_graphiti_client(self) -> "GraphitiClient":
        """获取当前工作空间的 Graphiti 客户端"""
        ...

    async def get_opa_client(self) -> "OPAClient":
        """获取当前工作空间的 OPA 客户端"""
        ...
```

---

## 3. 核心组件设计

### 3.1 WorkspaceManager

```python
class WorkspaceManager:
    """
    工作空间管理器 - 核心入口

    职责：
    - 工作空间 CRUD
    - 上下文管理（当前工作空间）
    - 资源隔离初始化
    - 生命周期管理
    """

    def __init__(self, store: WorkspaceStore, isolator: WorkspaceIsolator):
        self._store = store
        self._isolator = isolator
        self._current_context: WorkspaceContext | None = None

    async def create_workspace(
        self,
        name: str,
        domain: str,
        description: str = "",
        config: WorkspaceConfig | None = None,
        template_id: str | None = None,
    ) -> Workspace:
        """
        创建工作空间

        流程：
        1. 验证名称唯一性
        2. 创建 Workspace 记录
        3. 初始化隔离资源（Neo4j DB、OPA Bundle、Skill 注册表）
        4. 如有模板，导入模板数据
        5. 记录审计日志
        """
        ...

    async def delete_workspace(self, workspace_id: str, soft: bool = True) -> bool:
        """删除工作空间（默认软删除）"""
        ...

    async def switch_workspace(self, workspace_id: str) -> WorkspaceContext:
        """
        切换工作空间

        流程：
        1. 验证目标空间存在且为 ACTIVE
        2. 验证当前用户有权访问
        3. 清理当前上下文
        4. 加载新上下文
        5. 通知所有组件（Graphiti/OPA/Skill）上下文切换
        """
        ...

    async def get_current_context(self) -> WorkspaceContext:
        """获取当前工作空间上下文"""
        ...

    async def list_workspaces(
        self,
        domain: str | None = None,
        status: WorkspaceStatus | None = None,
    ) -> list[Workspace]:
        """列出工作空间"""
        ...
```

### 3.2 WorkspaceIsolator（资源隔离器）

```python
class WorkspaceIsolator:
    """
    工作空间资源隔离器

    实现策略（ADR-041）：Neo4j 多数据库隔离
    - 每个工作空间对应一个独立的 Neo4j 数据库
    - OPA Bundle 按工作空间路径隔离
    - Skill 注册表按工作空间命名空间隔离
    """

    async def initialize_resources(self, workspace: Workspace) -> None:
        """
        初始化工作空间资源

        1. 创建 Neo4j 数据库: CREATE DATABASE ws_{id前8位}
        2. 初始化 OPA Bundle 目录
        3. 初始化 Skill 注册表命名空间
        4. 初始化存储目录
        """
        ...

    async def teardown_resources(self, workspace: Workspace) -> None:
        """清理工作空间资源（删除/归档时调用）"""
        ...

    async def verify_isolation(self, workspace_id: str) -> IsolationReport:
        """
        验证隔离完整性

        检查项：
        - Neo4j 数据库是否独立
        - OPA Bundle 是否隔离
        - 文件存储是否隔离
        - 是否存在跨空间数据泄露
        """
        ...

    async def get_resource_usage(self, workspace_id: str) -> ResourceUsage:
        """获取工作空间资源使用情况"""
        ...
```

### 3.3 WorkspaceExporter（导入/导出器）

```python
class WorkspaceExporter:
    """
    工作空间导入/导出器

    导出格式：ODAP Workspace Package (.owp)
    结构：
    workspace.owp/
    ├── manifest.json          # 元信息
    ├── ontology/
    │   ├── schema.json        # 本体定义
    │   └── versions/          # 版本历史
    ├── skills/
    │   ├── registry.json      # Skill 注册信息
    │   └── configs/           # Skill 配置
    ├── policies/
    │   └── bundle.tar.gz      # OPA Bundle
    ├── data/
    │   ├── nodes.csv          # 节点数据
    │   └── edges.csv          # 边数据
    └── config.json            # 工作空间配置
    """

    async def export_workspace(
        self, workspace_id: str, include_data: bool = True
    ) -> str:
        """
        导出工作空间

        参数：
        - include_data: 是否包含实例数据（节点/边）

        返回：导出文件路径
        """
        ...

    async def import_workspace(
        self,
        package_path: str,
        target_name: str | None = None,
        conflict_policy: ConflictPolicy = "skip",
    ) -> Workspace:
        """
        导入工作空间

        参数：
        - package_path: .owp 包路径
        - target_name: 目标工作空间名称（默认使用包内名称）
        - conflict_policy: 冲突处理策略（skip/overwrite/rename）

        返回：新创建的 Workspace
        """
        ...

    async def create_template(
        self, workspace_id: str, template_name: str, description: str
    ) -> str:
        """从现有工作空间创建模板（不含实例数据）"""
        ...
```

---

## 4. 接口设计

### 4.1 REST API

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/workspaces | 列出工作空间 | workspace:list |
| POST | /api/workspaces | 创建工作空间 | workspace:create |
| GET | /api/workspaces/{id} | 获取工作空间详情 | workspace:read |
| PUT | /api/workspaces/{id} | 更新工作空间 | workspace:update |
| DELETE | /api/workspaces/{id} | 删除工作空间 | workspace:delete |
| POST | /api/workspaces/{id}/switch | 切换工作空间 | workspace:switch |
| POST | /api/workspaces/{id}/archive | 归档工作空间 | workspace:archive |
| GET | /api/workspaces/{id}/usage | 资源使用情况 | workspace:read |
| POST | /api/workspaces/{id}/export | 导出工作空间 | workspace:export |
| POST | /api/workspaces/import | 导入工作空间 | workspace:import |
| GET | /api/workspaces/templates | 列出模板 | workspace:template:list |
| POST | /api/workspaces/templates | 创建模板 | workspace:template:create |

### 4.2 内部接口（供其他模块调用）

```python
class IWorkspaceProvider(Protocol):
    """工作空间提供者接口 - 供基础设施层组件使用"""

    async def get_context(self) -> WorkspaceContext:
        """获取当前工作空间上下文"""
        ...

    async def get_neo4j_config(self, workspace_id: str) -> Neo4jConfig:
        """获取指定工作空间的 Neo4j 配置"""
        ...

    async def get_opa_config(self, workspace_id: str) -> OPAConfig:
        """获取指定工作空间的 OPA 配置"""
        ...

    async def validate_access(
        self, workspace_id: str, user_id: str, action: str
    ) -> bool:
        """验证用户对工作空间的访问权限"""
        ...
```

---

## 5. 与其他模块的交互

### 5.1 依赖关系

| 依赖模块 | 交互方式 | 说明 |
|----------|---------|------|
| M-01 Graphiti | 调用 | 工作空间切换时切换 Neo4j 数据库连接 |
| M-02 OPA | 调用 | 工作空间创建时初始化 OPA Bundle；切换时加载对应 Bundle |
| M-03 本体管理 | 调用 | 工作空间绑定本体版本，切换时加载对应本体 |
| M-08 Skill | 调用 | 工作空间绑定 Skill 注册表，切换时加载对应 Skill 集 |
| M-07 审计日志 | 被调用 | 所有工作空间操作记录审计日志 |

### 5.2 事件流

```
创建工作空间 →
    WorkspaceManager.create_workspace()
    → WorkspaceIsolator.initialize_resources()
        → Neo4j: CREATE DATABASE
        → OPA: 初始化 Bundle
        → Skill: 初始化注册表
    → AuditLogger.log("workspace.created")

切换工作空间 →
    WorkspaceManager.switch_workspace()
    → WorkspaceContext 更新
    → 通知所有组件上下文切换
        → GraphitiClient.reconnect(new_db)
        → OPAClient.load_bundle(new_path)
        → SkillRegistry.scope(new_scope)
    → AuditLogger.log("workspace.switched")
```

---

## 6. 数据存储设计

### 6.1 工作空间元数据（SQLite / PostgreSQL）

```sql
CREATE TABLE workspaces (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    domain      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    config      TEXT NOT NULL,  -- JSON
    resource_limits TEXT NOT NULL,  -- JSON
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by  TEXT NOT NULL,
    tags        TEXT DEFAULT '[]'  -- JSON array
);

CREATE TABLE workspace_templates (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    domain      TEXT NOT NULL,
    package_path TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by  TEXT NOT NULL
);
```

### 6.2 图谱数据（Neo4j 多数据库）

```
默认数据库: neo4j (系统管理)
工作空间数据库: ws_{workspace_id_prefix}
    - 每个工作空间一个独立数据库
    - 包含该空间的所有节点/边/Episode
```

### 6.3 策略数据（文件系统隔离）

```
/data/opa/
├── default/              # 默认策略 Bundle
│   └── bundle.tar.gz
├── ws_abc12345/          # 工作空间 abc12345 的策略
│   └── bundle.tar.gz
└── ws_def67890/          # 工作空间 def67890 的策略
    └── bundle.tar.gz
```

---

## 7. 非功能设计

### 7.1 性能

| 指标 | 目标 | 实现方式 |
|------|------|---------|
| 工作空间创建 | < 5s | 异步初始化资源，创建即返回 |
| 工作空间切换 | < 2s | 上下文缓存，预加载配置 |
| 导出（含数据） | < 30s (10K节点) | 流式导出，增量打包 |
| 导入 | < 60s (10K节点) | 批量写入，事务提交 |

### 7.2 安全

| 措施 | 说明 |
|------|------|
| 数据库级隔离 | Neo4j 多数据库，物理隔离 |
| 访问控制 | OPA ABAC 策略，workspace:{action} 权限 |
| 软删除 | 默认软删除，30 天后自动清理 |
| 操作审计 | 所有工作空间操作记录审计日志 |

### 7.3 可靠性

| 措施 | 说明 |
|------|------|
| 创建失败回滚 | 资源初始化失败时回滚已创建资源 |
| 切换失败恢复 | 切换失败时恢复原上下文 |
| 定期一致性检查 | 定时验证隔离完整性 |

---

## 8. 实现路径

### Phase 0 (当前)

- [x] WorkspaceManager 基础 CRUD
- [x] WorkspaceContext 概念模型
- [ ] Neo4j 多数据库隔离
- [ ] 导入/导出功能

### Phase 1

- [ ] 工作空间模板系统
- [ ] 资源配额与限制
- [ ] 隔离验证与一致性检查
- [ ] 工作空间管理 UI

### Phase 2

- [ ] 跨环境迁移
- [ ] 工作空间快照与恢复
- [ ] 共享工作空间（只读共享）
- [ ] 工作空间性能监控
