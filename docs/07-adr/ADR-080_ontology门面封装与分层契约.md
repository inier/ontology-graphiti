# ADR-080: core.ontology 门面封装与 import-linter 分层契约棘轮

## Status
**Accepted（2026-09-06：Stage A–G 三条契约零债账全严格；2026-09-07 Stage H 补第四条契约 C4 守卫 infra 下层边界，并续烧 C4 存量债账 22→19→14；2026-09-08 Stage I 引入 provider 注册表依赖倒置 seam 续烧 C4 14→10，见 ADR-081；2026-09-11 Stage J 把 `lint-imports` 接成 CI 阻塞门禁，此前 § 2 宣称的「CI 守卫」只有手工命令、无任何 workflow 调用，见 § 6）**

> 代码现实：`biz/core/ontology/public.py`（77 符号惰性门面）+ `public_routers.py`（31 路由惰性门面）已实现；`apps/api/pyproject.toml` 的 `[tool.importlinter]` 四条契约 C1/C2/C3/C4 全部 KEPT。C1/C2/C3 `ignore_imports` 清零（零债账全严格），C4 挂 10 条 infra→biz 存量债账（棘轮，只减不增；初始 22 条经 Tier1 删壳→19、Tier3 类型下沉→18、Tier2 object_service 迁移→14，Stage I 依赖倒置 Group A→10）。`cd apps/api && uv run lint-imports` 输出 `4 kept, 0 broken`（Stage J 实测 `Analyzed 1360 files, 2380 deps`）；该命令同时是 `ci.yml` / `quality-gate.yml` 的阻塞步骤（§ 6），不再仅靠人工执行。

## Context

ADR-068 将本体模块重组为 3+1 分层架构（Design → Construction → +Reasoning → Application），并在其代码审查中预判：「现有 120+ 跨模块 import 可通过 `__getattr__` 兼容层平滑迁移；24 个路由可保留在原地（薄壳模式）」。本 ADR 记录该迁移策略的**具体实现形态**与**防回退的 CI 守卫机制**。

重组后 `odap/biz/core/ontology/` 膨胀到 540 个 `.py` 文件、22 个顶级子目录。外部（其它 biz 域 / infra / tools / web）存在约 162 处直接伸进内部实现（`design.*` / `construction.*` / `application.*` / `reasoning.*` 的 `impl` / `storage` / `services` 深层路径）的 reach-in 导入。后果：ontology 内部任何重构（改名、移动、拆分）都会打断散落全仓的外部消费者，使 ADR-068 的分层边界形同虚设——层与层之间没有强制的 import 纪律，只有文档约定。

同时全仓存在跨层反向依赖：`common`（本应是叶子层）反向 import `biz`；`biz` / `infra`（下层）反向 reach-up `web`（顶层）取用 `event_bus` / `response_models` / `emit_build_progress` 等本应属于下层的共享设施；`infra`（本应在 `biz` 之下）反向 reach-up `biz` 取用 ontology/query/tool/session 等上层服务（原诊断粗测 "24+ 条"，Stage H 经 grimp 精确复测为 22 条直接边）。这些边让「common 是叶子、infra 在 biz 之下、web 是顶层」的分层意图无法被机器验证。

## Decision

### 1. 双门面封装 core.ontology（PEP 562 惰性 `__getattr__`）

为 core.ontology 提供**唯一稳定的对外 API 面**，两个姊妹模块：

- **`public.py`** —— 类型/服务/存储符号门面。`_PUBLIC_MAP: dict[str, tuple[str, str]]`（符号名 → (真实内部模块路径, 模块内属性名)）映射 77 个对外符号。外部一律 `from odap.biz.core.ontology.public import OntologyService, get_oms_service`，禁止 reach-in 内部实现路径。
- **`public_routers.py`** —— 路由门面。因 31 个 ontology 路由模块里的对象**全叫 `router`**（同名键无法共存于单一 `_PUBLIC_MAP`），单独建姊妹模块，用 `_ROUTER_MAP` 把 31 个同名 `router` 拍平成 31 个异名公共别名（`oms_router` / `action_type_router` / …），供 `web.router_registry` 与 `web.api.app` 集中消费。

两模块均采用 **PEP 562 模块级 `__getattr__` + `importlib.import_module`** 惰性解析：`import ...ontology.public` 本身零级联开销，不会把 540 文件的 ontology 包拖进 import-time，也规避循环导入。`TYPE_CHECKING` 块为 IDE / 类型检查器提供静态可见性。内部重构时只需维护这两张映射表，外部消费者与 CI 无感。

### 2. import-linter 四条 forbidden 契约（棘轮 ratchet 模式）

在 `apps/api/pyproject.toml` 的 `[tool.importlinter]` 定义四条 `forbidden` 契约，把 ADR-068 的分层意图固化为机器可验证的守卫。grimp 纯 AST 静态分析，host `.venv` 即可运行（`cd apps/api && uv run lint-imports`），不需 DB / OPA / 容器。**注意：契约定义（本 Stage）与门禁接线（§ 6，Stage J）是两件事**——本节只让契约可被人工执行，直到 Stage J 才有 workflow 真正调用它：

| 契约 | 语义 | source → forbidden | 关键开关 |
|------|------|--------------------|----------|
| **C1** | common 是叶子层 | `odap.common` → `biz`/`infra`/`web` | 无 |
| **C2** | web 是顶层 | `odap.biz`/`odap.infra` → `odap.web` | 无 |
| **C3** | ontology 内部只能经门面访问 | 12 个非 ontology biz 子域 + infra + tools + web → 22 个 ontology 深层子包 | `allow_indirect_imports=true`；source 排除 ontology 自身（内部边不算违规）；forbidden 排除 `.public` / `.public_routers` / 包根 |
| **C4** | infra 在 biz 之下 | `odap.infra` → `odap.biz` | `allow_indirect_imports=true`（只禁**直接** infra→biz 边；放行经 `odap.tools` Skill 层的间接可达性，见 § 5）；10 条存量边挂 `ignore_imports` 棘轮（初始 22，Stage H 续烧至 14，Stage I 依赖倒置至 10） |

**棘轮模式**：`ignore_imports` 是只减不增的债账。落地初期允许存量违规挂在 `ignore_imports`  grandfather 条款下使契约即绿，随后逐条**物理修复 + 从 ignore 删除**（烧账），直至清零。清零后契约变为**完全严格**——任何未来新增违规立即 FAIL，无 grandfather 条款。

### 3. 跨层共享设施下沉到合法层（C2 烧账）

C2 的 10 条存量债按被 reach-up 的 web 符号分三类，全部下沉到其真实归属层，而非用 ignore 假装通过：

- `web.ws.event_bus`（5 边）：本就是 `infra.events.event_bus` 的 8 行兼容 shim，消费者直接改指 canonical infra。
- `web.api.response_models.DictResponse`（3 边）：纯 pydantic 共享 schema，下沉到 common 叶子层 `odap.common.response_models`。
- `web.ws.routes.emit_build_progress`（2 边）：只依赖 `infra.events.event_bus`、与 web 零耦合，属"工具函数放错层"，逐字下沉到 `odap.infra.events.build_progress`。

旧 web 路径一律保留为**向后兼容再导出 shim**（web→common / web→infra 均为向下依赖，C2 放行），历史调用点不破。

### 4. 命名空间包盲区修复（grimp 覆盖前提）

grimp 要求 `__init__.py` 链条完整才能看见一个包。ODAP 有 7 个隐式 PEP 420 命名空间包（无 `__init__.py`），导致整棵子树对 grimp 不可见（最大者 `ontology/design/` 123 模块）。补纯 docstring `__init__.py`（无 eager 导入，避免循环）修复，使磁盘模块数 == grimp 可见模块数（1355==1355，盲区 0）。**教训**：反向测试（注入探针）是发现盲区的唯一手段——只跑 KEPT 会假绿；审计脚本必须用差集反查（disk_modules − grimp.modules）而非过滤正查。

### 5. C4 守卫 infra 下层边界（Stage H，2026-09-07）

C1/C2/C3 就位后，分层拼图缺最后一块：守卫 `infra` 不得向上依赖 `biz`。用 grimp 精确复测 infra→biz 直接边得 **22 条**（原诊断粗测 "24+"），分三 tier：

- **Tier1 · vestigial shim（3 边，Stage H 当场烧账 → 22 降 19）**：`infra/graph/thought_routes.py` 是死模块（全仓零消费者，`router_registry.py:142` 早已直接从 biz canonical 导入 thought_router）；`infra/graph/thought_graph.py` 是纯透传壳，仅 `tests/unit/test_thought_graph.py` 消费。二者 canonical 实现均在 `biz.core.cognition.thought_graph`。删除两壳 + 把 9 处测试导入重接到 biz canonical（`.models.types` / `.services.thought_graph_service`），消除 3 条边。
- **Tier2 · 错放模块（10 边；其中 object_service 4 边已于 Stage H 续烧迁移，剩 6 边待整体迁移）**：`infra.object_service`（编排 4 个 biz service 的应用级聚合器，**已迁 `biz.data.object_service`**，见下方续烧）、`infra.openharness.engine_adapter`（装配 biz 插件/config/session 的集成编排）、`infra.resilience.fault_tolerance`（包裹 swarm_orchestrator）、`infra.openharness.agui.retrieval_adapter`（经门面取检索）。这些模块本质属 biz / biz.integration，误置于 infra，烧账方向是**整体迁移**而非删导入。
- **Tier3 · 真实向上取数（9 边；其中 PermissionScope 1 边已于 Stage H 续烧下沉，query source 3 边已于 Stage I 依赖倒置烧账，剩 5 边需依赖倒置，长期债）**：`infra.query.*`（**Stage I 已烧 3 边**：`ontology_source` / `sources/schema_source` / `sources/unstructured_source` 改经 `odap.infra.providers` 注册表解析 biz 协作者，见 ADR-081）、`infra.storage.scenario_store` 需 ontology 数据（多经 `public` 门面，卫生较好；模块级单例缓烧）、`infra.opa.opa_service` module-level 导入 `PermissionScope` 类型（**已下沉 common**，见下方续烧）、`infra.queue.tasks` 取 hyper_extract 适配器（应任务注册表注入）。

**关键开关 `allow_indirect_imports=true`**：实测发现 infra 经 `odap.tools`（领域 Skill 层，独立顶级包）**间接**触达 biz（`engine_adapter`/`tool_adapter`/`fault_tolerance` → `odap.tools` → `tools.{base,query.nl_query_skills,web.web_skills}` → biz）。默认 forbidden 会把这些多跳链判违规，但 `infra→tools`、`tools→biz` 各是独立边（tools 作为 Skill 层使用 biz 服务属其本职），不应由 C4 承担。故 C4 语义收敛为「任何 infra 模块不得**直接** import biz 模块」，与 C3 的 `allow_indirect_imports` 用法一致。tools 层的间接可达性留作独立技术债。

C4 落地即挂 19 条存量边于 `ignore_imports`（棘轮，只减不增），今日即绿；任何新增 infra→biz 直接边立即 FAIL。

**Stage H 续烧（同日，19 → 14）**：契约落地后当轮继续烧账，消除 5 条 Tier2/Tier3 边。

- **Tier3 · PermissionScope 类型下沉（1 边，19→18）**：`infra.opa.opa_service` module-level 导入 `biz.platform.roles.api.schemas.PermissionScope`——纯类型依赖，无需依赖倒置，直接下沉到 common 叶子层。新建 `odap/common/permission_scope.py` 承载 `PermissionScope(str, Enum)`，`common/__init__.py` 导出；`biz.platform.roles.api.schemas` 保留向后兼容再导出（内部消费者 routes/storage/tests 无需改导入）；`opa_service.py:29` 改从 common 导入。
- **Tier2 · object_service 整体迁移（4 边，18→14）**：`infra.object_service` 是编排 ontology/business/agent/kb 四源的**应用级聚合器**，本质属 biz 且无 infra 外部消费者，故整体迁移（非删导入）。`git mv infra/object_service → biz/data/object_service`（4 文件），5 处消费者换源：`biz.data.qa.semantic_retriever.retriever`（2）、`web.router_registry`、`web.api.app`、`tests/unit/test_object_service.py` + `test_pydantic_mutable_defaults.py`。
- **Tier2 · engine_adapter 不可迁移判定**：`infra.openharness.engine_adapter` 虽有 4 条 biz 边，但存在 infra 内部消费者（`openharness/__init__.py`、`tool_adapter`、`skill_adapter`、`agui_handler`），整体迁移会连带破坏 infra.openharness 内聚——判定为**需依赖倒置（provider 注入）的长期债**，本轮不烧。

**Stage I 续烧（2026-09-08，14 → 10）**：引入 infra provider 注册表依赖倒置 seam（ADR-081），消除 Group A 的 4 条边——删死函数 `register_query_tools`（`query_tools`→`tool_registry`，1 边）+ 三个 query source 适配器改经 `odap.infra.providers` 注册表解析 biz 协作者（`ontology_source`/`schema_source`→`ontology.public`、`unstructured_source`→`qa.semantic_retriever`，3 边）。source 模块留在原处、`infra.query` 公共 API 不破（约 40 处 `QueryService` 消费者无感）。

剩余 10 条 C4 边全部需依赖倒置重构（provider 接口注入 / 任务注册表注入 / 装配注入），非简单迁移或类型下沉可解：`engine_adapter`(4) + `fault_tolerance`(1) + `agui.retrieval_adapter`(1) + `scenario_store`(2，模块级单例缓烧) + `queue.tasks`(2)，留作后续 Stage 逐步烧至零（详见 ADR-081「剩余 C4 债账」表）。

### 6. CI 门禁接线（Stage J，2026-09-11）

§ 2 把四条契约称为「机器可验证的 CI 守卫」，Consequences 也宣称「任何新增违规在 `lint-imports` 立即 FAIL」——但落地时只写了手工命令 `cd apps/api && uv run lint-imports`，**全仓没有任何 workflow 调用过它**。即 C1–C4 在 Stage A–I 期间完全依赖人工自觉：契约本身零债账、状态健康，却对回归没有任何拦截力，一次 reach-in 提交可以静默合入。本 Stage 补上这道缺失的门禁，使 ADR 的宣称与现实一致。

接线形态（两处，均为**阻塞**而非告警），每个门禁步骤都是**两条命令**：

```bash
uv sync --frozen --inexact                          # 仓库根：补装 dev 组（import-linter / grimp）
cd apps/api && uv run --frozen --no-sync lint-imports   # apps/api：跑四契约
```

| Workflow | 位置 | 形态 |
|----------|------|------|
| `.github/workflows/ci.yml` | `backend-test` job 内新增 step `Verify architecture contracts (import-linter C1-C4)` | 上述两条命令，非零退出即 fail 整个 job；与同 job 的 ruff 步骤 `continue-on-error: true` 刻意相反 |
| `.github/workflows/quality-gate.yml` | 新增独立 job `architecture-contracts`，并接进汇总门禁 `needs: [backend-test, frontend-build, architecture-contracts]` | 与测试/构建平级，契约破了则汇总 gate 一并红 |

**两条命令都是承重项**，各自挡一个已实测的失败模式：

1. **`uv sync --frozen --inexact`（仓库根）—— 不装就根本没有 `lint-imports` 可执行文件。** `import-linter` / `grimp` 声明在**仓库根** `pyproject.toml` 的 `[dependency-groups] dev`，而 CI 的安装步骤是 `uv sync --frozen --no-dev --package odap`，`--no-dev` 直接排除该组。更隐蔽的是：即便去掉 `--no-dev`，从 `apps/api` 执行 `uv run` 解析到的是 **odap 项目**，其依赖闭包同样不含这两个包（实测 inexact dry-run 只补 `pytest`，不补 `grimp` / `import-linter`）——因为根 dev 组属于根项目 `odap-monorepo`，不随成员包传递。首版接线正是踩在这里：干净环境下门禁恒以 `error: Failed to spawn: lint-imports / program not found` 退出码 2 失败，**每次 CI 都红，且红的原因与架构契约毫无关系**。
   - 必须用 `--inexact`：根项目 `odap-monorepo` 没有 `[project.dependencies]`，精确 sync 只装 dev 组，会把上一步刚装好的 `odap` 当外来包**卸掉**，导致 grimp 找不到 `root_packages` 里的 `odap`。`--inexact` 语义即"不卸载环境中已有的外来包"。
2. **`cd apps/api`—— 配置在那里。** `[tool.importlinter]` 配在 `apps/api/pyproject.toml`，从仓库根执行 `lint-imports` 读不到配置，以 `Could not read any configuration` 退出 1。故门禁失败有两种语义，排查时先看报错文本再看契约名：`Failed to spawn` = 依赖没装（本条 1）；`Could not read any configuration` = 工作目录错（本条 2）；`BROKEN` 才是契约真破。
   - `--no-sync` 避免 `uv run` 的隐式 inexact sync 再动一次环境；`--frozen` 保证跑锁文件里那版 import-linter / grimp，防止 CI 临时解析到新依赖导致契约行为与边计数漂移。

接线后在**干净环境**（`UV_PROJECT_ENVIRONMENT` 指向空目录，按 CI 顺序逐步执行）复测：step 1/2/3 退出码均 0，`lint-imports` 输出 `4 kept, 0 broken`，`Analyzed 1360 files, 2380 dependencies`，C4 仍恰好 `KEPT (10 ignored imports)`（棘轮未涨）。deps 相对 § 5 收官态下降是同日 `biz/**/__init__.py` 幻影再导出清理的副产物（见下），属期望方向——删掉的是死边，不是漏扫。

> **关联清理**：同轮扫描发现 6 个 `biz/**/__init__.py` 用 `try: from ... import X / except Exception: pass` 做再导出，其中 `biz/data/__init__.py` 指向**根本不存在的模块** `qa_engine_v2`（真实模块是 `qa_engine`，类名 `QAEngineV2`）——ImportError 被吞，包初始化恒静默成功。这类裸 `except: pass` 对 grimp 同样是可见边（AST 层面 import 语句存在），既污染 deps 计数又掩盖幻影。已全部删除并以 `tests/unit/test_biz_package_inits.py` 上零容忍棘轮（AST 扫描全部 `biz/**/__init__.py`，出现裸 `except: pass` 即 FAIL）。

## Consequences

### 变得更容易

- **ontology 内部自由重构**：改名/移动/拆分内部实现，只需维护 `public.py` / `public_routers.py` 两张映射表，全仓外部消费者与 CI 契约无感。
- **分层纪律机器可验证**：C1/C2/C3 全严格、C4 棘轮守卫后，任何 `common→上层`、`biz/infra→web`、`外部→ontology 深层`、`infra→biz 直接` 的新增违规在 `lint-imports` 立即 FAIL，无需人工 review 抓 reach-in。四层边界（common 叶子 ← infra ← biz ← web 顶层）全部有契约背书。
- **共享设施各归其位**：`DictResponse` 在 common、`event_bus` / `emit_build_progress` 在 infra，下层不再反向依赖 web。
- **门面零 import-time 开销**：PEP 562 惰性解析避免把 540 文件拖进启动路径，也规避循环导入。

### 变得困难 / 需注意

- **门面映射表需人工维护**：内部重构后若忘记同步 `_PUBLIC_MAP` / `_ROUTER_MAP`，运行期 `__getattr__` 抛 `AttributeError`（已带明确提示"内部重构后请同步更新 public.py"）。这是刻意选择——失败必须显式（遵守规则 14），不做静默兜底。
- **grimp 看不见 importlib 动态边**：门面的 `importlib.import_module` 是运行期动态边，grimp 静态分析不可见。这正是 C3 放行门面→深层的原理，但也意味着门面映射表本身不受契约约束，需靠反向探针 + 运行期遍历 `__all__` 验证。
- **命名空间包必须显式 `__init__.py`**：任何新增无 `__init__.py` 的子包会重新制造 grimp 盲区，使契约对该子树假绿。

### 风险与缓解

- **风险：契约假绿（盲区/动态边）** → 缓解：反向探针（注入已知违规证明契约 BROKEN）+ 差集反查审计 + 容器终验（OpenAPI 路由数逐一相等证明零丢路由）。
- **风险：门面成为新的 god module** → 缓解：门面只做符号再导出（映射表 + 惰性 `__getattr__`），不含业务逻辑；`public.py`（符号）与 `public_routers.py`（路由）职责分离。
- **风险：烧账引入运行时回归** → 缓解：每阶段容器终验（app healthy + OpenAPI 755 paths/957 ops 与基线逐一相等 + 改动覆盖域定向回归）；预存失败用 `git stash` 反向测试铁证与本次无关。

## 验证（Stage H 收官态，2026-09-07）

| 验证 | 结果 |
|------|------|
| `lint-imports`（host） | `4 kept, 0 broken`；`Analyzed 1357 files, 2389 deps`；C1/C2/C3 KEPT 且**无 `(N ignored imports)` 后缀**，C4 `KEPT (14 ignored imports)` |
| C4 精确测量 | grimp 枚举 infra→biz 直接边：初始 **22** → Tier1 删 2 shim → **19** → Tier3 PermissionScope 下沉 → **18** → Tier2 object_service 迁移（消 4 边）→ **14** |
| 反向探针 | `biz/_c2_probe.py`→C2 BROKEN；`web/_c3_router_probe.py`→C3 BROKEN；`infra/_c4_probe.py`（`from odap.biz.data.qa.models import *`）→**C4 BROKEN（3 kept, 1 broken）**；逐一删探针恢复 `4 kept, 0 broken` |
| 容器终验 | `graphiti-dev-app` restart 后 healthy；OpenAPI **755 paths / 957 ops**，与烧账前基线逐一相等（object_service 路由随迁移仍注册，零丢路由） |
| Tier1 回归 | `tests/unit/test_thought_graph.py` 重接 biz canonical 后 **22/22 passed**；全仓 grep 对两删壳**零残留引用** |
| Tier2/Tier3 回归 | object_service 迁移 + PermissionScope 下沉后定向回归 **182/182 passed**（test_object_service 75 + test_roles 41 + test_thought_graph 22 + test_pydantic_mutable_defaults 3 + test_resilience 41）；全仓 grep 对 `odap.infra.object_service` 旧路径**零残留引用** |
| 门面运行时解析 | 遍历 `public_routers.__all__`（31）→ 31/31 解析为真实 `APIRouter` |
| Stage G 定向回归 | 改动覆盖域 364 passed；唯 2 失败经 `git stash` 反向测试铁证为预存 OPA mock 权限 bug |

## 相关

- **ADR-068**（本体模块四层分层架构）：本 ADR 是其迁移策略（`__getattr__` 兼容层 + 路由薄壳）的实现与 CI 守卫。
- **ADR-071 / ADR-072**（BuildResultContract / ReasoningServiceContract）：层间契约，与门面符号并存于 `public.py`。
- **ADR-081**（infra→biz 依赖倒置 provider 注册表 seam）：C4 棘轮 Stage I 烧账（14→10）所引入的依赖倒置机制，续接本 ADR §5 的 Stage H 收官态。
- 实施全记录：`workspace/outputs/core-ontology拆分迁移方案.md`（附录一~八 + 收官 Stage A–I 总览）。
