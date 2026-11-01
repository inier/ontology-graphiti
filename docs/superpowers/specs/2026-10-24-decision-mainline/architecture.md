---
id: odap.l15.specs-2026-10-24-decision-mainline-architecture
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

# 决策主线贯通 —— 技术架构 Spec

- 状态：Draft（待 Phoenix 评审）
- 日期：2026-10-24
- 分支：`feat/semantic-gap-drift`（禁止 commit / push / 切分支 / 改依赖）
- 基线 ADR：ADR-076（决策一等公民）、ADR-051（闭环反馈）、ADR-074（HE/Graphiti 分层）、ADR-023/041（工作空间隔离）、ADR-028（OPA）
- 关联产出：同目录 `api-spec.yaml`（OpenAPI 3.0 sidecar，前后端联调唯一契约）

---

## 0. 结论摘要

| 项 | 结论 |
|---|---|
| 收敛方案 | 三个「结论型」链（pipeline / record / recommendation）funnel 到已存在的 `DecisionService.record_decision()` 单一写入口；`agent` 链的 5 个端点**整体下线**（含跨空间 IDOR），列表粒度并入台账 `?agent_id=`，推理步骤粒度迁到 `…/reasoning-steps` 并落权威存储。新增 `decision_hub` 包只承担读侧与编排，**不重写任何既有编排逻辑** |
| 新增端点 | **7 个 = 5 + 2**。台账/队列/执行族 5 个（台账、队列、单条裁决、执行、批量裁决）+ 推理步骤族 2 个（读/写）。后 2 个不是净新增能力，而是 `POST\|GET /api/agent/decisions/{id}/steps` 下线后的等价承接，故能力口径记 5、路径口径记 7。**CSV 导出已降 P1，不在本期** |
| 删除端点 | 5 个（`/api/agent/decisions` 的 list / create / get / chain / steps） |
| 既有端点 | **零改动 6 个**（含 `GET /{id}/chain`、`GET /{id}/impact`、`GET /similar` 三个被复用的只读端点，行为不变，见 §3.10）；`POST /api/decisions` 仅 +1 可选字段 |
| 数据模型 | 新增 5 字段：`status`（6 态）、`entry_source`（7 值）、`recommended_action`（可执行载荷）、`resolution`（裁决留痕）、`status_assumed`（存量推定标记）；`DecisionOutcome` 五态**零变更**；推理步骤复用既有 `reasoning_trace` |
| 任务数 | 12 个（含 1 个 P0 前置 + 1 个演示数据 + 1 个 AC-17 收口），≈ **14.4 人日**（初版 12.5 → +T11 0.5 → +契约扩展 0.5 → +T6 0.2 → −CSV 导出 0.3 → −evidence_count 排序 0.3 → +`update_outcome` 改签名 0.2 → −错误处理缩面 0.1 → +详情页第二信号读取 0.5 → +AC-17 收口 0.7；加减明细见 §10） |
| 最大风险 | **JWT `ws_id` 恒为空 → 现有 7 个决策端点全部 422**。不修这个，决策主线端到端 100% 演示不通（§9 B-1） |
| 安全收口 | `GET /api/agent/decisions` 跨空间返回全量（`decision_service.py:87` `if workspace_id:` falsy 即不过滤）+ 单条读取无隔离（IDOR）。本 Spec **下线而非修补**，迁移映射见 §3.8 |
| 与 PRD 的偏离 | 已全部裁定闭合：B-1（workspace 切换）批准并立为 T1；B-2 批准新增 `status`，PM 撤回派生规则并补三条约束（本文 §5.1.2 / §4.3 / §3.2 已承接）；B-3 口径确认 |
| 契约版本 | `api-spec.yaml` **1.5.0**（1.4.0 → 1.5.0 **无行为变化**：`ErrorResponse` 更名 `ErrorEnvelope` 对齐 AC-17；按 AC-17 锁定"决策模块路由体内禁止 `raise HTTPException`"，`403` / `404` / 模块级 `422` 从 `ErrorDetail` 迁到信封并各自带上 `error.code`；新增 `ErrorCodeCatalog` 穷举 13 个码。前端改动集中在 `parseApiError` 一处） |
| 状态 | 8 轮反馈全部落地：team-lead 5 条输入（B-1/B-2/B-3 裁定、404 修正、T11、execute 从 `decided` 发起）见 §9.1；第 6 轮（设计侧 4 项 + PM 的〈同步窗口〉/〈已回滚〉/〈状态矩阵〉三条）见「第 6 轮新增裁决」；第 7 轮（错误信封自查）见「第 7 轮」；**第 8 轮（`APIError` 实为活代码、`status` 写点、`execute` 写 `action_status`、列表不出同步中）见「第 8 轮」** |

---

## 1. 现状差异矩阵

### 1.1 四条链实测

| 维度 | ① agent decision | ② decision_pipeline | ③ decision_recommendation | ④ decision_record |
|---|---|---|---|---|
| 路由文件 | `odap/biz/core/agent/api/decision_routes.py` | `odap/biz/decision/decision_pipeline/routes.py` | `odap/biz/decision/decision_recommendation/api/routes.py` | `odap/biz/decision/decision_record/api/routes.py` |
| 前缀 | `/api/agent/decisions` | `/api/decision-pipeline` | `/api/decision` | `/api/decisions` |
| 端点数 | 5 | 4 | 5 | 7 |
| 职责 | ReAct 步骤过程留痕（OBSERVE/ORIENT/DECIDE/ACT） | 5 段流水线：analyze→decide→validate→perform→feedback | LLM 推荐生成/风险评估/采纳审计 | 决策对象 CRUD + 因果/证据/影响 |
| 存储 | **进程内 dict**（`DecisionService._decisions`），重启即失 | 无自有存储，写 Graphiti 图 | **进程内 list**（`engine._history`），重启即失 | Neo4j `:Decision` 节点 + 4 类边 |
| 是否写 `DecisionRecord` | **否** | 是（`pipeline.py:248-253`，失败不阻断） | **否** | 是（本身即写入口） |
| decision_id 是否穿透到 Action | 否 | 是（`pipeline.py:611` `ActionRequest.decision_id`） | 否 | 间接（`link_triggered_action`） |
| outcome 是否回填 | 否 | 是（`pipeline.py:659-692`） | 否 | 是（`PATCH /{id}/outcome`） |
| `workspace_id` 来源 | body/query 透传，**无校验、可空**（`decision_service.py:87` `if workspace_id:` falsy 即不过滤） | `assert_workspace_access` | **无 workspace 概念** | `get_current_workspace`（JWT 声明，缺失 422） |
| ID 形态 | `uuid4()`（36 字符带横线） | `dec_{12hex}` | `recommendation_id`（独立命名空间） | `dec_{12hex}` |
| 前端入口 | `AgentPage.tsx:47` 决策 Tab（**恒传 `undefined`**） | 无（仅 `/simulation` 间接） | 无 | `/decisions`（`AppRoutes.tsx:117`，需手输决策 ID） |
| 判断 | **过程记录 + 跨空间暴露（G6）→ 本期下线** | **决策生产者 + 执行者（已贯通）** | **推荐生产者，非决策对象** | **决策对象权威存储，读能力不全** |

### 1.1.1 agent 链的隔离缺陷（G6，team-lead 实测）

四跳链路，每跳独立可复现：

| 跳 | 位置 | 行为 |
|---|---|---|
| 1 | `web/src/modules/agent/pages/AgentPage.tsx:47` | `loadDecisions(undefined, 1, 20)`，显式传 `undefined` |
| 2 | `web/src/modules/agent/services/agentApi.ts:80-88` | `if (workspaceId) qs.set('workspace_id', ...)`，falsy 就不写查询串 |
| 3 | `api/decision_routes.py:39-51` | `workspace_id: Optional[str] = None` 直接透传 service，**无 `assert_workspace_access`、无 `get_current_workspace`、无非空拒绝** |
| 4 | `api/services/decision_service.py:87` | `if workspace_id:` —— falsy 则跳过过滤，返回 `self._decisions` **全量（所有工作空间）** |

比列表泄露更严重的一层：`decision_routes.py:13` `GET /{decision_id}` 与 `:26` `GET /{decision_id}/chain` **连 workspace 参数都没有**，`get_decision(decision_id)` 按主键直取 → 凭 ID 即可越权读取任意空间的决策详情与推理步骤（**IDOR**）。且 `_decisions` 是进程级单例、不按 workspace 分区，不同用户创建的决策共处一个字典。

**修复口径**：不接受"前端补传 workspace"（那是把"空 = 全量"换成"伪造 = 越权"，性质不变，且违反 ADR-076 §7 的信任模型）。本 Spec 直接**下线该链 5 个端点**，见 §3.8 迁移映射与 §9.1 裁决记录。

### 1.2 由此得出的四条结论

1. **写入口其实已经不散了**。`pipeline` 与 `record` 都落在 `DecisionService.record_decision()`；真正散的是**读入口**——台账/队列根本没有，前端只能手输 `dec_xxx` 才能看到数据。
2. **`agent` 与 `recommendation` 产出的是「过程」和「推荐」，不是「决策」对象本体**。但 agent 的**推理步骤**是决策的可审计附属物，必须落在决策对象上（`reasoning_trace` 字段已存在），不能留在进程内存里。
3. **`DecisionRecord` 丢了可执行载荷**。`_build_decision_record`（`pipeline.py:629-657`）只保留了 `option.name`，`action_type_id / target_object_id / target_object_type / parameters` 全部丢失。结果是：即使做出台账和待决策队列，点"裁决通过 → 执行"这一步也没有参数可提交。这是本次必须补的字段。
4. **`agent` 链的问题不是"两套存储不一致"，是隔离在该 Tab 未生效**。所以 A4「单一数据源」必须与 G6「跨空间收口」做成同一个交付物——拆开做等于先统一读路径、把旧接口留成后门。

---

## 2. 收敛方案

### 2.1 分层与包位置

新增包：`apps/api/odap/biz/decision/decision_hub/`

**为什么放这里**：

- `odap.biz.decision` 已是 ADR-076 的领域根，`decision_hub` 与 `decision_record` / `decision_pipeline` / `action_service` 是**兄弟包**，依赖方向 `hub → record/action` 单向向下，无环。
- 不能放 `odap.infra`：import-linter C4 禁止 `infra → biz`。
- 不能放 `odap.web`：C2 禁止 `biz → web`，而 hub 必须被 biz 内的路由装配。
- 不能放 `odap.biz.core.ontology`：C3 把 `odap.biz.core.ontology.*` 的 22 个子包列为 forbidden，hub 一旦需要本体能力只能经 `odap.biz.core.ontology.public` 门面，放进去等于自投 forbidden 名单。
- 复用 `decision_record` 内部能力无需跨模块：`DecisionService.store` 是公开属性，`api/routes.py:207` 已有 `service.store.get_decision(...)` 的既存用法，hub 沿用同一手法读 store，**因此完全不改 `decision_service.py`（259 行，逼近 300 行硬上限）**。

### 2.2 「薄壳 vs 重写」边界（评审必读）

| 对象 | 决策 | 理由 |
|---|---|---|
| `decision_pipeline/pipeline.py` | **不重写**，仅 +2 行字段映射 | 5 段流水线是已验证可用的编排；重写等于把 demo 押在 715 行存量代码的重构上。用户要的是"串起来"，不是"推倒" |
| `decision_pipeline/routes.py` | **不改**（4 端点、响应契约零变化） | 向后兼容 |
| `action_service` | **不改**（仅修 `feedback_loop.py:45` 一处取值 bug） | 已有 `decision_id` 列 + `idx_action_decision` 索引，能力齐备 |
| `decision_recommendation`（873 行） | **不改**，改为前端在"采纳"时调 `POST /api/decisions` | 推荐是**无状态计算**，把它变有状态（`record=true`）会让纯计算端点依赖 workspace 解析并引入 422 风险面。"推荐→决策"本质是用户动作，必须由用户显式落到唯一写入口 |
| `core/agent/api/decision_routes.py` | **整体下线 5 个端点**（删除 router 与 `router_registry` 注册），列表粒度并入 `GET /api/decisions?agent_id=`，步骤粒度迁 `…/reasoning-steps` | 三端点列表/单条/链全无 workspace 隔离（G6，含 IDOR），修补仍留第二个决策入口。且其 `DecisionChain` 模型（`uuid4` 主键、无 workspace 分区、进程内单例）与决策对象语义冲突，接图等于重写。下线成本低于修补（§3.8 迁移映射） |
| `core/agent/services/decision_service.py`（内存单例） | **保留进程内 dict 仅作为"未落库步骤缓冲"**，对外暴露的方法全部要求 `workspace_id` 且做归属校验；不再提供 list/chain | 避免一次性删除引发 ImportError；缓冲不承担任何读取职责，读取统一走图库。T7 完成后该 dict 可进一步删除 |
| `decision_record/` 7 端点 | **不改路径/响应**，`POST ""` 仅 +1 请求字段 `entry_source` | 向后兼容（缺省 `manual`） |
| `Neo4jDecisionStore` | **按读/写拆分**（408 行 → 288 + 276） | 408 行已超 300 硬上限，禁止在超限文件里继续堆新逻辑 |

### 2.3 ASCII 调用图

```
   场景 / 问答 (web)               ┌──────────── 表现层 ────────────┐
   /qa  /simulation               │ modules/decision/pages         │
        │  "记为决策"               │  DecisionLedgerPage   (台账)   │
        ├─────────────────────────▶│  DecisionQueuePage    (队列)   │
        │                         │  DecisionIntelligencePage(溯源)│
   AgentPage 决策 Tab ─────────────▶│  （改读台账 ?agent_id=）        │
        │  （不再打 /api/agent/*）  └───────────────┬────────────────┘
        │                                          │ Bearer JWT
   ┌─────────────── 路由层 odap/biz/decision/*/api/routes ─────────────────┐
   │ decision_record_router   /api/decisions        (7 存量端点, 不改)      │
   │ decision_hub_router      /api/decisions        (8 新增端点)            │
   │ decision_pipeline_router /api/decision-pipeline(不改)                  │
   │ decision_recommendation  /api/decision         (不改)                  │
   │ [已删除] agent_decision_router /api/agent/decisions  ← G6 下线         │
   └────────┬──────────────────────────────────┬───────────────────────────┘
            │ (新)                             │ (存量)
   ┌────────▼─────────────┐          ┌─────────▼───────────────────┐
   │ 编排层 DecisionHub   │          │ DecisionPipeline (5 段)      │
   │ list_ledger          │          │ analyze→decide→validate      │
   │ list_pending         │          │ →perform→feedback            │
   │ resolve (状态机)      │          └─────────┬───────────────────┘
   │ execute (→ActionReq) │                    │
   └────────┬─────────────┘                    │
            │        ┌─────────────────────────┘
            │        │ 漏斗：唯一写入口
   ┌────────▼────────▼──────────────────────────────────┐
   │ 服务层 DecisionService  (decision_record/services) │
   │ record_decision / trace_chain / find_similar /      │
   │ analyze_impact / add_causal_relationship /          │
   │ check_decision_rules / update_outcome /             │
   │ link_triggered_action                               │
   └────────────────────┬───────────────────────────────┘
                        │ IDecisionStore
   ┌────────────────────▼───────────────────────────────┐
   │ 存储层                                              │
   │  Neo4jDecisionStore        (写: 节点/边/outcome)    │
   │  Neo4jDecisionQueryStore   (读: 链/similar/impact/  │
   │                             台账分页/计数/CAS 迁移)  │
   │  ∟ :Decision 节点                                   │
   │  ∟ -[:DERIVED_FROM]-> Entity / Episodic             │
   │  ∟ -[:CAUSED_BY|INFLUENCED_BY|PRECEDENT_FOR]-> Decision
   │  ∟ -[:TRIGGERED]-> ActionRecord                     │
   └────────────────────▲───────────────────────────────┘
                        │ decision_id 全链路穿透
   ┌────────────────────┴───────────────────────────────┐
   │ ActionService (submit_action / approve_and_execute) │
   │   ∟ ActionRecord.decision_id  (SQLite, idx_action_decision)
   │ FeedbackLoop (close_loop) → outcome 回填             │
   └────────────────────────────────────────────────────┘
```

### 2.4 端到端主链路（演示口径）

```
场景/问答 ──POST /api/decisions {entry_source:qa|manual}──▶ status=pending
   │
   ├─ 或 pipeline: POST /api/decision-pipeline/execute ──▶ status=pending（自动链路也进队列）
   │
   ▼
GET /api/decisions/pending   ◀── 待决策队列（按 waited_minutes 降序）
   │
   ├──POST /{id}/resolve {action:reject}──▶ status=rejected（终态，outcome=rejected）
   │
   └──POST /{id}/resolve {action:approve}─▶ status=decided
                │
                ▼
        POST /{id}/execute ──▶ ActionService.submit_action(decision_id)
                │                    │
                │                    ├─ confirmation_required=true → ActionRecord.status=approved（停）
                │                    └─ 否则自动 validating→executing→completed/failed
                ▼
        status: decided ─▶ executing ─▶ executed / failed
        outcome: pending ─▶ success / partial_success / failure
                │
                ▼
        GET /{id}/chain（证据 + 上游链 + 先例）
        GET /{id}/impact（下游决策 + 目标变化）
        GET /similar?context=...（先例复用，采纳后 PRECEDENT_FOR 留痕）
```

---

## 3. API 契约变更（锁定）

> 完整机器可读定义见同目录 `api-spec.yaml`。所有路径含版本前缀语义统一为 `/api/...`（仓库既有约定，不引入 `/api/v1`——本仓库全量路由均为无版本前缀，改动版本前缀属独立技术债，不在本次范围）。

### 3.1 决策台账（新增）

```
GET /api/decisions
```

| 查询参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `page` | int 1..100 | 1 | 页码。**上限 100，超出 422**——估算态下"跳末页"本就无意义，深翻页 `SKIP` 是 O(n) |
| `page_size` | int 1..100 | 20 | 与既有 `list_decisions` 命名一致 |
| `status` | enum 可重复 | — | `pending` / `decided` / `executing` / `executed` / `failed` / `rejected` |
| `outcome` | enum **可重复** | — | `success` / `partial_success` / `failure` / `pending` / `rejected`。**必须支持多值**：界面同时勾「执行成功 + 部分成功」时，两者同为 `status=executed`、只差 `outcome`，单值参数表达不了这个 OR |
| `entry_source` | enum **单值** | — | `manual` / `pipeline` / `recommendation` / `qa` / `agent` / `import` / `legacy`。**与相邻两行的多选刻意不一致，理由不是"做不到"而是"不值得"**：`status` / `outcome` 多选是 PRD 明确要求的界面组合（"执行成功 + 部分成功"两个标签指向同一个 `outcome` 值域，单值表达不了这个 OR）；`entry_source` 没有这个要求，7 个取值里绝大多数流量集中在 `manual` / `pipeline` 两个，实际用法就是"看某一条链的产物"，一次一个来源。**不做多选不封路**：把标量参数改成可重复参数是向后兼容的扩展，将来真需要时前端只是把单选换多选，旧请求不受影响。要看来源构成用分组统计，不要塞进筛选器 |
| `decision_type` | str | — | 精确匹配 |
| `agent_id` | str | — | 精确匹配。**Agent 页决策 Tab 的唯一数据来源**（替代已下线的 `/api/agent/decisions` 列表） |
| `min_confidence` | float 0..1 | — | 置信度闭区间下界 |
| `max_confidence` | float 0..1 | — | 闭区间上界。`min > max` → **422**（静默返回空集会让人以为"没有数据"） |
| `q` | str ≤100 | — | 对 `context_summary` / `recommended_option` 做 `CONTAINS`。**不含 `reasoning`**——推理全文命中率低、噪音大，且会把每次关键词搜索变成大字段全扫（与 PRD §4.2「不搜推理全文」一致） |
| `created_from` | datetime | — | 闭区间下界（ISO8601，服务端归一化为 UTC） |
| `created_to` | datetime | — | 闭区间上界 |
| `sort` | enum | `created_at` | `created_at` / `updated_at` / `confidence`（**`evidence_count` 降 P1，本期不做**） |
| `order` | enum | `desc` | `asc` / `desc` |

响应 `DecisionLedgerPage`：

```json
{
  "items": [ /* DecisionRecord[] */ ],
  "total": 137,
  "total_is_estimate": false,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

- `total_is_estimate`（**设计侧硬要求**）：Neo4j 精确 `count()` 是全扫描，10 万级过滤计数不可接受。策略——`count_decisions` 内部用 `LIMIT $probe+1`（`probe=5000`）探测：命中 ≤ probe 时做精确计数并返回 `total_is_estimate=false`；超限时返回 `total=probe`（表述为"约 N 条"）、`total_is_estimate=true`，前端在此态关闭"跳末页"并显示"约 N 条"。该字段**恒返回**，前端无需分支判空。
- `has_more`：由 `skip + len(items) < effective_total` 判定；`total_is_estimate=true` 时以"是否取满 `page_size`"判定，不依赖 total。
- 认证：`Depends(get_current_user)`（Bearer JWT）
- 隔离：`workspace_id` 由 `get_current_workspace` 从 JWT 声明解析，**不接受任何客户端 workspace 参数**；Cypher 强制 `WHERE n.group_id = $ws`
- 错误码：`401` 无/无效 token；`422` JWT 缺 workspace 声明；`422` 参数校验失败

> **`agent_id` 与 G6 的关系**：`agent_id` 是**空间内**的收窄维度，不是租户边界。所有查询仍先由 `n.group_id = $ws` 锁定空间，`agent_id` 只在其内二次过滤——不存在"传别人 agent_id 读到别空间数据"的路径。

> **`entry_source=legacy` 与 `status_assumed=true` 不是同一件事，禁止合并**：前者是**来源标签**（这条记录写于该字段存在之前，来源不明，不伪装成 `manual`），后者是**数据可信度标记**（`status` 是迁移时推定的，不是真实流程状态）。存量回填时二者同时为真，但之后会分开：一旦有人核对出真实流程状态并把 `status_assumed` 置 `false`，这条记录仍是 `legacy` 来源。因此队列排除历史数据**只能按 `status_assumed`**（§6 第 18 条）；若"简化"成按 `entry_source != 'legacy'` 排除，那些已被核对过的记录会被永久挡在队列外，且没人会想到去查来源字段。

### 3.2 待决策队列（新增）

```
GET /api/decisions/pending
```

> **本节是对设计师 A-1 / team-lead 必改 1 的修正**：本端点**不是**按单一 `status` 过滤。前版 summary 写"固定 `status=pending`"，与 `group.to_execute = status ∈ {decided, executing}` 不可同时成立——按字面实现会让 `to_execute` 恒空、`to_execute_count` 恒 0，PRD §5.1 整节定义的次队列直接消失。
> 修正后口径：**按"是否进入待办域"过滤**（`status ∈ {pending, decided, executing}`），再由 `group` 二分。`group` 的二分条件与 `counts.to_resolve` / `counts.to_execute` **由同一处派生**（同一条 Cypher 的 `grp` 表达式），禁止两处各写一遍条件；另外两个计数（`sla_warning` / `sla_breached`）复用同一批记录按 `waited_minutes` 划分，也不单独查一次库。

| 查询参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `page` / `page_size` | int | 1 / 20 | 同上 |
| `group` | enum | `all` | `all` / `to_resolve` / `to_execute`（`to_resolve` 为 PRD 主队列） |
| `entry_source` | enum | — | 可选收窄 |
| `decision_type` | str | — | 可选收窄 |
| `sort_by` | enum | `waited_desc` | `waited_desc` / `created_asc` / `confidence_asc`（**`evidence_count_asc` 降 P1**） |

**SLA 阈值走服务端配置，不做入参**（team-lead 必补 4）：`SLA_WARNING_MINUTES = 24*60`、`SLA_BREACH_MINUTES = 72*60`，读 `settings` 允许线上调，但**客户端不得自定义**——否则前端调一个参数就能把"已超时 40 条"改成"0 条"，SLA 变成摆设。

响应 `PendingQueuePage`，`items` 为 `PendingDecisionItem`：

```json
{
  "items": [{
    "decision": { /* DecisionRecord */ },
    "group": "to_resolve",
    "waited_minutes": 187,
    "decided_waited_minutes": null,
    "sla_state": "ok",
    "available_operations": ["approve", "reject"],
    "executable": true
  }],
  "total": 12,
  "counts": { "to_resolve": 9, "to_execute": 3, "sla_warning": 2, "sla_breached": 0 },
  "page": 1,
  "page_size": 20,
  "has_more": false
}
```

**两个等待时长字段，不是一个**（设计侧 Q/R 追问后补，原文漏了）：

| 字段 | 计时起点 | 有值的档 | 用途 |
|---|---|---|---|
| `waited_minutes` | `created_at` | 全部 | 待裁定档"等了多久没人拍板"；也是默认排序键 |
| `decided_waited_minutes` | `resolution.at` | 仅 `status ∈ {decided, executing}` | 待执行确认档"拍完板多久没落地" |

两者差一整个待裁定周期。用 `waited_minutes` 给 `decided` 档算 SLA 会把"昨天裁决的"显示成"等了 5 天"。**`sla_state` 的计时基准按 `group` 取**：`to_resolve` 用 `created_at`，`to_execute` 用 `resolution.at`——同一行里 `sla_state` 与哪个 `*_waited_minutes` 配对由 `group` 决定，两者必须一致，否则徽标与数字互相打脸。缺 `resolution.at` 的异常记录回落 `updated_at` 并打 warning，不留 `null` 让前端猜。

`counts.sla_warning` / `counts.sla_breached` 同样是**全库口径、按各自档位的基准计时**，不是"页内算出来"——页内计数会让用户以为只有 3 条超时。

- 隔离：同 3.1；`statuses` 由**服务端硬编码注入** `("pending", "decided", "executing")`，客户端无法用 `status` 参数绕过队列语义（请求体里根本没有 `status` 字段）
- `group` 由 status 派生（`pending→to_resolve`、`decided|executing→to_execute`），排序规则见 §5.1.1；`group` 查询参数只能在上述两值内收窄，不能扩大取值域
- `sla_state` 三档（`ok` ≤24h / `warning` 24–72h / `breached` >72h）。前版只有 `sla_breached:boolean` + `sla_minutes ≤ 1440`，**表达不了 PRD §5.3 的三档**（72h 超出上限，布尔值分不出"较久"与"已超时"）；不接受做假三档
- `available_operations`（前版名 `available_actions`，按设计师 C-4 改名，避免与 `RecommendedAction` 这个"要执行的命令对象"混淆）由状态机单点派生，前端不自行推断
- `counts` 一次给齐 PRD 要求的四个计数（待裁定 / 待执行确认 / 等待较久 / 已超时），用与 `items` 相同的过滤条件、不受分页影响
- **等待时长口径统一取 `created_at`**（不取 `updated_at`）：避免任何一次编辑/回填把"等了多久"重置为 0。见 §9.1
- **`status_assumed = true` 的存量推定记录不进队列**（PRD §8〈历史数据容错〉/ team-lead B-2 追加要求）。否则队列一上线第一屏就是几百条假待办，演示现场直接不可用。详见 §4.3
- **列表执行状态列 = 4 档 + 1 空态**（PM 二次修订，采纳）：
  - `executing` → 进行中；`executed` → 已完成；`failed` → 失败或已回滚；未派发且非 `decided` → 未开始
  - **`decided` → 空态（显示"—"或"无动作"），不并进"进行中"也不并进"未开始"**。原因是用户下一步动作不同：`decided` 能点"发起执行"，`executing` 只能等——并档会把次队列要堵的那个漏点（"采纳了却忘了执行"）重新盖回去
  - 实现零额外成本：全部只读 `status` 一个字段，**不跨库、不引入 N+1**
- **列表不出「状态同步中」，这一档只在详情页**（PM 第 8 轮否决了我的原设计，采纳）。原设计写"同一判断在列表与详情都生效"，实现不出来，而且硬凑出来会更糟：
  - **判不出来**：`PendingDecisionItem` 只有 `status` 与 `action_record_id`，没有"回写是否完成"这个信息。要判断残留，`action_record_id` 非空是唯一可用的信号——而它在**每一次正常执行**里都非空，于是"状态同步中"会在每次正常执行时闪一下。**一个在正常路径上就会出现的告警，等于没有告警**：它会把真正卡住的那条淹掉，用户学会的是无视它。
  - **要真的做得出来，就得加字段**：给 `PendingDecisionItem` 加 `status_sync_pending: bool`，服务端显式判定。**本期不加**——列表是"扫一眼挑哪条要处理"的界面，加一个只有列表才需要的布尔值，成本落在一个不靠它决策的位置上。详情页本来就要展示精确 8 态（§7），判定材料天然齐备，放那里不欠任何东西。
  - 列表侧仍保留 §3.2 已定的处理：`executing` → 「进行中」。这不是"把不确定伪装成确定"，因为列表**没有声称**自己知道得更多；详情页才是"点了名字要看清楚"的地方。
- **「状态同步中」必须自带期限**（PRD §8〈同步窗口必须诚实且有上限〉第 2 条，采纳，作用于详情页）：该文案若可无限期停留，就变成"用户无法自行证伪"的兜底——一次真实失败会被它永久盖住。因此按 `updated_at` 计时，超过 **`SYNC_STALE_MINUTES`（默认 10 分钟）** 降级为「状态可能未同步，请检查执行记录」并给执行记录跳转入口。三级判定表见 §7。
  - **计时字段用 `updated_at`，不新增 `status_changed_at`**：§4.1 的字段表已锁 5 个，为一句兜底文案加第 6 个字段不划算。`updated_at` 会被编辑刷新（同 §9.1 Q2 对"等待时长"的顾虑），但这里刷新只会把提示推迟、不会误报，且该判断**只影响文案**，不参与任何计数、排序、`sla_state`——正因如此可以容忍它的不精确。
  - **阈值放前端单点常量**（`apps/web/src/modules/decision/constants/decisionConfig.ts` 的 `SYNC_STALE_MINUTES`），与 SLA 阈值下沉服务端的处理**刻意不同**：SLA 阈值决定"返回哪一批记录"，客户端能改就是漏洞；同步窗口只决定"说哪句话"，改它不改变任何数据集合，因此不需要服务端权威。P1 随 SLA 阈值配置一起迁到服务端下发（PM 已登记同批）。
  - **不得用 `sla_state` 或 `waited_minutes` 反推本窗口**：三者计时起点不同（`created_at` / `resolution.at` / `updated_at`），混用会出现"等待 3 天但状态同步中 2 分钟"的自相矛盾展示。

### 3.3 裁决动作（新增）

> **动作集合已由 team-lead 裁定为 3 个**：采纳（approve）/ 驳回（reject）/ 查看详情（无接口）。「改选备选」不做——它会连锁触发"换方案后置信度是否重算、证据链是否失效"，降 P1 单独评估。因此请求体**不预留第 4 个动作的任何字段**。

```
POST /api/decisions/{decision_id}/resolve
```

请求 `ResolveDecisionRequest`：

```json
{
  "action": "approve",
  "reason": "证据充分，按建议方案执行"
}
```

- `action`: `approve` | `reject`（必填，仅此两值）
- `reason`: str ≤500，`reject` 时必填（≥5 字），`approve` 时可选
- 响应：`DecisionRecord`（迁移后的最新状态）
- 认证：`Depends(get_current_user)` + `get_current_workspace`
- 隔离：`transition_status` 的 CAS 条件为 `uuid AND group_id AND status IN expected`
- 错误码（全部走信封 + `error.code`，AC-17）：`403 forbidden` 无裁决权限（OPA fail-closed，**不含跨空间**——跨空间一律 404）；`404 not_found` 不存在或跨空间（不泄漏存在性）；`409 illegal_transition` 非法状态迁移 → `raise ConflictError(msg, code="illegal_transition", details={"handler_name": ..., "current_status": ...})`，响应体 `{"error": {"code": "illegal_transition", "details": {...}}}`（前端展示"已被张三处理"，`handler_name` 取自已写入的 `resolution.by`；无则 `null`）；`422` 参数
- 副作用：写 `resolution`（最近一次裁决，`actor_type=user`、`by` 为当前登录人）+ Graphiti 审计 Episode `decision_resolved`（零 LLM，失败不阻断）
- **门禁拒绝写 `actor_type=system`**：若拒绝来自策略门禁而非人工（`POST /check-rules` 不通过、或 `execute` 前的 OPA fail-closed），写 `resolution={action:reject, actor_type:system, by:"系统（策略门禁）", reason:"<门禁摘要>"}`。这条与人工驳回**同用一个字段但是两种语义**，靠 `actor_type` 区分，不允许互相覆盖

### 3.4 执行触发（新增）

```
POST /api/decisions/{decision_id}/execute
```

请求 `ExecuteDecisionRequest`（全部可选，缺省取 `recommended_action`）：

```json
{
  "action_type_id": "freeze_settlement",
  "target_object_id": "ent_8f21",
  "target_object_type": "Supplier",
  "parameters": { "reason": "semantic_drift" }
}
```

响应 `DecisionExecuteResult`：

```json
{
  "decision": { /* DecisionRecord, status 已映射 */ },
  "action_record": { /* ActionRecord */ },
  "decision_status": "executing",
  "decision_outcome": "pending",
  "idempotent_replay": false
}
```

- 前置校验：`status ∈ {decided, failed}`，否则 `raise ConflictError(..., code="illegal_transition")` → `409`。**`decided` 必须允许**（team-lead 裁定）——`decided` 的本质是"人已拍板、等待落地"，它是执行的前置态而非终态；若不允许，次队列"已裁决未执行（需催办）"这一档就变成只能看不能动的死档。**`pending` 不得直接进执行**（未裁决不许执行），返回 `409 code=illegal_transition`
- 载荷缺失（body 与 `recommended_action` 均为空）→ `422`
- 编排：`ActionService.submit_action(ActionRequest(decision_id=...))` → `link_triggered_action` 建 `TRIGGERED` 边 → **单份 `StatusOutcomePatch` 一次写完**如下四项（不拆多次写，理由见 §5.2.1）：
  - 顶层 `action_record_id`（修缺陷 C，该字段全仓从未被赋值）
  - `status` / `outcome`（按 §5.3 映射，走 `to_node_patch()`）
  - `outcome_details` 的**完整快照** `{action_record_id, action_status}`
  - 审计 Episode `decision_executed`

**`execute` 路径必须写 `outcome_details.action_status`**（设计侧第 8 轮追问，本版定为必做）。这一条容易被"流水线不是已经写了吗"糊过去，但两者写的**不是同一个时刻**：

- `_backfill_decision_outcome` 只在**执行结束之后**写；而"刚点完发起执行"到"下一次回填"之间是一个真实窗口，此时 `outcome_details` 里什么都没有。
- 如果 execute 不写，详情页「8 态精确展示」在**用户最需要它的那个瞬间**（刚点完，想知道到底跑起来没有）恒为空，只能退化成"执行中"；而 `status=executing` 本身也说不清是"已派发在跑"还是"根本没派发"。**这等于把一个短窗口换成一个长窗口的假状态**，正是〈同步窗口必须诚实且有上限〉要堵的那类问题。
- 成本为零：这次写本来就要发生（状态映射回写），只是 `details` 里多带一个键。**不新增往返、不新增字段、不新增人日。**

**`outcome_details` 的写入纪律（因为它是一个整体 JSON 串，不是 map）**：`SET n.outcome_details = $json` 是**替换**，不是合并。所以每个写点都必须写"当次完整快照"，**禁止只写一个键**——否则先写的键会被静默抹掉，而抹掉的动作在 Cypher 里看不出来。execute 写 `{action_record_id, action_status}`，pipeline 回填写 `{action_record_id, action_status, feedback_pipeline}`，两者都是各自时刻的完整快照，这是允许的；将来若要"只更新一个键"，必须先读出来改再写回，且要在同一事务里。

- 隔离：先 `get_decision(id, ws)` 双条件读（None → 404），再提交
- 错误码（全部走信封，AC-17）：`404 not_found` / `409 illegal_transition`、`409 execute_in_progress` / `422 missing_action_payload`

**幂等与并发（team-lead 裁定，必须实现）**

不做分布式锁——**用 CAS 当锁**，两步走：

```
① claim = transition_status(id, ws, expected=("decided","failed"),
                            to_status="executing", patch={})        # 见下：不写额外字段
   ├─ True  → 我是唯一赢家，进 ②
   └─ False → 读当前节点：
              ├─ action_record_id 非空 → 返回既有 ActionRecord，idempotent_replay=true
              └─ action_record_id 为空 → 409 execute_in_progress（另一请求派发中）
② 仅赢家调 submit_action() → 单份 StatusOutcomePatch（顶层 action_record_id +
   status/outcome + outcome_details 快照）
```

理由：CAS 的 `WHERE status IN $expected` 本身就是互斥点，两个并发请求只有一个能把 `decided` 改成 `executing`，天然满足"只创建一个 ActionRecord"。引入 Redis 锁反而引入新的失效面（锁超时、脑裂）。

**① 的 `patch` 为什么是空的**（本版修正）：前版写 `patch={executing_since: now}`，但 §4.1 的字段表只锁了 5 个字段，`executing_since` 不在其中——**为了让一句兜底文案有个计时起点而新增第 6 个字段，与 §3.2「用 `updated_at` 不新增字段」的决定自相矛盾**。`to_node_patch()` 本来就会写 `updated_at`，所以 ① 这次 CAS 成功本身就是同步窗口的计时起点，`executing_since` 是重复记账。**同一个事实存两处，迟早会不一致，而且不一致时没人知道该信哪个。**

- **幂等重放**：第二次调用读出 `action_record_id` 非空 → 直接返回既有记录 + `idempotent_replay: true`，不再提交
- **并发窗口内的诚实回答**：赢家已 CAS 成功但尚未写回 `action_record_id` 时，输家既拿不到记录也不该假装成功 → `409 execute_in_progress`，前端提示"正在派发，请稍后刷新"，不静默返回空
- **执行失败必须回写终态**：`submit_action` 抛错或 ActionRecord 落到 `failed`，必须写 `status=failed` + `outcome=failure`，**不允许停在 `executing`**（停在那里等于既不能重试也不在失败统计里）。② 的整份 patch 与状态回写放在 `finally`，不放在 try 的末尾
- **跨库残留态自愈**：`status=executing` 但 `action_record_id` 非空、且对应 ActionRecord 已终结时，重放 `execute` 必须**读回 ActionRecord 并按 §5.3 重新映射**（而不是直接 `idempotent_replay` 返回旧状态）——否则一次 failed 的提交会被"幂等重放"永久固化成 `executing`

### 3.5 批量裁决（新增，对应 PRD B3）

```
POST /api/decisions/batch-resolve
```

请求 `BatchResolveRequest`：

```json
{
  "decision_ids": ["dec_ab12cd34ef56", "dec_77aa88bb99cc"],
  "action": "approve",
  "reason": "批量清理积压"
}
```

响应 `BatchResolveResult`：

```json
{
  "succeeded": 1,
  "failed": 1,
  "results": [
    { "decision_id": "dec_ab12cd34ef56", "ok": true,  "status": "decided",  "error": null },
    { "decision_id": "dec_77aa88bb99cc", "ok": false, "status": null,
      "error": { "code": "conflict", "message": "该决策已被他人处理（当前状态 executed）" } }
  ]
}
```

- `decision_ids`: 1..50（超限 422，对应 PRD「>50 条拒绝提交」）
- **不做事务回滚**：逐条独立走 CAS，部分失败保留已成功项（PRD 明确要求）
- 失败原因分类：`not_found`（不存在/跨空间，不泄漏存在性）、`conflict`（状态已变更）、`permission`（无裁决权限）
- 隔离：逐条 CAS 含 `group_id`，跨空间条目一律归为 `not_found`
- 错误码：`401`（共享依赖，`{"detail": ...}`）/ `422 batch_empty`、`422 batch_size_invalid`、`422 reason_required`（走信封）；单条失败体现在 `results` 内而非整体非 200

### 3.6 台账导出（**降 P1，本期不做**，对应 PRD B5）

```
GET /api/decisions/export.csv      ← 本期不实现，已从 api-spec.yaml 移除
```

team-lead 裁定 CSV 导出降 P1，因此**路径已从契约里删除**，前端不渲染导出按钮（不放假控件——渲染一个点了没反应的按钮比不渲染更伤信任）。

设计不丢，验证过的结论留在这里，P1 捡起来时直接照做：

- 查询参数与 3.1 **完全一致**（复用同一 `DecisionQuery`，保证"导出 = 当前筛选结果"）
- 上限 5000 行：超出直接 `422` 并提示收窄筛选（PRD 要求）
- 响应：`text/csv; charset=utf-8`，**UTF-8 带 BOM**（`\ufeff` 前缀，保证 Excel 不乱码）
- **解到独立列，不塞 JSON 单元格**（PM 补充要求 1）：`resolution` 必须展开为「裁决人」「裁决时间」「驳回理由」三列。导出的人是要在 Excel 里排序筛选的，JSON 塞一格等于没导
- 列序：`decision_id` / `状态` / `结果` / `入口来源` / `决策类型` / `上下文摘要` / `推荐方案` / `置信度` / `裁决动作` / `裁决人` / `裁决时间` / `驳回理由` / `执行记录ID` / `创建时间` / `更新时间`
- **门禁拒绝与人工驳回在「裁决人」列可区分**（PM 补充要求 2 / PRD §8〈驳回来源可区分〉）：`resolution.actor_type=system` 时裁决人列写「系统（策略门禁）」、理由列写门禁摘要；`actor_type=user` 时写实际处理人与人工理由
- `Content-Disposition: attachment; filename="decisions_{workspace}_{yyyymmddHHMM}.csv"`
- 导出动作写审计：`action=decision_ledger_export`，`details={count, filters_hash}`

### 3.7 推理步骤（新增，替代 `/api/agent/decisions/{id}/steps`）

agent 链的"过程记录"不再是一等端点，但**推理步骤本身是决策的可审计附属物**，必须落到决策对象上（复用既有 `reasoning_trace` 字段，格式对齐 ADR-076 §4 引用的 ADR-075 step 对象）。

**写**：

```
POST /api/decisions/{decision_id}/reasoning-steps
```

```json
{ "phase": "orient", "description": "确认漂移集中在供应商主体", "evidence": [{ "entity_id": "ent_8f21" }] }
```

- `phase`: `observe` | `orient` | `decide` | `act`（与既有 `DecisionPhase` 枚举一致，硬编码白名单）
- `description`: str ≤1000
- `evidence`: `List[Dict]` ≤20
- 服务端补 `step_id`（`uuid4`）与 `timestamp`（服务端时间，不接受客户端传）
- 追加进 `reasoning_trace`，单决策上限 **200 条**（超出 422，防止无界增长）
- 响应：`{ "decision_id", "step_id", "phase", "timestamp", "step_count" }`
- 认证：`get_current_user` + `get_current_workspace`；隔离：`append_reasoning_step` 的 MATCH 含 `uuid AND group_id`，跨空间 → 404
- 权限：与裁决同一 OPA 判定（写推理步骤属于修改决策对象）

**422 必须带可区分的 `reason_code`**（设计侧第 6 轮提出，采纳）：

前端默认会把 422 当成"表单校验失败"，于是 200 条上限也会被提示成"你填错了"。但这两类 422 的处置完全不同——一个是用户改输入，一个是系统容量到顶、用户改什么都没用。因此 `POST` 的 422 走 `{"error": {...}}` 信封，`error.code` 承载原因：

| `error.code` | `error.details.field` | 性质 | 前端文案 |
|---|---|---|---|
| `step_limit_reached` | `null` | **系统容量上限，非用户错误** | 「该决策的推理步骤已达上限（200 条），无法继续追加」；**已存在的 199 条不得渲染成失败态** |
| `invalid_phase` | `"phase"` | 用户输入 | 「阶段取值不合法，可选 observe / orient / decide / act」 |
| `description_too_long` | `"description"` | 用户输入 | 「描述不能超过 1000 字」 |
| `evidence_too_many` | `"evidence"` | 用户输入 | 「证据条目不能超过 20 条」 |

`error.details` 同时带 `step_count` 与 `limit`（仅 `step_limit_reached` 有值），让前端能显示"200/200"而不是让用户猜。

**不用 429/507**：这不是限流也不是存储不足，是整个决策对象的可审计体积上限，422 是对的语义；而两者共用 422 就必须靠 `reason_code` 区分——否则前端只能给一句通用文案。

**实现约束：这四种原因都不能靠 Pydantic 字段约束产生，必须写在处理函数里。** 否则契约里的 `error.code` 不会出现：

全仓**没有** `RequestValidationError` 处理器（`exception_handler.py` 的 `register_exception_handler` 只 `add_middleware`，处理的是未捕获异常、`ValueError`、`PermissionError`）。因此 Pydantic 层的校验失败走 FastAPI 默认体：

```json
{ "detail": [ { "type": "string_too_long", "loc": ["body","description"], "msg": "..." } ] }
```

`detail` 是**数组**，而契约 `ErrorDetail.detail` 是 `string`——前端按契约写的 `res.detail` 拿到的是被 JS 隐式转换过的 `[object Object]`，最终仍落到"操作失败"一句通用文案。这正是设计侧提这条需求要解决的问题，只在 schema 里加字段是修不掉的。

两个可选路径，选后者：

1. 全局注册 `RequestValidationError` 处理器改信封 —— **否决**：那会把全仓所有端点的 422 体一起改形，为一个端点的文案需求改动全局错误契约，回归面远超收益。
2. 本端点**不用** `Literal` / `max_length` / `maxItems` 约束，把入参声明为 `phase: str` / `description: str` / `evidence: list[dict] | None`，在 `append_reasoning_step` 里依次校验并抛领域错误 —— **采纳**。OpenAPI 里仍保留枚举与长度上限（它是文档的一部分），只是**执行权**从模型挪到函数。

**这里不能顺手写成 `raise HTTPException(422, detail=<dict>)`。** FastAPI 对 `HTTPException` 的处理是 `{"detail": <detail 参数>}`，于是实际响应体变成 `{"detail": {"detail": "...", "reason_code": ...}}`——多套一层 `detail` 键，前端顶层读不到 `reason_code`，又回到"操作失败"。`HTTPException` 只能产生 `{"detail": <标量>}` 一种形状。

**第 8 轮修正：不要新造异常类，仓库里那四个是活的（team-lead 实测推翻了我的前提）**

前版这一段设计了一个 `DecisionApiError(Exception)` + 一个专属 handler + `web/app.py` 注册。**这个设计建立在"`APIError` 是死代码"的假设上，而这个假设是假的。**

事实（team-lead 逐行核对，我复验）：`exception_handler.py` 末尾 `APIError` / `ValidationError`(400) / `NotFoundError`(404) / `ConflictError`(409) 四个类齐全，字段与 `to_dict()` 都写好了，`error_code` / `status_code` / `details` 一应俱全——**但中间件的 `_handle_exception` 只按 `ValueError` / `PermissionError` 判类型，没有 `isinstance(exc, APIError)` 分支**，全仓零个 `raise APIError` 点。于是它是"半成品"：类在、形状在、没人接。

我原来的报错路径若按此交付，后果是：`DecisionApiError` 拿到的是 **500**，裁决端点的 409 永远不会出现在客户端，而**测试会全绿**——因为没人真的发请求，既有 `TestAPIError` 只断言了 `err.status_code == 404` 这个**对象属性**。

修法（team-lead 已落地，`exception_handler.py:46-65`）：在 `_handle_exception` 里补一支 `isinstance(exc, APIError)`，原样透出 `status_code` 与 `error_code`。**比我的方案少一个文件、少一处注册，还顺带修好了一个既有的全仓缺陷**：在此之前 `NotFoundError(404)` 会掉进通用分支变成 500，"资源不存在"被客户端读成"服务器炸了"。

结论收回，落地方式改为：

```python
# infra/middleware/exception_handler.py（已存在，team-lead 已补分支）
# APIError 分支产出：{"error": {"type", "code", "message", "request_id", "path", "details"?}}
```

```python
# decision_hub/models/errors.py（新建，约 14 行）
from odap.infra.middleware.exception_handler import APIError


class StepRejectError(APIError):
    """推理步骤 422。复用全局信封，`error.code` 即 4 个 `reason_code` 之一。

    `details` 三个键**恒存在**（不适用的给 null），不用"键是否存在"表达分支——
    前端读 `error.details.field` 时不该先判断 `in`，那正是它会漏判的地方。
    """

    def __init__(self, code: str, message: str, *, field=None, step_count=None, limit=None):
        super().__init__(
            message=message,
            error_code=code,
            status_code=422,
            details={"field": field, "step_count": step_count, "limit": limit},
        )
```

**不需要** `register_decision_error_handler`、**不需要**改 `web/app.py`、**不需要**新 handler。§8.1 与 T5 中的三行文件清单据此删除。

**`DecisionInvariantError` 不继承 `APIError`——这是我对 team-lead「两者都继承 `APIError`」的一处有意偏离，理由有两条，都可验证：**

1. **日志级别会错。** `APIError` 分支打的是 `logger.warning`。而 `status × outcome` 非法是**内部不变量被破坏**，必须进 `logger.error` + 堆栈，否则运维的告警规则（按 error 级别触发）永远收不到它——一条只在 warning 里出现的"服务端 bug"，等于没被发现。通用分支（`:102`）打的是 `logger.error` 且带 `traceback.format_exc()`，语义正好。
2. **生产环境会漏内部值。** `APIError` 分支在 `is_prod` 判断**之前**返回，`message` 原样出网。500 类错误的 body 本来就不该给客户端任何可读细节（前端对 500 只显示通用文案 + `request_id`），把 `status=executing, outcome=success` 这类内部枚举值送到浏览器没有收益。

当前实现（`status_matrix.py:27` `class DecisionInvariantError(Exception)`）就是对的，**保持不动**。代价是 500 的 body 里没有 `error.code`——**这个代价是我们要的**：前端若拿到 500 却去分支判断 `code`，说明它在假装能处理不该处理的情况。契约里 500 只承诺 `error.type` / `message` / `request_id` / `path`（生产 `type` 恒为 `InternalServerError`）。

> **一条附带的运行时事实，值得写下来免得后人"顺手修正"**：`DecisionInvariantError` 不继承 `ValueError` 还带来第二个好处——Pydantic v2 的 `model_validator` 只把 `ValueError` / `AssertionError` 收进 `ValidationError`，其余异常**原样抛出**。所以在 `StatusOutcomePatch` 的校验器里抛它，会一路穿透到中间件被当作未捕获异常 → 500。若改成 `ValueError` 子类，会被 Pydantic 包成 `ValidationError`，再被中间件当 `ValueError` 映射成 **400**——**两层包装，一层都不能省**。

**为什么不改写既有 `HTTPException` 的用法**：既有 6 个决策端点返回 `{"detail": "<字符串>"}`。新端点中凡是**需要前端按字段分流**的错误（本节的 422、§3.3-§3.5 的 409）走 `APIError` 家族（信封 `{"error": {...}}`）；只在客户端提示一句话的错误（401/403/404）继续用 `HTTPException`（形状 `{"detail": "..."}`）。

**判据是"前端是否需要读错误体里除一句文案以外的字段"**，不是"新端点必须用新的"。这条判据的代价必须写清：**同一次会话里前端会遇到两种错误体**，所以读取只允许有一处封装（见 §7「错误读取单点封装」），不允许每个调用点各写一套 `error`/`detail` 判断。

验收断言（T5）：构造 `description` 超 1000 字 → `422` 且 **`resp.json()["error"]["code"] == "description_too_long"`**、`error.details.field == "description"`；构造第 201 步 → `error.code == "step_limit_reached"` 且 **`error.details["field"] is None`**、`step_count == 200`、`limit == 200`。全部**从 `error` 这一层读**（不是 `detail`、不是顶层）——这一条专门防上面那条路径被"顺手简化"回 `HTTPException`。


**读**：

```
GET /api/decisions/{decision_id}/reasoning-steps
```

```json
{ "decision_id": "dec_ab12cd34ef56", "steps": [ { "step_id": "...", "phase": "observe", "description": "...", "evidence": [], "timestamp": "..." } ], "total": 4 }
```

- 按 `timestamp` 升序
- 认证/隔离同上；跨空间 → 404
- 与 `GET /{id}/chain` 的关系：`chain` 已返回 `reasoning_trace`，**列表页与详情页复用 `chain` 即可**；本端点用于 Agent Tab 的"只看推理步骤"区块与增量刷新，避免为此拉整条因果链

### 3.8 agent 链下线：迁移映射（对应 G6 / PRD Q7）

**结论：直接下线，不设过渡期。** 5 个端点全部删除（含 `router_registry` 注册）。

| 原端点 | 处置 | 迁移去向 |
|---|---|---|
| `GET /api/agent/decisions`（列表） | **删除** | `GET /api/decisions?entry_source=agent&agent_id=<id>`（台账） |
| `GET /api/agent/decisions/{id}`（单条） | **删除** | `GET /api/decisions/{id}/chain`（含 `decision` 本体） |
| `GET /api/agent/decisions/{id}/chain` | **删除** | `GET /api/decisions/{id}/chain`（同名语义，另有结构化 `DecisionChain`） |
| `POST /api/agent/decisions`（建链） | **删除** | `POST /api/decisions`（`entry_source=agent`，`decision_id` 由服务端生成） |
| `POST /api/agent/decisions/{id}/steps` | **删除** | `POST /api/decisions/{id}/reasoning-steps` |
| `POST /api/decisions/{id}/reasoning-steps`（新） | — | 读：`GET /api/decisions/{id}/reasoning-steps` |

**为什么直接下线而非过渡期保留**：

1. 保留即"决策的第二个入口"，与 A4「单一数据源」的目标直接冲突（PM 立场，我认同）。
2. 过渡期保留必须先补隔离，而补隔离的改动量（3 端点加依赖 + service 加归属校验 + 单测）= 下线改动量；既然成本相同，就不该留一个仍需维护的后门。
3. 前端唯一调用点是 `AgentPage.tsx` + `agentApi.ts`，与本次台账改造同批（T7），无外部调用方，无需兼容窗口。

**注意**：app 内部无其他模块 import 这两个 router/service（已确认 `router_registry.py` 是唯一注册点）；`core/agent/services/decision_service.py` 的内存 dict 在 T7 后不再承担任何读取职责。

### 3.9 既有 3 条链的兼容策略

| 链 | 端点契约变化 | 兼容性 |
|---|---|---|
| pipeline | **零变化**。仅内部 `_build_decision_record` 增 `entry_source=pipeline` + `recommended_action` 两个字段赋值 | 完全向后兼容，`PipelineResult` schema 不动 |
| recommendation | **零变化**。"采纳→决策"由前端调 `POST /api/decisions` 携带 `entry_source=recommendation` + `constraints.recommendation_id` | 完全向后兼容 |
| agent | **5 端点删除**（见 §3.8），能力由台账 + `reasoning-steps` 承接 | **破坏性变更**，唯一调用方同批改造；迁移映射见 §3.8 |
| record | `POST /api/decisions` 请求体新增可选 `entry_source`（默认 `manual`） | 缺省值保证旧调用方无感 |

### 3.10 三个被复用的只读端点：本期行为不变（答复设计师 A-7）

设计师的硬阻塞是"详情页三块没有契约确认"。准话如下，可以按"不变"定稿：

| 端点 | 本期处置 | 契约保证 |
|---|---|---|
| `GET /api/decisions/{id}/chain` | **不改造、不迁移、不加参数**，仅被 `decision_hub` 详情编排复用 | `evidence_entities[].name` **稳定返回**；`reasoning_trace` 字段一并返回，详情页不必为推理路径再打一次接口 |
| `GET /api/decisions/{id}/impact` | 同上 | 响应结构零变化，`impact_completeness` 语义不变 |
| `GET /api/decisions/similar` | 同上 | `group_ids=[ws]` 的空间过滤已在 `find_similar_decisions` 内，不改 |

**推理路径区块不用删。** 上一版 `api-spec.yaml` 里确实没有它，那是漏收不是不做——`GET|POST /api/decisions/{id}/reasoning-steps` 已在本次契约内（§3.7），详情页「推理路径」区块有契约支撑，`DecisionTimeline` 可以下沉。但注意：详情页若已拉 `/chain`，`reasoning_trace` 已在响应里，**不必再调 reasoning-steps**；该端点服务于 Agent Tab 的独立区块与增量刷新。

**`evidence_entities[].name` 为空时**显示「未命名实体」而非空白单元格（PM A2 前端要求，与设计师 §6.6 一致）。

---

## 4. 数据模型变更

### 4.1 新增字段（`models/decision_record.py`）

```python
class DecisionStatus(str, Enum):
    PENDING   = "pending"     # 待裁决（进队列）
    DECIDED   = "decided"     # 已裁决，待执行
    EXECUTING = "executing"   # 执行中
    EXECUTED  = "executed"    # 已执行完毕
    FAILED    = "failed"      # 执行失败（可重试）
    REJECTED  = "rejected"    # 已否决（终态）

class DecisionEntrySource(str, Enum):
    MANUAL = "manual"; PIPELINE = "pipeline"; RECOMMENDATION = "recommendation"
    QA = "qa"; AGENT = "agent"; IMPORT = "import"; LEGACY = "legacy"
```

在 `DecisionRecord` 上新增：

| 字段 | 类型 | 默认 | 用途 |
|---|---|---|---|
| `status` | `DecisionStatus` | `PENDING` | 决策流程状态，台账/队列的筛选与排序主键。服务端产生，客户端不可写 |
| `entry_source` | `DecisionEntrySource` | `MANUAL` | 台账"这条决策从哪条链来"（对应 PRD G2 / A3） |
| `recommended_action` | `Optional[Dict[str, Any]]` | `None` | 可执行载荷（`action_type_id` / `target_object_id` / `target_object_type` / `parameters`），补齐 `execute` 的数据缺口 |
| `resolution` | `Optional[Dict[str, Any]]` | `None` | 裁决留痕（对应 PRD G4）：`{action, actor_type, by, at, reason}`。**独立字段而非塞 `outcome_details`**（PM Q1 问询，答复见 §9.1） |
| `status_assumed` | `bool` | `False` | `True` = 该 `status` 是迁移时为存量数据**推定**的，非真实流程状态。队列排除此类记录（PRD §8〈历史数据容错〉）；详情页据此标注"历史数据，流程状态未记录" |

**`resolution` 里 `actor_type: system|user` 的由来**：PM 指出门禁拒绝与人工驳回必须可区分（PRD §8〈驳回来源可区分〉）。`outcome=rejected` 两者共用，`action` 也共用，唯一能落差分的就是 `actor_type` + `by` + `reason` 三者组合。这不是锦上添花——复盘时"系统规则拦下"与"人的判断失误"是两个完全不同的结论。

**为什么裁决留痕用 1 个 dict 而不是 3 个平铺字段**：PRD G4 要 `decided_by` / `decided_at` / 驳回理由 三个值，但台账列表只是**展示**这三列，不做筛选/排序。用一个 `resolution` dict 既完整承载，又避免为一个纯展示需求往 243 行的核心模型上加 3 个字段。若后续「裁决人」成为筛选维度，再拆平铺字段并加索引。

**状态迁移历史不在决策节点上存**：完整迁移轨迹由 Graphiti 审计 Episode 承载（`decision_resolved` / `decision_executed`，零 LLM，复用既有 `save_audit_episode`）。决策节点只保留**当前状态 + 最近一次裁决**，避免 `status_history` 这类无界数组把节点撑大并引发读-改-写并发丢条目。

同步修改 `to_node_properties()` / `from_node_properties()`（`recommended_action`、`resolution` 走 JSON 序列化）。

**文件行数控制**：`decision_record.py` 现 243 行。把 4 个枚举（`DecisionOutcome` / `CausalLinkType` / `DecisionStatus` / `DecisionEntrySource`）抽到新文件 `models/enums.py`（约 45 行，抵掉约 22 行），4 字段 + 8 行序列化净增约 30 行 → 目标 ≤ 265 行。由 `models/__init__.py` 与包根 `__init__.py` 再导出，**所有既有 `from ...decision_record.models import DecisionOutcome` 导入路径保持不变**。

### 4.2 为什么不能只靠 `outcome`

PRD §2 明确约束「不新增决策状态枚举值，用户可见状态由 `outcome` 五态 + 执行动作状态派生」（PRD 第 16 行 / G3）。这个约束在本仓库的**当前代码事实上不可执行**，四条理由：

1. **派生所需的 `action_record_id` 从未被写入**（实测，见 B-3）。`DecisionRecord.action_record_id` 字段存在、会序列化、会被读取（`decision_record.py:83/122/184`），但全仓**没有任何一处给它赋值**：`_build_decision_record`（`pipeline.py:634-657`）不设它；`link_triggered_action` → `create_triggered_edge`（`neo4j_decision_store.py:207-223`）只建边和影子节点、不 `SET d.action_record_id`；`_backfill_decision_outcome`（`pipeline.py:686-687`）只写进嵌套的 `outcome_details.action_record_id`。所以"已关联执行动作"这个派生条件在图上是恒为假的。
2. **改走 `TRIGGERED` 边派生，动作状态是陈旧的**。边对应的 `:ActionRecord` 是影子节点，其 `status` 只在建边那一刻 `SET` 一次（`neo4j_decision_store.py:215`），此后 `ActionService` 更新状态只写 SQLite（`sqlite_action_storage.py:114`），影子节点永不刷新。要拿到真实的「排队/校验中/已批准/执行中」必须回表 SQLite，而台账列表是 Neo4j 查询——这会把一次列表查询变成跨库 N+1。
3. **`outcome=pending` 天然污染队列语义**。`_backfill_decision_outcome`（`pipeline.py:678-679`）对"未执行"的决策一律写 `PENDING`。PRD 的派生规则用「且未关联执行动作」来消歧，但该条件因理由 1 恒真，结果是**每一条流水线跑完但未执行的决策都会落进"待裁定"主队列**。
4. **`outcome` 无 CAS 能力，也无法区分两类拒绝**。`outcome` 是裸覆盖写（`update_outcome` 直接 `SET`），做不到 `WHERE status IN expected`，两个审批人同时点通过会双写执行（PRD B3 的"冲突条目不覆盖他人结果"直接失效）；OPA 拒绝与人工驳回都写 `rejected`（`pipeline.py:670-671` / `manual`），台账无法区分（PRD 要求「驳回理由」列可见，且要能分辨门禁拒）。

**架构师结论**：建议采用 `status` 新增字段（详见 B-2）。`status` 与 `outcome` **职责分离且不重叠**——`outcome` 仍是执行结果（五态不变，ADR-076 §3 契约零变更），`status` 是流程位置。这不构成与 ADR-076 §3 的冲突，因为 ADR-076 §3 定义的是 `outcome` 的值域，未约束"决策对象只允许一个状态字段"。

**若 Phoenix 坚持不新增字段（Plan B）**：退回纯派生 + 双写补偿，代价是——(a) 必须先修 B-3 让 `action_record_id` 落库；(b) 队列查询需 Neo4j 取 `action_record_id` 列表后用 `IN (...)` 批量查 SQLite 再在内存分组，列表接口多一次跨库往返且分页必须先取全量再切（`total` 无法在库侧算）；(c) 裁决仍需一个 `resolution` 字段承载"谁在何时驳回"，`outcome` 装不下。评估：Plan B 的实际改动量不小于新增 `status`，但正确性更差、分页更贵，故不推荐。

### 4.3 迁移策略（Neo4j Cypher，幂等）

迁移入口：`Neo4jDecisionQueryStore.migrate_legacy_fields()`，由 `ensure_indices()` 末尾调用（沿用 `_indices_ready` 守卫），并在 `list_decisions` 首行调用（读路径自愈，保证只读启动场景也不漏）。

```cypher
// M1 时态类型归一：created_at/updated_at 必须是字符串，否则范围过滤与排序索引失效
MATCH (n:Decision)
WHERE NOT n.created_at IS :: STRING
SET n.created_at = toString(n.created_at)
RETURN count(n) AS normalized;

// M2 status / entry_source / status_assumed 回填，WHERE 保证二次运行匹配 0 行
MATCH (n:Decision) WHERE n.status IS NULL
WITH n, CASE
      WHEN n.outcome IN ['success','partial_success'] THEN 'executed'
      WHEN n.outcome = 'failure'                      THEN 'failed'
      WHEN n.outcome = 'rejected'                     THEN 'rejected'
      WHEN n.outcome_details CONTAINS 'action_status' THEN 'executing'
      ELSE 'pending' END AS derived
SET n.status         = derived,
    n.status_assumed = (derived = 'pending'),
    n.entry_source   = coalesce(n.entry_source, 'legacy'),
    n.updated_at     = coalesce(n.updated_at, n.created_at)
RETURN count(n) AS migrated;
```

**存量回填规则表（team-lead 要求：必须写清，且不得与〈历史数据容错〉冲突）**

| 存量数据特征 | 回填 `status` | `status_assumed` | 依据 |
|---|---|---|---|
| `outcome ∈ {success, partial_success}` | `executed` | `false` | 有终态结果，流程必然走完，可判定 |
| `outcome = failure` | `failed` | `false` | 同上 |
| `outcome = rejected` | `rejected` | `false` | 同上 |
| `outcome ∈ {NULL, pending}` 且 `outcome_details` 含 `action_status` | `executing` | `false` | 有真实执行痕迹（`_backfill_decision_outcome` 只在 `_perform` 之后写该键），说明已派发未终结 |
| `outcome ∈ {NULL, pending}` 且无任何执行痕迹 | `pending` | **`true`** | **无法判定**是"待裁决"还是"已裁决未派发"。标 `status_assumed=true`，**不进队列** |

最后一行就是〈历史数据容错〉与 team-lead 追加要求的落点，也是"两套口径"的防冲突阀：`pending` + `status_assumed=true` 在**数据层**就不满足队列条件（`§5.5` 队列 Cypher 恒带 `coalesce(n.status_assumed,false)=false`），不靠前端过滤、不靠展示层遮。若不这么做，队列上线第一屏就是几百条历史假待办——恰好是演示现场最差的第一印象。

**为什么用 `CONTAINS 'action_status'` 而不是 `n.outcome_details.action_status`**：`outcome_details` 在图上存的是 **JSON 字符串**（`to_node_properties()` 第 123 行 `json.dumps(...)`），不是 map。写成属性取值会恒为 null，规则静默失效——这条本身就是一个容易踩的坑，写在这里防回退。

- **幂等性**：M1/M2 均带 `WHERE ... IS NULL` / `WHERE NOT ... IS ::` 守卫，**二次运行匹配 0 行**（`RETURN count(n)` 返回 0）。`status` 一旦写入即不再匹配，因此可以在 `ensure_indices()` 与 `list_decisions` 首行重复调用做读侧自愈。
- **存量默认值**：`status` 由 `outcome` 推导（语义保真），`entry_source=legacy`（明确标记来源不明，不伪装成 `manual`）。
- **读侧兜底**：`from_node_properties` 对缺失字段给默认值（`status→pending`、`entry_source→LEGACY`、`status_assumed→False`），即使迁移未跑也不会 500。
- **不建 UNIQUE 约束**：`uuid` 现为普通索引；改约束在存量重复时会让启动期索引创建失败。保持普通索引，重复风险记录为技术债。

### 4.4 索引变更（`ensure_indices`）

```cypher
CREATE INDEX decision_ws_status_created IF NOT EXISTS
  FOR (n:Decision) ON (n.group_id, n.status, n.created_at);
CREATE INDEX decision_ws_entry IF NOT EXISTS
  FOR (n:Decision) ON (n.group_id, n.entry_source);
CREATE INDEX decision_ws_agent IF NOT EXISTS
  FOR (n:Decision) ON (n.group_id, n.agent_id);
CREATE INDEX decision_ws_created IF NOT EXISTS
  FOR (n:Decision) ON (n.group_id, n.created_at);
```

复合 RANGE 索引（Neo4j 5.x）。既有 `CREATE VECTOR INDEX ... OPTIONS {indexConfig:{...}}` 已在用，可确认服务端 ≥ 5.11，语法可用。每条语句独立 try/except（沿用现有降级策略）：失败时记 warning 并依次尝试单属性索引 `ON (n.status)` / `ON (n.created_at)` / `ON (n.agent_id)`，最差退化为 `group_id` 索引 + 过滤。

`decision_ws_created` 是台账默认视图（`group_id` + `created_at` 倒序 + 30 天窗口）的专用索引——没有它，台账首屏就是全 label 扫描；`decision_ws_agent` 专供 Agent Tab（`group_id` + `agent_id`）。四个索引的写入放大在决策这种低频写入实体上可忽略。

---

## 5. 状态机与存储层新增能力

### 5.1 状态机（`decision_hub/state_machine.py`，手写 dict，零依赖）

```python
ALLOWED_TRANSITIONS = {
    "pending":   {"decided", "rejected"},   # 裁决：采纳 / 驳回
    "decided":   {"executing"},             # 派发执行（无「撤回采纳」，见下）
    "executing": {"executed", "failed"},    # 执行结果回写（内部驱动，非用户动作）
    "failed":    {"executing"},             # 重试执行
    "executed":  set(),                     # 终态
    "rejected":  set(),                     # 终态
}
```

- `assert_transition(current, target)` → 非法抛 **`ConflictError(msg, code="illegal_transition", details={"current_status": current})`**，映射 **409**（不是 500——非法迁移是可预期的客户端错误）。**不能抛裸 `ValueError`**：它会被 `ExceptionHandlerMiddleware` 当业务校验错映射成 400，契约里的 409 永远出不来，而"抛了 ValueError"的单测是全绿的
- `available_operations(status)` → `pending→["approve","reject"]`、`decided→["execute"]`、`failed→["retry"]`、`executing/executed/rejected→[]`
- **`pending` 不得直接跳 `executing`**（未裁决不许执行），`assert_transition("pending","executing")` 抛 `ConflictError` → 409
- **`decided → rejected` 与 `failed → rejected` 本期不开放**。理由：`decided` 已裁决，PM 明确要求次队列两档都"不可重复裁决"；在 `decided` 上允许 reject 等于把驳回变成"撤回采纳"这个第 4 个动作。`failed` 同理（它不是待裁决态）。这两个动作写进 §13 待 P1 评估，**不在本期留空壳，也不留一个"点了没反应"的按钮**
- **`failed` 不入队列**，所以 `retry` 只出现在详情页；`execute` 出现在队列 `to_execute` 档与详情页。二者由同一个 `available_operations()` 派生，不存在两处各判一次
- 批量裁决复用同一 `assert_transition`：逐条校验、逐条 CAS，单条冲突不影响其他条
- 不引入 `transitions` / `python-statemachine`（零依赖约束）

### 5.1.1 队列的「待裁定 / 待执行确认」分组（对齐 PRD §5.1）

PRD 要求队列分主队列（待裁定）与次队列（待执行确认）两组。落到本设计：

| PRD 用户可见分组 | 本设计判定条件 | 可做动作 |
|---|---|---|
| 待裁定（主队列） | `status = pending` 且 `status_assumed = false` | 采纳 / 驳回 / 批量 |
| 待执行确认·已裁决未派发（次队列 A） | `status = decided` | **发起执行**（可操作，不是只读） |
| 待执行确认·执行中（次队列 B） | `status = executing` | 只读查看进度 |
| 已闭环（不显示） | `status ∈ {executed, failed, rejected}` | 去台账查看 |
| 历史推定（不显示） | `status_assumed = true` | 详情页标注"历史数据，流程状态未记录" |

**次队列 A 必须可操作，这是对 PM 版定义的修正**（team-lead 已裁定）：PM 原定义把整个次队列写成"只读"，但 `decided` 的本质是"人已拍板、等待落地"——执行的前置态，不是终态。"采纳了却忘了执行"比"没人拍板"更隐蔽：前者表面上已经处理过了，不会出现在任何人的待办清单里，直到复盘才发现这个决策从来没落地。所以：

- 次队列 A（`decided`）→ `available_operations = ["execute"]`，可催办、可派发
- 次队列 B（`executing`）→ `available_operations = []`，只读
- **两档都"不可重复裁决"**（`approve` / `reject` 均不出现），PM E9/E9b 的两条语义都满足

`GET /api/decisions/pending` 返回**两组都含**（`items[i].group ∈ {"to_resolve","to_execute"}`），`to_resolve` 排在 `to_execute` 之前，组内按 `waited_minutes` 降序。次队列 A/B 的区分不在 `group` 上再加一层枚举——前端用 `items[i].decision.status`（`decided` / `executing`）直接分，契约面不再膨胀。

这样前端一个请求就能渲染 PRD 的两段分组与顶部四个计数，不必打两次接口，也不会出现"分组为空但计数非零"（`group` 与 `counts` 同源派生）。

### 5.1.2 `status` × `outcome` 合法组合矩阵（team-lead 要求，测试断言的直接来源）

两个状态字段并存的最大风险是出现 `status=executed` 但 `outcome=pending` 这类矛盾态——谁都不知道该信哪个。因此把合法组合穷举成常量表：

| `status` | 允许的 `outcome` | 语义 |
|---|---|---|
| `pending` | `pending` | 未裁决，不可能有执行结果 |
| `decided` | `pending` | 已裁决待派发 |
| `executing` | `pending` | 执行中，结果未出 |
| `executed` | `success` / `partial_success` | 执行完毕，必有结果。**`partial_success` 只在这里合法**——它是界面"部分成功"标签的唯一来源，语义是"事情做成了，只是没做全" |
| `failed` | `failure` | 终局失败。**不接受 `partial_success`**，理由见 §5.3 |
| `rejected` | `rejected` | 否决（含门禁拒绝） |

`6 × 5 = 30` 组合，**合法 7 个，非法 23 个**。典型非法组合与后果：`(executed, pending)` → 台账显示"执行成功"但结果待定；`(pending, success)` → 未裁决就已有成功结果，说明有人绕过裁决直接执行；`(rejected, success)` → 已驳回却执行成功；**`(failed, partial_success)` → 同一 outcome 值映射出两个界面标签，筛选与展示对不上**（这条是 PM 用具体故障路径论证后加进来的，此前本 Spec 曾允许它）。

**校验落点：写侧专用载荷 `StatusOutcomePatch`，不是 `DecisionRecord` 读模型。** 这是本设计里一个容易做错的决定，理由：

1. `DecisionRecord` 是**从图节点反序列化**的模型（`from_node_properties`）。若在模型上加 `model_validator` 做硬校验，任何一条历史脏数据都会让**读取**抛异常——列表页直接 500，为了防漂移把可用性搞挂，不划算。
2. 校验落点在**写侧专用载荷模型或服务层**，**不能放在 `DecisionRecord` 读模型上**。后端已实现的方式比我原先设想的更好，本 Spec 以它为准：`StatusOutcomePatch`（`status_matrix.py:65`）是专用写入载荷，`model_validator` 在构造时断言，`to_node_patch()` 把 `status` 与 `outcome` 合并成**单份** `SET n += $patch` 原子写。校验与原子写是同一步，不存在"校验通过了两者却被分两次写"的缝——这比在 `_build_patch()` 里先校验再分开写更安全。
3. **两类错误必须分开映射**，性质不同，混用会把排查方向带跑：
   - 非法**迁移**（`resolve` 打到一条已被别人裁决的决策）→ **客户端可修** → `409` + `ConflictError(code="illegal_transition", details={handler_name, current_status})`，响应体 `{"error": {"code": "illegal_transition", "details": {...}}}`。
   - 非法**组合**（`status` × `outcome`）→ **正常请求不可达**：四个写入方（resolve / execute / 批量 / pipeline 回填）全是服务端自己的代码，触发即意味着内部不变量被破坏，是 bug → `DecisionInvariantError` → HTTP **500** + `logger.error` 带 `decision_id` 与具体组合值。**不要映射成 409**：409 的语义是"你和别人撞了，换条路再试"；这里客户端换什么都不可能成功，把它伪装成可重试的冲突，会让人去查并发而实际问题在映射表。

**实现上的三个坑（都对着源码验过，任一个都会让前端拿到错误的东西）**：

1. `pydantic.ValidationError` **是 `ValueError` 的子类**，而 `model_validator` 只把 `ValueError` / `AssertionError` 收进 `ValidationError`。所以若 `assert_legal` 抛 `ValueError`，它会被 Pydantic 包成 `ValidationError`，再被 `ExceptionHandlerMiddleware`（`exception_handler.py:67`）当成 `ValueError` 映射成 **400** + `{"error": {type: "ValidationError", ...}}`——既不是 409 也不是 500。**两层包装必须一起看**：只改中间件那层不够，Pydantic 那层会先动手。当前实现抛 `DecisionInvariantError(Exception)`（不经 Pydantic 包装、不进 `ValueError` 分支）→ 落到通用分支 → 500，是对的。
2. `HTTPException(409, detail=<dict>)` 会被再包一层成 `{"detail": {...}}`，前端读 `res.reason_code` 恒为 `undefined`。409 走 `ConflictError(details={...})`，由中间件的 `APIError` 分支直出 `{"error": {...}}`。
3. **全链路不允许裸 `ValueError` 逃到中间件**：任何一处 `raise ValueError(...)` 到了全局中间件都会变成 400 + 另一套信封，而单测断言"抛了 ValueError"是完全绿的。
4. **读取侧只告警不抛错**：`from_node_properties` 发现非法组合时 `logger.warning` 并**以 `status` 为准**（`status` 是流程位置，`outcome` 是结果，冲突时流程位置更可信），前端 `DecisionStatusTag` 再叠 `WarningOutlined` + Tooltip 止血。

**断言必须双向**（PRD §8〈状态矩阵服务端强制〉口径）：30 组逐条断言——7 组合法逐条断言**放行**（能写入、能读回、标签符合 `FRONTEND_LABEL`），23 组非法逐条断言**被拒**（抛 `DecisionInvariantError`，**不是断言 HTTP 409**，理由见上）。只测"非法被拒"会漏掉"合法被误拒"，而后者是上线后才被用户发现的缺陷：一个合法的 `(executed, partial_success)` 若被矩阵误杀，全体"部分成功"决策就变成不可写的状态。

判定表与标签表放同一处（顺序一致，便于对照）：

```python
LEGAL_OUTCOMES = {
    "pending":   {"pending"},
    "decided":   {"pending"},
    "executing": {"pending"},
    "executed":  {"success", "partial_success"},
    "failed":    {"failure"},
    "rejected":  {"rejected"},
}
FRONTEND_LABEL = {
    ("pending", None): "待裁定",
    ("decided", None): "待执行确认",
    ("executing", None): "待执行确认",
    ("executed", "success"): "执行成功",
    ("executed", "partial_success"): "部分成功",   # 全仓唯一来源
    ("failed", "failure"): "执行失败",
    ("rejected", "rejected"): "已驳回",
}
```

### 5.2 `IDecisionStore` 新增方法

避免 12 个过滤参数 ×2 次重复（也为了守住「函数源码跨度 ≤40 行」），先引入查询对象：

```python
# interfaces/decision_query.py
@dataclass(frozen=True)
class DecisionQuery:
    workspace_id: str
    statuses: Tuple[str, ...] = ()
    outcomes: Tuple[str, ...] = ()                  # 多值：success + partial_success 需同时命中
    entry_source: Optional[str] = None
    decision_type: Optional[str] = None
    agent_id: Optional[str] = None                   # Agent Tab 数据源收窄（空间内维度，非租户边界）
    min_confidence: Optional[float] = None
    max_confidence: Optional[float] = None
    text_query: Optional[str] = None
    created_from: Optional[str] = None               # 归一化 UTC ISO8601
    created_to: Optional[str] = None
    exclude_assumed: bool = True                     # 队列传 True（排除历史推定），台账传 False
    sort_by: str = "created_at"                      # created_at|updated_at|confidence
    order: str = "desc"
```

`exclude_assumed` 默认 `True` 是**故意让危险值成为默认**：唯一会传 `False` 的调用方是台账（要看全量），漏传的后果只是"队列少了几条历史假数据"，而不是"队列被历史数据淹掉"。默认值应当把系统往安全侧推。

新增 4 个抽象方法：

```python
@abstractmethod
async def list_decisions(
    self, query: DecisionQuery, skip: int = 0, limit: int = 20
) -> List[DecisionRecord]: ...

@abstractmethod
async def count_decisions(self, query: DecisionQuery, probe: int = 5000) -> Tuple[int, bool]:
    """返回 (count, is_estimate)。命中 ≤ probe 时精确；超限返回 (probe, True)。"""

@abstractmethod
async def transition_status(
    self,
    decision_id: str,
    workspace_id: str,
    expected: Tuple[str, ...],     # CAS：仅当当前 status 命中才迁移
    to_status: str,
    patch: Dict[str, Any],         # outcome / outcome_details / resolution / action_record_id / updated_at
) -> bool: ...                     # False = 未命中（不存在 / 跨空间 / 状态不符）

@abstractmethod
async def append_reasoning_step(
    self, decision_id: str, workspace_id: str, step: Dict[str, Any], max_steps: int = 200
) -> int: ...                      # 返回写入后总步数；超 max_steps 抛 StepRejectError(422)，未命中抛 NotFoundError(404)
```

> **不要抛 `ValueError`**：它会被中间件映射成 400，与契约的 422 / 404 都对不上（§5.1.2 坑 3）。"抛了 `ValueError`"的单测是全绿的，所以这条只能靠 HTTP 层断言发现。

新增 1 个具体方法（非抽象，`Mixin` 内实现，供 pipeline 回写执行关联）：

```python
async def attach_action_record(
    self, decision_id: str, workspace_id: str, action_record_id: str
) -> None:
    """回写 decision.action_record_id（修复 B-3：该字段全仓从未被赋值）。

    只写这一个字段，**不碰 status / outcome**——调用点（pipeline `_perform`）此刻
    只拿到了关联句柄，还没有执行结果，硬写状态就是编造。
    `execute` 端点**不走本方法**：它同一时刻既知道 action_record_id 又知道状态，
    必须合成一份 `StatusOutcomePatch` 一次写完（§3.4 / §5.2.1）。
    """
```

**判据：同一时刻已经知道的两个字段，不能分两次写。** 两个写入方在"知道多少"上不同，所以写法不同——这不是不一致，是各自只写自己确实知道的东西。**"顺手多写一个默认值"是最常见的越界**：pipeline 若在 attach 时顺手把 `status` 写成 `pending`，就会把一条已被 `execute` 推进到 `executing` 的记录打回原点，而 CAS 条件让它看起来像"正常迁移"。

**破坏性影响（必须同 PR 修）**：`tests/unit/test_decision_record_isolation.py` 的 `FakeDecisionStore` 实现了全部 10 个抽象方法；新增 4 个 abstractmethod 后 `FakeDecisionStore()` 实例化会抛 `TypeError`，该文件 10 个用例全红。且 `attach_action_record` 实现于 `Neo4jDecisionQueryMixin`，Fake 直接实现 `IDecisionStore` 不会继承到它，hub 测试会 `AttributeError`。修复方式：给 Fake 补 4 个抽象方法内存实现 + 1 个 `attach_action_record`（合计约 45 行）。

**`count_decisions` 的两个调用方语义不同**：台账用 `probe=5000`（要 `total_is_estimate`）；队列的 `counts` 四计数必须先精确（否则"已超时 N 条"会骗人），故队列用 `probe=0`（无限精确）。队列数据量天然小（只含 pending/decided/executing 三态），精确计数可接受。

### 5.2.1 `status` 的四个写点（team-lead 第 8 轮追问，实测复查后本版新增）

**现状必须说清**：`status` 目前在整条链路上**没有任何一个写入点**。`update_decision_outcome` / `update_outcome` 的签名里没有 `status`，其 Cypher（`neo4j_decision_store.py:224-235`）只写 `n.outcome` / `n.outcome_details` / `n.feedback_summary` / `n.updated_at`；`decision_hub` 目前只有 2 个只读端点，`resolve` / `execute` / `batch-resolve` 都还没实现。这不是缺陷，是**写侧还没做**——但它意味着"加个字段"这件事只完成了读的一半，四个写点必须在 T3/T4/T5 里逐个指定，否则 `status` 会变成第二个 `action_record_id`（字段存在、序列化完整、永远为默认值）。

| # | 写点 | 迁移 | `status` / `outcome` | 同一份 patch 里还要写 |
|---|---|---|---|---|
| 1 | **建**（`POST /api/decisions`、pipeline `_build_decision_record`） | 无（新建） | `pending` / `pending` | `entry_source`、`status_assumed=false`、`recommended_action` |
| 2 | **裁决**（`POST /{id}/resolve`、`/batch-resolve`） | `pending → decided` 或 `pending → rejected` | `decided`/`pending` 或 `rejected`/`rejected` | `resolution`（含 `actor_type`） |
| 3 | **派发**（`POST /{id}/execute`） | `decided\|failed → executing` | `executing` / `pending` | 顶层 `action_record_id` + `outcome_details={action_record_id, action_status}`（§3.4） |
| 4 | **回填**（`pipeline._backfill_decision_outcome`） | `executing → executed\|failed\|rejected` | 按 §5.3 映射 | `outcome_details`、`feedback_summary` |

**纪律：这四个写点全部走 `StatusOutcomePatch.to_node_patch()`，禁止任何一处散写 `SET n.status = ...`。** 理由不是风格统一，是正确性：

- `status` 与 `outcome` 存在 §5.1.2 的 7/23 矩阵约束，散写会绕开 `model_validator`，让矩阵退化成一纸文档。**唯一能保证"非法组合写不进去"的方式，是让写 `status` 的代码路径只有一条。**
- 4 个写点若各自拼 Cypher，`updated_at` 的写法会出现四种版本，而 §3.2 的同步窗口计时**整个建立在这个字段上**。一处忘写，那一类记录的窗口就永远不老化。
- 写点 1 是唯一不走 CAS 的（新建无前态），写点 2/3/4 必须带 `WHERE status IN $expected`。**同一个 `to_node_patch()`，两种用法**：写点 1 走 `CREATE`/`set_node_properties`，写点 2/3/4 走 `transition_status`。

**因此 `IDecisionStore.update_outcome` 的签名要改**（T3 交付范围内，不是新增能力）：

```python
- async def update_outcome(self, decision_id, workspace_id, outcome, outcome_details, feedback_summary=None) -> bool
+ async def update_outcome(
+     self, decision_id: str, workspace_id: str, patch: StatusOutcomePatch, feedback_summary: str | None = None
+ ) -> bool
```

把 `outcome` 换成整个 `patch`，`status` 才有地方进来；`outcome_details` 也从"一个独立参数"变成 `patch.details` 的一部分——否则会出现"`status`/`outcome` 走 patch、`outcome_details` 走另一个参数"的两条路，而它们在语义上是同一次快照。**改签名会波及 `_backfill_decision_outcome` 与 `FakeDecisionStore`**，两处都在 T3/T6 的既有改动面内，不新增文件。

### 5.3 ActionRecord 状态 → DecisionStatus 映射

| ActionRecord.status | DecisionStatus | DecisionOutcome | 备注 |
|---|---|---|---|
| `pending` / `validating` / `approved` / `executing` | `executing` | `pending` | 结果未出 |
| `completed` | `executed` | `success` | 全部达成 |
| `rolled_back` | `failed` | `failure` | **终局是失败。** 达成项与被撤销项写 `outcome_details`：`{action_status:"rolled_back", achieved_items:[...], rolled_back_items:[...]}` |
| `failed` | `failed` | `failure` | — |
| `rejected` | `rejected` | `rejected` | — |

**`rolled_back` 不得映射为 `partial_success`**（PM 反对，采纳）。原因是一个会被用户直接撞到的故障，不是语义偏好：若 `failed` 也允许 `partial_success`，同一个 `outcome` 值会对应两个界面标签（`executed+partial_success` 显示"部分成功"、`failed+partial_success` 显示"执行失败"）——用户按"部分成功"筛选会返回标签写着"执行失败"的行，导出后按 `outcome` 排序与屏幕标签对不上，**台账里没有任何一个字段能解释自己看到的分组**。

原则写在这里，防止以后有人"顺手"加回来：**枚举值一旦能同时表示两种业务结论，它就不再是结论。** "部分达成后被回滚"这个事实用 `outcome_details` 结构化承载，不占用 `outcome`——`outcome` 是终局裁决的粗粒度结论，终局是失败就是 `failure`。

**顺带修一个存量缺陷**：现有 `_backfill_decision_outcome`（`pipeline.py:659-694`）**从不产出 `partial_success`**——它只有 `SUCCESS` / `REJECTED` / `FAILURE` / `PENDING` 四个分支，`rolled_back` 掉进 `else` 被写成 **`PENDING`**。也就是说"回滚"在现网被记成"结果待定"，属于 §4.2 提到的 `outcome` 语义污染的一个实例。

PM 复核后把这个缺陷说得更准（已采纳，写进 PRD §2.4 G3 第 5 条证据）：`ActionRequestStatus` 有 8 个值，落进 `else → PENDING` 的是 **5 个**——`pending` / `validating` / `approved` / `executing` / `rolled_back`。所以不是"`rolled_back` 掉进去了"，而是**同一个 `outcome=pending` 同时表示"还没人裁决""已派发正在跑""跑到一半回滚了"三件事**。这正是"垃圾桶"式映射的完整证据，也解释了它当初为什么看起来能覆盖一切——**一个把所有映射不上的状态都倒进去的桶，必然看起来完备，也因此永远无法用来推断流程位置**。T6 一并修：`rolled_back` 显式分支到 `failed` + `failure`，并把达成/撤销项写进 `outcome_details`。

**验收（PRD §8〈"已回滚"不得记成"待定"〉反例断言）**：跑一条**会回滚**的流水线产物，`outcome` 不得为 `pending`，台账结果列必须显示「执行失败」而非「待定」。该断言落在 T4 单测与 T11 种子（`rolled_back` 样本）两处，只测正向映射会漏掉这条。

### 5.3.1 `outcome_details.action_status` 是**快照**，不是残留判据（设计侧追问 + team-lead 必改，本版新增）

契约已把 `outcome_details` 从"零结构承诺"改成显式声明（`action_record_id` / `action_status` / `feedback_pipeline` / `achieved_items` / `rolled_back_items`），`action_status` 复用 `ActionRequestStatus` 8 态。但**声明它不等于能用它判残留**，这中间有一个必然会踩的坑：

`action_status` 由 `_backfill_decision_outcome`（`pipeline.py:686-692`）在**回写那一刻**写入。而"残留"的定义是"执行已提交、决策侧**尚未回写**"——也就是说，**残留窗口内 `action_status` 恰恰是缺失或过期的那个值**。用它判"回写是否完成"，逻辑上是拿"没写进去的东西"去证明"没写进去"。

因此定死三条：

1. **`action_status` 的用途**：详情页展示"精确动作状态（排队/校验中/已批准/执行中/已完成/失败/已回滚）"、`rolled_back` 的达成/撤销明细。**仅此两用。**
2. **残留判定的证据必须来自"另一个存储"**（PM 复核后把这一条提成了可验收的失败场景，采纳）：

   > 构造"节点侧只有 `outcome_details.action_status`、无关系库执行记录"的输入，断言**不得出现「状态同步中」**。

   理由是我上面那句循环论证的推论：`action_status` 与 `status` 写在**同一份节点 patch** 里，所以它俩永远同生同灭。拿它和 `status` 比，比的是"同一份 patch 和自己"，谈不上"两个信号不一致"。**节点侧的 `action_status` 不是第二信号，是同一份 patch 的回声。**
   - 因此 ①（有证据=状态同步中）的成立前提是：第二信号来自 `ActionRecord` 所在的**关系库**，按 `action_record_id` 实时读 `GET /api/actions/records/{id}`（单条回表，PRD §4.1 已允许）。
   - **只有节点侧 `action_status`、拿不到关系库记录时，必须按 ③ 处理**（承认不知道），**不得按 ①**。
   - 时间兜底仍在：超过 `SYNC_STALE_MINUTES`（见 §3.2）→ 降级为「状态可能未同步，请检查执行记录」。

   > **这笔工作量要记在详情页那侧，不记在通用封装里**（PM 记账纪律）：① 支从"读一个已在手边的字段"变成"按 `action_record_id` 多打一次关系库请求"，是本期的**新增一侧工作量**。**"反正详情页要跳执行记录"不产生这次读取**——"要跳转"只产生一个链接。已计入 T10（+0.5）。
3. **取不到就承认不知道**：既没有实时动作状态、又超过阈值 → 显示「状态可能未同步，请检查执行记录」，**不得**退化成"执行中"了事。否则 PM 要堵的"永久不可证伪"只是从"永久同步中"换成了"永久执行中"，一寸没前进。
4. **取值不在 8 值枚举内 → 视为"不可判定"，不得当终态**（设计侧补充，team-lead 转达采纳）：`ActionRequestStatus` 以后若新增第 9 个值时，**旧前端一定先于新前端上线**。届时详情页读到未识别的字符串，只有两种处理方式：当成"未知，按进行中处理（显示执行中/可能未同步）"，或当成终态。**必须选前者**。选后者的后果是：一个新增的中间态被旧前端渲染成"已完成"，而"已完成"是不再变化的终态——用户会以为事情结束了，实际还在跑。这正是 §5.3「垃圾桶映射」的同一个病：**未知值必须流向"不确定"，不能流向"终局"**。
   **本条只管"字段取值怎么解释"，不管"界面说哪句话"**（PM 指出两者同构但不可合并）：字段层判成"不可判定"之后，界面层还有一次选择——显示"执行中"还是"状态可能未同步 + 出口"，那一步是 §7 三级判定（②/③）的职责。**合成一条的后果是"不可判定"被直接实现成"显示执行中"，而"永久执行中"正是这条要堵的洞。**
5. **`execute` 路径必须写这个键**（§3.4）：`_backfill_decision_outcome` 只在执行**结束之后**写，所以"刚点完发起执行 → 下一次回填"这段真实窗口里，`outcome_details` 是空的。如果 execute 不写，详情页「8 态精确展示」就在用户最需要它的时刻恒为空，而 `status=executing` 本身也分不清"派发了在跑"和"根本没派发"。**写它零成本**（那次状态映射回写本来就要发生），不写则等于用一个长窗口的假状态替换掉一个短窗口的假状态。

> 这一条是"字段存在"与"字段可用作判据"的区分。设计侧最初的版本用 `sla_state ∈ {warning, breached}` 当残留判据，更糟：`sla_state` 只在 `/pending` 的 `PendingDecisionItem` 上，详情页根本没有这个字段，那条判据**恒为假**——写了一行永远不成立的判断，测试还会因为它不触发而全绿。

### 5.4 分页策略：skip/limit vs cursor


**选择 skip/limit + 独立 COUNT**。理由：

1. 台账 UI 必须显示「共 N 条」，cursor 分页天生拿不到 total，仍需额外一次 count。
2. 台账是低频只读页，深翻页罕见；demo 数据量 < 10k，`SKIP` 的 O(skip) 代价 < 50ms。
3. 排序键 `created_at` **非唯一**（同秒多条），正确的 keyset 必须用 `(created_at, uuid)` 复合游标，前后端复杂度各升一档，收益在 10k 量级为零。
4. 与仓库既有 `list_decisions`（`page/page_size/total`）命名一致，前端筛选组件无需两套分页模型。

**切换阈值（写进代码注释）**：单 workspace `:Decision` > 50,000 条 或 台账 p95 > 300ms → 改 keyset `(created_at, uuid)`，新增 `cursor` 参数与 `page` 并存（向后兼容），再下线 `page`。

### 5.5 Cypher 实现要点

```cypher
// list：所有过滤条件用参数 null / 空列表短路（避免字符串拼接）
MATCH (n:Decision {group_id: $ws})
WHERE ($statuses = [] OR n.status IN $statuses)
  AND ($outcomes = [] OR n.outcome IN $outcomes)
  AND ($entry_source IS NULL OR n.entry_source = $entry_source)
  AND ($decision_type IS NULL OR n.decision_type = $decision_type)
  AND ($agent_id IS NULL OR n.agent_id = $agent_id)
  AND ($min_conf IS NULL OR n.confidence >= $min_conf)
  AND ($max_conf IS NULL OR n.confidence <= $max_conf)
  AND ($exclude_assumed = false OR coalesce(n.status_assumed, false) = false)
  AND ($q IS NULL OR n.context_summary CONTAINS $q OR n.recommended_option CONTAINS $q)
  AND ($from IS NULL OR n.created_at >= $from)
  AND ($to   IS NULL OR n.created_at <= $to)
RETURN n ORDER BY <白名单分支> SKIP $skip LIMIT $limit

// count（带 probe 上限，供 total_is_estimate）
MATCH (n:Decision {group_id: $ws}) WHERE <同 list 的过滤条件>
RETURN count(n) AS c LIMIT 1        -- probe=0 时（队列四计数）
// probe>0 时的写法：先 LIMIT probe+1 再数，命中 probe+1 即判 estimate
MATCH (n:Decision {group_id: $ws}) WHERE <同 list 的过滤条件>
RETURN n LIMIT $probe_plus_one

// transition（CAS）
MATCH (n:Decision {uuid: $did, group_id: $ws})
WHERE coalesce(n.status, 'pending') IN $expected
SET n += $patch
RETURN n.uuid AS uuid

// append_reasoning_step：reasoning_trace 是 JSON 字符串，Neo4j 无法原子 append，
// 故用「读 → Python append → 以旧原始串为 CAS 条件回写」，冲突重试 1 次
// 步骤 1：MATCH (n:Decision {uuid: $did, group_id: $ws})
//         RETURN coalesce(n.reasoning_trace, '[]') AS raw
// 步骤 2：MATCH (n:Decision {uuid: $did, group_id: $ws})
//         WHERE coalesce(n.reasoning_trace, '[]') = $raw          // CAS
//         SET n.reasoning_trace = $next, n.updated_at = $now
//         RETURN size($steps) AS step_count
```

- `sort` / `order` 只能来自枚举白名单拼入 Cypher（防注入），与既有 `add_causal_link` 的 `edge` 拼接同一手法。
- `IN $statuses` 且 `$statuses = []` 时短路——空列表不能直接用 `IN`（`x IN []` 恒 false），故用 `$statuses = []` 先判。`$outcomes` 同理。
- `ORDER BY n[$sort]` 不被 Cypher 支持，实际实现按白名单分支生成三条固定语句（`created_at` / `updated_at` / `confidence`），避免动态属性名。
- **`evidence_count` 排序已降 P1**（team-lead 裁定）。当时的实现结论留档：`evidence_entity_ids` 在图上存 JSON 字符串，`size()` 对它无效，必须写时算派生属性 + M3 回填。P1 捡起来时照此做，本期不建 M3、不输出派生属性。
- `created_at` 是字符串：`to_node_properties` 改为统一输出定宽格式 `YYYY-MM-DDTHH:MM:SS.ffffff+00:00`（`_iso_utc()` 助手），保证字典序 == 时间序；M1 迁移把历史 temporal 类型归一为同格式字符串。

**队列专用 Cypher（与 §5.1.1 同源派生，不另写一遍条件）**

```cypher
// 待办域 + 分组 + 四计数，一次聚合算完，再据此取当页
MATCH (n:Decision {group_id: $ws})
WHERE n.status IN ['pending','decided','executing']       // 服务端硬编码，无入参
  AND coalesce(n.status_assumed, false) = false            // 排除历史推定（§8〈历史数据容错〉）
WITH n, CASE WHEN n.status = 'pending' THEN 'to_resolve' ELSE 'to_execute' END AS grp
RETURN grp, count(n) AS c
```

`counts.to_resolve` / `counts.to_execute` 直接取这个聚合结果，`counts.sla_warning` / `counts.sla_breached` 由 `waited_minutes` 在 Python 侧按同一批记录二分成 `(24h, 72h]` 与 `>72h`。**四个计数与 `group` 字段共用同一 `grp` 表达式**，这是"不许两处各写一遍"在代码上的落点。

### 5.6 Neo4j 读写拆分（守住 300 行）

| 文件 | 内容 | 目标行数 |
|---|---|---|
| `impl/neo4j_decision_store.py` | 驱动单例 + `ensure_indices` + `save_decision_node` + 4 类建边 + `update_outcome` | ~288（现 408） |
| `impl/neo4j_decision_query.py`（新） | `Neo4jDecisionQueryMixin`：`trace_chain` / `find_similar_by_text` / `analyze_impact` / `list_decisions` / `count_decisions` / `transition_status` / `append_reasoning_step` / `attach_action_record` / `migrate_legacy_fields` | ~290 |

`class Neo4jDecisionStore(Neo4jDecisionQueryMixin, IDecisionStore)`——单继承链 + 一个 mixin，纯方法搬迁，无逻辑改写，`get_decision` 留在 store 侧供 mixin 调用（MRO 正常解析）。

---

## 6. 工作空间隔离 Checklist（逐条对照 ADR-076 §7）

| # | ADR-076 §7 条目 | 新端点如何覆盖 | 覆盖位置 |
|---|---|---|---|
| 1 | 路由层解析，覆盖客户端值 | 7 个新端点**均不提供** workspace 入参；`workspace_id: str = Depends(get_current_workspace)`。客户端无任何途径指定空间 | `decision_hub/api/routes.py` |
| 2 | 非空拒绝（422） | `get_current_workspace` 对空/缺失声明抛 422（fail-closed），不做 `user_id` 兜底 | `infra/security/workspace_access.py:154-173`（复用） |
| 3 | 存储层双保险：读路径 `WHERE group_id = $ws` | `list_decisions` / `count_decisions` / `list_pending` 的 MATCH 强制 `{group_id: $ws}`；`decision_id` 查询一律带 `workspace_id` 双条件 | `decision_query.py` |
| 4 | 更新条件含 `decision_id AND workspace_id` | `transition_status` / `append_reasoning_step` / `attach_action_record` 的 MATCH 均为 `{uuid: $did, group_id: $ws}`，CAS 额外加 `status IN $expected` | `decision_query.py` |
| 5 | 跨空间不泄漏存在性 | `resolve` / `execute` / 批量 / `reasoning-steps` 的失败统一表述为"不存在或不属于当前工作空间"，HTTP 一律 **404**（批量则归为 `not_found`），与 `PATCH /{id}/outcome` 既有行为一致 | `hub.py` |
| 6 | 队列不能绕过状态语义 | `list_pending` 的 `statuses` 由服务端硬编码注入 `("pending","decided","executing")`，请求参数不存在 `status` 字段 | `hub.py` |
| 7 | 向量/文本检索 `group_ids` 过滤 | 台账不做向量检索；先例检索沿用既有 `find_similar_decisions`（`group_ids=[ws]`），不改 | 无变化 |
| 8 | 审计必须带 workspace | `resolve` / `execute` / `batch_resolve` / `export` / `reasoning-steps` 写均写审计，payload 含 `workspace_id`（`resolve`/`execute` 走 Graphiti 审计 Episode；`export` 走 `unified_audit.log_audit`，与既有 `_audit` 惯例一致） | `hub.py` |
| 9 | OPA 门禁不被绕过 | `execute` 前不重复做 OPA（`ActionService` 内部已有 OPA 校验 + fail-closed），避免双重门禁不一致；决策侧 OPA 仍由 `POST /check-rules` 提供 | `hub.py` 注释说明 |
| 10 | 跨空间因果边 | 沿用 `add_causal_relationship` 的同空间校验 + 环检测，不改 | 无变化 |
| 11 | 裁决权限（PRD §8〈权限不足时列表仍可读〉，"看 ≠ 判"） | `resolve` / `batch-resolve` 在 CAS 之前调既有 OPA ABAC（`OPAManagerV2.check_permission_abac`，action=`decision.resolve`）；无权限返回 **403** 且**列表仍可读**（读接口不做该判定）。无 OPA 可用时 **fail-closed** 拒绝裁决 | `hub.py` + `infra/opa/opa_service.py`（复用） |
| 12 | 批量跨空间条目 | 逐条 CAS 含 `group_id`；任一条不属当前空间 → 该条 `not_found`，不影响其他条，不泄漏存在性 | `ledger_service.py` |
| 13 | **G6 收口：agent 链不留后门** | 5 个端点整体删除（含 `router_registry` 注册），能力由台账 `?agent_id=` + `…/reasoning-steps` 承接。删除后无任何"无 workspace 参数"的决策读写路径 | 见 §3.8 |
| 14 | **G6 单对象读取** | 原 `GET /api/agent/decisions/{id}` 与 `/{id}/chain` **凭 ID 即可越权**（IDOR）。替代端点一律走 `{uuid, group_id}` 双条件，跨空间 → 404 | `decision_query.py` |
| 15 | **G6 空值契约** | 决策域**全链路** `workspace_id` 缺失即 422（`get_current_workspace` fail-closed），**不存在**"空则不过滤"分支。新增回归用例：空 workspace 上下文 + 存在跨空间数据 → 拒绝且零条数据 | `tests/unit/test_decision_workspace_isolation.py` |
| 16 | **G6 残余内存单例** | `core/agent/services/decision_service.py` 的 dict 只作未落库缓冲，其对外方法一律要求 `workspace_id` 入参并做 `chain.workspace_id != workspace_id` 归属校验，不匹配按 not found；**不再提供 list / chain 读取** | T7 |
| 17 | **404 一律优先于 403**（team-lead 修正 1） | 逐端点复核：跨空间命中 = 404（不泄漏存在性）；仅"已确认属于当前空间但无操作权限" = 403。全端点表见 §3.2-§3.7 的错误码行，无一处反过来 | `hub.py` 各方法、`resolution` 复用 `assert_workspace_access` 的 403 分支 |
| 18 | **队列不吞历史推定数据** | `list_pending` 的 `exclude_assumed=True`（§5.2 默认值），Cypher 恒带 `coalesce(n.status_assumed,false)=false`。反例断言：造 5 条 `status=pending, status_assumed=true` 的历史数据，队列 `total` 必须仍为 0 | `ledger_service.list_pending` + `test_decision_hub.py` |
| 19 | **SLA 阈值不可被客户端改写** | `SLA_WARNING_MINUTES` / `SLA_BREACH_MINUTES` 只从 `settings` 读；`PendingQueue` 的请求模型**不存在**任何 SLA 相关字段（前版有 `sla_minutes` / `stale_minutes`，已删）。反例断言：请求带 `sla_minutes=99999` 不改变 `sla_state` | `models.py`（请求模型）+ `test_decision_ledger_api.py` |
| 20 | **`status` × `outcome` 非法组合不可写入** | `StatusOutcomePatch` / `assert_legal`（§5.1.2）用 `LEGAL_OUTCOMES` 断言；6×5=30 组合**双向断言**：7 组合法逐条断言放行、23 组非法逐条断言抛 `DecisionInvariantError`（PRD §8〈状态矩阵服务端强制〉口径：只测"非法被拒"会漏掉"合法被误拒"）。**非法组合是内部不变量被破坏 → 500 + error 日志，不是 409**（正常请求不可达，四个写入方都是服务端代码）；读取侧仅告警不抛错 | `status_matrix.py` + `test_decision_hub.py` |
| 21 | **分组与计数同源、计时基准分档** | 造 3 条 `decided` → `counts.to_execute == 3` **且** `group=to_execute` 非空；造 0 条 → 计数为 0 且该组为空。`to_resolve` 行的 `sla_state` 必须由 `created_at` 推出，`to_execute` 行必须由 `resolution.at` 推出（造一条 `created_at` 是 5 天前、`resolution.at` 是 1 小时前的 `decided`，其 `sla_state` 必须是 `ok` 而非 `breached`）。**两个等待时长必须断言"有差异"，不是"有值"**（PRD §8〈等待时长不得张冠李戴〉）；**该断言在字段补齐前必须是红的，不得写成 skip**——"字段还没加"是红灯的理由，不是跳过的理由：同一条记录 `waited_minutes ≥ 7000` 且 `decided_waited_minutes ≤ 120`，**并断言两者的比值**——禁止写成 `assert item.decided_waited_minutes is not None`，那个断言会被"把 `created_at` 抄给两个字段"的实现通过，而那正是唯一要防的错误 | `ledger_service.py` + `test_decision_ledger_api.py` |
| 22 | **跨库残留态可自愈（不是 happy-path 幂等）** | 构造一条停在 `executing` 而对应 ActionRecord **已终结**（`completed` 或 `failed`）的记录，再次调 `execute`：断言它**自愈到终态**（`executed`/`success` 或 `failed`/`failure`）、`idempotent_replay=true`、且 **ActionRecord 数量仍为 1**。只测"连点两次都成功"不算覆盖 | `hub.py` + `test_decision_hub.py` |
| 23 | **推理步骤上限是容量问题，不是输入问题** | 达到 200 条时返回 `422` + `{"error": {"code": "step_limit_reached", "details": {"field": null, "step_count": 200, "limit": 200}}}`。反例断言：① `error.details.field` 必须为 `null`，前端无法把它归到某个表单项；② 已存在的 199 条步骤读回来状态正常（不得因为追加失败而被渲染成失败）；③ 其余三种 `error.code` 才带 `field` | `hub.py` + `test_decision_hub.py` |
| 24 | **错误必须打到 HTTP 层，且契约里的状态码不能在运行时被换掉**（PRD §8〈拒绝必须能被界面读出来〉，本轮新增） | 每个非 2xx 分支断言**三件事**：状态码、**响应体形状**（`{"error": {...}}` 还是 `{"detail": ...}`）、以及读哪个键（`error.code` / `error.details.*`）。反例断言：409 分支不得返回 400/422（服务层抛 `ValueError` 会被中间件映射成 400，而单测断言"抛了 ValueError"照样全绿）；非法 `status×outcome` 必须 500 而非 409；**按 AC-17 断言 403 / 404 / 模块级 422 的响应体是 `{"error": ...}` 且 `error.code` 分别是 `forbidden` / `not_found` / 对应码**——路由体若还在 `raise HTTPException`，这条必红（形状回归 `{"detail": ...}`）。**这一类缺陷只在 HTTP 层可见**——服务层每一步都对，错误在到达前端之前被换了形状 | `test_decision_hub.py` / `test_decision_ledger_api.py`（`TestClient`，不打服务层） |

---

## 7. 前端设计约束（P0 规则落地）

- **图标库锁定**：`@ant-design/icons@6.1.1`（已在 `apps/web/package.json:19`，零新增依赖）。`menu_config` seed 中的 icon 字段本身即为 AntD 图标名（`seed_four_steps.py:250` `FundOutlined`），保持一致。**禁止**引入 `lucide-react` / `react-icons` / iconfont，**禁止** emoji 作为功能图标。
- **颜色零硬编码**：新组件一律 `const { token } = theme.useToken()`，用 `token.colorPrimary / colorSuccess / colorError / colorWarning / colorTextSecondary / colorBorder`。禁止 `#722ed1`（紫）、`#1677ff` 等字面量，禁止紫→粉渐变。
- **既有违规一并清理**：`components/DecisionChainGraph.tsx:14-20` 的 `NODE_COLORS` 硬编码（含紫色 `#722ed1`）在 T9 改为从 `theme.useToken()` 取值后传入 G6 图配置（G6 不消费 CSS 变量，必须由 JS 传值）。
- **状态/来源展示**：`STATUS_META` / `ENTRY_SOURCE_META` 只放 `label` + `token 名称`，不放十六进制色值；`Tag` 用 AntD 语义色（`color="success"` / `"error"` / `"processing"` / `"default"`）。
- **结果标签收敛为 4 色系、界面只出 5 类标签**（PM 定调，设计侧已回写 uiux.md）：执行成功 / 部分成功 → `success`；执行失败 → `error`；待定（待裁定）/ 待定（待执行确认）→ `warning`；已驳回 → 中性。**内部派生模型仍是 6 态**（待裁定可操作、待执行确认只读，行为不同必须分开），界面映射只在 `DecisionStatusTag` 一处，禁止三处各写一份（PRD US-8）。`info` 系只用于"执行状态"列（排队/校验中/执行中/已批准），不参与结果标签，因此不构成第 6 个色系。
- **映射函数签名必须是 `toDisplayLabel(status, outcome)`**（设计师 D-2）：`DecisionStatus` 六值里**没有** `partial_success`，它只在 `DecisionOutcome` 里；只吃 `status` 会把「部分成功」丢掉——而它是 PRD §4.1.1 的 5 类标签之一。`DecisionRecord.status` 的契约描述里已加一句"`executed` 需配合 `outcome` 区分成功/部分成功"防止后续误用。
- **`available_operations` 为空时不渲染按钮组**（设计师 D-1，采纳）：`to_execute` 的行右下角不出现灰按钮，改显示一行次要色文字「已裁决，等待执行完成（{执行状态}）」。禁用态是给"你没权限"用的（PRD §5.6 要求按钮存在但禁用 + Tooltip 说明所需权限）；"这个动作对谁都不存在"却渲染灰按钮，会让用户反复点并怀疑自己缺权限。两种语义不能混用同一表现。
- **列表「执行状态」列 = 4 档 + 1 空态**（详见 §3.2）：`executing` 进行中 / `executed` 已完成 / `failed` 失败或已回滚 / 其余未派发未开始 / **`decided` 空态（显示"—"）**。`decided` 不并入"进行中"也不并入"未开始"——它的下一步动作是"发起执行"，并档会盖住次队列要堵的漏点。全部只读 `status`，零额外查询；精确的 ActionRecord 8 态细分只在详情页单条回表一次。
- **详情页的「执行状态」是三级判定，不是两级**（设计侧补充第 3 支，采纳）：

  | 级 | 条件 | 显示 | 性质 |
  |---|---|---|---|
  | ① | 实时动作状态为终态，且 `updated_at` 在阈值内 | 状态同步中 | **有证据**：两个信号不一致 |
  | ② | 实时动作状态为进行中 | 执行中 | **有证据**：两个信号一致 |
  | ③ | 取不到实时动作状态，且 `updated_at` 超过阈值 | 状态可能未同步，请检查执行记录（+ 跳转） | **无证据**：承认不知道 |

  第 ③ 支的关键：**① 是断言（"我知道结果出来了，只是没写回"），③ 是承认（"我不知道，你去看看"）**，用同一句话表达这两件事，等于把不确定伪装成确定。**如果没有 ③**，那"取不到动作状态"这一支就变成新的永久不可证伪状态——"永久同步中"只是换成了"永久执行中"，一寸没前进。
  - 数据来源注意：① 的"实时动作状态"必须来自**实时读执行记录**（`GET /api/actions/records/{id}`），**不能读 `outcome_details.action_status` 的快照**——残留窗口内快照恰恰是缺的那一项（§5.3.1）。
  - 阈值 `SYNC_STALE_MINUTES` 默认 10 分钟，定义在前端常量（`constants/decisionConfig.ts`）；**ADR 不写这个数字**，只写口径区分（见 §11「已知边界」）。
- **残留态只在详情页表达「状态同步中」，台账列表不出这一档**（PM 第 8 轮否决列表侧，采纳）：`status=executing` 但回写未完成时，详情页必须表达"不确定"，不得把不确定伪装成确定；**且超过 `SYNC_STALE_MINUTES`（默认 10 分钟）必须降级**为「状态可能未同步，请检查执行记录」+ 执行记录跳转入口——无限期的"同步中"是用户无法证伪的状态，等于替系统兜住一次失败。列表侧维持 4 档 + 空态（`executing` → 「进行中」），理由见 §3.2：列表的 DTO 里没有"回写是否完成"这个信息，唯一可用信号在**每次正常执行**里都成立，硬猜会让告警在正常路径上闪，把真正的异常淹掉。详见 §3.2 与 §5.3.1。
- **组件归属分工（第 6 轮裁定：设计侧 4 个文件移交前端）**：`DecisionStatusTag.tsx` 新建、`OUTCOME_META`（`types.ts:68-74`）下线、`PrecedentSearch.tsx:64,74`、`DecisionIntelligencePage.tsx:53,92` 四处调用点替换，**改由 `mvp-dev-expert-team-frontend` 落地**，须在 T9 之前合并。理由（设计侧提出，我认同）：这 4 个文件是纯展示层改动，前端有 code review 承接链而设计侧没有，放在没人 review 的通道里改动越多风险越大。
  - **移交判据不是"文件列表"，而是接口形态**：`displayStatus.ts` 必须**零颜色字面量**，5 个纯函数：`toDisplayLabel(status, outcome)` / `toStatusToken(status)` / `toExecutionTier(status)` / `toExecutionLabel(status)` / `toLedgerQuery(filters)`。颜色只在 `DecisionStatusTag` 里经 `theme.useToken()` 取。满足这条才算可移交——否则颜色逻辑会跟着搬过去又搬回来。
  - **`toExecutionTier` 与 `toExecutionLabel` 必须是两个函数，不能合并成一个 `toExecutionCell`**（设计侧指出，team-lead 已批，前缀版本写错已改）：前者出**台账 4 档**（未开始 / 进行中 / 已完成 / 失败或已回滚）+ 空态「无动作」；后者出**详情 8 态**（`pending` / `validating` / `approved` 必须分开）。合并的后果是二选一——台账显示 8 态（列表被撑爆，用户不需要在列表区分"门禁在算"和"批了没跑"），或详情只剩 4 档（用户点进详情就是为了排查，把"没人派发"和"门禁在算"合并等于把答案藏掉）。两者数据源同为 `outcome_details.action_status`，但**抽象层级不同，不能共用**。
  - **`toStatusToken` 只返回语义等级**（`warning` / `success` / `error` / `neutral`），**不返回 token 名**（如 `--odap-color-warning`）。token 名已经是颜色体系的一部分，返回它等于把颜色决策搬进 `displayStatus.ts`，"零颜色字面量"这条判据就失守了。语义等级到具体 token 的映射只在 `DecisionStatusTag` 里做。
  - **`toDisplayLabel` 与 `toLedgerQuery` 必须同人同批维护**：前者把 `status×outcome` 映射成 5 类标签，后者把界面筛选项映射成 `outcome` 多值数组；改一个不改另一个，就会出现"筛选项写着部分成功、标签渲染成执行失败"。
  - **落地顺序**：`displayStatus.ts` + `DecisionStatusTag` → 台账 → 队列 → 详情。倒过来做会让后三个页面各自临时写一份标签逻辑，`DecisionStatusTag` 落地时又得回头清理。
  - **留在架构侧（T9/T10）的部分**：`DecisionChainGraph.tsx` 的 `nodeColors?: Record<string,string>` prop 签名与传值、`useEffect` 依赖修正、`ImpactPanel` 的部分拷贝、`DecisionIntelligencePage` 的页面组装与路由。双方都改 `DecisionIntelligencePage.tsx`，约定：前端先交 `DecisionStatusTag` + 替换 diff，我在 T9 基于其合并后的版本继续改组装，不回退其改动。
- **路由体内禁止 `raise HTTPException`**（AC-17，team-lead 锁定）：决策模块自己判定的错误一律走 `APIError` 家族，**`403` / `404` / 模块级 `422` 全部改走信封并带 `error.code`**（`not_found` / `forbidden` / `missing_action_payload` / `batch_empty` / `batch_size_invalid` / `reason_required`），全表见契约 `ErrorCodeCatalog`。

  > **范围必须逐字对齐（PM 第 9 轮实测纠正）**：AC-17 写的是"决策模块路由体内"，那么它覆盖的是**三个** `api/routes.py`，不是新增的那一个。前版门禁只扫 `odap/biz/decision/decision_hub/`，于是 `decision_record`（9 处）与 `decision_recommendation`（5 处）**共 14 处违规被绿着放过**。
  >
  > **这是"判据的覆盖范围比规范窄"——绿是判据的属性，不是代码的属性。** 与我上一轮否掉"行与行互比"的错法一模一样：那次是基准错，这次是范围错。**门禁的扫描路径必须从 AC-17 的文字里抄，不能从"这次改了哪个目录"里抄。**
  - **理由不是洁癖**：不禁的话，"同一接口的错误体形状"取决于后端随手选了哪个异常类，而不是取决于接口语义。前端就只能对每条路径各写一套兼容分支——**那不叫兼容，叫没有契约**。
  - **两处例外，都不是漏改**：① `401` 与"JWT 缺 `workspace` 的 `422`"由 `infra/security/*` 的**共享依赖**在进入路由体之前抛出（`jwt_auth.py:29/35/65`、`workspace_access.py:163-172`），决策模块改不了；② 框架字段级 `422` 是 `{"detail": [...]}`（无 `RequestValidationError` 处理器）。要消灭①得改全仓每个域共用的路径，与"能局部解决就不要全局改"直接冲突。
- **错误读取必须只有一处封装，但要拆成两层文件**（PRD §8〈拒绝必须能被界面读出来〉第 1 条；两层拆分由设计侧提出，采纳）。本域同时存在两种错误体：`APIError` 家族的 `{"error": {type, code, message, request_id, path, details?}}`（本域自己判定的全部 4xx/5xx）与共享依赖产出的 `{"detail": "..."}`（仅 401 与 JWT 缺声明 422），另有 FastAPI 字段级 422 的 `{"detail": [...]}`（数组）。
  1. **`modules/shared/services/apiError.ts`（域无关）**：`parseApiError(resp) → { status: number; code?: string; message: string; details?: Record<string, unknown>; requestId?: string }`，只负责把三套形状读成同一个结构。**这是唯一允许出现 `resp.error` / `resp.detail` 判断的地方**——三处各写一套，同一个 409 会在一页显示"已被处理"、另一页显示"操作失败"。
     **`status` 必须是返回结构的一部分，不是附加信息**（设计侧指出，采纳）：AC-17 的例外一让 `401` **没有 `code`**，而 401 与 403 的动作完全相反——

     | | `401` | `403` |
     |---|---|---|
     | 有无 `code` | **无**（共享依赖产出 `{"detail": ...}`） | `forbidden` |
     | 正确动作 | **跳登录页** | 就地提示，**不跳转、不清空页面** |

     只按 `code` 判，401 会落进"未知原因"通用提示——用户只是登录过期，看到的却是"操作失败"，而且**不会自动去登录**。把 401 的判据挂在 `code` 上，等于把一个"能自愈的状态"变成一个"需要用户自己想明白的报错"。
  2. **`modules/decision/utils/errorMessages.ts`（域相关）**：`code → 文案` 的映射，以契约 `ErrorCodeCatalog` 为穷举源。**不混进 `apiError.ts`**：否则第二个域接信封时会把决策域的文案表一起搬走——**域无关的读取逻辑和域相关的文案表，生命周期不一样**。
  3. **旧形状走降级不崩**：`detail` 是字符串就直接当 `message`；是**数组**取 `detail[0].msg`。直接塞数组进弹窗会渲染成 `[object Object]`。
  4. **`code` 缺失时不是"一句通用文案"，而是按 `status_code` 分档**（PM 提出，采纳）：

     | `status_code` | 缺码时的通用文案 | 不得写成 |
     |---|---|---|
     | `404` | 找不到该内容，或你没有权限查看 | 操作失败／"决策不存在" |
     | `403` | 没有权限 | 操作失败 |
     | `409` | 已被其他人改动，请刷新 | 操作失败 |
     | `500` | 服务异常，请提供 `request_id`（可复制） | 操作失败 |

     **404 的文案不得写"不存在"，也不得回显 `decision_id`**（设计侧提出，采纳）：契约里 `not_found` 的定义是"不存在**或跨空间**（两者不区分，不泄漏存在性）"，所以真实情况有三种——真不存在 / 属于别的空间 / 你没有权限看。写"决策不存在"在跨空间时**是一句假话**，而且会引导用户反复输入同一个 ID 去试。
     理由不是措辞偏好，是 `code` **覆盖面不均**的连带后果：同一个 `404` 在决策模块带 `not_found`、在别的域不带码（共享依赖产出的 `{"detail": ...}`）。缺码时统一回落成"操作失败"，会让**同类错误在两个页面呈现两种体验**——用户不会说"这个接口没迁移"，他只会说"这系统一会儿正常一会儿抽风"。
     **底线不变**：`code` 缺失只说明"这个分支没有机器可读原因"，**不得**当成成功、不得跳过提示、不得让 `undefined` 出现在界面上。
  - **前端靠 `code` 判断，不靠文案**：`code === 'illegal_transition'` → "该决策已被处理，请刷新后重试"；`code === 'execute_in_progress'` → "正在派发，请稍后刷新"。用文案匹配会在改一句话时静默失效。
  - **`details` 的读法必须是两层，不是一层**（设计侧指出我一处表述错误，采纳）：不能"直接读 `details.field`"，因为 409 的 `details` 形状是 `{handler_name, current_status}` 或 `{}`，**没有 `field` 键**，而 `details` 本身还是 `nullable`：
    ```ts
    const details = err.details ?? {};      // 收 null
    const field = details.field ?? null;    // 收 undefined
    if (field) { 挂到该字段 } else { 挂整体 }
    ```
    **`field` 三键恒存在只在 422 `StepRejectDetail` 上成立**（`{field, step_count, limit}`），不能推广到 409。意图不变：**不判键在不在，只判值**——`null` 与键缺失收敛到同一行为，这样"键缺一次就静默走另一支"那类错就没有发生的位置。
  - **500 的 `request_id` 必须可复制、不得藏在 Tooltip 里**（设计侧补充，采纳）：500 时用户唯一能提供给排查的信息就是它，而它确实是前端拿到的值。藏在悬浮层里，用户截不了图、也复制不到——**等于没有**。
- **文案**：禁止 AI 模板味（"赋能""一站式""无缝"等）；按钮用动词（"批准执行""驳回""记为决策"）。
- **队列分组与只读态**（PRD §5.1 / §8〈权限不足时列表仍可读〉）：队列页一次请求渲染两段（待裁定 / 待执行确认）+ 顶部四个计数徽标；次队列 A（`decided`）出「派发执行」按钮，次队列 B（`executing`）不出按钮只出进度文字。**不得整页 403 或空白**。
- **`status_assumed = true` 的记录**：详情页必须可见地标注「历史数据，流程状态未记录」（不能只放 Tooltip——截图、打印、键盘操作下 Tooltip 全丢），且不出任何裁决/执行按钮。
- **发起入口的可见性（PM B1 追加要求）**：问答/推荐结果处必须**同时**出现「记为决策（不执行）」与「直接执行」两个选项。后端零改动（`POST /api/decisions` 落库即 `pending`，不自动执行），但**"仅记录"如果只是接口能力、界面上没有入口，队列就永远没有数据**。这是纯前端交付项，Effort 1。
- **批量裁决**（PRD B3）：多选上限 50（超出禁用提交并提示）、批量驳回统一理由 ≥5 字。**CSV 导出降 P1，前端不渲染导出按钮。**
- **证据可读性**（PRD A2/A2-US3）：溯源页证据实体展示 `name` 而非 UUID；`evidence_episodes` 为空时必须显式标注"证据出处层不完整"，不得显示空区块（对应既有 `impact_completeness` 的同类处理）。

---

## 8. 影响面与回归风险

### 8.1 会改到的文件（精确路径）

**后端**

| 路径 | 动作 |
|---|---|
| `apps/api/odap/biz/decision/decision_record/models/enums.py` | 新建（4 枚举） |
| `apps/api/odap/biz/decision/decision_record/models/decision_record.py` | 改：删 2 枚举定义、+4 字段、`_iso_utc`、序列化 |
| `apps/api/odap/biz/decision/decision_record/models/__init__.py` | 改：再导出 |
| `apps/api/odap/biz/decision/decision_record/__init__.py` | 改：再导出 |
| `apps/api/odap/biz/decision/decision_record/interfaces/decision_query.py` | 新建（`DecisionQuery`） |
| `apps/api/odap/biz/decision/decision_record/interfaces/idecision_store.py` | 改：+4 abstractmethod（list / count / transition / append_reasoning_step） |
| `apps/api/odap/biz/decision/decision_record/interfaces/__init__.py` | 改：再导出 |
| `apps/api/odap/biz/decision/decision_record/impl/neo4j_decision_store.py` | 改：读写拆分，目标 ≤300 行 |
| `apps/api/odap/biz/decision/decision_record/impl/neo4j_decision_query.py` | 新建（Mixin：读/分页/计数/迁移/步骤追加/执行关联） |
| `apps/api/odap/biz/decision/decision_record/api/routes.py` | 改：`DecisionRecordCreate` +`entry_source`，`record_decision` 透传 |
| `apps/api/odap/biz/decision/decision_hub/__init__.py` | 已建 |
| `apps/api/odap/biz/decision/decision_hub/models/__init__.py` + `responses.py` | 已建（响应 Pydantic：`DecisionLedgerPage` / `PendingQueuePage` / `PendingDecisionItem`） |
| `apps/api/odap/biz/decision/decision_hub/models/errors.py` | 新建（仅 `StepRejectError(APIError)`，约 14 行；**不新建 handler、不改 `web/app.py`**，理由见 §3.7，`DecisionApiError` 已作废） |
| `apps/api/odap/biz/decision/decision_hub/services/state_machine.py` | 已建（`ALLOWED_TRANSITIONS` + `available_operations`） |
| `apps/api/odap/biz/decision/decision_hub/services/sla.py` | 已建（阈值读 `settings`，三档派生） |
| `apps/api/odap/biz/decision/decision_hub/services/ledger_service.py` | 已建（查询 + CAS 迁移 + 状态映射；目标 ≤300 行） |
| `apps/api/odap/biz/decision/decision_hub/api/__init__.py` + `params.py` + `routes.py` | 已建（当前 2 个只读端点；本期补到 7 个） |
| `apps/api/odap/web/router_registry.py` | 改：+`decision_hub_router`（注册在 `decision_record_router` 之后）；**−`agent_decision_router` 导入与注册（G6 下线）** |
| `apps/api/odap/infra/middleware/exception_handler.py` | **已由 team-lead 改**：`_handle_exception` 增加 `isinstance(exc, APIError)` 分支（第 8 轮）。本域不再需要任何中间件改动 |
| `apps/api/odap/biz/decision/decision_pipeline/pipeline.py` | 改：`_build_decision_record` +2 行（`entry_source` / `recommended_action`）；`_perform` 后调 `attach_action_record`；`_backfill_decision_outcome` 补 status 迁移 |
| `apps/api/odap/biz/decision/action_service/feedback_loop.py` | 改：**1 行 bug 修复**（见 8.3 缺陷 A） |
| `apps/api/odap/biz/core/agent/api/decision_routes.py` | **删除**（G6，5 端点下线） |
| `apps/api/odap/biz/core/agent/services/decision_service.py` | 改：`get_decision` / `record_step` / `create_decision` 全部要求 `workspace_id` 入参并做归属校验；删除 `list_decisions` / `get_decision_chain`（读取职责移交台账） |
| `apps/api/odap/infra/security/workspace_switch_routes.py` | 新建（P0 前置，见 B-1） |
| `apps/api/scripts/seed_decision_demo.py` | 新建（PM Q6：幂等、非生产守卫 `ODAP_ENV != production`、生成待裁定/待执行/已闭环三态样例） |

**测试**

| 路径 | 动作 |
|---|---|
| `apps/api/tests/unit/test_decision_record_isolation.py` | 改：`FakeDecisionStore` 补 4 抽象方法 + `attach_action_record`（否则 10 用例全红） |
| `apps/api/tests/unit/test_decision_hub.py` | 新建（状态机 + 映射 + 批量部分失败 + 计数） |
| `apps/api/tests/unit/test_decision_ledger_api.py` | 新建（TestClient + FakeStore 覆盖 7 个新端点，含队列双分组/四计数、`total_is_estimate`、跨库自愈重放） |
| `apps/api/tests/unit/test_decision_workspace_isolation.py` | 新建（**G6 回归**：空 workspace 上下文 + 存在跨空间数据 → 拒绝且零条数据；IDOR 按 ID 直取他空间 → 404） |
| `apps/api/tests/unit/test_decision_pipeline.py` | 可能受影响（`_build_decision_record` 新增字段）— 需实跑确认 |

**前端**

| 路径 | 动作 |
|---|---|
| `apps/web/src/modules/decision/types.ts` | 改：+`DecisionStatus` / `EntrySource` / `LedgerPage` / `PendingItem` / `BatchResolveResult`；下线 `OUTCOME_META`（设计侧） |
| `apps/web/src/modules/decision/services/decisionApi.ts` | 改：+8 封装（含 reasoning-steps 读写；**不加 blob 下载**——导出已降 P1） |
| `apps/web/src/modules/shared/services/apiError.ts` | **新建**（域无关的 `parseApiError`，三套错误形状在这里收敛成 `{code, message, details, requestId}`；**唯一允许判断 `resp.error` / `resp.detail` 的文件**） |
| `apps/web/src/modules/decision/utils/errorMessages.ts` | **新建**（`error.code → 文案`，以契约 `ErrorCodeCatalog` 为穷举源） |
| `apps/web/src/modules/decision/utils/displayStatus.ts` | **新建**（5 个纯函数、零颜色字面量；`toExecutionTier` 台账 4 档 / `toExecutionLabel` 详情 8 态，**不得合并**） |
| `apps/web/src/modules/decision/constants/decisionConfig.ts` | **新建**（`SYNC_STALE_MINUTES` 单点常量；ADR 不写这个数字） |
| `apps/web/src/modules/decision/pages/DecisionLedgerPage.tsx` | 新建 |
| `apps/web/src/modules/decision/pages/DecisionQueuePage.tsx` | 新建 |
| `apps/web/src/modules/decision/components/DecisionFilterBar.tsx` | 新建 |
| `apps/web/src/modules/decision/components/ResolveDecisionModal.tsx` | 新建（单条 + 批量共用） |
| `apps/web/src/modules/decision/components/DecisionStatusTag.tsx` | 新建（**设计侧**，单一映射点） |
| `apps/web/src/modules/decision/pages/DecisionIntelligencePage.tsx` | 改：从台账/队列点行进入，替代手输 ID；推理步骤区块；清硬编码色 |
| `apps/web/src/modules/decision/components/DecisionChainGraph.tsx` | 改：新增 `nodeColors?: Record<string,string>` prop，`useEffect` 依赖补 `nodeColors`（修「切主题不重绘」） |
| `apps/web/src/modules/agent/pages/AgentPage.tsx` | 改：决策 Tab 改读台账 `?agent_id=` + `/reasoning-steps`，**不再传 `undefined`** |
| `apps/web/src/modules/agent/services/agentApi.ts` | 改：删除 5 个 `/api/agent/decisions` 封装 |
| `apps/web/src/AppRoutes.tsx` | 改：+`/decisions/ledger`、`/decisions/queue`；`/decisions` 收口为台账 |
| `apps/api/odap/biz/platform/menu_config/seeds/seed_four_steps.py` | 改：`/decisions` 下加两个子菜单条目（否则侧边栏进不去） |

### 8.2 回归风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| `IDecisionStore` 加 4 个 abstractmethod → `FakeDecisionStore` 实例化失败，`test_decision_record_isolation.py` 10 用例全红；另有 `attach_action_record`（实现于 Mixin）在 Fake 上不存在 → hub 测试 `AttributeError` | **高** | T3 内同 PR 修 Fake：补 4 个抽象方法 + `attach_action_record`（含在验收项） |
| **删除 `agent_decision_router` 后若有未发现的调用方 → 启动 ImportError** | **高** | T7 首步全仓 `grep -rn "agent_decision_router\|agent/decisions"` 清零后再删；`test_decision_workspace_isolation.py` 断言 `/api/agent/decisions` 返回 404 |
| **错误响应形状与契约不一致（前端按契约解析得到 `undefined`）** | **高** | 三种形状并存，且**都不在服务层**：① Pydantic 字段级校验失败 → FastAPI 默认 `{"detail": [...]}`（数组），全仓无 `RequestValidationError` 处理器；② `HTTPException` → `{"detail": "<字符串>"}`；③ `APIError` 家族与任何裸 `ValueError` → **中间件**产出的 `{"error": {...}}`。规避：需要字段分流的错误走 `APIError`（§3.7），`/reasoning-steps` 的约束校验写在处理函数内，`assert_transition` 抛 `ConflictError` 而非 `ValueError`；前端读取封在 `parseApiError` 一处（§7）。**必须在 HTTP 层断言状态码 + 形状 + 读哪个键**，服务层单测全绿也发现不了 |
| `AgentPage.tsx` 改数据源后若历史决策 `agent_id` 为空 → Tab 空列表 | 中 | 台账支持 `entry_source=agent` 兜底筛选；种子脚本（PM Q6）生成带 `agent_id` 的样例 |
| `neo4j_decision_store.py` 方法与 mixin 拆分后 MRO/`self` 解析错 | 中 | 纯方法搬迁不改逻辑；拆分后逐一跑 `test_decision_record_isolation.py` |
| `created_at` 序列化格式变化（加定宽微秒）影响既有节点排序 | 中 | M1 迁移归一；`from_node_properties` 已容忍多格式 |
| 复合索引语句在旧版本 Neo4j 失败 | 中 | 沿用现有 try/except 降级 + 单属性回退 |
| `pipeline.py` 新增字段导致 `test_decision_pipeline.py` 断言失败 | 中 | 实跑；新增字段为可选，不影响既有断言 |
| **`_backfill_decision_outcome` 构造的 (status, outcome) 若与 §5.1.2 矩阵不一致 → pipeline 侧触发 409** | **中** | 逐条对齐后矩阵是合法的：`completed→(executed,success)`、`rolled_back→(failed,failure)`、`failed→(failed,failure)`、`rejected→(rejected,rejected)`、其余→`(executing,pending)`。T6 验收含"pipeline 跑一遍不出现 409" |
| **存量回填 `status_assumed` 判定依赖 `outcome_details CONTAINS 'action_status'`** | 中 | 该键只在 `_perform` 之后写入，语义可用；但 `outcome_details` 是 JSON 字符串（`decision_record.py:123`），写成属性取值会恒 null 并静默失效——迁移语句必须用 `CONTAINS`，T3 验收含"造 3 条不同形态的存量节点，回填结果与 §4.3 规则表逐行一致" |
| `available_actions` → `available_operations` 改名后若有旧前端代码读旧字段得到 `undefined` | 低 | 前端尚未实现该字段（本期新建页面），无存量调用方；契约版本号已到 1.5.0 且每版都写变更说明（1.5.0 只把 `403`/`404`/模块级 `422` 迁到信封并加 `error.code`，无删除字段） |
| **前端按旧形状读 409**（`res.reason_code` / `res.detail`）**得到 `undefined`** | **高** | 1.4.0 把 409 的读取位置从顶层搬到 `error.code` / `error.details`。缓解：① 契约与 architecture.md §7 都写明"单点封装 `parseApiError`"；② 409 分支的 T5/T9 断言直接读 `error.code`；③ 过渡期 `parseApiError` 两种形状都认，收到旧形状走降级文案不崩 |
| `append_reasoning_step` 的 CAS 回写在并发下需重试 → 极端情况 409 | 低 | 重试 1 次；仍失败返回 409 由前端重试，不静默丢步骤 |
| 新 router 与既有 `/api/decisions` 前缀共存导致路由遮蔽 | 低 | 新端点全部为多段静态路径或根路径，**不引入单段 `/{decision_id}` 路由**；新 router 注册在既有之后 |
| `menu_config` seed 改动需重建菜单 | 低 | seed 为幂等 upsert，重启触发；验收时确认侧边栏出现 |
| import-linter C1~C4 | 低 | hub 只 import `odap.biz.decision.*` 与 `odap.infra.security`，全部向下；不触碰 ontology 深层。删除 `core.agent` 路由不影响 C3（`odap.biz.core.agent` 是 source_module，只禁止它深插 ontology） |

### 8.3 调研中发现的三个既有缺陷

**缺陷 A（阻塞反馈回填链路）** — `action_service/feedback_loop.py:45`

```python
decision_id=action_record.get('agent_id'),   # ← 取错字段
```

`ActionFeedback.decision_id` 取的是 `agent_id`，导致从 action 侧收回的 feedback 永远挂错决策。应改为 `action_record.get('decision_id')`。一行修复，直接影响"反馈回填"链路正确性。**T6 内修**。

**缺陷 B（阻塞整条主线演示）** — 见 B-1（JWT `ws_id` 恒为空）。

**缺陷 C（字段形同虚设）** — `DecisionRecord.action_record_id` 全仓从未被赋值

`grep -rn "action_record_id" odap/biz/decision/` 结果显示：该字段只在 `decision_record.py` 里被**声明 / 序列化 / 反序列化**（83 / 122 / 184 行），在三处应该写入的地方全部缺失：

| 应该写入的位置 | 实际行为 |
|---|---|
| `pipeline._build_decision_record`（`pipeline.py:634-657`） | 构造 `DecisionRecord` 时不传 `action_record_id` |
| `link_triggered_action` → `create_triggered_edge`（`neo4j_decision_store.py:207-223`） | 建边 + 建影子 `:ActionRecord` 节点，**不写** `d.action_record_id` |
| `_backfill_decision_outcome`（`pipeline.py:686-687`） | 只写进嵌套的 `outcome_details.action_record_id` |

后果：图上 `action_record_id` 恒为 `null`，任何"决策→执行"关联只能靠 `TRIGGERED` 边反查，而 `TRIGGERED` 指向的影子 `:ActionRecord` 节点状态**永不刷新**（`create_triggered_edge` 只在建边那一刻 `SET a.status`；后续状态变更只写 SQLite）。这同时是 PRD "用派生状态代替新增枚举"方案不可执行的第一因（见 §4.2）。

**修法**：两处、两种写法，都不是新方法（§5.2 / §5.2.1）：

- `execute` 端点：与状态映射**同一次** `StatusOutcomePatch` 写顶层 `action_record_id` + `outcome_details`（它此刻两个都知道了）。
- pipeline `_perform`：单独调 `attach_action_record()` 只写顶层 `action_record_id`（它此刻还没有执行结果，不能碰 `status`/`outcome`）。

**T4 内实现、T6 内接线**。

---

## 9. 阻塞项与已落实裁决

### 9.1 已由架构侧定稿的裁决（无需再讨论，供测试与 PM 验收对齐）

> **跨文档引用纪律（PM 2026-10-24 定，本版已全量执行）**：PRD 的 `E*` 编号**只服务于 PRD 内部**，不作为跨文档引用键。本文引用验收项一律写「**章节 + 名称**」（如「PRD §8〈等待时长不得张冠李戴〉」）。
>
> **这不是洁癖，本轮已经付过一次代价**：我写 §6 第 21 条时把「测差异不是测有值」记成了 `E33`，而 PRD 的 `E33` 是〈状态矩阵服务端强制〉——**两者都是我要引用的东西，编号指错后两条断言看起来都还成立**，只是读者会去查错的那一条。同一份文档里我还把「驳回来源可区分」写成了 `E30`（实为 `E31`），而 `E30` 是〈历史数据容错〉。**编号漂移的可怕之处不是错，是错了还能自洽**：`E30` 与 `E31` 都在讲"字段要分清"，指错了照样读得通。
>
> 纪律：① 跨文档只写章节+名称；② **本条是本文唯一允许出现 `E*` 的地方**（举反例用），正文已清零——`grep -rn "E[0-9][0-9]"` 应**只命中本条**，命中别处即违规。

#### G6 收口三问（team-lead 提问的 a/b/c）

**a) 跨 workspace 命中返回 404 还是 403？→ 404。**

理由：`decision_id` 是可枚举的（`dec_{12hex}`，且历史 agent 链用的是裸 `uuid4`）。403 会泄露"这条决策存在、只是你没权限"，配合可枚举 ID 就形成存在性探测面；404 把"不存在"与"不属于你"合并回答，攻击者拿不到任何区分信号。裁决权限不足（能确认属于本空间但无 `decision.resolve` 权限）才返回 **403**，这是两种不同的判定：**归属**失败 → 404，**授权**失败 → 403。

**b) `workspace_id` 空值的契约？→ 422 拒绝，全链路无例外。**

决策域统一用 `get_current_workspace`（`workspace_access.py:154-173`，fail-closed，不做 `user_id` 兜底）。明确否决两种方案：
- 否决"空则不过滤"（现状 `decision_service.py:87` 的 `if workspace_id:`）——这是漏洞本体。
- 否决"空则回落固定 `"default"` 空间"——所有未声明用户共享同一空间数据，等于把租户边界换成全局空间，违反 ADR-076「非空拒绝」决议。
- 否决"前端补传 workspace"——那是把"空 = 全量"换成"伪造 = 越权"，信任模型没变，反而把 ADR-076 §7 明令禁止的做法正当化。

**c) 原 4（实为 5）个端点是保留还是废弃？→ 直接废弃并删除，无过渡期。**

迁移映射表见 §3.8。判断依据：过渡期保留必须先补隔离，而补隔离的改动量（3 端点加依赖 + service 加归属校验 + 单测）等于下线改动量；既然成本相同，就不该留一个仍需维护的后门。前端唯一调用方（`AgentPage.tsx` / `agentApi.ts`）与本次台账改造同批。

**G6 是否单独立测试用例？→ 必须。** 见 `test_decision_workspace_isolation.py`（T7/T10）：空 workspace 上下文 + 存在跨空间数据 → 拒绝且零条数据；凭 ID 直取他空间决策 → 404。这是一条能永久防回归的用例，成本极低。

#### PM 的三个待定调问题

| 问题 | 裁决 | 理由 |
|---|---|---|
| Q1 裁决留痕落点 | **独立字段 `resolution`**（结构化 dict，不是塞 `outcome_details`） | ① `outcome_details` 已被 `_backfill_decision_outcome` 覆写（`pipeline.py:686-692`），放裁决信息会被 pipeline 冲掉；② 独立字段可被台账直接投影成"裁决人/裁决时间/驳回理由"三列，不必在序列化层再挖一层；③ 导出 CSV 时取字段路径稳定，不随 `outcome_details` 的结构演进漂移 |
| Q2 等待时长口径 | **从 `created_at` 算** | 与 PM 倾向一致。取 `updated_at` 会让任何一次编辑/回填把等待时长重置为 0，队列的"最久没人管"语义直接失效 |
| Q6 演示数据 | **`apps/api/scripts/seed_decision_demo.py`**（T10） | 幂等（按固定 `decision_id` 前缀 + `MERGE`）、非生产守卫（`ODAP_ENV == "production"` 直接退出并打印原因）、生成三态样例（待裁定 3 条含 1 条超 SLA、待执行确认 2 条、已闭环 3 条含 success/failure/rejected），并建 1 条 `PRECEDENT_FOR` 边以演示先例复用 |

#### 第 6 轮新增裁决（设计侧追问 + PM 修正，均已落地）

| 事项 | 裁决 | 落实位置 |
|---|---|---|
| `entry_source` 要不要支持多选 | **单值，本期不做多选**（设计侧已按单选改回，无需返工）。不是做不到，是没有需求支撑且不封路：来源的 7 个取值里流量集中在 `manual` / `pipeline`，真实用法是"看某一条链的产物"；而 `status` / `outcome` 必须多值是因为界面存在"执行成功 + 部分成功"这类跨值域组合诉求，来源没有对应诉求。标量参数改可重复参数是向后兼容扩展，将来要加不构成返工。**纠正一处我此前写错的论证**：多选并不等价于"不传"（`manual + pipeline` 确实是一次真实收窄），旧表述会把下一个读的人带进错误推理 | §3.1 参数表 + `api-spec.yaml` |
| 推理步骤 200 条上限的 422 能否区分原因 | **带原因码**（`step_limit_reached` / `invalid_phase` / `description_too_long` / `evidence_too_many`）。"系统容量上限"与"用户输入错误"都是 422，但不能同一句文案——前者用户改什么都没用。第 8 轮起原因码位置为 `error.code`（原顶层 `reason_code` 已迁走） | §3.7 表 + `StepRejectDetail` schema |
| 残留态「状态同步中」是否要有期限 | **有，默认 10 分钟，超时降级**（PRD §8〈同步窗口必须诚实且有上限〉第 2 条）。无限期的"同步中"是用户无法证伪的状态 | §3.2 / §7 |
| SLA 三档由前端算还是服务端下发 | **服务端下发 `sla_state`**，阈值走 `settings`、客户端不可配（下方单独说明） | §3.2 / §6 第 19 条 |
| 4 个展示层文件归属 | **移交 `mvp-dev-expert-team-frontend`**，判据是 `displayStatus.ts` 零颜色字面量 | §7 |
| T11 种子口径 | **真函数、假输入**（PM 与 team-lead 方法冲突的收口方案） | §10 T11 |

**关于 `sla_state` 与 PRD §5.3「SLA 分档是展示逻辑、不下沉接口」的分歧**（设计侧第 6 轮报出，我维持原判并说明理由，供 PM 复核）：

`SLA` 分档**不是纯展示逻辑**，它同时驱动三件有数据后果的事：① `counts.sla_warning` / `counts.sla_breached` 是**全库口径**计数（若前端用当前页数据算，会出现"页内 3 条超时"而库里 40 条，用户据此判断优先级会误判）；② 默认排序 `waited_desc` 与徽标必须同源，否则"排第一的行没有红色徽标"；③ 三档阈值若落在前端，队列页与详情页会各实现一次，阈值漂移后同一个决策在两个页面上分档不同。

因此接口下发的是**判定结果**（`sla_state` 三档）而不是阈值；前端仍然拿到 `waited_minutes` 用于显示"已等待 37 小时"这类具体数字。**这不是双份实现，是分工**：服务端判定档位、前端负责文案与配色。若 PM 仍认为该下沉，需要同时给出 ①②③ 的替代方案，否则我建议按现契约执行。

#### 第 7 轮新增：错误信封与契约对齐（本版自查发现，非任何一方提出）

查证"422 能不能带 `reason_code`"时发现的连带问题——三处运行时信封与契约不一致，且**都不在服务层**，只打服务层单测全绿也发现不了：

| 事项 | 裁决 | 落实位置 |
|---|---|---|
| Pydantic 字段约束产生的 422 体形状 | 全仓无 `RequestValidationError` 处理器，字段级失败返回 `{"detail": [...]}`（数组）。**不为一个端点改全局信封**，改为把 `/reasoning-steps` 的枚举/长度校验从模型挪进处理函数，OpenAPI 里仍保留约束作为文档 | §3.7 |
| 裸 `ValueError` → 409 | 实际会被 `ExceptionHandlerMiddleware` 映射成 **400** + `{"error": {...}}`，契约里的 409 永远出不来。改为 `ConflictError`，**不允许裸 `ValueError` 逃到中间件** | §5.1 / §5.1.2 |
| `HTTPException(detail=<dict>)` 的嵌套 | FastAPI 会再包一层成 `{"detail": {...}}`，前端顶层读不到原因码。需要字段分流的错误走 `APIError` 家族，由中间件直出 `{"error": {...}}` | §3.7 |

**为什么不做成"统一全仓错误信封"**：那是一次跨域重构，回归面覆盖所有端点，而本次收益只有决策域的若干字段。**能局部解决就不要全局改**，除非局部的代价更高——这条判据在下一轮又用了一次，而且方向出乎意料。

#### 第 8 轮：`APIError` 不是死代码的替代品，是"没接线的活代码"（team-lead 实测推翻我的前提）

| 事项 | 裁决 | 落实位置 |
|---|---|---|
| 我设计 `DecisionApiError` + 专属 handler + `web/app.py` 注册 | **作废**。前提取错：`APIError` 四个子类早已存在且字段齐全，只是中间件没有 `isinstance(exc, APIError)` 分支、全仓零个 `raise` 点。team-lead 补上这一支（`exception_handler.py:46-65`）后，**新增文件数从 3 降到 1，还顺带修好了既有的"`NotFoundError(404)` 变 500"** | §3.7（含"为什么我错了"的完整复盘） |
| `DecisionInvariantError` 该不该继承 `APIError` | team-lead 要求"两者都继承"，**我做了一处有意偏离：不继承**。理由 ① `APIError` 分支打 `logger.warning`，而内部不变量被破坏必须进 `logger.error` + 堆栈，否则按 error 级别配的告警永远收不到；② `APIError` 分支在 `is_prod` 判断**之前**返回，500 的 `message` 会原样出网，把内部枚举值送到浏览器没有收益。当前实现（`status_matrix.py:27`）即此，保持不动 | §3.7 |
| 全局错误信封的字段 | `{"error": {"type", "code", "message", "request_id", "path", "details"?}}`；`code` 取 `error_code`，**仅 `APIError` 家族有值**（`ValueError` / 通用 500 / 共享依赖产出的 401/422 都没有）。前端按 `code` 判断，**不读文案** | `api-spec.yaml` 1.5.0 `ErrorEnvelope` / `ErrorInfo` / `ErrorCodeCatalog` |
| 409 的冲突信息放哪 | 放 `error.details`（`handler_name` / `current_status`），不再放顶层 `reason_code`。理由：`ConflictError.details` 是既有的承载位，中间件已实现"非空则带出" | §3.3 / `api-spec.yaml` |
| `execute` 是否写 `outcome_details.action_status`（设计侧问了两轮） | **必须写**，且与状态映射同一次 patch。不写则详情页 8 态在"刚点完"这个用户最需要的瞬间恒为空 | §3.4 / §5.3.1 第 4 条 |
| `status` 的写点有哪些（team-lead 实测：目前**一个都没有**） | **四个**：建 / 裁决 / 派发 / 回填。全部走 `StatusOutcomePatch.to_node_patch()`，**禁止任何一处散写 `SET n.status = ...`**；`IDecisionStore.update_outcome` 签名改成收整份 patch | §5.2.1 |
| `executing_since` 字段 | **删**。它不在 §4.1 锁定的 5 个字段里，而 §3.2 已决定用 `updated_at` 计时——同一事实存两处迟早不一致 | §3.4 |
| 台账列表是否出「状态同步中」（PM 否决） | **不出，只在详情页**。列表 DTO 没有"回写是否完成"的信息，唯一可用信号（`action_record_id` 非空）在每次正常执行里都成立，硬猜会让告警在正常路径上闪，把真正的异常淹掉 | §3.2 / §7 |
| AC-17：决策模块禁用 `HTTPException` | **采纳，但把范围写成可验收的**：路由体内抛出的错误一律 `APIError` 家族（`403`/`404`/模块级 `422` 全迁信封 + `error.code`）；**两处例外写进契约**——① `401` 与 JWT 缺声明 `422` 由 `infra/security/*` 共享依赖在路由体之前抛出；② 框架字段级 `422`。不写这两条例外，AC-17 就变成一条永远验不过的断言（PM 对〈同步窗口〉的同一批判） | 契约 1.5.0 `ErrorDetail` / `ValidationFailure` / `ErrorCodeCatalog`；§7 |
| 契约 schema 命名 | **`ErrorResponse` → `ErrorEnvelope`**，与 AC-17 的措辞对齐，**不留别名**（"一个语义两个名字"正是下一轮接不上的种子）。1.4.0 未流出，改名无外部影响 | 契约 1.5.0 |
| `action_status` 出现第 9 个枚举值时怎么办 | **不可判定 → 流向"不确定"，不得当终态**。理由：旧前端一定先于新前端上线，把未知中间态渲染成"已完成"会让用户以为事情结束了，而它还在跑——与「垃圾桶映射」同一个病 | §5.3.1 第 4 条 |

#### 第 9 轮：AC-17 的门禁范围比 AC-17 窄（PM 实测，本版修正）

| 事项 | 裁决 | 落实位置 |
|---|---|---|
| AC-17 覆盖几个 router 模块 | **三个**（`decision_hub` / `decision_record` / `decision_recommendation`）。前版门禁只扫 `decision_hub/`，实测另两个模块共 **14 处** `raise HTTPException` 被"绿着放过"：`decision_record` 9 处（404×3 / 链路 422×3 / 500×3）、`decision_recommendation` 5 处（404×1 / 500×4）。**判据覆盖范围比规范窄，绿是判据的属性，不是代码的属性** | §7 AC-17 段、§10 门禁、新增 **T12** |
| 14 处怎么迁 | 404→`NotFoundError`（4 处，跨空间与不存在**共用文案**不得拆开）；模块级 422→**新增 `UnprocessableError`**（3 处）；500→**去掉 `try/except` 让异常逃到中间件**（7 处）。共 **+0.7 人日** | §10「T12 口径」 |
| 为什么 422 不能换 `ValidationError` | 它是 **400**（`exception_handler.py:168-177` 写死）。机械替换会让 3 处 422 静默变 400——类名、字段名、日志全"看着对"，只断言"抛了 APIError"的测试会全绿 | §10 坑 1 |
| 为什么 500 不是"换一个类" | `HTTPException(500, detail=f"…{e}")` **绕过中间件的生产脱敏**，把 `str(e)` 直接发给浏览器。换成 `APIError(f"…{e}")` 会原样保留泄漏；正确做法是删掉这层包装 | §10 坑 2 / T12 验收 |
| `error.details` 的"没有详情"怎么写 | **收紧为"键不存在或非空对象"，不接受 `null` 也不接受 `{}`**（PM 提出）。理由：同一语义两种写法，断言必然裂开——`details is not None` 会把 `{}` 判成"有详情"。实现本来就只在这两种形态：`APIError.__init__` 的 `details or {}` + 中间件的 `if exc.details:` | 契约 1.6.0 `ErrorInfo.details` |
| `error.code` 的大小写 | **全部统一 `lower_snake_case`**（2 个大写的改成小写，其余 11 个本来如此），并**禁止前端做任何大小写归一化**（设计侧提出）。归一化的危害：能"抹平"当下，但后端哪天统一风格时它不会报错、只会静默错位——键和值都归一化过，看起来永远匹配得上 | 契约 1.7.0；§7 |
| `parseApiError` 要不要返回 `status` | **要**（设计侧指出）。AC-17 例外一让 `401` 没有 `code`，而 401 与 403 的动作相反：401 **跳登录页**、403 就地提示不跳转。只按 `code` 判，401 会落进通用提示——用户只是登录过期，看到的却是"操作失败"，且不会自动去登录 | §7 |
| 404 文案能不能写"不存在" | **不能**，也不得回显 `decision_id`。契约里 `not_found` 是"不存在**或跨空间**（不区分、不泄漏存在性）"，写"决策不存在"在跨空间时是一句假话，还会引导用户反复输入同一个 ID 去试 | §7 缺码分档表 |
| 422 的 `details.field` 指向 | 判据统一为"**用户能不能通过改这个字段跨过限制**"：`batch_empty` / `batch_size_invalid` → `decision_ids`；`reason_required` → `reason`；`evidence_too_many` → `evidence`；只有 `step_limit_reached` 是 `field=null` | 契约 1.7.0 `ErrorCodeCatalog` |
| "期望 0 命中"的检查 | **每一条都必须配一条"必须命中"的正向对照**（PM 提出）。空结果有两种解释——规范被满足了，或检查根本没匹配上，**二者在输出上不可区分** | §10 门禁 |
| 「新增」与「修改」的边界 | `UnprocessableError` 是**加在 `infra` 里的新子类**（零调用点、零既有行为变化），与"改 `infra/security/*` 四个共用函数"性质不同。**不能因为都在 `infra` 就一概拒绝——那会把一条正确的边界用成教条** | §10 坑 1 尾段 |

#### team-lead 的裁决已落实位置

| 裁决 | 落实位置 |
|---|---|
| A4 数据源统一本期做，与 G6 同一交付物 | T7（§10）；§8.2 已标注"不可拆分" |
| 裁决动作仅 3 个，不预留第 4 个 | §3.3 请求体只有 `action` + `reason`；`resolution` 只有 `{action, actor_type, by, at, reason}`；**已从契约中物理删除 `selected_option` / `expected_outcome`** |
| 隔离缺陷写入 Checklist | §6 第 13-16 条 |
| **B-1 批准**（T1，0.5 人日）+ 契约四要求 | §B-1 方案 B 已补全：切换前校验成员资格（非 admin 不得切到非成员空间）、重签 access+refresh、每次切换写审计、失败返回 403 且不泄露空间是否存在。T1 验收项已按此四条重写 |
| **B-2 批准新增 `status` 6 态，Plan B 否决** + 要求给存量回填规则 | §4.3 **存量回填规则表**（5 行）+ 二次运行 0 行的证明；`status_assumed` 字段作为"无法判定"的显式落点 |
| **B-3 确认收窄**（A2 复用 `/chain`、B1 靠 `POST /api/decisions`、B4 靠 `precedent_decision_ids`） | §3.9 / §3.10 / §7「发起入口的可见性」。新端点口径见 §0（5 + 2） |
| **修正 1：跨空间一律 404，仅本空间无权限才 403** | §6 第 17 条逐端点复核；§3.2-§3.7 错误码行无一反过来 |
| **修正 2：演示数据纳入交付（T11）** | §10 T11：`scripts/seed_decision_demo.py`，幂等、`ODAP_ENV=production` 硬拒绝、写入独立 demo workspace、≥5 条待裁定 + 若干已执行/已驳回 |
| **execute 必须允许从 `decided` 发起** | §3.4 + §5.1：`decided → executing` 合法，`pending → executing` 非法返回 409 |
| **execute 幂等：不创建第二条 ActionRecord，返回 `idempotent_replay: true`** | §3.4 两步 CAS 方案 |
| **execute 并发保护（二选一，需给理由）** | §3.4：选 **CAS 当锁**，不引分布式锁——`WHERE status IN $expected` 本身就是互斥点，加锁只增加失效面 |
| **执行失败必须回写 `status=failed` + `outcome=failure`** | §3.4；`attach_action_record` 与状态回写放 `finally` |
| **`status` × `outcome` 合法组合矩阵 + 校验落点** | §5.1.2：7 合法 / 23 非法；校验放**服务层写入侧**（不是 `model_validator`，理由已写）；读取侧只告警 |
| **advisory 1 批准**（同 PR 修 FakeDecisionStore） | T3 验收项，约 45 行 |
| **advisory 2 批准**（修 `feedback_loop.py:45` + 用 `attach_action_record()` 补写） | T6（缺陷 A）/ T4（缺陷 C） |
| **advisory 3 批准**（拆 `neo4j_decision_query.py` Mixin） | §5.6，目标 288 / 276 行 |
| **advisory 4 记债不扩范围**（`action_records` 无 workspace_id 列） | §13 第 1 条技术债 |
| **advisory 5 延后**（全文索引 P1），但 keyset 切换阈值必须写进 spec | §5.4 已含阈值（>50,000 条 或 p95 > 300ms）；§13 第 2 条 |

#### 设计侧最小接口面的采纳情况（含逐行读契约后的 7 条 P0）

| 设计要求 | 采纳 | 说明 / 落点 |
|---|---|---|
| `total_is_estimate` | 采纳 | §3.1，恒返回；`count_decisions(probe=5000)` 实现 |
| `has_more` | 采纳 | §3.1，估算态以"是否取满 `page_size`"判定 |
| `counts{overdue, stale, awaiting, confirming}` | 采纳并改名 | 落在 `counts{to_resolve, to_execute, sla_warning, sla_breached}`（与 PRD 文案"待裁定/待执行确认/等待较久/已超时"对齐） |
| 队列按 `bucket` 分两次请求 | **不采纳** | 改为一次返回两组 + 四计数（`items[i].group` + `counts`），省一次往返；`group` 参数仍可用于收窄 |
| 409 返回处理人姓名 | 采纳 | §3.3：409 响应体 `handler_name` 取 `resolution.by`（无则 `null`） |
| 批量 `failed:[{id, reason_code}]` | 采纳 | §3.5，`reason_code ∈ {not_found, conflict, permission}` |
| `referenced_precedent_ids[]` | **不采纳为裁决参数** | 先例留痕已由 `POST /api/decisions` 的 `precedent_decision_ids` 在建决策时完成（自动建 `PRECEDENT_FOR` 边）；裁决阶段再传会引入"裁决时改因果图"的隐式副作用，且与"3 个动作"裁定冲突 |
| `(workspace_id, created_at)` / `(workspace_id, agent_id)` 索引 | 采纳 | §4.4 两个独立复合索引 |
| `reasoning-steps` 读端点 | 采纳 | §3.7；写入端点也在（缺它则 agent 端点下线后无替代） |
| **A-1** `/pending` 的 summary 与 `group` 定义自相矛盾 | **采纳，已改** | §3.2 / api-spec：改为"待办域过滤（pending+decided+executing）+ group 二分"，`counts` 与 `group` 同源派生 |
| **A-2** `outcome` 需多选 | **采纳，已改** | §3.1 / api-spec：改 `array + explode`。`display_status` 前端友好参数列为 P1（团队已裁定用 `outcome` 数组，不在本期新增第二套语义） |
| **A-3** SLA 需三档 | **采纳，已改** | `sla_state: ok\|warning\|breached` + `waited_minutes`；阈值 24h/72h 走服务端配置，**不做入参** |
| **A-4** 置信度区间筛选 | **采纳，按 team-lead 口径** | `min_confidence` / `max_confidence`（0~1 闭区间，`min>max` → 422）。未采用 `confidence_band`——三档前端 Segmented 可直接映射成 min/max 两个值，不必在后端多一套枚举 |
| **A-5** `evidence_incomplete` 筛选 | **降级 P1**（team-lead 裁定） | 需要先定义"不完整"口径（0 条？少于 N 条？），口径未定就上会反复返工。写入 §13 Out-of-Scope |
| **A-6** `agent_id` 缺失 | **采纳，已补** | 台账查询参数 + 响应字段（`DecisionRecord.agent_id` 已存在） |
| **A-7** 三个只读端点是否行为不变 | **确认不变** | §3.10，`/chain`、`/impact`、`/similar` 不改造不迁移；`evidence_entities[].name` 稳定返回。推理路径区块**不用删** |
| **G** `sort` 缺 `evidence_count` | **本期不做**（team-lead 降 P1） | 实现需要派生属性 + M3 回填，性价比不足以留在本期。前端**不渲染该排序项**，不放假控件 |
| **H** `q` 搜不搜 `reasoning` | **删掉 `reasoning`**（按 PRD） | §3.1。PRD §4.2 明确"不搜推理全文"，契约服从 PRD；顺带避免大字段全扫 |
| **I** `total` 估算标记 + 深翻页 | **采纳** | `total_is_estimate` 恒返回；`page` 上限 100，超出 422 |
| **J** `/pending` 排序缺项 | **部分采纳** | 增 `confidence_asc`；`evidence_count_asc` 随 G 一起降 P1 |
| **K** `execute` / `retry` 在队列里不可达 | **澄清 + 采纳改名** | `available_operations` 是"该记录当前可做的动作"，由同一派生函数在队列与详情页共用：`decided→[execute]`（队列可点）、`failed→[retry]`（`failed` 不入队列，只在详情页出现）。契约里已写明 `available_operations` 与 `RecommendedAction` 是两个概念 |
| **C-1** `status` 与 `outcome` 双真相源 | **采纳诉求，落在写路径收敛** | 不采用"读时派生"（派生不可实现，见 §4.2）；采用**同一条 Cypher 语句同时写 `status` 与 `outcome`**——`transition_status` 的 `SET n += $patch` 是单节点原子操作，不存在两者分开写的中间态。另加 §5.1.2 合法组合矩阵 + 写侧断言，把"漂移"变成"写不进去" |
| **C-2** 移除 `selected_option` | **采纳，已删** | api-spec 的 `Resolution` 与 `ResolveDecisionRequest` 均已删除该字段。理由与 team-lead 一致：能力存在而决策不做是最坏组合，前端一定会把它做成下拉框 |
| **C-3** `expected_outcome` 语义未定义 | **删除** | 同上，一并从两个 schema 移除。若 P1 要做"预期 vs 实际"偏差，需先设计 `deviation` 的呈现方式再引入 |
| **C-4** `available_actions` 与 `RecommendedAction` 撞名 | **采纳改名** | 改为 `available_operations`（用户可做的动作）vs `RecommendedAction`（要执行的命令对象） |
| **D-1** `to_execute` 渲染禁用态 | **采纳你的方案** | §7：整组不渲染按钮，改出状态说明文字。"对谁都不存在"与"你没权限"必须不同表现 |
| **D-2** 部分成功不能只靠 `status` | **采纳** | §7 + api-spec：映射函数签名锁定 `toDisplayLabel(status, outcome)`，`DecisionStatus.description` 已加注 |

---

### B-1 【P0】JWT `ws_id` 恒为空，现有 7 个决策端点在生产登录流下全部 422

**证据链**：

1. `infra/security/auth_routes.py:74` → `auth_service.login(request.username, request.password, ip_address)`，**未传 `workspace_id`**。
2. `auth_service.py:247-250` → `issue_access_token(..., workspace_id=workspace_id)`，此处 `workspace_id=""`。
3. `jwt_service.py:56` → payload `"ws_id": ""`。
4. `workspace_access.py:167-172` → `get_current_workspace` 取 `user.get("workspace_id") or user.get("ws_id") or ""`，为空 → **抛 422**。
5. `decision_record/api/routes.py` 的 5 个端点（`/chain`、`/similar`、`/impact`、`/outcome` + 本次全部新端点）依赖该函数。
6. 前端 `decisionApi.ts` 明确"workspace_id 由后端从 JWT 声明解析，前端无需也不应透传"→ 无任何补偿路径。
7. `LoginRequest`（`auth_models.py:55-57`）只有 `username` / `password`，登录时无法注入空间。
8. 仓库无任何 `switch-workspace` / `X-Workspace-ID` 机制（`web/router_registry.py` 与 `workspace/api/routes.py` 均无）。

**结论**：`/decisions` 页面在真实登录下必然 422。既有单测没暴露，因为 `test_decision_record_isolation.py` 直接构造带 `ws_id` 的 payload 调 `get_current_workspace`，绕过了登录签发环节。

**方案对比**

| 方案 | 做法 | 代价 | 评价 |
|---|---|---|---|
| A. 登录带 workspace | `LoginRequest` +`workspace_id`，前端登录框选空间 | 0.5 人日 | 登录前无法列空间（`/api/workspaces` 要 token），体验差 |
| B. `POST /api/auth/switch-workspace`（**推荐**） | 登录后调一次，校验成员资格 → 重签 access+refresh，`ws_id` 更新；每次切换留审计 | 0.5 人日 | 标准做法，隔离不打折，且顺带补齐 ADR-076 §7 里"`X-Workspace-ID` 覆盖记为可选增强"的缺口（用显式接口替代隐式头，更可审计） |
| C. `get_current_workspace` 回落到固定 `"default"` | 缺声明即用 default | 0.1 人日 | **否决**：所有未声明用户共享 default 空间数据，直接违反 ADR-076「非空拒绝」决议与 ADR-023 隔离架构 |

**裁定结果：方案 B 已批准，立为 T1（0.5 人日）。** team-lead 独立复验了本链路（`auth_routes.py:74` 传 3 参、`auth_service.py:231-232` 默认 `workspace_id=""`、全仓 `X-Workspace` 解析 0 处、`switch_workspace` 0 处、`get_current_workspace` 6 个使用点），并明确**拒绝方案 C**（回落 default 违反 ADR-076 §7 非空拒绝）。

T1 的四条契约要求（team-lead 追加，缺一条不算完成）：

1. **切换前校验成员资格**：非 admin 不得切到非成员空间（`workspace_members` 表查成员关系，不用"能否看到空间名"当判据）
2. **重签 access + refresh**：不只改 access token，refresh 也必须同步——否则 15 分钟后静默回到空 `ws_id`，现场演示正好卡在那儿
3. **每次切换写审计**：`action=workspace_switch`，`details={from_ws, to_ws}`（写审计失败不阻断切换，但必须落 warning 日志）
4. **失败返回 403 且不泄露空间是否存在**：非成员空间与不存在的空间返回同一响应体，否则用这个端点就能枚举全平台 workspace_id

### B-2 【已裁定：批准新增 `status`】PRD「不新增决策状态枚举值」在当前代码上不可执行

| # | 冲突点 | PRD 原主张 | 本 Spec 主张 | 裁定 |
|---|---|---|---|---|
| B-2 | 状态枚举 | 第 16 行："不新增决策状态枚举值"，队列分组由 `outcome` 五态 + 动作状态派生（G3） | 新增 `status` 字段（6 态）。派生方案在当前代码上不可实现，证据见 §4.2 / 缺陷 C | **采纳 `status`，Plan B 否决。** team-lead 依据：`action_record_id=` 全仓仅 `decision_record.py:184` 一处且是反序列化**读**，从无写入，派生前置条件确实不可求值。PM 已撤回派生规则并写入 PRD「PM 认错记录」 |

**PM 撤回派生规则后提的三条约束，已全部落进本 Spec（缺一条 PRD 那条就是空文）**：

| PM 约束 | 落点 |
|---|---|
| ① 界面只出 5 类标签，`status` 6 态不得直接暴露 | §7「结果标签收敛为 4 色系、界面只出 5 类标签」+ `toDisplayLabel(status, outcome)` 签名锁定；映射只在 `DecisionStatusTag` 一处 |
| ② `status` × `outcome` 合法组合矩阵，禁止矛盾态 | §5.1.2：6×5=30 组合，7 合法 / 23 非法，落成 `LEGAL_OUTCOMES` 常量并被写侧断言；§6 第 20 条为验收项 |
| ③ 历史数据不得默认灌进待裁定队列 | §4.3 规则表最后一行 + `status_assumed` 字段 + §5.5 队列 Cypher 恒带 `coalesce(n.status_assumed,false)=false` + §6 第 18 条反例断言（造 5 条历史数据，队列 `total` 必须仍为 0） |

三条里第 ③ 条最容易做漏：它不是展示层过滤，而是**数据层不满足条件**。若靠前端过滤，导出、计数、批量裁决三处都会漏，且 `counts.to_resolve` 会把历史数据算进去。

### B-3 【已确认收窄】PRD 9 条 P0 里的三条不需要新端点

| # | 冲突点 | PRD 主张 | 本 Spec 主张 | 裁定 |
|---|---|---|---|---|
| B-3 | 范围 | 9 条 P0：A1–A4（台账/详情/来源/数据源统一）+ B1–B5（发起待决策/队列/批量/先例/导出） | 全部覆盖，但 A2 详情页复用既有 `/chain` + 渲染实体 `name`；B1 用「`POST /api/decisions` 不自动执行」天然满足；B4 用既有 `precedent_decision_ids` 天然满足 | **口径确认**，PM 按此更新 PRD。新端点口径见 §0（能力 5 + 路径 7） |

**B1 的半条不能全收，PM 的反驳成立**：我原主张"B1 靠 `POST /api/decisions` 天然满足"，这是接口能力口径；但验收标准必须落在用户能碰到的地方——问答/推荐结果处要同时有「记为决策（不执行）」与「直接执行」两个选项，否则用户根本不知道有这个入口，队列就永远没有数据。已改为**纯前端入口，后端零改动**（§7「发起入口的可见性」）。PM 据此把 B1 的 RICE Effort 从 2 降到 1，总分 18→24。

**A4 的 Effort 回执（PM 问询）**：A4 从"只统一读路径"变成"数据源统一 + G6 收口 + 推理步骤迁移"，真实工作量 **1.5 人日**（T7），按 RICE 的 1-5 相对值应记 **4**，不是 2。请据此调整 A4 的分批或维持其在批次 A（我建议维持——它是安全项，不应挪到批次 B）。

---

## 10. 实施任务拆分（12 个，含依赖顺序）

| # | 任务 | 改哪些文件 | 验收方式 | 人日 | 依赖 |
|---|---|---|---|---|---|
| **T1** | **P0 前置：workspace 切换**（已批准） | `infra/security/workspace_switch_routes.py`（新）、`router_registry.py`、`web/src/modules/shared/stores/authStore.ts` | ① 登录 → 调 switch → `/api/auth/me` 返回非空 `ws_id` → `GET /api/decisions` 返 200（不再是 422）；② **成员资格**：非 admin 切到非成员空间 → 403；③ **access 与 refresh 同时重签**（改 `access_token` 15 分钟后不得退回空 `ws_id`）；④ 每次切换写 `action=workspace_switch` 审计；⑤ 不存在的空间与非成员空间返回**同一响应体**（不可枚举） | 0.5 | — |
| **T2** | 数据模型 + 枚举拆分 | `models/enums.py`（新）、`decision_record.py`、`models/__init__.py`、包根 `__init__.py` | `from odap.biz.decision.decision_record import DecisionStatus, DecisionEntrySource, DecisionOutcome` 通过；`wc -l decision_record.py` ≤ 265；5 新字段 round-trip（`to_node_properties` → `from_node_properties`）单测；缺失字段读取回落默认值不抛错 | 0.5 | — |
| **T3** | 存储层：契约 + 读写拆分 + 分页 + 迁移 | `interfaces/decision_query.py`（新）、`idecision_store.py`（+4 抽象方法、**`update_outcome` 改收整份 `StatusOutcomePatch`**）、`impl/neo4j_decision_query.py`（新）、`impl/neo4j_decision_store.py`、`tests/unit/test_decision_record_isolation.py` | 两文件均 ≤300 行；`test_decision_record_isolation.py` 10/10 绿；Fake 版 list/count/transition/append_step/attach 单测绿；**迁移幂等：跑两次，第二次 `RETURN count(n)` = 0**；**造 5 类不同形态存量节点，回填结果与 §4.3 规则表逐行一致**（含 `status_assumed` 判定、`CONTAINS 'action_status'` 生效）；CAS 并发（同一条两次 approve）只有一次成功；`count_decisions(probe=5000)` 超限返回 `(5000, True)`；**`update_outcome` 走 `to_node_patch()` 后 `status` 真的被写入**（反例断言：改签名但 Cypher 仍只写 `outcome` 时必须有测试红）；**M3（`evidence_count` 回填）不在本期** | 2.1 | T2 |
| **T4** | 状态机 + SLA + Hub 编排 | `decision_hub/services/state_machine.py`、`services/sla.py`、`services/ledger_service.py`、`services/hub.py`、`models/responses.py`、`__init__.py`（均新建或补齐） | 非法迁移抛 `ConflictError` 映射 409 单测（含 `pending→executing`）；ActionRecord→DecisionStatus 映射 5 条全覆盖；**§5.1.2 矩阵：7 合法全过、23 非法全拒（含 `failed+partial_success` 必须被拒），写侧断言生效**；**`group` 与 `counts` 同源派生**（造数据使 to_execute=3，断言分组条数与计数一致）；批量部分失败逐条归因（`not_found`/`conflict`/`permission`）；`services/*` 均 ≤300 行、**函数源码跨度 ≤40 行**（ast 量 `end_lineno-lineno`，含注释与空行，不是逻辑复杂度） | 1.5 | T3 |
| **T5** | 7 个新端点 + 注册 | `decision_hub/api/routes.py`（新）、`decision_hub/api/__init__.py`、`decision_hub/models/errors.py`（新，约 14 行 `StepRejectError`）、`router_registry.py` | `TestClient` 覆盖：台账分页/多选 `status`+`outcome`/`agent_id`/置信度区间（`min>max`→422）/`sort=confidence`/`page>100`→422 + `total_is_estimate`；队列双分组 + 四计数 + `sla_state` 三档（请求带 `sla_minutes` 不改变结果）；resolve 200/409（**断言 `resp.json()["error"]["code"] == "illegal_transition"` 且 `error.details.handler_name` 有值，状态码是 409 而不是 400**——服务层若抛裸 `ValueError`，会被全局中间件映射成 400 并换一套信封，而"抛了 ValueError"的单测照样全绿）/404/403；execute 从 `decided` 成功、从 `pending` 409、二次调用 `idempotent_replay=true` 且 ActionRecord 只有一条、并发两请求只一个成功；**execute 成功后 `outcome_details.action_status` 非空**（§3.4）；**跨库残留态自愈：停在 executing 而 ActionRecord 已终结时，重放 execute 自愈到终态且 ActionRecord 仍为 1 条**；batch 逐条结果含部分失败；reasoning-steps 读写 + 200 条上限 422（**断言 `error.code=step_limit_reached`、`error.details.field` 为 `null`、`step_count=200`、`limit=200`**——若实现把 `maxLength`/`maxItems`/`Literal` 留在 Pydantic 模型上，此处会返回 FastAPI 默认的 `{"detail": [ ... ]}` 数组，前端按 `error` 读会得到 `undefined`；所以本端点的约束校验必须写在处理函数里）；`/openapi.json` 恰含 7 个新路径且**不含 `/export.csv`** | 1.7 | T4 |
| **T6** | Funnel 收口 + 缺陷 A/C 接线 | `pipeline.py`（+`entry_source`/`recommended_action`；`_perform` 后调 `attach_action_record`；`_backfill_decision_outcome` 同步 status）、`feedback_loop.py:45`（1 行）、`decision_record/api/routes.py`（+`entry_source`） | pipeline 跑一次后台账出现 `entry_source=pipeline`、`recommended_action` 非空、`action_record_id` 非空；`test_decision_pipeline.py` 绿；`POST /api/decisions` 不传 `entry_source` 时落库为 `manual`；**`rolled_back` 走显式分支落 `failed`+`failure` 且 `outcome_details` 含 `achieved_items`/`rolled_back_items`（不再掉进 else 被写成 `pending`）**，该分支有单测 | 0.7 | T2, T4 |
| **T7** | **G6 收口：agent 链下线 + 步骤迁移 + Agent Tab 改数据源** | 删 `core/agent/api/decision_routes.py`；改 `core/agent/services/decision_service.py`（方法加 `workspace_id` + 归属校验，删 list/chain）；改 `router_registry.py`（−`agent_decision_router`）；改 `web/.../agent/pages/AgentPage.tsx`、`services/agentApi.ts`；新建 `tests/unit/test_decision_workspace_isolation.py` | 全仓 `grep -rn "agent_decision_router\|api/agent/decisions"` 命中 0；`/api/agent/decisions` 任意方法返回 404；**空 workspace 上下文 + 存在跨空间数据 → 拒绝且零条**；凭 ID 直取他空间决策 → 404；Agent Tab 数据来自台账 `?agent_id=`，切换空间后列表随之变化 | 1.5 | T5 |
| **T8** | 前端台账页（**CSV 导出降 P1，不在本期**） | `DecisionLedgerPage.tsx`、`DecisionFilterBar.tsx`、`types.ts`、`decisionApi.ts` | 首屏 20 条 + 总数（`total_is_estimate=true` 时显示"约 N 条"且禁用跳末页）；状态/结果/来源/时间范围/关键词筛选生效；分页与排序生效（`created_at`/`updated_at`/`confidence`）；**不渲染导出按钮、不渲染"证据数"排序项**（不放假控件）；零硬编码色（`grep -E "#[0-9a-fA-F]{6}"` 无命中）；零 emoji | 0.7 | T5 |
| **T9** | 前端待决策队列 + 裁决/执行/批量 | `DecisionQueuePage.tsx`、`ResolveDecisionModal.tsx`、`types.ts`、`decisionApi.ts` | 两段分组 + 四计数正确；超 SLA / 等待较久高亮；批准→`decided`、驳回→`rejected`（理由 ≥5 字）；执行→`executing` 并跳转溯源；多选 ≤50、批量结果逐条展示、部分失败不回滚；409 显示"已被 X 处理"；无权限时按钮禁用且列表可读（不整页 403） | 1.5 | T5 |
| **T10** | 溯源页/路由菜单/颜色治理 + 种子 + 测试与端到端 | `DecisionIntelligencePage.tsx`（含推理步骤区块 + **详情页执行记录实时读取**）、`DecisionChainGraph.tsx`（`nodeColors` prop）、`AppRoutes.tsx`、`menu_config/seeds/seed_four_steps.py`、`scripts/seed_decision_demo.py`（新）、`tests/unit/test_decision_hub.py`、`tests/unit/test_decision_ledger_api.py`、前端 vitest | `/decisions` 进台账，点行进入溯源（不再手输 ID）；证据实体显示 `name`，出处层缺失显式标注；`nodeColors` 由 `useToken()` 传入且 `useEffect` 依赖补 `nodeColors`（切主题重绘）；侧边栏出现台账/队列；**详情页三级判定三支各有断言：① 关系库动作已终结 + 阈值内 → 「状态同步中」；② 关系库动作进行中 → 「执行中」；③ 只有节点侧 `action_status`、无关系库记录 → 不得出现「状态同步中」（§5.3.1 第 2 条的反例）**；种子脚本可重复执行且 `ODAP_ENV=production` 时拒跑；`lint-imports` = `Contracts: 4 kept, 0 broken`；`ruff` 通过；`pytest -k decision` 全绿；端到端 8 步（种子→台账可见→问答记为决策→队列待裁定→驳回→再记一条→批准→执行→反馈回填+溯源+先例；**导出不在本期**） | 2.5 | T6, T7, T8, T9 |
| **T11** | **演示数据（team-lead 新增，独立交付）** | `apps/api/scripts/seed_decision_demo.py`（新） | 幂等（固定 `decision_id` 前缀 + `MERGE`，连跑两次节点数不变）；`ODAP_ENV=production` 时**硬拒绝**并打印原因（退出码非 0）；写入**独立 demo workspace**（不污染真实空间）；产出 ≥5 条待裁定（含 1 条 `sla_state=breached`、1 条 `warning`）+ ≥2 条已执行 + ≥1 条已驳回 + 1 条 `PRECEDENT_FOR` 边（演示先例复用）；其中 1 条带 `status_assumed=true` 用于验证"不进队列"；**样本必须由生产代码路径产生**（口径见本节末「T11 种子口径细则」：真函数、假输入）；含 1 条 `rolled_back` 与 1 条 `completed`，并断言 `rolled_back` 那条 `outcome != pending`（PRD §8〈"已回滚"不得记成"待定"〉） | 0.5 | T5, T6 |
| **T12** | **AC-17 收口：既有两模块错误信封迁移**（PM 第 9 轮实测：14 处违规被旧门禁放过） | `decision_record/api/routes.py`（9 处）、`decision_recommendation/api/routes.py`（5 处）、`infra/middleware/exception_handler.py`（+`UnprocessableError`，约 8 行纯新增） | 门禁 `grep -rn "raise HTTPException" odap/biz/decision/` 命中 **0**；三模块的 404 / 模块级 422 / 500 各有一条**HTTP 层断言**（断言 `{"error": ...}` 与 `error.code`，不是只断言状态码）；**`decision_record` 的 3 处 422 迁移后状态码仍必须是 422**（若误用 `ValidationError` 会变成 400，见下方「T12 口径」）；`POST /api/decisions` 落库失败时响应体**不得**含 `str(e)` | 0.7 | T2 |

**T12 口径：14 处怎么迁（两处不能照搬，照搬会静默改变行为）**

实测分布（`decision_record` 9 / `decision_recommendation` 5）：

| 处数 | 现状 | 迁成 | 注意 |
|---|---|---|---|
| 4 | `HTTPException(404, "决策不存在或不属于当前工作空间")` | `NotFoundError(...)` → `code=not_found` | 跨空间与不存在**共用同一句文案**，迁移时不得顺手拆开（不泄漏存在性） |
| 3 | `except ValueError as e: raise HTTPException(422, str(e))` | `UnprocessableError(str(e))` → 422 + `code=unprocessable` | **不能换 `ValidationError`**，见坑 1 |
| 7 | `except Exception as e: raise HTTPException(500, f"…{e}")` | **去掉包装，让异常逃到中间件** | 见坑 2，这不是"迁成另一个类"，是"不要接住" |

> **坑 1：`ValidationError` 是 400，不是 422。** `infra/middleware/exception_handler.py:168-177` 把 `status_code=400` 写死了。按"422 就换 ValidationError"机械替换，会让**3 处 422 静默变成 400**——状态码变了，但字段名、类名、日志全都"看起来对"，测试若只断言"抛了 APIError"会全绿。因此新增 `UnprocessableError(APIError)`（`status_code=422`、`error_code="unprocessable"`，约 8 行）。
> **这是"给既有模块加一个子类"，与"改 `infra/security/*` 的四个函数"性质不同**：前者零调用点、零既有行为变化；后者是全仓共用入口。**"新增"和"修改"不能因为都在 `infra` 就一概拒绝**——那会把一条正确的边界用成教条。

> **坑 2：`HTTPException(500, detail=f"…{e}")` 泄漏内部异常文本。** 它绕过中间件的 `is_prod` 脱敏（那层只保护"未捕获异常"），把 `str(e)`（可能含 Cypher 片段、连接串、路径）直接发给浏览器。**迁移的正确做法不是把它换成 `APIError(f"…{e}")`——那会原样保留泄漏**，而是删掉这层 `try/except`，让异常正常逃到中间件：生产环境返回脱敏的 `InternalServerError`，同时进 `logger.error` + traceback（比 `f"决策落库失败: {e}"` 更好排查）。
> **这一条顺带修掉一个既有缺陷**：迁移前，`POST /api/decisions` 落库失败会把内部异常文本交给前端；迁移后不会。T12 的验收里有专项断言。

**合计 ≈ 14.4 人日**（逐行取任务表的人日列相加：0.5 + 0.5 + 2.1 + 1.5 + 1.7 + 0.7 + 1.5 + 0.7 + 1.5 + 2.5 + 0.5 + 0.7 = 14.4）

**T11 种子口径细则：真函数、假输入**

PM（"至少 1 条必须由流水线真实跑出来"）与 team-lead（"不得真跑完整 pipeline，别把演示可靠性绑到 LLM 上"）在方法上冲突，收口方案是**真函数、假输入**——把"流水线"拆成"推理段"和"产物构造段"，只跳过前者：

| 环节 | 真实代码还是 fixture | 理由 |
|---|---|---|
| `AnalysisInput` / `AnalysisResult` / `DecisionResult` 三个入参对象 | **fixture**（pydantic 直接构造，零网络） | 它们只是推理结果的数据容器，构造不需要模型 |
| `_analyze` / `_decide` 两段（LLM 推理） | **跳过** | 唯一依赖网络的环节，跳过不影响产物结构 |
| `_build_decision_record` | **必须真调** | `entry_source` / `recommended_action` / 决策正文由它产出 |
| `attach_action_record` | **必须真调** | `action_record_id`（可执行载荷的句柄）由它写入，手写等于伪造句柄 |
| `_backfill_decision_outcome` | **必须真调** | `outcome` 映射（含 `rolled_back → failure`）正是本期要验的映射本身 |
| `MERGE` | **仅作幂等键**（按固定 `decision_id`），禁止用它手写业务字段 | 手写字段会让演示数据与真实数据口径分叉，演示通过 ≠ 功能通过 |

这样 PM 的顾虑（"流水线产物天然携带可执行载荷，是唯一能演示到『点发起执行』的数据来源"）被满足：载荷由真实函数产出，脚本不会卡在执行那一步；team-lead 的顾虑（LLM 不可用则演示挂）也被排除：只跳过推理段，不跳过产物构造段。

**加减明细（team-lead 要求"把加减都写出来"，否则下一个人看到数字会以为是笔误）**

| 项 | 变化 | 累计 |
|---|---|---|
| 初版 10 任务（含 T7 的 G6 收口 1.5） | — | 12.5 |
| T11 演示数据（独立交付） | +0.5 | 13.0 |
| T5 契约扩展（`outcome` 多选 / `sla_state` 三档 / 置信度区间 / `page` 上限 / 队列两档排序） | +0.5 | 13.5 |
| T6 `rolled_back` 显式分支 + 明细 + 单测 | +0.2 | 13.7 |
| CSV 导出降 P1（T8 从 1.0 降到 0.7，导出约占 0.3） | −0.3 | 13.4 |
| `evidence_count` 排序与 M3 回填降 P1（T3 2.0→1.9、T5 2.0→1.8） | −0.3 | 13.1 |
| 第 8 轮：`update_outcome` 改收整份 `StatusOutcomePatch`（T3 1.9→2.1，含 Fake 同步） | +0.2 | 13.3 |
| 第 8 轮：错误处理从"新造类 + handler + 注册 3 处"缩到"1 个 `StepRejectError`"（T5 1.8→1.7） | −0.1 | 13.2 |
| 第 8 轮补：详情页 ① 支的"第二信号"必须来自关系库 → 多一次按 `action_record_id` 的执行记录读取（T10 2.0→2.5，PM 记账口径：记在详情页侧，不记在通用封装） | +0.5 | 13.7 |
| 第 9 轮：AC-17 范围按文字扩到三个 router 模块，14 处 `HTTPException` 迁移（新 T12） | +0.7 | **14.4** |

**为什么不是 team-lead 给的 12.4 —— 需要一处澄清**

顶部写的 −1.0 记在"T8 CSV 导出"上，但 **T8 是一个整体 1.0 的任务，包含「台账列表页」+「CSV 导出」两半，导出本身只占约 0.3**。按 −1.0 记账，等于把**台账列表页也一并降成 P1**，而那是 PM 的 **A1（P0）**，也是端到端演示的主界面。

所以：

- 若只砍导出（本 Spec 目前的记账）→ **14.4**
- 若砍掉整个 T8（含台账列表页）→ 12.4，但 T10 的第 1 步"台账可见"要改写，且 PM 的 A1 降级需要 PM 本人同意
- 若既保留台账页又要压到 12.4 → 还需再砍 0.7，最接近的组合是「T9 批量裁决 0.5 + T10 前端 vitest 0.2」，但那会削掉 PRD B3 的"一次处理多条"演示价值

本 Spec 按**保留台账列表页**记账（14.4），因为这属于"没有它演示就没有主界面"的一级交付物。若 team-lead 确认要 A1 降 P1，我把 T8 归零、总额改 12.4，并在 T10 的验收里把台账环节替换为队列环节。

**跨库不一致窗口（team-lead 要求写进 §10）**：`Decision.status` 与 `ActionRecord.status` 允许的最长不一致窗口 = **一次回写往返**（`submit_action` 返回后立即回写）。**超出该窗口仍不一致即视为缺陷**，不属于"正常的最终一致"，按 bug 排查。窗口内**详情页**显示「状态同步中」，不显示「执行中」（台账列表不出这一档，理由见 §3.2 PM 否决）。自愈路径见 §6 第 22 条。

**T1 是否必须在 T2 之前串行？** 不必。T1 只改 `infra/security` 与前端 `authStore`，与 T2/T3/T4 的数据模型、存储层零文件重叠，**可与 T2 并行**。但 T1 必须在**端到端验收（T10）之前**完成——否则 `/api/decisions` 在真实登录下全 422，T10 的 8 步演示一步都跑不通。真正的硬串行只有一条：T10 依赖 T1。

**为什么 T11 不能并到 T10**：现状系统不会自然沉淀待裁定数据（门禁通过即执行、不通过即 `rejected`），队列默认是空的。"端到端可演示"这条验收在没有种子数据时**无法验收**，而种子脚本的失败模式（幂等性、生产守卫）与页面组装完全不同，混在 T10 里会让 2.0 人日的任务变成一个 2.5 人日的黑盒。

**一个必须注意的落地顺序（否则会误伤既有链路）**

写侧矩阵断言（T4）与 pipeline 映射修复（T6）之间有一个**时间窗陷阱**：

```
T4 上线断言  →  但 pipeline 仍把 rolled_back 写成 outcome=pending
              →  台账出现 (status=failed, outcome=pending)
              →  被断言拦成 409  →  pipeline 整条链路失败
```

现有 `_backfill_decision_outcome`（`pipeline.py:659-694`）是 `outcome` 的**唯一回填出口**，只在 `decision_hub` 的映射函数里兜是兜不住的。所以：

- **推荐顺序**：T2 → T3 → T4（断言就位）→ **T6 紧随其后**（pipeline 映射同步，含 `rolled_back` 显式分支）→ T5 → 其余
- **次选**：T4 的写侧断言先只对新端点（resolve / execute / 批量）生效，T6 完成后再打开 pipeline 路径的校验

不要按 "T4 → T7 → T8 → T9 → T6" 排——那段时间里任何一次 pipeline 实跑都会 409，而 pipeline 是演示链路的入口。

**`rolled_back` 的明细从哪来**：ActionRecord 没有 `achieved_items` 字段，**不要为此改 SQLite 表结构**（触发迁移）。从 `ActionRecord.parameters` 里提取子项清单；单目标动作则给 `achieved_items: []` + `rolled_back_items: [target_object_id]`。这两个字段的定位是"给出可用信息"，不是"完备审计"——完备审计在 Graphiti Episode 里（`save_audit_episode` 已记录）。为了填它去反查 execution 明细会把 0.2 人日变成 1 人日。

### 门禁命令（每个任务交付前必跑）

```bash
cd apps/api && ../../.venv/Scripts/lint-imports.exe --config pyproject.toml   # 期望 Contracts: 4 kept, 0 broken
cd apps/api && ../../.venv/Scripts/python.exe -m pytest tests/unit -k "decision or action" -q
# 单文件 ≤300 行自检
cd apps/api && find odap/biz/decision odap/biz/core/agent odap/web -name '*.py' | xargs wc -l | sort -rn | awk '$1>300 && $2!="total"'

# --- 函数源码跨度 ≤40 行（ast，零依赖；注意量的是**源码跨度**，含注释与空行，不是逻辑复杂度）---
# 新代码（decision_hub/）必须 0；存量按基线，**只许减不许增**
cd apps/api && python -c "
import ast, glob, io, sys
def spans(path):
    t = ast.parse(io.open(path, encoding='utf-8').read())
    for n in ast.walk(t):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield n.name, n.lineno, (n.end_lineno or n.lineno) - n.lineno + 1
new = [(p, *f) for p in glob.glob('odap/biz/decision/decision_hub/**/*.py', recursive=True) for f in spans(p) if f[2] > 40]
old = [(p, *f) for p in glob.glob('odap/biz/decision/**/*.py', recursive=True) for f in spans(p) if f[2] > 40]
print('新代码超限:', len(new), new[:5])
print('存量超限总数（基线 20，只许减）:', len(old))
sys.exit(1 if new or len(old) > 20 else 0)
"

# --- AC-17：决策模块路由体内禁止 HTTPException（期望命中 0）---
# 范围 = AC-17 的文字范围（odap/biz/decision/ 下全部 api/routes.py，三个模块），
# 不是"这次改了哪个目录"——前版只扫 decision_hub/ 放过了 14 处。
cd apps/api && grep -rn "raise HTTPException" odap/biz/decision/ && echo "违反 AC-17" && exit 1 || echo "AC-17 OK"

# --- 「能力存在 ≠ 能力在用」：隔离依赖必须被真实引用（期望每个 router 模块 ≥1）---
cd apps/api && for f in $(grep -rl "APIRouter" odap/biz/decision/decision_hub/); do
  n=$(grep -c "get_current_workspace" "$f"); echo "$f: $n"; [ "$n" -ge 1 ] || echo "  该 router 未挂隔离依赖"
done

# --- ErrorCodeCatalog 双向一致：契约里的码集合 == 代码里真实抛出的码集合 ---
# 单向会漏两类：catalog 有但没人抛（假规格）、抛了但 catalog 没有（前端按未知处理 → 体验降级）
cd apps/api && grep -rhoE '(error_code|code)="[A-Za-z_]+"' odap/biz/decision/ \
  | sed -E 's/.*"([A-Za-z_]+)"/\1/' | sort -u > /tmp/codes_code.txt
grep -oE '^ +\| `[A-Za-z_]+` \| [0-9]{3} \|' ../../docs/superpowers/specs/2026-10-24-decision-mainline/api-spec.yaml \
  | sed -E 's/.*`([A-Za-z_]+)`.*/\1/' | sort -u > /tmp/codes_spec.txt
echo "catalog 有、代码没有（假规格）:"; comm -23 /tmp/codes_spec.txt /tmp/codes_code.txt
echo "代码有、catalog 没有（前端会按未知处理）:"; comm -13 /tmp/codes_spec.txt /tmp/codes_code.txt

# --- 文档结构（两份核对器，基准都是表头/规范源，不是行间互比）---
python scripts/check_markdown_tables.py docs/superpowers/specs/2026-10-24-decision-mainline/
python docs/superpowers/specs/2026-10-24-decision-mainline/check_doc.py --all
```

> **每条"期望 0 命中"的检查都必须配一条"必须命中"的正向对照**（PM 提出，采纳）：空结果有两种解释——规范被满足了，或者检查根本没匹配上，**而这二者在输出上不可区分**。所以下面每条 grep 类门禁都要能被一个已知违规样例打红一次，否则它的"绿"不构成证据。我这条 catalog 检查的第一版就栽在这里：正则漏了两个大写的码（当时叫 `NOT_FOUND` / `FORBIDDEN`，1.7.0 起已统一为小写），13 个只数出 11 个，而"漏 2 个"与"通过"都是空 diff。

> **写这条命令时踩到的坑，记一笔**：第一版正则用了 `[a-z_]+`，于是当时那两个大写的码被静默漏掉，13 个只剩 11 个——**而"漏掉 2 个"和"通过"在输出上长得一模一样（都是空 diff）**。两个码与其余 11 个风格不一致是历史原因（`APIError` 的默认 `error_code` 是大写——1.7.0 已统一），但这恰好说明**穷举表的一致性检查必须是真的跑过一遍**，而不是写出来就算。

**为什么后三条要进本次门禁**：它们各自对应本轮一次真实事故——AC-17 那类是"契约写了、代码没跟"（§6 第 24 条只能靠 HTTP 层断言抓）；`get_current_workspace` 引用计数是 G6 那次"依赖齐全、路由没挂、把接线当成造轮子讨论了一轮"的机械版检查；两份核对器是"行间互比在整表一致地错时永远通过"的产物。**能机械检查的判据不要留在人眼里**——第 4 条尤其：`引用计数 0` 一次 grep 就能测出来，而人眼要看三个文件才能发现。

存量超限文件（本次**不得**再加长，且 T3 修复其中 1 个）：`decision_pipeline/pipeline.py` 715、`decision_recommendation/engine.py` 873、`action_service/executor.py` 651、`decision_record/impl/neo4j_decision_store.py` 408（T3 拆分至 ≤300）。

---

## 11. ADR 草稿

> 建议编号 **ADR-091**（当前最大 ADR-090）。文件名：`docs/07-adr/ADR-0XX_决策主线贯通_决策台账与待决策队列.md`

```markdown
# ADR-0XX: 决策主线贯通 —— 决策台账与待决策队列

## Status
Proposed (2026-10-24)

## Context

ADR-076 已把决策确立为一等公民对象并落地 7 个端点（record / chain / similar /
impact / causal-links / check-rules / outcome），但四条决策相关链路并存且语义重叠：

- `core/agent`（`/api/agent/decisions`）：进程内 dict 记录 ReAct 步骤过程，重启即失，
  无 workspace 校验，不写图。
- `decision_pipeline`（`/api/decision-pipeline`）：5 段流水线，已写 DecisionRecord、
  已穿透 decision_id 到 ActionRecord、已回填 outcome。
- `decision_recommendation`（`/api/decision`）：LLM 推荐，进程内 history，不写图。
- `decision_record`（`/api/decisions`）：决策对象权威存储，7 端点。

实测结果是：**写入口其实已经收敛**（pipeline 与 record 都落在
`DecisionService.record_decision()`），真正缺失的是**读入口**——没有任何列表/台账
端点，前端只能手输 `dec_xxxxxxxxxxxx` 才看得到一条决策；也**没有待决策队列**，
决策产出后"谁来裁决、裁了没、执行到哪一步"无从查询。

同时 `DecisionRecord` 丢失了可执行载荷（`_build_decision_record` 只保留
`option.name`，`action_type_id / target_object_id / parameters` 全丢），
即使补上台账与队列，"批准 → 执行"也无可提交参数。

更严重的是 `core/agent` 这条链的隔离缺陷，四跳可独立复现：
`AgentPage.tsx:47` 恒传 `undefined` → `agentApi.ts:80-88` falsy 即不写查询串 →
`decision_routes.py:39-51` 既无 `get_current_workspace` 也无非空拒绝 →
`decision_service.py:87` `if workspace_id:` falsy 即跳过过滤，**返回全工作空间数据**。
更进一层，`GET /{decision_id}` 与 `/{decision_id}/chain` 连 workspace 参数都没有，
凭可枚举的 ID 即可越权读取任意空间的决策详情与推理步骤（IDOR）；
`_decisions` 又是进程级单例、不按 workspace 分区，不同用户的决策共处一个字典。
因此"统一决策数据源"不能只是前端改造题，它是隔离缺陷题。

## Decision

1. **确定唯一写入口**：所有决策对象写入必须经
   `DecisionService.record_decision()`；不新增第二条写入路径。
2. **明确对象边界**：`agent` 链记录的是 ReAct 步骤（过程），
   `recommendation` 链产出的是推荐（建议），两者**都不是决策对象**，
   不落入 `:Decision` 节点。它们通过调用方显式调用唯一写入口
   （携带 `entry_source`）进入主线。
3. **新增 `decision_hub` 包**作为读侧与编排门面：台账查询、待决策队列、
   裁决状态机、执行触发。它复用 `DecisionService.store`（既有公开属性），
   **不改** 259 行的 `decision_service.py`。
4. **`DecisionRecord` 新增 5 字段**：`status`（6 态流程状态）、
   `entry_source`（7 值入口来源）、`recommended_action`（可执行载荷）、
   `resolution`（裁决留痕 `{action, actor_type, by, at, reason}`）、
   `status_assumed`（存量推定标记）。`DecisionOutcome` 值域**零变更**。
   注意 `status` 是对同期 PRD「不新增决策状态枚举值」约束的**有意偏离**，
   理由见 Considered Options 3。
5. **`status` 与 `outcome` 同语句写入**：`transition_status` 的 `SET n += $patch`
   是单节点原子操作，两者永不分两次写；并以 `LEGAL_OUTCOMES` 矩阵
   （6×5 中 7 合法 / 23 非法）在写侧断言，使"状态漂移"从"事后对账"
   变成"写不进去"。
6. **状态迁移用 CAS**：`WHERE uuid AND group_id AND status IN expected`，
   0 行命中即返回 False，路由映射 409，防止双审批并发双写执行；
   批量裁决逐条独立 CAS，不做整体事务回滚。
   `execute` 的并发保护同样用 CAS 当锁，不引入分布式锁。
7. **分页用 skip/limit + 独立 COUNT**，切换 keyset 的阈值为
   单 workspace > 50,000 条或 p95 > 300ms。
8. **不重写既有链路**：pipeline 仅 +2 行字段映射；recommendation 零代码改动；
   **agent 链 5 个端点整体下线**（跨空间列表泄露 + 单条读取 IDOR），
   列表粒度并入台账 `?agent_id=`，推理步骤粒度迁 `…/reasoning-steps`
   并落到决策对象上，不再留在进程内存。
9. **新增 7 个端点 + 删除 5 个端点**：台账列表、待决策队列、单条裁决、
   执行触发、批量裁决（≤50 条），以及推理步骤读 / 写（后两者是
   agent 端点下线后的等价承接，能力口径记 5、路径口径记 7）。
   跨空间命中一律 **404**，仅"本空间内无操作权限"才 403。
   CSV 导出降 P1（列序与 BOM 方案已验证并留档）。

## Consequences

### 正面
- 决策主线可在 UI 上闭环：问答/场景 → 决策记录 → 待决策队列 → 裁决 → 执行 →
  反馈回填 → 先例复用 → 台账复盘/导出，全部有端点与页面承载，可端到端演示。
- 台账成为唯一读入口，`agent` / `recommendation` 的内存列表不再是"影子真相"。
- `status` 与 `outcome` 职责分离后，"系统拒绝"与"人工否决"可区分，
  队列语义不再被 pipeline 的 `outcome=pending` 污染。
- `recommended_action` 补齐后，决策从"只能看"变为"可直接执行"。
- **跨空间读取的入口从 5 个降为 0 个**：删掉 agent 链后，全仓不存在
  "无 workspace 参数"的决策读写路径，隔离不再依赖调用方自觉。

### 负面
- 存量 `:Decision` 节点需一次幂等迁移（`status` / `entry_source` /
  `status_assumed` / 时态类型归一）。
  未迁移时仍可读（`from_node_properties` 有默认值），但按 `status` 过滤会漏节点，
  因此迁移挂在 `ensure_indices()` 与 `list_decisions` 双入口做自愈。
- 无法判定流程状态的存量数据只能标 `status_assumed=true` 并排除在队列外。
  这些记录在详情页显示"待定"，既不能裁决也不能执行——**这是有意的**：
  宁可让人去核，也不让历史脏数据冒充待办，把队列第一屏变成假待办墙。
- `IDecisionStore` 新增 4 个抽象方法，会让未实现它们的测试替身失效
  （本次同步修 `FakeDecisionStore`，约 45 行）。
- skip/limit 深翻页为 O(skip)，大数据量下需换 keyset（已定阈值）。
- `status` 与 `outcome` 两个状态字段并存，存在长期被误用（改错字段）的风险；
  缓解手段：`outcome` 只允许经 `update_outcome` 写、`status` 只允许经
  `transition_status` 写，两个方法各自单测覆盖，代码评审按此规则检查。
- 批量裁决不做回滚，部分失败会让调用方看到"部分成功"的中间态；
  这是 PRD 的明确要求（不覆盖他人结果），不是遗漏。
- **删除 agent 端点是对外契约的破坏性变更**。当前唯一调用方
  （`AgentPage.tsx` / `agentApi.ts`）与台账改造同批上线，无外部调用方，
  因此不设兼容窗口。

### 已知边界（非缺陷，将来排查前先读这一节）

**本设计不保证 `Decision.status` 与 `ActionRecord.status` 任何时刻严格一致。**

原因是它们不在同一个存储：`Decision` 在 Neo4j，`ActionRecord` 在 SQLite。
跨库同事务需要分布式事务机制（两阶段提交 / outbox + 补偿任务），其工作量级与
本次"打通主线"的目标不匹配。这是一次**有意的取舍**，不是遗漏。

具体的边界承诺：

| 项 | 承诺 |
|---|---|
| `status` 与 `outcome` 之间 | **严格一致**。同一 `SET n += $patch` 语句写，单节点原子；另有合法组合矩阵在写侧断言，矛盾态写不进去 |
| `Decision.status` 与 `ActionRecord.status` 之间 | **最终一致**，允许的不一致窗口 = **一次回写往返**（调用 `submit_action` 返回后立即回写） |
| 超出该窗口仍不一致 | **视为缺陷**，不是"正常的最终一致"。此时按缺陷排查，不要用本节当挡箭牌 |
| 不一致窗口内的呈现 | **详情页**显示「状态同步中」，**不得显示「执行中」**。把不确定伪装成确定，比显示不确定更坏。**台账列表不出这一档**——列表 DTO 里没有"回写是否完成"的信息，唯一可用信号在每次正常执行里都成立，硬猜会让告警在正常路径上闪，把真正的异常淹掉（PM 否决，§3.2） |
| 呈现的期限 | 该文案**必须自带期限**：超过可配阈值降级为「状态可能未同步，请检查执行记录」并给执行记录入口。**默认值定义在前端常量 `SYNC_STALE_MINUTES`，ADR 不写具体数字**——一个数出现在两处，第一个被记住的就是那个数，后面写多少句"不要当挡箭牌"都拦不住。**无限期的"同步中"是用户无法证伪的状态，等于替系统永久兜住一次失败** |
| 两个尺度的区别 | 上面两行说的**不是同一个时间尺度**：判"这是不是 bug"用工程口径（一次回写往返，该窗口内不一致属正常）；判"用户该看到什么"用文案口径（可配阈值，超时降级）。**后者不是前者的容忍期**——文案兜底不能拿来给数据不一致免责 |
| 窗口内的自愈 | 崩溃残留的 `executing` 由 `execute` 幂等重放自愈：读回 ActionRecord 当前状态补写，且不产生第二条 ActionRecord。**该路径有测试覆盖** |

**判据（"阈值该放哪边"一刀切，供后来人不必重推）**：**阈值是否必须服务端权威，取决于它是否改变"返回哪一批数据"。** SLA 阈值决定分组、计数与排序 → 必须后端；同步窗口阈值只决定"说哪句话"，不改变任何数据集合 → 前端单点常量足够。**两个阈值刻意不一致，禁止为了"统一配置机制"合并**——那是个看起来永远正确的重构，做下去就把 SLA 的防线拆了。

**错误信封的边界（第 8 轮补）**：本域有**三种**错误体并存——`{"error": {...}}`（`APIError` 家族与任何逃到中间件的异常）、`{"detail": "<字符串>"}`（`HTTPException`）、`{"detail": [...]}`（FastAPI 字段级 422）。**不是缺陷，是本期的分批结果**：只把"前端需要按字段分流"的错误迁到信封，其余保持原形状，避免跨域重构的回归面。代价是前端必须**单点封装**读取（§7）。`error.code` **只在 `APIError` 家族里有值**，500 与 `HTTPException` 都没有——所以"读不到 `code`"只表示"这个分支没有机器可读原因"，**不得**据此判断成功或跳过提示。

**`updated_at` 能当计时起点的前提（写死在别人看得到的地方）**：它只影响一句文案，**不参与计数、不参与排序、不参与 SLA**。字段表锁 5 个是对的，锁住的代价就是这个前提；**一旦有人拿这个时长做统计口径，前提即破，必须改回真字段**。

**一条通用的判据（第 8 轮踩坑后新增，不止适用于错误处理）**：**"这个类/字段/端点存在"与"它被接上了"是两件事。** 我在 §5 写 `DecisionApiError(APIError)` 时只读到 `APIError` 的类定义，就当成"可用的基础设施"，没查谁 `raise` 它、中间件认不认它——结论是它从没被消费，我的设计会拿到 500，而测试会因为"没人真的发请求"全绿。**凡是引用既有能力，必须同时找到它的消费点**（`grep` 到至少一个真实调用 / 一个 `isinstance` 分支 / 一个路由注册），找不到就按"不存在"处理。这条判据在本次已连中三次：`APIError`（有类无消费）、`execute` 的 `action_status`（有键无写入）、`status` 的写点（有字段无赋值）。

看到"执行中"和"已完成"不一致时，先查这里，再查代码。若已超出窗口，那是 bug。

## Considered Options

1. **重写 pipeline 为 hub 内部实现** — 否决：把 demo 押在 715 行已验证代码的重构上，
   风险与收益不对称。
2. **让 agent / recommendation 也写 `:Decision`** — 否决：过程记录与推荐会污染台账
   语义；且 agent 链缺失 workspace 解析，接线即引入跨租户风险。
3. **用 `outcome` 兼作队列筛选（PRD 原方案，不新增枚举）** — 否决。
   PRD 的派生规则是「`outcome=pending` 且未关联执行动作 = 待裁定」，
   但前置条件不可求值：`DecisionRecord.action_record_id` 全仓从未被赋值
   （`_build_decision_record` 不传、`create_triggered_edge` 不写），
   派生条件恒真，结果是每条流水线跑完未执行的决策都涌进主队列。
   若改走 `TRIGGERED` 边派生，影子 `:ActionRecord` 节点的 `status` 只在建边时
   写一次、永不刷新（真实状态在 SQLite），列表查询会退化为跨库 N+1。
   且 `outcome` 无 CAS 能力，无法满足 PRD B3「冲突条目不覆盖他人结果」。
4. **保留 agent 端点并加 `Deprecation` 响应头** — 否决：保留即"决策的第二个入口"，
   与数据源统一的目标直接冲突；且补隔离的改动量（3 端点加依赖 + service 加归属
   校验 + 单测）等于下线改动量，成本相同就该删掉，而不是留一个仍需维护的后门。
5. **cursor 分页** — 否决：拿不到 total、需 `(created_at, uuid)` 复合游标，
   在 10k 量级收益为零。
6. **引入 `transitions` / `python-statemachine`** — 否决：零新增依赖约束；
   6 态 7 边的迁移表手写 dict 即可。
7. **在 `DecisionRecord` 上加 `model_validator` 校验状态矩阵** — 否决：
   该模型是从图节点反序列化的，硬校验会让任何一条历史脏数据在**读取**时抛异常，
   列表页直接 500。校验放服务层写入侧，读取侧只告警不抛错。

## Reversibility

可逆，代价低：
- 7 个新端点独立前缀路径与独立 router，删除只需回滚 `router_registry.py` 一行。
- 新增字段全部有默认值，回滚模型不影响既有节点读取（多余属性被
  `from_node_properties` 忽略）。
- 迁移脚本幂等且不删除任何数据，回滚无需反向迁移。
- `AGENT` / `RECOMMENDATION` 两个 `entry_source` 值若后续废止，
  只需从枚举移除对应分支，历史数据保留为只读标签。
- **唯一不易回滚的是 agent 端点删除**：回滚需恢复 router、恢复 3 处 workspace
  校验、并回滚前端。若评审认为风险过高，替代路径是"先补齐隔离上过渡期、
  下个迭代再删"——但那必须给 5 行迁移映射挂一个 `Sunset` 日期，
  否则"过渡期"会变成永久，这正是本 ADR 选择直接删除的原因。
```

---

## 12. 自检（对照生成式代码失效模式）

| 失效模式 | 本 Spec 的防线 |
|---|---|
| Happy-path 偏差 | 7 个端点的错误码逐条列出（401/403/404/409/422），无一条只写成功分支；状态机 7 条合法边 + 全部非法组合映射 409；批量裁决三种失败码逐条定义；`execute` 的幂等重放与"派发中"两条非 happy 路径都有明确响应 |
| 沉默逻辑错误 | 状态机、ActionRecord→DecisionStatus 映射、`status×outcome` 矩阵（7 合法/23 非法）三者均列成表并要求单测覆盖（T4 验收项）；CAS 用 `WHERE status IN expected` 而非裸 SET；`group` 与 `counts` 强制同源派生，并设"造 to_execute=3 断言两者一致"的用例 |
| **文档内部不自相矛盾** | 本版两处已修：`/pending` 的 summary 原写"固定 status=pending"却与 `group.to_execute` 定义冲突（会导致次队列恒空）；`outcome` 单值参数无法表达"成功+部分成功"多选。两处都是**看字面实现就出错**的类型，故在 §3.2 顶部留了修正说明，防止后续按旧版回退 |
| **表格/结构自渲染失败** | 本次实际踩过一次：把细则子表嵌进任务表的 T11 单元格，导致整行脱离表格。已改为把细则移出表格（§10「T11 种子口径细则」），并建议把结构自检固化为 `scripts/check_docs.py`（§13 第 12 条）——这类问题**只有渲染后才看得见**，靠人眼复查不可靠。**本轮又踩了同类的第二种**：6 行表格的单元格里含未转义 `\|`（`decided\|failed`、`grep -rn "a\|b"`），整行被切成多余单元格——空行检查抓不到，必须加"列数一致"检查（§13 第 12 条已从七项扩到八项） |
| 幻觉依赖/接口 | 全部方法签名对照源码核实：`get_current_workspace`（`workspace_access.py:154`）、`assert_workspace_access`、`save_audit_episode`、`submit_action`、`link_triggered_action`、`FeedbackLoop.close_loop`、`ActionRequestStatus` 8 值、`EntityNode.save` 均在本仓已验证存在；`outcome_details` 是 JSON **字符串**（`decision_record.py:123`）也已核实，迁移语句据此改用 `CONTAINS`；零新增第三方依赖 |
| 缺失系统上下文 | §6 隔离 Checklist **24 条**（含裁决权限「看 ≠ 判」、批量跨空间、404 优先于 403、历史推定不入队、SLA 阈值不可客户端改写、状态矩阵写侧双向断言、分组计数同源且计时基准分档、推理步骤上限与输入错误可区分）；认证/隔离/错误码逐端点标注；`page ≤ 100`、`page_size ≤ 100`、批量 ≤ 50、导出 ≤ 5000、`q ≤ 100`、推理步骤 ≤ 200 |
| 性能盲区 | 明确 skip/limit 的 O(skip) 与切换阈值；复合索引 4 条 + 降级链；无 N+1（台账单查询 + 单 COUNT；队列四计数一次聚合）；`CONTAINS` 全扫风险标注（>1 万条时转全文索引，见 §13）；**PM 已主动把列表执行状态从 8 态降为 4 档**，跨库 N+1 从产品侧消除 |
| 静默缺失 import | T10 门禁含 `lint-imports` + `ruff` + `pytest`，三者必过；删除 `agent_decision_router` 前先 `grep` 清零（§8.2 高风险行） |
| **契约与运行时信封不一致** | 第 7 轮识别、第 8 轮定案：运行时有**三套形状**并存——① `{"error": {...}}`（`APIError` 家族 + 任何逃到中间件的异常）；② `{"detail": "<字符串>"}`（`HTTPException`）；③ `{"detail": [...]}`（FastAPI 字段级 422，全仓无 `RequestValidationError` 处理器）。契约从**只承诺一种**改为**显式声明三套**，并要求前端单点封装读取（§7）。T5 的断言全部打 HTTP 层，且**同时断言状态码、形状、读哪个键**——只打服务层单测发现不了，因为服务层每一步的行为都是正确的 |
| **引用了一个未被消费的类**（本轮新增，最该记住的一条） | §3.7 前版把 `DecisionApiError(APIError)` 当成"复用既有基础设施"，但 `APIError` 全仓零个 `raise` 点、中间件也没有 `isinstance` 分支——**它从没被接上**。若按此交付，裁决的 409 永远不会出现在客户端，而测试全绿（因为没人真的发请求，既有单测只断言了对象属性）。这是"幻觉依赖"的变体：**类是真的，用它这件事是假的**。防线已写进 §11 已知边界：引用既有能力必须同时指出它的消费点 |
| **修一次缺陷，制造五个**（本轮新增，最笨的一条） | 收到 918/919 的竖线报告后，我写了个「把单元格里所有竖线转义成『反斜杠+竖线』」的脚本，**没先判断哪些已经转义过**——于是 4 行原本正确的位置多出一个反斜杠（更坏），加上我自己在 §12 新增的一行里写了 2 个裸竖线，一次性把 2 个缺陷扩成 5 个。**根因与两个核对器的分歧是同一个：把输入当成「已知状态」。**核对器不能拿行与行互比（整表一致地错时永远通过）；修复脚本也不能无条件转义（已经对的地方会被改坏）。**修复前必须先枚举当前状态，而不是假设状态。** 另一条：我用来复核的正则把两字符的转义序列整段删掉再数，于是三字符的错误形态也被当成「已转义」而静默通过——**检查器把自己要检查的东西归一化掉了，是这一整类事故的共同形状** |
| **"我测的那部分" ≠ "判据声明的范围"**（本轮第三次，最贵的教训） | 一天之内同一个坑踩三次：① 表格核对器拿行与行互比（基准错）；② AC-17 门禁只扫 `decision_hub/`（范围错，放过 14 处）；③ 我按 PM 的 `ast` 方案验"现状是否达标"，只跑了两个 `routes.py` 就说"是 0"，跑全模块是 **20 个**。三次的共同形状：**把"我验过的那部分"当成"判据覆盖的那部分"。** 所以门禁写完后要问一句——**这条判据的规范源在哪儿，扫描范围是从规范源抄的，还是从我这次改动的目录抄的**。前者叫判据，后者叫自证 |
| **同一个错误的两个方向**（PM 补的镜像，本轮新增） | 上面两条其实是同一件事：**把输入当成已知状态**。修复脚本假设"现在的写法都是错的"→ 改坏对的；检查器把要查的东西归一化成"可接受"→ 永远通过。PM 今天犯的是镜像：判据写成「格数 > 表头 = 必报／< 表头 = 空列可接受」，于是**整表一致少一列时永远通过**。所以真正的判据不是"有没有报"，而是"**报与不报都必须能被一个反例推翻**"——给不出反例的检查，等于没有检查。**PM 补的三条补丁（采纳，缺一条它就会退化成一句漂亮话）**：① 反例必须在**门禁里每次执行**，写在文档里不跑等于没有；② 反例必须**成对**——一个必红、一个必绿，**只有红样例时，"报了"不等于"报对了"**（会把误报当检出）；③ **给不出反例不是缺陷，冒充有防线才是**（这条是本轮把"函数源码跨度"从假防线转成真防线的直接理由） |
| **注释/文档与代码分叉** | 本轮实测到第三例：`status_matrix.py:58` 的 docstring 写着"路由映射 409"，而 code 与 Spec 都已定为 **500**；此前两例是 `SYNC_STALE_MINUTES` 的注释与「22 个非法」（实为 23）。三次都不是逻辑错，是**照注释实现就会错**。已列为 §13 待办：改常量/枚举时同一提交内改注释 |

---

## 13. 遗留与建议（非本次范围）

1. **【技术债，team-lead 记为 advisory 4】`action_records` 表无 `workspace_id` 列**：`sqlite_action_storage.py` 只有 `decision_id` 索引。理论上持有 `action_record_id` 的跨空间用户可经 `GET /api/actions/records/{id}` 读到他人执行记录。本次不扩范围（新端点只读自己刚创建的记录，且入口先过决策归属校验），但应**单独立项**。
2. **【P1，team-lead 裁定延后】台账 `q` 用 `CONTAINS` 全扫**：`> 10,000` 条时应转 Neo4j 全文索引（`CREATE FULLTEXT INDEX decision_ft`），与 §5.4 的 keyset 切换同批处理。**keyset 切换阈值已写进 §5.4 与代码注释**（单 workspace > 50,000 条 或 p95 > 300ms），不会因为延后而丢失触发条件。
3. **【P1，team-lead 降级】`evidence_incomplete` / `has_no_evidence` 筛选**：需先定义"证据不完整"的口径——是 0 条实体？出处 0 条但实体 > 0？还是少于 N 条？口径未定就上会反复返工。前端本期不渲染该控件（渲染一个点了没反应的筛选器比不渲染更伤信任）。
4. **【P1】「改选备选」与 `selected_option`**：PRD §7 第 8 条明确排除。契约里已把 `selected_option` 物理删除，**不保留带开关的扩展字段**——能力存在而决策不做是最坏组合，前端一定会把它做成下拉框。启用前须先修订 PRD §7，并回答"改选后置信度是否重算、原证据链是否失效"。
5. **【P1】`failed → rejected`（放弃失败决策）与 `decided → rejected`（撤回采纳）未开放**：前者是"重试多次后认输"的收尾动作，后者是"手滑批准后的补偿"。两者都超出本期"3 个裁决动作 + 执行"的裁定范围，故状态机不开放、契约里不留空壳按钮。若 P1 需要，必须先定义"撤回后原执行动作如何处理"。
6. **【P1，team-lead 减项】CSV 导出（PRD B5）**：列序、UTF-8 BOM、`resolution` 展开三列、5000 行上限、`actor_type` 区分门禁与人工——全部方案已验证并留档在 §3.6，P1 捡起来可直接照做。**本期前端不渲染导出按钮**。
7. **【P1，team-lead 减项】台账 `sort=evidence_count` 与队列 `sort_by=evidence_count_asc`**：实现需要写时派生属性 + M3 回填（`evidence_entity_ids` 在图上存 JSON 字符串，`size()` 无效），单独立项更划算。**本期前端不渲染该排序项**。
8. **【P1】`display_status` 便捷筛选参数**：设计侧建议直接收界面 6 个筛选项、由后端映射。本期团队裁定用 `outcome` 多值数组（等价能力，语义不重复），故不新增第二套筛选语义。
9. **既有超限文件**：`pipeline.py` 715 / `engine.py` 873 / `executor.py` 651 均超 300 行硬上限，本次禁止再加长并通过 `attach_action_record` 调用点最小化接触，建议单独排期拆分。
10. **API 版本前缀**：全仓路由无 `/api/v1` 前缀（与团队规范不一致）。改动会影响全部前端调用，属独立技术债。
11. **前端存量缺陷（设计侧清单，非后端范围）**：`DecisionTimeline.tsx:25-30` 把 `act`（执行）阶段用 error 红，语义误导，应为 primary；`DecisionChainGraph.tsx` 的 `useEffect` 依赖只有 `[chain]`（:133）导致切主题不重绘（T10 修）；`types.ts:68-74` `OUTCOME_META` 用 antd 预设色名（`lime` 与 `green` 不可区分）已由 `DecisionStatusTag` 取代。
12. **【建议，team-lead 提出】把本次文档自检固化为 `scripts/check_docs.py`**：交付前用的 §12 八项检查（代码围栏成对、表格行间无空行、**表格列数一致（`|` 在单元格内必须写成 `\|`，含行内代码里的）**、章节号递增、人日合计与任务表一致、已删除端点名无残留、emoji 计数、OpenAPI `$ref` 无悬空）——**第八项是本轮实测补的**：有 6 行的行内代码含未转义 `|`（如 `` `decided|failed` ``），整行被切成多余单元格，空行检查发现不了，只有列数检查能抓目前是一次性脚本。建议固化进仓库并在 pre-commit 跑——否则下一个改这份文档的人会重复踩"表格被一个空行切断"这类**只有渲染后才看得见**的坑（本次已实际发生一次）。**本期不做**（不改 CI、不新增脚本目录），仅登记。
13. **【P1】`SLA` 阈值与 `SYNC_STALE_MINUTES` 统一下发**：现为 SLA 走服务端 `settings`、同步窗口走前端常量（理由见 §3.2：前者决定数据集合、后者只决定文案）。P1 引入配置下发接口后两者同批迁移，避免两套配置源。PRD §5.1.4 / §8〈同步窗口必须诚实且有上限〉已登记同批。
14. **【P0，本轮实测，已报后端】`status_matrix.py:58` 的 docstring 仍写"路由映射 409"**：Spec 与代码行为都已定为 **500**（内部不变量被破坏）。这不是逻辑错，是**照注释实现就会错**——本 Spec 已第三次遇到同一类问题（另两次：`SYNC_STALE_MINUTES` 的注释、`"非法 22 个"`实为 23）。**规矩**：改常量 / 枚举 / 状态码时，注释与实现必须在同一提交内改完；只改实现不改注释，等于给下一个人留了一个"看起来是笔误"的坑，他会"修正"回去。
15. **【P0，本轮实测，已报后端】`PendingDecisionItem` 缺 `decided_waited_minutes`、多 `evidence_count`**；`decision_query_cypher.py` 的 `_ORDER_CLAUSES` 与前端 `ledgerQuery.ts` 的 `LedgerSort` 仍含 `evidence_count` 升降序。契约已把这四项列为 P1 并移除，**代码未跟上**。影响：§6 第 21 条的"两个等待时长必须有差异"断言今天**跑不起来**（字段不存在）。
16. **【已从"假防线"转成真防线】函数源码跨度 ≤40 行现在有机检**：PM 给了零依赖的 `ast` 方案（`end_lineno - lineno`），已收进 §10 门禁。**顺带纠正两件事**：
    - **名字改了**：原来叫"单函数 ≤40 行"，`ast` 量的是**源码跨度**（含注释与空行），不是逻辑复杂度。**名字不改就是骗人**——按"逻辑行数"理解的人会以为它测的是圈复杂度。
    - **存量本来就不达标**：全模块实测 **20 个**函数超 40 行源码跨度（最大 `pipeline.py:execute` 223 行、`executor.py:submit_action` 163 行）。所以门禁写成两段——**新代码 `decision_hub/` 必须 0；存量按基线 20，只许减不许增**。写成"全模块期望 0"会是永久红，那和没有检查同效。
    - 这是对 PM 那句提醒的执行：**"为一条本来能绿的东西保留'我承认它没有防线'的注记，会让读者低估其他注记的可信度"**——读者分不清哪条是真没有、哪条是懒得写。
17. **【P1】`error.code` 的缺省语义需要前端二次确认**：本期 `code` 仅在 `APIError` 家族有值，500 与 `HTTPException` 都没有。若后续要"每个错误都有机器可读 code"，正确路径是给 `HTTPException` 用法逐步换装，而不是给 500 编一个 code——**500 没有 code 是有意的边界**（§11 已知边界）。
