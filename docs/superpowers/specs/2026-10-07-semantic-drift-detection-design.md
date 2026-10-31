---
id: odap.l15.specs-2026-10-07-semantic-drift-detection-design
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

# 语义漂移检测（drift scan）设计

- **状态**：待复审
- **日期**：2026-10-07
- **范围**：子项目 2 —— 术语分叉现状扫描 + 三来源口径演进 diff + 落库报告 + commit 侧道自动触发 + semantic-admin 漂移页
- **关联**：子项目 1 spec `2026-10-07-concept-gap-loop-design.md`（同批补齐；本设计独立存储，不依赖 gap_pool）；参考实现 BeModel「语义漂移」两条检测线
- **规则约束**：AGENTS.md 规则 2（服务层返回 `{"status","message"}` dict）、规则 6（routes→services→storage）、规则 9（新模块零测试不提交）、规则 12（架构级决策需 ADR + 文档同步）、规则 14（失败显式、兜底可观测、禁止幻影调用/hasattr 探测式降级、测试必须执行真实函数体）

---

## 1. 背景与问题

系统集成里最贵的一类 Bug 是「同一个词在不同系统里指的不是同一件事」。ODAP 当前**没有任何漂移可见性**：

- 术语分叉无检测：同一说法原文挂到多个 USL 术语（概念）时无人知晓，直到问答答错才暴露。
- 口径演进无追溯：概念定义在哪个版本从什么改成了什么，无字段级变更记录。
- 指标口径（indicator-types）**无历史快照**：改了公式不留痕，「口径在哪个版本从什么改成什么」无从查起。
- USL 术语变更无历史：`UslTerm` 只有 `updated_at`，无 before/after。

BeModel 的两条检测线（术语分叉 = 分歧的直接证据；口径演进 = 相邻发布版本字段级 diff）与一条纪律（**只报告真实数据，不做任何占比推断**）是本设计的直接参照。

## 2. 已锁定决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 组件归属 | **独立 `drift_scan` 子服务**（`biz/semantic_admin/drift_scan/`），报告与发现全部落库 | 报告即不可变证据；自动触发必须有落点；与 gap_pool 的「信号聚合」纪律分离 |
| 触发时机 | **双触发**：手动 `POST /drift/scan` + 本体 commit 后侧道自动扫描 | 用户锁定决策；自动扫描走 `asyncio.create_task`，异常绝不传播 commit 路径 |
| 演进范围 | **三来源**：① 相邻版本 doc_snapshot 字段级 diff；② indicator 口径快照积累后 diff；③ USL 术语历史 diff | 用户锁定决策；② 需新建历史积累写钩子，演进 diff 从第二个快照起可用 |
| fork 判定 | 全量 USL 术语按说法原文分组（canonical+synonyms+near_synonyms+aliases，**排除 stoplist 与空串**），挂 ≥2 个 distinct term 即分叉 | 分歧的直接证据，不是猜测 |
| 失败语义 | 单源失败 → 跳过该源 findings 但**必记 `source_errors`**；全源失败 → report status=failed | 规则 14 失败显式，无静默跳过 |
| 扫描鉴权 | `POST /drift/scan` 用 `get_current_user`（分析操作，对语义资产只读） | 不改动语义资产的写操作才需 verify_semantic_writer |
| 报告纪律 | 报告完成后**不可变**；counts 全为 `len(findings)`；**不产任何比例/推断** | BeModel「只报告真实数据」纪律 |
| 前端 | 本期含漂移页（扫描按钮 + 报告列表 + 双栏详情 + source_errors banner） | 与子项目 1 页面一致 |
| ADR | 新增 **ADR-087 语义漂移检测** | 规则 12 架构级决策 |

## 3. 关键事实（决定实现方式）

- **doc_snapshot 真实落库**：commit 路径 `biz/core/ontology/ontology_api/services/ontology_service.py:174` `commit_schema_version`，`:250` 写 `doc_snapshot=json.dumps(snapshot)`。版本链 `parent_version` 指针（`design/services/version_service.py:28-48`）。→ 「相邻发布版本」= 相邻 committed 版本。
- **稳定 join 键**：`deterministic_entity_id(entity_type, name)`（`design/schema/document.py:95`）——实体跨版本 join 用 entity_id，不靠位置。
- **indicator 写钩点**：`ontology_service.py:892 create_indicator_type` / `:927 update_indicator_type`；级联删除在 `:159` 调 `storage.delete_indicator_types_by_ontology`（bulk，返回 int）→ 删除历史在级联调用点**先取 before 再删**记录。
- **term 写钩点**：`usl_manager_service.py:180 create_term` / `:231 update_term` / `:257 delete_term`。
- **无 publish/release 概念**：semantic_admin 无发布门禁版本对象，演进 diff 的「版本」对 ②③ 来源退化为**快照时间序**（captured_at / at 相邻），报告中标注 source 语义差异。
- **OntologyDocument 六内容体**：entities/relations/events/actions/rules/constraints（`design/schema/document.py:210-235`），字段级 diff 覆盖 entities/relations/rules/constraints 四类（actions/events 为运行时数据，不进演进 diff，spec 明示）。

## 4. 设计

### 4.1 组件边界

```
apps/api/odap/biz/semantic_admin/drift_scan/
  models/drift.py                 # DriftReport / DriftFinding dataclass + DriftKind(str,Enum: fork|evolution) + EvolutionSource(str,Enum: version_snapshot|indicator_caliber|usl_term)
  storage/sqlite_drift_storage.py # 四表；connect/close 每次调用、JSON TEXT、ISO 时间
  services/scanners.py            # fork_scan(terms, scope) / diff_version_snapshots(a,b) / diff_indicator_snapshots(rows) / diff_term_history(rows)：纯函数
  services/snapshot_writer.py     # record_indicator_snapshot(...) / record_term_history(...)：写钩子入口
  services/drift_service.py       # run_scan(scope, trigger) / list_reports / get_report / on_ontology_committed(oid)
  api/schemas.py / api/routes.py  # prefix /api/semantic-admin/drift
```

调用方向 routes→services→storage（规则 6）；services 返回 dict（规则 2）；routes 统一 `except HTTPException: raise`。

### 4.2 存储四表

| 表 | 关键列 |
|----|--------|
| drift_scan_reports | id, trigger(manual\|commit), ontology_id NULL, scope_json, started_at, finished_at, status(ok\|failed), error TEXT NULL, source_errors_json, counts_json |
| drift_findings | id, report_id, kind(fork\|evolution), source, subject, subject_label, field NULL, old_value_json NULL, new_value_json NULL, sides_json NULL(fork 两侧证据), version_ref_json NULL, at |
| indicator_caliber_snapshots | id, indicator_id, ontology_id, definition_json, captured_at, captured_version_id NULL, change_op(create\|update\|delete) |
| usl_term_history | id, term_id, domain_id, op(create\|update\|delete), before_json NULL, after_json NULL, at |

run_scan 事务性写入 report + N findings；报告完成后不可变（无 update 接口）。

### 4.3 写钩子与纪律

- indicator create/update 成功后（`ontology_service.py:892/927` 返回成功分支）各加一次 `snapshot_writer.record_indicator_snapshot(...)`；级联删除点（`:159` 前）先 list before 再删，记 op=delete。
- term create/update/delete 成功后（`usl_manager_service.py:180/231/257`）各加一次 `record_term_history(...)`（update 带 before/after）。
- 钩子失败 → `logger.warning` + 模块级计数（stats 可见），**绝不阻塞/回滚主写**（规则 14 侧道可观测）。

### 4.4 fork 扫描算法（纯函数）

输入 scope 内全量 UslTerm；展开 expression→[term refs]（canonical+synonyms+near_synonyms+aliases；排除 `stoplist_flag=True` 与空串/纯空白）；expression 映射 ≥2 distinct term id → finding(kind=fork)，`sides_json` = 各侧 `{term_id, canonical, domain_id, semantic_type, from_list}`。counts.forks = len。

### 4.5 演进 diff 算法（纯函数，无 LLM 无推断）

- **version_snapshot**：沿 parent_version 取相邻 committed 且含 doc_snapshot 的版本对；entities 按 entity_id join，diff 字段 name/name_en/aliases/basic_properties/statistical_properties/capabilities/constraints（deep compare，报变更键 old/new）；relations 按 relation_id（source_entity/target_entity/relation_type/properties）；rules 按 rule_id（condition/consequence/priority）；constraints 按 constraint_id。新增/删除主体记 `field='__added__'/'__removed__'`。actions/events 不进 diff（运行时数据，明示）。
- **indicator_caliber**：每 indicator_id 按 captured_at 序相邻快照 diff definition_json 键级 old/new；create/delete op 记 `__added__`/`__removed__`。
- **usl_term**：每 term_id 按 at 序相邻历史行 diff before/after（canonical/synonyms/near_synonyms/aliases/definition/semantic_type/stoplist_flag）。
- ②③ 来源的「版本」语义为快照时间序，finding 的 version_ref_json 存 `{prev_at, cur_at}`；① 存 `{version_a, version_b}`。

### 4.6 触发与失败语义

- 手动：`POST /drift/scan`（get_current_user），body scope `{ontology_id?, domain_id?}`，同步 run_scan 返回 report_id。
- 自动：commit 完成点调 `drift_service.on_ontology_committed(oid)` → `asyncio.create_task(run_scan(trigger='commit', ontology_id=oid))`；task 内异常 → 该 report status=failed + error 落库 + warning，**不传播 commit 路径**。
- 单源失败：跳过该源 findings，`source_errors_json[source]=error`；≥1 源成功 → status=ok；全失败 → status=failed。并发扫描不去重，各出独立报告。

### 4.7 API 清单

prefix `/api/semantic-admin/drift`：`POST /scan`、`GET /reports`（分页 + trigger/status 过滤）、`GET /reports/{id}`（report + findings 按 kind/source 分组）、`GET /reports/latest`。

### 4.8 前端漂移页

`/semantic-admin/drift`：扫描按钮 + 报告列表（trigger、时间、counts、status、source_errors badge）；报告详情双栏——fork 列表（expression + sides 证据）与演进列表（三来源分组、字段级 old→new）；source_errors 顶部 banner。菜单走 seed 权威源 `biz/platform/menu_config/seeds/seed_four_steps.py` + 既有 DB 迁移脚本。

## 5. 测试策略（规则 9 / 14.6）

> 单测目录为 `apps/api/tests/unit/`（仓库根 `tests/` 无 unit 子目录）；drift 相关测试放 `apps/api/tests/unit/biz/semantic_admin/`。运行命令必须带离线变量，见计划 Global Constraints。

- `apps/api/tests/unit/biz/semantic_admin/test_drift_fork_scanner.py`：真 UslTerm 对象；fork 判定、stoplist 排除、空串排除、单术语表达无误报。
- `apps/api/tests/unit/biz/semantic_admin/test_drift_evolution_diff.py`：手构两份 OntologyDocument（字段改/增/删）断言 field 级 old/new 与 `__added__`/`__removed__`；relations/rules 按 id join；indicator/term 快照序 diff。
- `apps/api/tests/unit/biz/semantic_admin/test_drift_storage.py`：tmp_path 真 DB；report+findings CRUD、快照/历史追加、坏 JSON 容错。
- `apps/api/tests/unit/biz/semantic_admin/test_drift_routes.py`：状态码映射、`except HTTPException: raise` 透传。
- `apps/api/tests/unit/biz/semantic_admin/test_drift_auto_trigger.py`：commit 钩子调用后真实调度扫描并出 report；注入扫描异常 → report failed + error 落库 + warning，commit 路径返回正常；全程真 run_scan + 真 scanners。

## 6. 文档同步（规则 12）

- 新增 **ADR-087 语义漂移检测**（fork 判定规则、三来源演进 diff、报告不可变证据、source_errors 显式、侧道自动触发）+ `docs/07-adr/README.md` 索引。
- `docs/03-modules/README.md` 模块清单加 drift_scan。
- 新路由 prefix 注册 `router_registry.py` + agents.md 附录 E 速查表。
- 菜单 seed + 迁移脚本。
- 提交前对照 `docs/09-checklists/DOC_SYNC_CHECKLIST.md` 逐项检查。

## 7. 验收标准

1. 五个测试文件全绿。
2. 种子数据：两个含已知字段变更的版本 + 一对 fork 术语 + 一次 indicator 更新 + 一次 term 改名 → 扫描报告 findings 与这些变更**恰好一致、不多不少**；source_errors 注入故障可见。
3. commit 后自动触发产出 trigger=commit 报告；漂移页双栏与 banner 在 dev 容器（`python apps/api/bootstep.py dev`）手验可见。

## 8. 非目标（Out of Scope）

- 任何比例/占比推断；LLM 参与扫描或 diff。
- 定时（cron）扫描；跨 ontology 的 fork 合并视图。
- actions/events 的演进 diff（运行时数据）。
- 指标口径在「本体版本号」维度的对齐（②来源为快照时间序，报告已标注语义差异）。
