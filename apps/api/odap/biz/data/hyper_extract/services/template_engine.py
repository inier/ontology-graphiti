"""TemplateEngine — HE template assessment, scoring, and settled-template reuse.

Responsibilities:
- list_presets(): dynamically enumerate HE preset templates (no hardcoding)
- assess(): settled check → embedder pre-filter → trial_extract → score → sort
- _compute_score(): scoring formula per FR-013
- _validate_settled(): lightweight 500-char trial, score ≥ threshold * 0.8

Dependencies:
- HEAdapter (trial_extract, _create_embedder, _Template.list)
- SqliteTemplateStorage (get_by_ontology, update_usage_count)
"""

import json
import logging
import math
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import yaml

from odap.infra.config_composer import get_config

logger = logging.getLogger("template_engine")

# Default scoring weights (FR-013)
_W_ENTITY = 0.3
_W_RELATION = 0.3
_W_COVERAGE = 0.2
_W_DIVERSITY = 0.2

# Default thresholds
_DEFAULT_SCORE_THRESHOLD = 0.5
_SETTLED_VALIDATION_RATIO = 0.8  # settled passes if score ≥ threshold * 0.8
_SETTLED_SAMPLE_SIZE = 500
_DEFAULT_TOP_K = 5

# ODAP 5 output categories for multi-template set cover (US2)
_ODAP_5_CATEGORIES = ["object", "relation", "action", "rule", "process"]

# Keyword mappings for type → ODAP category inference
_ACTION_KEYWORDS = ("action", "act", "buy", "sell", "execute", "transfer", "perform", "operation")
_RULE_KEYWORDS = ("rule", "constraint", "policy", "regulation", "law", "restriction")
_PROCESS_KEYWORDS = ("process", "workflow", "procedure", "flow", "step", "pipeline")


class TemplateEngine:
    """HE template lifecycle manager — assess, score, select, settle."""

    def __init__(
        self,
        he_adapter,
        storage,
        embedder=None,
    ):
        """Initialize with HEAdapter and SqliteTemplateStorage.

        Args:
            he_adapter: HEAdapter instance (provides trial_extract, _Template, _create_embedder).
            storage: SqliteTemplateStorage instance (provides get_by_ontology, save, update_usage_count).
            embedder: Optional pre-built embedder. If None, lazy-loaded from he_adapter.
        """
        self._adapter = he_adapter
        self._storage = storage
        self._embedder = embedder
        self._presets_cache: Optional[List[Dict[str, Any]]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_presets(self) -> List[Dict[str, Any]]:
        """Dynamically enumerate HE preset templates via Template.list().

        Returns:
            List of dicts with keys:
            - name: display name (e.g. "graph")
            - template_path: full path for Template.create() (e.g. "general/graph")
            - description, type, tags, language
            Empty list if no presets found.

        Raises:
            RuntimeError: if HE is not available.
        """
        if not self._adapter.is_available():
            raise RuntimeError("hyperextract 未安装或不可用")

        template_cls = self._adapter._Template
        # include_methods=False: only YAML preset templates, not method-based
        presets_dict = template_cls.list(filter_by_language="zh", include_methods=False)

        if not presets_dict:
            return []

        result: List[Dict[str, Any]] = []
        for key, cfg in presets_dict.items():
            # `key` is the full path (e.g. "general/graph") usable as source
            # for Template.create(). `cfg.name` is the short display name.
            if isinstance(cfg, dict):
                display_name = cfg.get("name", key)
                result.append({
                    "name": display_name,
                    "template_path": key,
                    "description": _extract_description(cfg.get("description", "")),
                    "type": cfg.get("type", ""),
                    "tags": cfg.get("tags", []),
                    "language": cfg.get("language", "zh"),
                })
            else:
                # Object-style TemplateCfg
                display_name = getattr(cfg, "name", key)
                result.append({
                    "name": display_name,
                    "template_path": key,
                    "description": _extract_description(getattr(cfg, "description", "")),
                    "type": getattr(cfg, "type", ""),
                    "tags": getattr(cfg, "tags", []),
                    "language": getattr(cfg, "language", "zh"),
                })
        return result

    def assess(self, text: str, ontology_id: str) -> Dict[str, Any]:
        """Assess template suitability for given text and ontology.

        Flow:
            1. Check settled template → lightweight 500-char trial validation
            2. If settled passes → return early (skip full assessment)
            3. If no settled or fails → list_presets + embedder pre-filter top-k=5
            4. trial_extract each top-k candidate
            5. Score and sort descending

        Returns:
            {
                "candidates": [{"name", "description", "source", "trial_result", "score"}, ...],
                "best_score": float,
                "threshold": float,
                "needs_custom": bool,
                "settled_used": bool,
            }
        """
        threshold = float(get_config("he.template_score_threshold", _DEFAULT_SCORE_THRESHOLD))

        # Step 1: Check settled template
        settled = self._storage.get_by_ontology(ontology_id)
        if settled:
            settled_result = self._validate_settled(settled, text, threshold)
            if settled_result is not None:
                # Settled template passes lightweight validation
                return {
                    "candidates": [settled_result],
                    "best_score": settled_result["score"],
                    "threshold": threshold,
                    "needs_custom": settled_result["score"] < threshold,
                    "settled_used": True,
                }

        # Step 2: Full assessment — list presets, pre-filter, trial, score
        presets = self.list_presets()
        if not presets:
            return {
                "candidates": [],
                "best_score": 0.0,
                "threshold": threshold,
                "needs_custom": True,
                "settled_used": False,
            }

        # Step 3: Embedder pre-filter top-k
        top_k = int(get_config("he.template_top_k", _DEFAULT_TOP_K))
        filtered = self._pre_filter(text, presets, top_k=top_k)

        # Step 4: Trial extract each candidate
        trial_results: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        for preset in filtered:
            # Use template_path (full path like "general/graph") for Template.create()
            tpl_path = preset.get("template_path") or preset["name"]
            template_config = {"template_path": tpl_path, "language": preset.get("language", "zh")}
            try:
                trial = self._adapter.trial_extract(text, template=template_config)
                trial_results.append((preset, trial))
            except Exception as exc:
                logger.warning("trial_extract failed for %s: %s", preset["name"], exc)
                trial_results.append((preset, {
                    "entity_count": 0, "relation_count": 0,
                    "field_coverage": 0.0, "type_diversity": 0.0, "types_found": [],
                }))

        # Step 5: Score and sort
        max_ec = max((t["entity_count"] for _, t in trial_results), default=0)
        max_rc = max((t["relation_count"] for _, t in trial_results), default=0)

        candidates: List[Dict[str, Any]] = []
        for preset, trial in trial_results:
            score = self._compute_score(trial, max_ec, max_rc)
            candidates.append({
                "name": preset["name"],
                "template_path": preset.get("template_path", preset["name"]),
                "description": preset.get("description", ""),
                "source": "preset",
                "trial_result": trial,
                "score": round(score, 4),
            })

        candidates.sort(key=lambda c: c["score"], reverse=True)
        best_score = candidates[0]["score"] if candidates else 0.0

        return {
            "candidates": candidates,
            "best_score": best_score,
            "threshold": threshold,
            "needs_custom": best_score < threshold,
            "settled_used": False,
        }

    def select_complementary(
        self,
        scored_candidates: List[Dict[str, Any]],
        ontology_schema: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Greedy set cover multi-template selection (US2 / T055).

        Selects a combination of templates that together cover the 5 ODAP
        output categories (object, relation, action, rule, process).

        Algorithm:
            1. Compute covers for each candidate from trial_result.
            2. Sort candidates by score descending.
            3. Greedily add templates: start with highest score, then add
               the template covering the most uncovered categories.
            4. Stop when all 5 categories covered or candidates exhausted.
            5. Skip templates that add no new coverage.

        Args:
            scored_candidates: Candidates from assess(), each with
                "name", "score", "trial_result".
            ontology_schema: Ontology schema dict (unused for now, reserved
                for future schema-aware selection).

        Returns:
            List of {"name", "covers", "score"} sorted by selection order.
        """
        if not scored_candidates:
            return []

        # Step 1: Compute covers for each candidate
        candidates_with_covers: List[Dict[str, Any]] = []
        for cand in scored_candidates:
            covers = self._compute_covers(cand.get("trial_result", {}))
            candidates_with_covers.append({
                "name": cand.get("name", ""),
                "template_path": cand.get("template_path", cand.get("name", "")),
                "score": cand.get("score", 0.0),
                "covers": covers,
            })

        # Step 2: Sort by score descending
        candidates_with_covers.sort(key=lambda c: c["score"], reverse=True)

        # Step 3: Greedy set cover
        all_categories = set(_ODAP_5_CATEGORIES)
        covered: set = set()
        selected: List[Dict[str, Any]] = []

        for cand in candidates_with_covers:
            if covered == all_categories:
                break
            new_coverage = set(cand["covers"]) - covered
            if not new_coverage:
                # This template adds no new coverage — skip
                continue
            selected.append(cand)
            covered.update(cand["covers"])

        return selected

    @staticmethod
    def _compute_covers(trial_result: Dict[str, Any]) -> List[str]:
        """Compute ODAP category coverage from a trial_extract result.

        Mapping:
            - entity_count > 0 → "object"
            - relation_count > 0 → "relation"
            - types_found contains action-like types → "action"
            - types_found contains rule-like types → "rule"
            - types_found contains process-like types → "process"
        """
        covers: List[str] = []
        if trial_result.get("entity_count", 0) > 0:
            covers.append("object")
        if trial_result.get("relation_count", 0) > 0:
            covers.append("relation")

        types_found = trial_result.get("types_found", []) or []
        for t in types_found:
            t_lower = str(t).lower()
            if any(kw in t_lower for kw in _ACTION_KEYWORDS) and "action" not in covers:
                covers.append("action")
            if any(kw in t_lower for kw in _RULE_KEYWORDS) and "rule" not in covers:
                covers.append("rule")
            if any(kw in t_lower for kw in _PROCESS_KEYWORDS) and "process" not in covers:
                covers.append("process")

        return covers

    # ------------------------------------------------------------------
    # Scoring (FR-013)
    # ------------------------------------------------------------------

    def _compute_score(
        self,
        trial: Dict[str, Any],
        max_ec: int,
        max_rc: int,
    ) -> float:
        """Compute template score per FR-013.

        Formula: 0.3*norm(ec) + 0.3*norm(rc) + 0.2*fc + 0.2*td

        Normalization: divide entity_count/relation_count by max across candidates.
        field_coverage and type_diversity are already 0-1.

        Args:
            trial: trial_extract() result dict.
            max_ec: max entity_count across candidates (for normalization).
            max_rc: max relation_count across candidates (for normalization).

        Returns:
            Score in [0.0, 1.0].
        """
        ec = trial.get("entity_count", 0)
        rc = trial.get("relation_count", 0)
        fc = trial.get("field_coverage", 0.0)
        td = trial.get("type_diversity", 0.0)

        # Normalize by max (guard against division by zero)
        norm_ec = ec / max_ec if max_ec > 0 else 0.0
        norm_rc = rc / max_rc if max_rc > 0 else 0.0

        score = (
            _W_ENTITY * norm_ec
            + _W_RELATION * norm_rc
            + _W_COVERAGE * fc
            + _W_DIVERSITY * td
        )
        return round(score, 4)

    # ------------------------------------------------------------------
    # Settled template validation (T029)
    # ------------------------------------------------------------------

    def _validate_settled(
        self,
        settled: Dict[str, Any],
        text: str,
        threshold: float,
    ) -> Optional[Dict[str, Any]]:
        """Lightweight validation of settled template.

        Uses 500-char trial_extract. Passes if score ≥ threshold * 0.8.

        Args:
            settled: Settled template record from storage.
            text: Input text.
            threshold: Score threshold (default 0.5).

        Returns:
            Candidate dict if passed, None if failed or YAML missing.
        """
        yaml_path = settled.get("yaml_path")
        if not yaml_path or not os.path.exists(yaml_path):
            # EC-013: YAML file deleted → skip settled
            logger.info("Settled template YAML missing: %s", yaml_path)
            return None

        template_config = {
            "template_path": yaml_path,
            "language": "zh",
        }
        passing_score = threshold * _SETTLED_VALIDATION_RATIO
        empty_trial = {
            "entity_count": 0, "relation_count": 0,
            "field_coverage": 0.0, "type_diversity": 0.0, "types_found": [],
        }

        try:
            trial = self._adapter.trial_extract(
                text, template=template_config, sample_size=_SETTLED_SAMPLE_SIZE
            )
        except Exception as exc:
            # EC-016: trial_extract failed — if YAML is structurally valid
            # (loadable as TemplateCfg), accept as degraded-pass to avoid
            # triggering a full assessment storm under LLM rate-limiting.
            logger.warning("Settled template trial failed (%s), checking YAML validity", exc)
            if not self._yaml_structurally_valid(yaml_path):
                return None
            logger.info("Settled YAML structurally valid, using degraded-pass")
            score = passing_score
            trial = empty_trial
        else:
            # For single-candidate validation, normalize by own metrics
            score = self._compute_score(trial, trial["entity_count"], trial["relation_count"])

        if score >= passing_score:
            # Increment usage_count for reused template
            try:
                self._storage.update_usage_count(settled["id"])
            except Exception as exc:
                logger.warning("Failed to increment usage_count: %s", exc)

            return {
                "name": settled.get("name", ""),
                "template_path": yaml_path,
                "description": settled.get("description", ""),
                "source": "settled",
                "trial_result": trial,
                "score": round(score, 4),
            }
        return None

    @staticmethod
    def _yaml_structurally_valid(yaml_path: str) -> bool:
        """Quick structural check: YAML loads + required top-level TemplateCfg keys present.

        Does NOT invoke HE or the LLM. Used as a degraded-pass gate for
        _validate_settled when the API is rate-limited (503).
        """
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        except Exception:
            return False
        if not isinstance(cfg, dict):
            return False
        required = {"name", "type", "output", "guideline", "display"}
        return required.issubset(cfg.keys())

    # ------------------------------------------------------------------
    # Embedder pre-filtering
    # ------------------------------------------------------------------

    def _pre_filter(
        self,
        text: str,
        presets: List[Dict[str, Any]],
        top_k: int = _DEFAULT_TOP_K,
    ) -> List[Dict[str, Any]]:
        """Pre-filter presets using embedder cosine similarity.

        Computes embedding of input text and all preset descriptions,
        selects top-k by cosine similarity.

        Args:
            text: Input text.
            presets: List of preset dicts (from list_presets()).
            top_k: Number of top candidates to select.

        Returns:
            Top-k preset dicts sorted by similarity descending.
        """
        if not presets:
            return []

        if len(presets) <= top_k:
            return presets

        embedder = self._get_embedder()
        if embedder is None:
            # No embedder available → prefer general/* templates, then others
            general = [p for p in presets if (p.get("template_path", "") or "").startswith("general/")]
            others = [p for p in presets if not (p.get("template_path", "") or "").startswith("general/")]
            ordered = general + others
            return ordered[:top_k]

        try:
            text_emb = embedder.embed_query(text)
            descriptions = [p.get("description", "") or p.get("name", "") for p in presets]
            preset_embs = embedder.embed_documents(descriptions)

            similarities = [
                _cosine_similarity(text_emb, pe) for pe in preset_embs
            ]
            # Sort by similarity descending, take top-k
            indexed = list(enumerate(similarities))
            indexed.sort(key=lambda x: x[1], reverse=True)
            top_indices = [i for i, _ in indexed[:top_k]]
            return [presets[i] for i in top_indices]
        except Exception as exc:
            logger.warning("Embedder pre-filter failed: %s", exc)
            return presets[:top_k]

    # ------------------------------------------------------------------
    # Custom template generation (US3 / T034-T037)
    # ------------------------------------------------------------------

    def generate_custom(
        self,
        text: str,
        ontology_schema: Dict[str, Any],
        gaps: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Generate a custom HE YAML template via LLM.

        Args:
            text: Input text summary (for LLM prompt context).
            ontology_schema: Ontology schema dict (object_types, link_types, etc.).
            gaps: Missing output categories (e.g. ["action", "rule"]).

        Returns:
            {"name": "custom_...", "yaml_content": str, "score": float} or None
            if all retries fail.
        """
        llm_client = self._get_llm_client()
        if llm_client is None:
            logger.error("LLM client unavailable for custom template generation")
            return None

        prompt = self._build_custom_prompt(text, ontology_schema, gaps)
        max_retries = 2

        for attempt in range(max_retries + 1):
            try:
                response = llm_client.invoke(prompt)
                yaml_content = self._extract_yaml_from_response(response)

                if not yaml_content:
                    logger.warning("Attempt %d: empty YAML from LLM", attempt + 1)
                    continue

                # Validate YAML is parseable
                parsed = yaml.safe_load(yaml_content)
                if not isinstance(parsed, dict):
                    logger.warning("Attempt %d: YAML not a dict", attempt + 1)
                    continue

                name = parsed.get("name", f"custom_{attempt}")

                # Validate with trial_extract
                score = self._validate_custom_yaml(yaml_content, text)
                if score is None:
                    logger.warning("Attempt %d: trial_extract validation failed", attempt + 1)
                    continue

                return {
                    "name": name,
                    "yaml_content": yaml_content,
                    "score": round(score, 4),
                    "source": "custom",
                }
            except Exception as exc:
                logger.warning("Attempt %d: generate_custom error: %s", attempt + 1, exc)
                continue

        logger.error("generate_custom failed after %d retries", max_retries)
        return None

    def generate_custom_with_fallback(
        self,
        text: str,
        ontology_schema: Dict[str, Any],
        gaps: List[str],
        best_preset: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate custom template with fallback to best preset (EC-016).

        If generate_custom fails after retries, returns best_preset with
        degradation_flag="custom_generation_failed".
        """
        result = self.generate_custom(text, ontology_schema, gaps)
        if result is not None:
            return result

        # Fallback to best preset with degradation flag
        if best_preset is None:
            return {
                "name": "fallback",
                "degradation_flag": "custom_generation_failed",
                "score": 0.0,
            }
        return {
            **best_preset,
            "degradation_flag": "custom_generation_failed",
        }

    def settle_template(
        self,
        ontology_id: str,
        name: str,
        yaml_content: str,
        score: float,
        coverage: List[str],
    ) -> str:
        """Persist a template: YAML to disk + metadata to SQLite.

        Args:
            ontology_id: Ontology ID.
            name: Template name.
            yaml_content: YAML content string.
            score: Assessment score.
            coverage: List of covered ODAP categories.

        Returns:
            template_id from storage.
        """
        templates_dir = self._get_templates_dir()
        ont_dir = os.path.join(templates_dir, ontology_id)
        os.makedirs(ont_dir, exist_ok=True)

        yaml_path = os.path.join(ont_dir, f"{name}.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        now = datetime.now().isoformat()
        record = {
            "ontology_id": ontology_id,
            "name": name,
            "description": f"Custom template for {ontology_id}",
            "source": "custom",
            "yaml_path": yaml_path,
            "score": score,
            "coverage": json.dumps(coverage),
            "created_at": now,
            "updated_at": now,
        }
        return self._storage.save(record)

    def get_settled_template(self, ontology_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve settled template for an ontology.

        EC-013: Returns None if YAML file has been deleted.

        Args:
            ontology_id: Ontology ID.

        Returns:
            Template dict (with yaml_path, name, score) or None.
        """
        record = self._storage.get_by_ontology(ontology_id)
        if not record:
            return None

        yaml_path = record.get("yaml_path")
        if not yaml_path or not os.path.exists(yaml_path):
            # EC-013: YAML file deleted
            logger.info("Settled template YAML missing for %s", ontology_id)
            return None

        # Increment usage_count
        try:
            self._storage.update_usage_count(record["id"])
        except Exception as exc:
            logger.warning("Failed to increment usage_count: %s", exc)

        return record

    # ------------------------------------------------------------------
    # Custom generation helpers
    # ------------------------------------------------------------------

    def _build_custom_prompt(
        self,
        text: str,
        ontology_schema: Dict[str, Any],
        gaps: List[str],
    ) -> str:
        """Build LLM prompt for custom template generation.

        The prompt encodes the EXACT HE YAML schema (verified against
        hyperextract.utils.template_engine.parsers.schemas) so the LLM
        produces a TemplateCfg-compatible YAML on the first attempt.
        """
        text_summary = text[:1000] if len(text) > 1000 else text
        schema_json = json.dumps(ontology_schema, ensure_ascii=False, default=str)
        gaps_str = ", ".join(gaps) if gaps else "无"

        return f"""你是一个 Hyper-Extract YAML 模板生成专家。请根据输入文本和本体 Schema，生成一个严格符合 HE YAML 规范的 graph 类型自定义模板。

# 输入文本摘要
{text_summary}

# 本体 Schema
{schema_json}

# 缺失的产出类别（需重点覆盖）
{gaps_str}

# HE YAML 模板规范（graph 类型，必须严格遵守）

顶层字段（全部必需，除非标注可选）：
- language: 语言列表，如 [zh, en]
- name: 模板名称字符串，必须以 custom_ 前缀
- type: 必须为 "graph"（本次只生成 graph 类型）
- tags: 字符串列表
- description: 多语言 dict，含 zh 和 en 两个 key，值为字符串
- output: GraphOutputSchema，结构见下方
- guideline: GraphGuidelineSchema，结构见下方
- identifiers: GraphIdentifiersSchema，结构见下方
- options: GraphOptionsSchema（可选但建议包含）
- display: GraphDisplaySchema，必需

## output 结构（GraphOutputSchema）
output:
  description: {{zh: 字符串, en: 字符串}}   # 必需
  entities:                                  # 必需，NaiveOutputSchema
    description: {{zh: 字符串, en: 字符串}}   # 必需
    fields:                                  # 必需，字段列表
    - name: 字段名                            # 必需，字符串
      type: 字段类型                          # 必需，只能是 str/int/float/bool/list 之一
      description: {{zh: 字符串, en: 字符串}}  # 必需
      required: true或false                   # 可选
  relations:                                 # 必需，NaiveOutputSchema
    description: {{zh: 字符串, en: 字符串}}   # 必需
    fields:                                  # 必需
    - name: source
      type: str
      description: {{zh: 关系起点实体名称, en: Source entity name}}
    - name: target
      type: str
      description: {{zh: 关系终点实体名称, en: Target entity name}}
    - name: type
      type: str
      description: {{zh: 关系类型, en: Relation type}}
    - name: description
      type: str
      description: {{zh: 关系说明, en: Relation description}}
      required: false

## guideline 结构（GraphGuidelineSchema）
guideline:
  target: {{zh: 字符串, en: 字符串}}                  # 必需
  rules_for_entities:                                  # 必需
    zh: [字符串列表]
    en: [字符串列表]
  rules_for_relations:                                 # 必需
    zh: [字符串列表]
    en: [字符串列表]

## identifiers 结构（GraphIdentifiersSchema）
identifiers:
  entity_id: name                                       # 实体ID取自 name 字段
  relation_id: '{{source}}|{{type}}|{{target}}'         # 关系ID模板
  relation_members:
    source: source
    target: target

## options 结构（GraphOptionsSchema，可选）
options:
  extraction_mode: two_stage                            # 或 one_stage

## display 结构（GraphDisplaySchema，必需）
display:
  entity_label: '{{name}} ({{type}})'
  relation_label: '{{type}}'

# 完整示例（base_graph 风格，可直接参考其结构）

language: [zh, en]
name: custom_example
type: graph
tags: [custom, graph]
description:
  zh: '自定义图谱模板 - 从文本中提取实体节点及二元关系。'
  en: 'Custom graph template - Extract entity nodes and binary relations.'
output:
  description:
    zh: '由实体节点和关系边组成的知识图谱。'
    en: 'Knowledge graph of entity nodes and relation edges.'
  entities:
    description:
      zh: '文本中可独立识别的实体节点。'
      en: 'Independently identifiable entity nodes.'
    fields:
    - name: name
      type: str
      description:
        zh: '实体名称。'
        en: 'Entity name.'
    - name: type
      type: str
      description:
        zh: '实体类型。'
        en: 'Entity type.'
    - name: description
      type: str
      description:
        zh: '实体说明。'
        en: 'Entity description.'
      required: false
  relations:
    description:
      zh: '实体之间的语义关系边。'
      en: 'Semantic relation edges between entities.'
    fields:
    - name: source
      type: str
      description:
        zh: '关系起点实体名称。'
        en: 'Source entity name.'
    - name: target
      type: str
      description:
        zh: '关系终点实体名称。'
        en: 'Target entity name.'
    - name: type
      type: str
      description:
        zh: '关系类型。'
        en: 'Relation type.'
    - name: description
      type: str
      description:
        zh: '关系说明。'
        en: 'Relation description.'
      required: false
guideline:
  target:
    zh: '你是知识抽取专家，请从文本中识别实体并构建二元关系。'
    en: 'You are a knowledge extraction expert. Identify entities and binary relations.'
  rules_for_entities:
    zh:
    - '提取对理解文本有价值的实体。'
    - '同一实体保持命名一致。'
    en:
    - 'Extract valuable entities.'
    - 'Keep consistent naming.'
  rules_for_relations:
    zh:
    - '仅在文本明确表达语义联系时创建关系。'
    - '避免重复关系。'
    en:
    - 'Create relations only on explicit semantic connections.'
    - 'Avoid duplicate relations.'
identifiers:
  entity_id: name
  relation_id: '{{source}}|{{type}}|{{target}}'
  relation_members:
    source: source
    target: target
options:
  extraction_mode: two_stage
display:
  entity_label: '{{name}} ({{type}})'
  relation_label: '{{type}}'

# 生成要求
1. 输出必须是单一 YAML 文档，可被 yaml.safe_load() 解析为 dict
2. type 必须为 "graph"
3. 所有 field.type 只能是 str/int/float/bool/list 之一
4. 所有多语言字段必须同时包含 zh 和 en 两个 key
5. 实体 fields 至少包含 name 和 type 两个必需字段
6. 关系 fields 必须包含 source、target、type 三个必需字段
7. 模板名称 name 必须以 custom_ 前缀
8. 根据本体 Schema 调整实体类型描述，以覆盖缺失类别: {gaps_str}
9. 直接输出 YAML 内容，不要包含 ```yaml 代码块标记，不要任何解释文字
"""

    def _extract_yaml_from_response(self, response: Any) -> Optional[str]:
        """Extract YAML string from LLM response."""
        if response is None:
            return None
        # LangChain ChatModel response has .content
        content = getattr(response, "content", None)
        if content is None and isinstance(response, str):
            content = response
        if not content:
            return None
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first line (```yaml or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)
        return content

    def _validate_custom_yaml(self, yaml_content: str, text: str) -> Optional[float]:
        """Validate generated YAML by trial extraction. Returns score or None."""
        # Write to temp file for trial_extract
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(yaml_content)
            tmp_path = tmp.name

        try:
            template_config = {"template_path": tmp_path, "language": "zh"}
            trial = self._adapter.trial_extract(text, template=template_config)
            score = self._compute_score(
                trial, trial["entity_count"], trial["relation_count"]
            )
            return score
        except Exception as exc:
            logger.warning("Custom YAML validation failed: %s", exc)
            return None
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _get_llm_client(self):
        """Get LLM client from HEAdapter."""
        try:
            return self._adapter._create_llm_client()
        except Exception as exc:
            logger.warning("Failed to create LLM client: %s", exc)
            return None

    def _get_templates_dir(self) -> str:
        """Get the base directory for HE template YAML files."""
        return os.path.join(
            os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "he_templates",
        )

    # ------------------------------------------------------------------
    # Ontology-based template generation (absorbed from OntologyTemplateGenerator)
    # ------------------------------------------------------------------

    _PROPERTY_TYPE_MAP = {
        "STRING": "str",
        "INTEGER": "int",
        "FLOAT": "float",
        "BOOLEAN": "bool",
        "DATE": "str",
        "DATETIME": "str",
        "ARRAY": "list",
        "OBJECT": "dict",
    }

    def generate_from_ontology(self, ontology_id: str) -> Dict[str, Any]:
        """Generate a HE YAML-compatible template from ontology definition.

        Reads the ontology's object_types, link_types, and action_types
        to build a template dict suitable for HE AutoGraph.

        Args:
            ontology_id: Ontology ID

        Returns:
            HE YAML-compatible template dict, or {"status": "error", ...}
        """
        if not ontology_id:
            return {"status": "error", "message": "ontology_id is required"}

        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import (
                OntologyService,
            )
            svc = OntologyService()
        except ImportError:
            return {"status": "error", "message": "OntologyService not available"}

        ontology_result = svc.get_ontology(ontology_id)
        if ontology_result.get("status") == "error":
            return ontology_result

        ontology_name = ontology_result.get("name", ontology_id)
        ontology_desc = ontology_result.get("description", "")

        obj_result = svc.list_object_types(ontology_id)
        if obj_result.get("status") == "error":
            return obj_result
        object_types = obj_result.get("object_types", [])

        link_result = svc.list_link_types(ontology_id)
        if link_result.get("status") == "error":
            return link_result
        link_types = link_result.get("link_types", [])

        action_result = svc.list_action_types(ontology_id)
        if action_result.get("status") == "error":
            return action_result
        action_types = action_result.get("action_types", [])

        has_actions = len(action_types) > 0
        template_type = "temporal_graph" if has_actions else "graph"

        template: Dict[str, Any] = {
            "language": "zh",
            "name": ontology_name,
            "type": template_type,
            "description": ontology_desc or f"Ontology template for {ontology_name}",
            "output": {
                "entities": {
                    "fields": self._build_entity_fields(object_types),
                },
                "relations": {
                    "fields": self._build_relation_fields(link_types),
                },
            },
            "identifiers": {
                "entity_id": "name",
                "relation_id": "{source}|{type}|{target}",
            },
        }

        if has_actions:
            template["output"]["events"] = {
                "fields": self._build_event_fields(action_types),
            }

        logger.info(
            "Generated HE template for ontology %s: type=%s, entities=%d, relations=%d, events=%d",
            ontology_id, template_type,
            len(object_types), len(link_types), len(action_types),
        )
        return template

    def _build_entity_fields(self, object_types: List) -> List[Dict[str, Any]]:
        """Build entity fields from ontology object type definitions."""
        fields = [
            {"name": "name", "type": "str", "description": "实体名称"},
            {"name": "type", "type": "str", "description": "实体类型"},
            {"name": "description", "type": "str", "description": "实体描述", "required": False},
        ]
        seen: set = set()
        for ot in object_types:
            for prop in ot.get("properties", []):
                prop_name = prop.get("name", "") if isinstance(prop, dict) else ""
                if prop_name and prop_name not in seen:
                    seen.add(prop_name)
                    fields.append({
                        "name": prop_name,
                        "type": self._map_property_type(prop.get("property_type", "STRING")),
                        "description": prop.get("description", "") or prop.get("display_name", prop_name),
                        **({"required": False} if not prop.get("required", True) else {}),
                    })
        return fields

    def _build_relation_fields(self, link_types: List) -> List[Dict[str, Any]]:
        """Build relation fields from ontology link type definitions."""
        fields = [
            {"name": "source", "type": "str", "description": "源实体名称"},
            {"name": "target", "type": "str", "description": "目标实体名称"},
            {"name": "type", "type": "str", "description": "关系类型"},
        ]
        seen: set = set()
        for lt in link_types:
            for prop in lt.get("properties", []):
                prop_name = prop.get("name", "") if isinstance(prop, dict) else ""
                if prop_name and prop_name not in seen:
                    seen.add(prop_name)
                    fields.append({
                        "name": prop_name,
                        "type": self._map_property_type(prop.get("property_type", "STRING")),
                        "description": prop.get("description", "") or prop.get("display_name", prop_name),
                        **({"required": False} if not prop.get("required", True) else {}),
                    })
        return fields

    def _build_event_fields(self, action_types: List) -> List[Dict[str, Any]]:
        """Build event fields from ontology action type definitions."""
        fields = [
            {"name": "name", "type": "str", "description": "事件名称"},
            {"name": "type", "type": "str", "description": "事件类型"},
            {"name": "target_object", "type": "str", "description": "作用对象类型"},
            {"name": "time", "type": "str", "description": "事件发生时间", "required": False},
            {"name": "description", "type": "str", "description": "事件描述", "required": False},
        ]
        seen: set = set()
        for at in action_types:
            for param in at.get("parameters", []):
                param_name = param.get("name", "") if isinstance(param, dict) else ""
                if param_name and param_name not in seen:
                    seen.add(param_name)
                    fields.append({
                        "name": param_name,
                        "type": self._map_property_type(param.get("property_type", "STRING")),
                        "description": param.get("description", "") or param.get("display_name", param_name),
                        **({"required": False} if not param.get("required", True) else {}),
                    })
        return fields

    def _map_property_type(self, prop_type: str) -> str:
        """Map ODAP PropertyType to HE field type."""
        if not prop_type:
            return "str"
        return self._PROPERTY_TYPE_MAP.get(prop_type.upper(), "str")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_embedder(self):
        """Lazy-load embedder from HEAdapter."""
        if self._embedder is None:
            try:
                self._embedder = self._adapter._create_embedder()
            except Exception as exc:
                logger.warning("Failed to create embedder: %s", exc)
                self._embedder = None
        return self._embedder


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _extract_description(desc: Any) -> str:
    """Extract a plain-string description from a TemplateCfg description field.

    HE YAML descriptions may be {zh: str, en: str} dicts or plain strings.
    """
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        return desc.get("zh") or desc.get("en") or ""
    return str(desc) if desc else ""


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)
