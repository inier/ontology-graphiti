---
id: odap.l7.adr-090-子项目d-promote按attribution-layer路由-类型化编辑
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

# ADR-090: 子项目 D · `promote` 按 attribution.layer 路由——类型化编辑

## Status
**已接受（2026-10-09，v2 同日修订）。承接 ADR-088 子项目 A 的归因能力，把 `gap_service.promote` 单路径（仅 USL candidate）改为按 `attribution.layer` 路由到 USL candidate / ChangeProposal / tool_routing_ticket。本 ADR 记录 15 项关键决策（D-D1~D-D15），实施前需 spec 复审通过。**

> **v2 修订（用户 2026-10-09 指示「不倒过来，体系化解决」+「需要」+「不能按简单方式走，要考虑功能的完整性和可用性」）**：①优先级**保持体系化** `schema > tool > content`（不变）——结构问题先于术语解决，根因优先；②tool 路径升级为**完整工单工作流**（D-D11 状态机 / D-D12 优先级+SLA / D-D13 事件审计 / D-D14 前端界面）；③新增 D-D15 `route-preview` 端点。

> 触发来源：EvoOntology 论文「类型化编辑」机制——根据归因（schema / content / tool）决定编辑形态，避免把所有缺口都当成「缺一个术语」去解决。
> 承接链路：ADR-088 子项目 A 让 gap 带 attribution（知道缺什么 + 在哪一层）→ 本 ADR 让 promote 按 layer 路由（按层选编辑形态）；ADR-088 子项目 B 的配对回放作为变更的「效果验证」挂审批界面（不自动门控）。
> 关联：ADR-088（子项目 A 归因 / 子项目 B 配对回放）；ChangeProposal 已实现（`goal/models/proposal.py:46-115`，6 态状态机 + RFC 6902 校验）；Branch&Merge 已存在（goal 子包）；AGENTS.md 规则 2/3/6/9/12/14。

---

## Context

### 现状（证据见 spec §1 + 本轮代码勘验）

`gap_service.promote(gap_id, ...)`（`gap_pool/services/gap_service.py:58`）当前形态：

- 不论 `gap.attribution_counts` 内容，无条件调 `cs.create_candidate_from_gap(payload)`
- 后果：所有「结构性问题」（object_type 缺、relation_type 错）被错当成「术语问题」处理
- 这违背 EvoOntology 的「类型化编辑」原则——按归因决定编辑形态
- 也违背本项目根因诊断——结构问题不解决，术语补丁只是把锅甩给 LLM

EvoOntology 摘要（中文复述）：**「编辑不是『发现一个词缺定义』，而是先归因到 schema / content / tool 三层中的具体元素，再生成针对性修改。」** 项目已经做了归因（ADR-088），但 promote 端没用上。

### 问题陈述

当运营人工 promote 一个「schema 缺 object_type」的 gap 时，当前系统：

1. 把它路由到 `create_candidate_from_gap`——一条面向「术语/映射」的工作流
2. 候选审批人看到的是「缺术语」而非「缺 object_type」，可能错批
3. 即便批了，writeback 侧也是往 USL 写——不是往 schema 写，**改不了根因**
4. LLM 持续按幻觉生成候选，本体持续不收敛

`ChangeProposal`（`goal/models/proposal.py:46-115`）已实现：6 态状态机（draft → submitted → under-review → approved/rejected → implemented）、JSON Patch（RFC 6902）严格校验（op ∈ {add,remove,replace,move,copy,test}、必填 op/path 字段）、`ImpactAnalyzer` 已存在但计算昂贵。**现成的基础设施，缺的是把 gap 路由到它的胶水。**

`unified_router`（`semantic_retrieval/impl/unified_router.py`）已存在，但「引擎能力缺/路由缺」的工单表尚未建立——本 ADR 顺势建 `tool_routing_tickets`（最小集：open → resolved_by + note，不做复杂状态机）。

---

## Decisions

### D-D1. `promote` 加 `force_layer` 可选入参

```python
def promote(self, gap_id, *, actor, force_layer: str = None) -> dict:
    gap = self.storage.get_gap(gap_id)
    if not gap:
        return {"status": "error", "code": "GAP_NOT_FOUND_404", ...}
    routed = promote_router.route(gap, force_layer=force_layer)
    # ...
```

向后兼容：旧调用方不传 `force_layer` 时，行为 = 当前实现（`route()` 内部按 attribution 决策）；旧 gap 数据（无 attribution）走 content 路径，与现状一致。

### D-D2. 风险倒序路由优先级

`schema > tool > content`。理由：结构问题不解决，术语补丁是给 LLM 找借口；工具能力缺是工程债；术语错最末（已经「先验可观测」）。`force_layer` 优先级最高；归因计数 > 0 的层取风险最高。

### D-D3. `content` 路径：现状不动

`create_candidate_from_gap(payload)` 行为完全不变。`semantic_type` 透传（ADR-088 落地）。**这意味着既有 `test_gap_promote.py` 必须零回归**——验收红线。

### D-D4. `schema` 路径：ChangeProposal，不立即 ImpactAnalyzer

`ImpactAnalyzer` 计算昂贵（`goal/impl/impact_analyzer_impl.py:40`）。提案阶段只存 RFC 6902 ops，**不**调 ImpactAnalyzer；审批前由审批人手动跑（提供单独 CLI/端点）。这是 trade-off：

- 获：提案创建快（毫秒级），无昂贵计算
- 失：审批人需主动看爆炸半径（待办：把「提交时同步跑 ImpactAnalyzer」列为未来增强；本 ADR 不做）

`_build_schema_patch` 产 RFC 6902 列表；缺 attribution 时返回空 list（与 ADR-088「不造数」一致）。

### D-D5. `schema` 路径落 change_proposals 表

沿用 goal 子包既有 `change_proposals` 表（已核对字段无需 migration）。`goal_id` **由缺口 id 派生**为 `gap:<gap_id>`（实施定稿，替代初稿「从 scope_key 推导」）：缺口即该结构性变更的动因锚点，`gap:` 前缀可识别「非人工 Goal」来源，且保证「缺口 → 提案」双向可溯源。**不**伪造 Goal 行（不为自动衍生提案污染 Goal 看板）。gap 状态 `promoted`，`promoted_proposal_id` 回填。

**C3 契约**：`semantic_admin` 不得直连 `ontology.goal.*`，故 `goal` 子包新增公共工厂 `services/schema_proposal.py::create_schema_proposal()` 与 `storage.get_goal_storage()`，经 `odap.biz.core.ontology.public` 门面暴露（新增两个门面符号）。

### D-D6. `tool` 路径：完整工单工作流

落 `tool_routing_tickets` 表（**完整** schema：gap_id/engine/expression/scope_key/title/description/priority/status/assignee/sla_deadline/created_by/created_at/updated_at/resolved_at/resolved_by/resolution_note），gap 状态 `promoted`，`promoted_ticket_id` 回填。**不**调 `unified_router` 改路由规则——路由规则变更属更高风险动作，落独立工单等人工处理（与 D-D7 门控一致）。

**不**取「最小集」而是完整工作流（用户明确「需要」）：工程债需可跟踪、可度量、可闭环。详见 D-D11~D-D14。

### D-D7. 门控归人（与 ADR-088 一致）

ChangeProposal 与 routing ticket 都需人工审批后才会真改 schema/路由；promote 只创建提案不执行。**EvoOntology 的自动接受在这里不适用**——本项目本体挂 OPA 权限、审计关键路径、分支合并与版本不可变，爆炸半径与 EvoOntology 论文场景完全不同。ADR-088 D3 已立基线，本 ADR 是其延伸。

### D-D8. `promote_router` 单独模块

`promote_router.py` 负责 layer 决策 + payload 构造，**不改** `gap_service.promote` 主流程（保持薄壳——仅做错误码 + 三条 `_route_*` 私有方法的调度）。后续若加新 layer（如 `policy` 治理）只动 router。

### D-D9. 不接 pair-replay

ADR-088 子项目 B 的配对回放是给「自动改」用的门控；本 ADR 不自动改，所以不强制接。ChangeProposal 的 `model_validator`（`proposal.py:93-112`）已做 RFC 6902 静态校验，足以过滤「错误 patch」。

### D-D10. 旧数据兜底

未带归因的 gap（attribution_counts 为空）走 `content` 路径。与 ADR-088 D10「不造数」一致——不让 promote 路由对历史数据做「无依据 schema 路由」。

### D-D11. tool 工单状态机（6 态）

`open → assigned → in_progress → resolved → closed`，另有 `rejected` 终态；`resolved` 可复开回 `in_progress`。非法转换 → service 返回 `INVALID_TICKET_TRANSITION`，路由层 409（规则 14 失败显式）。状态机常量化于模型层（`TICKET_TRANSITIONS`），service 校验。

### D-D12. 优先级 P0~P3 + SLA 违约

`PRIORITY_SLA_HOURS = {P0:4, P1:24, P2:72, P3:168}`；创建/改优先级时按 priority 派生 `sla_deadline`；`sla_breached` **读取时计算**（`status ∉ 终态 ∧ now > sla_deadline`），列表/详情返回该布尔，`/stats` 聚合违约数。理由：违约是时间的函数，不落库避免「需要定时任务刷新」的复杂度；读时计算始终正确。

### D-D13. 事件审计表（只 INSERT）

`tool_routing_ticket_events` 记录 `created/assigned/transitioned/commented/priority_changed/sla_breached`，含 `from_status/to_status/actor/note/payload_json`。「报告即不可变证据」延伸——工单每次状态变化留痕，可审计、可回溯。**不做** UPDATE/DELETE。

### D-D14. 前端工单界面（完整性 + 可用性）

`RoutingTicketsPage`（统计卡 by_status/by_priority/违约数 + 过滤 + 表格，违约行红色高亮）+ `RoutingTicketDetailPage`（基本信息 + 事件时间线 Timeline + 按状态机禁用非法操作的按钮组）。路由 `/semantic-admin/routing-tickets[/:id]` 为**子路由非 Tab**（与 gaps 一致，不改 7 Tab 不变量）。入口：`GapDetailPage` promote 结果含 `ticket_id` 时提供跳转。

### D-D15. `route-preview` 端点（无副作用预览）

`GET /api/semantic-admin/gaps/{gap_id}/route-preview` 返回 `{status, layer, routed_to, target_kind, already_promoted}`，并按 layer 附送 `changes`（schema，RFC 6902 ops 列表）或 `engine`（tool），**不产生任何副作用**。运营 promote 前可预览将路由到哪，避免误 promote（可用性）。

## 实施记录（2026-10-09 落地）

**新增/修改文件**

| 层 | 文件 | 说明 |
|----|------|------|
| 路由（纯函数） | `gap_pool/services/promote_router.py` | `route/decide_layer/target_kind_for/build_schema_patch/attribution_for_layer` + `RouteResult`（frozen） |
| 编排 | `gap_pool/services/gap_service.py` | `promote` 改薄壳调度三路 `_route_to_candidate/_route_to_proposal/_route_to_ticket`；`route_preview`；`_goal_storage`/`_ticket_service` 注入点 |
| 存储 | `gap_pool/storage/sqlite_gap_storage.py` | 幂等加 `promoted_proposal_id`/`promoted_ticket_id` 两列；`update_status` 白名单扩列；`_sanitize_attribution` 白名单增加 `parent`（见下） |
| 工单子包 | `semantic_admin/routing_tickets/` | models（6 态状态机 + P0~P3 SLA）/storage（两表，只 INSERT 事件）/services/`TicketService`/api（7 端点） |
| 门面 | `core/ontology/public.py` | 新增 `create_schema_proposal`、`get_goal_storage` 两个公共符号（C3 唯一合法入口） |
| 门面实现 | `core/ontology/goal/services/schema_proposal.py` | 新建：构造 `ChangeProposal` + 落 `change_proposals`（draft） |
| 路由注册 | `web/router_registry.py` | 注册 `routing_tickets`（路由模块数 +1） |
| 前端 | `semantic-admin/services/routingTicketApi.ts`、`pages/RoutingTicketsPage.tsx`、`pages/RoutingTicketDetailPage.tsx`、`AppRoutes.tsx`、`routes.tsx`、`GapDetailPage.tsx`、`gapApi.ts` | 列表/详情页 + promote 下拉（含 force_layer）+ 路由预览卡 + 产物跳转 |

**实施中做的两项修正（如实登记）**

1. **`_sanitize_attribution` 白名单增加 `parent`（ADR-088 存储契约小幅放宽）**：schema 层 `property` 缺口需要「父对象类型」才能推导 RFC 6902 路径 `/object_types/<parent>/properties/<name>`；不保留 `parent` 则只能落到 `/object_types/Unknown/...`，提案不可用。仍是**白名单已知键**，不放行任意字段（`test_gap_attribution_storage.py::test_sanitize_keeps_parent_key_for_schema_property` 锁定）。
2. **修复 ADR-089（子项目 C）引入的 `EntityExtractor` 默认值回归**：C 给构造器加 `mode` 并默认 `"off"`，**覆盖**了 ADR-079 的上下文驱动行为（注入 `term_resolver`/`entity_set` 时应做归一化 + 本体集合过滤），导致 ADR-079 边界测试与 ADR-088 两处 emitter 接线测试失败。修法：`mode` 未显式指定时**按上下文推导**（有 `term_resolver`/`entity_set` → `inject`；皆无 → `off`），显式 `mode=`/`set_entity_context(mode=...)` 仍以显式为准。

## Status & Verification

- **状态**：**已实施**（2026-10-09）。spec v2 已落稿并同步实施。
- **Spec**：`docs/superpowers/specs/2026-10-09-subproject-d-promote-routing-design.md`
- **测试**：新增 7 个测试文件（`test_promote_router` / `test_promote_schema_path` / `test_promote_tool_path` / `test_promote_routes` / `test_promote_loop_acceptance` / `test_ticket_*` 5 个）+ 前端 `routingTicketApi.test.ts` / `RoutingTicketsPage.test.tsx`，全绿。
- **回归红线**：`test_gap_promote.py` / `test_gap_attribution_*`（ADR-088）/ `test_regression_*`（ADR-088）/ `test_goal.py` / `test_adr079_llm_boundary.py` / `test_nl_query_service.py` 全绿（93 passed 验证批次）。
- **lint-imports**：C1/C2/C3/C4 **4 契约全部 KEPT**（C3 经门面新增符号满足，未引入深插违规）。

## 备选方案（未采用）

1. **把 schema/tool 路径也走 create_candidate**：候选审批人会被错路由误导（schema 问题被当成术语），否决。
2. **直接在 schema 路径调 ImpactAnalyzer 并阻塞**：提案创建慢（可能数秒），且被驳回时浪费算力。
3. **tool 路径直接调 `unified_router.register_rule` 改路由**：工具能力变更风险高，绕过人工门控，否决。
4. **为 tool 路径建「最小集」工单（open → resolved_by + note，无状态机/SLA）**：用户明确要求完整工单，最小集不能满足「可跟踪/可度量/可闭环」，否决。
5. **为 promote 路由做缓存**：低频管理动作（人工手动 promote），缓存无收益，复杂度徒增。
