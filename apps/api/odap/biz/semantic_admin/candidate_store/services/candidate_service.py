"""Candidate Service（Candidate Store 业务服务层：routes → services → storage）。

2 级审批：approve/reject（HIGH/MEDIUM 加速通道→writeback；LOW→admin_pending；VERY_LOW→reject）。
所有方法返回 Dict[str, Any]，错误格式 {"status": "error", "message": "..."}。

双写策略：Candidate 写入 SQLite 的同时，尝试写入 Neo4j（容错，Neo4j 失败不影响主流程）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ._approval_helper import (
    ALLOWED_LEVEL1_APPROVE_STATUS,
    check_level2_status,
    run_fastpath_approve,
    run_level2_approve,
    run_low_admin_pending,
    score_to_tier,
)

if TYPE_CHECKING:  # pragma: no cover
    from ..storage.sqlite_candidate_storage import SQLiteCandidateStorage
    from ...usl_writeback.services.writeback_service import WritebackService
    from odap.infra.graph.graph_service import GraphManager


logger = logging.getLogger(__name__)


# 新枚举 → 旧枚举的兼容映射（service 对外层暴露旧语义）
_STATUS_LEGACY_MAP = {
    "DRAFT":              "new",
    "QUALITY_GATED":      "gated",
    "PENDING_REVIEW":     "gated",
    "AUDITOR_APPROVED":   "auditor_approved",
    "ADMIN_PENDING":      "admin_pending",
    "ADMIN_APPROVED":     "approved",
    "APPROVED":           "approved",
    "AUDITOR_REJECTED":   "rejected",
    "ADMIN_REJECTED":     "rejected",
    "REJECTED":           "rejected",
    "WRITTEN_BACK":       "written_back",
    "STOPLISTED":         "stoplisted",
    "ARCHIVED":           "archived",
}


def _translate_status_to_legacy(cand: Dict[str, Any]) -> Dict[str, Any]:
    """把新大写枚举翻译为旧小写枚举对外暴露。"""
    if not isinstance(cand, dict):
        return cand
    s = cand.get("status")
    if isinstance(s, str) and s in _STATUS_LEGACY_MAP:
        out = dict(cand)
        out["status"] = _STATUS_LEGACY_MAP[s]
        return out
    return cand


class CandidateService:

    def __init__(
        self,
        storage: Optional["SQLiteCandidateStorage"] = None,
        writeback_service: Optional["WritebackService"] = None,
    ) -> None:
        if storage is None:
            from ..storage import SQLiteCandidateStorage as _Storage
            storage = _Storage()
        self.storage = storage
        if writeback_service is None:
            from ...usl_writeback.services import WritebackService as _Wb
            writeback_service = _Wb(usl_storage=None, candidate_storage=storage)
        self.writeback = writeback_service

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def list_candidates(self, **kw) -> Dict[str, Any]:
        try:
            result = self.storage.list_candidates(**kw)
            if isinstance(result, dict) and isinstance(result.get("items"), list):
                out_items = [_translate_status_to_legacy(c) for c in result["items"]]
                out = dict(result)
                out["items"] = out_items
                return out
            return result
        except Exception as e:  # pragma: no cover
            return {"status": "error", "message": f"查询候选失败: {e}"}

    def get_candidate(self, candidate_id: str) -> Dict[str, Any]:
        try:
            cand = self.storage.get_candidate(candidate_id)
            if not cand:
                return {"status": "error", "message": f"候选 {candidate_id} 不存在"}
            qr = self.storage.get_quality_report_by_candidate(candidate_id)
            if qr:
                cand["quality_report"] = qr
            # 向后兼容：把新大写枚举翻译为旧小写枚举对外暴露
            cand = _translate_status_to_legacy(cand)
            return cand
        except Exception as e:  # pragma: no cover
            return {"status": "error", "message": f"读取候选失败: {e}"}

    # ------------------------------------------------------------------
    # 2 级审批
    # ------------------------------------------------------------------
    def approve(self, candidate_id, *, reviewer, comment=None, level=1):
        try:
            cand = self.storage.get_candidate(candidate_id)
            if not cand:
                return {"status": "error", "message": f"候选 {candidate_id} 不存在"}
            current_status = str(cand.get("status") or "")
            qr = self.storage.get_quality_report_by_candidate(candidate_id)
            tier = score_to_tier(None if not qr else qr.get("overall_score"))

            # level=2 admin
            if int(level) >= 2:
                err_msg = check_level2_status(current_status)
                if err_msg:
                    return {"status": "error", "message": err_msg, "code": "invalid_status_409"}
                return run_level2_approve(
                    self, candidate_id, reviewer=reviewer, comment=comment, tier=tier,
                )

            # level=1 schema_auditor
            if current_status not in ALLOWED_LEVEL1_APPROVE_STATUS:
                return {
                    "status": "error", "code": "invalid_status_409",
                    "message": (
                        f"当前状态 '{current_status}' 不允许 level1 审批，"
                        f"仅允许: {sorted(ALLOWED_LEVEL1_APPROVE_STATUS)}"
                    ),
                }
            task1 = self.storage.create_approval_task(
                candidate_id=candidate_id, level=1, assignee=reviewer,
            )
            self.storage.update_approval_task(
                task1["id"], status="approved", reviewer=reviewer, comment=comment,
            )
            if tier in ("HIGH", "MEDIUM"):
                return run_fastpath_approve(
                    self, candidate_id, reviewer=reviewer, comment=comment,
                    tier=tier, task1=task1,
                )
            if tier == "LOW":
                return run_low_admin_pending(
                    self, candidate_id, reviewer=reviewer, comment=comment,
                    tier=tier, task1=task1,
                )
            # VERY_LOW：直接 reject
            self.storage.update_approval_task(
                task1["id"], status="rejected", reviewer=reviewer,
                comment=(comment or "") + " [VERY_LOW 系统自动驳回]",
            )
            return self.reject(
                candidate_id, reviewer=reviewer, level=1,
                comment=f"[VERY_LOW 自动驳回] {comment or ''}",
                add_to_stoplist=True,
            )
        except Exception as e:  # pragma: no cover
            return {"status": "error", "message": f"审批失败: {e}"}

    def reject(self, candidate_id, *, reviewer, comment=None, level=1,
               add_to_stoplist=False):
        """任何状态都可 reject；同步 writeback.write_rejected（USL 停用词可选）。"""
        try:
            cand = self.storage.get_candidate(candidate_id)
            if not cand:
                return {"status": "error", "message": f"候选 {candidate_id} 不存在"}
            level_i = int(level)
            task = self.storage.create_approval_task(
                candidate_id=candidate_id, level=level_i, assignee=reviewer,
            )
            self.storage.update_approval_task(
                task["id"], status="rejected", reviewer=reviewer, comment=comment,
            )
            wb = self.writeback.write_rejected(
                candidate_id,
                reason_code=comment or "rejected_by_auditor",
                add_to_stoplist=bool(add_to_stoplist),
                executed_by=reviewer or "system",
            )
            # ----- 兼容 STOPLIST 新状态 -----
            if add_to_stoplist:
                # 先拿到现有的 provenance 合并 stoplist_added=True，且 status → STOPLISTED
                existing_prov = dict(cand.get("provenance") or {})
                merged_prov = dict(existing_prov)
                merged_prov["stoplist_added"] = True
                merged_prov["stoplist_by"] = reviewer or "system"
                merged_prov["stoplist_reason"] = comment or ""
                self.storage.update_candidate_status(
                    candidate_id, "STOPLISTED",
                    stoplist_flag=True,
                    provenance=merged_prov,
                )
            self.storage.append_audit_log(
                action="candidate_rejected",
                actor=reviewer or "system", candidate_id=candidate_id,
                approval_task_id=task.get("id"),
                payload={
                    "level": level_i, "comment": comment or "",
                    "add_to_stoplist": bool(add_to_stoplist), "writeback": wb,
                },
            )
            # stoplist 相关审计：保证 list_audit_logs 过滤 stoplist 命中
            if add_to_stoplist:
                self.storage.append_audit_log(
                    action="candidate_stoplist_added",
                    actor=reviewer or "system", candidate_id=candidate_id,
                    approval_task_id=task.get("id"),
                    payload={
                        "level": level_i, "comment": comment or "",
                        "reason": comment or "rejected_by_auditor",
                    },
                )
            # 若 STOPLIST，重新 get_candidate 返回 STOPLISTED 状态
            updated = self.get_candidate(candidate_id)
            if isinstance(updated, dict) and "id" in updated:
                updated["writeback"] = wb
                # 向后兼容：对外层 caller 暴露 status=rejected 或 stoplisted
                if add_to_stoplist:
                    updated["status"] = "stoplisted"  # 兼容旧枚举：STOPLISTED → stoplisted
                elif not updated.get("status") or updated["status"] not in (
                    "STOPLISTED", "stoplisted",
                ):
                    updated["status"] = "rejected"  # 默认 rejected
            return updated
        except Exception as e:  # pragma: no cover
            return {"status": "error", "message": f"驳回失败: {e}"}

    # ------------------------------------------------------------------
    # 审批任务 / 审计 / 删除
    # ------------------------------------------------------------------
    def list_approval_tasks(self, **kw) -> Dict[str, Any]:
        try:
            return self.storage.list_approval_tasks(**kw)
        except Exception as e:  # pragma: no cover
            return {"status": "error", "message": f"查询审批任务失败: {e}"}

    def list_audit_logs(self, **kw) -> Dict[str, Any]:
        try:
            return self.storage.list_audit_logs(**kw)
        except Exception as e:  # pragma: no cover
            return {"status": "error", "message": f"查询审计失败: {e}"}

    def delete_candidate(self, candidate_id, *, actor="system") -> Dict[str, Any]:
        try:
            cand = self.storage.get_candidate(candidate_id)
            if not cand:
                return {"status": "error", "message": f"候选 {candidate_id} 不存在"}
            deleted = self.storage.delete_candidate(candidate_id)
            self.storage.append_audit_log(
                action="candidate_deleted", actor=actor,
                candidate_id=candidate_id, payload={},
            )
            return {"status": "ok", "deleted": bool(deleted), "id": candidate_id}
        except Exception as e:  # pragma: no cover
            return {"status": "error", "message": f"删除失败: {e}"}

    # ======================================================================
    # A5-2: modify_candidate + promote_to_usl（B5 + B7 契约）
    # ======================================================================

    _EDITABLE_STATUS = {
        "DRAFT", "L1_DONE", "L2_DONE", "PENDING_REVIEW", "AUDITOR_MODIFIED",
        # 旧枚举兼容
        "new", "gated", "pending", "auditor_modified",
    }

    _MODIFY_ALLOWED_FIELDS = {
        # 原字段
        "canonical", "synonyms", "near_synonyms", "aliases", "definition",
        "semantic_type", "domain_id", "confidence", "editor_note",
        # 旧别名兼容
        "canonical_term", "hint_parents",
        # ---- 新契约 B5 的 7 个 patch key（从 approval_workflow/schemas 来） ----
        "term",                  # → canonical (别名)
        "canonical_label",       # → canonical (别名)
        "term_type",             # → semantic_type (别名)
        "custom_attributes",     # → provenance["custom_attributes"]
        "status",                # → 更新 status（不走 AUDITOR_MODIFIED 自动覆盖）
    }

    def modify_candidate(
        self,
        candidate_id: str,
        *,
        patch: Dict[str, Any],
        editor_id: str = "unknown",
    ) -> Dict[str, Any]:
        """PATCH /candidates/{id}

        patch ∈ {canonical, synonyms, near_synonyms, aliases, definition,
                  semantic_type, domain_id, confidence, editor_note}
        只有 status ∈ {DRAFT, L1_DONE, L2_DONE, PENDING_REVIEW, AUDITOR_MODIFIED}
        的可修改；否则 409 STATUS_NOT_EDITABLE
        修改后自动触发 QualityEvaluator.evaluate()，重算 quality_report（若存在）
        追加一条 usl_approval_records 流水：action=MODIFY, approver_id=editor_id,
            before_status, after_status=AUDITOR_MODIFIED, changes=patch
        """
        try:
            cand = self.storage.get_candidate(candidate_id)
            if not cand:
                return {"status": "error", "message": f"候选 {candidate_id} 不存在",
                        "code": "CANDIDATE_NOT_FOUND_404"}
            # 翻译：cand 的 status 经 _deserialize → 已经是旧枚举（如 gated/new）
            # 需要通过 storage._norm_cand_status 转成新枚举检查
            cur_status_raw = str(cand.get("status") or "")
            cur_norm = self.storage._norm_cand_status(cur_status_raw)

            # 可编辑状态检查（新枚举 + 旧枚举双重检查）
            editable_norms = {"DRAFT", "L1_DONE", "L2_DONE", "PENDING_REVIEW",
                              "AUDITOR_MODIFIED", "QUALITY_GATED"}
            if cur_norm not in editable_norms:
                return {
                    "status": "error",
                    "code": "STATUS_NOT_EDITABLE_409",
                    "message": (
                        f"候选 status={cur_status_raw}（规范={cur_norm}）不可编辑，"
                        f"仅允许: {sorted(editable_norms)}"
                    ),
                }

            # patch 字段过滤
            if not isinstance(patch, dict):
                return {"status": "error", "message": "patch 必须是 dict"}
            clean_patch: Dict[str, Any] = {}
            desired_status: Optional[str] = None  # 显式要求的 status（不走自动 AUDITOR_MODIFIED）
            for k, v in patch.items():
                if k in self._MODIFY_ALLOWED_FIELDS:
                    # 旧字段 → 新字段名映射
                    if k == "canonical_term":
                        clean_patch["canonical"] = v
                    elif k == "hint_parents":
                        clean_patch["parent_candidates"] = v
                    # ---- 新契约 B5 的 7 key 映射 ----
                    elif k == "term":
                        clean_patch["canonical"] = v
                    elif k == "canonical_label":
                        clean_patch["canonical"] = v
                    elif k == "term_type":
                        clean_patch["semantic_type"] = v
                    elif k == "status":
                        desired_status = None if v is None else str(v)
                    else:
                        clean_patch[k] = v
            if not clean_patch and desired_status is None:
                # 空 patch：不报错，直接返回
                return self.get_candidate(candidate_id)

            # 构建 extra kwargs 给 update_candidate_status（它会按字段名映射）
            extra_updates: Dict[str, Any] = {}
            for fld, val in clean_patch.items():
                if fld == "canonical":
                    extra_updates["canonical"] = str(val)
                elif fld == "synonyms":
                    extra_updates["synonyms"] = list(val or [])
                elif fld == "near_synonyms":
                    extra_updates["near_synonyms"] = list(val or [])
                elif fld == "aliases":
                    extra_updates["aliases"] = list(val or [])
                elif fld == "definition":
                    extra_updates["definition"] = None if val is None else str(val)
                elif fld == "semantic_type":
                    extra_updates["semantic_type"] = str(val)
                elif fld == "domain_id":
                    extra_updates["domain_id"] = None if val is None else str(val)
                elif fld == "confidence":
                    try:
                        extra_updates["confidence"] = float(val)
                    except (TypeError, ValueError):
                        pass
            # provenance 合并：追加 editor_note + custom_attributes
            old_prov = dict(cand.get("provenance") or {})
            merged_prov = dict(old_prov)
            editor_note = clean_patch.get("editor_note")
            if editor_note:
                notes = list(merged_prov.get("editor_notes") or [])
                notes.append({
                    "editor": editor_id,
                    "note": str(editor_note),
                    "at": __import__("datetime").datetime.now().isoformat(),
                })
                merged_prov["editor_notes"] = notes
            custom_attrs = clean_patch.get("custom_attributes")
            if isinstance(custom_attrs, dict):
                old_ca = dict(merged_prov.get("custom_attributes") or {})
                merged_ca = dict(old_ca)
                merged_ca.update(custom_attrs)
                merged_prov["custom_attributes"] = merged_ca
            extra_updates["provenance"] = merged_prov

            # 更新 status：
            #   - 若 patch 中显式传 status → 用用户指定值（比如 PENDING_REVIEW / DRAFT 等）
            #   - 否则若 clean_patch 里有除 custom_attributes/editor_note 外的实际字段改动 → AUDITOR_MODIFIED
            #   - 否则保持原 status（比如只改 custom_attributes/editor_note）
            before_norm = cur_norm
            fields_affecting_content = {
                "canonical", "synonyms", "near_synonyms", "aliases", "definition",
                "semantic_type", "domain_id", "confidence",
            }
            has_content_change = any(f in clean_patch for f in fields_affecting_content)
            if desired_status is not None:
                after_norm = desired_status
            elif has_content_change:
                after_norm = "AUDITOR_MODIFIED"
            else:
                after_norm = before_norm
            ok = self.storage.update_candidate_status(
                candidate_id, after_norm, **extra_updates
            )
            if not ok:
                return {"status": "error", "message": "更新候选字段失败"}

            # 触发 QualityEvaluator.evaluate → 重算 quality_report（若之前有则覆盖）
            try:
                from odap.biz.semantic_admin.quality_gate.services.quality_evaluator import (
                    evaluate_candidate,
                )
                updated_cand = self.storage.get_candidate(candidate_id) or {}
                qr = evaluate_candidate(updated_cand)
                if qr:
                    self.storage.save_quality_report(qr)
            except Exception:
                # 质量评估失败不阻塞修改操作（降级）
                pass

            # 追加审批流水 action=MODIFY
            ws_id = str(cand.get("workspace_id") or "unknown_ws")
            self.storage.append_approval_record(
                candidate_id=candidate_id,
                approver_id=editor_id,
                approver_role="schema_auditor",
                workspace_id=ws_id,
                action="MODIFY",
                before_status=before_norm,
                after_status=after_norm,
                comment=str(editor_note or ""),
                changes=clean_patch,
            )
            self.storage.append_audit_log(
                action="candidate_modified",
                actor=editor_id, candidate_id=candidate_id,
                payload={"changes": clean_patch},
            )
            return self.get_candidate(candidate_id)
        except Exception as e:
            return {"status": "error", "message": f"modify_candidate 失败: {e}"}

    def promote_to_usl(
        self,
        candidate_id: str,
        *,
        admin_id: str,
        force_overwrite: bool = False,
        parent_term_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /candidates/{id}/promote-to-usl（仅 admin 角色）

        步骤：
          1. 查 candidate，查不到 → 404
          2. 查 usl_terms 同 domain_id + canonical 是否存在
             - 存在且 force_overwrite=False → 409 TERM_EXISTS
             - 存在且 force_overwrite=True → UPDATE synonyms/definition
             - 不存在 → INSERT 新 term
          3. 写入 usl_approval_records action=APPROVE approver_role='admin'
          4. candidate.status = WRITTEN_BACK；provenance.writeback_usl_term_id = 新 term.id
          5. 返回 {usl_term_id, created_new: bool, overwrote_existing: bool,
                   term: {...TermResponse...}}
        复用 UslWritebackHandler.write_approved()
        """
        try:
            cand = self.storage.get_candidate(candidate_id)
            if not cand:
                return {"status": "error", "message": f"候选 {candidate_id} 不存在",
                        "code": "CANDIDATE_NOT_FOUND_404"}
            # 复用 UslWritebackHandler
            from odap.biz.semantic_admin.usl_writeback.impl.usl_writeback_handler import (
                UslWritebackHandler,
            )
            usl_storage = None
            wb = self.writeback
            if isinstance(wb, UslWritebackHandler):
                pass
            else:
                wb = UslWritebackHandler(
                    usl_storage=None, candidate_storage=self.storage,
                )
            usl = wb._usl()

            # 步骤 2：查重（先手动查同 domain + canonical）
            domain_id = cand.get("domain_id") or None
            canonical = str(cand.get("canonical") or "")
            existing_term: Optional[Dict[str, Any]] = None
            if domain_id and canonical:
                try:
                    # list_terms by domain + canonical_q（storage 返回 Tuple[List,int] 或 dict）
                    result = usl.list_terms(
                        domain_id=domain_id, canonical_q=canonical,
                        page=1, page_size=10,
                    )
                    if isinstance(result, tuple):
                        items, _t = result
                    elif isinstance(result, dict):
                        items = result.get("items") or []
                    else:
                        items = []
                    for t in items:
                        t_canon = str(t.get("canonical") or "").strip()
                        t_dom = str(t.get("domain_id") or "")
                        if t_canon == canonical.strip() and (
                            not domain_id or t_dom == domain_id or not t_dom
                        ):
                            existing_term = t
                            break
                except Exception:
                    existing_term = None

            created_new = False
            overwrote_existing = False
            usl_term_id: Optional[str] = None
            term_dict: Dict[str, Any] = {}

            if existing_term:
                if not force_overwrite:
                    return {
                        "status": "error",
                        "code": "TERM_EXISTS_409",
                        "message": (
                            f"USL 中已存在 domain={domain_id} canonical={canonical} 的 Term，"
                            f"指定 force_overwrite=True 覆盖"
                        ),
                    }
                # force_overwrite=True → UPDATE synonyms/definition
                usl_term_id = str(existing_term.get("id"))
                new_syns = list(cand.get("synonyms") or [])
                # 合并：保留现有同义词 + 追加候选同义词（去重）
                old_syns = list(existing_term.get("synonyms") or [])
                merged_syns: List[str] = []
                seen = set()
                for s in list(old_syns) + list(new_syns):
                    s_norm = str(s).strip().lower()
                    if not s_norm or s_norm in seen:
                        continue
                    seen.add(s_norm)
                    merged_syns.append(str(s))
                update_payload: Dict[str, Any] = {
                    "synonyms": merged_syns,
                }
                if cand.get("definition"):
                    update_payload["definition"] = str(cand.get("definition"))
                if cand.get("semantic_type"):
                    update_payload["semantic_type"] = str(cand.get("semantic_type"))
                try:
                    # update_term 如果有则调用，否则 save_term(upsert 语义)
                    updater = getattr(usl, "update_term", None)
                    if updater is not None:
                        updater(usl_term_id, **update_payload)
                    else:
                        # save_term 用 INSERT OR REPLACE
                        merged_term = dict(existing_term)
                        for k, v in update_payload.items():
                            merged_term[k] = v
                        saved = usl.save_term(merged_term)
                        usl_term_id = str(saved["id"])
                except Exception:
                    # fallback 直接 save_term 幂等替换
                    merged_term = dict(existing_term)
                    for k, v in update_payload.items():
                        merged_term[k] = v
                    saved = usl.save_term(merged_term)
                    usl_term_id = str(saved["id"])
                overwrote_existing = True
                # 重新 get
                try:
                    got = usl.get_term(usl_term_id)
                    term_dict = dict(got) if got else dict(existing_term)
                except Exception:
                    term_dict = dict(existing_term)
            else:
                # 不存在 → INSERT：复用 write_approved
                wb_result = wb.write_approved(
                    candidate_id, executed_by=admin_id or "system",
                )
                if isinstance(wb_result, dict) and wb_result.get("status") == "error":
                    return wb_result
                if isinstance(wb_result, dict):
                    usl_term_id = wb_result.get("usl_term_id")
                created_new = True
                if usl_term_id:
                    try:
                        got = usl.get_term(usl_term_id)
                        term_dict = dict(got) if got else {}
                    except Exception:
                        term_dict = {}

            # ========== Phase 2 Iter4：USL → Graphiti 双写 ==========
            graphiti_result: Dict[str, Any] = {"status": "skipped", "reason": "no_usl_term_id"}
            ontology_id: Optional[str] = None
            graphiti_type_id: Optional[str] = None
            try:
                if usl_term_id and term_dict:
                    from odap.biz.semantic_admin.usl_writeback.impl.graphiti_writeback_adapter import (
                        GraphitiWritebackAdapter,
                    )
                    g_adapter = GraphitiWritebackAdapter(
                        ontology_service=None, usl_storage=usl if 'usl' in locals() else None,
                    )
                    ws_id_g = str(cand.get("workspace_id") or "")
                    sc_id_g = cand.get("scenario_id") if isinstance(cand.get("scenario_id"), str) else None
                    # 步骤 G1：Domain → Ontology
                    domain_id_g = term_dict.get("domain_id") or (
                        cand.get("domain_id") if isinstance(cand.get("domain_id"), str) else None
                    )
                    if not domain_id_g:
                        # fallback：用 USL 查出的 term
                        if isinstance(term_dict, dict):
                            domain_id_g = term_dict.get("domain_id")
                    if domain_id_g:
                        ont_res = g_adapter.resolve_ontology(
                            str(domain_id_g),
                            workspace_id=ws_id_g,
                            scenario_id=sc_id_g,
                        )
                        if isinstance(ont_res, dict) and ont_res.get("status") == "error":
                            graphiti_result = {
                                "status": "error",
                                "step": "resolve_ontology",
                                "message": ont_res.get("message", ""),
                            }
                        else:
                            ontology_id = ont_res.get("ontology_id")
                            # 步骤 G2：Term → Graphiti Type
                            if ontology_id:
                                # 组装完整 term_dict：USL 已存的 term + candidate 的扩展字段
                                enriched_term = dict(term_dict)
                                enriched_term["synonyms"] = list(
                                    enriched_term.get("synonyms") or cand.get("synonyms") or []
                                )
                                enriched_term["near_synonyms"] = list(
                                    enriched_term.get("near_synonyms") or cand.get("near_synonyms") or []
                                )
                                enriched_term["aliases"] = list(
                                    enriched_term.get("aliases") or cand.get("aliases") or []
                                )
                                if not enriched_term.get("definition"):
                                    enriched_term["definition"] = str(cand.get("definition") or "")
                                if not enriched_term.get("semantic_type"):
                                    enriched_term["semantic_type"] = str(cand.get("semantic_type") or "对象类型")
                                # provenance 带 link 等元信息
                                cprov = dict(cand.get("provenance") or {})
                                tprov = dict(enriched_term.get("provenance") or {})
                                merged_prov = dict(cprov)
                                merged_prov.update(tprov)
                                enriched_term["provenance"] = merged_prov

                                gt_res = g_adapter.write_term(
                                    enriched_term,
                                    ontology_id=ontology_id,
                                    force_overwrite=bool(force_overwrite),
                                )
                                graphiti_result = gt_res
                                if isinstance(gt_res, dict) and gt_res.get("status") == "ok":
                                    graphiti_type_id = gt_res.get("type_id")
            except Exception as g_exc:
                # 降级：Graphiti 写入失败不影响 USL 主流程
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "Graphiti writeback failed (degraded): %s", g_exc,
                )
                graphiti_result = {
                    "status": "error",
                    "step": "write_term_exception",
                    "message": str(g_exc),
                }
            # ==================================================================

            # 步骤 3：写入审批流水 action=APPROVE approver_role='admin'
            ws_id = str(cand.get("workspace_id") or "unknown_ws")
            before_norm = self.storage._norm_cand_status(str(cand.get("status") or ""))
            self.storage.append_approval_record(
                candidate_id=candidate_id,
                approver_id=admin_id,
                approver_role="admin",
                workspace_id=ws_id,
                action="APPROVE",
                before_status=before_norm,
                after_status="WRITTEN_BACK",
                comment=(
                    f"[promote_to_usl] force_overwrite={force_overwrite}, "
                    f"created_new={created_new}, overwrote={overwrote_existing}, "
                    f"graphiti={graphiti_result.get('status') if isinstance(graphiti_result, dict) else 'n/a'}"
                ),
                changes={
                    "force_overwrite": force_overwrite,
                    "parent_term_id": parent_term_id,
                    "usl_term_id": usl_term_id,
                    "graphiti_ontology_id": ontology_id,
                    "graphiti_type_id": graphiti_type_id,
                },
            )

            # 步骤 4：candidate.status = WRITTEN_BACK；provenance.writeback_usl_term_id + graphiti_*
            old_prov = dict(cand.get("provenance") or {})
            new_prov = dict(old_prov)
            if usl_term_id:
                new_prov["writeback_usl_term_id"] = usl_term_id
            new_prov["promoted_by_admin"] = admin_id
            # Graphiti 双写回状态
            new_prov["graphiti_ontology_id"] = ontology_id
            new_prov["graphiti_type_id"] = graphiti_type_id
            new_prov["graphiti_writeback"] = graphiti_result  # 完整结果，前端可用于展示状态
            self.storage.update_candidate_status(
                candidate_id, "WRITTEN_BACK", provenance=new_prov,
            )
            self.storage.append_audit_log(
                action="candidate_promoted_to_usl",
                actor=admin_id, candidate_id=candidate_id,
                payload={
                    "usl_term_id": usl_term_id,
                    "force_overwrite": force_overwrite,
                    "created_new": created_new,
                    "overwrote_existing": overwrote_existing,
                    "parent_term_id": parent_term_id,
                    "graphiti": graphiti_result,
                    "graphiti_ontology_id": ontology_id,
                    "graphiti_type_id": graphiti_type_id,
                },
            )

            # 步骤 5：返回（含 USL + Graphiti 双写回状态）
            return {
                "usl_term_id": usl_term_id,
                "created_new": created_new,
                "overwrote_existing": overwrote_existing,
                "term": term_dict,
                "graphiti": graphiti_result,
                "graphiti_ontology_id": ontology_id,
                "graphiti_type_id": graphiti_type_id,
            }
        except Exception as e:
            return {"status": "error", "message": f"promote_to_usl 失败: {e}",
                    "code": "PROMOTE_FAILED_500"}

    # ======================================================================
    # FR-019: 批量操作（batch_delete ≤50 条 + export ≤10000 条 JSON）
    # ======================================================================

    _BATCH_DELETE_LIMIT = 50
    _EXPORT_LIMIT = 10000

    def batch_delete_candidates(
        self,
        candidate_ids: List[str],
        *,
        actor: str = "system",
    ) -> Dict[str, Any]:
        """批量软删除（将 status 置 REJECTED + 审计）。

        - 超过 50 条返回 400 BATCH_TOO_LARGE_400
        - 每条逐条校验：不存在则跳过并计入 skipped
        - 返回 {deleted, skipped, failed, ids_deleted, ids_skipped, ids_failed}
        """
        ids = list(candidate_ids or [])
        if len(ids) > self._BATCH_DELETE_LIMIT:
            return {
                "status": "error",
                "code": "BATCH_TOO_LARGE_400",
                "message": f"批量删除上限 {self._BATCH_DELETE_LIMIT} 条，实际传入 {len(ids)} 条",
                "limit": self._BATCH_DELETE_LIMIT,
                "submitted": len(ids),
            }
        deleted = 0
        skipped = 0
        failed = 0
        ids_deleted: List[str] = []
        ids_skipped: List[str] = []
        ids_failed: List[str] = []
        try:
            for cid in ids:
                if not cid or not isinstance(cid, str):
                    skipped += 1
                    ids_skipped.append(str(cid))
                    continue
                cand = self.storage.get_candidate(cid)
                if not cand:
                    skipped += 1
                    ids_skipped.append(cid)
                    continue
                try:
                    # 软删：status 置 REJECTED + 审计（不物理删除）
                    self.storage.update_candidate_status(cid, "REJECTED")
                    self.storage.append_audit_log(
                        action="candidate_batch_deleted",
                        actor=actor, candidate_id=cid,
                        payload={"method": "soft_delete_rejected"},
                    )
                    deleted += 1
                    ids_deleted.append(cid)
                except Exception as _e:
                    failed += 1
                    ids_failed.append(cid)
            return {
                "deleted": deleted,
                "skipped": skipped,
                "failed": failed,
                "ids_deleted": ids_deleted,
                "ids_skipped": ids_skipped,
                "ids_failed": ids_failed,
                "total_submitted": len(ids),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"batch_delete_candidates 失败: {e}",
                "code": "BATCH_DELETE_FAILED_500",
            }

    def export_candidates(
        self,
        *,
        limit: int = 10000,
        page: int = 1,
        **filters: Any,
    ) -> Dict[str, Any]:
        """导出候选列表（JSON 格式，上限 10000 条）。

        - 超过 limit 截断到 10000
        - 返回 {count, items: [...扁平 dict 列表]}
        - 若请求 limit > 10000 返回 400 EXPORT_TOO_LARGE_400
        """
        if int(limit) > self._EXPORT_LIMIT:
            return {
                "status": "error",
                "code": "EXPORT_TOO_LARGE_400",
                "message": f"单次导出上限 {self._EXPORT_LIMIT} 条，请求 limit={limit}",
                "limit": self._EXPORT_LIMIT,
                "requested": int(limit),
            }
        eff_limit = min(int(limit), self._EXPORT_LIMIT)
        try:
            result = self.storage.list_candidates(
                page=int(page), page_size=eff_limit, **filters,
            )
            if isinstance(result, tuple):
                items_raw, total = result
                items = [
                    _translate_status_to_legacy(c) if isinstance(c, dict) else c
                    for c in items_raw
                ]
                return {"count": len(items), "total": int(total), "items": items}
            if isinstance(result, dict):
                raw_items = list(result.get("items") or [])
                items = [
                    _translate_status_to_legacy(c) if isinstance(c, dict) else c
                    for c in raw_items
                ]
                return {
                    "count": len(items),
                    "total": int(result.get("total") or len(items)),
                    "items": items,
                }
            return {"status": "error", "message": f"storage.list_candidates 返回未知类型 {type(result)}"}
        except Exception as e:
            return {"status": "error", "message": f"export_candidates 失败: {e}",
                    "code": "EXPORT_FAILED_500"}
