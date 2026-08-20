"""TDD 单元测试：候选实体解析（USL 术语字典驱动的确定性判重）。

验证本体论原则：
- 判重基于 USL 精确字典查表，而非字符相似度阈值
- 同义词归一化到同一 canonical → 判定重复
- 未命中 USL 的词不参与判重（宁可不判，不误判）

覆盖：
  T-ER-1: UslTermResolver 精确归一化（canonical/synonyms/aliases → canonical）
  T-ER-2: UslTermResolver 未命中返回原词（不猜测）
  T-ER-3: UslTermResolver 停用词不参与映射
  T-ER-4: EntityResolver 同义词候选判重（"势力" vs "阵营" → 同一 canonical）
  T-ER-5: EntityResolver 未命中候选不判重（不误判）
  T-ER-6: EntityResolver workspace 隔离
  T-ER-7: is_duplicate 精确判定
"""

from __future__ import annotations

import pytest

from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import (
    UslTermResolver,
)
from odap.biz.semantic_admin.candidate_store.services.entity_resolution import (
    EntityResolver,
    TwoStageEntityResolver,
)


@pytest.fixture
def terms():
    """标准 USL 术语（势力/人物，含同义词/别名）"""
    return [
        {
            "canonical": "势力",
            "semantic_type": "对象类型",
            "synonyms": ["阵营", "国家", "方"],
            "near_synonyms": ["军团", "集团", "诸侯"],
            "aliases": ["三国势力"],
            "stoplist_flag": False,
        },
        {
            "canonical": "人物",
            "semantic_type": "对象类型",
            "synonyms": ["角色", "人物形象"],
            "near_synonyms": [],
            "aliases": [],
            "stoplist_flag": False,
        },
        {
            "canonical": "停用词例",
            "semantic_type": "对象类型",
            "synonyms": ["无用词"],
            "near_synonyms": [],
            "aliases": [],
            "stoplist_flag": True,
        },
    ]


class TestUslTermResolver:
    def test_resolve_synonym_to_canonical(self, terms):
        resolver = UslTermResolver()
        resolver.load_terms("d1", terms)
        # 同义词/别名 → canonical
        assert resolver.resolve("阵营", "d1") == "势力"
        assert resolver.resolve("国家", "d1") == "势力"
        assert resolver.resolve("三国势力", "d1") == "势力"
        # canonical 自身
        assert resolver.resolve("势力", "d1") == "势力"

    def test_resolve_unknown_returns_original(self, terms):
        resolver = UslTermResolver()
        resolver.load_terms("d1", terms)
        # 未命中 → 原词，不猜测
        assert resolver.resolve("不明词", "d1") == "不明词"

    def test_stoplist_not_mapped(self, terms):
        resolver = UslTermResolver()
        resolver.load_terms("d1", terms)
        # 停用词的 canonical 和 synonyms 都不参与映射
        assert resolver.resolve("停用词例", "d1") == "停用词例"
        assert resolver.resolve("无用词", "d1") == "无用词"

    def test_canonical_of_returns_none_for_unknown(self, terms):
        resolver = UslTermResolver()
        resolver.load_terms("d1", terms)
        assert resolver.canonical_of("势力", "d1") == "势力"
        assert resolver.canonical_of("不明词", "d1") is None


class TestEntityResolver:
    def test_synonym_candidates_dedup(self, terms):
        resolver = EntityResolver()
        resolver.load_usl_terms("d1", terms)
        candidates = [
            {"id": "c1", "canonical": "势力", "workspace_id": "ws1"},
            {"id": "c2", "canonical": "阵营", "workspace_id": "ws1"},  # 同义词 → 势力
            {"id": "c3", "canonical": "国家", "workspace_id": "ws1"},  # 同义词 → 势力
        ]
        result = resolver.resolve_duplicates(candidates, domain_id="d1", workspace_id="ws1")
        assert result["duplicate_count"] == 1
        group_ids = set(result["duplicate_groups"][0]["candidate_ids"])
        assert group_ids == {"c1", "c2", "c3"}

    def test_unresolved_candidates_not_dedup(self, terms):
        resolver = EntityResolver()
        resolver.load_usl_terms("d1", terms)
        candidates = [
            {"id": "c1", "canonical": "未知词甲", "workspace_id": "ws1"},
            {"id": "c2", "canonical": "未知词乙", "workspace_id": "ws1"},
        ]
        result = resolver.resolve_duplicates(candidates, domain_id="d1", workspace_id="ws1")
        # 未命中 USL → 不判重（宁可不判，不误判）
        assert result["duplicate_count"] == 0
        assert result["unresolved_count"] == 2

    def test_workspace_isolation(self, terms):
        resolver = EntityResolver()
        resolver.load_usl_terms("d1", terms)
        candidates = [
            {"id": "c1", "canonical": "势力", "workspace_id": "ws1"},
            {"id": "c2", "canonical": "阵营", "workspace_id": "ws2"},  # 不同 ws
        ]
        result = resolver.resolve_duplicates(candidates, domain_id="d1", workspace_id="ws1")
        assert result["duplicate_count"] == 0

    def test_is_duplicate(self, terms):
        resolver = EntityResolver()
        resolver.load_usl_terms("d1", terms)
        # 同义词 → 重复
        assert resolver.is_duplicate("势力", "阵营", "d1") is True
        # 不同 canonical → 不重复
        assert resolver.is_duplicate("势力", "人物", "d1") is False
        # 未命中 → 不判重
        assert resolver.is_duplicate("未知甲", "未知乙", "d1") is False

    def test_backward_compat_alias(self, terms):
        # TwoStageEntityResolver 是 EntityResolver 的别名
        assert TwoStageEntityResolver is EntityResolver
