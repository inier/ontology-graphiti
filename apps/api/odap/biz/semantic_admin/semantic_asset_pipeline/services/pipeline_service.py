"""SemanticAssetPipeline — 语义资产统一编排服务。

职责（严格确定性，无 LLM 判断）：
1. options()  — 返回前端下拉所需选项（数据源类型 / 模板 / 本体）
2. run()      — 统一编排入口：按 source_type 路由到链路 A（结构化）或链路 B（非结构化）
3. get_run()  — 查询一次 pipeline 的产出候选列表
4. submit()   — 将 DRAFT 候选批量提交审核（→ PENDING_REVIEW）

候选归集：把两条链路的产出统一写入 Candidate Store，打上
source_template_id / pipeline_run_id / source_kind 追溯标记。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
    SQLiteCandidateStorage,
    CAND_DRAFT,
    CAND_PENDING_REVIEW,
)

logger = logging.getLogger(__name__)

# 结构化数据源（链路 A，走 UnifiedIngestFacade）
STRUCTURED_SOURCE_TYPES = frozenset({
    "url", "news", "tavily", "manual", "json",
    "random_events", "database", "kb_upload", "ontology_document",
    "webhook", "sensor", "mcp", "file", "api",
})

# 非结构化文档源（链路 B，走 ExtractService）
UNSTRUCTURED_SOURCE_TYPES = frozenset({
    "natural_language", "document",
})

# 事件驱动源（走 UnifiedIngestFacade → PerceptionHub，复用其 ExtractionResult）。
# = SourceCategory.EVENT_DRIVEN 去掉 sensor（ADR-082 §5：sensor 延后，保持其现有
# 显式行为，不纳入事件候选归集）。这些类型仍是 STRUCTURED_SOURCE_TYPES 的子集，
# 路由走 _run_structured，但候选归集分流到 _collect_event_candidates（Task 3）。
EVENT_SOURCE_TYPES = frozenset({"webhook", "mcp", "file", "api"})

# BI 业务指标源（走 BusinessService.list_indicators，映射为「属性」候选）。
# 不在 STRUCTURED_SOURCE_TYPES 内，run() 须先于结构化分支单独分派（ADR-082 §3）。
INDICATOR_SOURCE_TYPES = frozenset({"business_indicators"})


class SemanticAssetPipeline:
    """统一编排器（单例）。

    复用 UnifiedIngestFacade（结构化）与 ExtractService（非结构化），
    只负责：路由 → 抽取/引入 → 候选归集 → 提交审核。
    """

    _instance: Optional["SemanticAssetPipeline"] = None

    @classmethod
    def get_instance(cls) -> "SemanticAssetPipeline":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._ingest_facade = None
        self._ingest_service = None
        self._extract_service = None
        self._candidate_storage = None
        self._business_service = None

    # ------------------------------------------------------------------
    # 延迟加载
    # ------------------------------------------------------------------
    @property
    def ingest_facade(self):
        if self._ingest_facade is None:
            from odap.biz.data.ingest.unified_ingest_facade import (
                get_unified_ingest_facade,
            )
            self._ingest_facade = get_unified_ingest_facade()
        return self._ingest_facade

    @property
    def ingest_service(self):
        """摄入服务（只读侧）— 用于按 record_id 回捞本体文档。"""
        if self._ingest_service is None:
            from odap.biz.core.ontology.public import get_ingest_service
            self._ingest_service = get_ingest_service()
        return self._ingest_service

    @property
    def extract_service(self):
        if self._extract_service is None:
            from odap.biz.data.hyper_extract.services.extract_service import (
                ExtractService,
            )
            self._extract_service = ExtractService()
        return self._extract_service

    @property
    def candidate_storage(self) -> SQLiteCandidateStorage:
        if self._candidate_storage is None:
            self._candidate_storage = SQLiteCandidateStorage()
        return self._candidate_storage

    @property
    def business_service(self):
        """业务资产服务（只读侧）— 用于按 ontology_id 拉取 BI 指标清单。"""
        if self._business_service is None:
            from odap.biz.management.business.services.business_service import (
                BusinessService,
            )
            self._business_service = BusinessService()
        return self._business_service

    # ------------------------------------------------------------------
    # 1. options — 前端下拉选项
    # ------------------------------------------------------------------
    def options(self, ontology_id: Optional[str] = None) -> Dict[str, Any]:
        """返回 Pipeline 向导所需选项：数据源类型、模板列表、本体列表。

        本体列表做了可读性整形（Iter 增强）：
        - 以 domain_code（ADR-079 §7 权威字段）查 USL 领域，映射为可读的
          「领域名 (code)」，并附带 domain_code / domain_display_name 供前端展示；
        - 非 USL 本体（无 domain_code，用户手工建）保留原名。
        """
        try:
            from odap.biz.data.hyper_extract.services.template_engine import (
                TemplateEngine,
            )
            from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
            from odap.biz.data.hyper_extract.storage import Storage
            te = TemplateEngine(HEAdapter(), Storage())
        except Exception as e:  # pragma: no cover
            logger.warning("TemplateEngine 初始化失败: %s", e)
            te = None

        templates: List[Dict[str, Any]] = []
        if te is not None:
            try:
                templates = te.list_presets()
            except Exception as e:
                logger.warning("list_presets 失败: %s", e)

        raw_ontologies: List[Dict[str, Any]] = []
        try:
            from odap.biz.core.ontology.public import OntologyService
            svc = OntologyService()
            # 不再用 hasattr 探测（规则 14：探测式降级）。list_ontologies 确实存在
            # （design/services/ontology_service.py），探测失败会静默返回空本体列表，
            # 让向导看起来"没有可选本体"，而真实原因是一次方法改名。
            res = svc.list_ontologies()
            if isinstance(res, dict):
                raw_ontologies = list(res.get("ontologies") or res.get("items") or [])
            elif isinstance(res, list):
                raw_ontologies = res
        except Exception as e:
            logger.warning("list_ontologies 失败: %s", e)

        # USL 领域 code → display_name 映射（用于把 USL__{code} 转成可读名）
        domain_display_map: Dict[str, str] = {}
        try:
            from odap.biz.semantic_admin.usl_manager.services import UslManagerService
            usl = UslManagerService()
            usl_res = usl.list_domains(page=1, page_size=500)
            for d in (usl_res.get("items") or []):
                code = str(d.get("code") or "")
                disp = str(d.get("display_name") or code)
                if code:
                    domain_display_map[code] = disp
        except Exception as e:
            logger.warning("list_domains 失败: %s", e)

        ontologies: List[Dict[str, Any]] = []
        for o in raw_ontologies:
            if not isinstance(o, dict):
                continue
            item = dict(o)
            name = str(item.get("name") or "")
            domain_code = str(item.get("domain_code") or "")
            if domain_code:
                display = domain_display_map.get(domain_code)
                item["domain_display_name"] = display or ""
                # 可读 label：领域名 (code)；拿不到领域名则回退为 code
                item["display_label"] = (
                    f"{display}（{domain_code}）" if display else domain_code
                )
            else:
                item["display_label"] = name
            ontologies.append(item)

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

    def list_usl_ontologies(
        self, workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列出 USL 本体（用于「USL 本体管理」界面）。

        返回：
        - 仅含 domain_code 非空的系统本体（ADR-079 §7 权威关联）；
        - 每个本体附带 domain_display_name / display_label / 类型计数；
        - 附 domains 全量（供前端按领域筛选/联动）。
        """
        raw: List[Dict[str, Any]] = []
        try:
            from odap.biz.core.ontology.public import OntologyService
            svc = OntologyService()
            res = svc.list_ontologies(workspace_id=workspace_id)
            if isinstance(res, dict):
                raw = list(res.get("ontologies") or [])
            elif isinstance(res, list):
                raw = res
        except Exception as e:
            logger.warning("list_ontologies 失败: %s", e)

        # 领域映射
        domain_map: Dict[str, Dict[str, Any]] = {}
        try:
            from odap.biz.semantic_admin.usl_manager.services import UslManagerService
            usl = UslManagerService()
            usl_res = usl.list_domains(page=1, page_size=500)
            for d in (usl_res.get("items") or []):
                code = str(d.get("code") or "")
                if code:
                    domain_map[code] = d
        except Exception as e:
            logger.warning("list_domains 失败: %s", e)

        items: List[Dict[str, Any]] = []
        warnings: List[str] = []
        for o in raw:
            if not isinstance(o, dict):
                continue
            name = str(o.get("name") or "")
            domain_code = str(o.get("domain_code") or "")
            if not domain_code:
                continue  # 非 USL 本体，管理界面不展示
            dom = domain_map.get(domain_code)
            oid = str(o.get("ontology_id") or o.get("id") or "")
            if dom is None:
                # 本体挂了 domain_code 但 USL 领域表里查不到 —— 这是悬空引用，
                # 静默显示空白领域名会让业务人员以为"这个本体没有领域"。
                warnings.append(
                    f"本体 {name or oid} 的 domain_code={domain_code!r} "
                    f"在 USL 领域表中不存在（悬空引用）"
                )
                logger.warning(
                    "USL 本体 %s 的 domain_code=%r 在领域表中不存在（悬空引用）",
                    name, domain_code,
                )
                dom = {}
            type_counts, type_count_errors = self._count_ontology_types(oid)
            for err in type_count_errors:
                warnings.append(f"本体 {domain_code}: {err}")
            items.append({
                "ontology_id": oid,
                "name": name,
                "domain_code": domain_code,
                "domain_display_name": str(dom.get("display_name") or ""),
                "domain_description": str(dom.get("description") or ""),
                "display_label": (
                    f"{dom.get('display_name')}（{domain_code}）"
                    if dom.get("display_name") else domain_code
                ),
                "workspace_id": str(o.get("workspace_id") or ""),
                "created_at": o.get("created_at"),
                "type_counts": type_counts,
                "type_count_errors": type_count_errors,
            })

        return {
            "status": "ok",
            "items": items,
            "total": len(items),
            "domains": list(domain_map.values()),
            "warnings": warnings,
        }

    _TYPE_COUNT_SOURCES: Tuple[Tuple[str, str], ...] = (
        ("object_types", "list_object_types"),
        ("link_types", "list_link_types"),
        ("action_types", "list_action_types"),
        ("process_types", "list_process_types"),
        ("rule_types", "list_rule_types"),
    )

    def _count_ontology_types(
        self, ontology_id: str,
    ) -> Tuple[Dict[str, int], List[str]]:
        """统计某本体下各类类型定义的数量，返回 (counts, errors)。

        counts 只含**成功查到**的类别，查不到的类别直接缺席而不是写 0；errors 逐条
        记录失败原因，由调用方透出给前端。

        旧实现把所有失败都塌成 0（`getattr(svc, name, None)` 探测 + `except: 0`
        + 外层 `except: pass`），于是「本体确实是空的」和「本体查询坏了」在前端长得
        一模一样 —— 一次方法改名就能让整个 USL 管理界面显示全 0 而无人察觉
        （规则 14：探测式降级 + 静默假成功）。这里 getattr 不带默认值，方法消失会
        抛 AttributeError 并被记入 errors，而不是被探测吞掉。
        """
        counts: Dict[str, int] = {}
        errors: List[str] = []
        if not ontology_id:
            errors.append("ontology_id 为空，无法统计类型数量")
            return counts, errors

        try:
            from odap.biz.core.ontology.public import OntologyService
            svc = OntologyService()
        except Exception as e:
            errors.append(f"OntologyService 初始化失败: {e}")
            logger.warning(
                "统计本体类型失败（ontology_id=%s）: OntologyService 初始化失败: %s",
                ontology_id, e,
            )
            return counts, errors

        for kind, fn_name in self._TYPE_COUNT_SOURCES:
            try:
                r = getattr(svc, fn_name)(ontology_id)
            except Exception as e:
                errors.append(f"{kind}: {fn_name}({ontology_id}) 调用失败: {e}")
                logger.warning(
                    "统计本体类型 %s 失败（ontology_id=%s）: %s", kind, ontology_id, e,
                )
                continue

            if not isinstance(r, dict):
                errors.append(
                    f"{kind}: {fn_name} 返回了非 dict（{type(r).__name__}），无法解析"
                )
                logger.warning(
                    "统计本体类型 %s 返回非 dict（ontology_id=%s）: %r",
                    kind, ontology_id, r,
                )
                continue
            if r.get("status") == "error":
                # 被调方已按规则 2 返回错误状态，调用方必须读它，不能当作 0 条
                errors.append(f"{kind}: {r.get('message')}")
                logger.warning(
                    "统计本体类型 %s 返回错误（ontology_id=%s）: %s",
                    kind, ontology_id, r.get("message"),
                )
                continue
            # OntologyService.list_*_types 的契约是 {"<kind>": [...], "count": N}，
            # 只认 count；缺 count 说明契约变了，报出来而不是猜一个 0。
            if "count" not in r:
                errors.append(
                    f"{kind}: {fn_name} 返回缺少 count 字段（实际键={sorted(r)}）"
                )
                logger.warning(
                    "统计本体类型 %s 返回缺少 count（ontology_id=%s）: %r",
                    kind, ontology_id, r,
                )
                continue
            try:
                counts[kind] = int(r["count"] or 0)
            except (TypeError, ValueError) as e:
                errors.append(f"{kind}: count 字段不是整数: {e}")
                logger.warning(
                    "统计本体类型 %s 的 count 字段不是整数（ontology_id=%s）: %r",
                    kind, ontology_id, r.get("count"),
                )
        return counts, errors

    # ------------------------------------------------------------------
    # 2. run — 统一编排入口
    # ------------------------------------------------------------------
    async def run(
        self,
        *,
        source_type: str,
        ontology_id: Optional[str] = None,
        extraction_mode: str = "exploratory",
        template_ref: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        scenario_id: str = "",
        workspace_id: str = "default",
        actor: str = "system",
    ) -> Dict[str, Any]:
        """执行一次 pipeline。

        Args:
            source_type: 数据源类型（结构化/非结构化）
            ontology_id: 目标本体 ID（约束性抽取时必填）
            extraction_mode: constrained | exploratory
            template_ref: 模板名/路径（仅非结构化链路使用）
            payload: 各源所需参数（text/json/url/form_data/...）
            actor: 操作者标识

        Returns:
            {status, pipeline_run_id, source_kind, candidates, ...}
        """
        payload = payload or {}
        pipeline_run_id = str(uuid.uuid4())

        if not source_type:
            return {"status": "error", "message": "source_type 不能为空"}

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

        result["pipeline_run_id"] = pipeline_run_id
        if source_type in UNSTRUCTURED_SOURCE_TYPES:
            result["source_kind"] = "unstructured"
        elif source_type in INDICATOR_SOURCE_TYPES:
            result["source_kind"] = "indicator"
        else:
            # 含事件源（webhook/mcp/file/api）：run 级标签仍为 structured，
            # 候选 provenance.source_kind 才是 "event"（Task 2/3）。
            result["source_kind"] = "structured"
        result["source_type"] = source_type
        return result

    # ------------------------------------------------------------------
    # 链路 B：非结构化文档抽取
    # ------------------------------------------------------------------
    async def _run_unstructured(
        self,
        source_type: str,
        ontology_id: Optional[str],
        extraction_mode: str,
        template_ref: Optional[str],
        payload: Dict[str, Any],
        scenario_id: str,
        workspace_id: str,
        pipeline_run_id: str,
    ) -> Dict[str, Any]:
        if not ontology_id:
            return {"status": "error", "message": "非结构化抽取需要 ontology_id"}

        text = payload.get("text") or payload.get("content") or ""
        mode = payload.get("mode")
        if extraction_mode == "exploratory":
            # 探索性：启用 schema_learning，产出 L0 候选供后续审核
            mode = mode or "schema_learning"

        try:
            if source_type == "document" and payload.get("file_path"):
                ext_result = await self.extract_service.extract_from_document(
                    ontology_id=ontology_id,
                    file_path=payload.get("file_path"),
                    template_id=template_ref,
                    mode=mode,
                    workspace_id=workspace_id,
                )
            else:
                ext_result = await self.extract_service.extract_from_nl(
                    text=text,
                    ontology_id=ontology_id,
                    template_id=template_ref,
                    mode=mode,
                )
        except Exception as e:
            logger.error("非结构化抽取失败: %s", e)
            return {"status": "error", "message": f"抽取失败: {e}"}

        if ext_result.get("status") == "error":
            return ext_result

        merged = ext_result.get("result") or {}
        try:
            candidates = self._collect_candidates(
                merged,
                run_id=pipeline_run_id,
                template_ref=template_ref or ext_result.get("template_used", ""),
                ontology_id=ontology_id,
                source_kind="unstructured",
                domain_code=self._resolve_domain_code(ontology_id),
            )
        except RuntimeError as e:
            # 抽取成功但候选落库失败：抽取结果没进审核队列，等于白跑，
            # 必须显式报错而不是报 status=ok + candidate_count>0。
            logger.error("非结构化抽取候选落库失败（ontology_id=%s）: %s", ontology_id, e)
            return {
                "status": "error",
                "message": f"抽取完成但候选落库失败: {e}",
                "session_id": ext_result.get("session_id"),
            }

        return {
            "status": "ok",
            "session_id": ext_result.get("session_id"),
            "template_used": ext_result.get("template_used", template_ref),
            "candidate_count": len(candidates),
            "candidates": candidates,
            "degradation_flags": ext_result.get("degradation_flags", []),
        }

    # ------------------------------------------------------------------
    # 链路 A：结构化数据引入
    # ------------------------------------------------------------------
    async def _run_structured(
        self,
        source_type: str,
        ontology_id: Optional[str],
        extraction_mode: str,
        payload: Dict[str, Any],
        scenario_id: str,
        workspace_id: str,
        pipeline_run_id: str,
    ) -> Dict[str, Any]:
        kwargs = dict(payload)
        kwargs["ontology_id"] = ontology_id
        kwargs["extraction_mode"] = extraction_mode
        if scenario_id:
            kwargs.setdefault("scenario_id", scenario_id)
        if workspace_id:
            kwargs.setdefault("workspace_id", workspace_id)

        try:
            ingest_result = await self.ingest_facade.ingest(source_type, **kwargs)
        except Exception as e:
            logger.error("结构化引入失败: %s", e)
            return {"status": "error", "message": f"引入失败: {e}"}

        if ingest_result.get("status") == "error":
            return ingest_result

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
        if collected.get("status") == "error":
            # 引入成功但归集不出业务语义 —— 这是能力缺口，不是「0 条候选」的正常结果，
            # 必须显式报出，否则前端会显示"成功、0 条候选"而无人知道链路是断的。
            logger.error(
                "结构化引入成功但候选归集失败（source_type=%s）: %s",
                source_type, collected.get("message"),
            )
            return {
                "status": "error",
                "message": (
                    f"数据已引入但未能归集业务语义候选: {collected.get('message')}"
                ),
                "ingest": ingest_result,
            }

        return {
            "status": "ok",
            "ingest": ingest_result,
            "candidate_count": len(collected["records"]),
            "candidates": collected["records"],
            "collection_stats": collected["stats"],
            "collection_warnings": collected["warnings"],
        }

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

    # ------------------------------------------------------------------
    # 3. get_run — 查询 pipeline 产出
    # ------------------------------------------------------------------
    def get_run(self, pipeline_run_id: str) -> Dict[str, Any]:
        try:
            result = self.candidate_storage.list_candidates(
                pipeline_run_id=pipeline_run_id,
                page=1, page_size=500,
            )
            if isinstance(result, tuple):
                items, total = result
            elif isinstance(result, dict):
                items = list(result.get("items") or [])
                total = int(result.get("total") or len(items))
            else:
                items, total = [], 0
            return {
                "status": "ok",
                "pipeline_run_id": pipeline_run_id,
                "total": total,
                "candidates": items,
            }
        except Exception as e:
            return {"status": "error", "message": f"查询失败: {e}"}

    # ------------------------------------------------------------------
    # 4. submit — 提交审核
    # ------------------------------------------------------------------
    def submit(self, pipeline_run_id: str, *, actor: str = "system") -> Dict[str, Any]:
        """将 pipeline 下所有 DRAFT 候选提交审核（→ PENDING_REVIEW）。"""
        try:
            result = self.candidate_storage.list_candidates(
                pipeline_run_id=pipeline_run_id,
                page=1, page_size=500,
            )
            if isinstance(result, tuple):
                items, _ = result
            elif isinstance(result, dict):
                items = list(result.get("items") or [])
            else:
                items = []

            submitted = 0
            skipped = 0
            for c in items:
                if not isinstance(c, dict):
                    skipped += 1
                    continue
                cid = c.get("id")
                status = self.candidate_storage._norm_cand_status(
                    c.get("status") or ""
                )
                if status != CAND_DRAFT:
                    skipped += 1
                    continue
                ok = self.candidate_storage.update_candidate_status(
                    cid, CAND_PENDING_REVIEW
                )
                if ok:
                    submitted += 1
                else:
                    skipped += 1

            return {
                "status": "ok",
                "pipeline_run_id": pipeline_run_id,
                "submitted": submitted,
                "skipped": skipped,
            }
        except Exception as e:
            return {"status": "error", "message": f"提交审核失败: {e}"}

    # ------------------------------------------------------------------
    # 候选归集工具
    # ------------------------------------------------------------------
    def _resolve_domain_code(self, ontology_id: Optional[str]) -> str:
        """解析本体的 domain_code（ADR-079 §7 权威领域关联字段）。

        候选表列名是 domain_id，但语义对齐 USL 的 domain_code（Task #18 已把
        USL 写入归一为 code），故此处填 code，避免再制造一次 code/id 分裂。
        解析不到返回空串：候选 domain_id 落空后由质量闸打「未匹配领域」标签，
        而非按命名约定猜测性反推（规则 14 第 4 条）；读取失败记 warning（第 3 条）。
        """
        if not ontology_id:
            return ""
        try:
            from odap.biz.core.ontology.public import OntologyService
            res = OntologyService().get_ontology(ontology_id)
        except Exception as e:
            logger.warning("解析本体 %s 的 domain_code 失败: %s", ontology_id, e)
            return ""
        if not isinstance(res, dict) or res.get("status") == "error":
            logger.warning(
                "本体 %s 读取失败，候选 domain_id 将落空: %s",
                ontology_id, res.get("message") if isinstance(res, dict) else res,
            )
            return ""
        return str(res.get("domain_code") or "")

    def _collect_candidates(
        self,
        merged: Dict[str, Any],
        *,
        run_id: str,
        template_ref: str,
        ontology_id: Optional[str],
        source_kind: str,
        domain_code: str = "",
    ) -> List[Dict[str, Any]]:
        """把 ExtractService 的 5 类产出归集为候选记录并落库。"""
        type_keys = (
            ("object_types", "对象类型"),
            ("link_types", "关系类型"),
            ("action_types", "动作类型"),
            ("rule_types", "规则类型"),
            ("process_types", "过程类型"),
        )
        records: List[Dict[str, Any]] = []
        for key, semantic_type in type_keys:
            for item in merged.get(key, []) or []:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if not name:
                    continue
                records.append({
                    "run_id": run_id,
                    "domain_id": domain_code,
                    "canonical": str(name),
                    "semantic_type": semantic_type,
                    "definition": item.get("description", ""),
                    "synonyms": item.get("synonyms") or [],
                    "confidence": float(item.get("confidence", 0.0)),
                    "origin": "llm",
                    "source_text": item.get("source_text", ""),
                    "provenance": {
                        "source_kind": source_kind,
                        "source_template_id": template_ref,
                        "ontology_id": ontology_id,
                        "raw_item": item,
                    },
                })
        if records:
            # 落库失败绝不能当成成功：返回未持久化的候选会让调用方报出
            # candidate_count>0，而 get_run 再查时一条都没有（规则 14：假成功）。
            try:
                self.candidate_storage.bulk_insert_candidates(records)
            except Exception as e:
                logger.error("候选归集落库失败: %s", e)
                raise RuntimeError(
                    f"候选落库失败（{len(records)} 条未持久化）: {e}"
                ) from e
        return records

    def _resolve_ingest_documents(
        self, ingest_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """回捞结构化摄入产出的本体文档。

        UnifiedIngestFacade.ingest 只返回 record_id / event_id，**不含**抽取出的
        实体清单；但 _DocumentProcessor.process 会把整个 OntologyDocument（含
        entities / relations / events / actions / rules / constraints 全量）持久化到
        ontology_documents 表，而摄入记录的 extracted_data.document_ids 就是索引。
        注意 extracted_data 里的 entities/relations/events 是**计数**（int），
        不是清单，所以不能拿它当抽取产物用。

        Returns:
            {"documents": [...], "unreadable_doc_ids": [...], "error": Optional[str]}
            error 非空表示链路没交出它承诺的产物 —— 调用方必须显式失败，
            不得静默返回空清单再报 candidate_count=0（规则 14：失败必须显式）。
        """
        record_id = ingest_result.get("record_id") or ingest_result.get("event_id")
        if not record_id:
            return {
                "documents": [],
                "unreadable_doc_ids": [],
                "error": (
                    "结构化引入结果既无 record_id 也无 event_id，无法回捞抽取产物；"
                    f"实际返回键={sorted(ingest_result.keys())}"
                ),
            }

        record = self.ingest_service.get_ingest_status(record_id)
        if not record:
            return {
                "documents": [],
                "unreadable_doc_ids": [],
                "error": f"摄入记录不存在: {record_id}",
            }

        extracted = record.get("extracted_data") or {}
        doc_ids = list(extracted.get("document_ids") or [])
        if not doc_ids:
            return {
                "documents": [],
                "unreadable_doc_ids": [],
                "error": (
                    f"摄入记录 {record_id} 未产出任何本体文档"
                    f"（extracted_data.document_ids 为空，status={record.get('status')!r}）；"
                    "事件通道（webhook/sensor/mcp/file/api → PerceptionHub）"
                    "不生成 OntologyDocument，因此没有可归集的业务语义"
                ),
            }

        documents = []
        unreadable: List[str] = []
        for doc_id in doc_ids:
            doc = self.ingest_service.get_ontology_document(doc_id)
            if doc is None:
                unreadable.append(str(doc_id))
            else:
                documents.append(doc)
        if unreadable:
            # 部分文档读不回属于真实的数据不一致，必须留痕（规则 14 要求 3：≥ warning）
            logger.warning(
                "摄入记录 %s 声明 %d 个本体文档，其中 %d 个读不回: %s",
                record_id, len(doc_ids), len(unreadable), unreadable[:10],
            )
        return {"documents": documents, "unreadable_doc_ids": unreadable, "error": None}

    def _collect_structured_candidates(
        self,
        ingest_result: Dict[str, Any],
        *,
        run_id: str,
        ontology_id: Optional[str],
        source_kind: str,
        domain_code: str = "",
    ) -> Dict[str, Any]:
        """把结构化摄入产出的 OntologyDocument 归集为待审候选。

        历史缺陷：本方法曾读 `ingest_result["entities"] / ["items"]`，而
        UnifiedIngestFacade 从不返回这两个键 —— 14 种结构化源全部「引入成功、
        候选恒为 0」，却照报 status=ok。现改为按 record_id 回捞真实产物。

        Returns:
            {"status": "ok", "records": [...], "stats": {...}, "warnings": [...]}
            或 {"status": "error", "message": "..."}
        """
        resolved = self._resolve_ingest_documents(ingest_result)
        if resolved.get("error"):
            return {"status": "error", "message": resolved["error"]}

        documents = resolved["documents"]
        record_id = ingest_result.get("record_id") or ingest_result.get("event_id")
        base_prov = {
            "source_kind": source_kind,
            "ontology_id": ontology_id,
            "ingest_record_id": record_id,
        }

        # (semantic_type, canonical) → 候选，跨文档去重并合并同义词
        merged: Dict[tuple, Dict[str, Any]] = {}
        stats: Dict[str, int] = {}

        def _add(
            *, semantic_type: str, canonical: str, doc_id: str,
            definition: str = "", en: str = "", synonyms: Optional[List[str]] = None,
            source_text: str = "", extra_prov: Optional[Dict[str, Any]] = None,
        ) -> None:
            name = str(canonical or "").strip()
            if not name:
                return
            stats[semantic_type] = stats.get(semantic_type, 0) + 1
            key = (semantic_type, name)
            hit = merged.get(key)
            if hit is None:
                prov = dict(base_prov)
                prov["doc_id"] = doc_id
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
                    # 结构化源是逐字读出的事实，不是模型推断，故置信度 1.0
                    "confidence": 1.0,
                    "origin": "structured",
                    "source_text": source_text,
                    "provenance": prov,
                }
                return
            # 已存在：补空字段 + 合并同义词，不覆盖已有定义
            if not hit["definition"] and definition:
                hit["definition"] = definition
            if not hit["en"] and en:
                hit["en"] = en
            for s in synonyms or []:
                if s and s not in hit["synonyms"]:
                    hit["synonyms"].append(s)
            hit["provenance"].setdefault("merged_doc_ids", []).append(doc_id)

        # 直接取属性而非 getattr(x, "name", "")：doc 是真实的 OntologyDocument
        # dataclass（ADR-032），字段由 @dataclass 保证。用带默认值的 getattr 会让
        # 一次字段改名静默变成「候选恒为空 + status=ok」，正是本次要修的失效模式。
        for doc in documents:
            doc_id = str(doc.doc_id or "")

            for e in doc.entities:
                props = dict(e.basic_properties or {})
                _add(
                    semantic_type="对象类型",
                    canonical=e.name,
                    doc_id=doc_id,
                    en=e.name_en or "",
                    synonyms=list(e.aliases or []),
                    definition=str(props.get("description") or ""),
                    extra_prov={
                        "entity_id": e.entity_id,
                        "entity_type": e.entity_type,
                    },
                )
                # 实体的属性槽位也是业务语义（如 归属/状态/位置），归为「属性」
                for group, mapping in (
                    ("basic_properties", props),
                    ("statistical_properties", dict(e.statistical_properties or {})),
                ):
                    for prop_name in mapping:
                        _add(
                            semantic_type="属性",
                            canonical=str(prop_name),
                            doc_id=doc_id,
                            extra_prov={
                                "attribute_of": e.name,
                                "property_group": group,
                            },
                        )

            for r in doc.relations:
                _add(
                    semantic_type="关系类型",
                    canonical=r.relation_type,
                    doc_id=doc_id,
                    source_text=(
                        f"{r.source_entity} --[{r.relation_type}]--> {r.target_entity}"
                    ),
                    extra_prov={
                        "relation_id": r.relation_id,
                        "sample_source": r.source_entity,
                        "sample_target": r.target_entity,
                    },
                )

            for ev in doc.events:
                _add(
                    semantic_type="过程类型",
                    canonical=ev.event_type,
                    doc_id=doc_id,
                    definition=str(ev.description or ""),
                    extra_prov={
                        "event_id": ev.event_id,
                        "participants": list(ev.participants or []),
                    },
                )

            for a in doc.actions:
                _add(
                    semantic_type="动作类型",
                    canonical=a.action_type,
                    doc_id=doc_id,
                    source_text=f"{a.actor} 执行 {a.action_type} → {a.target}",
                    extra_prov={
                        "action_id": a.action_id,
                        "sample_actor": a.actor,
                        "sample_target": a.target,
                        "opa_required": bool(a.opa_required),
                    },
                )

            for ru in doc.rules:
                _add(
                    semantic_type="规则类型",
                    canonical=ru.rule_type,
                    doc_id=doc_id,
                    definition=str(ru.description or ""),
                    source_text=f"若 {ru.condition} 则 {ru.consequence}",
                    extra_prov={
                        "rule_id": ru.rule_id,
                        "priority": ru.priority,
                    },
                )
            # constraints 不入候选：USL 6 类语义类型里没有对应项，
            # 硬塞进某一类等于猜测性归类（规则 14 要求 4）。

        records = list(merged.values())
        warnings: List[str] = []
        if resolved.get("unreadable_doc_ids"):
            warnings.append(
                f"{len(resolved['unreadable_doc_ids'])} 个本体文档读不回，"
                f"归集结果不完整: {resolved['unreadable_doc_ids'][:10]}"
            )

        if records:
            # 落库失败绝不能当成成功：返回未持久化的候选会让调用方报出
            # candidate_count>0，而 get_run 再查时一条都没有（规则 14：假成功）。
            try:
                self.candidate_storage.bulk_insert_candidates(records)
            except Exception as e:
                logger.error("结构化候选归集落库失败: %s", e)
                return {
                    "status": "error",
                    "message": f"结构化候选落库失败（{len(records)} 条未持久化）: {e}",
                }

        return {
            "status": "ok",
            "records": records,
            "stats": {
                "documents": len(documents),
                "raw_items": sum(stats.values()),
                "deduped_candidates": len(records),
                "by_semantic_type": dict(stats),
            },
            "warnings": warnings,
        }

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


_singleton: Optional[SemanticAssetPipeline] = None


def get_semantic_asset_pipeline() -> SemanticAssetPipeline:
    global _singleton
    if _singleton is None:
        _singleton = SemanticAssetPipeline()
    return _singleton
