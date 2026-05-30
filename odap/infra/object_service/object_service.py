import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from .schemas import (
    ObjectQuery, ObjectQueryResult, ObjectQueryResponse,
    SemanticQuery, SemanticQueryResponse,
    ObjectQueryOperator,
)

logger = logging.getLogger(__name__)


class ObjectService:
    def __init__(self):
        self._oms = None
        self._graph_manager = None
        self._business_storage = None
        self._agent_storage = None
        self._kb_storage = None

    @property
    def oms(self):
        if self._oms is None:
            from odap.biz.core.ontology.oms.services import get_oms_service
            self._oms = get_oms_service()
        return self._oms

    @property
    def graph(self):
        if self._graph_manager is None:
            from odap.infra.graph.graph_service import GraphManager
            self._graph_manager = GraphManager()
        return self._graph_manager

    @property
    def business(self):
        if self._business_storage is None:
            from odap.biz.management.business.services import get_business_service
            self._business_storage = get_business_service()
        return self._business_storage

    @property
    def agents(self):
        if self._agent_storage is None:
            from odap.biz.management.agent_management.api.routes import agent_service
            self._agent_storage = agent_service
        return self._agent_storage

    # ── Core Query: Unified Object Access ──

    async def query_objects(self, query: ObjectQuery) -> ObjectQueryResponse:
        results = []
        total = 0

        if query.object_type:
            type_results, type_total = await self._query_by_type(query)
            results.extend(type_results)
            total += type_total
        else:
            for source_name, fetcher in [
                ("graph", self._fetch_from_graph),
                ("business", self._fetch_from_business),
                ("knowledge", self._fetch_from_knowledge_base),
                ("agent", self._fetch_from_agents),
            ]:
                try:
                    src_results = await fetcher(query)
                    if src_results:
                        results.extend(src_results)
                        total += len(src_results)
                except Exception as e:
                    logger.warning(f"ObjectService: {source_name} query failed: {e}")

        if query.sorts:
            results = self._apply_sorts(results, query.sorts)

        paginated = results[query.offset : query.offset + query.limit]

        if query.include_links or query.link_depth > 0:
            for r in paginated:
                r.links = await self._get_links(r.object_id, r.object_type, depth=query.link_depth)

        if query.include_actions:
            for r in paginated:
                r.available_actions = await self._get_available_actions(r.object_type)

        return ObjectQueryResponse(
            results=paginated,
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    # ── Semantic Query: Text → Objects ──

    async def semantic_query(self, query: SemanticQuery) -> SemanticQueryResponse:
        raw_entities = []
        try:
            result = self.graph.search_hybrid(query.query_text, top_k=query.top_k)
            if hasattr(result, 'entities'):
                raw_entities = result.entities
            elif isinstance(result, list):
                raw_entities = result
            elif isinstance(result, dict):
                raw_entities = result.get('results', result.get('entities', []))
        except Exception as e:
            logger.warning(f"ObjectService semantic search failed: {e}")
            raw_entities = []

        object_results = []
        seen_ids = set()

        for entity in raw_entities[:query.top_k]:
            obj_id = entity.get('id', entity.get('entity_id', ''))
            obj_type = entity.get('type', entity.get('entity_type', 'Unknown'))
            props = entity.get('properties', {})

            if not obj_id or obj_id in seen_ids:
                continue
            seen_ids.add(obj_id)

            name = props.get('name', '') or entity.get('name', '')
            display_props = {}
            for k in ('name', 'type', 'status', 'area', 'affiliation'):
                if k in props and props[k]:
                    display_props[k] = props[k]

            result_obj = ObjectQueryResult(
                object_id=obj_id,
                object_type=obj_type,
                properties=display_props,
                links=[],
                available_actions=[],
                source="graph",
            )

            if query.include_links and query.link_depth > 0:
                result_obj.links = await self._get_links(obj_id, obj_type, depth=query.link_depth)

            object_results.append(result_obj)

        return SemanticQueryResponse(
            results=object_results,
            total=len(object_results),
        )

    # ── Get Single Object (Full Assembly) ──

    async def get_object(self, object_id: str, object_type: str = None) -> Optional[ObjectQueryResult]:
        query = ObjectQuery(
            object_type=object_type,
            filters=[],
            limit=1,
            include_links=True,
            include_actions=True,
            link_depth=1,
        )
        response = await self.query_objects(query)
        if response.results:
            return response.results[0]
        return None

    # ── Private: Source-specific Fetchers ──

    async def _query_by_type(self, query: ObjectQuery) -> Tuple[List[ObjectQueryResult], int]:
        results = []
        type_def = self.oms.get_object_type(query.object_type)
        if not type_def:
            return [], 0

        try:
            entities = self.graph.query_entities(entity_type=query.object_type)
        except Exception as e:
            logger.warning(f"Graph query for type {query.object_type} failed: {e}")
            entities = []

        filtered = []
        for entity in entities:
            e_dict = entity.to_dict() if hasattr(entity, 'to_dict') else dict(entity)
            eid = e_dict.get('id', '')
            props = e_dict.get('properties', {})
            name = props.get('name', '')

            if not self._match_filters(props, query.filters):
                continue

            filtered.append(ObjectQueryResult(
                object_id=eid,
                object_type=query.object_type,
                properties={k: v for k, v in props.items() if v is not None},
                links=[],
                available_actions=[],
                source="graph",
            ))

        return filtered, len(filtered)

    async def _fetch_from_graph(self, query: ObjectQuery) -> List[ObjectQueryResult]:
        results = []
        try:
            all_entities = self.graph.query_entities(workspace_id=None)
            for entity in all_entities:
                e_dict = entity.to_dict() if hasattr(entity, 'to_dict') else dict(entity)
                eid = e_dict.get('id', '')
                etype = e_dict.get('type', 'Entity')
                props = e_dict.get('properties', {})

                if query.object_type and etype != query.object_type:
                    continue
                if not self._match_filters(props, query.filters):
                    continue

                results.append(ObjectQueryResult(
                    object_id=eid,
                    object_type=etype,
                    properties={k: v for k, v in props.items() if v is not None},
                    links=[],
                    available_actions=[],
                    source="graph",
                ))
        except Exception as e:
            logger.warning(f"Graph fetch failed: {e}")
        return results

    async def _fetch_from_business(self, query: ObjectQuery) -> List[ObjectQueryResult]:
        results = []
        try:
            processes = self.business.list_processes()
            for p in processes:
                pid = p.get('process_id', p.get('id', ''))
                pname = p.get('display_name', p.get('name', ''))
                pdict = dict(p)
                if query.filters and not self._match_filters(pdict, query.filters):
                    continue
                results.append(ObjectQueryResult(
                    object_id=pid,
                    object_type='BusinessProcess',
                    properties={'name': pname, 'description': p.get('description', ''), **{k: v for k, v in pdict.items() if k not in ('process_id',)}},
                    links=[],
                    available_actions=[],
                    source="business_sqlite",
                ))

            rules = self.business.list_rules()
            for r in rules:
                rid = r.get('rule_id', r.get('id', ''))
                rname = r.get('display_name', r.get('name', ''))
                rdict = dict(r)
                if query.filters and not self._match_filters(rdict, query.filters):
                    continue
                results.append(ObjectQueryResult(
                    object_id=rid,
                    object_type='BusinessRule',
                    properties={'name': rname, 'description': r.get('description', ''), **{k: v for k, v in rdict.items() if k not in ('rule_id',)}},
                    links=[],
                    available_actions=[],
                    source="business_sqlite",
                ))

            logics = self.business.list_logics()
            for l in logics:
                lid = l.get('logic_id', l.get('id', ''))
                lname = l.get('display_name', l.get('name', ''))
                ldict = dict(l)
                if query.filters and not self._match_filters(ldict, query.filters):
                    continue
                results.append(ObjectQueryResult(
                    object_id=lid,
                    object_type='BusinessLogic',
                    properties={'name': lname, 'description': l.get('description', ''), **{k: v for k, v in ldict.items() if k not in ('logic_id',)}},
                    links=[],
                    available_actions=[],
                    source="business_sqlite",
                ))

            indicators = self.business.list_indicators()
            for i in indicators:
                iid = i.get('indicator_id', i.get('id', ''))
                iname = i.get('display_name', i.get('name', ''))
                idict = dict(i)
                if query.filters and not self._match_filters(idict, query.filters):
                    continue
                results.append(ObjectQueryResult(
                    object_id=iid,
                    object_type='Indicator',
                    properties={'name': iname, 'description': i.get('description', ''), **{k: v for k, v in idict.items() if k not in ('indicator_id',)}},
                    links=[],
                    available_actions=[],
                    source="business_sqlite",
                ))
        except Exception as e:
            logger.warning(f"Business storage fetch failed: {e}")
        return results

    async def _fetch_from_knowledge_base(self, query: ObjectQuery) -> List[ObjectQueryResult]:
        results = []
        try:
            from odap.biz.data.knowledge_base.services import get_kb_service
            kb_svc = get_kb_service()
            kbs = kb_svc.list_knowledge_bases()
            for kb in kbs:
                kid = kb.get('kb_id', '')
                kname = kb.get('name', '')
                if query.filters and not self._match_filters(kb, query.filters):
                    continue
                results.append(ObjectQueryResult(
                    object_id=kid,
                    object_type='KnowledgeBase',
                    properties={'name': kname, 'description': kb.get('description', ''),
                                'document_count': kb.get('knowledge_count', 0)},
                    links=[],
                    available_actions=[],
                    source="kb_sqlite",
                ))
        except Exception as e:
            logger.warning(f"KB storage fetch failed: {e}")
        return results

    async def _fetch_from_agents(self, query: ObjectQuery) -> List[ObjectQueryResult]:
        results = []
        try:
            from odap.biz.management.agent_management.api.routes import agent_service as _agent_svc
            agents = _agent_svc.list_agents()
            for a in agents:
                aid = a.get('agent_id', '')
                aname = a.get('display_name', a.get('name', ''))
                if query.filters and not self._match_filters(a, query.filters):
                    continue
                results.append(ObjectQueryResult(
                    object_id=aid,
                    object_type='Agent',
                    properties={'name': aname, 'main_object': a.get('main_object', ''),
                                'skills': a.get('related_skills', [])},
                    links=[],
                    available_actions=[],
                    source="agent_sqlite",
                ))
        except Exception as e:
            logger.warning(f"Agent storage fetch failed: {e}")
        return results

    # ── Helpers ──

    def _match_filters(self, data: Dict[str, Any], filters: list) -> bool:
        if not filters:
            return True
        for f in filters:
            val = data.get(f.field)
            op = f.operator
            target = f.value
            if op == ObjectQueryOperator.EQ and val != target:
                return False
            elif op == ObjectQueryOperator.NE and val == target:
                return False
            elif op == ObjectQueryOperator.CONTAINS:
                s_val = str(val).lower()
                s_target = str(target).lower()
                if s_target not in s_val:
                    return False
            elif op == ObjectQueryOperator.IN:
                if val not in (target or []):
                    return False
            elif op == ObjectQueryOperator.IS_NULL and val is not None:
                return False
            elif op == ObjectQueryOperator.IS_NOT_NULL and val is None:
                return False
        return True

    def _apply_sorts(self, results: List[ObjectQueryResult], sorts: list) -> List[ObjectQueryResult]:
        for sort in reversed(sorts):
            reverse = not sort.ascending
            results.sort(key=lambda r: str(r.properties.get(sort.field, '')), reverse=reverse)
        return results

    async def _get_links(self, object_id: str, object_type: str, depth: int = 1) -> List[Dict[str, Any]]:
        if depth <= 0:
            return []
        links = []
        try:
            if hasattr(self.graph, '_mode') and self.graph._mode in ('neo4j_driver', 'graphiti'):
                relationships = []
                rels = self.graph.search(object_id, max_depth=depth)
                if isinstance(rels, list):
                    relationships = rels
                for rel in relationships:
                    rel_dict = rel.to_dict() if hasattr(rel, 'to_dict') else dict(rel)
                    links.append({
                        'target_id': rel_dict.get('target_id', rel_dict.get('id', '')),
                        'link_type': rel_dict.get('relation_type', rel_dict.get('type', '')),
                        'properties': {k: v for k, v in rel_dict.get('properties', {}).items() if v is not None},
                    })
            elif hasattr(self.graph, '_mode') and self.graph._mode == 'fallback':
                links = self._get_links_fallback(object_id, depth)
        except Exception as e:
            logger.debug(f"Get links for {object_id} failed: {e}")
        return links

    def _get_links_fallback(self, object_id: str, depth: int = 1) -> List[Dict[str, Any]]:
        if not hasattr(self.graph, 'fallback_graph') or self.graph.fallback_graph is None:
            return []
        links = []
        visited = set()
        frontier = [(object_id, 0)]
        while frontier:
            current_id, current_depth = frontier.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)
            if current_depth >= depth:
                continue
            try:
                relations = self.graph.get_entity_relations(current_id)
                for rel in relations:
                    target_id = rel.get('target', '')
                    link_type = rel.get('type', 'RELATES_TO')
                    direction = rel.get('direction', 'out')
                    if target_id and target_id not in visited:
                        link_props = {k: v for k, v in rel.get('properties', {}).items() if v is not None}
                        link_props['direction'] = direction
                        links.append({
                            'target_id': target_id,
                            'link_type': link_type,
                            'properties': link_props,
                        })
                        frontier.append((target_id, current_depth + 1))
            except Exception as e:
                logger.debug(f"Fallback link query for {current_id} failed: {e}")
        return links

    async def _get_available_actions(self, object_type: str) -> List[Dict[str, Any]]:
        actions = self.oms.list_action_types(target_type=object_type)
        return [{'action_type_id': a['action_type_id'], 'name': a['name'],
                 'display_name': a.get('display_name', a['name']),
                 'confirmation_required': a.get('confirmation_required', False)}
                for a in actions]


# Singleton instance
_object_service_instance = None


def get_object_service() -> ObjectService:
    global _object_service_instance
    if _object_service_instance is None:
        _object_service_instance = ObjectService()
    return _object_service_instance
