import logging
import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from odap.infra.object_service.object_service import get_object_service
from odap.infra.object_service.schemas import (
    ObjectQueryResult, SemanticQuery, ObjectQuery,
    ObjectQueryFilter, ObjectQueryOperator,
)

logger = logging.getLogger(__name__)


class SemanticRetrievalResult(BaseModel):
    answer_context: str
    objects: List[ObjectQueryResult] = []
    links_summary: str = ""
    suggested_actions: List[Dict[str, Any]] = []


class SemanticObjectRetriever:
    def __init__(self):
        self._object_service = None

    @property
    def object_service(self):
        if self._object_service is None:
            self._object_service = get_object_service()
        return self._object_service

    async def retrieve(self, query_text: str, top_k: int = 10) -> SemanticRetrievalResult:
        semantic_results = await self.object_service.semantic_query(
            SemanticQuery(
                query_text=query_text,
                top_k=top_k,
                include_links=True,
                link_depth=1,
            )
        )

        if not semantic_results.results:
            return SemanticRetrievalResult(
                answer_context="",
                objects=[],
                links_summary="",
                suggested_actions=[],
            )

        context_parts = []
        for i, obj in enumerate(semantic_results.results, 1):
            obj_desc = self._describe_object(obj)
            link_desc = ""
            if obj.links:
                link_parts = []
                for link in obj.links:
                    link_parts.append(
                        f"  → [{link.get('link_type', 'related')}] {link.get('target_id', '')}"
                    )
                link_desc = "\n" + "\n".join(link_parts)
            context_parts.append(f"[{i}] {obj_desc}{link_desc}")

        answer_context = "\n".join(context_parts)
        links_summary = self._build_links_summary(semantic_results.results)
        suggested_actions = self._collect_suggested_actions(semantic_results.results)

        return SemanticRetrievalResult(
            answer_context=answer_context,
            objects=semantic_results.results,
            links_summary=links_summary,
            suggested_actions=suggested_actions,
        )

    async def retrieve_by_object_type(
        self,
        query_text: str,
        object_type: str,
        filters: Optional[List[Dict[str, Any]]] = None,
        top_k: int = 20,
    ) -> SemanticRetrievalResult:
        query_filters = []
        if filters:
            for f in filters:
                query_filters.append(ObjectQueryFilter(
                    field=f.get('field', ''),
                    operator=ObjectQueryOperator(f.get('operator', 'eq')),
                    value=f.get('value'),
                ))

        query = ObjectQuery(
            object_type=object_type,
            filters=query_filters,
            limit=top_k,
            include_links=True,
            include_actions=True,
            link_depth=1,
        )

        response = await self.object_service.query_objects(query)

        context_parts = []
        for i, obj in enumerate(response.results, 1):
            obj_desc = self._describe_object(obj)
            link_desc = ""
            if obj.links:
                link_parts = []
                for link in obj.links:
                    link_parts.append(
                        f"  → [{link.get('link_type', 'related')}] {link.get('target_id', '')}"
                    )
                link_desc = "\n" + "\n".join(link_parts)
            context_parts.append(f"[{i}] {obj_desc}{link_desc}")

        return SemanticRetrievalResult(
            answer_context="\n".join(context_parts),
            objects=response.results,
            links_summary=self._build_links_summary(response.results),
            suggested_actions=self._collect_suggested_actions(response.results),
        )

    def _describe_object(self, obj: ObjectQueryResult) -> str:
        name = obj.properties.get('name', obj.object_id)
        parts = [f"<{obj.object_type}> {name}"]

        key_props = []
        for key in ('status', 'area', 'affiliation', 'type', 'strength', 'description'):
            if key in obj.properties and obj.properties[key]:
                val = obj.properties[key]
                if isinstance(val, str) and len(val) > 100:
                    val = val[:100] + "..."
                key_props.append(f"{key}={val}")

        if key_props:
            parts.append("(" + ", ".join(key_props) + ")")

        return " ".join(parts)

    def _build_links_summary(self, objects: List[ObjectQueryResult]) -> str:
        link_count = sum(len(obj.links) for obj in objects)
        type_links: Dict[str, int] = {}
        for obj in objects:
            for link in obj.links:
                lt = link.get('link_type', 'unknown')
                type_links[lt] = type_links.get(lt, 0) + 1

        parts = [f"共 {len(objects)} 个对象, {link_count} 条关联"]
        if type_links:
            link_desc = ", ".join(f"{k}: {v}" for k, v in sorted(type_links.items()))
            parts.append(f"关联类型: {link_desc}")

        return "; ".join(parts)

    def _collect_suggested_actions(self, objects: List[ObjectQueryResult]) -> List[Dict[str, Any]]:
        actions = []
        seen = set()
        for obj in objects:
            for action in obj.available_actions:
                aid = action.get('action_type_id', '')
                if aid and aid not in seen:
                    seen.add(aid)
                    actions.append({
                        'action_type_id': aid,
                        'name': action.get('name', ''),
                        'display_name': action.get('display_name', ''),
                        'target_object_type': obj.object_type,
                        'confirmation_required': action.get('confirmation_required', False),
                    })
        return actions


_retriever_instance = None


def get_semantic_retriever() -> SemanticObjectRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = SemanticObjectRetriever()
    return _retriever_instance
