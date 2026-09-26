# 事件源与 BI 指标语义抽取入口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让语义资产 Pipeline 能从事件源（webhook/mcp/file/api）和 BI 业务指标中归集出待审业务语义候选，补齐「结构化数据引入」之外的两个能力缺口入口。

**Architecture:** 事件源复用 PerceptionHub 已有的 `ExtractionResult`（不重复抽取、不落 OntologyDocument），由 `UnifiedIngestFacade._ingest_event` 把抽取结果透传上来，`SemanticAssetPipeline._collect_event_candidates` 归集为候选；BI 指标新增 `business_indicators` 源类型，由 `_run_indicator → BusinessService.list_indicators → _collect_indicator_candidates` 把每条指标映射为「属性」候选。两条新链路都汇入既有 Candidate Store 与审核工作流，不新增存储表。

**Tech Stack:** Python 3.10+ · FastAPI · Pydantic v2 · SQLite（每操作 connect/close）· pytest（离线）· import-linter（C1-C4 契约）· React 19 / TypeScript / Ant Design 6（前端向导）。

**Spec:** `docs/07-adr/ADR-082_事件源与BI指标语义抽取入口.md`（本计划逐条实现该 ADR 的 §1-§6；执行前须同时阅读该 ADR）。

## Global Constraints

以下为项目级硬约束，**每个任务的要求都隐含包含本节**（值逐字取自 AGENTS.md 与 ADR-082）：

- **AGENTS.md 规则 14（禁止未经确认和评审的兜底逻辑）**：禁止 `except Exception: pass`、静默默认回退、静默切换服务、静默返回空结果、`hasattr` 探测式降级、幻影调用、无视被调方返回的错误状态。要求：失败必须显式（返回 `{"status":"error","message":...}` 或抛出）；兜底需可观测（日志 ≥ `warning`）；禁止猜测性反推（缺失数据显式建模，不按命名约定补全）；**测试必须执行真实函数体**（至少一条测试走真实实现，不得 `patch` 掉被测函数本身）。
- **规则 2**：服务层返回 `Dict[str, Any]`，错误格式 `{"status":"error","message":"..."}`；不在服务层抛 `HTTPException`。
- **规则 6**：调用链 `routes.py → services/ → impl/ → storage/`，禁止跨层。本计划新增的跨域导入 `biz.semantic_admin → biz.management.business.services.business_service`（服务层，非 storage）已确认不违反 import-linter C1-C4（C3 `forbidden_modules` 只列 ontology 内部子包）。
- **规则 8**：SQLite 每次操作 `connect()` → `close()`，无连接池（本计划不新增存储层，复用既有 `SQLiteCandidateStorage` / `BusinessStorage`）。
- **规则 9**：新增方法必须有对应测试；存储层测试用 `tmp_path` 真库，禁止 MagicMock 模拟数据库。
- **规则 12**：代码变更同步文档。Task 7 在 `docs/03-modules/semantic_admin/DESIGN.md` 增补「事件源候选归集」「BI 指标候选归集」两条能力记录。
- **规则 13**：临时文件写 `apps/api/data/`，禁止写项目根；测试一律用 `tmp_path` 注入库路径。
- **USL 6 类合法语义类型**：`对象类型 / 关系类型 / 属性 / 动作类型 / 过程类型 / 规则类型`（**无「指标类型」**）。BI 指标映射为「属性」。
- **ADR-079 §7**：候选表列名是 `domain_id`，但承载的是 `domain_code` 值；`_resolve_domain_code(ontology_id)` 解析不到返回空串，**不猜测性反推**。
- **离线 pytest 调用（强制，否则挂起）**：所有 pytest 命令从仓库根 `E:\DEMO\AI\ontology-graphiti` 执行，前缀环境变量：
  `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest <target> -q --no-header -p no:cacheprovider`
- **Git 提交（附录 F）**：`<type>(<scope>): <subject>`；**只按文件名 `git add` 指定文件**，禁止 `git add -A`（工作区有约 84 个与本计划无关的已改文件，不得卷入提交）。
- **明确不在本计划范围（保持范围外，勿折叠进来）**：
  1. 翻转 `INGEST_AUTO_PIPELINE_DEFAULT` 为 `true`（断链 1，属未经评审的行为变更，规则 14 #1，须单独经用户确认）。
  2. `sensor` 事件源（ADR-082 §5 明确延后，保持其现有显式行为，不纳入 `EVENT_SOURCE_TYPES`）。
  3. 数据仓库 schema / 本体类型定义的自动抽取（ADR-082 §5 延后）。

---

## File Structure

| 文件 | 责任 | 本计划改动 |
|------|------|-----------|
| `apps/api/odap/biz/data/ingest/unified_ingest_facade.py` | 统一摄入门面，按源类型路由 | Task 1：`_ingest_event` 透传 `extraction` + 传播 `FAILED` 状态 |
| `apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py` | 语义资产统一编排服务 | Task 2：`EVENT_SOURCE_TYPES` 常量 + `_collect_event_candidates`；Task 3：`_run_structured` 事件/文档分流；Task 4：`INDICATOR_SOURCE_TYPES` 常量 + `business_service` 属性 + `_collect_indicator_candidates`；Task 5：`_run_indicator` + `run()` 分派 + `source_kind` 标签；Task 6：`options()` 暴露 indicator 源 |
| `apps/api/tests/unit/test_unified_ingest_facade.py` | 门面单测 | Task 1：新增事件透传/FAILED 传播测试类 |
| `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py` | 结构化链路回归测试 | Task 2-6：新增事件归集/指标归集/分派/options 测试类；Task 2 扩充无探测回归闸 |
| `apps/api/odap/biz/management/business/services/business_service.py` | 业务资产服务（既有，只读复用） | 无改动（Task 4 只导入 `list_indicators`） |
| `docs/03-modules/semantic_admin/DESIGN.md` | 语义管理台模块设计 | Task 7：增补两条能力记录 |
| `apps/web/src/modules/semantic-admin/services/assetPipelineApi.ts` | 前端 API 类型 | Task 8：`AssetSourceTypes` 增 `indicator?` |
| `apps/web/src/modules/semantic-admin/pages/SemanticAssetPipelinePage.tsx` | 前端向导页 | Task 8：第三数据源 Select + indicator payload 分支 + version_id 输入 |

---

## Task 1: 门面 `_ingest_event` 透传抽取结果 + 传播 FAILED 状态

**Files:**
- Modify: `apps/api/odap/biz/data/ingest/unified_ingest_facade.py:233-299`（`_ingest_event`）
- Test: `apps/api/tests/unit/test_unified_ingest_facade.py`（文件末尾新增测试类）

**Interfaces:**
- Consumes: `PerceptionHub.process_event(event, ontology_id=None) -> PerceptionOutput`；`PerceptionOutput(event_id:str, extraction:ExtractionResult, status:PerceptionStatus, error:Optional[str])`；`ExtractionResult(entities/relations/events/actions: List[Dict], confidence: float)`；`PerceptionStatus.FAILED / .STORED`（均在 `odap.biz.data.perception.schemas`）。
- Produces: `_ingest_event` 成功返回体新增键 `"extraction": dict`（= `ExtractionResult.model_dump()`，含 `entities/relations/events/actions/confidence`）；`output.status == FAILED` 时返回 `{"status":"error", ..., "message": "事件感知处理失败: <error>"}`。Task 2/3 依赖 `ingest_result["extraction"]` 这一契约。

- [ ] **Step 1: 写失败测试（透传 extraction）**

在 `apps/api/tests/unit/test_unified_ingest_facade.py` 文件末尾追加：

```python
class TestEventIngestExtractionPassthrough:
    """规则 14：门面必须把 PerceptionHub 的抽取结果透传上来，且不得无视 FAILED。

    用真实 PerceptionOutput / ExtractionResult（非 MagicMock）驱动，确保
    `output.status == PerceptionStatus.FAILED` 判定与 `extraction.model_dump()`
    走真实对象路径（规则 14 要求 6：测试执行真实函数体）。
    """

    @pytest.mark.asyncio
    async def test_ingest_event_returns_extraction_payload(self, facade):
        from odap.biz.data.perception.schemas import (
            PerceptionOutput, PerceptionStatus, ExtractionResult,
        )

        real_output = PerceptionOutput(
            event_id="evt-001",
            extraction=ExtractionResult(
                entities=[{"entity_id": "e1", "entity_type": "Unit", "name": "红方装甲营"}],
                relations=[{"relation_id": "r1", "relation_type": "隶属于",
                            "source_entity": "红方装甲营", "target_entity": "红方第1师"}],
                events=[{"event_id": "ev1", "event_type": "装甲推进"}],
                actions=[],
                confidence=0.8,
            ),
            status=PerceptionStatus.STORED,
        )
        mock_hub = AsyncMock()
        mock_hub.process_event = AsyncMock(return_value=real_output)
        mock_hub.ingest_webhook = MagicMock(return_value="evt-001")
        facade._perception_hub = mock_hub

        result = await facade.ingest("webhook", payload={"key": "value"})

        assert result["status"] == "ok", result
        assert result["routed_to"] == "PerceptionHub"
        ext = result["extraction"]
        assert ext["confidence"] == 0.8
        assert ext["entities"][0]["name"] == "红方装甲营"
        assert ext["relations"][0]["relation_type"] == "隶属于"
        assert ext["events"][0]["event_type"] == "装甲推进"
        assert ext["actions"] == []

    @pytest.mark.asyncio
    async def test_ingest_event_propagates_failed_status(self, facade):
        from odap.biz.data.perception.schemas import (
            PerceptionOutput, PerceptionStatus, ExtractionResult,
        )

        failed = PerceptionOutput(
            event_id="evt-002",
            extraction=ExtractionResult(),
            status=PerceptionStatus.FAILED,
            error="LLM 抽取超时",
        )
        mock_hub = AsyncMock()
        mock_hub.process_event = AsyncMock(return_value=failed)
        mock_hub.ingest_webhook = MagicMock(return_value="evt-002")
        facade._perception_hub = mock_hub

        result = await facade.ingest("webhook", payload={"key": "value"})

        assert result["status"] == "error", result
        assert "LLM 抽取超时" in result["message"]
        assert result["event_id"] == "evt-002"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_unified_ingest_facade.py::TestEventIngestExtractionPassthrough -q --no-header -p no:cacheprovider`
Expected: FAIL —— `test_ingest_event_returns_extraction_payload` 报 `KeyError: 'extraction'`（当前返回体无此键）；`test_ingest_event_propagates_failed_status` 报 `assert 'ok' == 'error'`（当前无视 FAILED 照报成功）。

- [ ] **Step 3: 改 `_ingest_event` 实现**

在 `apps/api/odap/biz/data/ingest/unified_ingest_facade.py` 的 `_ingest_event` 内，把 schemas 导入行（当前 236-238）改为同时导入 `PerceptionStatus`：

```python
            from odap.biz.data.perception.schemas import (
                PerceptionEvent, PerceptionSourceType, PerceptionStatus,
            )
```

把 `output = await self.perception_hub.process_event(...)` 之后、`return {...}` 之前（当前 286-296）替换为：

```python
            output = await self.perception_hub.process_event(
                event, ontology_id=kwargs.get("ontology_id")
            )

            # 规则 14：不得无视被调方错误状态。process_event 内部异常会返回
            # status=FAILED + error 字段（而非抛出），此前门面照报 status=ok，
            # 把"感知抽取链路坏了"伪装成"这段文本没有可抽取内容"。
            if output.status == PerceptionStatus.FAILED:
                logger.error(
                    "UnifiedIngestFacade event perception failed (%s, event_id=%s): %s",
                    source_type, output.event_id, output.error,
                )
                return {
                    "status": "error",
                    "source_type": source_type,
                    "event_id": output.event_id,
                    "routed_to": "PerceptionHub",
                    "message": f"事件感知处理失败: {output.error}",
                }

            return {
                "status": "ok",
                "source_type": source_type,
                "event_id": output.event_id,
                "routed_to": "PerceptionHub",
                "extraction_confidence": output.extraction.confidence,
                # 透传 PerceptionHub 已产出的抽取结果，供上游归集业务语义候选，
                # 避免为拿实体清单而重复抽取一次（ADR-082 §1）。
                "extraction": output.extraction.model_dump(),
            }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_unified_ingest_facade.py -q --no-header -p no:cacheprovider`
Expected: PASS（新类 2 条通过；既有 `test_ingest_webhook_routes_to_event` 等不回归——它用 `MagicMock()` 作 output，`MagicMock().status != PerceptionStatus.FAILED` 故不进 error 分支，且它不断言 `extraction`）。

- [ ] **Step 5: 提交**

```bash
git add apps/api/odap/biz/data/ingest/unified_ingest_facade.py apps/api/tests/unit/test_unified_ingest_facade.py
git commit -m "$(cat <<'EOF'
feat(ingest): 事件门面透传抽取结果并传播感知 FAILED 状态

- _ingest_event 成功返回体新增 extraction（ExtractionResult.model_dump）
- output.status==FAILED 时显式返回 error，修规则14「无视被调方错误状态」
EOF
)"
```

---

## Task 2: `EVENT_SOURCE_TYPES` 常量 + `_collect_event_candidates`

**Files:**
- Modify: `apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py:37`（常量区后追加）、`:963`（`_collect_structured_candidates` 之后追加新方法）
- Test: `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py`（新增测试类 + 扩充无探测回归闸）

**Interfaces:**
- Consumes: `ingest_result["extraction"]`（Task 1 产出的 dict，键 `entities/relations/events/actions/confidence`）；实体 dict 键 `entity_id/entity_type/name/basic_properties/statistical_properties`（权威 schema 见 `design/services/pipeline_service.py:557-578` 的 LLM 抽取契约）；关系 dict 键 `relation_id/relation_type/source_entity/target_entity`；事件 dict 键 `event_id/event_type/location/description/participants`；动作 dict 键 `action_id/action_type/actor/target/opa_required`（**perception 恒返回 `actions=[]`**，见 `hub.py:204`）。`self.candidate_storage.bulk_insert_candidates(records)`（落库失败抛异常）。
- Produces: 模块级 `EVENT_SOURCE_TYPES = frozenset({"webhook","mcp","file","api"})`（Task 3 用）；方法 `_collect_event_candidates(self, ingest_result, *, run_id, ontology_id, source_kind="event", domain_code="") -> Dict[str,Any]`，成功返回 `{"status":"ok","records":[...],"stats":{...},"warnings":[...]}`，失败返回 `{"status":"error","message":"..."}`。候选记录字段与 `_collect_structured_candidates` 对齐，但 `origin="llm"`、`confidence=` 抽取置信度（0.8）。

- [ ] **Step 1: 写失败测试（事件归集映射 + 落库 + 缺 extraction 报错 + 空抽取告警）**

在 `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py` 文件末尾追加：

```python
# ──────────────────────────────────────────────────────────────────────
# 9. 事件源候选归集（ADR-082 §1）
# ──────────────────────────────────────────────────────────────────────
def _extraction(**overrides):
    """构造门面透传的 extraction dict（键对齐 LLM 抽取契约）。"""
    base: Dict[str, Any] = {
        "entities": [{
            "entity_id": "e1", "entity_type": "Unit", "name": "红方装甲营",
            "basic_properties": {"description": "红方主力装甲部队", "side": "Red"},
            "statistical_properties": {"personnel": 420},
        }],
        "relations": [{
            "relation_id": "r1", "relation_type": "隶属于",
            "source_entity": "红方装甲营", "target_entity": "红方第1师",
        }],
        "events": [{
            "event_id": "ev1", "event_type": "装甲推进",
            "description": "红方装甲营向蓝方阵地推进",
            "participants": ["红方装甲营", "蓝方守备连"], "location": "北线",
        }],
        "actions": [],
        "confidence": 0.8,
    }
    base.update(overrides)
    return base


class TestEventCandidateCollection:
    def test_event_extraction_maps_to_usl_semantic_types(self, pipeline):
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-1", "extraction": _extraction()},
            run_id="run-ev", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "ok", out
        grouped = _by_type(out["records"])
        assert grouped["对象类型"][0]["canonical"] == "红方装甲营"
        assert grouped["关系类型"][0]["canonical"] == "隶属于"
        assert grouped["过程类型"][0]["canonical"] == "装甲推进"
        # 事件源是 LLM 推断，置信度取抽取置信度、origin=llm（区别于结构化的 1.0/structured）
        obj = grouped["对象类型"][0]
        assert obj["origin"] == "llm"
        assert obj["confidence"] == 0.8
        assert obj["definition"] == "红方主力装甲部队"
        assert obj["provenance"]["event_id"] == "evt-1"
        assert obj["provenance"]["entity_type"] == "Unit"
        # 属性槽位（basic/statistical）归为「属性」，capabilities/constraints 不入候选
        attrs = {a["canonical"] for a in grouped["属性"]}
        assert {"description", "side", "personnel"} <= attrs
        assert grouped["关系类型"][0]["source_text"] == (
            "红方装甲营 --[隶属于]--> 红方第1师"
        )
        assert grouped["过程类型"][0]["provenance"]["participants"] == [
            "红方装甲营", "蓝方守备连",
        ]

    def test_actions_empty_produces_no_action_candidates(self, pipeline):
        """perception 恒返回 actions=[]，必须如实产出 0 条动作候选，不得捏造。"""
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-2", "extraction": _extraction()},
            run_id="run-ev2", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "ok"
        assert "动作类型" not in _by_type(out["records"])

    def test_event_candidates_are_persisted(self, pipeline):
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-3", "extraction": _extraction()},
            run_id="run-ev3", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "ok"
        assert len(_persisted(pipeline, "run-ev3")) == len(out["records"]) > 0

    def test_missing_extraction_key_is_explicit_error(self, pipeline):
        """门面若没透传 extraction（契约破裂），必须显式报错而非静默 0 候选。"""
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-4"},
            run_id="run-ev4", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "error", out
        assert "extraction" in out["message"]

    def test_empty_extraction_is_ok_with_warning(self, pipeline):
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-5",
             "extraction": _extraction(entities=[], relations=[], events=[])},
            run_id="run-ev5", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "ok", out
        assert out["records"] == []
        assert out["warnings"], "空抽取应给出告警而非静默成功"

    def test_persistence_failure_is_error_not_false_ok(self, pipeline, monkeypatch):
        def _boom(_records):
            raise RuntimeError("disk full")

        monkeypatch.setattr(
            pipeline.candidate_storage, "bulk_insert_candidates", _boom, raising=True,
        )
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-6", "extraction": _extraction()},
            run_id="run-ev6", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "error", out
        assert "disk full" in out["message"]
        assert _persisted(pipeline, "run-ev6") == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py::TestEventCandidateCollection -q --no-header -p no:cacheprovider`
Expected: FAIL —— `AttributeError: 'SemanticAssetPipeline' object has no attribute '_collect_event_candidates'`。

- [ ] **Step 3: 加 `EVENT_SOURCE_TYPES` 常量**

在 `pipeline_service.py` 的 `UNSTRUCTURED_SOURCE_TYPES` 定义之后（当前 37 行后）追加：

```python
# 事件驱动源（走 UnifiedIngestFacade → PerceptionHub，复用其 ExtractionResult）。
# = SourceCategory.EVENT_DRIVEN 去掉 sensor（ADR-082 §5：sensor 延后，保持其现有
# 显式行为，不纳入事件候选归集）。这些类型仍是 STRUCTURED_SOURCE_TYPES 的子集，
# 路由走 _run_structured，但候选归集分流到 _collect_event_candidates（Task 3）。
EVENT_SOURCE_TYPES = frozenset({"webhook", "mcp", "file", "api"})
```

- [ ] **Step 4: 加 `_collect_event_candidates` 方法**

在 `pipeline_service.py` 的 `_collect_structured_candidates` 方法之后（当前 963 行 `return {...}` 块之后、`_singleton` 之前）追加：

```python
    def _collect_event_candidates(
        self,
        ingest_result: Dict[str, Any],
        *,
        run_id: str,
        ontology_id: Optional[str],
        source_kind: str = "event",
        domain_code: str = "",
    ) -> Dict[str, Any]:
        """把事件源（webhook/mcp/file/api）的 PerceptionHub 抽取结果归集为待审候选。

        事件通道不生成 OntologyDocument，抽取产物是 UnifiedIngestFacade 透传上来的
        `ingest_result["extraction"]`（= ExtractionResult.model_dump()，ADR-082 §1）。
        实体/关系/事件是 LLM 推断（非逐字事实），故 origin="llm"、confidence 取抽取
        置信度，与结构化链路的 1.0/structured 区分。

        Returns:
            {"status": "ok", "records": [...], "stats": {...}, "warnings": [...]}
            或 {"status": "error", "message": "..."}
        """
        if "extraction" not in ingest_result:
            # 契约破裂必须显式失败（规则 14）：门面承诺透传 extraction，缺键说明
            # 上游没兑现，不能静默当成"这段事件没有可抽取内容"。
            return {
                "status": "error",
                "message": (
                    "事件引入结果缺少 extraction 键，无法归集业务语义候选；"
                    f"实际返回键={sorted(ingest_result.keys())}"
                ),
            }

        extraction = ingest_result.get("extraction") or {}
        confidence = float(extraction.get("confidence") or 0.0)
        event_id = ingest_result.get("event_id") or ""
        base_prov = {
            "source_kind": source_kind,
            "ontology_id": ontology_id,
            "event_id": event_id,
            "source_type": ingest_result.get("source_type", ""),
        }

        merged: Dict[tuple, Dict[str, Any]] = {}
        stats: Dict[str, int] = {}

        def _add(
            *, semantic_type: str, canonical: str,
            definition: str = "", en: str = "",
            synonyms: Optional[List[str]] = None, source_text: str = "",
            extra_prov: Optional[Dict[str, Any]] = None,
        ) -> None:
            name = str(canonical or "").strip()
            if not name:
                return
            stats[semantic_type] = stats.get(semantic_type, 0) + 1
            key = (semantic_type, name)
            hit = merged.get(key)
            if hit is None:
                prov = dict(base_prov)
                if extra_prov:
                    prov.update(extra_prov)
                merged[key] = {
                    "run_id": run_id,
                    "domain_id": domain_code,
                    "canonical": name,
                    "en": en,
                    "semantic_type": semantic_type,
                    "definition": definition,
                    "synonyms": list(dict.fromkeys(synonyms or [])),
                    "confidence": confidence,
                    "origin": "llm",
                    "source_text": source_text,
                    "provenance": prov,
                }
                return
            if not hit["definition"] and definition:
                hit["definition"] = definition
            if not hit["en"] and en:
                hit["en"] = en
            for s in synonyms or []:
                if s and s not in hit["synonyms"]:
                    hit["synonyms"].append(s)

        for e in extraction.get("entities") or []:
            if not isinstance(e, dict):
                continue
            basic = e.get("basic_properties") or {}
            _add(
                semantic_type="对象类型",
                canonical=e.get("name", ""),
                definition=str(basic.get("description") or ""),
                extra_prov={
                    "entity_id": e.get("entity_id", ""),
                    "entity_type": e.get("entity_type", ""),
                },
            )
            # 仅 basic_properties / statistical_properties 的键归为「属性」；
            # capabilities / constraints 不入候选——USL 6 类无对应项，硬塞等于
            # 猜测性归类（规则 14 #4），与 _collect_structured_candidates 一致。
            for group, mapping in (
                ("basic_properties", basic),
                ("statistical_properties", e.get("statistical_properties") or {}),
            ):
                if not isinstance(mapping, dict):
                    continue
                for prop_name in mapping:
                    _add(
                        semantic_type="属性",
                        canonical=str(prop_name),
                        extra_prov={
                            "attribute_of": e.get("name", ""),
                            "property_group": group,
                        },
                    )

        for r in extraction.get("relations") or []:
            if not isinstance(r, dict):
                continue
            _add(
                semantic_type="关系类型",
                canonical=r.get("relation_type", ""),
                source_text=(
                    f"{r.get('source_entity', '')} --[{r.get('relation_type', '')}]--> "
                    f"{r.get('target_entity', '')}"
                ),
                extra_prov={
                    "relation_id": r.get("relation_id", ""),
                    "sample_source": r.get("source_entity", ""),
                    "sample_target": r.get("target_entity", ""),
                },
            )

        for ev in extraction.get("events") or []:
            if not isinstance(ev, dict):
                continue
            _add(
                semantic_type="过程类型",
                canonical=ev.get("event_type", ""),
                definition=str(ev.get("description") or ""),
                extra_prov={
                    "event_id": ev.get("event_id", ""),
                    "participants": list(ev.get("participants") or []),
                    "location": ev.get("location", ""),
                },
            )

        # perception 当前恒返回 actions=[]（hub.py:204）；如实遍历，空则 0 条动作候选，
        # 不捏造动作（规则 14 #4）。将来若开始产出动作，此循环自动生效。
        for a in extraction.get("actions") or []:
            if not isinstance(a, dict):
                continue
            _add(
                semantic_type="动作类型",
                canonical=a.get("action_type", ""),
                source_text=(
                    f"{a.get('actor', '')} 执行 {a.get('action_type', '')} → "
                    f"{a.get('target', '')}"
                ),
                extra_prov={
                    "action_id": a.get("action_id", ""),
                    "sample_actor": a.get("actor", ""),
                    "sample_target": a.get("target", ""),
                    "opa_required": bool(a.get("opa_required")),
                },
            )

        records = list(merged.values())
        warnings: List[str] = []
        if not records:
            warnings.append(
                "事件抽取无实体/关系/事件，未归集到业务语义候选"
                "（请检查事件原文是否含可抽取内容）"
            )

        if records:
            try:
                self.candidate_storage.bulk_insert_candidates(records)
            except Exception as e:
                logger.error("事件候选归集落库失败: %s", e)
                return {
                    "status": "error",
                    "message": f"事件候选落库失败（{len(records)} 条未持久化）: {e}",
                }

        return {
            "status": "ok",
            "records": records,
            "stats": {
                "event_id": event_id,
                "raw_items": sum(stats.values()),
                "deduped_candidates": len(records),
                "by_semantic_type": dict(stats),
            },
            "warnings": warnings,
        }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py::TestEventCandidateCollection -q --no-header -p no:cacheprovider`
Expected: PASS（6 条全过）。

- [ ] **Step 6: 扩充无探测回归闸（确认新方法未引入 hasattr/默认 getattr 探测）**

`TestNoProbeDegradationInSource`（当前 974 行起）已用 AST 解析整个 `pipeline_service.py` 禁止 `hasattr(...)` 与带默认值的 `getattr(..., default)`。`_collect_event_candidates` 全程用 `dict.get(key)`（单参，非 `getattr`）与 `isinstance` 判定，不含被禁模式。运行该回归闸确认：

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py::TestNoProbeDegradationInSource -q --no-header -p no:cacheprovider`
Expected: PASS（无新增探测式降级）。

- [ ] **Step 7: 提交**

```bash
git add apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py apps/api/tests/unit/test_semantic_asset_pipeline_structured.py
git commit -m "$(cat <<'EOF'
feat(semantic-admin): 事件源抽取结果归集为业务语义候选

- 新增 EVENT_SOURCE_TYPES 与 _collect_event_candidates
- 实体→对象类型+属性、关系→关系类型、事件→过程类型、动作如实遍历
- 缺 extraction 键/落库失败均显式报错，空抽取给告警（ADR-082 §1，规则14）
EOF
)"
```

---

## Task 3: `_run_structured` 事件/文档分流

**Files:**
- Modify: `apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py:513-520`（`_run_structured` 归集调用处）
- Test: `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py`（新增测试类）

**Interfaces:**
- Consumes: `EVENT_SOURCE_TYPES`（Task 2）；`_collect_event_candidates`（Task 2）；`_collect_structured_candidates`（既有）；`_resolve_domain_code`（既有）。
- Produces: `_run_structured` 中，当 `source_type in EVENT_SOURCE_TYPES` 时走 `_collect_event_candidates(..., source_kind="event")`，否则走既有 `_collect_structured_candidates(..., source_kind="structured")`。返回体结构不变（`{status, ingest, candidate_count, candidates, collection_stats, collection_warnings}`）。

- [ ] **Step 1: 写失败测试（事件分支端到端 + 缺 extraction 冒泡）**

在 `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py` 文件末尾追加：

```python
# ──────────────────────────────────────────────────────────────────────
# 10. run() 事件源分流（ADR-082 §1/§3）
# ──────────────────────────────────────────────────────────────────────
class TestRunStructuredEventBranch:
    async def test_webhook_routes_to_event_collector(self, pipeline):
        class _Facade:
            async def ingest(self, source_type, **kwargs):
                return {
                    "status": "ok", "source_type": source_type,
                    "event_id": "evt-run", "routed_to": "PerceptionHub",
                    "extraction": _extraction(),
                }

        pipeline._ingest_facade = _Facade()
        # ontology_id=None 保持 hermetic：_resolve_domain_code 直接返回空串，
        # 不触发 OntologyService 构造（避免连 Neo4j）。
        res = await pipeline.run(
            source_type="webhook", payload={"payload": {"k": "v"}},
            scenario_id="sc-test", workspace_id="ws-test",
        )
        assert res["status"] == "ok", res
        assert res["candidate_count"] == len(res["candidates"]) > 0
        grouped = _by_type(res["candidates"])
        assert grouped["对象类型"][0]["canonical"] == "红方装甲营"
        # 事件候选 origin=llm（区别于结构化 1.0/structured）
        assert grouped["对象类型"][0]["origin"] == "llm"
        assert _persisted(pipeline, res["pipeline_run_id"])

    async def test_event_missing_extraction_bubbles_up(self, pipeline):
        class _Facade:
            async def ingest(self, source_type, **kwargs):
                return {
                    "status": "ok", "source_type": source_type,
                    "event_id": "evt-noext", "routed_to": "PerceptionHub",
                }

        pipeline._ingest_facade = _Facade()
        res = await pipeline.run(
            source_type="webhook", payload={"payload": {}},
            scenario_id="sc-test", workspace_id="ws-test",
        )
        assert res["status"] == "error", res
        assert "未能归集业务语义候选" in res["message"]
        assert res["ingest"]["event_id"] == "evt-noext"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py::TestRunStructuredEventBranch -q --no-header -p no:cacheprovider`
Expected: FAIL —— `test_webhook_routes_to_event_collector` 报 `assert 'error' == 'ok'`（当前 webhook 走 `_collect_structured_candidates`，因无 record_id/document_ids 而报"未能归集"）；`test_event_missing_extraction_bubbles_up` 可能已偶然通过（当前也报错），但第一条必红。

- [ ] **Step 3: 改 `_run_structured` 归集分流**

在 `pipeline_service.py` 的 `_run_structured` 内，把当前的归集调用（513-520 行）：

```python
        # 结构化链路的候选：按 record_id 回捞本体文档后归集
        collected = self._collect_structured_candidates(
            ingest_result,
            run_id=pipeline_run_id,
            ontology_id=ontology_id,
            source_kind="structured",
            domain_code=self._resolve_domain_code(ontology_id),
        )
```

替换为：

```python
        # 事件驱动源（webhook/mcp/file/api）不生成 OntologyDocument，抽取产物由
        # 门面透传在 ingest_result["extraction"]；其余结构化源按 record_id 回捞本体
        # 文档。两条归集路径产出结构一致（records/stats/warnings），下游无需区分。
        if source_type in EVENT_SOURCE_TYPES:
            collected = self._collect_event_candidates(
                ingest_result,
                run_id=pipeline_run_id,
                ontology_id=ontology_id,
                source_kind="event",
                domain_code=self._resolve_domain_code(ontology_id),
            )
        else:
            collected = self._collect_structured_candidates(
                ingest_result,
                run_id=pipeline_run_id,
                ontology_id=ontology_id,
                source_kind="structured",
                domain_code=self._resolve_domain_code(ontology_id),
            )
```

- [ ] **Step 4: 运行测试确认通过（含既有结构化回归）**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py -q --no-header -p no:cacheprovider`
Expected: PASS（新类 2 条通过；`TestRunStructuredPropagatesFailure` 等既有结构化用例不回归——`manual`/`url` 不在 `EVENT_SOURCE_TYPES`，仍走 `_collect_structured_candidates`）。

- [ ] **Step 5: 提交**

```bash
git add apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py apps/api/tests/unit/test_semantic_asset_pipeline_structured.py
git commit -m "$(cat <<'EOF'
feat(semantic-admin): 结构化链路按事件源分流到事件候选归集

- _run_structured 对 EVENT_SOURCE_TYPES 走 _collect_event_candidates
- 其余结构化源保持按 record_id 回捞本体文档（ADR-082 §3）
EOF
)"
```

---

## Task 4: `INDICATOR_SOURCE_TYPES` 常量 + `business_service` 属性 + `_collect_indicator_candidates`

**Files:**
- Modify: `apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py:37`（常量区）、`:55-59`（`__init__`）、`:94`（属性区后）、`:963`（新方法）
- Test: `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py`（新增测试类）

**Interfaces:**
- Consumes: `BusinessService.list_indicators(ontology_id=None, version_id=None) -> List[Dict]`（`odap.biz.management.business.services.business_service`；返回 **list**，非 error-dict）。指标 dict 键（权威 schema 见 `business/storage/sqlite_storage.py:78-99` + `_parse_row:130-140`）：`indicator_id/name/display_name/description/llm_description/related_objects(list)/related_processes(list)/related_rules(list)/indicator_type/calculation_formula/unit/ontology_id/version_id`。`self.candidate_storage.bulk_insert_candidates(records)`。
- Produces: 模块级 `INDICATOR_SOURCE_TYPES = frozenset({"business_indicators"})`（Task 5 用）；`__init__` 新增 `self._business_service = None`；懒加载属性 `business_service`；方法 `_collect_indicator_candidates(self, indicators, *, run_id, ontology_id, domain_code="", version_id="") -> Dict[str,Any]`，成功 `{"status":"ok","records","stats","warnings"}`，落库失败 `{"status":"error","message"}`。每条指标 → 一条「属性」候选：`canonical=display_name or name`、`definition=description or llm_description`、`provenance.attribute_of = related_objects[0] if related_objects else ""`、`confidence=1.0`、`origin="structured"`。**不把 related_objects/processes/rules 另发为独立候选**（避免循环归类）。

- [ ] **Step 1: 写失败测试（指标映射 + 空 related_objects 不崩 + 不另发关联候选 + name 回退 + 空列表告警 + 落库）**

在 `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py` 文件末尾追加：

```python
# ──────────────────────────────────────────────────────────────────────
# 11. BI 指标候选归集（ADR-082 §2）
# ──────────────────────────────────────────────────────────────────────
def _indicator(**overrides):
    base: Dict[str, Any] = {
        "indicator_id": "ind-1",
        "name": "gmv_total",
        "display_name": "成交总额",
        "description": "统计周期内全部成交金额",
        "llm_description": "",
        "related_objects": ["订单"],
        "related_processes": ["下单"],
        "related_rules": ["退款规则"],
        "indicator_type": "metric",
        "calculation_formula": "SUM(order.amount)",
        "unit": "元",
        "ontology_id": "ont-test",
        "version_id": "v1",
    }
    base.update(overrides)
    return base


class TestIndicatorCandidateCollection:
    def test_indicator_maps_to_attribute_candidate(self, pipeline):
        out = pipeline._collect_indicator_candidates(
            [_indicator()], run_id="run-ind", ontology_id="ont-test",
            domain_code="FINANCE", version_id="v1",
        )
        assert out["status"] == "ok", out
        rec = out["records"][0]
        assert rec["semantic_type"] == "属性"
        assert rec["canonical"] == "成交总额"
        assert rec["definition"] == "统计周期内全部成交金额"
        assert rec["domain_id"] == "FINANCE"
        assert rec["confidence"] == 1.0
        assert rec["origin"] == "structured"
        assert rec["source_text"] == "SUM(order.amount)"
        prov = rec["provenance"]
        assert prov["attribute_of"] == "订单"
        assert prov["indicator_id"] == "ind-1"
        assert prov["indicator_type"] == "metric"
        assert prov["unit"] == "元"
        assert prov["version_id"] == "v1"

    def test_empty_related_objects_yields_empty_attribute_of_not_crash(self, pipeline):
        """related_objects 为空时 attribute_of 落空串，不得 IndexError（ADR-082 §2）。"""
        out = pipeline._collect_indicator_candidates(
            [_indicator(related_objects=[])], run_id="run-ind2", ontology_id="ont-test",
        )
        assert out["status"] == "ok", out
        assert out["records"][0]["provenance"]["attribute_of"] == ""

    def test_related_objects_not_emitted_as_separate_candidates(self, pipeline):
        """指标只产 1 条属性候选；related_objects/processes/rules 不另发（避免循环归类）。"""
        out = pipeline._collect_indicator_candidates(
            [_indicator()], run_id="run-ind3", ontology_id="ont-test",
        )
        assert out["status"] == "ok"
        assert len(out["records"]) == 1
        canonicals = {r["canonical"] for r in out["records"]}
        assert canonicals == {"成交总额"}
        assert "订单" not in canonicals and "下单" not in canonicals

    def test_name_fallback_when_no_display_name(self, pipeline):
        out = pipeline._collect_indicator_candidates(
            [_indicator(display_name="", name="gmv_total")],
            run_id="run-ind4", ontology_id="ont-test",
        )
        assert out["status"] == "ok"
        assert out["records"][0]["canonical"] == "gmv_total"

    def test_definition_falls_back_to_llm_description(self, pipeline):
        out = pipeline._collect_indicator_candidates(
            [_indicator(description="", llm_description="LLM 生成的口径")],
            run_id="run-ind5", ontology_id="ont-test",
        )
        assert out["records"][0]["definition"] == "LLM 生成的口径"

    def test_empty_indicator_list_is_ok_with_warning(self, pipeline):
        out = pipeline._collect_indicator_candidates(
            [], run_id="run-ind6", ontology_id="ont-test",
        )
        assert out["status"] == "ok", out
        assert out["records"] == []
        assert out["warnings"], "空指标列表应给出告警"

    def test_indicators_are_persisted(self, pipeline):
        out = pipeline._collect_indicator_candidates(
            [_indicator(), _indicator(indicator_id="ind-2", display_name="客单价",
                                      name="aov", related_objects=["订单"])],
            run_id="run-ind7", ontology_id="ont-test",
        )
        assert out["status"] == "ok"
        assert len(_persisted(pipeline, "run-ind7")) == len(out["records"]) == 2

    def test_persistence_failure_is_error_not_false_ok(self, pipeline, monkeypatch):
        def _boom(_records):
            raise RuntimeError("disk full")

        monkeypatch.setattr(
            pipeline.candidate_storage, "bulk_insert_candidates", _boom, raising=True,
        )
        out = pipeline._collect_indicator_candidates(
            [_indicator()], run_id="run-ind8", ontology_id="ont-test",
        )
        assert out["status"] == "error", out
        assert "disk full" in out["message"]
        assert _persisted(pipeline, "run-ind8") == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py::TestIndicatorCandidateCollection -q --no-header -p no:cacheprovider`
Expected: FAIL —— `AttributeError: 'SemanticAssetPipeline' object has no attribute '_collect_indicator_candidates'`。

- [ ] **Step 3: 加 `INDICATOR_SOURCE_TYPES` 常量**

在 `pipeline_service.py` 的 `EVENT_SOURCE_TYPES` 之后追加：

```python
# BI 业务指标源（走 BusinessService.list_indicators，映射为「属性」候选）。
# 不在 STRUCTURED_SOURCE_TYPES 内，run() 须先于结构化分支单独分派（ADR-082 §3）。
INDICATOR_SOURCE_TYPES = frozenset({"business_indicators"})
```

- [ ] **Step 4: 加 `_business_service` 槽位与懒加载属性**

把 `__init__`（当前 55-59）改为：

```python
    def __init__(self) -> None:
        self._ingest_facade = None
        self._ingest_service = None
        self._extract_service = None
        self._candidate_storage = None
        self._business_service = None
```

在 `candidate_storage` 属性之后（当前 94 行后）追加：

```python
    @property
    def business_service(self):
        """业务资产服务（只读侧）— 用于按 ontology_id 拉取 BI 指标清单。"""
        if self._business_service is None:
            from odap.biz.management.business.services.business_service import (
                BusinessService,
            )
            self._business_service = BusinessService()
        return self._business_service
```

- [ ] **Step 5: 加 `_collect_indicator_candidates` 方法**

在 `pipeline_service.py` 的 `_collect_event_candidates` 之后追加：

```python
    def _collect_indicator_candidates(
        self,
        indicators: List[Dict[str, Any]],
        *,
        run_id: str,
        ontology_id: Optional[str],
        domain_code: str = "",
        version_id: str = "",
    ) -> Dict[str, Any]:
        """把 BI 业务指标归集为「属性」候选（ADR-082 §2）。

        指标是结构化逐字事实（非 LLM 推断），故 confidence=1.0、origin="structured"。
        USL 6 类无「指标类型」，指标语义上是被度量对象的属性，映射为「属性」；
        attribute_of 取 related_objects[0]，空列表落空串（不 IndexError、不反推）。
        related_objects/processes/rules 不另发为独立候选——那会把"指标关联了某对象"
        误当成"该对象本身是一条待审语义"，造成循环归类。

        Returns:
            {"status": "ok", "records": [...], "stats": {...}, "warnings": [...]}
            或 {"status": "error", "message": "..."}
        """
        base_prov = {
            "source": "business_indicators",
            "source_kind": "indicator",
            "ontology_id": ontology_id,
            "version_id": version_id,
        }

        merged: Dict[tuple, Dict[str, Any]] = {}
        stats: Dict[str, int] = {}

        for ind in indicators or []:
            if not isinstance(ind, dict):
                continue
            canonical = str(ind.get("display_name") or ind.get("name") or "").strip()
            if not canonical:
                continue
            related_objects = ind.get("related_objects") or []
            attribute_of = str(related_objects[0]) if related_objects else ""
            definition = str(ind.get("description") or ind.get("llm_description") or "")
            stats["属性"] = stats.get("属性", 0) + 1
            key = ("属性", canonical)
            if key in merged:
                continue
            prov = dict(base_prov)
            prov.update({
                "indicator_id": ind.get("indicator_id", ""),
                "indicator_type": ind.get("indicator_type", ""),
                "calculation_formula": ind.get("calculation_formula", ""),
                "unit": ind.get("unit", ""),
                "attribute_of": attribute_of,
                "related_objects": list(related_objects),
                "related_processes": list(ind.get("related_processes") or []),
                "related_rules": list(ind.get("related_rules") or []),
            })
            merged[key] = {
                "run_id": run_id,
                "domain_id": domain_code,
                "canonical": canonical,
                "en": str(ind.get("name") or ""),
                "semantic_type": "属性",
                "definition": definition,
                "synonyms": [],
                "confidence": 1.0,
                "origin": "structured",
                "source_text": str(ind.get("calculation_formula") or ""),
                "provenance": prov,
            }

        records = list(merged.values())
        warnings: List[str] = []
        if not records:
            warnings.append(
                "本体下未查询到 BI 业务指标，未归集到候选"
                "（请确认该本体/版本已定义指标）"
            )

        if records:
            try:
                self.candidate_storage.bulk_insert_candidates(records)
            except Exception as e:
                logger.error("BI 指标候选归集落库失败: %s", e)
                return {
                    "status": "error",
                    "message": f"BI 指标候选落库失败（{len(records)} 条未持久化）: {e}",
                }

        return {
            "status": "ok",
            "records": records,
            "stats": {
                "raw_indicators": len(indicators or []),
                "deduped_candidates": len(records),
                "by_semantic_type": dict(stats),
            },
            "warnings": warnings,
        }
```

- [ ] **Step 6: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py::TestIndicatorCandidateCollection -q --no-header -p no:cacheprovider`
Expected: PASS（8 条全过）。

- [ ] **Step 7: 提交**

```bash
git add apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py apps/api/tests/unit/test_semantic_asset_pipeline_structured.py
git commit -m "$(cat <<'EOF'
feat(semantic-admin): BI 指标归集为「属性」候选

- 新增 INDICATOR_SOURCE_TYPES、business_service 懒加载属性
- _collect_indicator_candidates：display_name/name→canonical，related_objects[0]→attribute_of（空落空串）
- 不另发 related_objects/processes/rules 为独立候选，避免循环归类（ADR-082 §2）
EOF
)"
```

---

## Task 5: `_run_indicator` + `run()` 分派 + `source_kind` 标签

**Files:**
- Modify: `apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py:388-405`（`run()` 分派与 source_kind）、`:543`（`_run_structured` 之后新增 `_run_indicator`）
- Test: `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py`（新增测试类）

**Interfaces:**
- Consumes: `INDICATOR_SOURCE_TYPES`（Task 4）；`self.business_service.list_indicators(ontology_id=, version_id=)`（Task 4 属性）；`_collect_indicator_candidates`（Task 4）；`_resolve_domain_code`（既有）。
- Produces: `async def _run_indicator(self, ontology_id, payload, pipeline_run_id) -> Dict[str,Any]`；`run()` 分派顺序变为 unstructured → **indicator** → structured → else error；`run()` 末尾 `source_kind` 标签对 `INDICATOR_SOURCE_TYPES` 置 `"indicator"`。

- [ ] **Step 1: 写失败测试（指标分派端到端 + 缺 ontology_id 报错 + list_indicators 异常显式 + 未知源报错）**

在 `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py` 文件末尾追加：

```python
# ──────────────────────────────────────────────────────────────────────
# 12. run() BI 指标分派（ADR-082 §2/§3）
# ──────────────────────────────────────────────────────────────────────
class TestRunIndicatorDispatch:
    async def test_business_indicators_routes_to_indicator_collector(self, pipeline):
        from unittest.mock import patch

        class _BizSvc:
            def list_indicators(self, ontology_id=None, version_id=None):
                assert ontology_id == "ont-test"
                return [_indicator()]

        class _FakeOntSvc:
            def get_ontology(self, oid):
                return {"ontology_id": oid, "domain_code": "FINANCE"}

        pipeline._business_service = _BizSvc()
        # patch 定义模块（非 public 门面）：门面 PEP 562 __getattr__ 会被 monkeypatch
        # 撤销时污染成永久真实属性（见本文件 test_list_usl_ontologies 注释）。
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            _FakeOntSvc,
        ):
            res = await pipeline.run(
                source_type="business_indicators", ontology_id="ont-test",
                payload={"version_id": "v1"},
            )
        assert res["status"] == "ok", res
        assert res["source_kind"] == "indicator"
        assert res["candidate_count"] == 1
        rec = res["candidates"][0]
        assert rec["semantic_type"] == "属性"
        assert rec["canonical"] == "成交总额"
        assert rec["domain_id"] == "FINANCE"
        assert _persisted(pipeline, res["pipeline_run_id"])

    async def test_missing_ontology_id_is_explicit_error(self, pipeline):
        res = await pipeline.run(
            source_type="business_indicators", ontology_id=None, payload={},
        )
        assert res["status"] == "error", res
        assert "ontology_id" in res["message"]

    async def test_list_indicators_exception_is_explicit_error(self, pipeline):
        class _BoomSvc:
            def list_indicators(self, ontology_id=None, version_id=None):
                raise RuntimeError("business.db locked")

        pipeline._business_service = _BoomSvc()
        res = await pipeline.run(
            source_type="business_indicators", ontology_id="ont-test", payload={},
        )
        assert res["status"] == "error", res
        assert "business.db locked" in res["message"]

    async def test_unknown_source_type_is_error(self, pipeline):
        res = await pipeline.run(source_type="not_a_real_source", payload={})
        assert res["status"] == "error", res
        assert "未知数据源类型" in res["message"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py::TestRunIndicatorDispatch -q --no-header -p no:cacheprovider`
Expected: FAIL —— `business_indicators` 既不在 `UNSTRUCTURED_SOURCE_TYPES` 也不在 `STRUCTURED_SOURCE_TYPES`，当前 `run()` 落到 else 返回"未知数据源类型"，故 `test_business_indicators_routes_to_indicator_collector` 报 `assert 'error' == 'ok'`。

- [ ] **Step 3: 加 `_run_indicator` 方法**

在 `pipeline_service.py` 的 `_run_structured` 方法之后（当前 543 行 `return {...}` 之后）追加：

```python
    # ------------------------------------------------------------------
    # 链路 C：BI 业务指标抽取（ADR-082 §2）
    # ------------------------------------------------------------------
    async def _run_indicator(
        self,
        ontology_id: Optional[str],
        payload: Dict[str, Any],
        pipeline_run_id: str,
    ) -> Dict[str, Any]:
        if not ontology_id:
            # 指标必须挂在具体本体（+可选版本）下，缺 ontology_id 无法定位指标清单。
            # 显式报错而非静默返回全量指标（规则 14：失败必须显式、禁止猜测性反推）。
            return {
                "status": "error",
                "message": "BI 指标抽取需要 ontology_id（请先在 Step 0 选择目标本体）",
            }

        version_id = str(payload.get("version_id") or "")
        try:
            indicators = self.business_service.list_indicators(
                ontology_id=ontology_id,
                version_id=version_id or None,
            )
        except Exception as e:
            logger.error(
                "拉取 BI 指标失败（ontology_id=%s, version_id=%s）: %s",
                ontology_id, version_id, e,
            )
            return {"status": "error", "message": f"拉取 BI 指标失败: {e}"}

        collected = self._collect_indicator_candidates(
            indicators,
            run_id=pipeline_run_id,
            ontology_id=ontology_id,
            domain_code=self._resolve_domain_code(ontology_id),
            version_id=version_id,
        )
        if collected.get("status") == "error":
            logger.error(
                "BI 指标候选归集失败（ontology_id=%s）: %s",
                ontology_id, collected.get("message"),
            )
            return {
                "status": "error",
                "message": f"BI 指标已读取但未能归集候选: {collected.get('message')}",
            }

        return {
            "status": "ok",
            "candidate_count": len(collected["records"]),
            "candidates": collected["records"],
            "collection_stats": collected["stats"],
            "collection_warnings": collected["warnings"],
        }
```

- [ ] **Step 4: 改 `run()` 分派与 source_kind 标签**

把 `run()` 的分派块（当前 388-399）：

```python
        if source_type in UNSTRUCTURED_SOURCE_TYPES:
            result = await self._run_unstructured(
                source_type, ontology_id, extraction_mode, template_ref,
                payload, scenario_id, workspace_id, pipeline_run_id,
            )
        elif source_type in STRUCTURED_SOURCE_TYPES:
            result = await self._run_structured(
                source_type, ontology_id, extraction_mode, payload,
                scenario_id, workspace_id, pipeline_run_id,
            )
        else:
            return {"status": "error", "message": f"未知数据源类型: {source_type}"}
```

替换为（indicator 分支置于 structured 之前）：

```python
        if source_type in UNSTRUCTURED_SOURCE_TYPES:
            result = await self._run_unstructured(
                source_type, ontology_id, extraction_mode, template_ref,
                payload, scenario_id, workspace_id, pipeline_run_id,
            )
        elif source_type in INDICATOR_SOURCE_TYPES:
            result = await self._run_indicator(
                ontology_id, payload, pipeline_run_id,
            )
        elif source_type in STRUCTURED_SOURCE_TYPES:
            result = await self._run_structured(
                source_type, ontology_id, extraction_mode, payload,
                scenario_id, workspace_id, pipeline_run_id,
            )
        else:
            return {"status": "error", "message": f"未知数据源类型: {source_type}"}
```

把 `run()` 末尾的 source_kind 标签（当前 402-404）：

```python
        result["source_kind"] = (
            "unstructured" if source_type in UNSTRUCTURED_SOURCE_TYPES else "structured"
        )
```

替换为：

```python
        if source_type in UNSTRUCTURED_SOURCE_TYPES:
            result["source_kind"] = "unstructured"
        elif source_type in INDICATOR_SOURCE_TYPES:
            result["source_kind"] = "indicator"
        else:
            # 含事件源（webhook/mcp/file/api）：run 级标签仍为 structured，
            # 候选 provenance.source_kind 才是 "event"（Task 2/3）。
            result["source_kind"] = "structured"
```

- [ ] **Step 5: 运行测试确认通过（含全文件回归）**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py -q --no-header -p no:cacheprovider`
Expected: PASS（`TestRunIndicatorDispatch` 4 条通过；既有 unstructured/structured 分派不回归）。

- [ ] **Step 6: 提交**

```bash
git add apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py apps/api/tests/unit/test_semantic_asset_pipeline_structured.py
git commit -m "$(cat <<'EOF'
feat(semantic-admin): run() 分派 BI 指标链路并标注 source_kind=indicator

- 新增 _run_indicator：缺 ontology_id/拉取异常均显式报错
- run() 分派顺序 unstructured→indicator→structured→else
- source_kind 对 indicator 源置 "indicator"（ADR-082 §2/§3）
EOF
)"
```

---

## Task 6: `options()` 暴露 indicator 源类型

**Files:**
- Modify: `apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py:172-180`（`options()` 返回体的 `source_types`）
- Test: `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py`（新增测试类）

**Interfaces:**
- Consumes: `INDICATOR_SOURCE_TYPES`（Task 4）。
- Produces: `options()` 返回体 `source_types` 新增键 `"indicator": sorted(INDICATOR_SOURCE_TYPES)`（即 `["business_indicators"]`）。前端 Task 8 读取该键渲染第三个数据源 Select。

- [ ] **Step 1: 写失败测试**

在 `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py` 文件末尾追加：

```python
# ──────────────────────────────────────────────────────────────────────
# 13. options() 暴露 indicator 源（ADR-082 §6）
# ──────────────────────────────────────────────────────────────────────
class TestOptionsExposeIndicatorSource:
    def test_source_types_include_indicator_group(self, pipeline, monkeypatch):
        # options() 会构造 TemplateEngine / OntologyService / UslManagerService 等
        # 重依赖；这里只验证 source_types 结构，故把三段外部构造打成轻量桩，
        # 被测的 options() 函数体（含 source_types 组装）照常执行（规则 14 要求 6）。
        monkeypatch.setattr(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            type("_S", (), {"list_ontologies": lambda self, workspace_id=None: {
                "status": "ok", "ontologies": []}}),
            raising=True,
        )
        monkeypatch.setattr(
            "odap.biz.semantic_admin.usl_manager.services.UslManagerService",
            type("_U", (), {"list_domains": lambda self, page=1, page_size=500: {
                "status": "ok", "items": []}}),
            raising=True,
        )

        res = pipeline.options()
        assert res["status"] == "ok"
        st = res["source_types"]
        assert st["indicator"] == ["business_indicators"]
        # 既有两组不回归
        assert "webhook" in st["structured"]
        assert "natural_language" in st["unstructured"]
```

> 注：`options()` 内 `TemplateEngine` 构造若在本机离线环境失败，已被其自身 `try/except` 记 warning 并置 `te=None`（既有行为，`templates` 返回空列表），不影响 `source_types` 断言。

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py::TestOptionsExposeIndicatorSource -q --no-header -p no:cacheprovider`
Expected: FAIL —— `KeyError: 'indicator'`（当前 `source_types` 只有 structured/unstructured）。

- [ ] **Step 3: 改 `options()` 返回体**

把 `options()` 的返回块（当前 172-180）：

```python
        return {
            "status": "ok",
            "source_types": {
                "structured": sorted(STRUCTURED_SOURCE_TYPES),
                "unstructured": sorted(UNSTRUCTURED_SOURCE_TYPES),
            },
            "templates": templates,
            "ontologies": ontologies,
        }
```

替换为：

```python
        return {
            "status": "ok",
            "source_types": {
                "structured": sorted(STRUCTURED_SOURCE_TYPES),
                "unstructured": sorted(UNSTRUCTURED_SOURCE_TYPES),
                "indicator": sorted(INDICATOR_SOURCE_TYPES),
            },
            "templates": templates,
            "ontologies": ontologies,
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py::TestOptionsExposeIndicatorSource -q --no-header -p no:cacheprovider`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py apps/api/tests/unit/test_semantic_asset_pipeline_structured.py
git commit -m "$(cat <<'EOF'
feat(semantic-admin): options() 暴露 indicator 数据源组

- source_types 新增 indicator=["business_indicators"]，供前端向导渲染（ADR-082 §6）
EOF
)"
```

---

## Task 7: 架构契约校验 + 离线全量回归 + 文档同步

**Files:**
- Modify: `docs/03-modules/semantic_admin/DESIGN.md`（增补两条能力记录）
- 无代码改动（本任务是验证 + 文档闸）

**Interfaces:**
- Consumes: Task 1-6 的全部代码改动。
- Produces: 一次干净的 `lint-imports`（C1-C4 无新增违规）+ 离线全量单测无新增回归 + DESIGN.md 两条新能力记录。

- [ ] **Step 1: 校验架构契约（import-linter C1-C4）**

import-linter / grimp 是仓库根 `[dependency-groups] dev` 工具，`[tool.importlinter]` 配置在 `apps/api/pyproject.toml`，故须先在根补 dev 组、再进 `apps/api` 执行（与 `.github/workflows/ci.yml:69-71` 一致）：

Run:
```bash
uv sync --frozen --inexact
cd apps/api && uv run --frozen --no-sync lint-imports
```
Expected: PASS —— 4 条契约（C1/C2/C3/C4）全绿。新增的 `biz.semantic_admin → biz.management.business.services.business_service` 是 biz→biz 跨域边，不在任何契约的 `forbidden_modules` 内（C3 只列 ontology 内部子包），故不触发违规。

> 若 `uv sync --frozen` 因锁文件漂移失败，改用 `uv sync --inexact`（不带 `--frozen`）后重试；本计划不改任何依赖，锁文件不应漂移。

- [ ] **Step 2: 离线全量单测回归**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit -q --no-header -p no:cacheprovider`
Expected: 与 Task #11 基线一致——无新增 failed。重点确认 `test_unified_ingest_facade.py`、`test_semantic_asset_pipeline_structured.py`、`test_perception.py` 全绿。若有 skip（依赖 graphiti-core/openharness/Neo4j 的用例）属正常。

- [ ] **Step 3: 同步 `docs/03-modules/semantic_admin/DESIGN.md`（规则 12）**

在该文档描述 `semantic_asset_pipeline` 能力的小节，增补两条（措辞对齐既有文档风格，描述**已实现**的代码，不写未落地内容）：

```markdown
- **事件源候选归集（ADR-082 §1）**：`webhook/mcp/file/api` 经 `UnifiedIngestFacade._ingest_event`
  路由到 PerceptionHub，门面把 `ExtractionResult` 透传上来（`ingest_result["extraction"]`），
  `SemanticAssetPipeline._collect_event_candidates` 将实体→对象类型+属性、关系→关系类型、
  事件→过程类型归集为待审候选（`origin="llm"`、置信度取抽取置信度）；`actions` 当前恒为空，
  如实产出 0 条动作候选。`sensor` 源延后（ADR-082 §5），保持其既有显式行为。
- **BI 指标候选归集（ADR-082 §2）**：新增 `business_indicators` 源类型，`_run_indicator`
  经 `BusinessService.list_indicators(ontology_id, version_id)` 拉取指标，
  `_collect_indicator_candidates` 将每条指标映射为一条「属性」候选
  （`canonical=display_name|name`、`attribute_of=related_objects[0]`（空落空串）、
  `confidence=1.0`、`origin="structured"`）；`related_objects/processes/rules` 不另发为
  独立候选，避免循环归类。缺 `ontology_id` 或拉取异常均显式报错（规则 14）。
```

- [ ] **Step 4: 提交**

```bash
git add docs/03-modules/semantic_admin/DESIGN.md
git commit -m "$(cat <<'EOF'
docs(semantic-admin): 增补事件源/BI指标候选归集能力记录（ADR-082，规则12）
EOF
)"
```

---

## Task 8: 前端向导新增「业务指标」数据源

**Files:**
- Modify: `apps/web/src/modules/semantic-admin/services/assetPipelineApi.ts:10-13`（`AssetSourceTypes`）
- Modify: `apps/web/src/modules/semantic-admin/pages/SemanticAssetPipelinePage.tsx`（memos / Step 1 Select / buildPayload / Step 2 version_id 输入）

**Interfaces:**
- Consumes: 后端 `GET /api/semantic-assets/pipeline/options` 返回的 `source_types.indicator`（Task 6）；`POST /run` 接受 `source_type="business_indicators"` + `ontology_id` + `payload.version_id`（Task 5）。
- Produces: 向导 Step 1 出现第三个数据源 Select（业务指标）；选中后 Step 2 可选填 `version_id`；`handleRun` 以 `source_type="business_indicators"` 提交。

> **验证限制（规则 7）**：前端运行时须在 Podman 容器内（`python apps/api/bootstep.py dev`）。宿主机只能做静态校验（`pnpm typecheck` / `pnpm lint`）；交互冒烟必须进容器，本任务无法纯离线完成最终验证——执行者须显式说明哪一步在容器内验证、哪一步只做了静态检查。

- [ ] **Step 1: 扩展 `AssetSourceTypes` 类型**

在 `apps/web/src/modules/semantic-admin/services/assetPipelineApi.ts`，把：

```typescript
export interface AssetSourceTypes {
  structured: string[];
  unstructured: string[];
}
```

改为：

```typescript
export interface AssetSourceTypes {
  structured: string[];
  unstructured: string[];
  /** BI 业务指标源（ADR-082 §2/§6），后端 options() 暴露 */
  indicator?: string[];
}
```

- [ ] **Step 2: 页面新增 indicator memos 与判定**

在 `SemanticAssetPipelinePage.tsx` 的 `unstructuredSourceTypes` memo（当前 97-100）之后追加：

```typescript
  const indicatorSourceTypes = useMemo(
    () => options?.source_types?.indicator ?? [],
    [options],
  );
```

在 `isUnstructured` memo（当前 108-111）之后追加：

```typescript
  const isIndicator = useMemo(
    () => indicatorSourceTypes.includes(state.sourceType ?? ''),
    [indicatorSourceTypes, state.sourceType],
  );
```

- [ ] **Step 3: 新增 version_id 输入状态**

在 `jsonPayload` 状态声明（当前 73）之后追加：

```typescript
  const [versionPayload, setVersionPayload] = useState('');
```

- [ ] **Step 4: buildPayload 增加 indicator 分支**

把 `buildPayload`（当前 143-166）的开头：

```typescript
  const buildPayload = useCallback((): Record<string, unknown> => {
    if (isUnstructured) {
```

改为：

```typescript
  const buildPayload = useCallback((): Record<string, unknown> => {
    if (isIndicator) {
      // BI 指标：ontology_id 走请求顶层字段，payload 只带可选 version_id
      return versionPayload ? { version_id: versionPayload } : {};
    }
    if (isUnstructured) {
```

并把该 `useCallback` 的依赖数组（当前 166）：

```typescript
  }, [isUnstructured, isStructured, state.sourceType, textPayload, jsonPayload]);
```

改为：

```typescript
  }, [isIndicator, isUnstructured, isStructured, state.sourceType, textPayload, jsonPayload, versionPayload]);
```

- [ ] **Step 5: Step 1 增加「业务指标」数据源 Select**

在 Step 1 卡片（`current === 1`）内、非结构化 Select 之后、`<Space>` 按钮组之前，追加第三个 Select。把当前 Step 1 中：

```tsx
              <Text strong>{t('非结构化文档抽取')}</Text>
              <Select
                style={{ maxWidth: 520 }}
                placeholder={t('选择非结构化数据源')}
                value={isUnstructured ? state.sourceType : undefined}
                onChange={(v) => setState((s) => ({ ...s, sourceType: v }))}
                options={unstructuredSourceTypes.map((s) => ({ value: s, label: s }))}
              />
              <Space>
```

改为：

```tsx
              <Text strong>{t('非结构化文档抽取')}</Text>
              <Select
                style={{ maxWidth: 520 }}
                placeholder={t('选择非结构化数据源')}
                value={isUnstructured ? state.sourceType : undefined}
                onChange={(v) => setState((s) => ({ ...s, sourceType: v }))}
                options={unstructuredSourceTypes.map((s) => ({ value: s, label: s }))}
              />
              <Text strong>{t('BI 业务指标抽取')}</Text>
              <Paragraph type="secondary">
                {t('业务指标抽取需先在 Step 0 选择目标本体；指标将归集为「属性」候选')}
              </Paragraph>
              <Select
                style={{ maxWidth: 520 }}
                placeholder={t('选择业务指标数据源')}
                value={isIndicator ? state.sourceType : undefined}
                onChange={(v) => setState((s) => ({ ...s, sourceType: v }))}
                options={indicatorSourceTypes.map((s) => ({ value: s, label: s }))}
              />
              <Space>
```

- [ ] **Step 6: Step 2 为 indicator 增加可选 version_id 输入**

在 Step 2 卡片（`current === 2`）内、`{isStructured && state.sourceType !== 'json' && (...)}` 块之后，追加：

```tsx
              {isIndicator && (
                <Form layout="vertical">
                  <Form.Item label={t('本体版本（可选）')}>
                    <Input
                      style={{ maxWidth: 520 }}
                      value={versionPayload}
                      onChange={(e) => setVersionPayload(e.target.value)}
                      placeholder={t('留空则抽取该本体全部版本的指标')}
                    />
                  </Form.Item>
                </Form>
              )}
```

- [ ] **Step 7: 宿主机静态校验**

Run: `cd apps/web && pnpm typecheck`
Expected: PASS（无类型错误；`indicator?` 为可选字段，旧 options 响应不报错）。

Run: `cd apps/web && pnpm lint`
Expected: PASS（无新增 lint 错误；跨目录导入仍用 `@` 别名，未引入相对路径跨目录）。

- [ ] **Step 8: 容器内交互冒烟（规则 7，须显式记录验证位置）**

启动开发容器并冒烟：

```bash
python apps/api/bootstep.py dev
```

待容器 Up 后，浏览器访问 `http://localhost:5173`，进入语义管理台 → 语义资产 Pipeline 向导：
1. Step 0 选择一个本体（业务指标必需）；
2. Step 1 确认出现「BI 业务指标抽取」Select，选 `business_indicators`；
3. Step 2 可选填版本；
4. 执行 → 确认返回候选（「属性」类型），或在该本体无指标时显示后端告警/错误文案（不得静默"成功 0 条"无提示）。

> 执行者须在完成报告中明确：Step 7 在宿主机静态校验、Step 8 在 Podman 容器内交互验证；若无法启动容器，须显式声明"Step 8 未验证"，不得宣称前端功能已验证通过（规则 14：失败/未验证必须显式）。

- [ ] **Step 9: 提交**

```bash
git add apps/web/src/modules/semantic-admin/services/assetPipelineApi.ts apps/web/src/modules/semantic-admin/pages/SemanticAssetPipelinePage.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): 语义资产向导新增 BI 业务指标数据源

- AssetSourceTypes 增 indicator?；Step1 第三 Select + Step2 可选 version_id
- buildPayload indicator 分支只带 version_id，ontology_id 走请求顶层（ADR-082 §6）
EOF
)"
```

---

## Self-Review

**1. Spec coverage（ADR-082 §1-§6 逐条对照）：**
- §0 host = asset pipeline → 全部改动落在 `SemanticAssetPipeline`（Task 2-6），未碰 ol_pipeline。✅
- §1 事件源：门面透传 extraction（Task 1）+ `_collect_event_candidates` 映射（Task 2）+ `_run_structured` 分流（Task 3）；entities→对象类型+属性（仅 basic/statistical）、relations→关系类型、events→过程类型、actions 如实空、origin=llm、confidence=抽取置信度、domain_id 解析。✅
- §2 BI 指标：`business_indicators` 源 + `_run_indicator`（Task 5）+ `_collect_indicator_candidates`（Task 4）；canonical=display_name|name、semantic_type=属性、definition=description|llm_description、attribute_of=related_objects[0] if any else ""、confidence=1.0、origin=structured、ontology_id 必填、不另发关联候选、导入 BusinessService 服务层。✅
- §3 常量与分派：`EVENT_SOURCE_TYPES={webhook,mcp,file,api}`（去 sensor）、`INDICATOR_SOURCE_TYPES={business_indicators}`、分派顺序 unstructured→indicator→structured→else。✅
- §4 错误处理（规则 14）：缺 extraction 键、缺 ontology_id、list_indicators 异常、落库失败、FAILED 状态——全部显式 error；空抽取/空指标→warning。每个失败路径都有对应测试。✅
- §5 延后项：sensor 不入 EVENT_SOURCE_TYPES（Task 2 注释 + Global Constraints）；warehouse schema/本体类型定义未触碰。✅
- §6 前端：options 暴露 indicator（Task 6）+ 向导第三 Select（Task 8）。✅

**2. Placeholder scan：** 无 TBD/TODO/"类似上文"/"适当处理"。每个代码步骤都给出完整可粘贴代码；每条测试都给出完整断言。✅

**3. Type consistency（跨任务签名核对）：**
- `_collect_event_candidates(self, ingest_result, *, run_id, ontology_id, source_kind="event", domain_code="")` —— Task 2 定义、Task 3 调用一致。✅
- `_collect_indicator_candidates(self, indicators, *, run_id, ontology_id, domain_code="", version_id="")` —— Task 4 定义、Task 5 调用一致。✅
- `_run_indicator(self, ontology_id, payload, pipeline_run_id)` —— Task 5 定义与 `run()` 调用一致。✅
- `business_service` 属性 / `_business_service` 槽位 —— Task 4 定义、Task 5 测试注入 `pipeline._business_service` 一致。✅
- `EVENT_SOURCE_TYPES` / `INDICATOR_SOURCE_TYPES` —— Task 2/4 定义、Task 3/5/6 使用一致。✅
- 门面返回键 `"extraction"` —— Task 1 产出、Task 2 消费（`ingest_result["extraction"]`）一致。✅
- 前端 `source_types.indicator` —— Task 6 后端产出、Task 8 `indicatorSourceTypes` 消费一致。✅
- 候选记录字段（run_id/domain_id/canonical/en/semantic_type/definition/synonyms/confidence/origin/source_text/provenance）—— 与既有 `_collect_structured_candidates` 及 `SQLiteCandidateStorage.bulk_insert_candidates` 契约一致（Task 2/4 沿用同结构）。✅

**4. 范围核对：** 断链 1（`INGEST_AUTO_PIPELINE_DEFAULT` 翻转）、sensor、warehouse schema 均在 Global Constraints 显式列为范围外，未折叠进任何任务。✅

---

## Execution Handoff

计划已保存到 `docs/superpowers/plans/2026-09-25-event-source-bi-indicator-ol-entries.md`。
