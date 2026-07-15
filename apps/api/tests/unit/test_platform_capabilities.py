"""
TDD Phase 0: 平台核心服务能力验证

行为列表:
  B0-1: OMS 服务可创建/查询/删除 object-type
  B0-2: OMS 服务可创建/查询/删除 action-type
  B0-3: Agent Management API 可创建/查询智能体
  B0-4: NL 查询 API 可分发自然语言查询
  B0-5: 语义层 Disambiguator 可注册和消歧术语

运行方式:
  cd E:\\DEMO\\AI\\ontology-graphiti
  python -m pytest tests/unit/test_platform_capabilities.py -v
"""

import pytest
import json
import os
import sys
import tempfile

# 确保项目路径在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ============================================================
# B0-1: OMS 服务可创建/查询/删除 object-type
# ============================================================

class TestOMSObjectTypes:
    """验证 OMS 服务对对象类型的 CRUD 操作"""

    def setup_method(self):
        """每个测试前创建临时数据库"""
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_oms.db")

    def teardown_method(self):
        """清理临时文件"""
        import shutil
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _get_oms_storage(self):
        """获取 OMS 存储（使用临时数据库）"""
        from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
        storage = SQLiteOMSStorage(db_path=self.db_path)
        return storage

    def test_create_object_type(self):
        """B0-1a: 创建对象类型"""
        storage = self._get_oms_storage()
        data = {
            "type_id": "test_character",
            "name": "人物/Character",
            "display_name": "测试人物",
            "description": "测试用人物类型",
            "properties": json.dumps([
                {"name": "name", "display_name": "姓名", "property_type": "string", "required": True},
                {"name": "age", "display_name": "年龄", "property_type": "integer", "required": False},
            ]),
            "links": json.dumps([]),
            "actions": json.dumps([]),
        }
        result = storage.create_object_type(data)
        assert result is not None, "创建对象类型应返回非空结果"

    def test_get_object_type(self):
        """B0-1b: 查询已创建的对象类型"""
        storage = self._get_oms_storage()
        data = {
            "type_id": "test_faction",
            "name": "势力/Faction",
            "display_name": "测试势力",
            "description": "测试用势力类型",
            "properties": json.dumps([]),
            "links": json.dumps([]),
            "actions": json.dumps([]),
        }
        storage.create_object_type(data)
        result = storage.get_object_type("test_faction")
        assert result is not None, "查询已创建类型应返回非空"
        assert result["type_id"] == "test_faction"
        assert result["name"] == "势力/Faction"
        assert result["display_name"] == "测试势力"

    def test_list_object_types(self):
        """B0-1c: 列出所有对象类型"""
        storage = self._get_oms_storage()
        for i, (tid, dname) in enumerate([("t1", "类型一"), ("t2", "类型二"), ("t3", "类型三")]):
            storage.create_object_type({
                "type_id": tid,
                "name": f"类型{tid}",
                "display_name": dname,
                "description": f"测试类型{i}",
                "properties": json.dumps([]),
                "links": json.dumps([]),
                "actions": json.dumps([]),
            })
        results = storage.list_object_types()
        assert len(results) >= 3, f"应有至少3个类型，实际{len(results)}"

    def test_delete_object_type(self):
        """B0-1d: 删除对象类型"""
        storage = self._get_oms_storage()
        data = {
            "type_id": "test_to_delete",
            "name": "待删除/DeleteMe",
            "display_name": "待删除类型",
            "description": "将被删除的类型",
            "properties": json.dumps([]),
            "links": json.dumps([]),
            "actions": json.dumps([]),
        }
        storage.create_object_type(data)
        # 确认存在
        assert storage.get_object_type("test_to_delete") is not None
        # 删除
        result = storage.delete_object_type("test_to_delete")
        assert result is True, "删除应返回 True"
        # 确认已删除
        assert storage.get_object_type("test_to_delete") is None

    def test_update_object_type(self):
        """B0-1e: 更新对象类型"""
        storage = self._get_oms_storage()
        data = {
            "type_id": "test_update",
            "name": "原名称/OldName",
            "display_name": "原显示名",
            "description": "原始描述",
            "properties": json.dumps([]),
            "links": json.dumps([]),
            "actions": json.dumps([]),
        }
        storage.create_object_type(data)
        # 更新
        updated = storage.update_object_type("test_update", {
            "name": "新名称/NewName",
            "display_name": "新显示名",
        })
        assert updated is not None
        assert updated["name"] == "新名称/NewName"
        assert updated["display_name"] == "新显示名"


# ============================================================
# B0-2: OMS 服务可创建/查询/删除 action-type
# ============================================================

class TestOMSActionTypes:
    """验证 OMS 服务对动作类型的 CRUD 操作"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_oms.db")

    def teardown_method(self):
        import shutil
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _get_oms_storage(self):
        from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
        return SQLiteOMSStorage(db_path=self.db_path)

    def test_create_action_type(self):
        """B0-2a: 创建动作类型"""
        storage = self._get_oms_storage()
        data = {
            "action_type_id": "sanguo.进军",
            "name": "进军/March",
            "display_name": "进军",
            "description": "移动单位至某地",
            "target_object_type": "SanguoCharacter",
            "parameters": json.dumps([
                {"name": "destination", "display_name": "目标", "param_type": "string", "required": True},
            ]),
            "required_roles": json.dumps(["commander"]),
            "confirmation_required": False,
        }
        result = storage.create_action_type(data)
        assert result is not None

    def test_get_action_type(self):
        """B0-2b: 查询已创建的动作类型"""
        storage = self._get_oms_storage()
        data = {
            "action_type_id": "xiyou.降妖",
            "name": "降妖/SubdueDemon",
            "display_name": "降妖除魔",
            "description": "取经人降伏妖魔",
            "target_object_type": "XiyouCharacter",
            "parameters": json.dumps([]),
            "required_roles": json.dumps([]),
            "confirmation_required": False,
        }
        storage.create_action_type(data)
        result = storage.get_action_type("xiyou.降妖")
        assert result is not None
        assert result["display_name"] == "降妖除魔"

    def test_list_action_types(self):
        """B0-2c: 列出所有动作类型"""
        storage = self._get_oms_storage()
        for atid in ["at1", "at2"]:
            storage.create_action_type({
                "action_type_id": atid,
                "name": f"动作{atid}",
                "display_name": f"动作{atid}",
                "description": f"测试动作{atid}",
                "target_object_type": "TestType",
                "parameters": json.dumps([]),
                "required_roles": json.dumps([]),
                "confirmation_required": False,
            })
        results = storage.list_action_types()
        assert len(results) >= 2


# ============================================================
# B0-5: 语义层 Disambiguator 可注册和消歧术语
# ============================================================

class TestDisambiguator:
    """验证语义层 Disambiguator 的多领域支持"""

    def test_default_domain_terms(self):
        """B0-5a: 默认军事领域术语仍可用"""
        from odap.biz.data.qa.nl_pipeline.disambiguator import Disambiguator
        d = Disambiguator()
        result = d.disambiguate("传感器")
        assert result["canonical"] == "传感器"

    def test_add_sanguo_domain_terms(self):
        """B0-5b: 可注册三国领域术语"""
        from odap.biz.data.qa.nl_pipeline.disambiguator import Disambiguator
        d = Disambiguator()
        d.reset()
        d.add_synonym("人物", "将军")
        d.add_synonym("人物", "谋士")
        result = d.disambiguate("将军")
        assert result["canonical"] == "人物"

    def test_add_xiyou_domain_terms(self):
        """B0-5c: 可注册西游领域术语"""
        from odap.biz.data.qa.nl_pipeline.disambiguator import Disambiguator
        d = Disambiguator()
        d.reset()
        d.add_synonym("法宝", "兵器")
        d.add_synonym("法宝", "宝贝")
        result = d.disambiguate("兵器")
        assert result["canonical"] == "法宝"

    def test_chinese_english_mapping(self):
        """B0-5d: 支持中英文映射查询"""
        from odap.biz.data.qa.nl_pipeline.disambiguator import Disambiguator
        d = Disambiguator()
        d.reset()
        d.add_synonym("人物", "Character")
        d.add_synonym("人物", "角色")
        result = d.disambiguate("Character")
        assert result["canonical"] == "人物"
        # 中文也能找到
        result2 = d.disambiguate("角色")
        assert result2["canonical"] == "人物"

    def test_expansion_rules(self):
        """B0-5e: 支持扩展规则"""
        from odap.biz.data.qa.nl_pipeline.disambiguator import Disambiguator
        d = Disambiguator()
        d.reset()
        d.add_expansion_rule("人物", "三国人物")
        d.add_expansion_rule("人物", "西游人物")
        result = d.disambiguate("人物")
        assert "三国人物" in result["expansions"]
        assert "西游人物" in result["expansions"]
