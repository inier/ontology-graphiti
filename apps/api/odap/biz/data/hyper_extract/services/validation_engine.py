"""ValidationEngine — 4-dimensional validation for Hyper-Extract results.

Validates extraction results against the ontology schema across four
dimensions (FR-024 ~ FR-028):
  1. Schema conformance  — type mismatch, missing required, undefined fields
  2. Completeness        — fill rate, empty rate, orphan entities
  3. Confidence scoring  — per-entity weighted score, needs_review gating
  4. Referential consistency — dangling relations, invalid action/rule targets

Design rules (AGENTS.md):
- Pure logic — no external dependencies (no HE, no LLM, no DB)
- EC-018: validate() catches all exceptions and returns status="error";
  validation failure never blocks the extraction pipeline.
- confidence_threshold defaults to 0.6, configurable via constructor.
"""
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Confidence score weights (spec: 0.4*fill + 0.3*template + 0.3*llm)
_FILL_WEIGHT: float = 0.4
_TEMPLATE_WEIGHT: float = 0.3
_LLM_WEIGHT: float = 0.3


class ValidationEngine:
    """4-dimensional validation engine for extraction results."""

    def __init__(self, confidence_threshold: float = 0.6) -> None:
        self._confidence_threshold = confidence_threshold

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def validate(
        self,
        extraction_result: Dict[str, Any],
        ontology_schema: Dict[str, Any],
        template_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Execute 4-dimensional validation and return a ValidationReport.

        EC-018: On any exception, returns {"status": "error", ...} so the
        extraction pipeline is never blocked by validation failure.
        """
        try:
            entities = extraction_result.get("entities", [])
            relations = extraction_result.get("relations", [])

            schema_result = self._validate_schema(entities, relations, ontology_schema)
            completeness = self._validate_completeness(entities, relations)
            confidence = self._score_confidence(entities, template_score)
            references = self._validate_references(entities, relations, ontology_schema)
            summary = self._build_summary(
                entities, relations, schema_result, confidence, references
            )
            return {
                "schema_conformance": schema_result,
                "completeness": completeness,
                "confidence": confidence,
                "referential_consistency": references,
                "summary": summary,
            }
        except Exception as exc:
            logger.exception("ValidationEngine failed: %s", exc)
            return {
                "status": "error",
                "message": str(exc),
                "summary": {
                    "total_entities": 0,
                    "total_relations": 0,
                    "needs_review_count": 0,
                    "overall_status": "error",
                },
            }

    # ------------------------------------------------------------------
    # Dimension 1: Schema conformance
    # ------------------------------------------------------------------

    def _validate_schema(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        ontology_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Check entity properties against ObjectType definitions."""
        obj_type_map = self._build_object_type_map(ontology_schema)
        violations: List[Dict[str, str]] = []
        passed_count = 0

        for entity in entities:
            if entity.get("type") != "object":
                continue
            name = entity.get("name", "")
            props = entity.get("properties", {})
            schema_props = obj_type_map.get(name)
            if schema_props is None:
                continue
            passed, viols = self._check_entity_props(name, props, schema_props)
            violations.extend(viols)
            passed_count += passed

        return {
            "violations": violations,
            "passed_count": passed_count,
            "violated_count": len(violations),
        }

    def _check_entity_props(
        self,
        entity_name: str,
        props: Dict[str, Any],
        schema_props: List[Dict[str, Any]],
    ) -> Tuple[int, List[Dict[str, str]]]:
        """Validate a single entity's properties against schema definitions."""
        schema_map = {p["name"]: p for p in schema_props}
        violations: List[Dict[str, str]] = []
        passed = 0

        for field_name, field_type in props.items():
            if field_name not in schema_map:
                violations.append(
                    {"entity": entity_name, "field": field_name, "issue": "undefined_field"}
                )
            elif str(field_type) != str(schema_map[field_name].get("type", "")):
                violations.append(
                    {
                        "entity": entity_name,
                        "field": field_name,
                        "issue": "type_mismatch",
                        "expected": str(schema_map[field_name].get("type", "")),
                        "actual": str(field_type),
                    }
                )
            else:
                passed += 1

        for sp in schema_props:
            if sp.get("required") and sp["name"] not in props:
                violations.append(
                    {"entity": entity_name, "field": sp["name"], "issue": "missing_required"}
                )

        return passed, violations

    def _build_object_type_map(
        self, ontology_schema: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Map object type name → its property definitions list."""
        result: Dict[str, List[Dict[str, Any]]] = {}
        for obj_type in ontology_schema.get("object_types", []):
            name = obj_type.get("name", "")
            if name:
                result[name] = obj_type.get("properties", [])
        return result

    # ------------------------------------------------------------------
    # Dimension 2: Completeness
    # ------------------------------------------------------------------

    def _validate_completeness(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute fill rate, empty rate, and orphan entities."""
        total_fields = 0
        filled_fields = 0

        for entity in entities:
            for value in entity.values():
                total_fields += 1
                if not self._is_empty(value):
                    filled_fields += 1

        fill_rate = filled_fields / total_fields if total_fields > 0 else 0.0
        empty_rate = 1.0 - fill_rate if total_fields > 0 else 0.0
        orphan_entities = self._find_orphans(entities, relations)

        return {
            "fill_rate": round(fill_rate, 4),
            "empty_rate": round(empty_rate, 4),
            "orphan_count": len(orphan_entities),
            "orphan_entities": orphan_entities,
        }

    def _find_orphans(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
    ) -> List[str]:
        """Return names of entities not appearing in any relation."""
        connected: set = set()
        for rel in relations:
            connected.add(rel.get("source", ""))
            connected.add(rel.get("target", ""))
        return [
            e.get("name", "")
            for e in entities
            if e.get("name", "") not in connected
        ]

    @staticmethod
    def _is_empty(value: Any) -> bool:
        """Check if a value is empty (None, empty string/dict/list)."""
        if value is None:
            return True
        if isinstance(value, str) and value == "":
            return True
        if isinstance(value, (dict, list)) and len(value) == 0:
            return True
        return False

    # ------------------------------------------------------------------
    # Dimension 3: Confidence scoring
    # ------------------------------------------------------------------

    def _score_confidence(
        self,
        entities: List[Dict[str, Any]],
        template_score: float,
    ) -> Dict[str, Any]:
        """Score each entity: 0.4*fill + 0.3*template + 0.3*llm."""
        per_entity: List[Dict[str, Any]] = []
        needs_review: List[str] = []

        for entity in entities:
            fill = self._entity_fill_rate(entity)
            llm = self._entity_llm_consistency(entity)
            score = (
                _FILL_WEIGHT * fill
                + _TEMPLATE_WEIGHT * template_score
                + _LLM_WEIGHT * llm
            )
            name = entity.get("name", "")
            per_entity.append(
                {
                    "entity": name,
                    "score": round(score, 4),
                    "components": {
                        "fill": round(fill, 4),
                        "template": template_score,
                        "llm": round(llm, 4),
                    },
                }
            )
            if score < self._confidence_threshold:
                needs_review.append(name)

        return {
            "threshold": self._confidence_threshold,
            "per_entity": per_entity,
            "needs_review": needs_review,
        }

    @staticmethod
    def _entity_fill_rate(entity: Dict[str, Any]) -> float:
        """Fraction of entity fields that are non-empty."""
        values = list(entity.values())
        if not values:
            return 0.0
        filled = sum(1 for v in values if not ValidationEngine._is_empty(v))
        return filled / len(values)

    @staticmethod
    def _entity_llm_consistency(entity: Dict[str, Any]) -> float:
        """Simplified LLM consistency: non-empty rate of name + description."""
        checks = [
            not ValidationEngine._is_empty(entity.get("name")),
            not ValidationEngine._is_empty(entity.get("description")),
        ]
        return sum(1 for c in checks if c) / len(checks)

    # ------------------------------------------------------------------
    # Dimension 4: Referential consistency
    # ------------------------------------------------------------------

    def _validate_references(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        ontology_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Check dangling relations, invalid action targets, invalid rule refs."""
        entity_names = {e.get("name", "") for e in entities}
        object_type_names = {
            ot.get("name", "") for ot in ontology_schema.get("object_types", [])
        }

        dangling = self._find_dangling_relations(relations, entity_names)
        invalid_actions = self._find_invalid_action_targets(entities, object_type_names)
        invalid_rules = self._find_invalid_rule_refs(entities, object_type_names)

        return {
            "dangling_relations": dangling,
            "invalid_action_targets": invalid_actions,
            "invalid_rule_references": invalid_rules,
        }

    @staticmethod
    def _find_dangling_relations(
        relations: List[Dict[str, Any]], entity_names: set
    ) -> List[Dict[str, str]]:
        """Find relations whose source or target is not in entity_names."""
        dangling: List[Dict[str, str]] = []
        for rel in relations:
            source = rel.get("source", "")
            target = rel.get("target", "")
            if source not in entity_names or target not in entity_names:
                dangling.append(
                    {
                        "source": source,
                        "target": target,
                        "type": rel.get("relation_type", rel.get("type", "")),
                    }
                )
        return dangling

    @staticmethod
    def _find_invalid_action_targets(
        entities: List[Dict[str, Any]], object_type_names: set
    ) -> List[Dict[str, str]]:
        """Find action entities whose target_type is not a defined object type."""
        invalid: List[Dict[str, str]] = []
        for entity in entities:
            if entity.get("type") != "action":
                continue
            target_type = entity.get("target_type", "")
            if target_type and target_type not in object_type_names:
                invalid.append(
                    {"action": entity.get("name", ""), "target_type": target_type}
                )
        return invalid

    @staticmethod
    def _find_invalid_rule_refs(
        entities: List[Dict[str, Any]], object_type_names: set
    ) -> List[Dict[str, str]]:
        """Find rule entities referencing undefined object types."""
        invalid: List[Dict[str, str]] = []
        for entity in entities:
            if entity.get("type") != "rule":
                continue
            rule_name = entity.get("name", "")
            for ref in entity.get("referenced_objects", []):
                if ref not in object_type_names:
                    invalid.append(
                        {"rule": rule_name, "referenced_object": ref}
                    )
        return invalid

    # ------------------------------------------------------------------
    # Summary builder
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        schema_result: Dict[str, Any],
        confidence: Dict[str, Any],
        references: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the summary dict with counts and overall_status."""
        needs_review_count = len(confidence.get("needs_review", []))
        has_critical = self._has_critical_issues(schema_result, references)

        if has_critical:
            overall_status = "failed"
        elif needs_review_count > 0:
            overall_status = "needs_review"
        else:
            overall_status = "passed"

        return {
            "total_entities": len(entities),
            "total_relations": len(relations),
            "needs_review_count": needs_review_count,
            "overall_status": overall_status,
        }

    @staticmethod
    def _has_critical_issues(
        schema_result: Dict[str, Any], references: Dict[str, Any]
    ) -> bool:
        """Determine whether critical violations exist."""
        if schema_result.get("violated_count", 0) > 0:
            return True
        if references.get("dangling_relations"):
            return True
        if references.get("invalid_action_targets"):
            return True
        if references.get("invalid_rule_references"):
            return True
        return False
