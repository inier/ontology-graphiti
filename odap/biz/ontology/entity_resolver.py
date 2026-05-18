"""
EntityResolver — 实体消歧解析器

解决核心问题: 随机摄入的事件数据中，同一现实实体（如"C区"）
可能以不同 entity_id 出现多次，需要识别为同一实体并合并属性。

解析策略:
1. 精确匹配: entity_type + name → 查注册表
2. 别名匹配: entity_type + aliases → 查注册表
3. 新实体注册: 未匹配到 → 生成确定性 ID 并注册

属性合并策略:
- basic_properties: 浅合并（新值覆盖旧值，旧值保留新值没有的 key）
- statistical_properties: 浅合并
- capabilities: 浅合并
- aliases: 并集合并
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from odap.biz.ontology.schema.document import (
    OntologyDocument, OntologyEntity, OntologyRelation, deterministic_entity_id
)
from odap.biz.ontology.storage.sqlite_ingest_storage import SQLiteIngestStorage

logger = logging.getLogger("entity_resolver")


class EntityResolver:
    """
    实体消歧解析器

    在数据摄入时自动运行，确保:
    1. 同名同类型实体映射到同一个 canonical_id
    2. 新属性合并到已有实体
    3. 别名自动积累
    4. 关系中的 entity_id 同步替换为 canonical_id
    """

    _instance: Optional['EntityResolver'] = None

    def __init__(self, storage=None):
        if storage is None:
            storage = SQLiteIngestStorage()
        self._storage: SQLiteIngestStorage = storage

    @classmethod
    def get_instance(cls, storage=None) -> 'EntityResolver':
        if cls._instance is None:
            cls._instance = EntityResolver(storage)
        return cls._instance

    def resolve(self, doc: OntologyDocument, ontology_id: str) -> OntologyDocument:
        """
        解析文档中的所有实体，返回消歧后的文档

        处理:
        1. 每个 entity 查注册表，匹配则替换 entity_id 为 canonical_id + 合并属性
        2. 未匹配则生成确定性 ID + 注册到注册表
        3. 同步更新 relation 中的 source_entity / target_entity
        """
        id_map: Dict[str, str] = {}

        resolved_entities = []
        for entity in doc.entities:
            resolved_entity, old_id, new_id = self._resolve_entity(entity, ontology_id)
            resolved_entities.append(resolved_entity)
            if old_id != new_id:
                id_map[old_id] = new_id

        resolved_relations = self._update_relation_ids(doc.relations, id_map)

        doc.entities = resolved_entities
        doc.relations = resolved_relations

        if id_map:
            logger.info(f"实体消歧: {len(id_map)} 个实体 ID 被替换 | {list(id_map.values())[:5]}")

        return doc

    def _resolve_entity(
        self, entity: OntologyEntity, ontology_id: str
    ) -> Tuple[OntologyEntity, str, str]:
        """
        解析单个实体

        Returns:
            (resolved_entity, old_entity_id, canonical_id)
        """
        old_id = entity.entity_id
        canonical_id = deterministic_entity_id(entity.entity_type, entity.name)

        registered = self._storage.lookup_entity(entity.entity_type, entity.name, ontology_id)

        if registered is None and entity.aliases:
            for alias in entity.aliases:
                registered = self._storage.lookup_entity_by_alias(entity.entity_type, alias, ontology_id)
                if registered:
                    break

        if registered is not None:
            canonical_id = registered['canonical_id']

            self._storage.update_entity_mentions(
                canonical_id,
                new_properties={
                    'basic_properties': entity.basic_properties,
                    'statistical_properties': entity.statistical_properties,
                    'capabilities': entity.capabilities,
                },
                new_aliases=entity.aliases,
            )

            merged_basic = {**registered.get('basic_properties', {}), **entity.basic_properties}
            merged_stat = {**registered.get('statistical_properties', {}), **entity.statistical_properties}
            merged_cap = {**registered.get('capabilities', {}), **entity.capabilities}
            merged_aliases = list(set(registered.get('aliases', []) + entity.aliases))

            entity.entity_id = canonical_id
            entity.basic_properties = merged_basic
            entity.statistical_properties = merged_stat
            entity.capabilities = merged_cap
            entity.aliases = merged_aliases

            logger.debug(f"实体匹配: '{entity.name}' → {canonical_id} (mention #{registered.get('mention_count', 0) + 1})")
        else:
            now = datetime.now().isoformat()
            self._storage.register_entity({
                'canonical_id': canonical_id,
                'entity_type': entity.entity_type,
                'name': entity.name,
                'name_en': entity.name_en,
                'aliases': entity.aliases,
                'ontology_id': ontology_id,
                'basic_properties': entity.basic_properties,
                'statistical_properties': entity.statistical_properties,
                'capabilities': entity.capabilities,
                'source_doc_id': None,
                'mention_count': 1,
                'first_seen_at': now,
                'last_seen_at': now,
                'confidence': 1.0,
            })

            entity.entity_id = canonical_id

            logger.debug(f"实体注册: '{entity.name}' ({entity.entity_type}) → {canonical_id}")

        return entity, old_id, canonical_id

    def _update_relation_ids(
        self, relations: List[OntologyRelation], id_map: Dict[str, str]
    ) -> List[OntologyRelation]:
        """同步更新关系中的 entity_id 引用"""
        if not id_map:
            return relations

        for rel in relations:
            if rel.source_entity in id_map:
                rel.source_entity = id_map[rel.source_entity]
            if rel.target_entity in id_map:
                rel.target_entity = id_map[rel.target_entity]

        return relations

    def get_registry(self, ontology_id: str = None, entity_type: str = None) -> List[Dict[str, Any]]:
        """获取实体注册表"""
        return self._storage.get_registry_entities(ontology_id, entity_type)
