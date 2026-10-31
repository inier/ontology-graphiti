---
id: odap.l15.specs-2026-10-07-concept-gap-loop-design
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

# 概念缺口回路（concept gap pool）设计

> **⚠️ 实现前设计快照（historical）**：本文是编码开始前的设计稿，其「状态：待复审」及 §4.3 接线点位、§5 测试口径等以设计时点的理解写成，**实现落地时已有出入**。**权威的 as-built 记录以 [ADR-086](../../07-adr/ADR-086_概念缺口回路.md) 为准**（已批准，含最终接线点位勘验、resolve-check 只读回归守卫 M1、`canonical_of` 发信 blast radius 登记等）。阅读本 spec 时请以 ADR-086 校正实现细节；本文正文保留为设计演进留痕，不再逐条回填。

- **状态**：待复审（设计快照；as-built 见 ADR-086）
- **日期**：2026-10-07
- **范围**：子项目 1 —— 四类缺口信号源接通 + gap_pool 子服务 + 晋升/驳回闭环 + stats + semantic-admin 前端三页
- **关联**：子项目 2「语义漂移检测」（独立 spec，复用本设计的 `concept_gaps` 存储与 emitter 基础设施）；参考实现 BeModel 概念缺口回路
- **规则约束**：AGENTS.md 规则 2（服务层返回 `{"status","message"}` dict）、规则 6（routes→services→storage）、规则 9（新模块零测试不提交）、规则 12（架构级决策需 ADR + 文档同步）、规则 13（临时文件/菜单 seed 权威源）、规则 14（失败显式、兜底可观测、禁止幻影调用/hasattr 探测式降级、测试必须执行真实函数体）

---

## 1. 背景与问题

ODAP 的本体语义层在运行时持续产生「概念缺口」信号——用户问到了本体里没有的词、检索降级、QA 兜底回答「未找到相关信息」。当前这些信号**全部只落在 logger 里**，无任何聚合、无回路：

- `UslTermResolver.canonical_of`（`biz/semantic_admin/usl_manager/services/usl_term_resolver.py:105-115`）未命中返回 `None`，调用方各自处理，无聚合点。
- `nl_engine` USL 归因 miss（`biz/core/ontology/semantic_retrieval/impl/nl_engine.py:61,68,99`）直接 `return None`。
- `intent_recognizer` 未命中本体集合的候选**丢弃**（`biz/data/qa/pipeline/understanding/intent_recognizer.py:112,162`），防幻觉但不留痕。
- 检索降级：`mdl_engine.py:122` `status="degraded"`、`metric_engine.py:80-87` `return None`、`chain_engine.py:130` degraded 标记。
- QA 兜底：`qa_engine.py:1384,1890` `self._answer_general(query, "未找到相关信息。", [])`。

后果：本体**化石化的速度不可见**——运营无法知道哪些高频词缺定义、补没补上、补上后是否真的能答。BeModel 的概念缺口回路给出的验收标准是「**同一个问题下次能答上**」，本设计把这条标准落成接口与测试，而非口号。

## 2. 已锁定决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 信号源范围 | **四类全接通**：term resolve miss / mapping failure / QA unanswered / NL query unanswered | 一次性打通回路，避免半回路产生误导统计 |
| 存储归属 | **独立 `gap_pool` 子服务**（`biz/semantic_admin/gap_pool/`），不扩展 candidate_store | 缺口≠候选；candidate 有审批语义，缺口是信号聚合，生命周期不同 |
| 前端范围 | **本期含完整三页**（list / detail / stats dashboard） | 运营可见性是回路成立的前提 |
| emitter 失败策略 | **同步直调；异常时 logger.warning + 内存 `emit_failures` 计数，绝不 raise、绝不阻塞主响应** | 规则 14：兜底可观测；缺口信号丢失不应拖垮问答主路径 |
| 聚合键 | `expression` 原文（strip 后）+ `scope_key = f"{workspace_id or '-'}::{domain_id or '-'}"`，唯一索引 `(expression, scope_key)` | 对齐 BeModel「按说法原文分组」；scope 隔离避免跨 workspace 串味 |
| heat 语义 | 每次 signal +1（含首次）；`sources_json` 仅保留最近 50 条 occurrence，`source_counts_json` 存全量计数 | 防 occurrence 无界增长，计数不丢 |
| 晋升路径 | `POST /gaps/{id}/promote` → CandidateService 建 candidate（`source_type='concept_gap'`），后续质量门/两级审批/writeback **全部走既有流程不改** | 复用既有人工裁决链，不新造审批 |
| 状态回流 | writeback 成功 → `on_candidate_resolved(id,'adopted',term_id)` → ADOPTED；审批驳回 → REJECTED | 闭环状态以既有流程终态为准，不猜 |
| 人工裁决 | promote / dismiss 均人工；AI 只聚合 | 「采不采永远人决定」 |
| REJECTED 复活 | REJECTED gap 收到新信号 → 回 OPEN，heat 继续累加 | 「再次被问」= 上次裁决没覆盖真实需求 |
| 菜单接入 | 走菜单 seed 权威源 `biz/platform/menu_config/seeds/seed_four_steps.py`；既有 DB 需迁移脚本（seed 幂等 skip 陷阱） | 菜单系统 seed-driven 事实 |
| ADR | 新增 **ADR-086 概念缺口回路** | 规则 12 架构级决策 |

## 3. 关键事实（决定实现方式）

- **candidate_store 已有可复用字段**：`source_type` / `source_ref` / `triggered_by` / `source_text` / `provenance_json`（`biz/semantic_admin/candidate_store/storage/sqlite_candidate_storage.py:397-398,437`）。gap→candidate 传播直接填这些字段，无需改 candidate 表。
- **semantic-admin 路由鉴权约定**：读 `Depends(get_current_user)`；写 `Depends(verify_semantic_writer)` 或 `verify_semantic_admin_only`（`biz/semantic_admin/usl_manager/api/routes.py:77-387`）。gap 路由照此：读 get_current_user，promote/dismiss 走 verify_semantic_writer。
- **emitter 无统一收敛点**：四类信号散落 ~10 处，必须**逐点接线**（清单见 §4.3），无「一个装饰器全收」的捷径。接线点全部是既有显式失败/丢弃分支，不改变其原有返回值语义。
- **resolve-check 的判定器**：term 类缺口用 `UslTermResolver.canonical_of` 现场判定；NL query 类缺口 resolve-check 语义弱，返回 `via='none'` 并在 detail 说明，不假装能判定。
- **writeback 终态查询点**：`biz/semantic_admin/usl_writeback/` 既有 status 接口；adopted 回流挂在 writeback 成功回调，writeback 失败**不改 gap 状态**（保持 PROMOTED + 既有 status 页显式展示失败），规则 14 失败显式。

## 4. 设计

### 4.1 组件边界

新建 `apps/api/odap/biz/semantic_admin/gap_pool/`：

```
gap_pool/
  models/gap.py            # ConceptGap dataclass + GapStatus(str,Enum) + GapSignalSource(str,Enum)
  storage/sqlite_gap_storage.py   # SQLiteGapStorage：connect/close 每次调用、JSON TEXT、ISO 时间
  services/gap_emitter.py  # GapSignalEmitter.report(...)：同步、异常吞为 warning+计数
  services/gap_service.py  # record_signal / list / get / promote / dismiss / on_candidate_resolved / stats / resolve_check
  api/schemas.py           # 请求/响应 pydantic 模型
  api/routes.py            # prefix /api/semantic-admin/gaps
```

调用方向严格 routes→services→storage（规则 6）；services 返回 `{"status","message",...}` dict（规则 2）；routes 层统一 `except HTTPException: raise` 透传。

### 4.2 数据模型

表 `concept_gaps`（SQLite，JSON TEXT，时间 ISO-8601 UTC 字符串）：

| 列 | 类型 | 说明 |
|----|------|------|
| id | TEXT PK | uuid4 |
| expression | TEXT NOT NULL | 说法原文（strip） |
| scope_key | TEXT NOT NULL | `f"{workspace_id or '-'}::{domain_id or '-'}"` |
| heat | INTEGER NOT NULL DEFAULT 1 | 每次 signal +1 |
| source_counts_json | TEXT | `{source: count}` 全量计数 |
| sources_json | TEXT | 最近 50 条 occurrence `[{source, ref, at, detail}]` |
| status | TEXT | open / promoted / adopted / rejected |
| first_seen / last_seen / updated_at | TEXT | ISO |
| promoted_candidate_id | TEXT NULL | promote 时填 |
| resolved_term_id | TEXT NULL | adopted 时填 |
| dismiss_reason | TEXT NULL | dismiss 时填（status=rejected） |

唯一索引 `UNIQUE(expression, scope_key)`。heat 累加用 `UPDATE ... SET heat=heat+1` 原子完成。

状态机：`open → promoted → adopted | rejected`；`open → rejected`(dismiss)；`rejected + 新信号 → open`（heat 续累）。

### 4.3 Emitter 与接线点

```python
class GapSignalSource(str, Enum):
    TERM_RESOLVE_MISS = "term_resolve_miss"
    MAPPING_FAILURE = "mapping_failure"
    QA_UNANSWERED = "qa_unanswered"
    NL_QUERY_UNANSWERED = "nl_query_unanswered"

class GapSignalEmitter:
    def report(self, source: GapSignalSource, expression: str, *,
               workspace_id: str | None = None, domain_id: str | None = None,
               ref: str | None = None, detail: str | None = None) -> None: ...
```

同步直调 `gap_service.record_signal`；任何异常 → `logger.warning` + 模块级 `_emit_failures += 1`（stats 暴露，重启归零，文档注明），**绝不 raise**。

接线点清单（只加一行 emitter 调用，不改原分支返回值）：

| 信号源 | 文件:行 | 传参 |
|--------|---------|------|
| TERM_RESOLVE_MISS | `usl_term_resolver.py:105-115`（canonical_of 返回 None 前） | expression=入参, domain_id |
| NL_QUERY_UNANSWERED | `nl_engine.py:61,68,99` | expression=查询原文, ref=engine |
| MAPPING_FAILURE | `intent_recognizer.py:162`（未命中本体丢弃分支）；`mdl_engine.py:122`（degraded）；`metric_engine.py:80-87` | expression=候选词/查询, detail=原因 |
| QA_UNANSWERED | `qa_engine.py:1384,1890`（fallback 生成分支） | expression=query, workspace_id |

### 4.4 晋升与闭环

- `POST /gaps/{id}/promote`（verify_semantic_writer）：gap_service 调 CandidateService 建 candidate：`source_type='concept_gap'`、`source_ref=gap.id`、`source_text=expression`、`triggered_by=当前用户`、domain/workspace 取自 gap scope；gap→PROMOTED，记 `promoted_candidate_id`。
- 回调接线（两处各加一次调用）：usl_writeback 成功 → `gap_service.on_candidate_resolved(candidate_id, 'adopted', term_id)`；审批驳回 → `on_candidate_resolved(candidate_id, 'rejected')`。writeback 失败不动 gap 状态。
- `POST /gaps/{id}/dismiss`（verify_semantic_writer，body 带 reason）：open→rejected + `dismiss_reason`。
- `GET /{id}/resolve-check`：term 类用 `UslTermResolver.canonical_of(expression)` 现场判定，返回 `{resolvable, via:'term'|'none', detail}`；NL 类 `via='none'`。

### 4.5 API 清单

prefix `/api/semantic-admin/gaps`：

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/` | get_current_user | 过滤 status/source/workspace；默认 heat 降序；分页 |
| GET | `/{id}` | get_current_user | 详情含 sources 时间线 |
| POST | `/{id}/promote` | verify_semantic_writer | 建 candidate + 转 PROMOTED |
| POST | `/{id}/dismiss` | verify_semantic_writer | body: reason |
| GET | `/{id}/resolve-check` | get_current_user | 现场判定 |
| GET | `/stats` | get_current_user | 见 §4.6 |

### 4.6 Stats

`GET /stats` 返回：`total`、`by_status{open,promoted,adopted,rejected}`、`by_source{source:count}`、`emit_failures`（内存计数）、`top_heat`（top N）、`adoption_rate = adopted/(adopted+rejected)`（分母为 0 时返回 null，不造数）。**所有指标从真实记录计算，无比例推断**；resolve_check_pass_rate 昂贵，本期不算。

### 4.7 前端三页

semantic-admin console 内新增（复用既有 table/filter/i18n 约定）：

- `/semantic-admin/gaps`：列表页（expression, heat, source counts, status, first/last seen；行操作 promote/dismiss/resolve-check）。
- `/semantic-admin/gaps/{id}`：详情页（sources 时间线、source counts、状态历史、promoted candidate 链接、resolved term 链接）。
- `/semantic-admin/gaps/stats`：dashboard（total / by_status / adoption_rate / emit_failures 卡片 + top-heat 图）。

菜单项接入走 seed 权威源 `biz/platform/menu_config/seeds/seed_four_steps.py`；**既有 DB 需配套迁移脚本**（seed 幂等 skip 陷阱）。

## 5. 测试策略（规则 9 / 14.6）

> 单测目录为 `apps/api/tests/unit/`（仓库根 `tests/` 无 unit 子目录）；semantic_admin 相关测试放 `apps/api/tests/unit/biz/semantic_admin/`。运行命令必须带离线变量，见计划 Global Constraints。

- `apps/api/tests/unit/biz/semantic_admin/test_gap_pool_storage.py`：tmp_path 真 DB；CRUD、唯一索引去重、heat 累加、sources 50 条截断、状态迁移、坏 JSON 容错。
- `apps/api/tests/unit/biz/semantic_admin/test_gap_emitter.py`：**每钩点至少一条走真实函数体**——真 `UslTermResolver.load_terms` 建表后 `canonical_of` 未命中断言落库；qa fallback 直接调真实 `_answer_general` 生成分支；emitter 抛异常时主路径返回正常 + warning + `emit_failures` 递增。
- `apps/api/tests/unit/biz/semantic_admin/test_gap_routes.py`：状态码映射、`except HTTPException: raise` 透传、鉴权 Depends override。
- `apps/api/tests/unit/biz/semantic_admin/test_gap_promote.py`：gap→candidate 字段传播（source_type/source_ref/source_text）、on_candidate_resolved 转 ADOPTED/REJECTED、dismiss 写 reason。
- **回路验收测试** `apps/api/tests/unit/biz/semantic_admin/test_gap_loop_acceptance.py`：signal→gap→promote→approve→writeback→resolver reload→同 expression 命中，把「同一个问题下次能答上」固化为测试。

> 接线点修正：`chain_engine.py:130` 的 degraded 属**基础设施降级**（stepper 不可用），不是概念缺口，**不接**入缺口池（保持池内信号纯语义）。

## 6. 文档同步（规则 12）

- 新增 **ADR-086 概念缺口回路**（四信号源、heat 聚合、人工裁决、无静默兜底、side-channel 可观测）+ `docs/07-adr/README.md` 索引。
- `docs/03-modules/README.md` 模块清单加 gap_pool。
- 新路由 prefix 注册 `router_registry.py` + agents.md 附录 E 速查表。
- 菜单 seed + 迁移脚本。
- 提交前对照 `docs/09-checklists/DOC_SYNC_CHECKLIST.md` 逐项检查。

## 7. 验收标准

1. 上述 5 个测试文件全绿，回路验收测试绿。
2. dev 容器（`python apps/api/bootstep.py dev`）手验：制造一次未命中 → list 页可见 heat=1 → promote → 审批 → writeback → detail 页 ADOPTED + resolved term 链接 → resolve-check 返回 resolvable=true。
3. stats 全字段从真实记录来；emit_failures 可注入故障验证递增。

## 8. 非目标（Out of Scope）

- 口径卡巡检、一门两径（另立项）。
- 子项目 2 语义漂移检测（独立 spec，复用本设计的存储与 emitter）。
- gap 跨 workspace 合并视图、occurrence 全量留存（>50 条归档）。
