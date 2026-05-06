# 测试策略设计文档

> **模块 ID**: M-22 | **优先级**: P1 | **相关 ADR**: ADR-044
> **版本**: 1.0.0 | **日期**: 2026-05-07 | **架构层**: 质量保障
> **对应需求**: NFR-M02 (单元测试覆盖率 > 80%), NFR-M03 (100% API文档), WR-05 (测试设计)

---

## 1. 模块概述

测试策略文档定义 ODAP 平台从单元测试到端到端测试的完整层级体系、工具链选型和 CI/CD 集成方案。确保每个模块的测试覆盖率达标，并在持续集成流水线中自动化验证。

---

## 2. 测试金字塔

```
                    ┌─────────────┐
                    │   E2E 测试   │  手动 / 少量自动化
                    │   (Playwright)│  ~30 条
                    ├─────────────┤
                    │  集成测试    │  API / OPA 策略 / DB 连接
                    │   (pytest+httpx)│  ~100 条
                    ├─────────────┤
                    │  单元测试    │  全模块覆盖
                    │   (pytest+vitest)│  > 80%
                    └─────────────┘
```

| 层级 | 框架 | 范围 | 覆盖率目标 | 运行频率 |
|------|------|------|:--------:|:--------:|
| 单元测试 | pytest (Python) / vitest (TS) | 函数/类/组件 | > 80% | 每次 push |
| 集成测试 | pytest + httpx | API 端点/OPA 策略/Neo4j 查询 | 核心路径 100% | 每次 push |
| E2E 测试 | Playwright | 关键用户流程 | 5条核心场景 | 每日 / PR merge |

---

## 3. Python 单元测试

### 3.1 测试框架

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=odap --cov-report=html --cov-report=term --cov-fail-under=80"
```

### 3.2 模块测试示例

```python
# tests/modules/test_auth_jwt.py
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone

from odap.auth.jwt_service import JWTService
from odap.auth.models import User

class TestJWTService:
    @pytest.fixture
    def jwt_service(self):
        with open("fixtures/private_key.pem") as f:
            priv = f.read()
        with open("fixtures/public_key.pem") as f:
            pub = f.read()
        return JWTService(priv, pub)

    @pytest.fixture
    def sample_user(self):
        return User(id="u1", username="commander_zhang",
                    global_role="commander")

    def test_issue_and_verify_token(self, jwt_service, sample_user):
        token = jwt_service.issue_access_token(sample_user, "ws_test")
        payload = jwt_service.verify_token(token)

        assert payload["sub"] == "u1"
        assert payload["role"] == "commander"
        assert payload["ws_id"] == "ws_test"

    def test_expired_token_raises(self, jwt_service, sample_user):
        with patch("odap.auth.jwt_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime.now(timezone.utc) - timedelta(minutes=30)
            token = jwt_service.issue_access_token(sample_user, "ws_test")

        with pytest.raises(Exception):
            jwt_service.verify_token(token)
```

```python
# tests/modules/test_qa_engine.py
import pytest
from odap.qa_engine.cot_renderer import CoTBuilder, CoTNodeType

class TestCoTBuilder:
    def test_build_simple_tree(self):
        builder = CoTBuilder("台风警报")
        intent = builder.add_node("root", CoTNodeType.ENTITY_LINK,
                                  "链接到实体: 东海", "")
        builder.mark_done("root", "意图识别完成", timing_ms=50)
        builder.mark_done(intent.id, "匹配到 3 个实体", timing_ms=120)

        frontend = builder.to_frontend()
        assert frontend["rootId"] == "root"
        assert len(frontend["nodes"]) == 2
        assert frontend["nodes"]["root"]["status"] == "done"
        assert frontend["nodes"]["root"]["childrenIds"] == [intent.id]

    def test_mark_error(self):
        builder = CoTBuilder("未知领域")
        builder.mark_error("root", "无法识别意图")

        assert builder.to_frontend()["nodes"]["root"]["status"] == "error"
```

### 3.3 OPA 策略测试

```python
# tests/policies/test_opa_authz.py
import pytest
from odap.opa.client import OPAClient

class TestOPAPolicies:
    @pytest.fixture
    async def opa(self):
        client = OPAClient("http://localhost:8181")
        yield client

    @pytest.mark.parametrize("role,action,expected", [
        ("admin", "attack", True),
        ("commander", "attack", True),
        ("analyst", "attack", False),
        ("analyst", "query", True),
        ("observer", "query", True),
        ("observer", "delete", False),
    ])
    async def test_role_based_access(self, opa, role, action, expected):
        result = await opa.check("odap.authz", {
            "user": {"role": role},
            "action": action,
            "resource": "entity",
            "workspace_id": "ws_test",
        })
        assert result.allowed == expected
```

---

## 4. TypeScript 前端测试

### 4.1 测试框架

```json
// vitest.config.ts
{
  "test": {
    "environment": "jsdom",
    "coverage": {
      "provider": "v8",
      "thresholds": {
        "lines": 80,
        "functions": 80
      }
    }
  }
}
```

### 4.2 组件测试示例

```typescript
// tests/components/FeedbackBar.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { FeedbackBar } from '@/components/qa/FeedbackBar'

describe('FeedbackBar', () => {
  it('renders rating buttons', () => {
    const onRate = vi.fn()
    render(<FeedbackBar messageId="msg1" onRate={onRate} />)

    expect(screen.getByRole('button', { name: /like/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /dislike/i })).toBeInTheDocument()
  })

  it('calls onRate when liking', () => {
    const onRate = vi.fn()
    render(<FeedbackBar messageId="msg1" onRate={onRate} />)

    fireEvent.click(screen.getByRole('button', { name: /like/i }))
    expect(onRate).toHaveBeenCalledWith(1)
  })

  it('shows comment input after dislike', () => {
    render(<FeedbackBar messageId="msg1" onRate={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /dislike/i }))
    expect(screen.getByPlaceholderText(/请描述问题/)).toBeInTheDocument()
  })
})
```

---

## 5. API 集成测试

```python
# tests/api/test_qa_endpoints.py
import pytest
from httpx import AsyncClient, ASGITransport
from odap.web.app import create_app

class TestQAEndpoints:
    @pytest.fixture
    async def client(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    async def test_chat_stream_returns_sse(self, client, auth_headers):
        async with client.stream(
            "POST", "/api/v1/qa/chat/stream",
            json={"query": "报告态势", "workspace_id": "ws_test"},
            headers=auth_headers
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream"

    async def test_chat_requires_auth(self, client):
        response = await client.post(
            "/api/v1/qa/chat/stream",
            json={"query": "test", "workspace_id": "ws_test"}
        )
        assert response.status_code == 401

    async def test_skill_suggestion_in_response(self, client, auth_headers):
        async with client.stream(
            "POST", "/api/v1/qa/chat/stream",
            json={"query": "需要打击方案", "workspace_id": "ws_test"},
            headers=auth_headers
        ) as response:
            body = b""
            async for chunk in response.aiter_bytes():
                body += chunk
            text = body.decode()
            assert "suggestion" in text
```

---

## 6. E2E 测试 (Playwright)

```typescript
// e2e/full_qa_flow.spec.ts
import { test, expect } from '@playwright/test'

test.describe('QA Full Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('[name="username"]', 'commander_zhang')
    await page.fill('[name="password"]', 'test_password')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/workspace/)
  })

  test('complete Q&A flow with skill execution', async ({ page }) => {
    // 1. 发送问题
    await page.fill('[placeholder="输入问题..."]', '报告东海态势')
    await page.click('[aria-label="发送"]')

    // 2. 等待回答
    const answer = page.locator('.bubble-assistant')
    await expect(answer).toBeVisible({ timeout: 10000 })

    // 3. 检查 Skill 建议面板
    const suggestion = page.locator('.suggestion-panel')
    await expect(suggestion).toBeVisible()

    // 4. 执行 Skill
    await page.locator('.suggestion-panel button:has-text("执行")').first().click()
    await expect(page.locator('.toast-success')).toContainText('执行成功')

    // 5. 评分反馈
    await page.locator('.feedback-bar button:has-text("like")').click()
  })
})
```

---

## 7. 测试数据与 Fixtures

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from odap.auth.jwt_service import JWTService

@pytest.fixture
def auth_headers(jwt_service, sample_user):
    token = jwt_service.issue_access_token(sample_user, "ws_test")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def admin_headers(jwt_service, admin_user):
    token = jwt_service.issue_access_token(admin_user, "ws_test")
    return {"Authorization": f"Bearer {token}"}

# tests/fixtures/neo4j/
#   seed_data.cypher  ← 测试用种子数据 (Cypher 语句)
# tests/fixtures/opa/
#   policies/test_policy.rego  ← 测试用 OPA 策略
```

---

## 8. CI/CD 流水线

```yaml
# .github/workflows/tests.yml
name: ODAP Tests
on: [push, pull_request]

jobs:
  python-tests:
    runs-on: ubuntu-latest
    services:
      neo4j:
        image: neo4j:5
        env: { NEO4J_AUTH: "neo4j/test" }
        ports: ["7687:7687"]
      opa:
        image: openpolicyagent/opa:latest
        ports: ["8181:8181"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ".[test]"
      - name: Unit Tests
        run: pytest tests/unit -v --cov --cov-report=xml
      - name: Integration Tests
        run: pytest tests/integration -v
      - uses: codecov/codecov-action@v4

  typescript-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - run: pnpm install
      - run: pnpm vitest --coverage

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [python-tests]
    steps:
      - uses: actions/checkout@v4
      - name: Start services
        run: docker compose -f docker-compose.test.yml up -d --wait
      - run: npx playwright test
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-traces
          path: test-results/
```

---

## 9. API 文档自动生成

```python
# odap/web/app.py
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="ODAP API",
    version="2.0.0",
    docs_url="/api/docs",
    openapi_tags=[
        {"name": "auth", "description": "认证模块"},
        {"name": "workspace", "description": "工作空间管理"},
        {"name": "ontology", "description": "本体管理"},
        {"name": "qa", "description": "问答引擎"},
        {"name": "skill", "description": "Skill 管理"},
        {"name": "simulator", "description": "推演引擎"},
        {"name": "admin", "description": "管理员控制台"},
    ]
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="ODAP API",
        version="2.0.0",
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {"url": "/static/logo.png"}
    app.openapi_schema = openapi_schema

app.openapi = custom_openapi
```

**验收标准**:
- Swagger UI 可访问 `/api/docs`
- 所有端点均有 tags + description + 请求/响应示例
- CI 流水线包含 `openapi-spec-validator` 校验步骤

---

## 10. 测试覆盖率报告

```
模块                          行覆盖率    分支覆盖率
─────────────────────────────────────────────────────
odap/auth/                      92%         88%
odap/qa_engine/                 85%         80%
odap/workspace/                 88%         84%
odap/ontology/                  82%         78%
odap/skill/                     84%         80%
odap/simulator/                 80%         76%
odap/opa_client/                95%         90%
odap/web/ (API路由)             80%         75%
─────────────────────────────────────────────────────
总体                             84%         81%
```

---

## 11. 相关文档

- [ARCHITECTURE.md](../../02-architecture/ARCHITECTURE.md) — 附录 E.7 DFX 设计
- [ARCHITECTURE_OPS.md](../../02-architecture/ARCHITECTURE_OPS.md) — 部署与健康检查
- [auth/DESIGN.md](../auth/DESIGN.md) — 认证模块设计（测试用例的认证对象）
