"""本体门控服务 — 检索的输入/输出验证门控

设计原则：
- 输入门控仅降级不拒绝（避免误拒绝合法查询）
- 输出门控调整分数而非排除结果
- ontology_ids=None 时完全透传（向后兼容）
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set

logger = logging.getLogger(__name__)


@dataclass
class OntologySchema:
    """本体 schema 摘要，用于检索约束"""
    ontology_id: str
    entity_types: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    relation_types: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    entity_type_names: Set[str] = field(default_factory=set)
    relation_type_names: Set[str] = field(default_factory=set)
    property_names_by_type: Dict[str, Set[str]] = field(default_factory=dict)


@dataclass
class QueryValidation:
    """查询验证结果"""
    is_valid: bool = True
    matched_entity_types: List[str] = field(default_factory=list)
    matched_relation_types: List[str] = field(default_factory=list)
    suggested_types: List[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class ResultValidation:
    """结果验证结果"""
    total: int = 0
    ontology_aligned: int = 0
    score_adjustments: Dict[int, float] = field(default_factory=dict)


class OntologyGate:
    """本体门控服务 — 检索的输入/输出验证门控"""

    def __init__(self):
        self._schema_cache: Dict[str, OntologySchema] = {}
        self._cache_ttl = 300
        self._cache_timestamps: Dict[str, float] = {}

    def load_schema(self, ontology_ids: List[str], workspace_id: str = "default") -> List[OntologySchema]:
        """加载本体 schema，带缓存"""
        schemas = []
        for oid in (ontology_ids or []):
            cache_key = f"{workspace_id}:{oid}"
            now = time.time()
            if cache_key in self._schema_cache:
                if now - self._cache_timestamps.get(cache_key, 0) < self._cache_ttl:
                    schemas.append(self._schema_cache[cache_key])
                    continue

            try:
                schema = self._load_schema_from_storage(oid, workspace_id)
            except Exception as e:
                logger.warning(f"OntologyGate: failed to load schema for {oid}: {e}")
                schema = None
            if schema:
                self._schema_cache[cache_key] = schema
                self._cache_timestamps[cache_key] = now
                schemas.append(schema)
        return schemas

    def validate_query(self, query: str, schemas: List[OntologySchema]) -> QueryValidation:
        """输入门控：验证查询是否在 ontology schema 范围内"""
        if not schemas:
            return QueryValidation(is_valid=True, confidence=1.0)

        matched_entity_types = []
        matched_relation_types = []
        suggested_types = []

        query_lower = query.lower()

        for schema in schemas:
            for type_name in schema.entity_type_names:
                if type_name.lower() in query_lower:
                    matched_entity_types.append(type_name)
                type_info = schema.entity_types.get(type_name, {})
                display_name = type_info.get("display_name", "")
                if display_name and display_name.lower() in query_lower:
                    if type_name not in matched_entity_types:
                        matched_entity_types.append(type_name)

            for rel_name in schema.relation_type_names:
                if rel_name.lower() in query_lower:
                    matched_relation_types.append(rel_name)

        if matched_entity_types:
            suggested_types = matched_entity_types
        elif matched_relation_types:
            for schema in schemas:
                for rel_name in matched_relation_types:
                    rel_info = schema.relation_types.get(rel_name, {})
                    src = rel_info.get("source_type", "")
                    tgt = rel_info.get("target_type", "")
                    if src and src not in suggested_types:
                        suggested_types.append(src)
                    if tgt and tgt not in suggested_types:
                        suggested_types.append(tgt)

        confidence = 1.0
        if not matched_entity_types and not matched_relation_types:
            confidence = 0.6

        return QueryValidation(
            is_valid=True,
            matched_entity_types=matched_entity_types,
            matched_relation_types=matched_relation_types,
            suggested_types=suggested_types,
            confidence=confidence,
        )

    def validate_results(self, results: List[Any], schemas: List[OntologySchema]) -> ResultValidation:
        """输出门控：验证检索结果是否符合本体定义，调整分数"""
        validation = ResultValidation(total=len(results))

        if not schemas or not results:
            return validation

        valid_entity_types: Set[str] = set()
        for schema in schemas:
            valid_entity_types.update(schema.entity_type_names)

        for idx, r in enumerate(results):
            metadata = getattr(r, 'metadata', {}) or {}
            entity_type = metadata.get("entity_type", metadata.get("type", ""))

            if entity_type and entity_type in valid_entity_types:
                validation.ontology_aligned += 1
            elif entity_type and valid_entity_types and entity_type not in valid_entity_types:
                original_score = getattr(r, 'score', 1.0)
                validation.score_adjustments[idx] = original_score * 0.5
            elif not entity_type and valid_entity_types:
                original_score = getattr(r, 'score', 1.0)
                validation.score_adjustments[idx] = original_score * 0.8

        return validation

    def apply_score_adjustments(self, results: List[Any], validation: ResultValidation) -> List[Any]:
        """应用分数调整"""
        if not validation.score_adjustments:
            return results

        adjusted = []
        for idx, r in enumerate(results):
            if idx in validation.score_adjustments:
                if hasattr(r, '__dataclass_fields__'):
                    from dataclasses import replace
                    r = replace(r, score=validation.score_adjustments[idx])
                elif hasattr(r, 'score'):
                    r.score = validation.score_adjustments[idx]
            adjusted.append(r)
        return adjusted

    def _load_schema_from_storage(self, ontology_id: str, workspace_id: str) -> Optional[OntologySchema]:
        """从存储加载本体 schema"""
        try:
            from odap.biz.data.ingest.storage import IngestStorage
            ingest_storage = IngestStorage()
            schema = OntologySchema(ontology_id=ontology_id)

            # 从摄入存储中获取本体类型定义
            try:
                entity_types = ingest_storage.list_entity_types(workspace_id=workspace_id)
                for et in (entity_types or []):
                    type_name = et.get("name", "")
                    if type_name and type_name not in schema.entity_type_names:
                        schema.entity_types[type_name] = {
                            "display_name": et.get("display_name", ""),
                            "properties": [p.get("name", "") for p in et.get("properties", [])],
                            "links": [l.get("name", "") for l in et.get("links", [])],
                        }
                        schema.entity_type_names.add(type_name)
                        schema.property_names_by_type[type_name] = set(
                            p.get("name", "") for p in et.get("properties", [])
                        )
            except Exception:
                pass

            # 从本体定义存储中获取
            try:
                from odap.biz.core.ontology.design.model.storage import Storage as OntologyStorage
                ont_storage = OntologyStorage()
                doc = ont_storage.get_ontology_document(ontology_id)
                if doc:
                    if isinstance(doc, dict):
                        for et in doc.get("object_types", []):
                            type_name = et.get("name", "")
                            if type_name and type_name not in schema.entity_type_names:
                                schema.entity_types[type_name] = {
                                    "display_name": et.get("display_name", ""),
                                    "properties": [p.get("name", "") for p in et.get("properties", [])],
                                    "links": [l.get("name", "") for l in et.get("links", [])],
                                }
                                schema.entity_type_names.add(type_name)
                                schema.property_names_by_type[type_name] = set(
                                    p.get("name", "") for p in et.get("properties", [])
                                )
                        for rel in doc.get("relations", []):
                            rel_name = rel.get("name", "")
                            if rel_name:
                                schema.relation_types[rel_name] = {
                                    "source_type": rel.get("source_type", ""),
                                    "target_type": rel.get("target_type", ""),
                                }
                                schema.relation_type_names.add(rel_name)
                    elif hasattr(doc, 'object_types'):
                        for et in (doc.object_types or []):
                            type_name = et.get("name", "") if isinstance(et, dict) else getattr(et, 'name', "")
                            if type_name and type_name not in schema.entity_type_names:
                                props = et.get("properties", []) if isinstance(et, dict) else getattr(et, 'properties', [])
                                links = et.get("links", []) if isinstance(et, dict) else getattr(et, 'links', [])
                                schema.entity_types[type_name] = {
                                    "display_name": et.get("display_name", "") if isinstance(et, dict) else getattr(et, 'display_name', ""),
                                    "properties": [p.get("name", "") if isinstance(p, dict) else getattr(p, 'name', "") for p in props],
                                    "links": [l.get("name", "") if isinstance(l, dict) else getattr(l, 'name', "") for l in links],
                                }
                                schema.entity_type_names.add(type_name)
                                schema.property_names_by_type[type_name] = set(
                                    p.get("name", "") if isinstance(p, dict) else getattr(p, 'name', "") for p in props
                                )
                        for rel in (doc.relations or [] if hasattr(doc, 'relations') else []):
                            rel_name = rel.get("name", "") if isinstance(rel, dict) else getattr(rel, 'name', "")
                            if rel_name:
                                schema.relation_types[rel_name] = {
                                    "source_type": rel.get("source_type", "") if isinstance(rel, dict) else getattr(rel, 'source_type', ""),
                                    "target_type": rel.get("target_type", "") if isinstance(rel, dict) else getattr(rel, 'target_type', ""),
                                }
                                schema.relation_type_names.add(rel_name)
            except Exception:
                pass

            return schema if schema.entity_type_names or schema.relation_type_names else None
        except Exception as e:
            logger.warning(f"OntologyGate: failed to load schema for {ontology_id}: {e}")
            return None
