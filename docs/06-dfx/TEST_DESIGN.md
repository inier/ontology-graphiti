# 测试设计文档 (Test Design)

> **版本**: 1.0.0 | **日期**: 2026-04-19
> **关联**: DFX_DESIGN.md §5.3, req-ok.md NFR-M02

---

## 1. 测试策略总览

### 1.1 测试金字塔

```
           ╱╲
          ╱E2E╲          ~5% — 关键用户流程端到端验证
         ╱──────╲
        ╱ 集成测试 ╲       ~15% — 模块间交互、外部依赖
       ╱────────────╲
      ╱   单元测试    ╲    ~80% — 模块内部逻辑、边界条件
     ╱──────────────────╲
```

### 1.2 覆盖率目标

| 层级 | 行覆盖率 | 分支覆盖率 | 工具 |
|------|---------|-----------|------|
| 单元测试 | > 80% | > 70% | pytest-cov |
| 集成测试 | 关键路径 100% | — | pytest + testcontainers |
| E2E 测试 | 核心流程 100% | — | Playwright |

### 1.3 质量门禁

| 门禁 | 条件 | 阶段 |
|------|------|------|
| 单元测试通过 | 覆盖率 > 80%，0 失败 | PR 合并前 |
| 集成测试通过 | 0 失败 | PR 合并前 |
| Lint 通过 | 0 error, 0 warning | PR 合并前 |
| 类型检查通过 | mypy/pyright 0 error | PR 合并前 |
| E2E 测试通过 | 核心流程通过 | 合并到 main 后 |
| 性能测试通过 | NFR-P 指标达标 | 发版前 |
| 安全扫描通过 | 无高危漏洞 | 发版前 |

---

## 2. 单元测试设计

### 2.1 按模块的测试要点

| 模块 | 测试重点 | Mock 策略 |
|------|---------|----------|
| **M-01 Graphiti** | 缓存命中/失效、连接池、查询构建、字段映射 | Mock Neo4j Driver |
| **M-02 OPA** | 策略编译、评估逻辑、缓存失效、Fail-Close | Mock OPA Server |
| **M-03 本体管理** | 实体验证、版本切换、回滚、约束校验 | Mock Neo4j + 内存存储 |
| **M-04 工作空间** | 创建/切换/删除、资源隔离、导入导出 | Mock Neo4j + 文件系统 |
| **M-05 Hook** | 注册/调度/优先级/错误传播/异步执行 | Mock Hook 实现 |
| **M-06 MCP** | 协议适配、数据转换、连接管理 | Mock MCP Server |
| **M-07 审计日志** | 事件记录、防篡改校验链、查询过滤 | Mock Channel |
| **M-08 Skill** | Skill 注册/执行/参数验证 | Mock LLM + ToolRegistry |
| **M-09 Swarm** | OODA 状态机、Agent 切换、故障恢复 | Mock Agent + Graphiti |
| **M-10 Agent** | 路由决策、ReAct 循环、自我纠正 | Mock LLM + ToolRegistry |
| **M-11 工具注册表** | 注册/发现/执行、权限校验、健康监控 | Mock OPA + Executor |
| **M-12 问答引擎** | 意图识别、检索编排、答案生成、溯源 | Mock LLM + Graphiti |
| **M-13 决策推荐** | 方案生成、风险评估、模拟集成 | Mock Simulator + LLM |
| **M-14 模拟推演** | 沙箱管理、版本管理、方案对比 | Mock Graphiti + Neo4j |
| **M-15 事件模拟器** | 事件生成、时间线引擎、触发器 | Mock Graphiti + Timeline |
| **M-16 API 网关** | 认证、限流、路由、权限 | Mock Auth + OPA |
| **M-17 Web 前端** | 组件渲染、交互逻辑、状态管理 | Jest + React Testing Library |
| **M-18 可视化** | 渲染逻辑、数据转换、LOD 策略 | Mock D3 + Canvas |

### 2.2 通用测试模式

```python
# 模式 1: 参数化边界测试
@pytest.mark.parametrize("input,expected", [
    ("normal_input", "expected_output"),
    ("", ValueError),                           # 空输入
    ("x" * 10000, ValueError),                  # 超长输入
    (None, TypeError),                           # None 输入
    ("unicode_输入_🎉", "expected_output"),       # Unicode
])

# 模式 2: 异步测试
@pytest.mark.asyncio
async def test_graphiti_search():
    client = GraphitiClient(mock_driver)
    result = await client.search("test query")
    assert len(result) > 0

# 模式 3: 状态机测试
class TestOODALoop:
    async def test_observe_to_orient(self): ...
    async def test_orient_to_decide(self): ...
    async def test_decide_to_act(self): ...
    async def test_invalid_transition(self): ...

# 模式 4: 并发测试
async def test_concurrent_workspace_switch():
    tasks = [workspace_manager.switch_workspace(id) for id in workspace_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, WorkspaceContext) for r in results)
```

---

## 3. 集成测试设计

### 3.1 测试环境

```yaml
# docker-compose.test.yml
services:
  neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/testpassword
    ports: ["7687:7687"]

  opa:
    image: openpolicyagent/opa:latest
    command: run --server /policies
    ports: ["8181:8181"]

  sut:
    build: .
    command: pytest tests/integration/
    depends_on: [neo4j, opa]
```

### 3.2 集成测试场景

| 场景 | 涉及模块 | 验证点 |
|------|---------|--------|
| 问答全链路 | M-16→M-12→M-01→M-07 | 问题到答案的完整流程 + 审计记录 |
| 工作空间切换 | M-04→M-01→M-02→M-08 | 切换后所有组件使用新上下文 |
| Agent OODA 闭环 | M-09→M-10→M-08→M-02 | 完整 OODA 循环 + OPA 校验 |
| 推演全流程 | M-15→M-14→M-01→M-13 | 事件生成→推演→决策推荐 |
| 权限校验链 | M-16→M-02→M-07 | 网关权限→服务权限→审计记录 |
| Hook 拦截 | M-05→M-07→M-02 | 操作触发 Hook→审计→权限校验 |
| 工具注册与执行 | M-08→M-11→M-02→M-07 | Skill 注册→发现→执行→权限→审计 |
| MCP 数据接入 | M-06→M-01→M-03 | 外部数据→转换→图谱写入→本体验证 |

### 3.3 Testcontainers 用法

```python
import pytest
from testcontainers.neo4j import Neo4jContainer
from testcontainers.core.container import DockerContainer

@pytest.fixture(scope="session")
def neo4j_driver():
    with Neo4jContainer("neo4j:5-community") as neo4j:
        driver = neo4j.get_driver()
        yield driver

@pytest.fixture(scope="session")
def opa_server():
    with DockerContainer("openpolicyagent/opa:latest") as opa:
        opa.with_command("run --server /policies")
        opa.with_exposed_ports(8181)
        opa.start()
        yield f"http://localhost:{opa.get_exposed_port(8181)}"
```

---

## 4. E2E 测试设计

### 4.1 核心用户流程

| 流程 ID | 流程名称 | 步骤 | 优先级 |
|---------|---------|------|--------|
| E2E-001 | 用户登录→问答 | 登录 → 问答页面 → 输入问题 → 验证答案 | P0 |
| E2E-002 | 图谱浏览 | 登录 → 图谱页面 → 搜索实体 → 点击节点 → 查看详情 | P0 |
| E2E-003 | 创建推演 | 登录 → 推演页面 → 创建场景 → 启动 → 注入事件 → 查看结果 | P0 |
| E2E-004 | 本体管理 | 登录 → 本体页面 → 创建实体 → 发布版本 → 对比版本 | P0 |
| E2E-005 | 审计溯源 | 登录 → 审计页面 → 过滤事件 → 查看详情 → 跳转图谱 | P1 |
| E2E-006 | 工作空间切换 | 登录 → 创建工作空间 → 切换 → 验证数据隔离 | P1 |

### 4.2 Playwright 示例

```typescript
// e2e/qa-flow.spec.ts
import { test, expect } from '@playwright/test';

test('E2E-001: User login and ask question', async ({ page }) => {
  // 登录
  await page.goto('/login');
  await page.fill('[data-testid="username"]', 'admin');
  await page.fill('[data-testid="password"]', 'admin123');
  await page.click('[data-testid="login-btn"]');
  await expect(page).toHaveURL('/');

  // 导航到问答
  await page.click('[data-testid="nav-qa"]');
  await expect(page).toHaveURL('/qa');

  // 提问
  await page.fill('[data-testid="qa-input"]', '东风21D的射程是多少？');
  await page.press('[data-testid="qa-input"]', 'Enter');

  // 验证答案（流式输出完成后）
  const answer = page.locator('[data-testid="qa-answer"]').last();
  await expect(answer).toBeVisible({ timeout: 10000 });
  await expect(answer).toContainText('1,500');

  // 验证来源标注
  const sourceAnnotation = page.locator('[data-testid="source-annotation"]').first();
  await expect(sourceAnnotation).toBeVisible();
});
```

---

## 5. 性能测试设计

### 5.1 Locust 测试场景

| 场景 | 并发数 | 持续时间 | 目标 |
|------|--------|---------|------|
| 问答压测 | 50 | 5 min | P95 < 3s |
| 图谱查询压测 | 100 | 5 min | P95 < 500ms |
| WebSocket 并发 | 200 | 10 min | 无断连 |
| 推演并发 | 10 | 30 min | 推演成功率 > 99% |

### 5.2 Locust 示例

```python
from locust import HttpUser, task, between

class ODAPUser(HttpUser):
    wait_time = between(1, 5)

    def on_start(self):
        # 登录获取 Token
        resp = self.client.post("/api/auth/login", json={
            "username": "test_user", "password": "test_pass"
        })
        self.token = resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def ask_question(self):
        self.client.post(
            "/api/qa/ask",
            json={"question": "当前态势如何？"},
            headers=self.headers,
        )

    @task(2)
    def search_graph(self):
        self.client.post(
            "/api/graph/search",
            json={"query": "东风21D", "limit": 10},
            headers=self.headers,
        )

    @task(1)
    def list_audit_events(self):
        self.client.get(
            "/api/audit/events?limit=20",
            headers=self.headers,
        )
```

---

## 6. 安全测试设计

### 6.1 测试场景

| 场景 | 验证点 | 工具 |
|------|--------|------|
| 认证绕过 | 未登录访问受保护 API | 手动 + 自动化 |
| 权限提升 | 普通用户访问管理员 API | OPA 策略测试 |
| 水平越权 | 用户 A 访问用户 B 的工作空间 | OPA 策略测试 |
| 注入攻击 | Cypher 注入、XSS | OWASP ZAP |
| 审计完整性 | 校验链防篡改 | 自动化脚本 |
| Fail-Close | OPA 不可达时行为 | Mock 测试 |

### 6.2 OPA 策略测试

```python
# tests/security/test_opa_policies.py
import pytest
from opa_client import OPAClient

@pytest.fixture
def opa():
    return OPAClient("http://localhost:8181")

class TestWorkspaceIsolation:
    async def test_user_cannot_access_other_workspace(self, opa):
        result = await opa.evaluate("gateway/allow", {
            "action": "workspace:read",
            "subject": {"id": "user_a", "roles": ["analyst"]},
            "resource": {"type": "workspace", "id": "workspace_b"},
        })
        assert result.allow == False

    async def test_admin_can_access_all_workspaces(self, opa):
        result = await opa.evaluate("gateway/allow", {
            "action": "workspace:read",
            "subject": {"id": "admin", "roles": ["admin"]},
            "resource": {"type": "workspace", "id": "workspace_b"},
        })
        assert result.allow == True
```

---

## 7. 测试数据管理

### 7.1 测试数据策略

| 类型 | 用途 | 来源 | 生命周期 |
|------|------|------|---------|
| 固定数据 | 单元测试 | 代码内嵌 | 测试用例 |
| 种子数据 | 集成测试 | JSON fixtures | 测试会话 |
| 生成数据 | 性能测试 | Factory 模式 | 测试会话 |
| 快照数据 | E2E 测试 | 生产脱敏 | 版本化 |

### 7.2 Fixture 管理

```
tests/
├── fixtures/
│   ├── ontologies/          # 本体定义
│   │   ├── military.json
│   │   └── finance.json
│   ├── policies/            # OPA 策略
│   │   ├── default.rego
│   │   └── workspace.rego
│   ├── events/              # 模拟事件
│   │   ├── basic_scenario.json
│   │   └── stress_test.json
│   └── users/               # 测试用户
│       ├── admin.json
│       ├── analyst.json
│       └── guest.json
├── conftest.py              # pytest 全局 fixtures
└── factories.py             # 数据工厂
```

---

## 8. CI/CD 集成

### 8.1 流水线

```yaml
# .github/workflows/test.yml
name: Test Pipeline

on: [push, pull_request]

jobs:
  unit-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/unit/ --cov=odap --cov-fail-under=80

  integration-test:
    runs-on: ubuntu-latest
    services:
      neo4j:
        image: neo4j:5-community
      opa:
        image: openpolicyagent/opa:latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/integration/

  e2e-test:
    runs-on: ubuntu-latest
    needs: [unit-test, integration-test]
    steps:
      - uses: actions/checkout@v4
      - run: npx playwright install
      - run: npx playwright test

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: bandit -r odap/
      - run: safety check
```

---

## 9. 测试指标与报告

| 指标 | 目标 | 采集方式 |
|------|------|---------|
| 单元测试覆盖率 | > 80% | pytest-cov |
| 集成测试通过率 | 100% | pytest |
| E2E 测试通过率 | > 95% | Playwright |
| 缺陷逃逸率 | < 5% | JIRA 统计 |
| 平均修复时间 | < 24h (P0) | JIRA 统计 |
| 测试执行时间 | < 10min (单元+集成) | CI 统计 |
