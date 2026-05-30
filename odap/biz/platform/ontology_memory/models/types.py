from enum import Enum


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    WORKING = "working"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    CONSOLIDATED = "consolidated"
    DECAYED = "decayed"
    ARCHIVED = "archived"


class RetrievalMethod(str, Enum):
    VECTOR_SIMILARITY = "vector_similarity"
    KEYWORD_BM25 = "keyword_bm25"
    GRAPH_TRAVERSAL = "graph_traversal"
    TEMPORAL_WEIGHT = "temporal_weight"
    HYBRID = "hybrid"
