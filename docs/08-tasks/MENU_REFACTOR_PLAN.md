---
id: odap.l8.menu-refactor-plan
status: reference
owner: pm
version: ''
layer: L8
concern: menu-refactor
lifecycle: historical
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 菜单重构计划已落地（标题自述实施计划），现行信息架构见 workspaces.ts
governance_evidence: apps/web/src/navigation/workspaces.ts 为 6 工作区现行来源
---

# 菜单重构实施计划：基于四步法（建/见/演/用）归集

> **版本**: v1.0 (2026-08-01)
> **依据**: [ARCHITECTURE_FOUR_STEPS.md](../02-architecture/ARCHITECTURE_FOUR_STEPS.md) 功能梳理
> **目标**: 将 51 个前端路由 + 68 个后端模块按"建/见/演/用 + 横向支撑"五分组归集，消除 8 项偏差，补齐 5 项缺失前端页面
> **约束**: 遵循项目工程约定（中文 i18n key / 函数体 ≤40 行 / 不改 packages 目录 / 双通道审计）

---

## 1. 重构目标

### 1.1 核心目标

1. **菜单分组对齐四步法**：建本体 / 见本体 / 演本体 / 用本体 / 系统管理 / 帮助
2. **消除 8 项偏差**（D1~D8）：散落页面归组、跨阶段页面拆分、命名冲突消解
3. **补齐 5 项缺失前端页面**：服务化目录 / 语义地图 / 消歧图 / 本体记忆 / 感知
4. **保持向后兼容**：现有 URL 可访问（redirect 兼容），不破坏书签

### 1.2 非目标

- 不改动后端 API 路由前缀（API 契约稳定）
- 不重构前端页面组件内部逻辑（仅调整路由分组 + 菜单配置）
- 不改动 `packages/` 目录（应用层定制）
- 不改动 RBAC 权限码体系（仅菜单树重组）

---

## 2. 迭代规划

### Iteration 总览

| Iteration | 主题 | 偏差项 | 缺失项 | 工作量 | 风险 |
|-----------|------|--------|--------|--------|------|
| **Iter 1** | P0 菜单归集（business + semantic-admin 拆分） | D1, D2 | — | 中 | 低 |
| **Iter 2** | P1 仿真合并 + QA 拆分 | D3, D4 | — | 中 | 中 |
| **Iter 3** | P2 命名消歧 + HE 关联 + MCP 入口 + 推理持久化 UI | D5, D6, D7, D8 | — | 高 | 中 |
| **Iter 4** | P3 缺失前端页面补齐 | — | 5 项 | 高 | 高 |

---

## 3. Iter 1：P0 菜单归集（business + semantic-admin 拆分）

### 3.1 目标

- D1：`/business/*` 5 个页面归入"演本体"菜单组
- D2：`/semantic-admin/*` 6 个页面拆分到"建本体"（USL/流水线/候选/审批/质量）+ "见本体"（仪表盘）

### 3.2 任务清单

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 1.1 | 菜单种子数据初始化 | `apps/api/odap/biz/platform/menu_config/seeds/seed_four_steps.py`（新建） | 按四步法生成默认菜单树种子数据，首次启动自动写入 |
| 1.2 | SemanticAdminIndex Tab 调整 | `apps/web/src/modules/semantic-admin/SemanticAdminIndex.tsx` | 顶层 Tab 拆分：建模类（usl/pipeline/candidates/approvals/quality）vs 探查类（dashboard） |
| 1.3 | 菜单配置 API 支持种子初始化 | `apps/api/odap/biz/platform/menu_config/services/menu_config_service.py` | 新增 `init_default_menu()` 方法，幂等写入四步法菜单树 |
| 1.4 | 前端菜单分组组件 | `apps/web/src/modules/shared/components/Sidebar.tsx`（或等效） | 侧边栏按"建/见/演/用/系统管理/帮助"六组渲染 |
| 1.5 | business 菜单归入演本体 | 菜单种子数据 | `/business/*` 5 项 parent_id 指向"演本体"目录 |
| 1.6 | semantic-admin 菜单拆分 | 菜单种子数据 | usl/pipeline/candidates/approvals/quality → 建本体；dashboard → 见本体 |

### 3.3 验收标准

- [ ] 侧边栏显示 6 个顶级分组（建本体/见本体/演本体/用本体/系统管理/帮助）
- [ ] `/business/process` 在"演本体"菜单组下可访问
- [ ] `/semantic-admin/usl` 在"建本体 / 语义管理"下可访问
- [ ] `/semantic-admin/dashboard` 在"见本体"下可访问
- [ ] 现有 URL 全部可访问（redirect 兼容）
- [ ] 管理员角色默认可见全部菜单
- [ ] 普通角色菜单权限不丢失

### 3.4 测试策略

- 单元测试：菜单种子数据初始化幂等性（调用 2 次不重复写入）
- 集成测试：`get_user_menu_tree()` 返回四步法分组结构
- 回归测试：现有 `test_semantic_retrieval_routes.py` + `test_menu_config` 全部通过

---

## 4. Iter 2：P1 仿真合并 + QA 拆分

### 4.1 目标

- D3：`/qa/*` 拆分 — QA 管理 → 见本体；QA 查询/评估 → 用本体
- D4：`/simulator` + `/simulation` 合并为"演本体 / 仿真沙盘"统一入口

### 4.2 任务清单

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 2.1 | QA 菜单拆分 | 菜单种子数据 | `/qa` → 见本体；`/qa/query` + `/qa/evaluation` → 用本体 |
| 2.2 | 仿真入口合并 | `apps/web/src/AppRoutes.tsx` | `/simulator` redirect 到 `/simulation`；`/simulation` 作为统一入口，内部 Tab 切换沙盘/推演 |
| 2.3 | SimulationPage Tab 整合 | `apps/web/src/modules/simulation/SimulationPage.tsx` | 新增 Tab：沙盘推演（原 Simulator）+ 策略推演（原 StrategyDeduction）+ 事件注入 |
| 2.4 | 旧路由兼容 redirect | `apps/web/src/AppRoutes.tsx` | `/simulator` → `/simulation`；`/simulation/deduction` → `/simulation?tab=deduction` |

### 4.3 验收标准

- [ ] `/qa` 在"见本体"菜单组下可访问
- [ ] `/qa/query` + `/qa/evaluation` 在"用本体"菜单组下可访问
- [ ] `/simulator` 自动 redirect 到 `/simulation`
- [ ] `/simulation` 页面含 3 个 Tab（沙盘/推演/事件）
- [ ] `/simulation/deduction` redirect 到 `/simulation?tab=deduction`

### 4.4 测试策略

- 集成测试：redirect 路由可访问性
- 回归测试：仿真相关测试全部通过

---

## 5. Iter 3：P2 命名消歧 + HE 关联 + MCP 入口 + 推理持久化 UI

### 5.1 目标

- D5：`/ontology/graph` 前端改名 `/ontology/explorer`（避免与 API `/graph` 冲突）
- D6：建本体下新增"HE 抽取链"子菜单关联 spec 006
- D7：用本体下新增"MCP 工具集"前端页面
- D8：候选管理页面增加"来源=reasoning"筛选

### 5.2 任务清单

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 3.1 | 前端路由改名 | `apps/web/src/AppRoutes.tsx` | `/ontology/graph` → `/ontology/explorer`；旧路径 redirect |
| 3.2 | OntologyGraphPage 引用更新 | 全局搜索 `OntologyGraphPage` 引用 | 更新所有 import 路径 |
| 3.3 | HE 抽取链菜单 | 菜单种子数据 | 建本体下新增"HE 抽取链"菜单项（关联 spec 006） |
| 3.4 | HE 抽取链前端页面 | `apps/web/src/modules/ontology/pages/HeExtractionPage.tsx`（新建） | 展示 HE 模板列表 + 抽取记录 + 执行状态 |
| 3.5 | MCP 工具集前端页面 | `apps/web/src/modules/ontology/pages/McpToolsPage.tsx`（新建） | 展示 7 个 MCP 工具清单 + input_schema + 在线试用 |
| 3.6 | MCP 工具集菜单 | 菜单种子数据 | 用本体下新增"MCP 工具集"菜单项 |
| 3.7 | 候选管理筛选增强 | `apps/web/src/modules/semantic-admin/CandidatesPage.tsx` | 新增"来源"筛选（origin=llm 且 provenance.source=reasoning） |
| 3.8 | 推理持久化标记展示 | `apps/web/src/modules/semantic-admin/CandidatesPage.tsx` | 来源=reasoning 的候选显示 chain_id + step_index 标签 |

### 5.3 验收标准

- [ ] `/ontology/explorer` 可访问，`/ontology/graph` redirect 兼容
- [ ] 建本体菜单含"HE 抽取链"子项
- [ ] 用本体菜单含"MCP 工具集"子项
- [ ] MCP 工具集页面展示 7 个工具
- [ ] 候选管理页面可按"来源=reasoning"筛选
- [ ] reasoning 来源候选显示 chain_id 标签

### 5.4 测试策略

- 单元测试：MCP 工具集页面渲染 7 个工具
- 集成测试：候选管理筛选 reasoning 来源
- 回归测试：`/ontology/graph` redirect 不破坏现有链接

---

## 6. Iter 4：P3 缺失前端页面补齐

### 6.1 目标

补齐 5 项有后端 API 无前端页面的模块。

### 6.2 任务清单

| # | 任务 | 文件 | 归属 | 说明 |
|---|------|------|------|------|
| 4.1 | 服务化目录页面 | `apps/web/src/modules/ontology/pages/ServiceCatalogPage.tsx`（新建） | 用本体 | 服务目录 + 部署状态 + 调用统计 |
| 4.2 | 语义地图页面 | `apps/web/src/modules/ontology/pages/SemanticMapPage.tsx`（新建） | 见本体 | 基于场景的语义地图可视化 |
| 4.3 | 消歧图页面 | `apps/web/src/modules/ontology/pages/AbutionGraphPage.tsx`（新建） | 见本体 | 实体消歧图可视化 |
| 4.4 | 本体记忆页面 | `apps/web/src/modules/simulation/pages/MemoryDashboardPage.tsx`（新建） | 演本体 | 记忆衰减 + 图谱同步 + 共享空间 |
| 4.5 | 感知数据页面 | `apps/web/src/modules/simulation/pages/PerceptionPage.tsx`（新建） | 演本体 | 数据感知接入 + 实时流 |
| 4.6 | 菜单种子数据更新 | 菜单种子数据 | 各归属 | 新增 5 个菜单项 |

### 6.3 验收标准

- [ ] 用本体菜单含"服务化目录"子项
- [ ] 见本体菜单含"语义地图" + "消歧图"子项
- [ ] 演本体菜单含"本体记忆" + "感知数据"子项
- [ ] 5 个新页面均可正常渲染（含空状态）

### 6.4 测试策略

- 单元测试：每个新页面渲染不报错
- 集成测试：API 调用成功 + 空状态展示
- E2E 测试：从菜单导航到页面完整流程

---

## 6A. Iter 5–7：增量演进（决策智能 / USL 本体管理 / 去重消歧）

> Iter 5、Iter 6 已在种子数据落地但当时未回填本计划，此处一并补记；Iter 7 为本次
> 依据 [MENU_DEDUP_PLAN.md](MENU_DEDUP_PLAN.md) 执行的去重/消歧 + 决策主线显性化。

### 6A.1 Iter 5（ADR-076 决策智能入口）

- 演本体新增「决策智能」菜单（`/decisions`，`menu:simulate:decision`），承载决策记录/先例/影响分析。

### 6A.2 Iter 6（USL 本体管理）

- 建本体 > 语义管理新增「USL 本体管理」（`/semantic-admin/usl-ontologies`，`menu:build:semantic:usl_ontologies`）。

### 6A.3 Iter 7（去重/消歧 + 决策主线显性化）— 本次

**动机**：菜单相似项多，根因是执行层把同一功能领域按"阶段"硬拆到不同目录，且部分命名不体现职责区别；同时"基于本体的辅助决策"这一平台核心价值的入口（决策智能）被压在演本体末位，IA 上不可见。

**目标树要点**（种子总数 55 → **57**，全部 code 稳定）：

- **消歧改名**：本体设计器→本体类型设计、蓝图设计器→蓝图编排、数据摄入→数据摄入管道、HE 抽取链→HE 文本抽取、知识库→知识库·管理、知识导航→知识库·浏览、本体图谱→本体图谱浏览、语义地图→语义映射管理、消歧图→消歧快照管理、QA 管理→智能问答、QA 查询→检索查询台、QA 评估→检索评估、智能体对话→智能体调度、管理后台→智能体管理。
- **新增 4 个分组子目录**：建本体「数据接入」(`dir:build:ingest`)、见本体「图谱与映射」(`dir:see:graph`)、演本体「业务建模」(`dir:simulate:business`)、用本体「问答检索」(`dir:use:qa`)。
- **移位**：QA 三项 见本体→用本体「问答检索」（`menu:see:qa` code 保持不变）；策略编辑器 演本体→系统管理（`menu:simulate:policy` code 保持不变，OPA 权限域）。
- **移除**：图谱查看器 `/iframe-viewer`（通用 iframe 容器伪菜单，固定入口点进去必空）+ 总览仪表盘 `/semantic-admin/dashboard`（与质量仪表盘同后端 API）从种子移除；dashboard 路由 redirect 到 quality，两条路由本身保留。
- **决策主线显性化**：演本体「决策智能」`/decisions` 从 sort 10 提升到 **sort 1**，使辅助决策价值在演本体首屏一眼可见。

**落地机制**：因 `init_default_menu()` 对已存在 code 直接 skip，改名/移位对既有 DB 无效，配套一次性迁移脚本 `apps/api/odap/biz/platform/menu_config/migrations/iter7_dedup.py`（按 code `INSERT OR REPLACE` 就地对齐 + 软删移除项，幂等，code/id 稳定故 role_menus 授权不丢；新分组子目录由服务层 `_ensure_parent_directories` 建树时自动补全，无需迁移 role_menus）。

**执行方式**：`python -m odap.biz.platform.menu_config.migrations.iter7_dedup`（或在部署初始化流程中调用 `migrate_iter7_dedup(storage)`）。

**同步项**：种子测试 `test_menu_seed_four_steps.py`（25 用例，计数/结构/改名/移位全量更新）、迁移测试 `test_menu_migration_iter7.py`（6 用例）、前端 `AppRoutes.tsx` dashboard redirect、i18n `menu-names`（zh/en/ja 各新增 19 键）、`ARCHITECTURE_FOUR_STEPS.md` §7 菜单树、`MENU_DEDUP_PLAN.md` 状态。离线单测 31 passed。

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 菜单种子数据覆盖用户自定义菜单 | 中 | 高 | `init_default_menu()` 幂等：仅首次启动写入，已有数据跳过 |
| 前端路由改名破坏书签 | 中 | 中 | 旧路由 redirect 兼容（`/ontology/graph` → `/ontology/explorer`） |
| 仿真入口合并影响现有用户习惯 | 中 | 中 | `/simulator` + `/simulation/deduction` 保持 redirect；Tab 默认选中用户原入口 |
| MCP 工具集页面暴露内部 API | 低 | 中 | 页面需管理员权限（`Depends(get_current_user)` + admin role check） |
| 缺失前端页面后端 API 不稳定 | 中 | 中 | Iter 4 每个页面对照 API 契约文档实现；空状态优先 |
| 菜单重构引入 i18n key 冲突 | 低 | 低 | 遵循"中文 as key"约定；新菜单项用中文名作 key |

---

## 8. 依赖关系

```
Iter 1（P0 菜单归集）
  └─→ Iter 2（P1 仿真合并 + QA 拆分）
        └─→ Iter 3（P2 命名消歧 + MCP 入口）
              └─→ Iter 4（P3 缺失页面补齐）
```

- Iter 1 是基础：菜单种子数据 + 侧边栏分组组件，后续 Iteration 复用
- Iter 2 依赖 Iter 1 的菜单框架
- Iter 3 依赖 Iter 1 的菜单框架 + Iter 2 的路由整理
- Iter 4 独立性较高，但菜单项需挂载到 Iter 1 的分组下

---

## 9. 技术约束备忘

| 约束 | 来源 | 适用范围 |
|------|------|---------|
| 中文 as i18n key | project_memory | 所有新菜单项名称 |
| 函数体 ≤ 40 行 | Constitution I | 菜单种子数据初始化 + 页面组件 |
| 不改 packages/ 目录 | project_memory | 所有 Iteration |
| 双通道审计 + 不记录明文 | project_memory | 菜单 CRUD 审计 |
| `user=Depends(get_current_user)` + `_extract_operator(user)` | project_memory | 新增 API 路由 |
| 菜单配置 PROXY_TARGET 用容器名 | project_memory | 部署配置 |
| 图谱查看器 API 强制认证 | project_memory | 新增图谱相关页面 |

---

## 10. 验收检查清单（全部 Iteration 完成后）

### 10.1 菜单结构

- [ ] 侧边栏 6 个顶级分组（建本体/见本体/演本体/用本体/系统管理/帮助）
- [ ] 建本体含 8 个二级菜单（含语义管理子组 5 项）
- [ ] 见本体含 8 个二级菜单
- [ ] 演本体含 9 个二级菜单
- [ ] 用本体含 4 个二级菜单（含智能体子组 4 项）
- [ ] 系统管理含 8 个二级菜单
- [ ] 帮助含 1 个菜单项

### 10.2 路由兼容

- [ ] 所有旧 URL 可访问（redirect 兼容）
- [ ] `/ontology/graph` → `/ontology/explorer`
- [ ] `/simulator` → `/simulation`
- [ ] `/simulation/deduction` → `/simulation?tab=deduction`

### 10.3 功能完整

- [ ] MCP 工具集页面展示 7 个工具
- [ ] 候选管理支持"来源=reasoning"筛选
- [ ] 5 个缺失前端页面全部补齐

### 10.4 回归无破坏

- [ ] 全部现有前端测试通过
- [ ] 全部现有后端测试通过
- [ ] RBAC 权限不丢失
- [ ] 审计日志正常记录

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-01 | 初始版本：4 个 Iteration，覆盖 8 偏差 + 5 缺失 |
| v1.1 | 2026-10-02 | 补记 Iter 5–6，新增 §6A.3 Iter 7（去重/消歧 + 决策主线显性化 + 迁移脚本，种子 55→57） |
