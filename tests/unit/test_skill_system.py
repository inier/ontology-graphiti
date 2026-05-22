import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.skill_system.impl.skill_manager import SkillManager
from odap.biz.skill_system.impl.hotplug import HotplugManager
from odap.biz.skill_system.models.skill import Skill, SkillStatus, SkillType, SkillVersion


class TestSkillManager:

    @pytest.fixture
    def manager(self):
        return SkillManager()

    def test_register_skill(self, manager):
        skill = manager.register_skill(
            name="test_skill",
            skill_type=SkillType.ACTION,
            description="A test skill",
            category="testing",
            tags=["test"]
        )

        assert skill.name == "test_skill"
        assert skill.type == SkillType.ACTION
        assert skill.description == "A test skill"
        assert skill.category == "testing"
        assert skill.tags == ["test"]
        assert skill.status == SkillStatus.DRAFT
        assert skill.id in manager._skills
        assert manager._skills[skill.id] is skill

    def test_get_skill(self, manager):
        skill = manager.register_skill("my_skill", SkillType.QUERY)
        result = manager.get_skill(skill.id)

        assert result is skill
        assert result.name == "my_skill"

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

    def test_list_skills(self, manager):
        for i in range(15):
            manager.register_skill(f"skill_{i}", SkillType.ACTION)

        page1 = manager.list_skills(page=1, page_size=10)
        page2 = manager.list_skills(page=2, page_size=10)

        assert len(page1) == 10
        assert len(page2) == 5

    def test_list_skills_filter_by_type(self, manager):
        manager.register_skill("action_skill", SkillType.ACTION)
        manager.register_skill("query_skill", SkillType.QUERY)
        manager.register_skill("transform_skill", SkillType.TRANSFORM)

        result = manager.list_skills(filters={"type": "query"})

        assert len(result) == 1
        assert result[0].type == SkillType.QUERY

    def test_list_skills_filter_by_status(self, manager):
        skill = manager.register_skill("draft_skill", SkillType.ACTION)
        active_skill = manager.register_skill("active_skill", SkillType.ACTION)
        manager.activate_skill(active_skill.id)

        result = manager.list_skills(filters={"status": "active"})

        assert len(result) == 1
        assert result[0].status == SkillStatus.ACTIVE

    def test_add_version(self, manager):
        skill = manager.register_skill("versioned", SkillType.ACTION)
        version = manager.add_version(
            skill_id=skill.id,
            version="2.0.0",
            implementation="def run(): pass",
            schema={"input": "str"},
            changelog="Major update"
        )

        assert version.skill_id == skill.id
        assert version.version == "2.0.0"
        assert version.implementation == "def run(): pass"
        assert version.changelog == "Major update"
        assert len(skill.versions) == 1
        assert skill.current_version == "2.0.0"

    def test_add_version_skill_not_found(self, manager):
        with pytest.raises(ValueError, match="Skill not found"):
            manager.add_version(
                skill_id="nonexistent_id",
                version="1.0.0",
                implementation="def run(): pass"
            )

    def test_activate_deactivate_skill(self, manager):
        skill = manager.register_skill("lifecycle", SkillType.ACTION)
        assert skill.status == SkillStatus.DRAFT

        activated = manager.activate_skill(skill.id)
        assert activated.status == SkillStatus.ACTIVE

        deactivated = manager.deactivate_skill(skill.id)
        assert deactivated.status == SkillStatus.INACTIVE


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
        mock_import.assert_called_once_with("fake.module")

    @patch('importlib.import_module')
    def test_load_skill_import_fails(self, mock_import, hotplug):
        mock_import.side_effect = ImportError("No module")
        hotplug.register_module("skill_1", "missing.module")

        result = hotplug.load_skill("skill_1")

        assert result is False

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

    def test_get_skill_status(self, hotplug):
        hotplug._loaded_skills["skill_1"] = MagicMock()
        hotplug._skill_modules["skill_1"] = "my.module"

        status = hotplug.get_skill_status("skill_1")

        assert status["skill_id"] == "skill_1"
        assert status["is_loaded"] is True
        assert status["module_name"] == "my.module"

    def test_get_skill_status_not_loaded(self, hotplug):
        hotplug._skill_modules["skill_x"] = "other.module"

        status = hotplug.get_skill_status("skill_x")

        assert status["skill_id"] == "skill_x"
        assert status["is_loaded"] is False
        assert status["module_name"] == "other.module"

    def test_register_module(self, hotplug):
        hotplug.register_module("skill_1", "custom.module")

        assert hotplug._skill_modules["skill_1"] == "custom.module"
