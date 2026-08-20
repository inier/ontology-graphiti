"""ConceptExtractor — schema_learning hook 入口（版块清理 2026-08-07）。

提供 `run_l1_l2_hook()` 接口供 006 ExtractService mode=schema_learning 调用。

职责：
  1. 接收 006 ExtractService 产出的 merged 抽取结果（entities / object_types /
     action_types / rule_types / process_types / link_types）
  2. 转换为 USL SchemaCandidate 格式（canonical / semantic_type / synonyms /
     origin / confidence）
  3. 可选：与已有 USL 术语去重（若 usl_storage 注入）
  4. 可选：写入 candidate_store（若 candidate_storage 注入）
  5. 返回 schema_candidates dict 供 006 写入 session.result_data

设计约束：
  - hook 异常不阻断 006 主流程（006 已在 _run_schema_learning_hook 中 catch）
  - 本模块不抛 HTTPException（services 层规则）
  - 返回 Dict[str, Any]（扁平 dict，不含 Pydantic/Enum 对象）

权威来源：
  - specs/007-semantic-admin-suite/plan.md（concept_extractor.py 项目结构）
  - specs/007-semantic-admin-suite/spec.md US4 hook 调用说明
  - specs/REFACTORING-NOTES.md
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
    from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage


# ======================================================================
# 006 ODAP 类型 → 007 USL semantic_type 映射
# ======================================================================

# 006 的 merged 结果包含 6 类 ODAP 类型，映射到 USL 合法 6 枚举：
_ODAP_TO_USL_SEMANTIC_TYPE: Dict[str, str] = {
    "object_types": "对象类型",
    "link_types": "关系类型",
    "action_types": "动作类型",
    "rule_types": "规则类型",
    "process_types": "过程类型",
    "attribute_types": "属性",  # 006 中较少见，但保留映射
}

# USL 合法 6 枚举（与 quality_protocol.py VALID_SEMANTIC_TYPES 对齐）
_VALID_SEMANTIC_TYPES = {
    "对象类型", "关系类型", "属性", "动作类型", "过程类型", "规则类型",
}


# ======================================================================
# ConceptExtractor 主类
# ======================================================================

class ConceptExtractor:
    """schema_learning hook 入口（供 006 ExtractService 调用）。

    版块清理（2026-08-07）：007 提供 `run_l1_l2_hook()` 接口，006 ExtractService
    在 mode=schema_learning 时通过 hook 调用 007，将 006 抽取结果转换为 USL
    SchemaCandidate 并写入 candidate_store。

    ExtractService 编排权归 006 FR-037；007 仅提供后置 hook，不参与 006 内部编排。
    hook 异常由 006 catch + 日志 warning，不阻断 006 主流程。

    用法：
        extractor = ConceptExtractor()
        result = extractor.run_l1_l2_hook(merged_dict)
        # result = {"candidates": [...], "count": N, "source": "007_concept_extractor"}
    """

    def __init__(
        self,
        *,
        candidate_storage: Optional["SQLiteCandidateStorage"] = None,
        usl_storage: Optional["SQLiteUslStorage"] = None,
    ) -> None:
        """初始化 ConceptExtractor。

        Args:
            candidate_storage: 可选的候选存储（用于写入 candidates）。
                若为 None，run_l1_l2_hook 仅返回 candidates 不写入 DB。
            usl_storage: 可选的 USL 术语存储（用于去重）。
                若为 None，跳过去重步骤。
        """
        self.candidate_storage = candidate_storage
        self.usl_storage = usl_storage

    # ------------------------------------------------------------------
    # 主入口：run_l1_l2_hook
    # ------------------------------------------------------------------
    def run_l1_l2_hook(
        self,
        merged: Dict[str, Any],
        *,
        workspace_id: str = "default",
        ontology_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """006 ExtractService mode=schema_learning 的后置 hook。

        将 006 产出的 merged 抽取结果转换为 USL SchemaCandidate 格式，
        可选去重 + 写入 candidate_store，返回 candidates dict。

        Args:
            merged: 006 ExtractService 产出的 merged 结果，包含：
                - entities: List[Dict] - 通用实体列表（每个含 name/type/description/properties）
                - object_types: List[Dict] - ODAP 对象类型
                - link_types: List[Dict] - ODAP 关系类型
                - action_types: List[Dict] - ODAP 动作类型
                - rule_types: List[Dict] - ODAP 规则类型
                - process_types: List[Dict] - ODAP 过程类型
                - conflicts: List[Dict] - 冲突列表（本 hook 忽略）
            workspace_id: 工作区 ID（写入 candidate 时使用）
            ontology_id: 可选的本体 ID（关联用）
            run_id: 可选的 pipeline run ID（若 006 已创建 run）

        Returns:
            Dict[str, Any] 形如：
            {
                "candidates": List[Dict],  # 转换后的候选列表
                "count": int,              # 候选数量
                "source": "007_concept_extractor",
                "written": bool,           # 是否写入 candidate_store
                "deduped_count": int,      # 去重后剩余数量
                "l1_tokens": int,          # L1 等效 token 数（= 输入实体数）
                "l2_concepts": int,        # L2 等效概念数（= 去重后候选数）
            }

        Note:
            hook 异常由 006 _run_schema_learning_hook catch（不阻断主流程）。
            本方法内部不再 catch（让 006 的 catch 处理）。
        """
        # Step 1: 从 merged 提取所有实体/类型，转换为 candidate dict 列表
        raw_candidates = self._extract_candidates_from_merged(merged)
        l1_token_count = len(raw_candidates)

        # Step 2: 与已有 USL 术语去重（若 usl_storage 注入）
        existing_usl_terms = self._load_existing_usl_terms()
        deduped_candidates = self._dedup_against_usl(
            raw_candidates, existing_usl_terms
        )
        l2_concept_count = len(deduped_candidates)

        # Step 3: 补充 candidate 元数据（run_id / workspace_id / provenance）
        now = datetime.now().isoformat()
        for cand in deduped_candidates:
            if "id" not in cand or not cand["id"]:
                cand["id"] = str(uuid.uuid4())
            if run_id and "pipeline_run_id" not in cand:
                cand["pipeline_run_id"] = run_id
            cand.setdefault("workspace_id", workspace_id)
            cand.setdefault("ontology_id", ontology_id)
            cand.setdefault("origin", "llm")
            cand.setdefault("status", "DRAFT")
            cand.setdefault("created_at", now)
            cand.setdefault("updated_at", now)
            # provenance 记录来源
            prov = cand.get("provenance") or {}
            if not isinstance(prov, dict):
                prov = {}
            prov["source"] = "007_concept_extractor.run_l1_l2_hook"
            prov["source_step"] = "l1_l2_hook"
            prov["hook_workspace_id"] = workspace_id
            if ontology_id:
                prov["hook_ontology_id"] = ontology_id
            cand["provenance"] = prov

        # Step 4: 写入 candidate_store（若注入）
        written = False
        if self.candidate_storage is not None and deduped_candidates:
            try:
                self.candidate_storage.bulk_insert_candidates(deduped_candidates)
                written = True
                logger.info(
                    "concept_extractor.run_l1_l2_hook 写入 %d 条候选到 candidate_store",
                    len(deduped_candidates),
                )
            except Exception as e:
                logger.warning(
                    "concept_extractor.run_l1_l2_hook 写入 candidate_store 失败（不影响返回）: %s",
                    e,
                )

        return {
            "candidates": deduped_candidates,
            "count": len(deduped_candidates),
            "source": "007_concept_extractor",
            "written": written,
            "deduped_count": l2_concept_count,
            "l1_tokens": l1_token_count,
            "l2_concepts": l2_concept_count,
        }

    # ------------------------------------------------------------------
    # 内部：从 merged 提取 candidates
    # ------------------------------------------------------------------
    def _extract_candidates_from_merged(
        self, merged: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """从 006 merged 结果提取所有实体/类型，转换为 candidate dict 列表。

        优先从 ODAP 5 类（object_types / link_types / action_types /
        rule_types / process_types）提取；若 5 类为空，回退到通用 entities。

        每个 candidate dict 包含：
            canonical: str          - 规范术语（取 name 字段）
            semantic_type: str      - USL 6 枚举之一
            synonyms: List[str]     - 同义词（取 aliases / alt_names）
            en: str                 - 英文映射（若有）
            confidence: float       - 置信度（取 confidence / score，默认 0.7）
            definition: str         - 定义（取 description）
            origin: str             - 来源（默认 'llm'）
        """
        candidates: List[Dict[str, Any]] = []
        seen_canonicals: set = set()  # 跨类型去重（同一 canonical 只保留首次出现）

        # 优先从 ODAP 5 类提取
        for odap_key, usl_type in _ODAP_TO_USL_SEMANTIC_TYPE.items():
            items = merged.get(odap_key) or []
            if not isinstance(items, (list, tuple)):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                cand = self._convert_item_to_candidate(item, usl_type)
                if cand is None:
                    continue
                canon_key = cand["canonical"].strip().lower()
                if canon_key and canon_key not in seen_canonicals:
                    seen_canonicals.add(canon_key)
                    candidates.append(cand)

        # 若 5 类为空，回退到通用 entities
        if not candidates:
            entities = merged.get("entities") or []
            if isinstance(entities, (list, tuple)):
                for entity in entities:
                    if not isinstance(entity, dict):
                        continue
                    # 推断 semantic_type：优先用 entity.type，否则默认"对象类型"
                    raw_type = str(entity.get("type") or "").strip()
                    usl_type = self._infer_usl_semantic_type(raw_type)
                    cand = self._convert_item_to_candidate(entity, usl_type)
                    if cand is None:
                        continue
                    canon_key = cand["canonical"].strip().lower()
                    if canon_key and canon_key not in seen_canonicals:
                        seen_canonicals.add(canon_key)
                        candidates.append(cand)

        return candidates

    # ------------------------------------------------------------------
    def _convert_item_to_candidate(
        self, item: Dict[str, Any], usl_type: str
    ) -> Optional[Dict[str, Any]]:
        """将单个 006 实体/类型 dict 转换为 USL candidate dict。

        Args:
            item: 006 抽取的单个实体/类型，形如：
                {"name": str, "type": str, "description": str,
                 "properties": dict, "confidence": float, ...}
            usl_type: USL 合法 semantic_type（对象类型/关系类型/...）

        Returns:
            candidate dict，或 None（若 name 为空）
        """
        # canonical：优先 name，其次 canonical / term / label
        canonical = (
            str(item.get("name") or item.get("canonical")
                or item.get("term") or item.get("label") or "").strip()
        )
        if not canonical:
            return None

        # synonyms：优先 synonyms / aliases / alt_names
        synonyms = self._extract_string_list(
            item, ("synonyms", "aliases", "alt_names", "alternative_names")
        )

        # en：优先 en / en_name / english_name
        en = str(
            item.get("en") or item.get("en_name")
            or item.get("english_name") or ""
        ).strip()

        # confidence：优先 confidence / score / cluster_confidence，默认 0.7
        confidence = self._safe_float(
            item.get("confidence") or item.get("score")
            or item.get("cluster_confidence"),
            default=0.7,
            clamp_01=True,
        )

        # definition：优先 description / definition
        definition = str(
            item.get("description") or item.get("definition") or ""
        ).strip()

        return {
            "canonical": canonical,
            "semantic_type": usl_type,
            "synonyms": synonyms,
            "en": en,
            "confidence": confidence,
            "definition": definition,
            "origin": "llm",
        }

    # ------------------------------------------------------------------
    # 内部：去重 + USL 加载
    # ------------------------------------------------------------------
    def _load_existing_usl_terms(self) -> List[Dict[str, Any]]:
        """从 usl_storage 加载已有 USL 术语（用于去重）。

        若 usl_storage 为 None 或加载失败，返回空列表。
        """
        if self.usl_storage is None:
            return []
        try:
            result = self.usl_storage.list_terms(page=1, page_size=100000)
            # SQLiteUslStorage.list_terms 返回 Tuple[List, int]
            if isinstance(result, tuple) and len(result) >= 1:
                return list(result[0]) if isinstance(result[0], list) else []
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return list(result.get("items") or result.get("terms") or [])
            return []
        except Exception as e:
            logger.warning(
                "concept_extractor 加载 USL 术语失败（跳过去重）: %s", e
            )
            return []

    def _dedup_against_usl(
        self,
        candidates: List[Dict[str, Any]],
        usl_terms: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """与已有 USL 术语去重：canonical 或 synonym 命中即跳过。

        Args:
            candidates: 待去重的候选列表
            usl_terms: 已有 USL 术语列表（每个含 canonical + synonyms）

        Returns:
            去重后的候选列表（不修改原列表）
        """
        if not usl_terms:
            return list(candidates)

        # 构建 USL 已知 surface 集合（canonical + synonyms，小写化）
        usl_surfaces: set = set()
        for t in usl_terms:
            if not isinstance(t, dict):
                continue
            canon = str(t.get("canonical") or "").strip()
            if canon:
                usl_surfaces.add(canon.lower())
            for s in (t.get("synonyms") or []):
                s_str = str(s or "").strip()
                if s_str:
                    usl_surfaces.add(s_str.lower())

        if not usl_surfaces:
            return list(candidates)

        deduped: List[Dict[str, Any]] = []
        skipped = 0
        for cand in candidates:
            canon = str(cand.get("canonical") or "").strip().lower()
            # canonical 命中 → 跳过
            if canon and canon in usl_surfaces:
                skipped += 1
                continue
            # 任一 synonym 命中 → 也跳过（视为同一概念）
            syn_hit = False
            for s in (cand.get("synonyms") or []):
                s_str = str(s or "").strip().lower()
                if s_str and s_str in usl_surfaces:
                    syn_hit = True
                    break
            if syn_hit:
                skipped += 1
                continue
            deduped.append(cand)

        if skipped > 0:
            logger.info(
                "concept_extractor 去重：跳过 %d 条命中 USL 的候选", skipped
            )
        return deduped

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_string_list(
        item: Dict[str, Any], keys: tuple
    ) -> List[str]:
        """从 item 中按优先级提取字符串列表。

        支持的值类型：List[str]、逗号分隔字符串、JSON 字符串。
        """
        for key in keys:
            raw = item.get(key)
            if raw is None:
                continue
            if isinstance(raw, (list, tuple)):
                return [str(x).strip() for x in raw if x is not None and str(x).strip()]
            if isinstance(raw, str):
                raw_stripped = raw.strip()
                if not raw_stripped:
                    continue
                # 尝试 JSON 解析
                if raw_stripped.startswith("["):
                    import json as _json
                    try:
                        parsed = _json.loads(raw_stripped)
                        if isinstance(parsed, (list, tuple)):
                            return [str(x).strip() for x in parsed if x is not None and str(x).strip()]
                    except Exception:
                        pass
                # 逗号分隔
                return [s.strip() for s in raw_stripped.split(",") if s.strip()]
        return []

    @staticmethod
    def _infer_usl_semantic_type(raw_type: str) -> str:
        """从 006 实体的 type 字段推断 USL semantic_type。

        若无法推断，默认"对象类型"（最通用）。
        """
        if not raw_type:
            return "对象类型"
        # 直接命中 USL 6 枚举
        if raw_type in _VALID_SEMANTIC_TYPES:
            return raw_type
        # 英文/常见别名推断
        raw_lower = raw_type.lower()
        alias_map = {
            "object": "对象类型",
            "objecttype": "对象类型",
            "entity": "对象类型",
            "relation": "关系类型",
            "link": "关系类型",
            "relationtype": "关系类型",
            "linktype": "关系类型",
            "action": "动作类型",
            "actiontype": "动作类型",
            "rule": "规则类型",
            "ruletype": "规则类型",
            "process": "过程类型",
            "processtype": "过程类型",
            "attribute": "属性",
            "property": "属性",
        }
        return alias_map.get(raw_lower, "对象类型")

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0, *, clamp_01: bool = True) -> float:
        """float() 解析但不抛 ValueError（复用 quality_evaluator 的同款实现）。"""
        try:
            if isinstance(v, bool):
                f = float(v)
            elif isinstance(v, (int, float)):
                f = float(v)
            else:
                s = str(v).strip() if v is not None else ""
                if not s:
                    return default
                f = float(s)
        except (TypeError, ValueError):
            return default
        if isinstance(f, float) and f != f:  # NaN check
            return default
        if clamp_01:
            return max(0.0, min(1.0, f))
        return f


__all__ = ["ConceptExtractor"]
