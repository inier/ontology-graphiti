import math
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from ..interfaces import IOntologyMemoryEngine
from ..models import (
    MemoryEntry, MemoryType, MemoryStatus, MemoryConsolidation,
    HybridRetrievalResult, RetrievalMethod, DecayConfig
)
from ..storage import Storage


class OntologyMemoryEngine(IOntologyMemoryEngine):
    def __init__(self, storage: Storage = None):
        self.storage = storage or Storage()

    def store(self, entry: MemoryEntry) -> MemoryEntry:
        if not entry.keywords:
            entry.keywords = self._extract_keywords(entry.content)
        if not entry.entities:
            entry.entities = self._extract_entities(entry.content)
        self.storage.save_memory(entry)
        return entry

    def retrieve(self, query: str, memory_type: Optional[MemoryType] = None,
                 top_k: int = 10, scenario_id: Optional[str] = None,
                 method_weights: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        weights = method_weights or {
            "vector": 0.3,
            "keyword": 0.3,
            "graph": 0.2,
            "temporal": 0.2
        }
        filters = {}
        if memory_type:
            filters["memory_type"] = memory_type.value
        if scenario_id:
            filters["source_scenario_id"] = scenario_id
        filters["status"] = MemoryStatus.ACTIVE.value
        all_memories = self.storage.list_memories(filters=filters, page=1, page_size=1000)
        if not all_memories:
            return []
        query_keywords = self._extract_keywords(query)
        query_entities = self._extract_entities(query)
        results = []
        for entry in all_memories:
            vector_score = self._vector_search(query, entry)
            keyword_score = self._keyword_search(query_keywords, entry)
            graph_score = self._graph_search(query_entities, entry)
            temporal_score = self._temporal_search(entry)
            combined_score = (
                weights.get("vector", 0.3) * vector_score +
                weights.get("keyword", 0.3) * keyword_score +
                weights.get("graph", 0.2) * graph_score +
                weights.get("temporal", 0.2) * temporal_score
            )
            combined_score *= entry.decay_factor
            methods_used = []
            if vector_score > 0.01:
                methods_used.append(RetrievalMethod.VECTOR_SIMILARITY)
            if keyword_score > 0.01:
                methods_used.append(RetrievalMethod.KEYWORD_BM25)
            if graph_score > 0.01:
                methods_used.append(RetrievalMethod.GRAPH_TRAVERSAL)
            if temporal_score > 0.01:
                methods_used.append(RetrievalMethod.TEMPORAL_WEIGHT)
            if len(methods_used) > 1:
                methods_used.append(RetrievalMethod.HYBRID)
            result = HybridRetrievalResult(
                entry=entry,
                score=combined_score,
                retrieval_methods=methods_used,
                vector_score=vector_score,
                keyword_score=keyword_score,
                graph_score=graph_score,
                temporal_score=temporal_score
            )
            results.append(result)
        results.sort(key=lambda r: r.score, reverse=True)
        top_results = results[:top_k]
        for r in top_results:
            self.storage.update_memory_access(r.entry.memory_id)
        return [self._retrieval_result_to_dict(r) for r in top_results]

    def _vector_search(self, query: str, entry: MemoryEntry) -> float:
        if entry.embedding is None:
            return self._simple_text_similarity(query, entry.content)
        query_vec = self._simple_embed(query)
        return self._cosine_similarity(query_vec, entry.embedding)

    def _keyword_search(self, query_keywords: List[str], entry: MemoryEntry) -> float:
        if not query_keywords or not entry.keywords:
            return 0.0
        matching = len(set(query_keywords) & set(entry.keywords))
        total = len(set(query_keywords) | set(entry.keywords))
        if total == 0:
            return 0.0
        jaccard = matching / total
        tf_component = matching / max(len(query_keywords), 1)
        return 0.5 * jaccard + 0.5 * tf_component

    def _graph_search(self, query_entities: List[str], entry: MemoryEntry) -> float:
        if not query_entities or not entry.entities:
            return 0.0
        matching = len(set(query_entities) & set(entry.entities))
        total = len(set(query_entities) | set(entry.entities))
        if total == 0:
            return 0.0
        return matching / total

    def _temporal_search(self, entry: MemoryEntry) -> float:
        now = datetime.now()
        age_hours = max((now - entry.created_at).total_seconds() / 3600, 0)
        recency = math.exp(-age_hours / (30 * 24))
        frequency = min(entry.access_count / 10.0, 1.0)
        importance_norm = entry.importance
        return 0.4 * recency + 0.3 * frequency + 0.3 * importance_norm

    def consolidate(self, memory_ids: List[str], strategy: str = "merge") -> Dict[str, Any]:
        source_entries = []
        for mid in memory_ids:
            entry = self.storage.get_memory(mid)
            if entry:
                source_entries.append(entry)
        if len(source_entries) < 2:
            return {"status": "error", "message": "At least 2 memories required for consolidation"}
        all_keywords = []
        all_entities = []
        all_content = []
        max_importance = 0.0
        for entry in source_entries:
            all_keywords.extend(entry.keywords)
            all_entities.extend(entry.entities)
            all_content.append(entry.content)
            max_importance = max(max_importance, entry.importance)
        merged_keywords = list(set(all_keywords))
        merged_entities = list(set(all_entities))
        merged_content = "\n---\n".join(all_content)
        merged_summary = self._generate_summary(all_content)
        new_importance = min(max_importance + 0.1, 1.0)
        consolidated_entry = MemoryEntry(
            memory_type=MemoryType.SEMANTIC,
            content=merged_content,
            summary=merged_summary,
            keywords=merged_keywords,
            entities=merged_entities,
            importance=new_importance,
            status=MemoryStatus.CONSOLIDATED,
            metadata={"consolidated_from": memory_ids, "strategy": strategy}
        )
        self.storage.save_memory(consolidated_entry)
        consolidation = MemoryConsolidation(
            source_ids=memory_ids,
            result_id=consolidated_entry.memory_id,
            strategy=strategy,
            summary=merged_summary,
            importance=new_importance
        )
        self.storage.save_consolidation(consolidation)
        for mid in memory_ids:
            self.storage.update_memory(mid, {"status": MemoryStatus.CONSOLIDATED.value})
        return {
            "consolidation_id": consolidation.consolidation_id,
            "result_id": consolidated_entry.memory_id,
            "source_ids": memory_ids,
            "strategy": strategy,
            "summary": merged_summary,
            "importance": new_importance,
            "created_at": consolidation.created_at.isoformat()
        }

    def decay_update(self, config: Optional[DecayConfig] = None) -> Dict[str, Any]:
        cfg = config or DecayConfig()
        all_memories = self.storage.list_memories(
            filters={"status": MemoryStatus.ACTIVE.value},
            page=1, page_size=10000
        )
        updated_count = 0
        now = datetime.now()
        for entry in all_memories:
            age_days = max((now - entry.created_at).total_seconds() / 86400, 0)
            base_decay = math.pow(0.5, age_days / cfg.half_life_days)
            access_boost = min(entry.access_count * cfg.access_boost, 1.0)
            importance_factor = entry.importance * cfg.importance_weight
            recency_factor = base_decay * cfg.recency_weight
            frequency_factor = access_boost * cfg.frequency_weight
            new_decay = importance_factor + recency_factor + frequency_factor
            new_decay = max(new_decay, cfg.min_decay_factor)
            new_decay = min(new_decay, 1.0)
            self.storage.update_memory(entry.memory_id, {"decay_factor": new_decay})
            updated_count += 1
        return {
            "updated_count": updated_count,
            "config": {
                "half_life_days": cfg.half_life_days,
                "min_decay_factor": cfg.min_decay_factor,
                "access_boost": cfg.access_boost,
                "importance_weight": cfg.importance_weight,
                "recency_weight": cfg.recency_weight,
                "frequency_weight": cfg.frequency_weight
            }
        }

    def forget(self, threshold: float = 0.1, archive: bool = False) -> Dict[str, Any]:
        all_memories = self.storage.list_memories(
            filters={"status": MemoryStatus.ACTIVE.value},
            page=1, page_size=10000
        )
        forgotten_ids = []
        new_status = MemoryStatus.ARCHIVED if archive else MemoryStatus.DECAYED
        for entry in all_memories:
            if entry.decay_factor < threshold:
                self.storage.update_memory(entry.memory_id, {"status": new_status.value})
                forgotten_ids.append(entry.memory_id)
        return {
            "forgotten_count": len(forgotten_ids),
            "forgotten_ids": forgotten_ids,
            "new_status": new_status.value,
            "threshold": threshold
        }

    def get_statistics(self, scenario_id: Optional[str] = None) -> Dict[str, Any]:
        filters = {}
        if scenario_id:
            filters["source_scenario_id"] = scenario_id
        total = self.storage.count_memories(filters=filters if filters else None)
        stats = {"total": total, "by_type": {}, "by_status": {}}
        for mt in MemoryType:
            type_filters = dict(filters)
            type_filters["memory_type"] = mt.value
            stats["by_type"][mt.value] = self.storage.count_memories(filters=type_filters)
        for ms in MemoryStatus:
            status_filters = dict(filters)
            status_filters["status"] = ms.value
            stats["by_status"][ms.value] = self.storage.count_memories(filters=status_filters)
        return stats

    def _extract_keywords(self, text: str) -> List[str]:
        if not text:
            return []
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', text.lower())
        return list(set(words))[:20]

    def _extract_entities(self, text: str) -> List[str]:
        if not text:
            return []
        patterns = [
            r'[\u4e00-\u9fff]{2,6}(?:公司|集团|机构|部门|系统|平台)',
            r'[A-Z][a-z]+(?:\s[A-Z][a-z]+)*',
        ]
        entities = []
        for pattern in patterns:
            entities.extend(re.findall(pattern, text))
        return list(set(entities))[:10]

    def _simple_text_similarity(self, text1: str, text2: str) -> float:
        words1 = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', text1.lower()))
        words2 = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', text2.lower()))
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    def _simple_embed(self, text: str) -> List[float]:
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', text.lower())
        if not words:
            return [0.0] * 8
        vec = [0.0] * 8
        for i, w in enumerate(words[:8]):
            vec[i % 8] = sum(ord(c) for c in w) / 1000.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2:
            return 0.0
        min_len = min(len(vec1), len(vec2))
        v1 = vec1[:min_len]
        v2 = vec2[:min_len]
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def _generate_summary(self, contents: List[str]) -> str:
        if not contents:
            return ""
        all_text = " ".join(contents)
        if len(all_text) <= 200:
            return all_text
        return all_text[:197] + "..."

    def _retrieval_result_to_dict(self, result: HybridRetrievalResult) -> Dict[str, Any]:
        entry = result.entry
        return {
            "memory_id": entry.memory_id,
            "memory_type": entry.memory_type.value,
            "content": entry.content,
            "summary": entry.summary,
            "keywords": entry.keywords,
            "entities": entry.entities,
            "importance": entry.importance,
            "decay_factor": entry.decay_factor,
            "status": entry.status.value,
            "score": result.score,
            "retrieval_methods": [m.value for m in result.retrieval_methods],
            "vector_score": result.vector_score,
            "keyword_score": result.keyword_score,
            "graph_score": result.graph_score,
            "temporal_score": result.temporal_score,
            "created_at": entry.created_at.isoformat(),
            "last_accessed_at": entry.last_accessed_at.isoformat()
        }
