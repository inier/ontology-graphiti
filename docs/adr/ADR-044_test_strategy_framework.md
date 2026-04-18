# ADR-044: 测试策略与框架

## 状态
已接受

## 上下文

ODAP Phase 4 需要建立系统化的测试体系，满足以下非功能需求：

- NFR-M02：测试覆盖率 > 80%（P0 模块）
- NFR-R01：推演成功率 > 99%
- NFR-M03：API 文档 100%
- 可维护性：模块间零循环依赖

### 测试维度

| 维度 | 需求 | 挑战 |
|------|------|------|
| 单元测试 | 行覆盖 > 80%，分支覆盖 > 70% | 外部依赖多（Neo4j、OPA、LLM） |
| 集成测试 | 关键路径 100% | 外部服务可用性、测试数据管理 |
| E2E 测试 | 核心流程 100% | 前后端协同、异步操作 |
| 契约测试 | 模块间接口兼容 | 接口变更频率高 |
| 性能测试 | P99 延迟基线 | 环境差异大 |

### 框架选型

| 层级 | 方案 A | 方案 B | 决策 |
|------|--------|--------|------|
| 单元测试 | pytest | unittest | pytest（生态丰富、fixture 强大） |
| Mock | unittest.mock + pytest-mock | respx + httpx | pytest-mock + respx（HTTP mock） |
| 集成测试 | testcontainers-python | 手动 Docker Compose | testcontainers（自动管理生命周期） |
| E2E 测试 | Playwright | Cypress | Playwright（Python + JS 双支持） |
| 契约测试 | Pact Python | 手动接口断言 | 手动接口断言（团队小，Pact 过重） |
| 性能测试 | Locust | k6 | Locust（Python 原生） |
| 覆盖率 | pytest-cov | coverage.py | pytest-cov（与 pytest 集成） |
| 类型检查 | mypy | pyright | mypy（社区标准） |

## 决策

### 测试金字塔

```
           ╱╲
          ╱E2E╲          ~5% — Playwright
         ╱──────╲
        ╱ 集成测试 ╲       ~15% — testcontainers + pytest
       ╱────────────╲
      ╱   单元测试    ╲    ~80% — pytest + pytest-mock
     ╱──────────────────╲
```

### 技术栈

| 类别 | 工具 | 版本约束 |
|------|------|---------|
| 测试框架 | pytest | ≥ 8.0 |
| Mock | pytest-mock + respx | — |
| 异步测试 | pytest-asyncio | ≥ 0.23 |
| 容器化测试 | testcontainers-python | ≥ 4.0 |
| E2E | Playwright | ≥ 1.40 |
| 性能 | Locust | ≥ 2.20 |
| 覆盖率 | pytest-cov | — |
| 类型检查 | mypy | — |
| Lint | ruff | ≥ 0.3 |

### 目录结构

```
odap/
├── tests/
│   ├── unit/                    # 单元测试（按模块）
│   │   ├── test_graphiti_client.py
│   │   ├── test_opa_manager.py
│   │   ├── test_ontology.py
│   │   └── ...
│   ├── integration/             # 集成测试
│   │   ├── conftest.py          # testcontainers fixtures
│   │   ├── test_graphiti_neo4j.py
│   │   ├── test_opa_integration.py
│   │   └── ...
│   ├── e2e/                     # 端到端测试
│   │   ├── test_qa_flow.py
│   │   ├── test_decision_flow.py
│   │   └── ...
│   ├── contract/                # 契约测试（接口断言）
│   │   ├── test_interface_compatibility.py
│   │   └── ...
│   └── conftest.py              # 公共 fixtures
frontend/
├── tests/
│   ├── unit/                    # Jest + React Testing Library
│   ├── e2e/                     # Playwright
│   └── setup.ts
```

### 质量门禁

| 阶段 | 门禁 | 条件 |
|------|------|------|
| PR 合并前 | 单元测试 | 覆盖率 > 80%，0 失败 |
| PR 合并前 | 集成测试 | 0 失败 |
| PR 合并前 | Lint + 类型 | 0 error |
| main 合并后 | E2E 测试 | 核心流程通过 |
| 发版前 | 性能测试 | P99 达标 |
| 发版前 | 安全扫描 | 无高危 |

### Mock 策略

| 外部依赖 | Mock 方式 | 集成测试 |
|----------|----------|---------|
| Neo4j | mock AsyncDriver | testcontainers Neo4j |
| OPA | mock OPA Server | testcontainers OPA |
| LLM API | respx HTTP mock | 可选：真实 API（标记 slow） |
| 文件系统 | tmp_path fixture | tmp_path |

## 后果

### 变得更容易

- **pytest 生态**：fixture、参数化、插件体系成熟
- **testcontainers**：自动管理 Neo4j/OPA 容器，测试环境一致性
- **Playwright**：前后端统一 E2E 测试

### 变得更难

- **测试维护**：18 个模块的测试代码量可能与业务代码相当
- **异步测试**：pytest-asyncio 的 fixture 生命周期管理有坑
- **LLM 测试**：LLM 输出不确定，需 snapshot + 语义等价判断

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| 测试代码膨胀 | 测试按模块独立、公共 fixture 复用、定期清理 |
| LLM 输出不确定 | 关键输出用 snapshot 测试、语义等价用 embedding 相似度 |
| testcontainers 慢 | 单元测试不依赖容器、集成测试并行化 |
| 前端 E2E 不稳定 | Playwright auto-wait + retry |

## 可逆性

**高**。测试框架替换成本主要是测试代码重写，但测试策略（金字塔、覆盖率目标、质量门禁）是稳定的，不随框架变化。

## 关联

- 关联 TEST_DESIGN.md（详细测试设计）
- 关联 req-ok.md NFR-M02（覆盖率 > 80%）
- 影响 WR-20（集成测试）
