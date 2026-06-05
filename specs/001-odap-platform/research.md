# Phase 0 研究文档: ODAP 本体驱动分析决策平台

**日期**: 2026-05-31 | **分支**: `001-odap-platform` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## 课题1: OpenHarness 进程内集成最佳实践

### 1.1 OpenHarness Python SDK 集成方式

**现状分析**:

代码库中已有两层 OpenHarness 集成实现：

1. **`odap/infra/openharness/tool_adapter.py`** — v1/v2 兼容适配层
   - `OpenHarnessToolAdapter`: 将 BaseSkill 适配为 OpenHarness `BaseTool`
   - `DomainHarness`: 封装 OpenHarness v1 `core.harness.Harness` 和 v2 `engine.query_engine.QueryEngine`
   - 自动检测 OpenHarness 版本（v1 → v2 → fallback），使用 `try/except ImportError` 降级

2. **`odap/infra/openharness/v2_adapter.py`** — v2 深度适配层
   - `GraphitiToolAdapter`: 继承 v2 `BaseTool`，实现 `execute(arguments, context) -> ToolResult`
   - `GraphitiAgentLoop`: 完整 Agent Loop（接收输入 → LLM 决策 → 工具调用 → 观察结果 → 循环）
   - `OpenHarnessIntegration`: 单例管理器，统一初始化 LLM Client + Agent Loop

3. **`odap/biz/integration/openharness_agent/`** — 业务层 API 路由
   - 通过 `v2_adapter` 的 `run_agent()` 暴露 REST API

**OpenHarness v2 核心接口**（来自 `openharness/src/openharness/`）：

| 模块 | 核心类 | 职责 |
|------|--------|------|
| `tools/base.py` | `BaseTool`, `ToolRegistry`, `ToolResult` | 工具注册与执行 |
| `engine/query_engine.py` | `QueryEngine` | 对话引擎，管理 Agent Loop |
| `hooks/types.py` | `HookResult`, `AggregatedHookResult` | 钩子结果类型 |
| `hooks/executor.py` | `HookExecutor` | 钩子执行器 |
| `hooks/hot_reload.py` | — | 钩子热重载 |
| `permissions/checker.py` | `PermissionChecker` | 权限检查 |
| `memory/manager.py` | `MemoryManager` | 记忆管理 |
| `mcp/client.py` | — | MCP 协议客户端 |
| `skills/registry.py` | — | Skill 注册表 |
| `swarm/in_process.py` | — | 进程内 Swarm |
| `sandbox/session.py` | — | 沙箱会话 |

### 1.2 进程内集成的线程模型和资源隔离

**Decision**: 采用 FastAPI lifespan 初始化 + 单例模式 + asyncio 事件循环

**Rationale**:
- OpenHarness v2 的 `QueryEngine` 是异步设计，与 FastAPI 的 asyncio 事件循环天然兼容
- 现有 `OpenHarnessIntegration` 已实现单例模式（`_instance`），确保全局唯一
- 进程内集成无 IPC 开销，Agent Loop 的 LLM 调用和工具执行在同一进程内完成
- 资源隔离通过 `workspace_id` 参数传递实现，而非进程级隔离

**Implementation Notes**:
- FastAPI `lifespan` 中调用 `await initialize_openharness(user_role, provider_config)`
- 每个 Agent Loop 实例绑定 `user_role` + `workspace_id`，通过上下文传递隔离
- OpenHarness 的 `PermissionChecker` 与 OPA 集成，实现权限隔离
- 沙箱推演使用 OpenHarness `sandbox/session.py` 的进程级隔离

### 1.3 独立性保证

**Decision**: 适配层隔离 + 封装隔离 + 版本锁定 + 不 fork 核心代码

**Rationale**:
- 现有 `odap/infra/openharness/` 已实现适配层模式：`tool_adapter.py` 和 `v2_adapter.py` 封装了所有 OpenHarness 调用
- 业务代码（如 `swarm_orchestrator.py`）通过 `DomainHarness` 间接使用 OpenHarness，不直接 `import openharness`
- OpenHarness 作为 Git Submodule 独立维护，通过 `pip install -e ./openharness` 安装
- `requirements.txt` 中锁定版本

**Alternatives Considered**:
1. **直接调用 OpenHarness API** — 简单但强耦合，升级时需修改所有调用点，被否决
2. **微服务隔离** — 独立进程/容器运行 OpenHarness，通过 HTTP/gRPC 通信 — 引入 IPC 开销和运维复杂度，被否决
3. **Fork OpenHarness** — 完全控制但失去上游更新能力，被否决

**Implementation Notes**:
- 适配层提供具体封装类，业务代码通过适配器调用 OpenHarness，不直接引用；适配器公共 API 保持稳定，OpenHarness API 变更时仅需更新适配器
- 新增适配器文件：`swarm_adapter.py`, `skill_adapter.py`, `memory_adapter.py`, `hook_adapter.py`
- 每个适配器文件对应 plan.md 中 `odap/infra/openharness/` 下的一个模块
- 当 OpenHarness API 变更时，仅需更新适配层，业务代码无感知

---

## 课题2: Palantir AIP 本体模型结构

### 2.1 Palantir AIP 四层结构详解

**Palantir AIP 本体模型**核心概念：

| 层次 | Palantir 概念 | 对应 ODAP 概念 | 说明 |
|------|---------------|----------------|------|
| **Object Type** | 对象类型 | EntityType | 实体的类型定义，包含属性、主键、约束 |
| **Property** | 属性 | Property | 对象类型的字段定义，含数据类型、分类级别 |
| **Link** | 链接/关系 | Relation/LinkDefinition | 对象类型之间的关联，含基数约束 |
| **Action** | 动作 | ActionType | 对对象可执行的操作，含参数、权限、回写配置 |

Palantir AIP 额外概念（ODAP 可借鉴但可简化）：
- **Rule**: 业务规则，约束对象行为（对应 ODAP Constraint）
- **Function**: 计算函数，派生属性（对应 ODAP servitization 中的 FunctionType）
- **Constraint**: 数据约束，属性级验证规则

### 2.2 与当前 OMS 实现的差异分析

**现有 OMS 实现**（`odap/biz/core/ontology/oms/`）：

| 维度 | 现有 OMS | Palantir AIP 参考目标 | 差距 |
|------|----------|----------------------|------|
| **ObjectType** | `ObjectTypeDefinition` 含 type_id, name, properties[], links[], actions[] | 需增加 primary_key, constraints[], classification_level | 缺少主键定义和约束 |
| **Property** | `PropertyDefinition` 含 name, property_type, required, category | 需增加 classification_level, default_value, validation_rule | 缺少分类级别和验证规则 |
| **Link** | `LinkDefinition` 含 name, source_type, target_type, cardinality | 基本对齐 | 需增加 link_type（关联/组合/依赖） |
| **Action** | `ActionTypeDefinition` 含 parameters[], opa_policy, required_roles, writeback_config | 基本对齐 | 需增加 trigger_type（手动/自动/事件） |
| **存储** | SQLite `object_types` + `action_types` 两张表 | 需增加 `constraints` 表 | 约束存储在 properties JSON 中 |
| **种子数据** | 从 `domain.py` 的 `ENTITY_TYPES` 生成 | 需迁移到 OntologyDocument 格式 | 格式不统一 |

**关键差距**：
1. **缺少 Constraint 模型** — 现有 OMS 没有独立的约束定义，验证逻辑散落在各处
2. **缺少 primary_key 定义** — 实例唯一性判定依赖隐式规则
3. **缺少 classification_level** — 数据分类标记（FR-027）需要属性级分类
4. **OntologyDocument 格式不统一** — 现有 `schema/document.py` 与 OMS 存储格式不一致

### 2.3 OntologyDocument JSON 格式设计

**Decision**: 基于 Palantir AIP 结构定义 OntologyDocument，作为所有本体数据交换的统一原子格式

**Rationale**:
- 现有 `odap/biz/core/ontology/schema/document.py` 已实现 ADR-032 定义的 OntologyDocument 格式
- 需要扩展以包含 Palantir 四层结构（ObjectType → Property → Link → Action）+ Rule/Constraint
- 所有数据摄入、导入导出、模块间数据交换必须使用此格式

**OntologyDocument JSON Schema**:
```json
{
  "id": "uuid",
  "name": "本体名称",
  "version": "1.0.0",
  "object_types": [
    {
      "id": "uuid",
      "name": "实体类型名",
      "display_name": "显示名",
      "properties": [
        {
          "name": "prop1",
          "data_type": "string",
          "required": true,
          "classification_level": "U",
          "default_value": null,
          "constraints": []
        }
      ],
      "primary_key": ["prop1"],
      "links": [
        {
          "name": "link1",
          "target_type": "OtherType",
          "cardinality": "1:N",
          "link_type": "association"
        }
      ],
      "actions": ["action_id_1"],
      "constraints": [
        {
          "name": "naming_convention",
          "constraint_type": "pattern",
          "expression": "^[A-Z][a-zA-Z0-9]*$",
          "error_message": "名称必须PascalCase"
        }
      ]
    }
  ],
  "action_types": [
    {
      "id": "action_id_1",
      "name": "deploy",
      "target_object_type": "MilitaryUnit",
      "parameters": [...],
      "required_roles": ["commander"],
      "confirmation_required": true
    }
  ],
  "metadata": {
    "created_at": "2026-05-31T00:00:00Z",
    "created_by": "admin",
    "source": "manual|import|palantir|owl"
  }
}
```

### 2.4 在 SQLite+Neo4j 上实现 Palantir 语义层

**Decision**: SQLite 存储类型定义（Schema），Neo4j 存储实例数据（Runtime），通过 OMS Service 统一访问

**Rationale**:
- SQLite 适合存储结构化的类型定义（ObjectType/Property/Link/Action），查询模式固定
- Neo4j 适合存储实例数据和关系，支持图遍历和时序查询
- OMS Service 作为统一入口，协调 SQLite（类型定义）和 Neo4j（实例数据）

**Implementation Notes**:
- SQLite 表结构扩展：`object_types` 增加 `primary_key TEXT`、`constraints TEXT` 列
- Neo4j 节点增加 `classification_level` 属性，支持数据分类查询
- `OMSService` 增加 `validate_instance(type_id, properties)` 方法，基于 Constraint 校验
- `to_owl()` / `to_rdf()` 导出方法实现 OntologyDocument → OWL/RDF 转换；`from_palantir()` 仅在需要导入 Palantir 数据时实现

---

## 课题3: Graphiti 双时态能力利用

### 3.1 valid_time 和 transaction_time 的语义

**双时态概念**：

| 时间维度 | 含义 | 示例 | 来源 |
|----------|------|------|------|
| **valid_time** | 业务有效时间 — "这个事实在现实世界中何时为真" | "2026-05-01 本体定义为V2版本" | 用户指定 |
| **transaction_time** | 系统记录时间 — "这个事实何时被记录到系统中" | "2026-05-31 14:30:00 系统写入" | 系统自动 |

**现有实现**（`odap/infra/graph/graph_service.py`）：
- `query_temporal(valid_time, transaction_time, entity_type)` — 已实现双时态查询 API
- `get_entity_history(entity_id)` — 已实现实体历史查询
- Graphiti 的 `add_episode()` 使用 `reference_time` 参数对应 valid_time
- `retrieve_episodes()` 支持 `valid_time` 和 `transaction_time` 参数

**关键发现**：
- 现有 `query_temporal()` 的实现将 `valid_time` 和 `transaction_time` 都映射到 `episode.created_at`，未真正区分两个时间维度
- 需要在 `add_episode()` 时分别传入 `valid_time`（业务时间）和自动记录 `transaction_time`（系统时间）

### 3.2 本体版本管理：基于双时态实现版本追踪/对比/回滚

**Decision**: 利用 Graphiti Episode 机制存储版本快照，valid_time 标记业务生效时间，transaction_time 标记系统记录时间

**Rationale**:
- Graphiti 的 Episode 天然支持时序数据，每次本体变更创建一个 Episode
- Episode 的 `reference_time` 对应 valid_time，`created_at` 对应 transaction_time
- 版本对比通过查询两个时间点的 Episode 快照实现

**Implementation Notes**:
- `create_version(ontology_id, change_desc, valid_time)`:
  - 创建 Episode，`reference_time=valid_time`，`name=f"version_{ontology_id}_{version_number}"`
  - Episode body 包含完整 OntologyDocument JSON
  - 同时写入 SQLite 版本元数据（version_number, changelog, status）
- `query_at_time(ontology_id, timestamp)`:
  - 调用 `retrieve_episodes(reference_time=timestamp)` 获取该时间点的 Episode
  - 解析 Episode body 还原 OntologyDocument
- `compare_versions(ontology_id, v1_id, v2_id)`:
  - 分别获取两个版本的 OntologyDocument
  - 逐层对比（object_types/properties/links/actions），生成差异报告
- `rollback_version(ontology_id, target_version_id)`:
  - 创建新 Episode 记录回滚操作，valid_time 设为回滚生效时间
  - 不删除历史 Episode，保持完整审计链

### 3.3 问答时序推理

**Decision**: 实现 `temporal_reasoner.py`，封装 Graphiti 双时态查询，支持三类时序问答

**Rationale**:
- 现有 `odap/infra/query/service.py` 已有 `_execute_temporal()` 方法，但功能简单
- 需要增强为支持自然语言时序问题的推理器

**三类时序问答**：

| 问题类型 | 示例 | 查询方式 |
|----------|------|----------|
| "当时发生了什么" | "5月1日Unit_A的状态是什么" | `query_temporal(valid_time="2026-05-01")` |
| "什么时候变成这样的" | "Unit_A什么时候被部署的" | `get_entity_history("Unit_A")` + 按 transaction_time 排序 |
| "某时间点的综合状态" | "5月1日整个战场的态势" | `query_temporal(valid_time="2026-05-01")` + 聚合 |

### 3.4 推演历史对比

**Decision**: 推演结果附带双时态存储，valid_time 为推演场景时间，transaction_time 为推演执行时间

**Rationale**:
- 不同时间点的推演结果可以基于 valid_time 对比
- 推演参数变化可以基于 transaction_time 追踪
- 决策推荐引擎可基于历史推演结果进行 RAG 增强推理

**Implementation Notes**:
- 推演结果写入 Graphiti Episode，`reference_time` 设为推演场景时间
- Episode name 格式：`simulation_{sandbox_id}_{scenario_time}`
- 对比查询：`query_temporal(valid_time=scenario_time, entity_type="simulation_result")`

---

## 课题4: MinIO 对象存储集成

### 4.1 MinIO Python SDK 使用方式

**Decision**: 使用 `minio` Python SDK（官方 minio-py），封装为 `odap/infra/storage/minio_client.py`

**Rationale**:
- minio-py 是 MinIO 官方 Python 客户端，API 兼容 Amazon S3
- 支持文件上传/下载、预签名 URL、桶管理、版本控制
- 与 FastAPI 的 `UploadFile` 集成简单

**核心 API**:
```python
from minio import Minio

client = Minio(
    endpoint="minio:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)

client.put_object(bucket_name, object_name, data, length, content_type)
client.get_object(bucket_name, object_name)
client.presigned_get_object(bucket_name, object_name, expires=timedelta(hours=1))
client.remove_object(bucket_name, object_name)
```

### 4.2 文档/图片存储方案设计

**Decision**: 按工作空间分桶，按模块/实体类型/实体ID组织对象Key

**Rationale**:
- 工作空间隔离要求每个工作空间独立桶
- 层级化 Key 便于权限控制和生命周期管理

**对象 Key 格式**:
```
{module}/{entity_type}/{entity_id}/{filename}
```

**示例**:
```
ingestion/MilitaryUnit/UNIT_001/situation_report.pdf
ingestion/MilitaryUnit/UNIT_001/satellite_image.png
ontology/exports/ontology_v2.json
simulation/sandbox_001/result_charts.png
```

### 4.3 与 FastAPI 的集成方式

**Decision**: 文件上传通过 `UploadFile` 接收 → MinIO 存储 → 返回对象 Key 和预签名 URL

**Rationale**:
- FastAPI 的 `UploadFile` 基于 `python-multipart`，支持流式上传
- 大文件不经过内存，直接流式传输到 MinIO
- 预签名 URL 实现临时访问，无需暴露 MinIO 凭证

**Implementation Notes**:
- `minio_client.py` 封装 `MinIOClient` 单例类
- `upload_object()`: 接收 FastAPI `UploadFile`，流式上传到 MinIO
- `get_presigned_url()`: 生成 1 小时有效的预签名 URL
- `download_object()`: 返回文件流，用于后端处理（OCR/PDF 提取）
- 桶自动创建：首次访问工作空间时创建 `ws-{workspace_id}` 桶

### 4.4 Docker Compose 中的 MinIO 配置

**Decision**: 新增 MinIO 服务到 `docker/docker-compose.yml`，端口 9000（API）+ 9001（Console）

**Rationale**:
- MinIO 官方 Docker 镜像轻量，单进程运行
- Console 端口便于开发调试时查看存储内容
- 数据持久化通过 volume 映射

**配置**:
```yaml
minio:
  image: minio/minio:latest
  ports:
    - "9000:9000"
    - "9001:9001"
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
  command: server /data --console-address ":9001"
  volumes:
    - minio_data:/data
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval: 30s
    timeout: 10s
    retries: 3
```

**环境变量**:
```
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
```

**Alternatives Considered**:
1. **SQLite BLOB 存储** — 大文件性能差，不符合"不重复引入存储引擎"原则，被否决
2. **本地文件系统** — 不支持分布式部署，容器环境数据持久化复杂，被否决
3. **AWS S3** — 需要云服务依赖，本地开发不便，被否决

---

## 课题5: 前端5级组件体系+可替代性设计

### 5.1 L1原子→L2分子→L3组织→L4模板→L5页面的具体划分标准

**Decision**: 按组件职责和复用粒度划分5级，每级有明确的输入输出契约

**划分标准**：

| 级别 | 名称 | 划分标准 | 特征 | 示例 |
|------|------|----------|------|------|
| L1 | Atoms | 最小不可拆分 UI 单元，无业务语义 | 单一职责、无内部状态管理、纯展示/交互 | Button, Input, Badge, Tooltip, Icon |
| L2 | Molecules | 原子组合，有明确功能，可配置 | 包含2+原子、有内部交互逻辑、可配置 | FormField, SearchBar, Card, Modal, Dropdown |
| L3 | Organisms | 分子组合，独立功能区块，可连接数据源 | 包含2+分子、有数据获取逻辑、可独立使用 | DataTable, FormPanel, GraphView, ChatPanel, MapView |
| L4 | Templates | 组织组合，页面布局骨架，定义区域 | 包含2+组织、定义布局结构、区域可替换 | MasterDetail, SplitView, FullScreen, Dashboard |
| L5 | Pages | 模板+数据，完整页面，绑定路由 | 包含1+模板、绑定数据源、关联路由 | OntologyDesigner, AgentChat, SimulationDeduction |

**关键约束**：
- L1-L3 组件必须与具体业务无关，可在任何模块复用
- L4 模板定义区域（slot），L5 页面填充区域内容
- 跨级引用规则：L_N 只能引用 L_{N-1} 及以下，禁止反向引用

### 5.2 组件库 adapter 隔离层设计模式

**Decision**: 实现 UIAdapter 抽象接口 + AntDesignAdapter 具体实现，L2+ 组件通过 Adapter 获取 L1 原子

**Rationale**:
- 现有前端代码直接引用 `antd` 组件（如 `import { Button } from 'antd'`），与 Ant Design 强耦合
- Adapter 隔离层使得替换组件库时只需实现新 Adapter，无需修改 L2+ 组件代码
- 隔离层保持轻量，当前仅实现 AntDesignAdapter；不预先添加其他适配器实现

**Adapter 接口设计**:
```typescript
interface UIAdapter {
  getButton(): React.ComponentType<ButtonProps>;
  getInput(): React.ComponentType<InputProps>;
  getTable(): React.ComponentType<TableProps>;
  getModal(): React.ComponentType<ModalProps>;
  getForm(): React.ComponentType<FormProps>;
  getSelect(): React.ComponentType<SelectProps>;
  getTag(): React.ComponentType<TagProps>;
  getTooltip(): React.ComponentType<TooltipProps>;
  getMessage(): MessageInstance;
  getNotification(): NotificationInstance;
}
```

**Implementation Notes**:
- `shared/components/adapter/UIAdapter.ts`: 抽象接口定义
- `shared/components/adapter/AntDesignAdapter.ts`: Ant Design 6 实现
- `shared/components/adapter/index.ts`: 导出当前 Adapter 实例
- L2+ 组件通过 `import { adapter } from '../adapter'` 获取组件，不直接 `import { Button } from 'antd'`
- **渐进式迁移**：现有页面不强制立即迁移，新组件必须使用 Adapter

### 5.3 移动优先6断点响应式实现策略

**Decision**: 移动优先 CSS（min-width 递进增强）+ useResponsive Hook + 6断点常量

**Rationale**:
- 现有 `frontend/src/modules/shared/utils/responsive.ts` 已实现基础断点检测
- 但现有断点定义与 plan.md 不完全一致（现有 lg=1024 vs plan lg=992）
- 需要统一为 Ant Design 6 的标准断点

**6断点定义**（对齐 Ant Design 6）：

| 断点 | 名称 | 宽度 | 典型设备 | 布局策略 |
|------|------|------|----------|----------|
| xs | 极小 | < 576px | 手机竖屏 | 单列全屏 |
| sm | 小 | ≥ 576px | 手机横屏 | 双列卡片 |
| md | 中 | ≥ 768px | 平板竖屏 | 侧栏折叠 |
| lg | 大 | ≥ 992px | 平板横屏/小笔记本 | 侧栏展开 |
| xl | 超大 | ≥ 1200px | 桌面 | 完整布局 |
| xxl | 极大 | ≥ 1600px | 大屏桌面 | 宽松布局 |

**Implementation Notes**:
- `shared/styles/breakpoints.ts`: 断点常量 + CSS 媒体查询 mixin
- `shared/hooks/useResponsive.ts`: 响应式 Hook，返回当前断点信息
- CSS 策略：移动优先，从 xs 基础样式开始，用 `@media (min-width: ...)` 递进增强
- Ant Design 6 的 Grid 系统（Row/Col）自带响应式支持，直接使用 `xs/sm/md/lg/xl/xxl` 属性

### 5.4 react-i18next 集成方案

**Decision**: 使用 react-i18next 作为 i18n 框架，按模块拆分翻译文件，后端 API 管理+LLM 翻译

**Rationale**:
- react-i18next 是 React 生态最成熟的 i18n 方案，支持命名空间、懒加载、插值
- 按模块拆分翻译文件避免单文件过大，支持按需加载
- 后端 API + LLM 翻译实现翻译管理的自动化

**Alternatives Considered**:
1. **react-intl** — ICU Message Format 更标准，但命名空间支持不如 i18next，被否决
2. **自研 i18n** — 维护成本高，功能不完善，被否决

**Implementation Notes**:
- 安装：`npm install react-i18next i18next i18next-http-backend`
- 初始化：`shared/stores/i18nStore.ts` 配置 i18next 实例
- 翻译文件：`modules/{name}/locales/{locale}/{name}.json`
- 共享翻译：`modules/shared/locales/{locale}/common.json`
- 使用：`const { t } = useTranslation('ontology'); <h1>{t('title')}</h1>`
- 后端 API：`/api/i18n/translations` CRUD + `/api/i18n/translations/auto-translate` LLM 翻译
- 语言切换：Zustand store 管理当前语言，切换时调用 `i18n.changeLanguage()`

---

## 课题6: ABAC+OPA 权限模型

### 6.1 ABAC 属性定义和策略编写

**Decision**: 四维 ABAC 模型（Subject + Action + Resource + Environment），OPA Rego 策略评估

**Rationale**:
- 现有 `odap/infra/opa/opa_service.py` 已实现 `ABACPolicyEvaluator` 和 `check_permission_abac()`
- 现有 Rego 策略（`opa_policy.rego`）基于 RBAC（user_role → permissions → restrictions）
- 需要扩展为完整 ABAC，增加环境属性（时间/IP/工作空间）和资源属性（分类级别/工作空间归属）

**ABAC 四维属性定义**：

| 维度 | 属性 | 来源 | 示例 |
|------|------|------|------|
| **Subject** | user_id, roles[], clearance_level, workspace_roles{} | JWT Token | {"roles": ["commander"], "clearance_level": "secret"} |
| **Action** | action_type, action_category | 请求参数 | {"type": "attack", "category": "write"} |
| **Resource** | resource_type, classification_level, workspace_id | 资源元数据 | {"type": "WeaponSystem", "classification": "S", "ws_id": "ws-1"} |
| **Environment** | time_of_day, source_ip, workspace_isolation_level | 请求上下文 | {"time": "09:00", "ip": "10.0.0.1", "isolation": "strict"} |

**Rego 策略示例**:
```rego
package odap.abac

default allow = false

allow {
    has_permission(input.subject, input.action)
    not is_restricted(input.subject, input.action, input.resource)
    classification_allowed(input.subject.clearance_level, input.resource.classification)
    workspace_allowed(input.subject.workspace_id, input.resource.workspace_id)
}

classification_allowed("TS", _)       # Top Secret 可访问所有
classification_allowed("S", level)    # Secret 可访问 S/C/U
classification_allowed("C", level)    # Confidential 可访问 C/U
classification_allowed("U", "U")      # Unclassified 仅访问 U
```

### 6.2 OPA Markdown→Rego 编译方案

**Decision**: 自定义 Markdown DSL → Rego 编译器，编译失败时保持旧策略运行（fail-close）

**Rationale**:
- 现有 `OPAManager` 已支持 `put_policy()` 上传 Rego 策略和 `hot_update_bundle()` 热更新
- 需要增加 Markdown→Rego 编译层，让非技术用户也能编写策略
- fail-close 保证编译失败时不影响现有策略

**Markdown DSL 语法**:
```markdown
## 规则: 指挥官攻击授权

当 [subject.role == "commander"]
且 [action.type == "attack"]
且 [resource.type != "CivilianInfrastructure"]
时 [允许]

## 规则: 禁止攻击民用设施

当 [resource.type == "CivilianInfrastructure"]
且 [action.type == "attack"]
时 [拒绝]
```

**编译流程**:
1. 解析 Markdown 标题 → Rego 规则名
2. 解析 `当 [...] 且 [...]` → Rego 条件组合
3. 解析 `时 [允许/拒绝]` → Rego 规则体
4. 生成完整 Rego 文件
5. 编译验证（`opa parse` 或 `opa eval --partial`）
6. 验证通过 → 上传到 OPA；验证失败 → 保持旧策略，返回错误信息

**Implementation Notes**:
- 新增 `odap/infra/opa/markdown_compiler.py`
- 编译器使用正则表达式解析 Markdown DSL
- 不暴露 Rego 编译错误细节给非管理员用户
- 策略版本管理：SQLite 存储策略版本历史，支持回滚

### 6.3 策略热更新机制

**Decision**: 基于 OPA Bundle API + 版本化策略文件 + 30秒生效

**Rationale**:
- 现有 `PolicyBundleManager` 已实现 Bundle 创建、保存、回滚
- OPA 的 Bundle API 支持原子性策略更新
- 30秒生效目标通过 OPA 的轮询间隔配置实现

**Implementation Notes**:
- `OPAManager.hot_update_bundle(policies)` — 创建新 Bundle 版本
- Bundle 包含所有 Rego 策略文件 + data.json
- 上传到 OPA 的 `/v1/bundles` 端点
- OPA 配置 `polling.min_delay_seconds: 5`，确保 30 秒内生效
- 编译失败时保持旧 Bundle 运行（fail-close）
- 缓存清理：热更新后调用 `clear_cache()` 清除权限缓存

### 6.4 审计日志与 OPA 集成

**Decision**: 所有写操作通过 `unified_audit.py` 记录，OPA 决策结果作为审计日志的一部分

**Rationale**:
- 现有 `unified_audit.py` 已实现统一审计通道
- 现有 `audit_graphiti_channel.py` 已实现 Graphiti 审计通道
- OPA 决策结果（allow/deny + reason）需要记录到审计日志

**Implementation Notes**:
- `OPAManager.check_permission_abac()` 内部调用 `_record_history()`
- 审计记录包含：actor, action, resource, result(allow/deny), reason, policy_version, timestamp
- 写入 SQLite（结构化查询）+ Graphiti（图遍历分析）
- 前端审计时间线组件展示 OPA 决策链路

---

## 课题7: 统一查询服务设计

### 7.1 schema/entity/topo/temporal 四种查询源的实现

**Decision**: 基于现有 `odap/infra/query/` 扩展，4种查询源通过 Protocol 接口定义

**Rationale**:
- 现有 `QueryService` 已实现 schema/entity/topo 三种查询源
- 现有 `protocols.py` 已定义 `SchemaSource`, `EntitySource`, `TopoSource` Protocol
- 现有 `parser.py` 已实现 `.schema/.entity/.topo/.temporal` 查询语法解析
- 需要增强 temporal 查询源和 Agent Safe 只读模式

**四种查询源实现**：

| 查询源 | 实现类 | 数据源 | 查询能力 |
|--------|--------|--------|----------|
| **schema** | `SchemaSourceImpl` | OMS (SQLite) | 对象类型/属性/关系/动作定义查询 |
| **entity** | `EntitySourceImpl` | GraphManager (Neo4j) | 实体实例 CRUD+过滤+分页+搜索 |
| **topo** | `TopoSourceImpl` | GraphManager (Neo4j) | 邻居/关系/路径/子图遍历 |
| **temporal** | 需新增 `TemporalSourceImpl` | GraphManager (Graphiti) | 时序查询/历史/双时态 |

**现有实现差距**：
- `TemporalSource` Protocol 未在 `protocols.py` 中定义
- `QueryService._execute_temporal()` 已有基础实现，但功能简单
- 需要新增 `TemporalSourceImpl`，封装 `GraphManager.query_temporal()` 和 `get_entity_history()`

### 7.2 Agent Safe 只读模式实现

**Decision**: 通过 `QueryServiceToolRegistry` 区分 read/write 工具，Agent 默认只能调用 read 工具

**Rationale**:
- 现有 `odap/infra/openharness/query_guard_hook.py` 已实现 `QueryServiceWriteGuard` 和 `QueryServiceToolRegistry`
- `QueryServiceToolRegistry` 已定义 READ_TOOLS（query_schema, query_entity, query_topo）和 WRITE_TOOLS
- 需要增强为完整的 Agent Safe 模式

**Implementation Notes**:
- Agent Safe 模式：Agent 通过 OpenHarness Tool 接口调用 QueryService，默认只暴露 READ_TOOLS
- WRITE_TOOLS 需要 OPA 审批才能调用
- 架构守卫：pytest 测试用例验证 Agent 代码中没有直接调用 `graph_manager` 的写方法
- `QueryServiceWriteGuard` 作为 OpenHarness Pre-Hook 拦截写操作

### 7.3 通过 OpenHarness Tool 接口注册

**Decision**: 将 QueryService 的4种查询源注册为 OpenHarness BaseTool，通过 ToolRegistry 管理

**Rationale**:
- 现有 `QueryServiceToolRegistry` 已定义工具注册格式
- OpenHarness `BaseTool` 接口要求 `name`, `description`, `input_model`, `execute()`
- 每种查询源注册为独立 Tool，Agent 可按需调用

**Implementation Notes**:
- `query_schema` → SchemaSource 查询 Tool
- `query_entity` → EntitySource 查询 Tool
- `query_topo` → TopoSource 查询 Tool
- `query_temporal` → TemporalSource 查询 Tool（新增）
- 所有 Tool 通过 `GraphitiToolAdapter` 适配为 OpenHarness `BaseTool`
- 注册到 `ToolRegistry`，Agent Loop 可自动发现和调用

---

## 课题8: OODA 编排+OADP 闭环共存方案

### 8.1 OODA 作为 Agent 编排模型

**Decision**: OODA（Observe→Orient→Decide→Act）作为 Agent 编排的核心循环，与 OpenHarness 对齐

**Rationale**:
- 现有 `odap/biz/core/agent/swarm_orchestrator.py` 已实现完整 OODA 循环
- `DomainSwarm` 类实现 `execute_mission()` → `_observe() → _orient() → _decide() → _act()`
- 三个 Agent 角色与 OODA 阶段对应：Intelligence(Observe/Orient) → Commander(Decide) → Operations(Act)
- 流式执行 `execute_streaming()` 通过 AsyncGenerator 逐步返回 OODA 进度

**OODA 与 OpenHarness 对齐**：
- Observe → OpenHarness Tool 调用（查询数据）
- Orient → OpenHarness Hook 后处理（RAG 增强）
- Decide → OpenHarness QueryEngine（LLM 决策）
- Act → OpenHarness Tool 执行（写操作）

### 8.2 OADP 作为闭环反馈扩展

**Decision**: OADP（Observe→Analyze→Decide→Propagate）作为 OODA 的闭环反馈扩展，含 Propagate 追踪传播

**Rationale**:
- OODA 是开环：Act 之后没有反馈机制
- OADP 在 OODA 基础上增加闭环：Act 的结果反馈到 Observe，形成持续改进循环
- Propagate 阶段确保决策结果传播到所有相关方和知识图谱

**OADP 阶段映射**：

| OADP 阶段 | 对应 OODA | ODAP 实现 | 关键组件 |
|-----------|-----------|-----------|----------|
| **Observe** | Observe | 感知层输入 | IntelligenceAgent + QueryService |
| **Analyze** | Orient | 分析理解 | KnowledgeNavigator + TemporalReasoner |
| **Decide** | Decide | 决策推荐 | DecisionRecommendationEngine + OPA |
| **Propagate** | Act + 反馈 | 执行+传播+追踪 | OperationsAgent + FeedbackCollector + Hook广播 |

**Propagate 追踪传播**：
- 执行结果写入 Graphiti（知识沉淀）
- 通过 Hook 系统广播变更事件（通知相关 Agent 刷新缓存）
- 审计日志记录完整决策链路
- 反馈分析器量化评估决策效果

### 8.3 两者在代码中的共存方式

**Decision**: OODA 作为 Agent 编排的核心循环（DomainSwarm），OADP 作为外层闭环包装（FeedbackLoop）

**Rationale**:
- OODA 是 Agent 执行的"内循环"，每次任务执行一次
- OADP 是系统级"外循环"，跨多次任务执行，持续改进
- 两者不冲突，OODA 是 OADP 的子集

**代码结构**：
```python
# OODA 内循环 - 已实现
class DomainSwarm:
    async def execute_mission(mission, context) -> MissionResult:
        observe_result = await self._observe(mission, context)
        orient_result = await self._orient(observe_result, context)
        decide_result = await self._decide(orient_result, context)
        act_result = await self._act(decide_result, context)
        return MissionResult(...)

# OADP 外循环 - 需新增
class FeedbackLoop:
    async def run_with_feedback(mission, context) -> FeedbackResult:
        # OODA 内循环
        mission_result = await self.swarm.execute_mission(mission, context)
        
        # Propagate 阶段
        await self.collector.collect(mission_result)           # 收集执行结果
        analysis = await self.analyzer.analyze(mission_result) # 分析决策效果
        await self.aggregator.aggregate(analysis)              # 聚合历史经验
        
        # 反馈到知识图谱
        await self._propagate_to_graphiti(analysis)
        
        # Hook 广播
        await self.hook_manager.emit("feedback.completed", analysis)
        
        return FeedbackResult(mission_result=mission_result, analysis=analysis)
```

**Implementation Notes**:
- `DomainSwarm` 保持不变，仅负责 OODA 内循环
- 新增 `FeedbackLoop` 类，包装 `DomainSwarm`，增加 Propagate 阶段
- `FeedbackLoop` 部署在同一进程内，通过 OpenHarness Hook 机制触发
- 反馈数据写入 Graphiti + SQLite，支持历史对比和经验沉淀
- OODA 和 OADP 在 API 层面共存：`/api/agent/dispatch` 触发 OODA，`/api/feedback/close-loop` 触发 OADP 闭环

**Alternatives Considered**:
1. **统一为 OADP** — 将 OODA 完全替换为 OADP — 改动太大且 OODA 概念更通用，被否决
2. **独立 OADP 服务** — OADP 作为独立微服务 — 引入 IPC 开销，被否决
3. **OADP 仅作为文档概念** — 代码中不体现 — 无法实现闭环反馈的自动化，被否决

---

## 附录：代码库关键文件索引

| 课题 | 关键文件 | 说明 |
|------|----------|------|
| OpenHarness | `odap/infra/openharness/tool_adapter.py` | v1/v2 兼容适配层 |
| OpenHarness | `odap/infra/openharness/v2_adapter.py` | v2 深度适配层 |
| OpenHarness | `odap/biz/integration/openharness_agent/api/routes.py` | Agent API 路由 |
| Palantir/OMS | `odap/biz/core/ontology/oms/schemas.py` | OMS 数据模型 |
| Palantir/OMS | `odap/biz/core/ontology/oms/storage/sqlite_oms_storage.py` | OMS SQLite 存储 |
| Palantir/OMS | `odap/biz/core/ontology/schema/document.py` | OntologyDocument 格式 |
| Palantir/OMS | `odap/biz/core/ontology/schema/domain.py` | 领域实体类型种子数据 |
| Graphiti | `odap/infra/graph/graph_service.py` | GraphManager（含双时态查询） |
| Graphiti | `odap/infra/openharness/memory_adapter.py` | Graphiti 记忆适配器 |
| Graphiti | `odap/infra/logging/graphiti_events.py` | Graphiti 事件追踪 |
| MinIO | `odap/infra/storage/` | 存储基础设施目录（需新增 minio_client.py） |
| 前端 | `frontend/src/modules/shared/utils/responsive.ts` | 响应式断点 |
| 前端 | `frontend/src/modules/shared/components/AppLayout.tsx` | 主布局组件 |
| OPA | `odap/infra/opa/opa_service.py` | OPA 权限管理器 |
| OPA | `odap/infra/opa/opa_policy.rego` | Rego 策略文件 |
| OPA | `odap/biz/platform/roles/opa_sync.py` | 角色→OPA 同步 |
| 查询 | `odap/infra/query/service.py` | 统一查询服务 |
| 查询 | `odap/infra/query/protocols.py` | 查询源 Protocol 定义 |
| 查询 | `odap/infra/query/parser.py` | 查询语法解析器 |
| 查询 | `odap/infra/openharness/query_guard_hook.py` | 查询守卫+工具注册 |
| OODA/OADP | `odap/biz/core/agent/swarm_orchestrator.py` | DomainSwarm OODA 循环 |
| OODA/OADP | `odap/biz/decision/decision_recommendation/engine.py` | 决策推荐引擎 |

---

## Phase 4 增量研究 (2026-06-05 Brainstorm)

> 以下课题对应 plan.md "Phase 4: Palantir/OntoFlow 增强层"，源自 2026-06-05 deep-dive brainstorm。

### 课题9: 本体 Branch & Merge 的存储与冲突解决算法

**Decision**: 3-way JSON Merge (基于 RFC 6902 JSON Patch) + 用户手动解决冲突

**Rationale**:
- Palantir Foundry 的 Branch & Merge 基于 git-like 语义，但底层是图数据库
- ODAP 的 OntologyDocument 是 JSON (FR-029)，天然适合 JSON Patch
- 3-way merge: base + ours + theirs → 自动合并无冲突字段 → 冲突字段由用户选择

**Alternatives Considered**:
- ❌ 文本 diff (line-based)：JSON 重排时产生大量误冲突
- ❌ Operational Transform (OT)：复杂度高，主流编辑器协议但不适合数据模型
- ✅ JSON Patch (RFC 6902)：标准协议、库成熟、社区广泛

**实施细节**:
- 存储：分支作为 `OntologyBranch` 实体，包含 `head_version_id`
- 合并：创建临时 3-way 快照，生成 JSON Patch diff
- 冲突检测：同一 `field_path` 在 base/ours/theirs 三方值不同
- 主分支保护：`is_protected=True` 时禁止 direct push

### 课题10: 计算属性依赖图与重算策略

**Decision**: 物化视图 + 反向依赖索引 + 增量重算 + 定时全量校验

**Rationale**:
- 维护 `Property.depends_on` 字段，构建反向索引 `EntityPropertyDependents`
- 实体变更时：触发下游 view 增量重算
- 大数据规模：> 100K 实例时支持分批重算
- Stale 警告：返回查询结果时附 `is_stale` 标志

**Alternatives Considered**:
- ❌ 实时计算（无缓存）：性能差，特别是复杂计算属性
- ❌ 触发器模式：与 OpenHarness Hook 系统重叠
- ✅ 物化视图：经典 OLAP 模式，成熟可靠

**实施细节**:
- 增量重算：基于 event sourcing，Post-Hook 监听 entity change
- 定时全量：apscheduler cron 表达式
- 失败重试：3 次指数退避，超过则标记 view 为 `degraded`

### 课题11: Action Type 与现有 ToolRegistry 集成方案

**Decision**: Action Type 作为 Skill 的"类型化包装"，现有 ToolRegistry 保留并标记 legacy

**Rationale**:
- Action Type 在本体层 (业务接口)，Skill 在能力层 (工程实现)
- 现有 ToolRegistry 已实现 Skill 管理 (FR-025)
- 增量方式：先支持 Action Type → Skill 映射，不破坏现有调用
- 长期：现有 Tool 逐步迁移为 Skill，再绑定到 Action Type

**Alternatives Considered**:
- ❌ 完全替换 ToolRegistry：破坏现有业务，回归测试工作量大
- ❌ Action Type 作为独立子系统：与 Skill 数据双轨制
- ✅ Action Type 作为 Skill 的 Facade：单一数据源，Action 提供业务语义

**实施细节**:
- `ActionType.implementation: List[str]` 引用 Skill IDs
- ActionExecutor 解析 Action → 加载 Skill 列表 → 按序执行
- 失败回滚：所有 Skill 视为同一事务，任一失败回滚

### 课题12: OntoFlow Goal-driven 演化的强制机制

**Decision**: 本体验证器 + UI 强制要求 goal + rationale，缺一拒绝提交

**Rationale**:
- OntoFlow 的核心：本体演化必须有业务目标驱动
- 强制方式：API 层 `ChangeRequest` schema 必填 `goal_id` + `rationale`
- 降低阻力：提供 Goal 模板 + 快捷创建（"功能改进"、"Bug 修复"、"性能优化"）

**Alternatives Considered**:
- ❌ 仅记录但不强制：沦为可选字段，无实际效果
- ❌ 完全自由化：不记录业务目标
- ✅ 强制 + 模板：保证质量的同时降低使用门槛

**实施细节**:
- `OntologyChange` model 加 `goal_id: str` (required) + `rationale: str` (required, min 20 chars)
- Goal CRUD 独立 API (`/api/ontology/goals`)
- 审计：`GET /api/ontology/changes?goal_id={id}` 反查
- 报表：每季度生成 Goal → Change → Impact 报表

### 课题13: Object View 与 OPA 的职责分离

**Decision**: View 决定"展示什么"（业务语义），OPA 决定"能否访问"（安全策略），互不重叠

**Rationale**:
- View 是业务概念：同一 Object Type 在不同场景展示不同属性（commander-view / operator-view）
- OPA 是安全概念：基于 subject + action + resource 决策
- 两者职责正交：View 提供候选，OPA 二次拦截
- 类比：View 是 RDBMS 的 VIEW，OPA 是 GRANT

**Alternatives Considered**:
- ❌ View 包含权限逻辑：业务与安全耦合
- ❌ OPA 包含 View 逻辑：策略文件爆炸
- ✅ 职责分离：View → OPA → 实际数据

**实施细节**:
- `ObjectView.included_properties` 白名单
- `RedactionRule`：mask/hash/partial/remove 四种脱敏
- ViewResolver：view → properties → OPA check → final visible props
- 缓存：Redis 缓存 view resolution (TTL 5min)


