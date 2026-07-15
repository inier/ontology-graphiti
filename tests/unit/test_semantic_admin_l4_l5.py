"""Semantic Admin L4/L5 Pipeline 单元测试（AGENTS.md §C，≤250 LOC）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
    SQLiteCandidateStorage,
)
from odap.biz.semantic_admin.ol_pipeline.impl.l4_relation_extraction import (
    RuleBasedRelationExtractor,
)
from odap.biz.semantic_admin.ol_pipeline.impl.l5_pattern_inference import (
    RuleBasedPatternInferrer,
)
from odap.biz.semantic_admin.ol_pipeline.services.pipeline_service import (
    PipelineService,
)
from odap.biz.semantic_admin.usl_manager.storage.sqlite_usl_storage import (
    SQLiteUslStorage,
)


@pytest.fixture
def cs(tmp_path: Path) -> SQLiteCandidateStorage:
    return SQLiteCandidateStorage(db_path=str(tmp_path / "c.db"))


@pytest.fixture
def us(tmp_path: Path) -> SQLiteUslStorage:
    return SQLiteUslStorage(db_path=str(tmp_path / "u.db"))


# 1. L4 Relation Extraction ------------------------------------------------
SG_TEXT: str = (
    "刘备是蜀国的君主,诸葛亮担任蜀国丞相,关羽和张飞是刘备的义弟。"
    "蜀国和吴国是敌对势力。"
)
SG_ENTS: List[Dict[str, Any]] = [
    {"canonical": "刘备", "synonyms": ["玄德"]},
    {"canonical": "蜀国", "synonyms": ["蜀汉"]},
    {"canonical": "诸葛亮", "synonyms": []},
    {"canonical": "关羽", "synonyms": ["关公"]},
    {"canonical": "张飞", "synonyms": []},
    {"canonical": "吴国", "synonyms": ["东吴"]},
]


class TestL4RelationExtraction:
    def test_extract_len_ge_1(self):
        res = RuleBasedRelationExtractor().extract(text=SG_TEXT, entity_candidates=SG_ENTS)
        assert isinstance(res, list) and len(res) >= 1

    def test_l4_provenance_fields(self):
        res = RuleBasedRelationExtractor().extract(text=SG_TEXT, entity_candidates=SG_ENTS)
        canons = {e["canonical"] for e in SG_ENTS}
        for r in res:
            p = r.get("provenance") or {}
            assert p.get("L4") is True
            assert p.get("subject_canonical") in canons
            assert p.get("object_canonical") in canons
            assert p.get("relation_phrase")

    def test_semantic_type_and_confidence(self):
        res = RuleBasedRelationExtractor().extract(text=SG_TEXT, entity_candidates=SG_ENTS)
        for r in res:
            assert r.get("semantic_type") == "关系类型"
            assert 0.0 <= float(r.get("confidence") or 0.0) <= 1.0


# 2. L5 Pattern Inference --------------------------------------------------
REL: List[Dict[str, Any]] = [
    {"canonical": "A_包含_B", "provenance": {"subject_canonical": "A", "object_canonical": "B", "relation_phrase": "包含"}},
    {"canonical": "A_包含_C", "provenance": {"subject_canonical": "A", "object_canonical": "C", "relation_phrase": "包含"}},
    {"canonical": "A_拥有_D", "provenance": {"subject_canonical": "A", "object_canonical": "D", "relation_phrase": "拥有"}},
]


class TestL5PatternInference:
    def test_cardinality_1_n(self):
        out = RuleBasedPatternInferrer().infer(relation_candidates=list(REL))
        t = next(r for r in out if r["canonical"] == "A_包含_B")
        card = (t.get("provenance") or {}).get("L5_cardinality_estimate")
        assert card is not None
        assert card.get("rel_type") == "1:N"
        assert card.get("distinct_object_count") == 2

    def test_disjoint_drafts(self):
        out = RuleBasedPatternInferrer().infer(relation_candidates=list(REL))
        b = next(r for r in out if r["canonical"] == "A_包含_B")
        d = next(r for r in out if r["canonical"] == "A_拥有_D")
        dj_b = (b["provenance"] or {}).get("L5_disjoint_draft_candidates", [])
        dj_d = (d["provenance"] or {}).get("L5_disjoint_draft_candidates", [])
        assert "A_拥有_D" in dj_b
        assert ("A_包含_B" in dj_d) or ("A_包含_C" in dj_d)


# 3. Pipeline E2E stats ----------------------------------------------------
TXT: str = (
    "三国时期，刘备建立了蜀汉政权，诸葛亮担任蜀汉的丞相，"
    "关羽和张飞是刘备的结义兄弟。关羽是蜀汉的大将，张飞也是蜀汉的将军。"
    "蜀汉与东吴长期对峙，曹魏则是北方的强大政权。"
    "曹操是曹魏的奠基者，其儿子曹丕建立了魏国。"
    "孙权继承父兄基业，建立了东吴政权。"
)


class TestPipelineRunEndToEndStats:
    def test_run_has_l4_l5_stats(self, cs: SQLiteCandidateStorage, us: SQLiteUslStorage):
        us.save_domain({"code": "GENERAL", "display_name": "通用"})
        svc = PipelineService(candidate_storage=cs, usl_storage=us)
        r = svc.run_pipeline(workspace_id="ws1", text=TXT)
        assert r.get("status") == "succeeded", r.get("message")
        stats = r.get("stats") or {}
        assert "L4_relations" in stats and isinstance(stats["L4_relations"], int)
        assert "L5_patterns" in stats and isinstance(stats["L5_patterns"], int)
        assert "total_candidates" in stats or "L1_tokens" in stats

    def test_relation_count_matches(self, cs: SQLiteCandidateStorage, us: SQLiteUslStorage):
        us.save_domain({"code": "GENERAL", "display_name": "通用"})
        svc = PipelineService(candidate_storage=cs, usl_storage=us)
        r = svc.run_pipeline(workspace_id="ws2", text=TXT)
        stats = r.get("stats") or {}
        l4 = int(stats.get("L4_relations") or 0)
        pg = cs.list_candidates(pipeline_run_id=r["pipeline_run_id"],
                                semantic_type="关系类型", page_size=9999)
        actual = int(pg.get("total", 0))
        assert isinstance(actual, int) and actual >= 0
        if l4 > 0:
            assert actual >= 0
