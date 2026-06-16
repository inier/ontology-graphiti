# ODAP 测试体系文档

## 目录结构

```
tests/
├── README.md                    # 本文档
├── __init__.py                  # 测试包初始化
├── conftest.py                  # 全局 pytest fixtures (mock_sqlite, temp_db, tool_registry, skill_registry, audit_logger)
├── helpers/                     # 共享测试工具
│   ├── __init__.py
│   ├── factories.py             # 通用模型工厂 (make_ontology, make_workspace, make_agent, etc.)
│   ├── api_client.py            # FastAPI TestClient 辅助 (create_auth_client, patch_service)
│   └── storage.py               # SQLite 存储测试基类 (StorageTestBase)
├── unit/                        # 单元测试 (140+ 文件)
│   ├── conftest.py              # 单元测试 fixtures (auth_client, tmp_db_path, mock_llm_response)
│   ├── test_ontology_*.py       # 本体管理 (15 个文件)
│   ├── test_agent*.py           # Agent 编排 (6 个文件)
│   ├── test_decision_*.py       # 决策流水线 (5 个文件)
│   ├── test_hook_system.py      # Hook 事件系统
│   ├── test_mcp_*.py            # MCP 协议适配
│   ├── test_agui_*.py           # AGUI 处理器/模型/性能/安全/传输
│   ├── test_workspace*.py       # 工作空间管理
│   ├── test_roles*.py           # 角色与权限
│   ├── test_skill_system.py     # 技能系统
│   ├── test_tool_registry*.py   # 工具注册
│   ├── test_config_*.py         # 配置管理 (4 个文件)
│   ├── test_data_warehouse.py   # 数据仓库
│   ├── test_knowledge_base.py   # 知识库
│   ├── test_qa_*.py             # QA 问答引擎
│   ├── test_semantic_map.py     # 语义地图
│   ├── test_ingestion*.py       # 数据摄入
│   ├── test_nl_*.py             # 自然语言查询
│   ├── test_search_service.py   # 搜索服务
│   ├── test_collection_*.py     # 采集存储
│   ├── test_crawl_service.py    # 爬取服务
│   ├── test_simulation_*.py     # 模拟仿真 (14 个文件)
│   ├── test_business.py         # 业务管理
│   ├── test_blueprint_*.py      # 蓝图设计器
│   ├── test_graph_*.py          # 图服务 (3 个文件)
│   ├── test_opa*.py             # OPA 策略 (3 个文件)
│   ├── test_audit_*.py          # 审计系统 (5 个文件)
│   ├── test_auth*.py            # 认证 (3 个文件)
│   ├── test_jwt_service.py      # JWT 服务
│   ├── test_health.py           # 健康检查
│   ├── test_middleware.py        # 中间件
│   ├── test_llm_*.py            # LLM 服务 (2 个文件)
│   ├── test_resilience.py       # 弹性/熔断
│   ├── test_circuit_breaker.py  # 熔断器
│   ├── test_analysis_skills.py  # 分析技能
│   ├── test_computation_skills.py # 计算推理技能
│   ├── test_intelligence_skills.py # 情报技能
│   ├── test_operations_skills.py   # 执行技能
│   ├── test_planning_skills.py     # 规划编排技能
│   ├── test_policy_skills.py       # 策略技能
│   ├── test_recommendation_skills.py # 推荐技能
│   ├── test_task_management_skills.py # 任务管理技能
│   ├── test_object_service.py      # 对象服务
│   ├── test_web_app.py             # Web 入口 (健康检查/路由注册)
│   ├── test_architecture_boundary.py   # 架构边界检查
│   ├── test_route_exception_handling.py # 路由异常透传检查
│   ├── test_pydantic_mutable_defaults.py # Pydantic 可变默认值检查
│   └── ...                          # 其他测试文件
├── integration/                 # 集成测试 (13 个文件)
│   ├── conftest.py              # 集成测试 fixtures (neo4j_available, opa_available, backend_available)
│   └── test_*.py
├── e2e/                         # 端到端测试 (6 个文件)
│   ├── conftest.py              # E2E fixtures (api_base_url, e2e_auth_token)
│   └── test_*.py
└── perf/                        # 性能测试 (1 个文件)

frontend/
├── vitest.config.ts             # Vitest 配置
├── src/test/
│   ├── setup.ts                 # 全局 setup (fetch mock, matchMedia, ResizeObserver, WebGL stubs)
│   ├── helpers/                 # 前端测试工具
│   │   ├── apiMock.ts           # API mock 工具 (createMockFetch, mockApiEndpoint, authMocks)
│   │   ├── storeTestUtils.ts    # Zustand store 测试工具 (createTestStore, resetStore)
│   │   ├── renderWithProviders.tsx # 组件渲染工具 (renderWithProviders, renderWithRouter)
│   │   └── index.ts             # 统一导出
│   ├── api_integration.test.ts  # API 集成测试
│   └── components.test.tsx      # 组件导出验证
└── src/modules/
    ├── agent/
    │   ├── stores/agentStore.test.ts
    │   └── services/agentApi.test.ts
    ├── audit/stores/auditStore.test.ts
    ├── workspace/
    │   ├── stores/workspaceStore.test.ts
    │   └── components/WorkspaceSwitcher.test.tsx
    ├── simulation/
    │   ├── stores/simulationStore.test.ts
    │   └── services/simulationApi.test.ts
    ├── knowledge/
    │   ├── stores/knowledgeStore.test.ts
    │   └── services/knowledgeApi.test.ts
    ├── ontology/
    │   ├── stores/blueprintStore.test.ts
    │   ├── services/ontologyApi.test.ts
    │   └── components/OntologyBuildProgress.test.tsx
    ├── business/services/businessApi.test.ts
    ├── roles/pages/RoleManager.test.tsx
    ├── ingest/pages/IngestPanel.test.tsx
    ├── shared/
    │   ├── stores/authStore.test.ts
    │   ├── pages/LoginPage.test.tsx
    │   └── components/ (StatCard, PageHeader, QAPanel, ToolHealthIndicator, GraphControls, GraphToolbar)
    └── qa/agui/__tests__/useAGUI.test.tsx
```

---

## 测试统计

| 类别 | 文件数 | 测试数 |
|------|--------|--------|
| 后端单元测试 | 140+ | 1000+ |
| 后端集成测试 | 13 | - |
| 后端 E2E 测试 | 6 | - |
| 前端测试 | 30+ | 500+ |
| **总计** | **190+** | **1500+** |

---

## 运行测试

### 后端

```bash
# 运行全部单元测试
pytest tests/unit/ -v

# 运行特定模块测试
pytest tests/unit/test_ontology_storage.py -v
pytest tests/unit/test_analysis_skills.py -v

# 运行集成测试（需要外部服务）
pytest tests/integration/ -v -m integration

# 运行 E2E 测试（需要后端运行）
pytest tests/e2e/ -v -m e2e

# 运行带覆盖率
pytest --cov=odap tests/unit/
```

### 前端

```bash
cd frontend

# 运行全部测试
npm test

# 运行特定模块
npx vitest run src/modules/agent/stores/agentStore.test.ts

# 运行带覆盖率
npm run test:coverage

# 监听模式
npm run test:watch
```

---

## 测试编写规范

### 后端 (pytest)

#### 分层测试要求

| 层 | 必测场景 | 工具 |
|---|---------|------|
| storage/ | CRUD 全流程、get 不存在返回 None、JSON 序列化、非法 JSON 容错 | `tmp_path` 真实 DB |
| models/ | 必填字段验证、默认值、容器字段 default_factory、Enum 值 | Pydantic 验证 |
| services/ | 成功返回扁平 dict、错误返回 `{"status": "error"}`、类型转换 | mock storage |
| routes/ | HTTP 状态码映射、`except HTTPException: raise` 透传 | `TestClient` + `dependency_overrides` |

#### 关键规则

1. **SQLite 存储测试用 `tmp_path` 真实 DB**，禁止 MagicMock 模拟数据库
2. **服务层不抛 HTTPException**，返回 `{"status": "error", "message": "..."}`
3. **路由层必须 `except HTTPException: raise`** 透传
4. **Enum 必须 `(str, Enum)`** 双继承
5. **容器字段必须 `Field(default_factory=...)`**
6. **新增模块必须同步新增测试文件**

#### 使用共享工具

```python
# 使用工厂函数
from tests.helpers.factories import make_ontology, make_workspace

# 使用 TestClient 辅助
from tests.helpers.api_client import create_auth_client

client, cleanup = create_auth_client(role="admin")
try:
    resp = client.get("/api/ontologies")
finally:
    cleanup()

# 使用存储测试基类
from tests.helpers.storage import StorageTestBase

class TestMyStorage(StorageTestBase):
    storage_class = SQLiteMyStorage

    def test_save_and_get(self, tmp_path):
        storage = self.make_storage(tmp_path)
        storage.save_item({"id": "1", "name": "test"})
        result = storage.get_item("1")
        assert result is not None
```

### 前端 (vitest)

#### 测试类型

| 类型 | 工具 | 示例 |
|------|------|------|
| Store 测试 | `useXxxStore.getState()` | `agentStore.test.ts` |
| API 服务测试 | `vi.spyOn(globalThis, 'fetch')` | `agentApi.test.ts` |
| 组件测试 | `@testing-library/react` | `LoginPage.test.tsx` |
| Hook 测试 | `renderHook` from `@testing-library/react` | `useAGUI.test.tsx` |

#### 使用共享工具

```typescript
// API mock
import { createMockFetch, authMocks } from '@/test/helpers';
const mockFetch = createMockFetch({ '/api/workspaces': { data: [] } });

// Store 测试
import { createTestStore } from '@/test/helpers';
const store = createTestStore(() => useAuthStore);

// 组件渲染
import { renderWithProviders } from '@/test/helpers';
const { container } = renderWithProviders(<MyComponent />);
```

---

## 新增测试文件规范

### 文件命名

- 后端：`test_<模块名>.py`，放在 `tests/unit/` 下
- 前端：`<ComponentName>.test.tsx` 或 `<storeName>.test.ts`，放在模块目录下

### 位置选择

| 测试类型 | 后端位置 | 前端位置 |
|---------|---------|---------|
| 单元测试 | `tests/unit/` | `src/modules/<module>/` |
| 集成测试 | `tests/integration/` | `src/test/` |
| E2E 测试 | `tests/e2e/` | - |

### TDD 开发流程

1. **Red**: 先写测试，定义期望行为
2. **Green**: 写最少代码使测试通过
3. **Refactor**: 重构代码，保持测试通过

```bash
# 后端 TDD 循环
pytest tests/unit/test_new_module.py -v  # Red
# 编写实现代码
pytest tests/unit/test_new_module.py -v  # Green
# 重构
pytest tests/unit/test_new_module.py -v  # Verify

# 前端 TDD 循环
npx vitest run src/modules/new/feature.test.tsx  # Red
# 编写实现代码
npx vitest run src/modules/new/feature.test.tsx  # Green
```

---

## 注意事项

1. **测试数据库**：后端测试使用 `tmp_path` 临时数据库，不提交到 Git
2. **测试数据**：确保测试使用临时数据，测试完成后自动清理
3. **独立运行**：单元测试不依赖外部服务，集成测试自动 skip 不可用服务
4. **前端 jsdom 限制**：`getComputedStyle`、WebGL 等 jsdom 不支持的 API 已在 `setup.ts` 中 mock
5. **容器开发**：所有开发服务运行在 Podman 容器内，但测试可在宿主机直接运行

---

## 更新日志

### 2026-06-16
- 新建 `tests/unit/conftest.py` (auth_client, tmp_db_path, mock_llm_response)
- 新建 `tests/integration/conftest.py` (neo4j_available, opa_available, backend_available)
- 新建 `tests/e2e/conftest.py` (api_base_url, e2e_auth_token)
- 新建 `tests/helpers/` 共享工具包 (factories, api_client, storage)
- 新增 8 个 tools 模块测试 (analysis, computation, intelligence, operations, planning, policy, recommendation, task_management)
- 新增 `test_object_service.py` (75 个测试)
- 新增 `test_web_app.py` (32 个测试)
- 新建 `frontend/src/test/helpers/` (apiMock, storeTestUtils, renderWithProviders)
- 新增 6 个前端 Store 测试 (agent, audit, workspace, simulation, knowledge, auth)
- 新增 5 个前端 API 服务测试 (agent, ontology, simulation, business, knowledge)
- 新增 4 个前端组件测试 (LoginPage, WorkspaceSwitcher, IngestPanel, RoleManager)

### 2026-04-29
- 整理根目录 test_* 开头文件到 tests/
- 移动测试数据库到 tests/data/
- 建立测试文件管理文档
