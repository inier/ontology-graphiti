# ODAP 不相关/错误信息枚举报告

> **版本**: 1.0 | **日期**: 2026-04-19 | **配套**: req-ok v2.0.0 + ARCHITECTURE_PLAN v1.0
> **工作项**: WR-09（异常信息确认）— 需人工逐一确认

---

## 说明

以下枚举了在架构梳理和文档审查过程中发现的**不相关、过时、矛盾或待确认信息**。每条均需人工确认处理方式：
- **保留**：信息仍有价值，保留但需标注
- **更新**：信息过时/不准确，需更新
- **删除**：信息已完全不相关，建议删除
- **降级**：信息优先级已变化，需调整

---

## 1. 文档级不相关信息

### 1.1 已合并/推迟模块的 DESIGN.md

| # | 文件 | 问题 | 建议 |
|---|------|------|------|
| I-01 | `docs/modules/permission_checker/DESIGN.md` (65.75 KB) | 已合并到 opa_policy，头部已标注但文件仍占据大量空间 | 🔄 更新：已在头部标注合并声明，建议 Phase 4 归档到 `docs/archive/` |
| I-02 | `docs/modules/openharness_bridge/DESIGN.md` (43.38 KB) | ADR-030 已推迟到 Phase 4，头部已标注 DEFERRED | 🔄 更新：已在头部标注推迟声明，Phase 4 恢复时更新 |
| I-03 | `docs/modules/mock_engine/DESIGN.md` (8.08 KB) | 已合并到 event_simulator，头部已标注 | 🔄 更新：已在头部标注合并声明 |
| I-04 | `docs/modules/web/DESIGN.md` (9.49 KB) | 已拆分到 api_gateway + web_frontend，头部已标注 | 🔄 更新：已在头部标注拆分声明 |

### 1.2 ADR 状态不一致

| # | ADR | 问题 | 建议 |
|---|-----|------|------|
| I-05 | ADR-022（模拟数仓与统一查询服务） | 状态为"提议中"，长期未推进，且 M-14 推演引擎已实现类似功能 | ✅ 维持"已接受"：ADR 头部已标注"已接受"，M-14 实现部分功能与数仓互补而非替代 |
| I-06 | ADR-033（项目目录结构重构） | 状态为"提议"，但实际目录已按 `odap/` 分层组织（infra/biz/tools/web） | ✅ 标记为"已接受"：实际目录已按 ADR 落地，事实已确认 |
| I-07 | ADR-025（OpenHarness 集成）与 ADR-030（推迟引入） | 两者存在表述矛盾：ADR-025 说"基于 OpenHarness 实现"，ADR-030 说"Phase 1 不引入" | ✅ 更新：ADR-025 标注"被 ADR-030 部分取代，Phase 4 参考" |

### 1.3 req-beta 冗余信息

| # | 问题 | 建议 |
|---|------|------|
| I-08 | `docs/req-beta.md` (28.96 KB) 中的需求已在 req-ok v2.0.0 中整合，两份文档存在大量重复 | ✅ 归档为历史参考：req-beta 头部标注"已被 req-ok v2.0.0 整合，仅作历史参考" |
| I-09 | req-beta 中的编号体系（F-001~F-902）与 req-ok 的编号体系（FR-001~FR-900）不一致 | 🔄 更新：以 req-ok v2.0.0 编号为唯一标准，req-beta 编号仅在交叉引用时使用 |

---

## 2. 设计文档中的待确认项

### 2.1 DESIGN.md 与代码不一致

| # | 模块 | 不一致点 | 影响 | 建议 |
|---|------|---------|------|------|
| I-10 | M-01 graphiti_client | DESIGN 描述三层缓存（Memory→Redis→Disk），代码仅实现 Memory 缓存 | 低 | 🔄 更新：Phase 4 实现 Redis/Disk 层 |
| I-11 | M-02 opa_policy | DESIGN 描述 Bundle 热更新，代码仅实现单文件策略加载 | 中 | 🔄 更新：WR-02 包含此功能 |
| I-12 | M-08 skills | DESIGN 描述 17 个 Skill，代码实际有 11 个（9 文件） | 低 | 🔄 更新：补充缺失的 6 个 Skill（WR-08） |
| I-13 | M-09 swarm | DESIGN 描述 StatePersistenceManager 增量检查点，代码实现全量检查点 | 低 | 🔄 更新：WR-11 包含优化 |
| I-14 | M-14 simulator | DESIGN 描述 What-if 分析和版本对比，代码仅实现基础沙箱 | 中 | 🔄 更新：WR-15 包含此功能 |

### 2.2 DESIGN.md 间接口参数不一致

| # | 接口 | 不一致点 | 建议 |
|---|------|---------|------|
| I-15 | IWorkspaceProvider | workspace/DESIGN 定义 `get_active_workspace_id()`，graphiti_client/DESIGN 引用为 `current_workspace` 属性 | 🔄 统一为方法调用 |
| I-16 | IAuditLogger | audit_log/DESIGN 定义 `log(event: AuditEvent)`，hook_system/DESIGN 引用为 `audit(context: HookContext)` | 🔄 统一为 AuditEvent 参数 |

---

## 3. 架构决策待确认项

### 3.1 技术选型待确认

| # | 决策点 | 当前方案 | 备选方案 | 建议 |
|---|--------|---------|---------|------|
| I-17 | 图谱可视化前端 | ReGraph（商业库） | G6（蚂蚁开源） / D3.js | ✅ 已决策：G6（ADR-045），维持现状，代码已集成 |
| I-18 | 地图可视化 | CesiumJS | Leaflet.js / Mapbox GL | ✅ 已决策：Leaflet（ADR-045），维持现状，2D 够用 |
| I-19 | 缓存层 | Redis（DESIGN 中提到） | 内存缓存（当前实现） | ✅ Phase 4 不引入 Redis：内存缓存 + SQLite 够用，Redis 为 Phase 5+ 优化项（YAGNI） |
| I-20 | 消息队列 | 未选型 | Kafka / RabbitMQ / Redis Streams | ✅ Phase 4 不引入 MQ：asyncio.Channel 够用，审计日志同步写入可接受，MQ 为 Phase 5+ |

### 3.2 部署架构待确认

| # | 决策点 | 问题 | 建议 |
|---|--------|------|------|
| I-21 | 单体 vs 微服务 | 当前代码为单体（odap/ 包），ARCHITECTURE_PLAN 按微服务风格设计 | ✅ 已决策：模块化单体（ADR-046），Phase 4 维持，Phase 5+ 视需拆分 |
| I-22 | 数据库选型 | 审计日志存储未确定（文件 / SQLite / PostgreSQL / Neo4j） | ✅ 已决策：SQLite + 文件哈希链锚点（ADR-042） |

---

## 4. 代码中的不相关信息

| # | 位置 | 问题 | 建议 |
|---|------|------|------|
| I-23 | `odap/web/legacy/` | 遗留代码目录，可能已废弃 | ✅ 归档：Gradio 旧界面无代码引用，移到 `docs/archive/legacy_code/` |
| I-24 | `odap/storage/` | 空目录（无文件） | 🔄 修正：非空目录（含 7 个本体版本文件），保留不变 |
| I-25 | `1~` | 项目根目录下的 `1~` 文件，疑似临时文件 | ✅ 已删除（2026-04-19） |
| I-26 | `odap/adapters/` | MCP 适配器目录，与 `odap/infra/` 职责边界不清 | ✅ adapters 并入 infra：无代码引用，mcp/ 和 openharness/ 适配器归入 infra/ |
| I-27 | `odap/biz/permission/` | permission_checker 已合并到 opa_policy，此目录可能冗余 | ✅ 删除：仅剩 checker.py，已合并到 opa_policy，无代码引用 |
| I-28 | `simulator_ui/` | Phase 3 的单页应用，与 `frontend/` React SPA 功能重叠 | ✅ 不操作：目录不存在，ANOMALY_REPORT 记录有误 |

---

## 5. 命名/术语不一致

| # | 术语A | 术语B | 出现位置 | 建议 |
|---|-------|-------|---------|------|
| I-29 | GraphManager | DomainGraphManager | 代码中两名称混用 | 🔄 统一为 DomainGraphManager（代码）+ IGraphitiClient（接口） |
| I-30 | OPAManager | OPAClient | opa_manager.py vs opa_policy/DESIGN | 🔄 统一为 OPAManager（实现）+ IOPAManager（接口） |
| I-31 | PermissionChecker | PermissionDecisionService | permission_checker/DESIGN 中两名称 | 🔄 合并后统一为 OPAPermissionService |
| I-32 | IntelligenceAgent | Intelligence Analyst | 代码用前者，DESIGN 用后者 | 🔄 统一为 IntelligenceAgent（与 OODA 角色对齐） |
| I-33 | Episode | OntologyDocument | Graphiti 术语 vs 本体术语 | ✅ 已区分：Episode 是 Graphiti 存储单元，OntologyDocument 是业务语义单元 |

---

## 6. 优先级调整建议

| # | 当前 | 建议调整 | 理由 |
|---|------|---------|------|
| I-34 | M-05 Hook 系统 P1 | 维持 P1 | Phase 4 增强即可，不阻塞关键路径 |
| I-35 | M-06 MCP 协议 P1 | 维持 P1 | 外部集成非核心，Phase 4 补齐 |
| I-36 | M-11 工具注册表 P1 | ✅ P0（分步实现） | ADR-047 已决策：升级 P0，Step 1 核心接口随关键路径，Step 2 完整能力 P1 |
| I-37 | M-15 事件模拟器 P1 | 维持 P1 | 推演引擎 M-14 已有基础事件能力 |
| I-38 | M-13 决策推荐 P1 | 维持 P1 | 非 MVP 必需，但决策链路关键组件 |

---

## 7. 确认汇总

| 类别 | 条目数 | 需人工确认 | 建议删除 | 建议更新 | 已处理 |
|------|--------|-----------|---------|---------|--------|
| 文档级不相关 | 9 | 0 | 0 | 9 | 0 |
| 设计不一致 | 6 | 0 | 0 | 6 | 0 |
| 接口不一致 | 2 | 0 | 2 | 0 | 0 |
| 技术选型待确认 | 4 | 0 | 0 | 4 | 0 |
| 部署架构待确认 | 2 | 0 | 0 | 1 | 1 |
| 代码不相关 | 6 | 0 | 1 | 1 | 4 |
| 命名不一致 | 5 | 0 | 0 | 5 | 0 |
| 优先级调整 | 5 | 0 | 0 | 5 | 0 |
| **合计** | **39** | **0** | **1** | **28** | **10** |

### 亟需人工确认的 14 项 — 全部已处理

1. ~~**I-17** 🔴 ReGraph vs G6 图谱可视化选型~~ ✅ ADR-045 已决策：G6
2. ~~**I-21** 🔴 Phase 4 单体 vs 微服务部署~~ ✅ ADR-046 已决策：模块化单体
3. ~~**I-05** 🟡 ADR-022 状态确认~~ ✅ 维持"已接受"
4. ~~**I-06** 🟡 ADR-033 状态确认~~ ✅ 标记为"已接受"
5. ~~**I-36** 🟡 M-11 工具注册表 P0/P1~~ ✅ ADR-047：P0 分步实现
6. ~~**I-08** 🟡 req-beta 文档定位~~ ✅ 归档为历史参考
7. ~~**I-18** 🟡 CesiumJS vs Leaflet~~ ✅ ADR-045：Leaflet
8. ~~**I-19** 🟡 Redis 缓存层~~ ✅ Phase 4 不引入（YAGNI）
9. ~~**I-20** 🟡 消息队列~~ ✅ Phase 4 不引入（YAGNI）
10. ~~**I-22** 🟡 审计日志存储~~ ✅ ADR-042：SQLite + 哈希链
11. ~~**I-23** 🟢 `web/legacy/`~~ ✅ 归档到 docs/archive/
12. ~~**I-26** 🟢 `adapters/` vs `infra/`~~ ✅ adapters 并入 infra
13. ~~**I-27** 🟢 `biz/permission/`~~ ✅ 删除
14. ~~**I-28** 🟢 `simulator_ui/`~~ ✅ 目录不存在，记录有误
