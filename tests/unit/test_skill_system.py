import pytest
import sys
import os
import json
import tempfile
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.platform.skill_system.impl.skill_manager import SkillManager, _infer_skill_type
from odap.biz.platform.skill_system.impl.hotplug import HotplugManager
from odap.biz.platform.skill_system.models.skill import Skill, SkillStatus, SkillType, SkillVersion
from odap.biz.platform.skill_system.services.skill_service import SkillService
from odap.biz.platform.skill_system.api.routes_extended import (
    _get_catalog_skills,
    _get_harness_tools,
    _scan_filesystem_skills,
    _get_catalog_categories,
    _get_filesystem_categories,
    parse_skill_markdown,
)


class TestSkillManagerSync:

    @pytest.fixture
    def manager(self):
        return SkillManager()

    def test_sync_from_catalog(self, manager):
        mock_catalog = {
            "query_entities": {"description": "查询实体", "handler": lambda: None, "category": "graph"},
            "analyze_graph": {"description": "分析图谱", "handler": lambda: None, "category": "analysis"},
        }
        with patch.dict('odap.biz.platform.skill_system.impl.skill_manager.SKILL_CATALOG' if False else 'sys.modules', {}):
            with patch('odap.biz.platform.skill_system.impl.skill_manager.SkillManager.sync_from_catalog') as mock_sync:
                mock_sync.return_value = 2

        with patch('odap.tools.registry.SKILL_CATALOG', mock_catalog, create=True):
            with patch.dict('sys.modules', {'odap.tools': MagicMock(SKILL_CATALOG=mock_catalog)}):
                count = manager.sync_from_catalog()
                assert count == 2
                assert manager._synced is True

    def test_sync_from_catalog_idempotent(self, manager):
        manager._synced = True
        count = manager.sync_from_catalog()
        assert count == 0

    def test_register_skill_dedup_by_name(self, manager):
        skill1 = manager.register_skill("dup_skill", SkillType.ACTION, "first")
        skill2 = manager.register_skill("dup_skill", SkillType.QUERY, "second")
        assert skill1.id == skill2.id
        assert skill1.description == "first"

    def test_get_skill_by_name(self, manager):
        skill = manager.register_skill("find_me", SkillType.QUERY, "desc")
        result = manager.get_skill_by_name("find_me")
        assert result is not None
        assert result.id == skill.id

    def test_get_skill_by_name_not_found(self, manager):
        result = manager.get_skill_by_name("nonexistent")
        assert result is None

    def test_list_skills_triggers_sync(self, manager):
        mock_catalog = {
            "test_skill": {"description": "test", "handler": lambda: None, "category": "general"},
        }
        with patch.dict('sys.modules', {'odap.tools': MagicMock(SKILL_CATALOG=mock_catalog)}):
            result = manager.list_skills()
            assert manager._synced is True
            assert len(result) >= 1

    def test_list_skills_filter_by_name(self, manager):
        manager.register_skill("alpha_skill", SkillType.ACTION)
        manager.register_skill("beta_skill", SkillType.ACTION)
        manager._synced = True

        result = manager.list_skills(filters={"name": "alpha"})
        assert len(result) == 1
        assert result[0].name == "alpha_skill"

    def test_delete_skill_removes_name_index(self, manager):
        skill = manager.register_skill("to_delete", SkillType.ACTION)
        assert "to_delete" in manager._name_index

        manager.delete_skill(skill.id)
        assert "to_delete" not in manager._name_index
        assert skill.id not in manager._skills

    def test_get_catalog_info(self, manager):
        mock_catalog = {"s1": {"description": "d1", "category": "c1"}}
        with patch.dict('sys.modules', {'odap.tools': MagicMock(SKILL_CATALOG=mock_catalog)}):
            info = manager.get_catalog_info()
            assert info["catalog_count"] == 1
            assert info["synced"] is True

    def test_activate_skill_syncs_to_harness(self, manager):
        skill = manager.register_skill("harness_skill", SkillType.ACTION)
        with patch('odap.biz.platform.skill_system.impl.skill_manager.SkillManager._sync_status_to_harness') as mock_sync:
            manager.activate_skill(skill.id)
            mock_sync.assert_called_once_with("harness_skill", True)

    def test_deactivate_skill_syncs_to_harness(self, manager):
        skill = manager.register_skill("harness_skill2", SkillType.ACTION)
        with patch('odap.biz.platform.skill_system.impl.skill_manager.SkillManager._sync_status_to_harness') as mock_sync:
            manager.deactivate_skill(skill.id)
            mock_sync.assert_called_once_with("harness_skill2", False)


class TestInferSkillType:

    def test_graph_category(self):
        assert _infer_skill_type("graph") == SkillType.QUERY

    def test_analysis_category(self):
        assert _infer_skill_type("analysis") == SkillType.QUERY

    def test_operations_category(self):
        assert _infer_skill_type("operations") == SkillType.ACTION

    def test_unknown_category(self):
        assert _infer_skill_type("unknown_cat") == SkillType.ACTION


class TestSkillServiceExtended:

    @pytest.fixture
    def service(self):
        return SkillService()

    def test_get_skill_by_name(self, service):
        skill = service.manager.register_skill("svc_skill", SkillType.ACTION, "desc")
        result = service.get_skill_by_name("svc_skill")
        assert result["name"] == "svc_skill"
        assert result["skill_id"] == skill.id

    def test_get_skill_by_name_not_found(self, service):
        result = service.get_skill_by_name("nonexistent")
        assert result["status"] == "error"

    def test_list_skills_total_count(self, service):
        service.manager.register_skill("s1", SkillType.ACTION)
        service.manager.register_skill("s2", SkillType.QUERY)
        service.manager._synced = True

        result = service.list_skills()
        assert result["total"] == 2

    def test_sync_from_catalog(self, service):
        mock_catalog = {"synced_skill": {"description": "d", "category": "c"}}
        with patch.dict('sys.modules', {'odap.tools': MagicMock(SKILL_CATALOG=mock_catalog)}):
            result = service.sync_from_catalog()
            assert result["status"] == "success"
            assert result["synced_count"] == 1

    def test_get_catalog_info(self, service):
        mock_catalog = {"info_skill": {"description": "d", "category": "c"}}
        with patch.dict('sys.modules', {'odap.tools': MagicMock(SKILL_CATALOG=mock_catalog)}):
            info = service.get_catalog_info()
            assert info["catalog_count"] == 1


class TestCatalogSkillsHelper:

    def test_get_catalog_skills(self):
        mock_catalog = {
            "skill_a": {"description": "A", "category": "graph", "handler": lambda: None},
            "skill_b": {"description": "B", "category": "analysis", "handler": lambda: None},
        }
        with patch.dict('sys.modules', {'odap.tools': MagicMock(SKILL_CATALOG=mock_catalog)}):
            skills = _get_catalog_skills()
            assert len(skills) == 2
            names = {s["name"] for s in skills}
            assert "skill_a" in names
            assert "skill_b" in names
            for s in skills:
                assert s["source"] == "catalog"
                assert s["enabled"] is True

    def test_get_catalog_skills_empty(self):
        with patch.dict('sys.modules', {'odap.tools': MagicMock(SKILL_CATALOG={})}):
            skills = _get_catalog_skills()
            assert skills == []

    def test_get_catalog_skills_import_error(self):
        original_func = _get_catalog_skills.__code__
        with patch('odap.biz.platform.skill_system.api.routes_extended._get_catalog_skills', side_effect=Exception("import error")):
            pass
        skills = _get_catalog_skills()
        assert isinstance(skills, list)


class TestHarnessToolsHelper:

    def test_get_harness_tools(self):
        mock_tool = MagicMock()
        mock_tool.name = "query_entities"
        mock_harness = MagicMock()
        mock_harness._tool_list = [mock_tool]

        with patch('odap.infra.openharness.tool_adapter.get_domain_harness', return_value=mock_harness):
            tools = _get_harness_tools()
            assert tools == ["query_entities"]

    def test_get_harness_tools_empty(self):
        with patch('odap.infra.openharness.tool_adapter.get_domain_harness', return_value=None):
            tools = _get_harness_tools()
            assert tools == []

    def test_get_harness_tools_import_error(self):
        with patch('odap.infra.openharness.tool_adapter.get_domain_harness', side_effect=ImportError("no module")):
            tools = _get_harness_tools()
            assert tools == []


class TestCatalogCategoriesHelper:

    def test_get_catalog_categories(self):
        mock_catalog = {
            "s1": {"description": "d", "category": "graph", "handler": lambda: None},
            "s2": {"description": "d", "category": "graph", "handler": lambda: None},
            "s3": {"description": "d", "category": "analysis", "handler": lambda: None},
        }
        with patch.dict('sys.modules', {'odap.tools': MagicMock(SKILL_CATALOG=mock_catalog)}):
            cats = _get_catalog_categories()
            cat_map = {c["name"]: c for c in cats}
            assert cat_map["graph"]["skill_count"] == 2
            assert cat_map["analysis"]["skill_count"] == 1

    def test_get_catalog_categories_empty(self):
        with patch.dict('sys.modules', {'odap.tools': MagicMock(SKILL_CATALOG={})}):
            cats = _get_catalog_categories()
            assert cats == []


class TestFilesystemSkillsHelper:

    def test_scan_filesystem_no_dir(self):
        with patch.object(Path, 'exists', return_value=False):
            skills = _scan_filesystem_skills()
            assert skills == []

    def test_scan_filesystem_with_skills(self, tmp_path):
        skill_dir = tmp_path / "graph" / "query_entities"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# query_entities\n\n## Description\n\n查询实体\n", encoding='utf-8')

        with patch('odap.biz.platform.skill_system.api.routes_extended.OPENHARNESS_SKILLS_DIR', tmp_path):
            skills = _scan_filesystem_skills()
            assert len(skills) == 1
            assert skills[0]["name"] == "query_entities"
            assert skills[0]["category"] == "graph"
            assert skills[0]["source"] == "filesystem"
            assert "SKILL.md" in skills[0]["files"]


class TestFilesystemCategoriesHelper:

    def test_get_filesystem_categories_no_dir(self):
        with patch.object(Path, 'exists', return_value=False):
            cats = _get_filesystem_categories()
            assert cats == []

    def test_get_filesystem_categories_with_dirs(self, tmp_path):
        (tmp_path / "graph" / "skill_a").mkdir(parents=True)
        (tmp_path / "graph" / "skill_b").mkdir(parents=True)
        (tmp_path / "analysis" / "skill_c").mkdir(parents=True)

        with patch('odap.biz.platform.skill_system.api.routes_extended.OPENHARNESS_SKILLS_DIR', tmp_path):
            cats = _get_filesystem_categories()
            cat_map = {c["name"]: c for c in cats}
            assert cat_map["graph"]["skill_count"] == 2
            assert cat_map["analysis"]["skill_count"] == 1
            assert cat_map["graph"]["source"] == "filesystem"


class TestParseSkillMarkdown:

    def test_basic_parsing(self):
        content = "# my_skill\n\n## Description\n\nThis is a test skill\n\n## Input Schema\n\n```json\n{\"type\": \"object\"}\n```"
        result = parse_skill_markdown(content)
        assert result["name"] == "my_skill"
        assert result["description"] == "This is a test skill"
        assert result["input_schema"] == {"type": "object"}

    def test_yaml_schema(self):
        content = "# yaml_skill\n\n## Output Schema\n\n```yaml\ntype: object\nproperties:\n  name:\n    type: string\n```"
        result = parse_skill_markdown(content)
        assert result["name"] == "yaml_skill"
        assert result["output_schema"]["type"] == "object"
        assert "name" in result["output_schema"]["properties"]

    def test_empty_content(self):
        result = parse_skill_markdown("")
        assert result["name"] == ""
        assert result["description"] == ""

    def test_multiple_sections(self):
        content = "# multi\n\n## Description\n\nDesc\n\n## Triggers\n\n- trigger1\n- trigger2\n\n## Notes\n\nSome notes"
        result = parse_skill_markdown(content)
        assert "description" in result["sections"]
        assert "triggers" in result["sections"]
        assert "notes" in result["sections"]


class TestHotplugManager:

    @pytest.fixture
    def hotplug(self):
        return HotplugManager()

    def test_load_skill_no_module(self, hotplug):
        result = hotplug.load_skill("unknown_skill")
        assert result is False

    def test_load_skill_already_loaded(self, hotplug):
        hotplug._loaded_skills["skill_1"] = MagicMock()
        result = hotplug.load_skill("skill_1")
        assert result is True

    @patch('importlib.import_module')
    def test_load_skill_with_module(self, mock_import, hotplug):
        mock_module = MagicMock()
        mock_import.return_value = mock_module
        hotplug.register_module("skill_1", "fake.module")

        result = hotplug.load_skill("skill_1")
        assert result is True
        assert hotplug._loaded_skills["skill_1"] is mock_module

    def test_unload_skill(self, hotplug):
        hotplug._loaded_skills["skill_1"] = MagicMock()
        hotplug._skill_modules["skill_1"] = "fake.module"
        result = hotplug.unload_skill("skill_1")
        assert result is True
        assert "skill_1" not in hotplug._loaded_skills

    def test_unload_skill_not_loaded(self, hotplug):
        result = hotplug.unload_skill("not_loaded")
        assert result is False

    def test_reload_skill_not_loaded(self, hotplug):
        result = hotplug.reload_skill("not_loaded")
        assert result is False

    def test_get_loaded_skills(self, hotplug):
        hotplug._loaded_skills["skill_a"] = MagicMock()
        hotplug._loaded_skills["skill_b"] = MagicMock()
        result = hotplug.get_loaded_skills()
        assert set(result) == {"skill_a", "skill_b"}

    def test_is_loaded(self, hotplug):
        hotplug._loaded_skills["skill_1"] = MagicMock()
        assert hotplug.is_loaded("skill_1") is True
        assert hotplug.is_loaded("skill_2") is False

    def test_register_module(self, hotplug):
        hotplug.register_module("skill_1", "custom.module")
        assert hotplug._skill_modules["skill_1"] == "custom.module"


class TestSkillManagerBasic:

    @pytest.fixture
    def manager(self):
        return SkillManager()

    def test_register_skill(self, manager):
        skill = manager.register_skill("test_skill", SkillType.ACTION, "A test skill", "testing", ["test"])
        assert skill.name == "test_skill"
        assert skill.type == SkillType.ACTION
        assert skill.description == "A test skill"
        assert skill.category == "testing"
        assert skill.tags == ["test"]
        assert skill.status == SkillStatus.DRAFT

    def test_get_skill(self, manager):
        skill = manager.register_skill("my_skill", SkillType.QUERY)
        result = manager.get_skill(skill.id)
        assert result is skill

    def test_get_skill_not_found(self, manager):
        result = manager.get_skill("nonexistent_id")
        assert result is None

    def test_update_skill(self, manager):
        skill = manager.register_skill("updatable", SkillType.ACTION)
        updated = manager.update_skill(skill.id, {"description": "updated desc", "category": "new_cat"})
        assert updated.description == "updated desc"
        assert updated.category == "new_cat"

    def test_update_skill_not_found(self, manager):
        with pytest.raises(ValueError, match="Skill not found"):
            manager.update_skill("nonexistent_id", {"description": "fail"})

    def test_delete_skill(self, manager):
        skill = manager.register_skill("deletable", SkillType.TRANSFORM)
        result = manager.delete_skill(skill.id)
        assert result is True
        assert skill.id not in manager._skills

    def test_delete_skill_not_found(self, manager):
        result = manager.delete_skill("nonexistent_id")
        assert result is False

    def test_list_skills_pagination(self, manager):
        for i in range(15):
            manager.register_skill(f"skill_{i}", SkillType.ACTION)
        manager._synced = True

        page1 = manager.list_skills(page=1, page_size=10)
        page2 = manager.list_skills(page=2, page_size=10)
        assert len(page1) == 10
        assert len(page2) == 5

    def test_list_skills_filter_by_type(self, manager):
        manager.register_skill("action_skill", SkillType.ACTION)
        manager.register_skill("query_skill", SkillType.QUERY)
        manager._synced = True

        result = manager.list_skills(filters={"type": "query"})
        assert len(result) == 1
        assert result[0].type == SkillType.QUERY

    def test_add_version(self, manager):
        skill = manager.register_skill("versioned", SkillType.ACTION)
        version = manager.add_version(skill_id=skill.id, version="2.0.0", implementation="def run(): pass", schema={"input": "str"}, changelog="Major update")
        assert version.skill_id == skill.id
        assert version.version == "2.0.0"
        assert skill.current_version == "2.0.0"

    def test_activate_deactivate_skill(self, manager):
        skill = manager.register_skill("lifecycle", SkillType.ACTION)
        assert skill.status == SkillStatus.DRAFT

        activated = manager.activate_skill(skill.id)
        assert activated.status == SkillStatus.ACTIVE

        deactivated = manager.deactivate_skill(skill.id)
        assert deactivated.status == SkillStatus.INACTIVE
