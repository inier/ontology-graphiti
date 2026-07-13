"""OL Pipeline 编排服务（L1→L2→L3→Quality Gate→Candidate Store写入）。

AGENTS.md §C 服务层规则：
  - 返回 Dict[str, Any]（扁平 dict，不含 Pydantic/Enum 对象
  - 错误格式 {"status": "error", "message": "..."}
  - 不在 services 层抛 HTTPException（routes 负责翻译
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
    from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage
    from ..interfaces import (
        L1TermExtractor, L2ConceptExtractor, L3Classifier,
    )


# Pipeline status 新枚举 → 旧枚举（服务层对外兼容暴露）
_RUN_STATUS_LEGACY = {
    "DRAFT":        "pending",
    "RUNNING":      "running",
    "L1_DONE":      "succeeded",
    "L2_DONE":      "succeeded",
    "L3_DONE":      "succeeded",
    "L4_DONE":      "succeeded",
    "L5_DONE":      "succeeded",
    "L6_DONE":      "succeeded",
    "COMPLETED":    "succeeded",
    "FAILED":       "failed",
}


def _run_to_legacy(run: Dict[str, Any]) -> Dict[str, Any]:
    """storage 层的 run dict → legacy status 翻译 + stats_json 解析为 stats dict."""
    import json as _json
    if not isinstance(run, dict):
        return run
    out = dict(run)
    s = out.get("status")
    if isinstance(s, str) and s in _RUN_STATUS_LEGACY:
        out["status"] = _RUN_STATUS_LEGACY[s]
    stats = out.get("stats")
    if not isinstance(stats, dict):
        sj = out.get("stats_json")
        if isinstance(sj, dict):
            out["stats"] = sj
        elif isinstance(sj, str) and sj:
            try:
                out["stats"] = _json.loads(sj)
            except Exception:
                out["stats"] = {}
        else:
            out["stats"] = {}
    return out


class PipelineService:
    """Pipeline 执行编排。

    8 步编排（Spec 007 Iter 2 实现 L1~L5，L6 写回 Iter 3 接入）：
      1. RUN_PENDING → RUNNING：元数据
      2. L1：术语抽取
      3. L2：概念合并
      4. L3：分类
      5. L4：关系抽取（Approach A 规则版）
      6. L5：模式归纳（基数 + 不相交草图打标）
      7. Quality Gate：按置信度打 grade(A/B/C/D)
      8. ol_candidates + quality_reports 写入 + 生成审批任务 + stats 更新
    """

    def __init__(
        self,
        *,
        candidate_storage: Optional["SQLiteCandidateStorage"] = None,
        usl_storage: Optional["SQLiteUslStorage"] = None,
        l1_extractor: Optional["L1TermExtractor"] = None,
        l2_merger: Optional["L2ConceptExtractor"] = None,
        l3_classifier: Optional["L3Classifier"] = None,
        l4_extractor: Optional[Any] = None,
        l5_inferrer: Optional[Any] = None,
        l3fca_analyzer: Optional[Any] = None,
        l5_fusion_service: Optional[Any] = None,
        l6_axiom_deriver: Optional[Any] = None,
    ) -> None:
        # 延迟注入：默认真实依赖（零 config 初始化默认用内建实现）
        if candidate_storage is None:
            from odap.biz.semantic_admin.candidate_store.storage import Storage as _CS
            candidate_storage = _CS()
        self.candidate_storage = candidate_storage

        if usl_storage is None:
            from odap.biz.semantic_admin.usl_manager.storage import Storage as _US
            usl_storage = _US()
        self.usl_storage = usl_storage

        if l1_extractor is None:
            from ..impl import NgramTermExtractor
            l1_extractor = NgramTermExtractor()
        self.l1 = l1_extractor
        if l2_merger is None:
            from ..impl import ConceptMergeEngine
            l2_merger = ConceptMergeEngine()
        self.l2 = l2_merger
        if l3_classifier is None:
            from ..impl import RuleBasedClassifier
            l3_classifier = RuleBasedClassifier()
        self.l3 = l3_classifier
        if l4_extractor is None:
            from ..impl import RuleBasedRelationExtractor
            l4_extractor = RuleBasedRelationExtractor()
        self.l4 = l4_extractor
        if l5_inferrer is None:
            from ..impl import RuleBasedPatternInferrer
            l5_inferrer = RuleBasedPatternInferrer()
        self.l5 = l5_inferrer
        # I4T1/I4T3/I4T4 新增 impl
        if l3fca_analyzer is None:
            from ..impl.l3_formal_concept import FormalConceptAnalyzer
            l3fca_analyzer = FormalConceptAnalyzer()
        self.l3fca = l3fca_analyzer
        if l5_fusion_service is None:
            from ..impl.l5_ontology_fusion import OntologyFusionService
            l5_fusion_service = OntologyFusionService()
        self.l5_fusion = l5_fusion_service
        if l6_axiom_deriver is None:
            from ..impl.l6_axiom_deriver import AxiomDeriver
            l6_axiom_deriver = AxiomDeriver()
        self.l6_axioms = l6_axiom_deriver

    def create_run(self, **kwargs) -> Dict[str, Any]:
        """创建 pipeline run。kwargs 对齐 storage.create_pipeline_run 签名。
        错误用 {"status":"error"} 格式返回。
        """
        try:
            if "workspace_id" not in kwargs or not kwargs["workspace_id"]:
                return {"status": "error", "message": "缺少必填参数 workspace_id"}
            return _run_to_legacy(self.candidate_storage.create_pipeline_run(**kwargs))
        except Exception as e:  # pragma: no cover
            return {"status": "error", "message": f"创建 Pipeline Run 失败: {e}"}

    def get_run(self, run_id: str) -> Dict[str, Any]:
        try:
            r = self.candidate_storage.get_pipeline_run(run_id)
            if not r:
                return {"status": "error", "message": f"Pipeline Run {run_id} 不存在"}
            return _run_to_legacy(r)
        except Exception as e:  # pragma: no cover
            return {"status": "error", "message": f"读取 Run 失败: {e}"}

    def list_runs(
        self,
        *,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        try:
            result = self.candidate_storage.list_pipeline_runs(
                workspace_id=workspace_id, status=status,
                page=page, page_size=page_size,
            )
            if isinstance(result, dict) and isinstance(result.get("items"), list):
                out = dict(result)
                out["items"] = [_run_to_legacy(r) for r in result["items"]]
                return out
            return result
        except Exception as e:  # pragma: no cover
            return {"status": "error", "message": f"列出 Runs 失败: {e}"}

    # ------------------------------------------------------------------
    # 核心：同步执行 Pipeline（Iter 2 默认同步）→ 调用者可 asyncio 异步封装
    # ------------------------------------------------------------------
    def run_pipeline(
        self,
        *,
        workspace_id: str,
        text: Optional[str] = None,
        extra_docs: Optional[List[str]] = None,
        ontology_id: Optional[str] = None,
        source_type: str = "natural_language",
        source_ref: Optional[str] = None,
        triggered_by: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """同步执行整个 pipeline（Iter 2 全程 CPU 密集型；Iter 3 将拆到后台任务。

        Returns:
            { "pipeline_run_id": str, "status": succeeded|failed|...,
              "output": {...}, "timing_ms": {...}, "candidate_count": int}
        """
        cfg = config or {}
        timing: Dict[str, float] = {}
        run: Optional[Dict[str, Any]] = None
        run_id: str = ""
        # Step 0: 初始化 Run 元数据
        t0 = time.perf_counter()
        total_chars = len(text or "") + sum(len(d or "") for d in (extra_docs or []))
        try:
            run = self.create_run(
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                source_type=source_type,
                source_ref=source_ref,
                triggered_by=triggered_by,
                total_input_chars=total_chars,
            )
            if run.get("status") == "error":
                return run
            run_id = run["id"]
            timing["meta_ms"] = int((time.perf_counter() - t0) * 1000)
            self.candidate_storage.update_pipeline_run_status(
                run_id, status="running", progress=1,
            )
            self.candidate_storage.append_audit_log(
                action="pipeline_started",
                actor=triggered_by or "system",
                pipeline_run_id=run_id,
                payload={
                    "workspace_id": workspace_id,
                    "ontology_id": ontology_id,
                    "input_chars": total_chars,
                },
            )

            # Step 1: L1 术语抽取
            t1 = time.perf_counter()
            self.candidate_storage.update_pipeline_run_status(
                run_id, status="running", progress=10,
            )
            tokens = self.l1.extract(
                text=(text or ""),
                extra_docs=(extra_docs or []),
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                config=cfg.get("l1"),
            )
            timing["l1_ms"] = int((time.perf_counter() - t1) * 1000)
            self.candidate_storage.append_audit_log(
                action="pipeline_l1_done",
                pipeline_run_id=run_id,
                payload={"token_count": len(tokens)},
            )
            # Step 2: L2 概念合并
            t2 = time.perf_counter()
            self.candidate_storage.update_pipeline_run_status(
                run_id, status="running", progress=35,
            )
            # 注入USL已有术语去重 —— storage 返回 Tuple[List, int]
            existing_items, _total = self.usl_storage.list_terms(page=1, page_size=1000000)
            concepts = self.l2.merge(
                tokens,
                existing_usl_terms=[
                    {"canonical": t.get("canonical"),
                     "synonyms": t.get("synonyms") or []}
                    for t in existing_items
                ],
                config=cfg.get("l2"),
            )
            timing["l2_ms"] = int((time.perf_counter() - t2) * 1000)
            self.candidate_storage.append_audit_log(
                action="pipeline_l2_done",
                pipeline_run_id=run_id,
                payload={"concept_count": len(concepts)},
            )

            # Step 3: L3 分类
            t3 = time.perf_counter()
            self.candidate_storage.update_pipeline_run_status(
                run_id, status="running", progress=60,
            )
            # 获取 domain 列表供 L3 域匹配 —— storage 返回 Tuple[List, int]
            domain_items, _dcount = self.usl_storage.list_domains(page=1, page_size=1000)
            classified = self.l3.classify(
                concepts,
                domains=domain_items,
                config=cfg.get("l3"),
            )
            timing["l3_ms"] = int((time.perf_counter() - t3) * 1000)
            self.candidate_storage.append_audit_log(
                action="pipeline_l3_done",
                pipeline_run_id=run_id,
                payload={"classified_count": len(classified)},
            )
            entity_candidates = classified
            # L1/L2/L3 stats 初始写入
            self.candidate_storage.update_pipeline_run_stats(
                run_id,
                stats_update={
                    "L1_tokens": len(tokens),
                    "L2_concepts": len(concepts),
                    "L3_entities": len(entity_candidates),
                },
            )

            # Step 3b: L4 关系抽取（同句共现 + 规则短语）
            t3b = time.perf_counter()
            self.candidate_storage.update_pipeline_run_status(
                run_id, status="running", progress=72,
            )
            l4_results = self.l4.extract(
                text=(text or ""),
                extra_docs=(extra_docs or []),
                entity_candidates=entity_candidates,
                config=cfg.get("l4"),
            )
            timing["l4_ms"] = int((time.perf_counter() - t3b) * 1000)
            self.candidate_storage.append_audit_log(
                action="pipeline_l4_done",
                pipeline_run_id=run_id,
                payload={"relation_count": len(l4_results)},
            )

            # Step 3c: L5 模式归纳（基数估计 + 不相交草图；in-place 注入 provenance）
            t3c = time.perf_counter()
            self.candidate_storage.update_pipeline_run_status(
                run_id, status="running", progress=82,
            )
            l4_l5_results = self.l5.infer(
                relation_candidates=l4_results,
                entity_candidates=entity_candidates,
                config=cfg.get("l5"),
            )
            l5_pattern_cnt = sum(
                1 for c in l4_l5_results
                if "L5_cardinality_estimate" in (c.get("provenance") or {})
            )
            timing["l5_ms"] = int((time.perf_counter() - t3c) * 1000)
            self.candidate_storage.append_audit_log(
                action="pipeline_l5_done",
                pipeline_run_id=run_id,
                payload={
                    "relation_count": len(l4_l5_results),
                    "pattern_count": l5_pattern_cnt,
                },
            )
            # 合并 entity + relation 为全量候选集合
            merged_candidates: List[Dict[str, Any]] = list(entity_candidates) + list(
                l4_l5_results
            )
            self.candidate_storage.update_pipeline_run_stats(
                run_id,
                stats_update={
                    "L4_relations": len(l4_l5_results),
                    "L5_patterns": l5_pattern_cnt,
                },
            )

            # Step 4: Quality Gate（规则分档A/B/C/D → 写入 quality_reports
            t4 = time.perf_counter()
            self.candidate_storage.update_pipeline_run_status(
                run_id, status="running", progress=90,
            )

            grade_map: Dict[str, Dict[str, Any]] = {}
            for c in merged_candidates:
                grade, scores = self._quality_grade(c)
                grade_map[c["canonical"]] = scores
                # 写入 candidate（status 初始按 grade 映射
                if grade == "D":
                    cstatus = "rejected"  # D级不产生审批
                elif grade == "A":
                    cstatus = "approved"  # A级自动批准（自动写回候选项）
                else:
                    cstatus = "gated"  # B/C 级送入审批
                c["pipeline_run_id"] = run_id
                c["status"] = cstatus
            # 批量写入 candidate（每个 candidate 然后生成quality_report
            inserted = self.candidate_storage.bulk_insert_candidates(merged_candidates)
            for c, cand in zip(merged_candidates, inserted):
                scores = grade_map.get(c["canonical"], {})
                if not scores:
                    continue
                self.candidate_storage.save_quality_report({
                    "candidate_id": cand["id"],
                    "overall_score": scores["overall"],
                    "novelty_score": scores.get("novelty"),
                    "completeness_score": scores.get("completeness"),
                    "orthogonality_score": scores.get("orthogonality"),
                    "consistency_score": scores.get("consistency"),
                    "grade": scores["grade"],
                    "risk_tags": scores.get("risk_tags") or [],
                    "suggestions": scores.get("suggestions") or [],
                })
                # 生成审批任务（B=1级/C=2级）
                grade = scores["grade"]
                level = {"B": 1, "C": 2}.get(grade)
                if level is not None:
                    self.candidate_storage.create_approval_task(
                        candidate_id=cand["id"], level=level,
                    )
            timing["gate_ms"] = int((time.perf_counter() - t4) * 1000)
            self.candidate_storage.append_audit_log(
                action="pipeline_quality_done",
                pipeline_run_id=run_id,
                payload={
                    "inserted": len(inserted),
                    "grade_counts": {
                        g: sum(1 for s in grade_map.values() if s["grade"] == g)
                        for g in "ABCD"
                    },
                },
            )
            self.candidate_storage.update_pipeline_run_stats(
                run_id,
                stats_update={
                    "total_candidates": len(inserted),
                    "grades": {
                        g: sum(1 for s in grade_map.values() if s["grade"] == g)
                        for g in "ABCD"
                    },
                },
            )

            # Step 5: 更新 Run 成功
            self.candidate_storage.update_pipeline_run_status(
                run_id,
                status="succeeded",
                progress=100,
                total_output_candidates=len(inserted),
            )
            self.candidate_storage.append_audit_log(
                action="pipeline_succeeded",
                pipeline_run_id=run_id,
                payload={"candidates": len(inserted)},
            )
            timing["total_ms"] = int((time.perf_counter() - t0) * 1000)
            run_record = self.candidate_storage.get_pipeline_run(run_id) or {}
            return {
                "pipeline_run_id": run_id,
                "status": "succeeded",
                "candidate_count": len(inserted),
                "timing_ms": timing,
                "run_meta": run,
                "stats": (run_record.get("stats") if isinstance(run_record, dict) else {}),
            }
        except Exception as e:
            msg = f"Pipeline失败: {e}"
            if run_id:
                self.candidate_storage.update_pipeline_run_status(
                    run_id, status="failed", error_message=msg,
                )
                self.candidate_storage.append_audit_log(
                    action="pipeline_failed",
                    pipeline_run_id=run_id,
                    payload={"error": msg},
                )
            return {"status": "error", "message": msg}

    # ------------------------------------------------------------------
    # Quality Gate：内部分档
    # ------------------------------------------------------------------
    @staticmethod
    def _quality_grade(cand: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """基于candidate.confidence + 字段完整性分档 A/B/C/D。

        Returns:
            (grade: "A" | "B" | "C" | "D", scores: dict_of_scores)
        """
        conf = float(cand.get("confidence") or 0.0)
        synonyms_cnt = len(cand.get("synonyms") or [])
        has_def = 1.0 if cand.get("definition") else 0.0
        has_examples = min(1.0, len(cand.get("examples") or []) / 3.0)
        has_domain = 1.0 if cand.get("domain_id") else 0.2

        novelty = min(1.0, conf)
        completeness = round(0.4 * min(1.0, synonyms_cnt / 3.0) + 0.4 * has_def + 0.2 * has_examples, 3)
        orthogonality = 1.0 if not bool(cand.get("stoplist_flag")) else 0.1
        consistency = min(1.0, 0.7 * has_domain + 0.3 * (1.0 if cand.get("semantic_type") else 0.0))

        overall = round(
            0.5 * conf + 0.2 * completeness + 0.2 * novelty + 0.1 * consistency, 4
        )
        risks: List[str] = []
        suggestions: List[str] = []
        if cand.get("stoplist_flag"):
            risks.append("命中停用词")
            suggestions.append("人工确认是否为停用词")
        if not cand.get("domain_id"):
            risks.append("未匹配领域")
            suggestions.append("人工指定domain_id")
        if not cand.get("definition"):
            risks.append("无定义")
            suggestions.append("补充definition")

        if overall >= 0.82 and not risks:
            grade = "A"
        elif overall >= 0.62:
            grade = "B"
        elif overall >= 0.38:
            grade = "C"
        else:
            grade = "D"
        scores = {
            "grade": grade,
            "overall": overall,
            "novelty": round(novelty, 4),
            "completeness": completeness,
            "orthogonality": round(orthogonality, 4),
            "consistency": round(consistency, 4),
            "risk_tags": risks,
            "suggestions": suggestions,
        }
        return grade, scores

    # ======================================================================
    # I4T5: L3~L6 单步 execute 方法 + 状态机补全
    # ======================================================================

    def _load_run_inputs(self, run_id: str) -> Dict[str, Any]:
        """加载 run 基础输入 + 所有候选。返回 {run_doc, candidates, entities_only}."""
        run = self.candidate_storage.get_pipeline_run(run_id) or {}
        candidates: List[Dict[str, Any]] = []
        # 全量加载（page_size 设大）
        try:
            res = self.candidate_storage.list_candidates(
                run_id=run_id, page=1, page_size=10_000,
            )
            if isinstance(res, dict) and isinstance(res.get("items"), list):
                candidates = list(res["items"])
        except Exception:
            candidates = []
        entities_only = [c for c in candidates if str(c.get("semantic_type") or "") != "关系类型"]
        relations_only = [c for c in candidates if str(c.get("semantic_type") or "") == "关系类型"]
        return {
            "run": run,
            "candidates": candidates,
            "entities": entities_only,
            "relations": relations_only,
        }

    def execute_l3(self, *, run_id: str, **_: Any) -> Dict[str, Any]:
        """L3 FCA 形式概念分析（I4T1）。

        输入：candidates 的 entities + properties
        输出：stats 更新 l3_concept_count / l3_suggested_edges / l3_context_size
        """
        ins = self._load_run_inputs(run_id)
        entities = ins["entities"]
        if not entities:
            return {
                "status": "ok",
                "level": "L3",
                "formal_concepts": [],
                "suggested_hierarchy_edges": [],
                "concept_count": 0,
                "stats_patch": {
                    "L3": "ok",
                    "l3_concept_count": 0,
                    "l3_suggested_edges": 0,
                },
            }
        result = self.l3fca.analyze(
            entities,
            attribute_fields=(
                "semantic_type", "synonyms", "domain_id",
                "definition", "tags", "near_synonyms",
            ),
            min_stability=0.0,
        )
        return {
            "status": "ok",
            "level": "L3",
            "formal_concepts": result.get("formal_concepts", []),
            "suggested_hierarchy_edges": result.get("suggested_hierarchy_edges", []),
            "concept_count": result.get("lattice_count", 0),
            "stats_patch": {
                "L3": "ok",
                "l3_concept_count": int(result.get("lattice_count", 0)),
                "l3_suggested_edges": int(len(result.get("suggested_hierarchy_edges", []))),
                "l3_context_size": result.get("context_size", {}),
            },
        }

    def execute_l4(self, *, run_id: str, **_: Any) -> Dict[str, Any]:
        """L4 关系抽取 + 4 类类型分类（I4T2）。

        若 run_pipeline 时已经写入 relations，该方法做一次 4 类型分类统计增量打标。
        若 candidates 中无关系，调用 self.l4.extract 从 source/source_text 现抽。
        输出：l4_relations_by_type 统计 dict。
        """
        ins = self._load_run_inputs(run_id)
        run_doc = ins["run"] or {}
        relations: List[Dict[str, Any]] = list(ins["relations"])
        entities = ins["entities"]
        # 如果 candidates 里没有关系，尝试从 source_text 抽取（兜底）
        if not relations:
            text_blob = " ".join([
                str(run_doc.get("source_text") or ""),
                str(run_doc.get("source") or ""),
                str(run_doc.get("corpus") or ""),
            ]).strip()
            if text_blob and entities:
                relations = self.l4.extract(
                    text=text_blob,
                    entity_candidates=entities,
                ) or []
        # 统计 4 类关系数量
        counts = {"is_a": 0, "part_of": 0, "attribute_of": 0, "related_to": 0}
        for r in relations:
            prov = r.get("provenance") or {}
            rt = str(prov.get("relation_type") or "")
            if rt not in counts:
                rt = "related_to"
            counts[rt] = counts.get(rt, 0) + 1
        stats_patch: Dict[str, Any] = {
            "L4": "ok",
            "l4_relation_count": len(relations),
            "l4_relations_by_type": counts,
        }
        return {
            "status": "ok",
            "level": "L4",
            "relations": relations,
            "relation_count": len(relations),
            "relations_by_type": counts,
            "stats_patch": stats_patch,
        }

    def execute_l5(
        self,
        *,
        run_id: str,
        existing_terms_limit: int = 5000,
        **_: Any,
    ) -> Dict[str, Any]:
        """L5 本体融合：candidates vs USL 术语 → 三分类（I4T3）。

        输出：l5_merged_count / l5_flagged_count / l5_kept_new_count。
        """
        ins = self._load_run_inputs(run_id)
        cands = ins["candidates"]
        if not cands:
            return {
                "status": "ok",
                "level": "L5",
                "fusion_decisions": [],
                "merged_count": 0, "flagged_count": 0, "kept_new_count": 0,
                "stats_patch": {"L5": "ok", "l5_merged_count": 0,
                                "l5_flagged_count": 0, "l5_kept_new_count": 0},
            }
        # 加载 USL 已有术语（top existing_terms_limit）
        existing: List[Dict[str, Any]] = []
        try:
            # SQLiteUslStorage.list_terms 返回 Tuple[List[dict], int]
            # 不接受 workspace_id 参数；USL 已经按 storage 实例隔离
            usl_res = self.usl_storage.list_terms(
                page=1, page_size=int(existing_terms_limit),
            )
            if isinstance(usl_res, tuple):
                lst = usl_res[0] if isinstance(usl_res[0], list) else []
                existing = list(lst)
            elif isinstance(usl_res, list):
                existing = usl_res
            elif isinstance(usl_res, dict):
                existing = list(usl_res.get("items") or usl_res.get("terms") or [])
        except Exception:
            existing = []
        decisions = self.l5_fusion.fuse_candidates(
            new_candidates=cands,
            existing_terms=existing,
        )
        mc = sum(1 for d in decisions if d["decision"] == "merge")
        fc = sum(1 for d in decisions if d["decision"] == "flag_conflict")
        kc = sum(1 for d in decisions if d["decision"] == "keep_as_new")
        return {
            "status": "ok",
            "level": "L5",
            "fusion_decisions": decisions,
            "merged_count": mc,
            "flagged_count": fc,
            "kept_new_count": kc,
            "stats_patch": {
                "L5": "ok",
                "l5_merged_count": mc,
                "l5_flagged_count": fc,
                "l5_kept_new_count": kc,
            },
        }

    def execute_l6(self, *, run_id: str, **_: Any) -> Dict[str, Any]:
        """L6 OWL 风格公理推导（I4T4）。5 类公理 + 统计。

        输入：L3 suggested_hierarchy_edges + L4 relations + L5 提示
        输出：l6_axiom_total / l6_axioms_by_type
        """
        # 先分别执行 L3 L4 保证有新鲜输入（安全幂等：各自都 <=1s 量级 小数据）
        l3_res = self.execute_l3(run_id=run_id)
        l4_res = self.execute_l4(run_id=run_id)
        # hierarchy: L3 suggested_edges + L4 is_a relations
        hierarchy: List[Dict[str, Any]] = []
        for e in (l3_res.get("suggested_hierarchy_edges") or []):
            concepts = l3_res.get("formal_concepts") or []
            fi = int(e.get("from_concept_index", 0))
            ti = int(e.get("to_parent_index", 0))
            if 0 <= fi < len(concepts) and 0 <= ti < len(concepts):
                child_ext = concepts[fi].get("extent") or []
                par_ext = concepts[ti].get("extent") or []
                if child_ext and par_ext:
                    ",".join(child_ext[:3])
                    par_name = ",".join(par_ext[:3])
                    # 不用整个拼接，直接用每个 child extent 的 canonical 单独加边
                    for c in child_ext[:5]:
                        hierarchy.append({
                            "child": str(c),
                            "parent": par_name,
                            "relation_type": "is_a",
                            "confidence": 0.7,
                            "source": "l3_fca_edge",
                        })
        # L4 is_a relations → 直接加 hierarchy
        for r in l4_res.get("relations") or []:
            prov = r.get("provenance") or {}
            if prov.get("relation_type") == "is_a":
                hierarchy.append({
                    "child": prov.get("subject_canonical", ""),
                    "parent": prov.get("object_canonical", ""),
                    "confidence": float(prov.get("relation_type_score") or 0.7),
                    "source": "l4_relation_is_a",
                })
        # 关系：transform l4 provenance -> axiom format
        relations_axiom: List[Dict[str, Any]] = []
        for r in l4_res.get("relations") or []:
            prov = r.get("provenance") or {}
            if not prov:
                continue
            relations_axiom.append({
                "subject_canonical": prov.get("subject_canonical", ""),
                "object_canonical": prov.get("object_canonical", ""),
                "relation_phrase": prov.get("relation_phrase", ""),
                "relation_type": prov.get("relation_type", "related_to"),
                "source_count": int(prov.get("frequency") or 1),
            })
        # 语义类型 hint（from candidates）
        term_semantic_types: Dict[str, str] = {}
        ins = self._load_run_inputs(run_id)
        for c in ins.get("candidates", []):
            canon = str(c.get("canonical") or "").strip()
            st = str(c.get("semantic_type") or "").strip()
            if canon and st:
                term_semantic_types[canon] = st
        # Hints: L5 fusion flag_conflict 且 best_match exact same name but different type → disjoint
        disjoint_hints: List[Dict[str, Any]] = []
        try:
            l5_res = self.execute_l5(run_id=run_id)
            for d in l5_res.get("fusion_decisions") or []:
                if d["decision"] == "flag_conflict":
                    bm = d.get("best_match") or {}
                    if bm and (bm.get("match_reason") or {}).get("exact_canonical_match"):
                        disjoint_hints.append({
                            "a": d["candidate_canonical"],
                            "b": bm["term_canonical"],
                            "reason": "cross_type_conflict_fusion",
                            "confidence": 0.88,
                        })
        except Exception:
            pass
        result = self.l6_axioms.derive(
            hierarchy=hierarchy,
            relations=relations_axiom,
            disjoint_pair_hints=disjoint_hints,
            term_semantic_types=term_semantic_types,
        )
        return {
            "status": "ok",
            "level": "L6",
            "axioms": result.get("axioms", []),
            "total": int(result.get("total", 0)),
            "counts_by_type": dict(result.get("counts_by_type", {})),
            "stats_patch": {
                "L6": "ok",
                "l6_axiom_total": int(result.get("total", 0)),
                "l6_axioms_by_type": dict(result.get("counts_by_type", {})),
            },
        }

    # ======================================================================
    # A5-1: advance_run + execute_all（B3 契约）
    # ======================================================================

    # 当前已完成层级的顺序（用于比较 target_step 是否 < 当前）
    _STEP_ORDER = ["DRAFT", "RUNNING", "L1_DONE", "L2_DONE", "L3_DONE",
                   "L4_DONE", "L5_DONE", "L6_DONE", "COMPLETED", "FAILED"]
    _TARGET_STEP_MAP = {
        "L1": "L1_DONE", "L2": "L2_DONE", "L3": "L3_DONE",
        "L4": "L4_DONE", "L5": "L5_DONE", "L6": "L6_DONE",
    }
    _NEXT_STEP = {
        "DRAFT": "L1_DONE", "RUNNING": "L1_DONE",
        "L1_DONE": "L2_DONE", "L2_DONE": "L3_DONE",
        "L3_DONE": "L4_DONE", "L4_DONE": "L5_DONE",
        "L5_DONE": "L6_DONE", "L6_DONE": "COMPLETED",
    }
    _NOT_IMPL_MSG = "Iter2 not deliver L{idx} classifier"

    def advance_run(
        self,
        *,
        run_id: str,
        target_step: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /pipeline/runs/{id}/advance

        target_step ∈ {None, 'L1','L2','L3','L4','L5','L6'}，None = 自动推进到下一步。
        幂等：若 run 已是 COMPLETED/FAILED 则直接返回，不报错。
        若 target_step < 当前已完成层级（按 status L1_DONE < L2_DONE ... 顺序），视为幂等直接返回。
        """
        try:
            run = self.candidate_storage.get_pipeline_run(run_id)
            if not run:
                return {"status": "error", "message": f"Pipeline Run {run_id} 不存在",
                        "code": "RUN_NOT_FOUND_404"}
            cur_status = str(run.get("status") or "DRAFT")
            stats_for_check: Dict[str, Any] = dict(run.get("stats_json") or run.get("stats") or {})
            _done_flags = {"ok", "skipped", "error"}
            _levels = ("L3", "L4", "L5", "L6")
            layers_incomplete = any(
                (lv not in stats_for_check) or (stats_for_check[lv] not in _done_flags)
                for lv in _levels
            )
            # 翻译：如果是 legacy status（succeeded/pending/running/failed）→ 转成新枚举
            cur_norm = self.candidate_storage._norm_run_status(cur_status)

            # 终止态：幂等直接返回 —— 但如果 L3~L6 未跑过，则视为非终止，回退到 L2_DONE 再推进
            if cur_norm in ("COMPLETED", "FAILED") and not layers_incomplete:
                return _run_to_legacy(run)
            if layers_incomplete and cur_norm == "COMPLETED":
                cur_norm = "L2_DONE"

            # 解析 target_step
            if target_step is None:
                target_norm = self._NEXT_STEP.get(cur_norm, "COMPLETED")
            else:
                ts_upper = str(target_step).upper()
                target_norm = self._TARGET_STEP_MAP.get(ts_upper)
                if not target_norm:
                    return {"status": "error", "message": f"非法 target_step={target_step}",
                            "code": "STEP_OUT_OF_ORDER_400"}

            # 比较顺序：若 target <= 当前，幂等返回
            try:
                cur_idx = self._STEP_ORDER.index(cur_norm)
            except ValueError:
                cur_idx = 0
            # 若 L3~L6 未完成，强制 cur_idx 不超过 L2_DONE(index=3)
            if layers_incomplete:
                cur_idx = min(cur_idx, 3)
            try:
                tgt_idx = self._STEP_ORDER.index(target_norm)
            except ValueError:
                tgt_idx = len(self._STEP_ORDER) - 1
            if tgt_idx <= cur_idx:
                return _run_to_legacy(run)

            # 推进：从当前的下一步 → 到 target，逐层执行
            error_msg: Optional[str] = None
            stats_patch: Dict[str, Any] = dict(run.get("stats_json") or run.get("stats") or {})
            # L1 -> index 2, L6 -> index 7
            start_process_idx = cur_idx + 1 if cur_idx < 7 else 2
            end_process_idx = tgt_idx
            for si in range(max(2, start_process_idx), min(8, end_process_idx + 1)):
                step_done_name = self._STEP_ORDER[si]  # e.g. L1_DONE
                lvl_num = step_done_name[0]  # 'L1'
                int(step_done_name[1])  # 1
                # L1/L2 已在 run_pipeline 真实执行；advance_run 语义 = 状态推进
                step_error: Optional[str] = None
                step_result: Optional[Dict[str, Any]] = None
                try:
                    if step_done_name == "L3_DONE":
                        step_result = self.execute_l3(run_id=run_id)
                    elif step_done_name == "L4_DONE":
                        step_result = self.execute_l4(run_id=run_id)
                    elif step_done_name == "L5_DONE":
                        step_result = self.execute_l5(run_id=run_id)
                    elif step_done_name == "L6_DONE":
                        step_result = self.execute_l6(run_id=run_id)
                except Exception as exc:
                    step_error = f"{lvl_num} execute failed: {exc}"
                if step_result and isinstance(step_result.get("stats_patch"), dict):
                    for k, v in step_result["stats_patch"].items():
                        stats_patch[k] = v
                    # 清空 skipped_reasons for that level
                    if "skipped_reasons" in stats_patch and lvl_num in stats_patch["skipped_reasons"]:
                        del stats_patch["skipped_reasons"][lvl_num]
                elif step_error:
                    stats_patch[lvl_num] = "error"
                    stats_patch.setdefault("errors", {})
                    stats_patch["errors"][lvl_num] = step_error
                    if error_msg:
                        error_msg = f"{error_msg}; {step_error}"
                    else:
                        error_msg = step_error
                # 状态推进
                self.candidate_storage.update_pipeline_run_status(
                    run_id, status=step_done_name,
                    progress=min(100, int(100 * (si / 7.0))),
                )
            # 若 target 是 COMPLETED（或达到 L6_DONE → COMPLETED）
            final_status = target_norm
            if target_norm == "L6_DONE" or end_process_idx >= 7:
                final_status = "COMPLETED"
            self.candidate_storage.update_pipeline_run_status(
                run_id, status=final_status, progress=100,
                error_message=error_msg,
            )
            if stats_patch:
                self.candidate_storage.update_pipeline_run_stats(
                    run_id, stats_update=stats_patch, merge=True,
                )
            updated = self.candidate_storage.get_pipeline_run(run_id) or run
            return _run_to_legacy(updated)
        except Exception as e:
            return {"status": "error", "message": f"advance_run 失败: {e}"}

    def execute_all(
        self,
        *,
        run_id: str,
        fail_fast: bool = True,
    ) -> Dict[str, Any]:
        """POST /pipeline/runs/{id}/execute-all

        等价于 advance_run(target_step='L6')，且每一步失败时：
          fail_fast=True → 立即设 run.status=FAILED，抛错停止
          fail_fast=False → 记录 error_message，继续推进到下一步
        """
        try:
            run = self.candidate_storage.get_pipeline_run(run_id)
            if not run:
                return {"status": "error", "message": f"Pipeline Run {run_id} 不存在",
                        "code": "RUN_NOT_FOUND_404"}
            # advance_run 到 L6_DONE（最终自动 COMPLETED）
            stats_patch: Dict[str, Any] = dict(run.get("stats_json") or run.get("stats") or {})
            # 关键修复：若旧 status 被 run_pipeline 标记为 succeeded/COMPLETED 但 L3~L6 尚未推进，
            # 则强制回退 cur_idx 到 L2_DONE 之后，这样循环才会执行 L3~L6。
            # 判定：若 stats 里任何 L3/L4/L5/L6 不是 'ok' / 'skipped' / 'error'，则视为未完成。
            _done_flags = {"ok", "skipped", "error"}
            _levels = ("L3", "L4", "L5", "L6")
            need_retry_layers = any(
                (lv not in stats_patch) or (stats_patch[lv] not in _done_flags)
                for lv in _levels
            )
            error_collected: List[str] = []
            # 逐步推进：L1 → L2 → ... → L6 → COMPLETED
            cur_norm = self.candidate_storage._norm_run_status(
                str(run.get("status") or "DRAFT")
            )
            try:
                cur_idx = self._STEP_ORDER.index(cur_norm)
            except ValueError:
                cur_idx = 0
            if need_retry_layers:
                # 强制从 L2 之后开始推进（即 si 从 L3_DONE = index 4 开始，要把 cur_idx 降到 3）
                cur_idx = min(cur_idx, 3)
            for si in range(max(2, cur_idx + 1), 8):
                step_done_name = self._STEP_ORDER[si]  # L1_DONE .. L6_DONE
                lvl_num = step_done_name[0]
                err_here: Optional[str] = None
                step_result: Optional[Dict[str, Any]] = None
                try:
                    if step_done_name == "L3_DONE":
                        step_result = self.execute_l3(run_id=run_id)
                    elif step_done_name == "L4_DONE":
                        step_result = self.execute_l4(run_id=run_id)
                    elif step_done_name == "L5_DONE":
                        step_result = self.execute_l5(run_id=run_id)
                    elif step_done_name == "L6_DONE":
                        step_result = self.execute_l6(run_id=run_id)
                except Exception as exc:
                    err_here = f"{lvl_num} execute failed: {exc}"
                # merge stats_patch
                if step_result and isinstance(step_result.get("stats_patch"), dict):
                    for k, v in step_result["stats_patch"].items():
                        stats_patch[k] = v
                    if "skipped_reasons" in stats_patch and lvl_num in stats_patch["skipped_reasons"]:
                        del stats_patch["skipped_reasons"][lvl_num]
                elif err_here:
                    stats_patch[lvl_num] = "error"
                    stats_patch.setdefault("errors", {})
                    stats_patch["errors"][lvl_num] = err_here
                # 推进状态
                progress_val = min(100, int(100 * (si / 7.0)))
                self.candidate_storage.update_pipeline_run_status(
                    run_id, status=step_done_name, progress=progress_val,
                )
                if err_here and fail_fast:
                    self.candidate_storage.update_pipeline_run_status(
                        run_id, status="FAILED",
                        error_message="; ".join(error_collected + [err_here]),
                    )
                    if stats_patch:
                        self.candidate_storage.update_pipeline_run_stats(
                            run_id, stats_update=stats_patch, merge=True,
                        )
                    return {
                        "status": "error",
                        "message": f"{step_done_name} 执行失败: {err_here}",
                        "code": "STEP_EXECUTION_ERROR_500",
                    }
                if err_here:
                    error_collected.append(err_here)
            # 最终 → COMPLETED
            final_err = "; ".join(error_collected) if error_collected else None
            self.candidate_storage.update_pipeline_run_status(
                run_id, status="COMPLETED", progress=100, error_message=final_err,
            )
            if stats_patch:
                self.candidate_storage.update_pipeline_run_stats(
                    run_id, stats_update=stats_patch, merge=True,
                )
            updated = self.candidate_storage.get_pipeline_run(run_id) or run
            return _run_to_legacy(updated)
        except Exception as e:
            # fail_fast → 标记 FAILED
            try:
                self.candidate_storage.update_pipeline_run_status(
                    run_id, status="FAILED", error_message=str(e),
                )
            except Exception:
                pass
            return {"status": "error", "message": f"execute_all 失败: {e}"}
