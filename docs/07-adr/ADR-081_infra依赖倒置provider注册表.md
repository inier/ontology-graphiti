---
id: odap.l7.adr-081-infra依赖倒置provider注册表
status: active
owner: architect
version: ''
layer: L7
concern: adr
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
---

# ADR-081: infra→biz 依赖倒置 provider 注册表 seam（C4 Stage I 烧账机制）

## Status
**Accepted（2026-09-08：Stage I · C4 Group A 烧账，14 → 10；引入 infra provider 注册表作为跨层依赖倒置的架构级 seam）**

> 代码现实：新增 `odap/infra/providers.py`（infra 侧注册表，5 个 API）+ `odap/biz/providers_bootstrap.py`（biz 侧工厂注册，组合根导入即生效）。`infra.query` 三个 source 适配器（`ontology_source` / `sources/schema_source` / `sources/unstructured_source`）由「惰性 import biz」改为「`resolve_provider(name)`」。删除死函数 `infra/query/query_tools.py::register_query_tools`（全仓零消费者）。`cd apps/api && uv run lint-imports` 输出 `4 kept, 0 broken`，C4 `KEPT (10 ignored imports)`（`Analyzed 1359 files, 2393 deps`）。

## Context

ADR-080 Stage H 收官后，C4（`infra` 不得直接 import `biz`）棘轮停在 **14 条**存量边。这 14 条与前三批（删壳 / 类型下沉 / 模块整体迁移）不同——它们**无法靠物理搬迁或类型下沉消除**：

- `infra.query.*` 的 source 适配器（`ontology_source` / `schema_source` / `unstructured_source`）在运行期确实需要 biz 的 ontology 数据与检索器，但 `get_ontology_design_source` 等已从 `infra.query` 公共 API 导出、约 40 处 `QueryService` 消费者依赖其位置——**整体迁移到 biz 会破坏 infra.query 的公共契约**。
- `infra.openharness.engine_adapter`（4 边）有 infra 内部消费者，迁移会破坏 `infra.openharness` 内聚（ADR-080 §5 已判定为长期债）。

这些 source 适配器其实**早已是 DI-lite 形态**：构造函数接受可选注入协作者，未注入时**惰性 import biz 作为默认值**——正是这条「惰性 import biz 默认值」构成 C4 边。`infra/query` 甚至已有 `protocols.py`（Protocol 接口）+ `service.py::register_tool_source()` 的注册 seam 先例，佐证依赖倒置是本子系统的既定方向。

因此需要一条**架构级机制**：让 infra 组件在运行期取用 biz 协作者，而**静态导入图上不出现 infra→biz 边**。

## Decision

### 1. provider 注册表 seam（`odap/infra/providers.py`）

infra 侧持有一张 `name → factory` 注册表（`_PROVIDER_FACTORIES: dict[str, Callable[[], Any]]`），对外 5 个 API：

| API | 语义 |
|-----|------|
| `register_provider(name, factory)` | 注册工厂（`factory` 必须可调用，否则 `TypeError`） |
| `resolve_provider(name)` | 解析：调用工厂返回协作者实例；未注册抛 `RuntimeError`（规则 14） |
| `is_registered(name)` | 查询是否已注册 |
| `registered_names()` | 返回已注册名（排序 tuple），供诊断/测试 |
| `clear_providers()` | 清空注册表，供测试隔离 |

注册表**只依赖标准库 typing**，位于 infra 最底层，不 import 任何 biz——它本身对 C4 完全合规。方向依赖被彻底倒置：infra 定义「我需要一个叫 `oms_service` 的东西」，biz 决定「`oms_service` 就是 `get_oms_service()` 的返回」。

### 2. biz 侧工厂注册（`odap/biz/providers_bootstrap.py`）

biz→infra 是合法下行依赖（C4 放行）。该模块把 5 个 biz 服务工厂注册进 infra 注册表：

| provider name | 工厂返回 | 消费者（infra） |
|---------------|----------|-----------------|
| `oms_service` | `get_oms_service()` | `schema_source.SchemaSourceImpl` |
| `semantic_object_retriever` | `SemanticObjectRetriever()` | `unstructured_source` |
| `design_contract` | `get_design_contract()` | `ontology_source.OntologyDesignSource` |
| `action_storage` | `SQLiteActionStorage()` | `ontology_source.query_action_types` 降级源 |
| `ontology_storage` | `SQLiteOntologyStorage()` | `ontology_source.query_action_types` 降级源 |

每个工厂是**闭包，内部惰性 import 目标 biz 模块**——`bootstrap()` 注册本身零开销、不触发 biz 重载；真正的 biz 导入发生在 infra 组件首次 `resolve_provider(...)` 时（运行期，应用已启动）。模块末尾 `bootstrap()` 使「导入即注册」。

### 3. 组合根接线（3 处）

provider 注册必须在**任何查询执行前**完成，故在三个组合根模块加载期导入 `odap.biz.providers_bootstrap`（side-effect import，`# noqa: F401`）：

- `odap/web/app.py` —— 生产入口（端口 8000）
- `odap/web/api/app.py` —— 本地开发入口（端口 8765）
- `tests/conftest.py` —— 测试全局

### 4. source 适配器改造（DI-lite → provider-resolve）

三个 source 把「未注入协作者时惰性 import biz 默认值」改为「`resolve_provider(name)`」。**注入协作者仍然优先**（构造函数注入路径不变），故所有注入 mock 的既有测试无感。`ontology_source.__init__` 采用**可重试单例**：先 `resolve` 成功、再置 `_initialized = True`——解析失败时不污染初始化标志，允许后续重试。

### 5. 规则 14：显式失败，不静默兜底

`resolve_provider` 对未注册名抛 `RuntimeError`，错误信息指明「请确保组合根已导入 `odap.biz.providers_bootstrap`，或向该 source 显式注入协作者」。**禁止**任何「未注册时静默返回 None / 回退到硬编码默认实现」的兜底——组合根漏接线必须在启动/首次查询时**炸响**，而非静默降级产出错误结果。

## 备选方案与否决理由

- **物理迁移 source 到 biz**：否决。`get_ontology_design_source` 等已从 `infra.query` 公共 API 导出，约 40 处 `QueryService` 消费者依赖其位置，迁移破坏公共契约（与 ADR-080 §5 object_service「无 infra 外部消费者故可迁移」的情形相反）。
- **纯构造函数注入（不建注册表）**：否决。source 已有构造注入，但默认值路径仍需 import biz；不建注册表就无法在「未注入」时切断 biz 边。注册表把「默认值来源」从静态 import 倒置为运行期解析。
- **门面化 infra.query（仿 ontology public.py）**：否决。门面解决「外部 reach-in 内部」，不解决「infra 反向依赖 biz」；方向相反。

## Consequences

### 变得更容易

- **C4 边可烧而无需搬迁模块**：凡「infra 运行期需要 biz 协作者」的边，均可注册一个 provider 工厂消除静态边，模块留在原处、公共 API 不破。
- **新 source 接入成本低**：新增 infra source 需要 biz 协作者时，只需在 `providers_bootstrap` 加一个工厂 + 在 source 里 `resolve_provider`。
- **测试隔离友好**：`clear_providers()` + 注入协作者双路径，单测无需真实 biz。

### 变得困难 / 需注意

- **provider name 是字符串契约**：拼写错误不会在 import 期报错，而是首次 `resolve_provider` 时抛 `RuntimeError`。缓解：名字集中在 `providers_bootstrap.bootstrap()` 一处注册，消费者与注册者相邻可查；运行期 smoke 遍历 `registered_names()` 逐一解析。
- **组合根接线顺序**：注册必须先于查询执行。三处组合根均已接线；新增入口（如新 CLI）必须记得 import bootstrap，否则首查即 `RuntimeError`（这是刻意的显式失败）。
- **grimp 看不见运行期解析边**：`resolve_provider` 是运行期动态解析，静态图上 infra 不再指向 biz——这正是烧账原理，但也意味着「provider 是否真能解析出正确 biz 对象」不受契约保护，须靠运行期 smoke + 定向回归兜底。

### 顺带修正的存量缺陷

`_semantic_object_retriever_factory` 暴露并修正了一处**存量缺陷**：`SemanticObjectRetriever` 定义在 `biz/data/qa/semantic_retriever/retriever.py`，但包 `__init__.py` 未再导出该名。历史 `unstructured_source` 惰性 import 写的是包路径（`from ...semantic_retriever import SemanticObjectRetriever`），运行期恒 `ImportError` 被 try/except 吞成 warning——`.unstructured` 检索路径因此长期静默失效。工厂改按真实定义路径（`...semantic_retriever.retriever`）导入，使该 provider 可被真正解析。（注：`.unstructured` 端到端可用性还受 `service.py` 另一处 `_execute_unstructured` 未定义的存量缺陷影响，属独立问题，不在本 Stage 范围。）

## 验证（Stage I · Group A，2026-09-08）

| 验证 | 结果 |
|------|------|
| `lint-imports`（host） | `4 kept, 0 broken`；`Analyzed 1359 files, 2393 deps`；C4 `KEPT (10 ignored imports)`（14 → 10） |
| C4 精确测量 | Group A 烧 4 边：死函数 `register_query_tools`→`tool_registry`（1）+ 三 source `resolve_provider` 化（ontology_source/schema_source→`ontology.public`、unstructured_source→`qa.semantic_retriever`，3）→ **14 → 10** |
| 反向探针 | 向 `infra/providers.py` 注入 `from odap.biz.data.qa.models import *` → **C4 BROKEN（3 kept, 1 broken）**，精确捕获 `odap.infra.providers -> odap.biz.data.qa.models (l.75)`；删探针恢复 `4 kept, 0 broken` |
| 运行期 smoke | `import providers_bootstrap` 后 `registered_names()` 返回 5 名；逐一 `resolve_provider` → OMSService / SemanticObjectRetriever / DesignContractFacade / SQLiteActionStorage / SQLiteOntologyStorage 全部解析成功；未注册名抛 `RuntimeError`（规则 14） |
| 定向回归 | `test_query`(45) + `test_unstructured_source`(5) + `test_design_contract_integration`(7) + `test_object_service`(75) + `test_query_guard`(7) = **139 passed**；注入协作者路径不受影响 |
| 容器终验 | `graphiti-dev-app` restart 后 healthy；OpenAPI **755 paths / 957 ops**，与基线逐一相等（DI seam 零丢路由） |

**已知预存失败（与本 Stage 无关）**：`tests/unit/test_no_design_in_infra.py::test_simulation_fixture_present_in_infra` 因该文件 `ROOT = e:\...\ontology-graphiti\odap`（缺 `apps/api/` 前缀）指向不存在路径而失败——git 确认该文件本轮未修改，属既有失效守卫（其扫描因路径错误而空转），留作独立修复。

## 剩余 C4 债账（10 条，待后续 Stage）

| 分组 | 边数 | 烧账方向 |
|------|------|----------|
| `openharness.engine_adapter` | 4 | 依赖倒置（infra 内部消费者多，不可整体迁移；需 provider/装配注入） |
| `resilience.fault_tolerance` | 1 | 依赖倒置（`AgentState` 下沉不足以断边，`DomainSwarm` 惰性 import 仍存活） |
| `openharness.agui.retrieval_adapter` | 1 | provider 解析（同 Group A 模式） |
| `storage.scenario_store` | 2 | **缓烧**：模块级单例 import 时即构造，惰性 provider 解析有启动顺序脆弱性；需从组合根构造注入或整体迁移 |
| `queue.tasks` | 2 | 任务注册表注入（取 hyper_extract 适配器） |

## 相关

- **ADR-080**（core.ontology 门面封装与分层契约棘轮）：本 ADR 是其 C4 棘轮 Stage I 烧账所引入的依赖倒置机制，续接 Stage H 的 22→19→18→14。
- **ADR-055**（统一查询服务）：`infra.query` 的 source 适配器协议与注册 seam 是本机制的既有先例。
- 实施全记录：`workspace/outputs/core-ontology拆分迁移方案.md`（附录八 · Stage I）。
