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
from typing import Any, Dict, List, Optional

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
        self._extract_service = None
        self._candidate_storage = None

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

    # ------------------------------------------------------------------
    # 1. options — 前端下拉选项
    # ------------------------------------------------------------------
    def options(self, ontology_id: Optional[str] = None) -> Dict[str, Any]:
        """返回 Pipeline 向导所需选项：数据源类型、模板列表、本体列表。"""
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

        ontologies: List[Dict[str, Any]] = []
        try:
            from odap.biz.core.ontology.ontology_api.services import OntologyService
            svc = OntologyService()
            res = svc.list_ontologies() if hasattr(svc, "list_ontologies") else {}
            if isinstance(res, dict):
                ontologies = list(res.get("ontologies") or res.get("items") or [])
            elif isinstance(res, list):
                ontologies = res
        except Exception as e:
            logger.warning("list_ontologies 失败: %s", e)

        return {
            "status": "ok",
            "source_types": {
                "structured": sorted(STRUCTURED_SOURCE_TYPES),
                "unstructured": sorted(UNSTRUCTURED_SOURCE_TYPES),
            },
            "templates": templates,
            "ontologies": ontologies,
        }

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
        elif source_type in STRUCTURED_SOURCE_TYPES:
            result = await self._run_structured(
                source_type, ontology_id, extraction_mode, payload,
                scenario_id, workspace_id, pipeline_run_id,
            )
        else:
            return {"status": "error", "message": f"未知数据源类型: {source_type}"}

        result["pipeline_run_id"] = pipeline_run_id
        result["source_kind"] = (
            "unstructured" if source_type in UNSTRUCTURED_SOURCE_TYPES else "structured"
        )
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
        candidates = self._collect_candidates(
            merged,
            run_id=pipeline_run_id,
            template_ref=template_ref or ext_result.get("template_used", ""),
            ontology_id=ontology_id,
            source_kind="unstructured",
        )

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

        # 结构化链路产出的候选：从 ingest 结果中尽力归集
        candidates = self._collect_structured_candidates(
            ingest_result,
            run_id=pipeline_run_id,
            ontology_id=ontology_id,
            source_kind="structured",
        )

        return {
            "status": "ok",
            "ingest": ingest_result,
            "candidate_count": len(candidates),
            "candidates": candidates,
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
    def _collect_candidates(
        self,
        merged: Dict[str, Any],
        *,
        run_id: str,
        template_ref: str,
        ontology_id: Optional[str],
        source_kind: str,
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
            try:
                self.candidate_storage.bulk_insert_candidates(records)
            except Exception as e:
                logger.warning("候选归集落库失败: %s", e)
        return records

    def _collect_structured_candidates(
        self,
        ingest_result: Dict[str, Any],
        *,
        run_id: str,
        ontology_id: Optional[str],
        source_kind: str,
    ) -> List[Dict[str, Any]]:
        """尽力从结构化 ingest 结果中归集候选（若结果含实体/类型列表）。"""
        records: List[Dict[str, Any]] = []
        # 常见产出字段
        entities = ingest_result.get("entities") or ingest_result.get("items") or []
        if isinstance(entities, list):
            for item in entities:
                if isinstance(item, str):
                    name = item
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("canonical")
                else:
                    continue
                if not name:
                    continue
                records.append({
                    "run_id": run_id,
                    "canonical": str(name),
                    "semantic_type": (
                        item.get("type") if isinstance(item, dict) else "对象类型"
                    ) or "对象类型",
                    "definition": (
                        item.get("description", "") if isinstance(item, dict) else ""
                    ),
                    "synonyms": [],
                    "confidence": 1.0,
                    "origin": "usl",
                    "source_text": "",
                    "provenance": {
                        "source_kind": source_kind,
                        "ontology_id": ontology_id,
                        "ingest_record_id": ingest_result.get("record_id")
                        or ingest_result.get("event_id"),
                    },
                })
        if records:
            try:
                self.candidate_storage.bulk_insert_candidates(records)
            except Exception as e:
                logger.warning("结构化候选归集落库失败: %s", e)
        return records


_singleton: Optional[SemanticAssetPipeline] = None


def get_semantic_asset_pipeline() -> SemanticAssetPipeline:
    global _singleton
    if _singleton is None:
        _singleton = SemanticAssetPipeline()
    return _singleton
