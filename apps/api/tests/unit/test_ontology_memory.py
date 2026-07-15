import pytest
import os
from datetime import datetime, timedelta
from unittest.mock import patch


def _make_memory(**overrides):
    from odap.biz.platform.ontology_memory.models import MemoryEntry, MemoryType, MemoryStatus
    defaults = {
        "memory_type": MemoryType.EPISODIC,
        "content": "测试记忆内容",
        "summary": "测试摘要",
        "keywords": ["测试", "记忆"],
        "entities": ["测试实体"],
        "importance": 0.5,
        "status": MemoryStatus.ACTIVE,
    }
    defaults.update(overrides)
    return MemoryEntry(**defaults)


class TestMemoryModels:
    def test_memory_type_enum(self):
        from odap.biz.platform.ontology_memory.models import MemoryType
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.PROCEDURAL.value == "procedural"
        assert MemoryType.WORKING.value == "working"
        assert issubclass(MemoryType, str)

    def test_memory_status_enum(self):
        from odap.biz.platform.ontology_memory.models import MemoryStatus
        assert MemoryStatus.ACTIVE.value == "active"
        assert MemoryStatus.CONSOLIDATED.value == "consolidated"
        assert MemoryStatus.DECAYED.value == "decayed"
        assert MemoryStatus.ARCHIVED.value == "archived"
        assert issubclass(MemoryStatus, str)

    def test_retrieval_method_enum(self):
        from odap.biz.platform.ontology_memory.models import RetrievalMethod
        assert issubclass(RetrievalMethod, str)
        assert RetrievalMethod.HYBRID.value == "hybrid"

    def test_memory_entry_defaults(self):
        from odap.biz.platform.ontology_memory.models import MemoryEntry, MemoryType, MemoryStatus
        entry = MemoryEntry(content="test")
        assert entry.memory_id
        assert entry.memory_type == MemoryType.EPISODIC
        assert entry.importance == 0.5
        assert entry.access_count == 0
        assert entry.decay_factor == 1.0
        assert entry.status == MemoryStatus.ACTIVE
        assert entry.keywords == []
        assert entry.entities == []
        assert entry.embedding is None
        assert entry.metadata == {}

    def test_memory_entry_with_overrides(self):
        from odap.biz.platform.ontology_memory.models import MemoryEntry, MemoryType, MemoryStatus
        entry = MemoryEntry(
            content="custom",
            memory_type=MemoryType.SEMANTIC,
            importance=0.9,
            keywords=["k1"],
            entities=["e1"],
            metadata={"key": "val"}
        )
        assert entry.memory_type == MemoryType.SEMANTIC
        assert entry.importance == 0.9
        assert entry.keywords == ["k1"]
        assert entry.metadata == {"key": "val"}

    def test_memory_consolidation_defaults(self):
        from odap.biz.platform.ontology_memory.models import MemoryConsolidation
        c = MemoryConsolidation(summary="test")
        assert c.consolidation_id
        assert c.strategy == "merge"
        assert c.source_ids == []
        assert c.result_id is None

    def test_hybrid_retrieval_result(self):
        from odap.biz.platform.ontology_memory.models import HybridRetrievalResult, MemoryEntry, RetrievalMethod
        entry = MemoryEntry(content="test")
        result = HybridRetrievalResult(entry=entry, score=0.8)
        assert result.score == 0.8
        assert result.vector_score == 0.0
        assert result.keyword_score == 0.0
        assert result.graph_score == 0.0
        assert result.temporal_score == 0.0

    def test_decay_config_defaults(self):
        from odap.biz.platform.ontology_memory.models import DecayConfig
        config = DecayConfig()
        assert config.half_life_days == 30.0
        assert config.min_decay_factor == 0.1
        assert config.access_boost == 0.2


class TestSQLiteOntologyMemoryStorage:
    def test_init_db(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        assert os.path.exists(db_path)

    def test_save_and_get_memory(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        entry = _make_memory()
        storage.save_memory(entry)
        result = storage.get_memory(entry.memory_id)
        assert result is not None
        assert result.memory_id == entry.memory_id
        assert result.content == entry.content
        assert result.keywords == entry.keywords
        assert result.entities == entry.entities

    def test_get_memory_not_found(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        result = storage.get_memory("nonexistent")
        assert result is None

    def test_list_memories(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        for i in range(5):
            storage.save_memory(_make_memory(content=f"content {i}"))
        results = storage.list_memories(page=1, page_size=10)
        assert len(results) == 5

    def test_list_memories_with_filter(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        from odap.biz.platform.ontology_memory.models import MemoryType
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        storage.save_memory(_make_memory(memory_type=MemoryType.EPISODIC))
        storage.save_memory(_make_memory(memory_type=MemoryType.SEMANTIC))
        results = storage.list_memories(filters={"memory_type": "episodic"})
        assert len(results) == 1
        assert results[0].memory_type == MemoryType.EPISODIC

    def test_delete_memory(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        entry = _make_memory()
        storage.save_memory(entry)
        assert storage.delete_memory(entry.memory_id) is True
        assert storage.get_memory(entry.memory_id) is None

    def test_delete_memory_not_found(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        assert storage.delete_memory("nonexistent") is False

    def test_update_memory_access(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        entry = _make_memory()
        storage.save_memory(entry)
        storage.update_memory_access(entry.memory_id)
        result = storage.get_memory(entry.memory_id)
        assert result.access_count == 1

    def test_update_memory(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        from odap.biz.platform.ontology_memory.models import MemoryStatus
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        entry = _make_memory()
        storage.save_memory(entry)
        storage.update_memory(entry.memory_id, {"decay_factor": 0.5, "status": MemoryStatus.DECAYED.value})
        result = storage.get_memory(entry.memory_id)
        assert result.decay_factor == 0.5
        assert result.status == MemoryStatus.DECAYED

    def test_json_fields_serialization(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        entry = _make_memory(
            keywords=["关键词1", "关键词2"],
            entities=["实体A", "实体B"],
            metadata={"source": "test", "version": 1}
        )
        storage.save_memory(entry)
        result = storage.get_memory(entry.memory_id)
        assert result.keywords == ["关键词1", "关键词2"]
        assert result.entities == ["实体A", "实体B"]
        assert result.metadata == {"source": "test", "version": 1}

    def test_save_and_list_consolidations(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        from odap.biz.platform.ontology_memory.models import MemoryConsolidation
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        c = MemoryConsolidation(
            source_ids=["id1", "id2"],
            result_id="result1",
            strategy="merge",
            summary="合并摘要",
            importance=0.8
        )
        storage.save_consolidation(c)
        results = storage.list_consolidations()
        assert len(results) == 1
        assert results[0].source_ids == ["id1", "id2"]
        assert results[0].importance == 0.8

    def test_count_memories(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        storage.save_memory(_make_memory())
        storage.save_memory(_make_memory())
        assert storage.count_memories() == 2

    def test_embedding_serialization(self, tmp_path):
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        entry = _make_memory(embedding=[0.1, 0.2, 0.3, 0.4])
        storage.save_memory(entry)
        result = storage.get_memory(entry.memory_id)
        assert result.embedding == [0.1, 0.2, 0.3, 0.4]


class TestOntologyMemoryEngine:
    def _make_engine(self, tmp_path):
        from odap.biz.platform.ontology_memory.impl.memory_engine import OntologyMemoryEngine
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        return OntologyMemoryEngine(storage=storage)

    def test_store(self, tmp_path):
        engine = self._make_engine(tmp_path)
        entry = _make_memory()
        result = engine.store(entry)
        assert result.memory_id == entry.memory_id
        assert result.keywords

    def test_store_auto_extract_keywords(self, tmp_path):
        engine = self._make_engine(tmp_path)
        entry = _make_memory(content="这是一个关于风险管理系统的测试", keywords=[])
        result = engine.store(entry)
        assert len(result.keywords) > 0

    def test_retrieve(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.store(_make_memory(content="风险管理是企业管理的重要组成部分", keywords=["风险管理"]))
        engine.store(_make_memory(content="数据分析需要使用Python编程语言", keywords=["数据分析"]))
        results = engine.retrieve("风险管理", top_k=5)
        assert len(results) > 0
        assert "score" in results[0]
        assert "retrieval_methods" in results[0]

    def test_retrieve_empty(self, tmp_path):
        engine = self._make_engine(tmp_path)
        results = engine.retrieve("test query")
        assert results == []

    def test_retrieve_with_type_filter(self, tmp_path):
        from odap.biz.platform.ontology_memory.models import MemoryType
        engine = self._make_engine(tmp_path)
        engine.store(_make_memory(memory_type=MemoryType.EPISODIC, content="情景记忆内容"))
        engine.store(_make_memory(memory_type=MemoryType.SEMANTIC, content="语义记忆内容"))
        results = engine.retrieve("记忆", memory_type=MemoryType.SEMANTIC)
        assert all(r["memory_type"] == "semantic" for r in results)

    def test_consolidate(self, tmp_path):
        engine = self._make_engine(tmp_path)
        e1 = engine.store(_make_memory(content="内容一", importance=0.6))
        e2 = engine.store(_make_memory(content="内容二", importance=0.7))
        result = engine.consolidate([e1.memory_id, e2.memory_id])
        assert result["result_id"]
        assert result["importance"] >= 0.7

    def test_consolidate_insufficient_memories(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine.consolidate(["single_id"])
        assert result["status"] == "error"

    def test_decay_update(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.store(_make_memory())
        result = engine.decay_update()
        assert "updated_count" in result
        assert result["updated_count"] == 1

    def test_forget(self, tmp_path):
        from odap.biz.platform.ontology_memory.models import MemoryStatus
        engine = self._make_engine(tmp_path)
        entry = _make_memory()
        engine.store(entry)
        engine.storage.update_memory(entry.memory_id, {"decay_factor": 0.05})
        result = engine.forget(threshold=0.1)
        assert result["forgotten_count"] == 1
        updated = engine.storage.get_memory(entry.memory_id)
        assert updated.status == MemoryStatus.DECAYED

    def test_forget_with_archive(self, tmp_path):
        from odap.biz.platform.ontology_memory.models import MemoryStatus
        engine = self._make_engine(tmp_path)
        entry = _make_memory()
        engine.store(entry)
        engine.storage.update_memory(entry.memory_id, {"decay_factor": 0.05})
        result = engine.forget(threshold=0.1, archive=True)
        assert result["forgotten_count"] == 1
        updated = engine.storage.get_memory(entry.memory_id)
        assert updated.status == MemoryStatus.ARCHIVED

    def test_get_statistics(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.store(_make_memory())
        stats = engine.get_statistics()
        assert "total" in stats
        assert "by_type" in stats
        assert "by_status" in stats
        assert stats["total"] >= 1


class TestOntologyMemoryService:
    def _make_service(self, tmp_path):
        from odap.biz.platform.ontology_memory.services.memory_service import OntologyMemoryService
        from odap.biz.platform.ontology_memory.impl.memory_engine import OntologyMemoryEngine
        from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
        db_path = str(tmp_path / "test_memory.db")
        storage = SQLiteOntologyMemoryStorage(db_path=db_path)
        service = OntologyMemoryService.__new__(OntologyMemoryService)
        service.engine = OntologyMemoryEngine(storage=storage)
        return service

    def test_store_memory(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.store_memory(
            memory_type="episodic",
            content="测试记忆",
            importance=0.7
        )
        assert "memory_id" in result
        assert result["memory_type"] == "episodic"

    def test_store_memory_invalid_type(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.store_memory(memory_type="invalid", content="test")
        assert result.get("status") == "error"

    def test_get_memory(self, tmp_path):
        service = self._make_service(tmp_path)
        stored = service.store_memory(memory_type="episodic", content="test")
        result = service.get_memory(stored["memory_id"])
        assert result["memory_id"] == stored["memory_id"]
        assert result["content"] == "test"

    def test_get_memory_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.get_memory("nonexistent")
        assert result.get("status") == "error"

    def test_list_memories(self, tmp_path):
        service = self._make_service(tmp_path)
        service.store_memory(memory_type="episodic", content="test1")
        service.store_memory(memory_type="semantic", content="test2")
        result = service.list_memories()
        assert "memories" in result
        assert result["total"] == 2

    def test_delete_memory(self, tmp_path):
        service = self._make_service(tmp_path)
        stored = service.store_memory(memory_type="episodic", content="test")
        result = service.delete_memory(stored["memory_id"])
        assert result["status"] == "success"

    def test_delete_memory_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.delete_memory("nonexistent")
        assert result["status"] == "error"

    def test_retrieve_memories(self, tmp_path):
        service = self._make_service(tmp_path)
        service.store_memory(memory_type="episodic", content="风险管理内容")
        result = service.retrieve_memories(query="风险管理")
        assert "results" in result

    def test_consolidate_memories(self, tmp_path):
        service = self._make_service(tmp_path)
        m1 = service.store_memory(memory_type="episodic", content="内容一", importance=0.6)
        m2 = service.store_memory(memory_type="episodic", content="内容二", importance=0.7)
        result = service.consolidate_memories(memory_ids=[m1["memory_id"], m2["memory_id"]])
        assert "result_id" in result

    def test_consolidate_memories_insufficient(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.consolidate_memories(memory_ids=["single"])
        assert result.get("status") == "error"

    def test_decay_update(self, tmp_path):
        service = self._make_service(tmp_path)
        service.store_memory(memory_type="episodic", content="test")
        result = service.decay_update()
        assert "updated_count" in result

    def test_forget_memories(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.forget_memories(threshold=0.1)
        assert "forgotten_count" in result

    def test_get_statistics(self, tmp_path):
        service = self._make_service(tmp_path)
        service.store_memory(memory_type="episodic", content="test")
        result = service.get_statistics()
        assert "total" in result
        assert result["total"] >= 1

    def test_service_returns_dict(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.store_memory(memory_type="episodic", content="test")
        assert isinstance(result, dict)
        result2 = service.get_memory(result["memory_id"])
        assert isinstance(result2, dict)


class TestSchemas:
    def test_store_memory_request(self):
        from odap.biz.platform.ontology_memory.api.schemas import StoreMemoryRequest
        req = StoreMemoryRequest(content="test")
        assert req.memory_type.value == "episodic"
        assert req.importance == 0.5

    def test_retrieve_memory_request(self):
        from odap.biz.platform.ontology_memory.api.schemas import RetrieveMemoryRequest
        req = RetrieveMemoryRequest(query="test query")
        assert req.top_k == 10

    def test_consolidate_memories_request(self):
        from odap.biz.platform.ontology_memory.api.schemas import ConsolidateMemoriesRequest
        req = ConsolidateMemoriesRequest(memory_ids=["id1", "id2"])
        assert req.strategy == "merge"

    def test_decay_update_request(self):
        from odap.biz.platform.ontology_memory.api.schemas import DecayUpdateRequest
        req = DecayUpdateRequest(half_life_days=15.0)
        assert req.half_life_days == 15.0
        assert req.min_decay_factor is None

    def test_forget_request(self):
        from odap.biz.platform.ontology_memory.api.schemas import ForgetRequest
        req = ForgetRequest(threshold=0.2, archive=True)
        assert req.threshold == 0.2
        assert req.archive is True
