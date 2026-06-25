# ODAP 自动化测试方案

> 本文档描述 ODAP 平台的完整自动化测试体系，包括测试分层、运行方式、覆盖目标与质量门禁。

---

## 一、测试分层架构

ODAP 采用经典的"测试金字塔"分层策略，覆盖后端（Python/FastAPI）与前端（React 19/TypeScript）。

```
                    ┌──────────┐
                    │   E2E    │  6 文件 — 全链路用户工作流（需后端运行）
                   ┌┴──────────┴┐
                   │ Integration │  13 文件 — 跨模块集成（需 Neo4j/OPA 等外部服务）
                  ┌┴────────────┴┐
                  │    Perf       │  1 文件 — 性能基准（缓存/熔断/查询时延）
                 ┌┴──────────────┴┐
                 │     Unit        │  140+ 文件 — 单元测试（storage/service/routes/models）
                └──────────────────┘
                 后端 5434+ 测试   前端 27 文件 500+ 测试
```

### 1.1 后端测试分层

| 层级 | 目录 | 数量 | 职责 | 外部依赖 |
|------|------|------|------|---------|
| **单元测试** | `tests/unit/` | 140+ 文件 / 5434+ 用例 | storage/service/routes/models/impl 单层验证 | 无 |
| **集成测试** | `tests/integration/` | 13 文件 | 跨模块联动、API 端点、外部服务接入 | Neo4j/OPA/后端 |
| **E2E 测试** | `tests/e2e/` | 6 文件 | 完整用户工作流（登录→创建→问答→仿真） | 后端运行 |
| **性能测试** | `tests/perf/` | 1 文件 | 缓存命中率、熔断恢复、查询时延基准 | 无（mock） |

### 1.2 前端测试分层

| 类型 | 工具 | 覆盖模块 | 示例 |
|------|------|---------|------|
| **Store 测试** | Zustand + vitest | 8 个模块 | `agentStore.test.ts` |
| **API 服务测试** | `vi.spyOn(fetch)` | 5 个模块 | `agentApi.test.ts` |
| **组件测试** | `@testing-library/react` | 11 个组件 | `LoginPage.test.tsx` |
| **Hook 测试** | `renderHook` | AGUI | `useAGUI.test.tsx` |

---

## 二、测试模式与运行

### 2.1 统一测试运行器

通过 `run_tests.py` 统一入口运行所有测试，支持 9 种模式：

```bash
# 冒烟测试（核心功能快速验证，<60s）—— 提交前/部署后必跑
python run_tests.py smoke

# 后端单元测试（默认全量）
python run_tests.py unit

# 回归测试（核心业务路径，标记 @pytest.mark.regression）
python run_tests.py regression

# 集成测试（需 Neo4j/OPA 等外部服务）
python run_tests.py integration

# 端到端测试（需后端运行）
python run_tests.py e2e

# 性能基准测试
python run_tests.py perf

# 前端测试
python run_tests.py frontend

# 全量测试（unit + frontend）
python run_tests.py full

# 全部测试（unit + integration + e2e + perf + frontend）
python run_tests.py all
```

### 2.2 常用选项

| 选项 | 说明 |
|------|------|
| `--no-coverage` | 跳过覆盖率统计（加速） |
| `--no-html` | 跳过 HTML 报告生成 |
| `--no-junit-xml` | 跳过 JUnit XML 报告 |
| `--parallel N` | 并行进程数（需 pytest-xdist） |
| `--keep-going` | 失败后继续运行后续阶段 |

### 2.3 直接运行（绕过运行器）

```bash
# 后端单元测试
python -m pytest tests/unit/ -v

# 仅冒烟测试
python -m pytest -m smoke tests/

# 仅回归测试
python -m pytest -m regression tests/unit/

# 带覆盖率
python -m pytest --cov=odap tests/unit/

# 前端测试
cd frontend && npm test
```

### 2.4 测试报告

运行后报告输出到 `test-reports/` 目录：

| 文件 | 说明 |
|------|------|
| `report.html` | HTML 可视化报告（含阶段明细、状态卡片、失败输出） |
| `report.json` | JSON 报告（便于 CI 解析） |
| `junit-{mode}.xml` | JUnit XML 报告（CI 集成用） |
| `coverage-{mode}.xml` | Cobertura XML 覆盖率报告 |
| `coverage-{mode}-html/` | HTML 覆盖率详情 |

---

## 三、测试标记体系

在 `pyproject.toml` 中注册的 pytest 标记：

| 标记 | 用途 | 运行命令 |
|------|------|---------|
| `@pytest.mark.smoke` | 冒烟测试（核心功能，<60s） | `pytest -m smoke` |
| `@pytest.mark.unit` | 单元测试 | `pytest -m unit` |
| `@pytest.mark.regression` | 回归测试（核心业务路径） | `pytest -m regression` |
| `@pytest.mark.integration` | 集成测试（需外部服务） | `pytest -m integration` |
| `@pytest.mark.e2e` | 端到端测试 | `pytest -m e2e` |
| `@pytest.mark.slow` | 慢速测试 | `pytest -m slow` |
| `@pytest.mark.perf` | 性能基准测试 | `pytest -m perf` |
| `@pytest.mark.docker` | 需要 Docker/Podman 容器 | `pytest -m docker` |

> 启用 `--strict-markers`，未注册的标记会报错，防止拼写错误。

---

## 四、测试编写规范

### 4.1 后端分层测试要求（AGENTS.md 规则）

| 层 | 必测场景 | 工具 |
|---|---------|------|
| **storage/** | CRUD 全流程、get 不存在返回 None、JSON 序列化、非法 JSON 容错 | `tmp_path` 真实 DB |
| **models/** | 必填字段验证、默认值、容器字段 `default_factory`、Enum 值 | Pydantic 验证 |
| **services/** | 成功返回扁平 dict、错误返回 `{"status": "error"}`、类型转换 | mock storage |
| **routes/** | HTTP 状态码映射、`except HTTPException: raise` 透传、404/400/500 | `TestClient` + `dependency_overrides` |

### 4.2 关键硬性规则

1. **SQLite 存储测试用 `tmp_path` 真实 DB**，禁止 MagicMock 模拟数据库
2. **服务层不抛 HTTPException**，返回 `{"status": "error", "message": "..."}`
3. **路由层必须 `except HTTPException: raise`** 透传，防止被 500 兜底吞掉
4. **Enum 必须 `(str, Enum)`** 双继承
5. **容器字段必须 `Field(default_factory=...)`**
6. **新增模块必须同步新增测试文件**

### 4.3 共享测试工具

| 工具 | 路径 | 用途 |
|------|------|------|
| 工厂函数 | `tests/helpers/factories.py` | `make_ontology`/`make_workspace`/`make_agent` 等 |
| TestClient 辅助 | `tests/helpers/api_client.py` | `create_auth_client` 创建认证客户端 |
| 存储测试基类 | `tests/helpers/storage.py` | `StorageTestBase` 处理 tmp_path DB |
| 全局 fixtures | `tests/conftest.py` | `mock_sqlite`/`temp_db`/`tool_registry`/`skill_registry` |
| 单元 fixtures | `tests/unit/conftest.py` | `auth_client`/`tmp_db_path`/`mock_llm_response` |

### 4.4 前端测试规范

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

## 五、测试覆盖现状

### 5.1 后端覆盖（按业务领域）

| 领域 | 模块数 | 已测模块 | 覆盖率 |
|------|--------|---------|--------|
| core/ontology | 15 子模块 | 15 | 100% |
| core/agent | 3 | 3 | 100% |
| core/cognition | 1 | 1 | 100% |
| decision | 3 | 3 | 100% |
| integration | 3 | 3 | 100% |
| platform | 9 | 9 | 100% |
| data | 8 | 8 | 100% |
| simulation | 5 | 5 | 100% |
| management | 2 | 2 | 100% |
| infra | 14 | 14 | 100% |

### 5.2 前端覆盖（按模块）

| 模块 | Store | API | 组件 |
|------|-------|-----|------|
| shared | ✅ authStore | — | ✅ LoginPage/StatCard/PageHeader/QAPanel/ToolHealthIndicator/GraphControls/GraphToolbar |
| agent | ✅ agentStore | ✅ agentApi | — |
| ontology | ✅ blueprintStore | ✅ ontologyApi | ✅ OntologyBuildProgress |
| qa | — | — | ✅ AGUIProvider/useAGUI |
| simulation | ✅ simulationStore | ✅ simulationApi | — |
| knowledge | ✅ knowledgeStore | ✅ knowledgeApi | — |
| workspace | ✅ workspaceStore | — | ✅ WorkspaceSwitcher |
| ingest | — | — | ✅ IngestPanel |
| roles | — | — | ✅ RoleManager |
| business | — | ✅ businessApi | — |
| audit | ✅ auditStore | — | — |

### 5.3 架构守护测试

| 守护规则 | 测试文件 |
|---------|---------|
| 路由异常透传 | `test_route_exception_handling.py` |
| 静默 except 捕获 | `test_silent_except_handling.py` |
| Pydantic 可变默认值 | `test_pydantic_mutable_defaults.py` |
| 架构边界（biz 不依赖 infra 设计） | `test_architecture_boundary.py` |
| 无硬编码密钥 | `test_no_hardcoded_secrets.py` |
| 函数长度限制 | `test_function_length.py` |
| 宪法合规 | `test_constitution_compliance.py` |

---

## 六、质量门禁

### 6.1 提交前门禁（本地）

```bash
# 1. 冒烟测试必须通过（<60s）
python run_tests.py smoke --no-coverage

# 2. 后端 lint
ruff check .

# 3. 前端 lint + typecheck
cd frontend && npm run lint && npm run typecheck
```

### 6.2 CI 门禁

| 阶段 | 命令 | 失败处理 |
|------|------|---------|
| Lint | `ruff check .` + `cd frontend && npm run lint` | 阻断 |
| 单元测试 | `python run_tests.py unit` | 阻断 |
| 前端测试 | `python run_tests.py frontend` | 阻断 |
| 覆盖率 | `pytest --cov=odap --cov-fail-under=70` | 阈值告警 |
| 集成测试 | `python run_tests.py integration` | 非阻断（仅告警） |

### 6.3 发布前门禁

```bash
# 全量测试（含集成/E2E/性能）
python run_tests.py all --keep-going
```

---

## 七、测试目录结构

```
tests/
├── TEST_PLAN.md                  # 本文档
├── README.md                     # 测试体系说明
├── __init__.py
├── conftest.py                   # 全局 fixtures
├── helpers/                      # 共享测试工具
│   ├── factories.py              #   工厂函数
│   ├── api_client.py             #   TestClient 辅助
│   └── storage.py                #   存储测试基类
├── unit/                         # 单元测试（140+ 文件）
│   ├── conftest.py               #   auth_client/tmp_db_path/mock_llm_response
│   ├── test_smoke.py             #   ⭐ 冒烟测试（11 用例，<60s）
│   ├── test_agent_api_routes.py  #   ⭐ Agent API 路由层（17 用例）
│   ├── test_cognition_api_routes.py # ⭐ Cognition API 路由层（17 用例）
│   ├── test_logging.py           #   ⭐ infra/logging 模块（22 用例）
│   └── ...                       #   其他 140+ 测试文件
├── integration/                  # 集成测试（13 文件）
│   └── conftest.py               #   neo4j_available/opa_available/backend_available
├── e2e/                          # 端到端测试（6 文件）
│   └── conftest.py               #   api_base_url/e2e_auth_token
└── perf/                         # 性能测试（1 文件）

test-reports/                     # 测试报告输出（运行后生成）
├── report.html                   #   HTML 可视化报告
├── report.json                   #   JSON 报告
├── junit-{mode}.xml              #   JUnit XML
└── coverage-{mode}-html/         #   HTML 覆盖率

run_tests.py                      # ⭐ 统一测试运行器
```

---

## 八、TDD 开发流程

### 8.1 Red-Green-Refactor

```bash
# 1. Red: 先写测试，定义期望行为
python -m pytest tests/unit/test_new_module.py -v  # 失败

# 2. Green: 写最少代码使测试通过
python -m pytest tests/unit/test_new_module.py -v  # 通过

# 3. Refactor: 重构代码，保持测试通过
python -m pytest tests/unit/test_new_module.py -v  # 仍通过
```

### 8.2 新增模块测试清单

新增 `odap/biz/{领域}/{模块}/` 时必须同步：

- [ ] `tests/unit/test_{模块}.py` 测试文件
- [ ] storage 层：CRUD + JSON 序列化 + 不存在返回 None
- [ ] models 层：必填字段 + 默认值 + `default_factory` + Enum
- [ ] services 层：成功返回 dict + 错误返回 `{"status": "error"}`
- [ ] routes 层：HTTP 状态码 + `except HTTPException: raise`
- [ ] 在 `odap/web/app.py` 注册路由后，补充路由注册测试

---

## 九、已知测试缺口与改进计划

### 9.1 已识别缺口（按优先级）

| 优先级 | 缺口模块 | 状态 | 备注 |
|--------|---------|------|------|
| 高 | Agent API 路由层 | ✅ 已补 | test_agent_api_routes.py |
| 高 | Cognition API 与服务层 | ✅ 已补 | test_cognition_api_routes.py |
| 高 | infra/logging 结构化日志 | ✅ 已补 | test_logging.py |
| 中-高 | QA 语义检索/向量检索 | 待补 | semantic_retriever/vector_retriever |
| 中-高 | 文档摄入处理器（PDF/Word/OCR） | 待补 | design/ingestion/ |
| 中 | 前端 system 模块 | 待补 | SkillManagement 等 |
| 中 | 前端 settings/config/version | 待补 | 5 个模块零测试 |
| 中-低 | 前端核心业务组件层 | 待补 | ontology/qa/business 组件 |

### 9.2 持续改进方向

1. **覆盖率阈值**：逐步提升 `--cov-fail-under` 阈值至 80%
2. **回归测试集**：为核心业务路径标注 `@pytest.mark.regression`
3. **契约测试**：引入 OpenAPI schema 验证，确保 API 契约一致
4. **突变测试**：引入 mutmut 验证测试有效性
5. **可视化 dashboard**：集成 Allure 或 ReportPortal 展示历史趋势

---

## 十、更新日志

### 2026-06-19
- 新建统一测试运行器 `run_tests.py`（9 种模式 + HTML/JSON/JUnit 报告）
- 新建冒烟测试套件 `tests/unit/test_smoke.py`（11 用例，<60s）
- 新建 Agent API 路由测试 `tests/unit/test_agent_api_routes.py`（17 用例）
- 新建 Cognition API 路由测试 `tests/unit/test_cognition_api_routes.py`（17 用例）
- 新建 infra/logging 测试 `tests/unit/test_logging.py`（22 用例）
- 注册 `smoke`/`regression`/`perf`/`docker` 标记，启用 `--strict-markers`
- 编写本测试方案文档
