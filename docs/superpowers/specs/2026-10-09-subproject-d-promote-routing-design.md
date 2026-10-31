---
id: odap.l15.specs-2026-10-09-subproject-d-promote-routing-design
status: reference
owner: architect
version: ''
layer: L15
concern: design-spec-record
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: superpowers 设计规格存档，结论已落 ADR 或代码，规格本身冻结
governance_evidence: docs/07-adr/README.md 各 ADR 的 specs 引用（如 ADR-087 引用 2026-10-07-semantic-drift-detection-design）
---

# 子项目 D · `promote` 按 attribution.layer 路由——类型化编辑 + 完整路由工单工作流

- **状态**：**已实施**（v2，2026-10-09 纳入用户三项指示；已按本 spec 以 TDD 落地，见 ADR-090「实施记录」）
- **日期**：2026-10-09
- **对应 ADR**：ADR-090（开工前落稿，规则 12）
- **来源 spec**：`docs/superpowers/specs/2026-10-08-evoontology-adoption-design.md` §4.3
- **承接**：ADR-088 子项目 A 让 gap 带 attribution，但 `gap_service.promote` 仍是单路径（只走 USL candidate）；本 spec 把 promote 改为按 layer 路由。

## v2 修订说明（用户 2026-10-09 指示）

用户指示：**「不倒过来，体系化解决」**（保持 `schema > tool > content` 风险倒序优先级）+ **「需要」**（tool 路径要完整工单工作流）+ **「不能按简单方式走，要考虑功能的完整性和可用性」**。据此本版修订：

- **优先级保持体系化**（C-D2/D-D2 不变）：结构问题（schema）先于术语（content）解决——根因优先。
- **tool 路径升级为完整工单工作流**：原 v1「最小集 open → resolved_by + note」改为**完整状态机 + 分配 + 优先级 + SLA 与违约检测 + 事件审计 + 评论**。
- **新增前端工单界面**：列表页（过滤/统计/批量视图）+ 详情页（事件时间线 + 操作）。

## 背景

`gap_service.promote(gap_id, ...)`（`gap_pool/services/gap_service.py:58`）当前对所有 gap 无条件调 `cs.create_candidate_from_gap(payload)`——所有「结构性问题」（object_type 缺、relation_type 错）被错当成「术语问题」处理，违背 EvoOntology「类型化编辑」原则，也让本体无法收敛。

项目已有 `ChangeProposal`（`goal/models/proposal.py:46-115`，6 态状态机 + RFC 6902 严格校验）、`ImpactAnalyzer`（`goal/impl/impact_analyzer_impl.py:40`）、`Branch/MergeRequest/ThreeWayMergeEngine`。缺的是把 gap 路由到它们的胶水，以及 tool 路径的**工程债承载系统**。

## 已锁定决策表

| 编号 | 决策 | 理由 |
|------|------|------|
| D-D1 | `promote` 加可选 `force_layer`（None = 按 attribution 自动） | 向后兼容；带归因的 gap 自动走对应路径 |
| D-D2 | **风险倒序优先级 `schema > tool > content`**（保持体系化，不倒过来） | 结构问题不解决，术语补丁只是把锅甩给 LLM；根因优先 |
| D-D3 | `content` 路径：`create_candidate_from_gap` 行为完全不变 | 既有 `test_gap_promote.py` 零回归红线 |
| D-D4 | `schema` 路径：构造 `ChangeProposal`（RFC 6902），**不立即**跑 ImpactAnalyzer（审批前手动跑） | 提案创建快；避免被驳回时浪费算力 |
| D-D5 | `schema` 路径落 `change_proposals` 表（沿用 goal 既有存储）；gap 状态 `promoted`，`promoted_proposal_id` 回填 | 复用既有基础设施 |
| D-D6 | **`tool` 路径：完整工单工作流**（见 §3）——状态机 + 分配 + 优先级 + SLA + 事件审计 + 评论；落 `tool_routing_tickets` + `tool_routing_ticket_events` 两表 | 用户明确「需要」完整工单；工程债需可跟踪、可度量、可闭环 |
| D-D7 | 门控归人：ChangeProposal 与工单都需人工审批/处理后才真改；promote 只创建不执行 | 与 ADR-088 基线一致；EvoOntology 自动接受在本项目不适用 |
| D-D8 | `promote_router` 单独模块，`gap_service.promote` 保持薄壳调度三条 `_route_*` | 职责单一；后续加 layer 只动 router |
| D-D9 | 不接 pair-replay（不自动改无必要；RFC 6902 静态校验足够） | 与 ADR-090 一致 |
| D-D10 | 旧数据（无 attribution）走 `content` 路径 | 与 ADR-088 D10「不造数」一致 |
| **D-D11** | **tool 工单状态机**（6 态）：`open → assigned → in_progress → resolved → closed`，另 `rejected` 终态；非法转换 → 409 | 完整可跟踪；非法转换显式报错（规则 14） |
| **D-D12** | **优先级 P0~P3 + SLA**：P0=4h / P1=24h / P2=72h / P3=168h（创建时按 priority 派生 `sla_deadline`）；读取时计算 `sla_breached`（now > deadline 且未终态） | 工程债可度量；违约可见 |
| **D-D13** | **事件审计表 `tool_routing_ticket_events`**（created/assigned/transitioned/commented/priority_changed/sla_breached），只 INSERT | 「报告即不可变证据」延伸；操作留痕 |
| **D-D14** | **前端工单界面**：`RoutingTicketsPage`（列表 + 过滤 + 统计）+ `RoutingTicketDetailPage`（事件时间线 + assign/transition/comment 操作）；路由 `/semantic-admin/routing-tickets[/:id]`（**子路由非 Tab**，与 gaps 一致，不改 7 Tab 不变量） | 完整性 + 可用性；工程债可见可操作 |
| **D-D15** | 新增端点 `GET /api/semantic-admin/gaps/{gap_id}/route-preview` 返回将路由到哪（layer/routed_to/target_kind），**无副作用** | 运营 promote 前可预览，避免误 promote |

## 关键事实（实施前必看）

| 事实 | 来源 |
|------|------|
| `gap_service.promote` 现仅调 `create_candidate_from_gap` | `gap_pool/services/gap_service.py:58-82` |
| `ChangeProposal` 已实现，6 态状态机 + RFC 6902 校验 | `goal/models/proposal.py:23-115` |
| `ImpactAnalyzer`（接口/实现）已存在，计算昂贵 | `goal/interfaces/impact_analyzer.py:15` / `goal/impl/impact_analyzer_impl.py:40` |
| `Branch` / `MergeRequest` / `ThreeWayMergeEngine` 已存在（goal 子包） | `goal/impl/` |
| 既有 `create_candidate_from_gap` payload 含 `semantic_type`（ADR-088 透传） | `candidate_store/services/candidate_service.py:660-720` |
| gap 状态机：`open → promoted/rejected/adopted` | `gap_pool/models/gap.py`（ADR-086） |
| `unified_router` 在 `semantic_retrieval/impl/`；工单两表待建 | 实施时核对 |
| 前端 gaps 是子路由非 Tab（`/semantic-admin/gaps/*`） | `AppRoutes.tsx:131-133` |
| `concept_gaps` 表 ADR-088 已加 attribution 列 + `attribution_counts_json` | ADR-088 落地 |

## 设计

### 1. `promote_router.route(gap, force_layer=None) → RouteResult`

```python
@dataclass(frozen=True)
class RouteResult:
    layer: str          # 'content' | 'schema' | 'tool'
    target_kind: str    # 'term' | 'object_type' | 'relation_type' | 'property' | 'engine'
    payload: dict
    routed_to: str      # 'candidate_store' | 'change_proposal' | 'tool_routing'
```

`_decide_layer(gap)`：无 attribution → `content`；否则按 `schema > tool > content` 取计数 > 0 的最高风险层。

### 2. `gap_service.promote` 集成（薄壳）

```python
def promote(self, gap_id, *, actor, force_layer=None):
    gap = self.storage.get_gap(gap_id)
    if not gap:
        return {"status": "error", "code": "GAP_NOT_FOUND_404",
                "message": f"缺口 {gap_id} 不存在"}
    routed = promote_router.route(gap, force_layer=force_layer)
    if routed.routed_to == "candidate_store":
        return self._route_to_candidate(gap, actor, routed)
    if routed.routed_to == "change_proposal":
        return self._route_to_proposal(gap, actor, routed)
    if routed.routed_to == "tool_routing":
        return self._route_to_ticket(gap, actor, routed)
    raise RuntimeError(f"unknown routed_to: {routed.routed_to}")
```

### 3. tool 路径：完整工单工作流（D-D6/D-D11/D-D12/D-D13）

**新子包** `biz/semantic_admin/routing_tickets/`（标准 7 层；semantic_admin 第 11 个子服务）：
`models/ticket.py`、`storage/sqlite_ticket_storage.py`、`services/ticket_service.py`、`api/routes.py`。

**表 1 `tool_routing_tickets`**：

```sql
CREATE TABLE IF NOT EXISTS tool_routing_tickets (
    id TEXT PRIMARY KEY,
    gap_id TEXT,
    engine TEXT NOT NULL,              -- 缺能力的检索引擎
    expression TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT NOT NULL DEFAULT 'P2',      -- P0|P1|P2|P3
    status TEXT NOT NULL DEFAULT 'open',      -- open|assigned|in_progress|resolved|rejected|closed
    assignee TEXT,                            -- 处理人 id
    sla_deadline TEXT,                        -- ISO；创建/改优先级时按 priority 派生
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by TEXT,
    resolution_note TEXT
);
CREATE INDEX IF NOT EXISTS idx_ticket_status   ON tool_routing_tickets(status);
CREATE INDEX IF NOT EXISTS idx_ticket_assignee ON tool_routing_tickets(assignee);
CREATE INDEX IF NOT EXISTS idx_ticket_priority ON tool_routing_tickets(priority);
CREATE INDEX IF NOT EXISTS idx_ticket_gap      ON tool_routing_tickets(gap_id);
```

**表 2 `tool_routing_ticket_events`**（审计，只 INSERT）：

```sql
CREATE TABLE IF NOT EXISTS tool_routing_ticket_events (
    id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    event_type TEXT NOT NULL,   -- created|assigned|transitioned|commented|priority_changed|sla_breached
    from_status TEXT,
    to_status TEXT,
    actor TEXT NOT NULL,
    note TEXT,
    payload_json TEXT,          -- 结构化补充（如 from/to priority）
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ticket_event_ticket ON tool_routing_ticket_events(ticket_id);
```

**状态机**（D-D11）：

```python
TICKET_TRANSITIONS = {
    "open":        ["assigned", "rejected"],
    "assigned":    ["in_progress", "open", "rejected"],
    "in_progress": ["resolved", "rejected", "assigned"],
    "resolved":    ["closed", "in_progress"],   # 可复开
    "rejected":    [],                           # 终态
    "closed":      [],                           # 终态
}
```

非法转换 → service 返回 `{"status":"error","code":"INVALID_TICKET_TRANSITION","message":...}`，路由层 409。

**SLA**（D-D12）：`PRIORITY_SLA_HOURS = {"P0":4,"P1":24,"P2":72,"P3":168}`；`sla_breached` 读取时计算（`status ∉ 终态 ∧ now > sla_deadline`）；列表/详情返回该布尔；`/stats` 聚合违约数。

**API 端点**（`/api/semantic-admin/routing-tickets`）：

```
GET    /                              list（过滤 status/priority/assignee/engine/page）
GET    /stats                         聚合（by_status/by_priority/breached_count/avg_age_hours）
GET    /{id}                          详情（含 sla_breached）
GET    /{id}/events                   事件时间线
POST   /{id}/assign                   body {assignee, priority?}   → assigned 态
POST   /{id}/transition               body {to_status, note?}      → 状态机校验
POST   /{id}/comment                  body {note}                  → 仅留痕
```

`_route_to_ticket`（在 `gap_service`）创建工单时：`status=open`、`priority=P2`（缺省）、`sla_deadline=now+72h`，写 `created` 事件，回填 `gap.promoted_ticket_id`，gap 状态 `promoted`。

### 4. `schema` 路径（D-D4/D-D5）

构造 `ChangeProposal`（`changes=_build_schema_patch(gap, routed)`），落 `change_proposals`，gap `promoted` + `promoted_proposal_id` 回填。`_build_schema_patch` 按 `target_kind` 产 RFC 6902 ops（object_type/relation_type/property）；缺 attribution → 空 list + warning（不造数）。

### 5. storage 改动

`concept_gaps` 加两列（幂等迁移，同 ADR-088 模式）：

```sql
ALTER TABLE concept_gaps ADD COLUMN promoted_proposal_id TEXT;
ALTER TABLE concept_gaps ADD COLUMN promoted_ticket_id TEXT;
```

### 6. 前端（D-D14）

- `services/routingTicketApi.ts`：list/stats/detail/events/assign/transition/comment 7 个调用
- `pages/RoutingTicketsPage.tsx`：统计卡（by_status/by_priority/违约数）+ 过滤 + 表格（优先级 Tag、状态 Badge、SLA 违约红色高亮、assignee）
- `pages/RoutingTicketDetailPage.tsx`：基本信息卡 + 事件时间线（Timeline）+ 操作（分配/流转/评论，按状态机禁用非法按钮）
- 路由：`AppRoutes.tsx` 加 `/semantic-admin/routing-tickets` 与 `/:id`；`routes.tsx` 元数据同步
- 入口：`GapDetailPage` promote 结果含 `ticket_id` 时可跳转（可用性）

## 测试策略

| 编号 | 场景 | 期望 | 测试文件 |
|------|------|------|---------|
| E-1 | 无归因 promote | 走 candidate_store，行为零变化 | `test_promote_router.py` |
| E-2 | `force_layer=content` | 忽略归因强制 content | 同上 |
| E-3 | `layer=schema` | 走 change_proposal；`promoted_proposal_id` 非空；changes 是 RFC 6902 | `test_promote_schema_path.py` |
| E-4 | schema patch 校验 | 非法 op/缺 path → ChangeProposal 报错 | 同上 |
| E-5 | `layer=tool` | 建工单（open/P2/sla_deadline=now+72h）；`promoted_ticket_id` 非空；写 created 事件 | `test_promote_tool_path.py` |
| E-6 | `_decide_layer` 优先级 | schema(3)+content(2) → schema | `test_promote_router.py` |
| E-7 | storage 幂等迁移 | 旧库无新列能启动 | `test_gap_attribution_storage.py` 加断言 |
| E-8 | 工单状态机合法/非法 | 合法转变落事件；非法 → INVALID_TICKET_TRANSITION | `test_ticket_state_machine.py` |
| E-9 | 工单分配 + 改优先级 | assignee 落库；改 P0 → sla_deadline 重算 + 事件 | `test_ticket_service.py` |
| E-10 | SLA 违约计算 | 过期未终态 → sla_breached=True；/stats 计数 | `test_ticket_sla.py` |
| E-11 | 事件审计 | 每操作一行，只 INSERT | `test_ticket_events.py` |
| E-12 | 工单端点 | 7 端点状态码/鉴权/异常透传 | `test_ticket_routes.py` |
| E-13 | `route-preview` | 返回 layer/routed_to，无副作用 | `test_promote_routes.py` |
| E-14 | 端到端 | gap(attribution=schema) → promote → proposal 落库 | `test_promote_loop_acceptance.py` |
| E-15 | 门控 | ChangeProposal status=draft，不自动改 schema | `test_change_proposal_not_auto_implemented.py` |
| E-16 | 前端工单列表/详情 | 渲染 + 操作调用 | `routingTicketApi.test.ts` / `RoutingTicketsPage.test.tsx` |

回归红线：`test_gap_promote.py` / `test_gap_attribution_*`（ADR-088）/ `test_regression_*`（ADR-088）零回归。

## 文档同步

| 文件 | 改动 |
|------|------|
| `docs/03-modules/README.md` | routing_tickets 第 11 子服务条目；gap_pool 条目补 routed_to |
| `docs/03-modules/README.md` 路由计数 | 路由模块数 +1（104→105）；端点数更新 |
| `AGENTS.md` 附录 E | 加 `/api/semantic-admin/routing-tickets*` + `route-preview` |
| `docs/superpowers/specs/2026-10-08-*.md` §4.3 | 「待立项框」改「子项目 D 已完成」 |
| `docs/07-adr/README.md` | ADR-090 已登记（v2 追加 D-D11~D-D15） |

## 验收标准

- **代码**：16 个新测试文件全绿；既有 gap_pool/change_proposal 测试零回归。
- **lint-imports**：4 契约保持 KEPT。
- **手验**：
  1. 造 attribution=`tool` 的 gap → promote → `/api/semantic-admin/routing-tickets` 列表出现该工单（open/P2）。
  2. 界面：分配 → in_progress → resolved → closed；每步详情页时间线新增事件；改 P0 后 SLA deadline 变 4h。
  3. 非法流转（open→resolved）界面禁用 + 直接 API 返回 409。
  4. `GET /api/semantic-admin/gaps/{id}/route-preview` 对 schema gap 返回 `layer=schema, routed_to=change_proposal`。
- **回归**：gap_pool 全量 + ADR-088 全部测试绿。

## 非目标

- **不**改 ChangeProposal 状态机或 ImpactAnalyzer 实现。
- **不**接 pair-replay（D-D9）。
- **不**动 Branch/MergeRequest 流程（审批后用户手动走）。
- **不**做工单的自动升级/提醒推送（SLA 违约仅**计算与展示**，不发通知；如需通知另起 spec）。
- **不**为 promote 路由做缓存（低频管理动作）。
- **不**改 `create_candidate_from_gap` 接口。
- **不**对 schema 路径做 Effect 校验（仅 op/path 静态校验；ImpactAnalyzer 审批前手动跑）。
- **不**改 7 个顶层 Tab（工单界面挂子路由，与 gaps 一致）。
