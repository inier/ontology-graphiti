"""BM25 精准关键词检索支柱"""

import logging
import os
import pickle
import re
from typing import Any, Dict, List, Optional

from odap.biz.data.qa.models import RetrievalResult, RetrievalPillar

logger = logging.getLogger(__name__)


def _tokenize_chinese(text: str) -> List[str]:
    """中文分词: 按连续中文字符(>=2字) + 英文单词拆分"""
    tokens: List[str] = []
    # 连续中文字符片段(>=2字)
    for m in re.finditer(r'[\u4e00-\u9fff]{2,}', text):
        segment = m.group()
        # 2-gram + 3-gram
        for n in (2, 3):
            for i in range(len(segment) - n + 1):
                tokens.append(segment[i:i + n])
    # 英文单词
    for m in re.finditer(r'[a-zA-Z][a-zA-Z0-9_]*', text):
        tokens.append(m.group().lower())
    return tokens


class BM25IndexManager:
    """BM25 索引管理器: 构建/持久化/增量更新"""

    def __init__(self, index_dir: Optional[str] = None):
        self.index_dir = index_dir or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "bm25_indices"
        )
        os.makedirs(self.index_dir, exist_ok=True)
        self._indices: Dict[str, Any] = {}      # key: "{ws_id}_{scenario_id}"
        self._corpus: Dict[str, List[Dict]] = {} # key 同上, 存原始文档

    def _index_key(self, workspace_id: str, scenario_id: Optional[str] = None) -> str:
        return f"{workspace_id}_{scenario_id or 'default'}"

    def _index_path(self, key: str) -> str:
        return os.path.join(self.index_dir, f"{key}.pkl")

    def build_index(self, workspace_id: str, scenario_id: Optional[str] = None,
                    documents: Optional[List[Dict[str, Any]]] = None) -> None:
        """构建 BM25 索引。若 documents 为 None, 从存储层加载。"""
        key = self._index_key(workspace_id, scenario_id)

        if documents is None:
            documents = self._load_documents_from_storage(workspace_id, scenario_id)

        if not documents:
            logger.warning(f"No documents to index for {key}")
            return

        corpus = []
        tokenized_corpus = []
        for doc in documents:
            content = doc.get("content", "") or doc.get("name", "") or ""
            if not content:
                continue
            corpus.append(doc)
            tokenized_corpus.append(_tokenize_chinese(content))

        if not tokenized_corpus:
            return

        try:
            from rank_bm25 import BM25Okapi
            index = BM25Okapi(tokenized_corpus)
            self._indices[key] = index
            self._corpus[key] = corpus
            # 持久化
            self._save_index(key, index, corpus)
            logger.info(f"BM25 index built for {key}: {len(corpus)} docs")
        except ImportError:
            logger.warning("rank_bm25 not installed, BM25 index not built")

    def update_index(self, workspace_id: str, scenario_id: Optional[str] = None,
                     document: Optional[Dict[str, Any]] = None) -> None:
        """增量更新索引（追加文档）。简单实现: 重建索引。"""
        key = self._index_key(workspace_id, scenario_id)
        existing = self._corpus.get(key, [])
        if document:
            existing.append(document)
        self.build_index(workspace_id, scenario_id, existing)

    def get_index(self, workspace_id: str, scenario_id: Optional[str] = None):
        """获取索引，优先内存，其次磁盘"""
        key = self._index_key(workspace_id, scenario_id)
        if key in self._indices:
            return self._indices[key], self._corpus.get(key, [])
        # 尝试从磁盘加载
        loaded = self._load_index(key)
        if loaded:
            index, corpus = loaded
            self._indices[key] = index
            self._corpus[key] = corpus
            return index, corpus
        return None, []

    def _save_index(self, key: str, index, corpus: List[Dict]) -> None:
        path = self._index_path(key)
        try:
            with open(path, "wb") as f:
                pickle.dump({"index": index, "corpus": corpus}, f)
        except Exception as e:
            logger.error(f"Failed to save BM25 index {key}: {e}")

    def _load_index(self, key: str):
        path = self._index_path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            return data["index"], data["corpus"]
        except Exception as e:
            logger.error(f"Failed to load BM25 index {key}: {e}")
            return None

    def _load_documents_from_storage(self, workspace_id: str,
                                      scenario_id: Optional[str] = None) -> List[Dict]:
        """从 SQLiteIngestStorage / SemanticMapStorage / ModelStorage 加载文档"""
        documents: List[Dict] = []

        # SQLiteIngestStorage
        try:
            from odap.biz.core.ontology.design.storage.sqlite_ingest_storage import SQLiteIngestStorage
            storage = SQLiteIngestStorage()
            entities = storage.list_entities(workspace_id=workspace_id, scenario_id=scenario_id)
            for e in (entities or []):
                documents.append({
                    "doc_id": e.get("entity_id", ""),
                    "content": f"{e.get('name', '')} {e.get('description', '')} {e.get('entity_type', '')}",
                    "source": "sqlite_ingest",
                    "metadata": e,
                })
        except Exception as e:
            logger.debug(f"SQLiteIngestStorage load failed: {e}")

        # SemanticMapStorage
        try:
            from odap.biz.data.semantic_map.storage import Storage as SemanticMapStorage
            storage = SemanticMapStorage()
            maps = storage.list_semantic_maps(workspace_id=workspace_id)
            for sm in (maps or []):
                objects = sm.get("objects", []) if isinstance(sm, dict) else []
                for obj in objects:
                    if isinstance(obj, dict):
                        documents.append({
                            "doc_id": obj.get("entity_id", ""),
                            "content": f"{obj.get('name', '')} {obj.get('object_type', '')}",
                            "source": "semantic_map",
                            "metadata": obj,
                        })
        except Exception as e:
            logger.debug(f"SemanticMapStorage load failed: {e}")

        # ModelStorage
        try:
            from odap.biz.core.ontology.design.model.storage.sqlite_model_storage import SQLiteModelStorage
            storage = SQLiteModelStorage()
            instances = storage.list_instances(workspace_id=workspace_id, scenario_id=scenario_id)
            for inst in (instances or []):
                documents.append({
                    "doc_id": inst.get("instance_id", ""),
                    "content": f"{inst.get('name', '')} {inst.get('type_name', '')} {inst.get('description', '')}",
                    "source": "model_storage",
                    "metadata": inst,
                })
        except Exception as e:
            logger.debug(f"ModelStorage load failed: {e}")

        logger.info(f"Loaded {len(documents)} documents for BM25 index (ws={workspace_id})")
        return documents


class BM25Retriever:
    """BM25 检索器"""

    def __init__(self, index_manager: Optional[BM25IndexManager] = None):
        self.index_manager = index_manager or BM25IndexManager()

    def search(self, query: str, top_k: int = 10,
               workspace_id: str = "",
               scenario_id: Optional[str] = None,
               filters: Optional[Dict[str, Any]] = None) -> List[RetrievalResult]:
        """BM25 关键词检索"""
        if not workspace_id:
            return []

        index, corpus = self.index_manager.get_index(workspace_id, scenario_id)
        if index is None or not corpus:
            # 尝试构建索引
            self.index_manager.build_index(workspace_id, scenario_id)
            index, corpus = self.index_manager.get_index(workspace_id, scenario_id)
            if index is None or not corpus:
                return []

        query_tokens = _tokenize_chinese(query)
        if not query_tokens:
            return []

        scores = index.get_scores(query_tokens)
        # 取 top_k
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results: List[RetrievalResult] = []
        for idx in top_indices:
            score = scores[idx]
            if score <= 0:
                continue
            doc = corpus[idx]
            # 应用过滤器
            if filters and not self._match_filters(doc, filters):
                continue
            results.append(RetrievalResult(
                doc_id=doc.get("doc_id", str(idx)),
                content=doc.get("content", ""),
                score=float(score),
                pillar=RetrievalPillar.BM25,
                source=doc.get("source", "bm25"),
                metadata=doc.get("metadata", {}),
            ))

        return results

    def _match_filters(self, doc: Dict, filters: Dict[str, Any]) -> bool:
        """简单过滤匹配"""
        metadata = doc.get("metadata", {})
        for key, value in filters.items():
            if key in metadata:
                if isinstance(value, list):
                    if metadata[key] not in value:
                        return False
                elif metadata[key] != value:
                    return False
        return True
