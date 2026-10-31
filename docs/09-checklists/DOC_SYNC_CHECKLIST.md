---
id: odap.l9.doc-sync-checklist
status: active
owner: qa
version: ''
layer: L9
concern: doc-sync
lifecycle: living
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 文档同步检查清单，与本次文档治理配套
---

# 文档同步检查清单 (DOC_CHECKLIST)

> **用途**: 提交代码前逐项检查，确保文档与代码一致。
> **维护者**: 所有贡献者。发现文档过期时**立即修正**，不留 TODO。

---

## 一、模块变更检查

当 `apps/api/odap/biz/` 下新增/删除/重命名模块时：

- [ ] `docs/03-modules/README.md` — 更新对应领域下的模块列表（模块名、路径、职责摘要）
- [ ] `docs/03-modules/{领域}/` — 新增或更新对应模块的 `DESIGN.md`
- [ ] `agents.md` § 3.1 — 更新后端包结构树（如有新领域或结构变更）

当 `apps/web/src/modules/` 下新增/删除/重命名模块时：

- [ ] `docs/03-modules/README.md` — 更新前端模块表
- [ ] `agents.md` § 4.2 — 更新前端路由方案表（如有新页面路由）

当 `apps/api/odap/infra/` 下新增/修改模块时（ADR-080 C4：infra 是 biz 的下层）：

- [ ] **禁止 infra 直接 import biz** — 新代码不得引入 `odap.infra.* -> odap.biz.*` 的直接依赖；若确需 biz 数据，走依赖倒置（在 `odap/infra/providers.py` 注册表解析 provider，工厂在 `odap/biz/providers_bootstrap.py` 注册，见 ADR-081）或把共享类型下沉到 common
- [ ] 若消除了 C4 存量债账（10 条之一），同步从 `apps/api/pyproject.toml` 的 C4 `ignore_imports` 删除对应行（棘轮只减不增）
- [ ] 运行 `cd apps/api && uv run --no-sync lint-imports` — 确认 C4 未因新增 infra→biz 直接边而 BROKEN

---

## 二、路由变更检查

当新增 `api/routes.py` 路由模块时：

- [ ] `apps/api/odap/web/router_registry.py` — 在 `create_router_registry()`（构建 `DEFAULT_ROUTER_REGISTRY`）中注册新路由
- [ ] **ontology 路由专属**（ADR-080 C3）— ontology 深层子包的路由必须经 `biz/core/ontology/public_routers.py` 门面暴露（`_ROUTER_MAP` 加异名别名），`router_registry` 从门面导入，禁止直接 reach-in `ontology.<深层>.api.routes`
- [ ] `apps/api/odap/web/app.py` — 确认 `register_routers(app, DEFAULT_ROUTER_REGISTRY)` 生效（生产入口）
- [ ] `agents.md` § 附录 E — 更新关键 API 路径速查表（如有新路径前缀）
- [ ] 运行 `cd apps/api && uv run --no-sync lint-imports` — 确认 C1/C2/C3/C4 四契约未因新路由 reach-in 而 BROKEN

---

## 三、架构决策检查

当引入新基础设施、新模式、新数据流、重大技术选型时：

- [ ] `docs/07-adr/` — 创建新 ADR 文件（按模板：状态/上下文/决策/后果/可逆性）
- [ ] `docs/07-adr/README.md` — 更新完整索引表（编号、标题、状态、文件链接）
- [ ] `docs/07-adr/README.md` — 更新分类索引（按领域归类到对应表格）
- [ ] `docs/07-adr/README.md` — 更新编号规则说明（新增 ADR 的编号范围）

---

## 四、环境/部署变更检查

当变更 `.env.docker`、`docker-compose*.yml`、`bootstep.py` 时：

- [ ] `agents.md` § 2.2 — 更新启动命令对照表
- [ ] `agents.md` § 2.3 — 更新环境变量速查
- [ ] `agents.md` § 2.2.6 — 更新关键文件速查表

---

## 五、存储层变更检查

当新增/修改 SQLite 表结构或字段时：

- [ ] 对应模块 `DESIGN.md` — 更新数据模型描述
- [ ] `agents.md` MEMORY — 记录关键陷阱（如字段名不匹配、位置索引禁用等）

---

## 六、过期检测机制

定期或在以下时机执行文档一致性审计：

| 触发时机 | 检查内容 | 方法 |
|---------|---------|------|
| 每次 PR/MR | 上述检查清单 | 提交者自检 + Reviewer 复核 |
| 新增 Phase/里程碑 | 全量文档审计 | 对比代码目录 vs 文档索引 |
| 季度 Review | ADR 状态更新 | 检查"提议"状态 ADR 是否已实现或废弃 |
| 发现文档不符 | 立即修正 | 不等不拖，修正后记录到 MEMORY |

### 快速审计命令

```bash
# 后端模块审计：对比代码目录与文档索引
ls apps/api/odap/biz/*/  | sort
# 然后与 docs/03-modules/README.md 中的模块列表逐项对照

# 前端模块审计
ls apps/web/src/modules/ | sort
# 然后与 docs/03-modules/README.md 前端模块表对照

# ADR 审计
ls docs/07-adr/ADR-*.md | sort
# 然后与 docs/07-adr/README.md 索引表逐项对照

# 路由审计（符号是 DEFAULT_ROUTER_REGISTRY，不是 router_registry —— 见 ADR-080 Stage F）
python -c "from odap.web.router_registry import DEFAULT_ROUTER_REGISTRY as r; print(f'共 {len(r)} 个路由模块')"
# 然后与 docs/03-modules/README.md 路由数量对照

# 分层契约审计（ADR-080：C1 common 叶子 / C2 web 顶层 / C3 ontology 门面封装 / C4 infra 下层）
cd apps/api && uv run --no-sync lint-imports
# 期望：Contracts: 4 kept, 0 broken
#   · C1/C2/C3 无 "(N ignored imports)" 后缀（零债账全严格）
#   · C4 显示 "KEPT (10 ignored imports)"（infra→biz 存量债账棘轮，只减不增；见 ADR-080 Stage H + ADR-081 Stage I）
# 新增 biz/infra→web、common→上层、外部→ontology 深层子包、infra→biz 的直接 import 会立即 FAIL
#
# 同一命令自 ADR-080 Stage J（2026-09-11）起也是 CI 阻塞门禁，CI 里是两条命令：
#   uv sync --frozen --inexact                             # 仓库根：补装 dev 组（import-linter/grimp）
#   cd apps/api && uv run --frozen --no-sync lint-imports  # apps/api：跑四契约
#   · .github/workflows/ci.yml → step "Verify architecture contracts (import-linter C1-C4)"
#   · .github/workflows/quality-gate.yml → job architecture-contracts，已接进汇总 gate 的 needs
# 本地跳过也会被 CI 拦住。
#
# 门禁红了先按报错文本分辨三种语义，别一上来就查契约：
#   · "Failed to spawn: lint-imports / program not found"
#       → 依赖没装。import-linter/grimp 在【仓库根】[dependency-groups] dev，
#         `uv sync --no-dev --package odap` 不装它；且从 apps/api 跑 uv run 解析到的是 odap
#         项目，闭包同样不含（根 dev 组不随成员包传递）。必须在根补装，且用 --inexact
#         （根项目无 [project.dependencies]，精确 sync 会把 odap 当外来包卸掉）。
#   · "Could not read any configuration"
#       → 工作目录错。[tool.importlinter] 在 apps/api/pyproject.toml，必须在 apps/api 下执行。
#   · "BROKEN" → 契约真破，按契约名定位违规边。
```

---

## 七、CI 门禁与架构契约变更检查

当变更 `.github/workflows/*.yml`、`apps/api/pyproject.toml` 的 `[tool.importlinter]`，或增删 C4 `ignore_imports` 债账时：

- [ ] **门禁必须阻塞，不得降级为告警** — 新增检查项要能 fail job（非零退出 / 接进 `needs`），`continue-on-error: true` 等于没有门禁
- [ ] **门禁工具确实在 CI 环境里可执行** — 别只看本地能跑。uv workspace 下 `[dependency-groups] dev` 属于**根项目**，不随成员包传递：CI 的 `uv sync --no-dev --package odap` 不装它，从 `apps/api` 执行 `uv run` 解析到 odap 项目、闭包同样不含。须在仓库根补一次 `uv sync --frozen --inexact`（`--inexact` 防止精确 sync 把已装的 odap 当外来包卸掉——根项目无 `[project.dependencies]`）
- [ ] **执行目录与配置位置一致** — `[tool.importlinter]` 在 `apps/api/pyproject.toml`，门禁命令必须 `cd apps/api` 后再跑；从仓库根执行会以 `Could not read any configuration` 退出 1
- [ ] **依赖版本锁死** — 用 `--frozen`（跑锁文件里那版工具，避免 CI 解析到新 import-linter/grimp 导致契约行为与边计数漂移）+ `--no-sync`（避免 `uv run` 的隐式 sync 再改环境）
- [ ] **接线后必须在干净环境实测一遍** — `UV_PROJECT_ENVIRONMENT=<空目录>` 按 CI 步骤顺序逐步执行，确认每步退出码 0。首版接线就是只在已有 `.venv` 里验过（工具早就装着），CI 上恒以 `Failed to spawn: lint-imports / program not found` 失败——门禁因环境原因常红，比没有门禁更糟（会训练所有人忽略红灯）
- [ ] 门禁失败的三种语义写进注释，便于排查：`Failed to spawn` = 依赖没装；`Could not read any configuration` = 工作目录错；`BROKEN` = 契约真破
- [ ] `docs/07-adr/ADR-080_ontology门面封装与分层契约.md` — 接线形态变更同步 § 6；C4 债账增减同步 Status 行、「代码现实」引文与 § 5 的棘轮数字
- [ ] `docs/07-adr/ADR-081_*` — 若通过 provider 依赖倒置烧掉 C4 存量边，同步其「剩余 C4 债账」表
- [ ] 本清单 § 六 的审计命令块 — 期望输出（`4 kept, 0 broken`、C4 ignored 条数）随实测更新
- [ ] **ADR 宣称与现实对齐** — ADR/文档中出现「CI 守卫」「自动拦截」「立即 FAIL」等措辞时，确认确有 workflow 在跑该检查；只有手工命令就不得这样写（规则 12：发现不符立即修正，不留 TODO）

---

## 八、临时文件目录化检查

当新增/修改写入文件（日志、SQLite、缓存、临时 dump）的代码时：

- [ ] **路径合规** — 写入路径符合 [AGENTS.md 规则 13](../../AGENTS.md) 的位置约束表：
  - 运行时日志 → `apps/api/data/logs/`
  - SQLite 数据库 → `apps/api/data/`（受 `DATA_DIR` 环境变量控制）
  - 临时缓存 → `<模块>/temp/`
  - 诊断脚本 → `scripts/` 或 `scripts/archive/`
- [ ] **无相对路径污染 CWD** — 代码中无 `open('app.log')`、`sqlite3.connect('sessions.db')` 等相对路径写入；用 `os.path.abspath(__file__)` 反推或读取 `DATA_DIR`
- [ ] **`os.makedirs` 幂等** — 目录创建使用 `exist_ok=True`
- [ ] **`.gitignore` 同步** — 若引入新的根目录散落临时文件模式，在 `.gitignore` 追加 `/` 前缀锁定规则；模块 `temp/` 目录由模块自行管理（`!` 例外规则在 git 中无法重新包含被通配符排除的文件）
- [ ] **模块 temp/ README** — 若新增 `<模块>/temp/` 目录，必须创建 `README.md` 描述用途、清理时机、负责人
- [ ] **AGENTS.md § 2.3 / § 6.4 同步** — 若新增环境变量（如 `DATA_DIR`）或日志路径变更，同步更新 `agents.md` 对应章节

---

## 九、文档层级与优先级

当不同文档对同一事项描述冲突时，按以下优先级裁决：

```
agents.md (工作手册)     ← 最高优先级，开发规则权威
  ↓
docs/02-architecture/   ← 架构设计权威
  ↓
docs/03-modules/        ← 模块设计权威
  ↓
docs/07-adr/            ← 决策记录权威
  ↓
代码注释                ← 最低优先级
```

**原则**: 高层文档定义"应该怎么做"，代码实现"实际怎么做"。两者不一致时，先修正文档（如果代码是正确的），或先修正代码（如果文档是正确的），**绝不允许两者长期不一致**。
