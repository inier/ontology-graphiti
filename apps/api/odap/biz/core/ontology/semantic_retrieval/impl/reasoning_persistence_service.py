"""ReasoningPersistenceService — 推理结论 → USL Candidate 持久化 (HITL 飞轮入口)。

设计文档：specs/008-semantic-retrieval-bus/design-reasoning-persistence.md

核心决策（D1~D4）：
  D1: opt-in 触发（persist_candidates=True/False，默认 False）
  D2: origin=llm, status=DRAFT
  D3: 主结论 + 关键节点（跳过 rule_id=init 或 input==output）
  D4: 独立 service（engine 保持纯计算，service 层编排）

容错原则：持久化失败不阻断推理返回（fire-and-forget + 日志）。
审计约束：dual-channel + 不记录明文（仅计数）。
 Constitution I：所有函数体 ≤ 40 行。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
    SQLiteCandidateStorage,
)

logger = logging.getLogger("semantic_retrieval.persistence")


class ReasoningPersistenceService:
    """推理结论 → USL Candidate 持久化（HITL 飞轮入口）。"""

    def __init__(self, candidate_storage: SQLiteCandidateStorage):
        self._storage = candidate_storage

    # ── 公共 API ───────────────────────────────────────────────────────

    def persist(
        self, reasoning: Dict[str, Any], workspace_id: str
    ) -> Dict[str, Any]:
        """映射 reasoning → candidates 并写库，返回 {run_id, persisted_count, candidate_ids}。

        容错：存储异常不抛出，返回 {persisted_count:0, error:str}（设计 §6.1）。
        """
        try:
            mode = reasoning.get("mode", "")
            r = reasoning.get("reasoning", {})
            if r.get("status") == "degraded":
                return self._skipped("reasoning degraded, skip persist")
            cands = self._dispatch_mapping(mode, reasoning)
            if not cands:
                return self._skipped("no candidates extracted")
            run_id = self._ensure_pipeline_run(workspace_id, reasoning)
            inserted = self._safe_bulk_insert(cands, run_id, reasoning, workspace_id)
            return self._build_success(run_id, inserted)
        except Exception as exc:  # noqa: BLE001 — 存储异常不阻断推理
            logger.warning("推理结论持久化失败（不阻断）: %s", exc)
            return {"persisted_count": 0, "error": str(exc)}

    # ── 映射分发 ───────────────────────────────────────────────────────

    def _dispatch_mapping(
        self, mode: str, reasoning: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """按 mode 分发到 chain/mdl 映射器；未知 mode 返回空。"""
        if mode == "chain":
            return self._map_chain_to_candidates(reasoning)
        if mode == "mdl":
            return self._map_mdl_to_candidates(reasoning)
        return []

    # ── chain 映射（方案 C：主结论 + 关键节点） ──────────────────────

    def _map_chain_to_candidates(
        self, reasoning: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """chain steps → candidates（跳过 init / input==output），串 parent 链。"""
        r = reasoning["reasoning"]
        steps = r.get("steps", [])
        chain_id = r.get("chain_id", "")
        confidence = r.get("confidence", 0.0)
        cycle = r.get("cycle_detected", False)
        candidates: List[Dict[str, Any]] = []
        prev_id: Optional[str] = None
        for idx, step in enumerate(steps):
            if not self._is_key_step(step):
                continue
            cand_id = str(uuid.uuid4())
            self._append_chain_candidate(
                candidates, cand_id, step, idx, chain_id, confidence, cycle, prev_id
            )
            prev_id = cand_id
        return candidates

    @staticmethod
    def _is_key_step(step: Dict[str, Any]) -> bool:
        """关键节点判断：跳过 init 步骤 + input==output 的占位步骤。"""
        if step.get("rule_id") == "init":
            return False
        if step.get("input") == step.get("output"):
            return False
        return True

    @staticmethod
    def _append_chain_candidate(
        out: List[Dict[str, Any]],
        cand_id: str,
        step: Dict[str, Any],
        idx: int,
        chain_id: str,
        confidence: float,
        cycle: bool,
        prev_id: Optional[str],
    ) -> None:
        """构建单条 chain candidate 并追加到 out。"""
        out.append({
            "id": cand_id,
            "canonical": step["output"],
            "en": "",
            "semantic_type": "对象类型",
            "synonyms": [step.get("input", "")],
            "aliases": [],
            "origin": "llm",
            "cluster_confidence": 0.0,
            "usl_align_confidence": 0.0,
            "review_confidence": confidence,
            "status": "DRAFT",
            "confidence": confidence,
            "parent_candidates": [prev_id] if prev_id else [],
            "provenance": {
                "source": "reasoning",
                "engine_mode": "chain",
                "chain_id": chain_id,
                "step_id": step.get("step_id", ""),
                "rule_id": step.get("rule_id", ""),
                "step_index": idx,
                "duration_ms": step.get("duration_ms", 0),
                "cycle_aborted": cycle,
            },
        })

    # ── mdl 映射 ───────────────────────────────────────────────────────

    def _map_mdl_to_candidates(
        self, reasoning: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """mdl extraction.entities → candidates（每个实体 1 条）。"""
        r = reasoning["reasoning"]
        extraction = r.get("extraction") or {}
        entities = extraction.get("entities") or []
        chain_id = r.get("chain_id", "")
        template = r.get("template", "")
        confidence = r.get("confidence", 0.0)
        return [
            self._build_mdl_candidate(e, idx, chain_id, template, confidence)
            for idx, e in enumerate(entities)
        ]

    @staticmethod
    def _build_mdl_candidate(
        entity: Dict[str, Any],
        idx: int,
        chain_id: str,
        template: str,
        confidence: float,
    ) -> Dict[str, Any]:
        """构建单条 mdl candidate。"""
        return {
            "id": str(uuid.uuid4()),
            "canonical": entity.get("text") or entity.get("name") or "",
            "en": entity.get("en", ""),
            "semantic_type": entity.get("type", "对象类型"),
            "synonyms": entity.get("aliases", []),
            "aliases": [],
            "origin": "llm",
            "cluster_confidence": 0.0,
            "usl_align_confidence": 0.0,
            "review_confidence": confidence,
            "status": "DRAFT",
            "confidence": confidence,
            "parent_candidates": [],
            "provenance": {
                "source": "reasoning",
                "engine_mode": "mdl",
                "chain_id": chain_id,
                "template": template,
                "entity_index": idx,
            },
        }

    # ── Pipeline Run + 写库 ────────────────────────────────────────────

    def _ensure_pipeline_run(
        self, workspace_id: str, reasoning: Dict[str, Any]
    ) -> str:
        """新建 pipeline run（每次推理新建，不复用）。"""
        r = reasoning.get("reasoning", {})
        run = self._storage.create_pipeline_run(
            workspace_id=workspace_id,
            source_type="reasoning",
            triggered_by="reasoning_persist",
            stats={
                "engine_mode": reasoning.get("mode", ""),
                "chain_id": r.get("chain_id", ""),
                "step_count": len(r.get("steps", [])),
            },
        )
        return run.get("id", "")

    def _safe_bulk_insert(
        self,
        cands: List[Dict[str, Any]],
        run_id: str,
        reasoning: Dict[str, Any],
        workspace_id: str,
    ) -> List[Dict[str, Any]]:
        """安全批量写库 + 审计；异常由调用方 persist() 上层 catch。"""
        for c in cands:
            c["run_id"] = run_id
        inserted = self._storage.bulk_insert_candidates(cands)
        self._write_audit(inserted, run_id, reasoning, workspace_id)
        return inserted

    def _write_audit(
        self,
        inserted: List[Dict[str, Any]],
        run_id: str,
        reasoning: Dict[str, Any],
        workspace_id: str,
    ) -> None:
        """审计日志：仅记计数，不记明文（project_memory 硬约束）。"""
        r = reasoning.get("reasoning", {})
        payload = {
            "action": "reasoning_persisted",
            "run_id": run_id,
            "workspace_id": workspace_id,
            "engine_mode": reasoning.get("mode", ""),
            "chain_id": r.get("chain_id", ""),
            "candidate_count": len(inserted),
            "step_count": len(r.get("steps", [])),
        }
        try:
            import sqlite3
            conn = sqlite3.connect(self._storage.db_path)
            try:
                conn.execute(
                    """INSERT INTO audit_logs (id, pipeline_run_id, action, actor, payload, created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        str(uuid.uuid4()),
                        run_id,
                        "reasoning_persisted",
                        "reasoning_persist",
                        __import__("json").dumps(payload, ensure_ascii=False),
                        __import__("datetime").datetime.now().isoformat(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001 — 审计失败不阻断业务
            logger.warning("审计日志写入失败（不阻断）: %s", exc)

    # ── 返回构建 ───────────────────────────────────────────────────────

    @staticmethod
    def _build_success(
        run_id: str, inserted: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {
            "run_id": run_id,
            "persisted_count": len(inserted),
            "candidate_ids": [c["id"] for c in inserted],
        }

    @staticmethod
    def _skipped(reason: str) -> Dict[str, Any]:
        return {"persisted_count": 0, "skipped_reason": reason}
