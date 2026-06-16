"""
TDD Phase 1-2: 语义层 + 三国本体测试

运行方式:
  cd E:\DEMO\AI\ontology-graphiti
  /c/Miniconda3/python.exe -m pytest tests/unit/test_domain_ontology.py -v --tb=short
"""

import pytest
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ============================================================
# B1-1~B1-3: 语义层多领域支持
# ============================================================

class TestSemanticLayer:
    """验证语义层多领域注册和中英映射"""

    def test_load_sanguo_semantic(self):
        """B1-1a: 加载三国语义配置"""
        from odap.biz.core.ontology.design.schema.semantic_layer.semantic_config import SANGUO_SEMANTIC
        assert SANGUO_SEMANTIC["domain"] == "sanguo"
        assert "en_mapping" in SANGUO_SEMANTIC
        assert "canonical_terms" in SANGUO_SEMANTIC
        assert SANGUO_SEMANTIC["en_mapping"]["势力"] == "Faction"

    def test_load_xiyou_semantic(self):
        """B1-1b: 加载西游语义配置"""
        from odap.biz.core.ontology.design.schema.semantic_layer.semantic_config import XIYOU_SEMANTIC
        assert XIYOU_SEMANTIC["domain"] == "xiyou"
        assert "canonical_terms" in XIYOU_SEMANTIC
        assert XIYOU_SEMANTIC["en_mapping"]["法宝"] == "Treasure"

    def test_sanguo_en_mapping_objects(self):
        """B1-2a: 三国中英文映射——对象类型"""
        from odap.biz.core.ontology.design.schema.semantic_layer.semantic_config import SANGUO_SEMANTIC
        em = SANGUO_SEMANTIC["en_mapping"]
        assert em["势力"] == "Faction"
        assert em["人物"] == "Character"
        assert em["地点"] == "Location"
        assert em["事件"] == "Event"
        assert em["谋略"] == "Strategy"
        assert em["物品"] == "Artifact"

    def test_xiyou_en_mapping_objects(self):
        """B1-2b: 西游中英文映射——对象类型"""
        from odap.biz.core.ontology.design.schema.semantic_layer.semantic_config import XIYOU_SEMANTIC
        em = XIYOU_SEMANTIC["en_mapping"]
        assert em["势力"] == "Faction"
        assert em["人物"] == "Character"
        assert em["法宝"] == "Treasure"
        assert em["法术"] == "Spell"
        assert "劫难" not in em  # "劫难"是事件的一种，在canonical_terms而非en_mapping

    def test_synonym_disambiguation(self):
        """B1-3a: 同义词消歧——三国"将军"→"人物" """
        from odap.biz.core.ontology.design.schema.semantic_layer.semantic_config import SANGUO_SEMANTIC
        term = SANGUO_SEMANTIC["canonical_terms"]["人物"]
        assert "将军" in term["synonyms"]
        assert "谋士" in term["synonyms"]
        assert "君主" in term["synonyms"]

    def test_xiyou_synonym_disambiguation(self):
        """B1-3b: 同义词消歧——西游"妖怪"→"人物" """
        from odap.biz.core.ontology.design.schema.semantic_layer.semantic_config import XIYOU_SEMANTIC
        term = XIYOU_SEMANTIC["canonical_terms"]["人物"]
        assert "妖怪" in term["synonyms"]
        assert "神仙" in term["synonyms"]
        assert "菩萨" in term["synonyms"]


# ============================================================
# B2-1~B2-3: 三国本体类型定义验证
# ============================================================

class TestSanguoOntology:
    """验证三国演义本体定义"""

    def test_sanguo_entity_type_defs(self):
        """B2-1: 三国7个对象类型定义完整"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        # 不依赖平台运行，只验证数据
        from sanguo_seed import FACTIONS, CHARACTERS, LOCATIONS, EVENTS, RELATIONSHIPS

        assert isinstance(FACTIONS, list) and len(FACTIONS) > 0, "势力数据不能为空"
        assert isinstance(CHARACTERS, list) and len(CHARACTERS) > 0, "人物数据不能为空"
        assert isinstance(LOCATIONS, list) and len(LOCATIONS) > 0, "地点数据不能为空"
        assert isinstance(EVENTS, list) and len(EVENTS) > 0, "事件数据不能为空"
        assert isinstance(RELATIONSHIPS, list) and len(RELATIONSHIPS) > 0, "关系数据不能为空"

    def test_sanguo_faction_data_fields(self):
        """B2-1b: 势力数据包含必要字段"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from sanguo_seed import FACTIONS
        for f in FACTIONS:
            assert "name" in f, "势力必须有name"
            assert "faction_id" in f, "势力必须有faction_id"

    def test_sanguo_character_data_fields(self):
        """B2-1c: 人物数据包含必要字段"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from sanguo_seed import CHARACTERS
        for c in CHARACTERS:
            assert "name" in c, "人物必须有name"
            assert "character_id" in c, "人物必须有character_id"
            assert "faction" in c, "人物必须有faction"

    def test_sanguo_event_data_fields(self):
        """B2-1d: 事件数据包含必要字段"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from sanguo_seed import EVENTS
        for e in EVENTS:
            assert "name" in e, "事件必须有name"
            assert "year" in e, "事件必须有year"


# ============================================================
# B3-1~B3-3: 西游记本体类型定义验证
# ============================================================

class TestXiyouOntology:
    """验证西游记本体定义"""

    def test_xiyou_entity_type_defs(self):
        """B3-1: 西游7个对象类型数据完整"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from xiyou_seed import FACTIONS, CHARACTERS, LOCATIONS, EVENTS, TREASURES, SPELLS, RELATIONSHIPS

        assert isinstance(FACTIONS, list) and len(FACTIONS) >= 4, f"势力数量应>=4，实际{len(FACTIONS)}"
        assert isinstance(CHARACTERS, list) and len(CHARACTERS) >= 15, f"人物数量应>=15，实际{len(CHARACTERS)}"
        assert isinstance(LOCATIONS, list) and len(LOCATIONS) >= 20, f"地点数量应>=20，实际{len(LOCATIONS)}"
        assert isinstance(EVENTS, list) and len(EVENTS) >= 20, f"事件数量应>=20，实际{len(EVENTS)}"
        assert isinstance(TREASURES, list) and len(TREASURES) >= 10, f"法宝数量应>=10，实际{len(TREASURES)}"
        assert isinstance(SPELLS, list) and len(SPELLS) >= 8, f"法术数量应>=8，实际{len(SPELLS)}"
        assert isinstance(RELATIONSHIPS, list) and len(RELATIONSHIPS) >= 25, f"关系数量应>=25，实际{len(RELATIONSHIPS)}"

    def test_xiyou_treasure_fields(self):
        """B3-1b: 法宝数据包含必要字段"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from xiyou_seed import TREASURES
        for t in TREASURES:
            assert "name" in t, "法宝必须有name"
            assert "holder" in t, f"{t.get('name')}法宝必须有holder"
            assert "treasure_type" in t, f"{t.get('name')}法宝必须有treasure_type"

    def test_xiyou_spell_fields(self):
        """B3-1c: 法术数据包含必要字段"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from xiyou_seed import SPELLS
        for s in SPELLS:
            assert "name" in s, "法术必须有name"
            assert "master" in s, f"{s.get('name')}法术必须有master"
            assert "spell_type" in s, f"{s.get('name')}法术必须有spell_type"

    def test_xiyou_event_trial_numbers(self):
        """B3-1d: 事件难数覆盖关键节点（1, 10, 50, 81）"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from xiyou_seed import EVENTS
        trial_numbers = {e.get("trial_number") for e in EVENTS if e.get("trial_number") is not None}
        # 关键检查点
        assert 1 in trial_numbers, "应有第1难"
        assert 4 in trial_numbers, "应有收伏悟空难"
        assert 50 in trial_numbers, "应有火焰山难"
        assert 81 in trial_numbers, "应有灵山取经难"

    def test_entity_type_build_script_has_all_types(self):
        """验证 build_xiyou_ontology.py 包含全部7个类型定义"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        import importlib
        spec = importlib.util.spec_from_file_location(
            "build_xiyou_ontology",
            os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "build_xiyou_ontology.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        types = mod.ENTITY_TYPE_DEFS
        expected = ["XiyouFaction", "XiyouCharacter", "XiyouLocation",
                     "XiyouEvent", "XiyouTreasure", "XiyouSpell", "XiyouRelationship"]
        for t in expected:
            assert t in types, f"缺少类型定义: {t}"

        # 验证每个类型有 display_name 和 properties
        for t in expected:
            assert "display_name" in types[t], f"{t}缺少display_name"
            assert "properties" in types[t], f"{t}缺少properties"
            assert len(types[t]["properties"]) > 0, f"{t}的properties不能为空"


# ============================================================
# B5-1~B5-2: 种子数据完整性验证
# ============================================================

class TestSeedDataIntegrity:
    """验证种子数据的完整性约束"""

    def test_xiyou_factions_count(self):
        """西游至少4个势力"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from xiyou_seed import FACTIONS
        faction_names = {f["name"] for f in FACTIONS}
        assert "天庭" in faction_names
        assert "佛门" in faction_names
        assert "妖界" in faction_names
        assert "人间" in faction_names

    def test_xiyou_tripitaka_team(self):
        """西游取经团队5人齐全"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from xiyou_seed import CHARACTERS
        team = {"唐僧", "孙悟空", "猪八戒", "沙僧", "白龙马"}
        names = {c["name"] for c in CHARACTERS}
        for member in team:
            assert member in names, f"取经团队成员 {member} 缺失"

    def test_xiyou_key_locations(self):
        """西游关键地点齐全"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from xiyou_seed import LOCATIONS
        names = {l["name"] for l in LOCATIONS}
        assert "花果山" in names, "缺少花果山"
        assert "五行山" in names, "缺少五行山"
        assert "火焰山" in names, "缺少火焰山"
        assert "灵山" in names, "缺少灵山"
        assert "长安" in names, "缺少长安"

    def test_sanguo_key_factions(self):
        """三国关键势力齐全"""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from sanguo_seed import FACTIONS
        names = {f["name"] for f in FACTIONS}
        assert "魏" in names or "曹魏" in names, "缺少魏"
        assert "蜀" in names or "蜀汉" in names, "缺少蜀"
        assert "吴" in names or "东吴" in names, "缺少吴"
