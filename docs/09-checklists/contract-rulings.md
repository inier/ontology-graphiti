---
id: odap.l9.contract-rulings
status: authoritative
owner: qa
version: ''
layer: L9
concern: contract-rulings
lifecycle: living
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 前后端契约裁定唯一权威，前端据此执行
governance_evidence: 标题「前后端契约裁定（2026-10-17，后端裁定，前端执行）」
---

# 前后端契约裁定（2026-10-17，后端裁定，前端执行）

裁定锚点优先级：`docs/00-requirements/SPEC-v2.md` §5（锁定端点） > `docs/02-architecture/openapi-v2.yaml`（机器可读真源） > **后端实际实现**（存量 `/api/*` 端点，SPEC §5 未覆盖者以此为准）。

裁定原则：**不为「看起来一致」改后端既有响应破坏现有消费者**。凡涉及后端改动，只允许 **additive（新增字段/新增端点）**；breaking 变更必须单独立项并给过渡方案。

---

## 总览

| # | 争点 | 结论 | 归谁改 | breaking |
|---|---|---|---|---|
| 1 | `ObjectView.object_type_id` vs `base_type_id` | 两个不同概念，**不统一**；ObjectView canonical 为 `base_type_id` | 不改（仅前端修一处误映射） | 否 |
| 2 | `/api/ontology/inheritance*` vs `/edges` | canonical 为复数 `/inheritance/edges`；图聚合端点缺失，**本轮不实现** | 前端改 3 处路径 | 否 |
| 3 | `VersionHistory` 依赖 `doc_id` | 后端**保证返回该字段**，值可能为空串 | 不改 | 否 |
| 4 | `registryApi.update` 签名 | canonical 主键名为 `type_id`，且**不接受** `constraints` | 前端改 | 否 |
| 5 | `getSystemMetrics()` 返回结构 | canonical 为「按指标类型分组的耗时统计」 | 前端改类型 | 否 |
| 6 | `ObjectView.filters` dict vs `FilterRule[]` | canonical 线上形态为 `{field: {op: value}}`；后端已支持数组入参归一 | 后端已做（入参）；前端做读侧转换 | 否 |

---

## 1. `ObjectView.object_type_id` vs `base_type_id`

**结论：不是同一概念，不需要统一。**

- `object_type_id` —— ObjectType **自身主键**，出现在 `ObjectTypeSummary`（`GET /api/ontology/object-types` 的返回项）与 `ComputedProperty*` / `MaterializedView*` 等以 ObjectType 为主体的载荷里。
- `base_type_id` —— ObjectView 上**指向** ObjectType 的外键（视图是「基于某个 ObjectType 的投影」）。

**canonical shape（ObjectView）**：后端 `ObjectView.base_type_id`（`apps/api/odap/biz/core/ontology/view/models/view.py:26`）、存储列 `object_views.base_type_id`、前端 `viewApi.ts:24` 三方已一致，**无需改动**。

**唯一真错（前端）**：`apps/web/src/modules/ontology/services/viewApi.ts:156` 与 `:173` 把 `base_type_id` 赋给 `object_type_name`，即「拿 id 当名字」。两种修法：删掉 `object_type_name`（用 `base_type_id` 展示），或真去 `listObjectTypes()` 里查 `name`。

**breaking**：否。

---

## 2. `/api/ontology/inheritance*` vs `/edges`

**后端真源（已存在，`inheritance/api/routes.py:36`，prefix `/api/ontology/inheritance`）**：

| Method | Path | 说明 |
|---|---|---|
| POST | `/edges` | 加边，body `{child_type_id, parent_type_id, discriminator?}` |
| GET | `/edges?child=&parent=` | 查边，返回 `{edges: [...], count}` |
| DELETE | `/edges/{child_id}/{parent_id}` | 删边（**成对主键，无 edge_id**） |
| GET | `/resolve/{type_id}` | 属性解析链 |
| POST | `/validate` | body `{type_id}` |
| POST/GET/PUT/DELETE | `/mixins`、`/mixins/{mixin_id}` | Mixin CRUD |
| POST | `/mixins/{mixin_id}/attach|detach/{type_id}` | Mixin 挂载 |

**前端 3 处真错（必改）**：`apps/web/src/modules/ontology/components/InheritanceGraph.tsx`
- `:80` `GET /api/ontology/inheritance?...` —— 该路径**不存在**（404）
- `:129` `POST /api/ontology/inheritance/edge` —— 单数，应为 `/edges`
- `:142` `DELETE /api/ontology/inheritance/edge/{edgeId}` —— 单数且形态错，应为 `/edges/{child_id}/{parent_id}`

**图聚合端点 `{nodes[], edges[]}`**：后端**没有**该端点，属真实功能缺口。裁定：**本轮不实现**，理由：
- SPEC §7 把 `/ontology/designer`、`/ontology/explorer` 标为「既有」API，不在本轮锁定交付面；
- 前端期望的节点字段（`parent_count` / `child_count` / `inherited_property_count` / `resolution_chain`）需要产品先确认统计口径（是否含 Mixin、`resolution_chain` 是全量下发还是按需拉 `/resolve/{type_id}`），口径未定就实现等于把猜测写进契约。

**前端短期过渡方案**：`GET /object-types`（节点）+ `GET /inheritance/edges`（边）在前端组合；节点统计字段先在 UI 上省略，或仅在点选节点时调 `GET /resolve/{type_id}` 取解析链。后端补 `/inheritance/graph` 已登记为本轮 unfinished。

**breaking**：否（前端改的是本就 404 的调用）。

---

## 3. `VersionHistory` 依赖 `doc_id`

**结论：后端保证返回 `doc_id`，无需改动。**

- 数据源：`OntologyVersion.doc_id: str` 为 dataclass **必填字段**（`design/services/version_service.py:34`），`to_dict()` = `asdict(self)` 后仅剔除 `doc_snapshot`，故 `doc_id` **必然出现在响应里**。
- 响应 schema `OntologyVersionResponse.doc_id: Optional[str] = None`（`workspace/api/schemas.py:219`）声明为可选，是契约层面的保守声明：历史版本可能因文档已解绑而为 `""`。

**canonical shape**：`doc_id: string`（字段必在，值可能为空串）。

**前端要求（不改代码，但必须保留现有逻辑）**：`apps/web/src/modules/version/pages/VersionHistory.tsx:77` 的 `docIdOf()` + `:96` 的 `if (!docId)` 空值守卫是**承重逻辑**（`""` 与 `undefined` 都会命中），后续重构不得删除；如需类型精确，可把 `doc_id: string` 放宽为 `string | null`。

**breaking**：否。

---

## 4. `registryApi.update` 签名

**canonical 请求体**（`registry/api/schemas.py:23-36` `RegistryObjectTypeUpdate`，12 个字段，全部可选）：
`name` / `display_name` / `description` / `properties[]` / `links[]` / `actions[]` / `primary_key[]` / `classification_level` / `icon` / `color` / `is_active` / `parent_type`

**canonical 响应体**：后端直接返回存储行字典（`ontology_api/services/ontology_service.py:516`），主键字段名是 **`type_id`**（不是 `id`），并含 `ontology_id`、`version_id`、`created_at`、`updated_at`；**不含** `constraints`。

**前端 2 处真错（必改）**：
1. `UpdateObjectTypeRequest = Partial<Omit<CreateObjectTypeRequest, 'ontology_id'>>` 里带 `constraints`。Pydantic 默认 `extra="ignore"` → 该字段被**静默丢弃**（比 422 更难排查：用户以为保存成功）。
2. `ObjectType.id` 与后端 `type_id` 不一致 → 读侧拿到 `undefined`。

**裁定**：**前端改**——发送端去掉 `constraints`；读侧把 `id` 改为 `type_id`（或做一次映射）。

**后端不改的理由**：约束在 ODAP 是**独立模型** `Constraint`（`design/model/models/constraint.py:20`，按 `object_type_id` 关联），语义上不属于 ObjectType 本体；要把 `constraints` 塞进 `object_type_definitions` 需要新增列 + 幂等迁移 + OMS 同步链路改造，属独立需求，不与本轮混做。

**breaking**：否。若确需 `constraints` 落库，另立需求（后端新增列 + 迁移 + 契约登记）。

---

## 5. `getSystemMetrics()` 返回结构

**canonical shape**：`GET /api/v1/monitoring/performance` 返回**按指标类型分组的耗时统计**，指标类型固定四个（`infra/monitoring/performance_monitor.py:25`）：

```json
{
  "llm_calls":        {"count": 128, "mean": 0.73, "median": 0.69, "min": 0.21, "max": 3.45, "p95": 1.88, "p99": 2.91},
  "database_queries": {},
  "api_requests":     {"count": 942, "mean": 0.043, "...": "..."},
  "tool_executions":  {}
}
```
无采样记录的类型为**空对象** `{}`；所有数值单位为**秒**。

**前端真错（必改）**：`apps/web/src/modules/shared/services/api.ts:1541` 声明 `{cpu_percent, memory_percent, disk_percent, uptime_seconds, active_connections, request_count, error_count}` —— 七个字段**一个都不存在**。该方法当前无调用方，属潜伏地雷。

**裁定**：**前端改类型**；后端已在 `openapi-v2.yaml` 登记 `/monitoring/performance` 与 `/monitoring/performance/reset` + `PerformanceStats` schema。
若确实需要 CPU/内存/磁盘面板，需后端新增系统资源端点（psutil），**另立需求**。

**breaking**：否。

---

## 6. `ObjectView.filters` dict vs `FilterRule[]`

**canonical wire shape**：字典 `{field: {op: value}}`，`op` ∈ `eq|ne|gt|lt|in|contains`（`view_query_engine_impl.py:82-89`）；也接受 `{field: scalar}` 等价于 `eq`。

**后端本轮已做（additive，零破坏）**：请求边界归一 `view/api/schemas.py::normalize_view_filters`
- `CreateViewRequest` / `UpdateViewRequest` 的 `filters` 现在同时接受 `{field: {op: value}}` 与 `[{field, op, value}]`；
- 数组入参按 `=`→`eq`、`!=`→`ne`、`>`→`gt`、`<`→`lt`、`contains/like`→`contains` 映射；同字段多条规则合并进同一操作符字典（语义等价 AND）；
- 不支持的算子（如 `>=`）→ 422 并指明 `filters[i].op`，**不再**静默丢过滤条件；
- 字典入参原样透传，存量调用方零影响。

**前端仍需改（读侧）**：响应恒为字典，而 `viewApi.listViews()` / `getView()` 目前把 `filters` 硬编码成 `[]`（`viewApi.ts:157`、`:173`），**会把真实过滤条件丢掉**，设计器回显后一保存就清空后端条件。需做 `dict → FilterRule[]` 转换：

```ts
const toRules = (filters: Record<string, unknown>): FilterRule[] =>
  Object.entries(filters ?? {}).flatMap(([field, expr]) =>
    expr && typeof expr === 'object' && !Array.isArray(expr)
      ? Object.entries(expr as Record<string, unknown>).map(([op, value]) => ({
          field, op: ({ eq: '=', ne: '!=', gt: '>', lt: '<', contains: 'contains', in: 'contains' } as const)[op] ?? '=',
          value: String(value),
        }))
      : [{ field, op: '=' as const, value: String(expr) }],
  );
```

**breaking**：否（后端只放宽入参）。

---

## 本轮后端配套改动清单

| 文件 | 改动 | 性质 |
|---|---|---|
| `apps/api/odap/biz/core/ontology/view/api/schemas.py` | 新增 `normalize_view_filters` + 两个 `field_validator` | additive |
| `docs/02-architecture/openapi-v2.yaml` | 新增 3 个 F9 动作端点 + `SuggestedAction`/`QaAction` schema | additive |
| `apps/api/tests/unit/test_view_filters_contract.py` | 15 条契约测试 | 新增 |

---

## 技术债偿还：AC-37 图证据校验 + AC-31 SHACL 分支

上轮登记的两个 TODO 已落地，均为**内部实现补齐**，不改任何对外响应契约。

### 1. `graph_edge` 证据校验器（AC-37）

| 项 | 内容 |
|---|---|
| 实现 | `biz/core/ontology/orchestration/impl/graph_evidence.py` |
| ref 形态 | `edge:<src>-><dst>`、`edge:<src>-[<REL_TYPE>]-><dst>`、裸节点标识（检索行只给 `entity_id`/`id` 时按节点校验） |
| 判定 | 查 Neo4j 真实存在性：节点 `(:Entity {id})`，关系类型按写入约定归一为 `upper().replace(' ', '_')` |
| 不可用 | 驱动缺失 / `NEO4J_PASSWORD` 未配置 / 连接失败 / 查询异常 → `(False, "GRAPH_UNAVAILABLE|GRAPH_QUERY_FAILED: …")`，**绝不假通过** |
| 注入点 | `DefaultEvidenceResolver(graph_verifier=…)` 仍优先；未注入时走 Neo4j 真实校验 |
| 前置条件 | 需配置 `NEO4J_PASSWORD`（缺省时快速失败，不发起连接，避免测试/CI 卡在 `localhost:7687`） |

### 2. `OutputContractGate` 的 SHACL 分支（AC-31）

| 项 | 内容 |
|---|---|
| 实现 | `biz/core/ontology/orchestration/impl/shacl_gate.py` + `output_contract_gate.py` 接线 |
| 触发条件 | `DraftAnswer.payload_ttl` 非空（结构化回答以 RDF/Turtle 承载；纯文本回答路径完全不变，不构造校验器） |
| 形状来源 | `semantic_admin/shacl_store`（`sa_shacl_shape`），按 `(ontology_version_id, constraint_revision, target_type)` 精确命中；未给失效键时取该类型最近登记的一条 |
| 违约码 | `SHACL_VIOLATION` / `SHACL_SHAPE_MISSING` / `SHACL_SHAPE_EMPTY` / `SHACL_PAYLOAD_INVALID` / `SHACL_SHAPE_INVALID` / `SHACL_TARGET_CLASS_MISSING` / `SHACL_PAYLOAD_EMPTY` / `SHACL_UNAVAILABLE` |
| 语义 | 任一违约即 `contract_ok=False` + `blocked_reasons[]`，答案按「部分答案 + 违约说明」返回，内容不丢失 |

配套测试：`tests/unit/biz/ontology/test_graph_evidence.py`（20 条）、`test_shacl_output_gate.py`（17 条）。
