# ADR-082: 事件源与 BI 指标的语义候选抽取入口（资产流水线扩展）

## Status
**已接受（2026-09-25 设计获批；实现待 writing-plans 拆片落地）**

> 代码现实（截至本 ADR 写就，尚未实现）：5 类事件源 webhook/sensor/mcp/file/api 已列在
> `semantic_asset_pipeline` 的 `STRUCTURED_SOURCE_TYPES` 里，但经 `UnifiedIngestFacade._ingest_event`
> → `PerceptionHub.process_event` 后**不生成 OntologyDocument、不写 ingest_record**，
> `_resolve_ingest_documents` 回捞必然命中显式 error → 候选恒为 0（功能空转）。
> BI 指标（`business.db` 的 `business_indicators` 表）**无任何入口**进入 semantic_admin 候选抽取。
> 本 ADR 记录把这两类「散落结构化数据」接进候选抽取流的架构决策。

## Context

需求（用户 2026-09 指定最高优先级）：「自动从各类散落的数据（结构化和非结构化）中抽取业务语义，
提交业务审核」。Task #14/#22 审计确认：语义构建的编排器（`SemanticAssetPipeline.run` +
OL 流水线 L1~L6）是真的，但**两类典型散落数据抽不到**：

1. **事件源（webhook/sensor/mcp/file/api）**：`PerceptionHub.process_event`（`biz/data/perception/hub.py:106-133`）
   已经做了**真实 LLM 抽取**——`_extract` 调 `LLMExtractionStageHandler._extract_with_llm`
   产出 `ExtractionResult(entities, relations, events, actions, confidence)`（`perception/schemas.py:48-53`）。
   但门面 `_ingest_event`（`unified_ingest_facade.py:233-299`）只保留 `extraction_confidence`，
   把整个抽取结果丢弃；唯一持久化是 Graphiti episode 文本（截断 2000 字符 + 一行实体摘要）。
   资产流水线 `_run_structured` 拿到 `{event_id, extraction_confidence}` 后走
   `_resolve_ingest_documents`（按 `extracted_data.document_ids` 回捞 OntologyDocument），
   事件源必然失败 → 显式 error（合规但空转）。

2. **BI 指标（BusinessIndicator）**：存于 `business.db` 的 `business_indicators` 表
   （`biz/management/business/storage/sqlite_storage.py:78-99`），字段含 name/display_name/
   description/llm_description/indicator_type(kpi/metric/dimension)/calculation_formula/unit/
   related_objects(List[str]，对既存本体对象类型的引用)/ontology_id/version_id。
   `BusinessService.list_indicators(ontology_id, version_id)`（`services/business_service.py:90`）
   提供读取。但 semantic_admin 全包**零 import** `biz.management.business`，指标抽不成候选。

约束事实（调查核实）：
- USL 6 类合法语义类型 `VALID_SEMANTIC_TYPES = {对象类型, 关系类型, 属性, 动作类型, 过程类型, 规则类型}`
  （`candidate_store/storage/sqlite_candidate_storage.py:132-134`），**没有「指标类型」**，
  尽管 `ontology_api` 存在 `indicator_type_definitions` 表。
- `_extract_with_llm`（`design/services/pipeline_service.py:502-608`）只 `return entities, relations, events`
  ——**actions 不返回**；`hub._extract` 因此硬编码 `actions=[]`。事件源没有动作抽取产物。
- C1-C4 import-linter 契约（`apps/api/pyproject.toml:109-270`）**不禁止** `biz.semantic_admin →
  biz.management` 跨域（C3 只禁 ontology 内部实现须走 public 门面；C4 只禁 infra→biz）。
  资产流水线现已直接 import `biz.data.ingest.unified_ingest_facade`，故新增对
  `biz.management.business` **服务层**的 import 不触契约、不需棘轮。
- 两条链共用同一个 `SQLiteCandidateStorage` / `usl_schema_candidates` 表；候选必填仅
  `run_id`(或 `pipeline_run_id`) + `canonical`。

## Decision

### 0. 宿主：资产流水线，不是 ol_pipeline

ol_pipeline 的 `run_pipeline`（`ol_pipeline/services/pipeline_service.py:216-227`）是
**text-only + L1~L6 LLM 层**（L1 `LlmTermExtractor` 吃 text/extra_docs），喂确定性结构化数据不合适。
资产流水线 `SemanticAssetPipeline.run`（`semantic_asset_pipeline/services/pipeline_service.py:357`）
已有 source_type 分派、`_collect_*` 候选收集、共用 candidate_store，是这两类入口的自然宿主。
事件源本就在 `STRUCTURED_SOURCE_TYPES`（修复收集即可）；BI 指标新增一个 source_type。

### 1. 事件源路径：捕获 PerceptionHub 已有抽取结果（不重复抽取、不落 OntologyDocument）

**数据流**：`run(source_type=webhook)` → `_run_structured` → `facade.ingest()` →
`PerceptionHub.process_event`（真实 LLM 抽取）→ **门面返回体带上 ExtractionResult** →
新 `_collect_event_candidates` 映射成候选 → `bulk_insert_candidates`。

**接口变更**：`unified_ingest_facade._ingest_event` 返回体从 `{event_id, extraction_confidence}`
增加 `extraction: {entities, relations, events, actions}`（4 个 list，原样透传 PerceptionHub
已抽出的结果）。这是**唯一**对感知链路的改动——不改 `process_event` 内部、不改 PerceptionHub 契约。

**映射**（复用现有结构化收集器的语义类型映射，但读 dict 而非 dataclass）：

| ExtractionResult | USL 候选 | 备注 |
|---|---|---|
| `entities[].name` | 对象类型 | canonical=name；entity_type/entity_id 进 provenance |
| `entities[].basic_properties / statistical_properties` 每个键 | 属性 | `provenance.attribute_of`=实体名，`provenance.property_group`=组名 |
| `relations[].relation_type` | 关系类型 | source_text=`{source_entity} --[{relation_type}]--> {target_entity}` |
| `events[].event_type` | 过程类型 | definition=description；event_id/participants/location 进 provenance |
| `actions[].action_type` | 动作类型 | **感知路径 actions 恒为 []**，故实际不产动作候选——如实记录，不伪造 |

- **`capabilities` / `constraints` 不产属性候选**：与既有 `_collect_structured_candidates`
  （`pipeline_service.py:861-875` 只遍历 basic_properties/statistical_properties；
  `:930-931` 明确「constraints 不入候选，硬塞进某一类等于猜测性归类，规则 14 #4」）保持一致。
  事件源路径读 dict 而非 dataclass，但语义类型映射规则**必须与结构化路径逐条对齐**，否则两条链
  对同一实体产出不同候选集，审核端会看到重复/矛盾。

- `origin="llm"`、`confidence=ExtractionResult.confidence`（hub 给 0.8）——区别于结构化逐字事实的
  `origin="structured"`/`confidence=1.0`，因为事件源是 LLM 推断而非确定性读取。
- `domain_id=_resolve_domain_code(ontology_id)`（复用 ADR-079 §7 / Task #18 的断链 2 成果）。
- `provenance` 带 `event_id`、`source_type`、`source_kind="event"` 及各项 id。

### 2. BI 指标路径：指标 → 属性（确定性读取，非 LLM）

**数据流**：`run(source_type="business_indicators", payload={ontology_id, version_id?})` →
`run()` 新分支 `_run_indicator` → `BusinessService().list_indicators(ontology_id, version_id)`
读 business.db → 新 `_collect_indicator_candidates` → `bulk_insert_candidates`。

**映射**（指标 → 属性，用户 2026-09-25 裁决）：

| 候选字段 | 取值 |
|---|---|
| `canonical` | `display_name or name` |
| `semantic_type` | `"属性"` |
| `definition` | `description or llm_description` |
| `provenance.attribute_of` | `related_objects[0] if related_objects else ""`（标注度量的是哪个对象；related_objects 全量进 provenance）。**空列表时 attribute_of="" 而非取 [0]**——否则 IndexError 被外层 except 吞成「指标恒抽不到」的幻影失败（规则 14）；空归属如实留空，交审核端判定 |
| `provenance` | `{source:"business_indicators", indicator_id, indicator_type, calculation_formula, unit, related_objects, related_processes, related_rules, ontology_id, version_id}` |
| `confidence` | `1.0`（确定性读取）|
| `origin` | `"structured"` |
| `domain_id` | `_resolve_domain_code(ontology_id)` |

- **不产** related_objects/related_processes/related_rules 的独立候选——它们已是既存本体类型，
  重复产候选会造成循环/重复（用户已确认）。
- 跨域 import 走 `BusinessService`（**服务层**），不直接戳 `BusinessStorage`（尊重 management 模块自身分层）。
- **必须给 ontology_id**：缺失则显式 error（否则指标无领域归属、跨本体混读）。

### 3. run() 分派扩展

```
run(source_type):
  source_type in UNSTRUCTURED_SOURCE_TYPES   → _run_unstructured   (text → ExtractService，现状不变)
  source_type in INDICATOR_SOURCE_TYPES      → _run_indicator      (新增：读 business.db)
  source_type in STRUCTURED_SOURCE_TYPES     → _run_structured     (内部再分 event / document)
  else                                        → 显式 error
```

`_run_structured` 内部按 source_type 分：`EVENT_SOURCE_TYPES = frozenset({"webhook","mcp","file","api"})`
（= `SourceCategory.EVENT_DRIVEN` 去掉 sensor，理由见 §5）→ `_collect_event_candidates(ingest_result, ...)`；
其余文档驱动源 → 现有 `_resolve_ingest_documents` + `_collect_structured_candidates`（不变）。

新常量：`EVENT_SOURCE_TYPES`、`INDICATOR_SOURCE_TYPES = frozenset({"business_indicators"})`。

### 4. 错误处理（AGENTS.md 规则 14 对齐）

- 事件源：`ingest_result` 缺 `extraction` 键 → 显式 error（链路断，非静默 0 候选）；
  `extraction` 各 list 为空 → status=ok + warning「事件抽取无实体/关系/事件」
  （区分「真没抽到」vs「抽取没发生」）。
- BI 指标：缺 ontology_id → 显式 error；`list_indicators` 读失败 → 显式 error + warning（≥ warning 级）。
- 落库失败 → 沿用现有显式 error（`bulk_insert_candidates` 异常上抛，不报假成功）。
- 全程禁 `hasattr`/`getattr(x, name, default)` 探测式降级、禁静默兜底、禁猜测性反推。

### 5. 范围边界（用户 2026-09-25 确认）

- **sensor 暂不纳入**：门面对 sensor 只入队（`SensorObserver._queue`）、不同步处理、返回体连
  event_id 都没有（`unified_ingest_facade.py:263-274`）。强行同步化要改感知子系统异步契约，
  blast radius 大。本次让 sensor 保持现有「显式不可归集」error（已合规），记为后续项
  （`/api/perception/observe` 轮询处理时再产候选）。
- **warehouse schema（`datasets.schema_json`）、本体类型定义（ontology_api 7 张 *_definitions 表）暂缓**：
  本次不做。但「读既有库 → 确定性映射候选」模式（§2）可复用，后续按同模式加 source_type 即可。
- **摄入面板 `/api/ingest/unified` 的事件路径仍只做感知**（Graphiti episode），不产候选——
  语义策展统一走 semantic-assets 流水线。这是职责边界，不改。

### 6. 前端

semantic-assets 流水线 UI 增「业务指标」源选项 + payload 表单（ontology_id/version_id）；
`/options` 端点增 `business_indicators` 源。事件源已在可选列表，后端修复后即生效。
`PipelineRunResponse` 复用现有 `collection_stats`/`collection_warnings` 承载新路径统计。

## 后果（Consequences）

**变得更容易**：
- 事件源（webhook/mcp/file/api）的 LLM 抽取产物不再被丢弃，能进审核队列——需求 (a) 对事件形态闭合。
- BI 指标成为可审核的 USL 属性候选——需求 (a) 对指标形态闭合，且复用断链 2 的 domain_id 归属。
- 「读既有库 → 确定性映射候选」模式为后续 warehouse schema / 本体类型定义入口铺好路。

**变得更难 / 新增债**：
- 门面 `_ingest_event` 返回体变宽（多 4 个 list），消费者需感知；但仅资产流水线消费，影响面可控。
- semantic_admin 新增对 `biz.management.business` 的跨域依赖（服务层）——当前契约放行，
  但若未来引入「biz 域间独立」契约，此边需走门面或 provider 倒置（参照 ADR-081 机制）。
- 事件源候选 confidence=0.8（LLM 推断），质量闸分档会低于结构化源的 1.0，审核负担略增。

## 可逆性（Reversibility）

**中**。逆转方式：
- 事件源：还原 `_ingest_event` 返回体（去掉 extraction），删 `_collect_event_candidates` 与
  `_run_structured` 的 event 分支——事件源回到「显式不可归集」error（现状），无数据残留。
- BI 指标：从 `INDICATOR_SOURCE_TYPES`/`run()` 分派移除 `business_indicators`，删
  `_run_indicator`/`_collect_indicator_candidates`——已产候选是普通 usl_schema_candidates 行，
  可按 run_id 批量清理。
- 两者都不改存储 schema、不改 USL 6 类枚举、不改 ol_pipeline，故逆转不触碰冻结契约（ADR-079）。

## 落地验证（实现时必填）

- [ ] `_collect_event_candidates` 单测：真实 ExtractionResult 形状 dict → 4 类映射；actions 空不产动作候选；domain_id 透传；回读真库（规则 14 #6 走真实函数体）。
- [ ] `_collect_indicator_candidates` 单测：tmp_path 真 business.db 造 indicator → 属性候选；attribute_of；provenance 带 formula/unit；不产 related_objects 候选；domain_id。
- [ ] 门面 `_ingest_event` 单测：mock PerceptionHub.process_event 返回带 extraction 的 PerceptionOutput，断言 facade 返回体含 extraction。
- [ ] `run()` 分派单测：indicator/event source_type 各走对应路径。
- [ ] 源码级回归闸：沿用 `TestNoProbeDegradationInSource` 模式禁探测式降级。
- [ ] `cd apps/api && uv run lint-imports` 仍 `kept/broken` 不新增违规（跨域 import 合规复核）。
- [ ] 离线全量单测无新增回归（对照 Task #11 基线）。
- [ ] 文档同步（规则 12）：本 ADR 登记进 `docs/07-adr/README.md` 索引 + 时间线 + 状态清算记录；`DOC_SYNC_CHECKLIST.md`；semantic_admin DESIGN.md 补两条新入口。
