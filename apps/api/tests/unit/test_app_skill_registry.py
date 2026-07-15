"""Unit tests for AppSkillRegistry."""
from odap.biz.core.ontology.application.skill_registry import (
    AppSkillRegistry, get_app_skill_registry,
)
from odap.biz.core.ontology.application.runtime.skill_adapter import RuntimeSkillAdapter


class FakeEngine:
    def list_functions(self, function_type=None, target_object_type=None):
        return {"status": "success", "functions": []}

    def execute_function(self, fn_id, ctx):
        return {"status": "success"}


class TestAppSkillRegistry:
    def test_register_and_get(self):
        reg = AppSkillRegistry()
        adapter = RuntimeSkillAdapter("ws-1", "ont-1", name="custom_runtime")
        reg.register(adapter)
        assert reg.get("custom_runtime") is adapter

    def test_bind_engine_success(self):
        reg = AppSkillRegistry()
        adapter = RuntimeSkillAdapter("ws-1", "ont-1", name="custom_runtime")
        reg.register(adapter)
        ok = reg.bind_engine("custom_runtime", FakeEngine())
        assert ok
        assert adapter._bound

    def test_bind_engine_not_found(self):
        reg = AppSkillRegistry()
        ok = reg.bind_engine("missing", FakeEngine())
        assert not ok

    def test_bind_engine_type_error(self):
        reg = AppSkillRegistry()
        adapter = RuntimeSkillAdapter("ws-1", "ont-1", name="custom_runtime")
        reg.register(adapter)
        ok = reg.bind_engine("custom_runtime", "not-an-engine")
        assert not ok

    def test_list_filtered(self):
        reg = AppSkillRegistry()
        a1 = RuntimeSkillAdapter("ws-1", "ont-1", name="r1")
        a2 = RuntimeSkillAdapter("ws-1", "ont-2", name="r2")
        a3 = RuntimeSkillAdapter("ws-2", "ont-1", name="r3")
        reg.register(a1)
        reg.register(a2)
        reg.register(a3)
        assert len(reg.list(workspace_id="ws-1")) == 2
        assert len(reg.list(workspace_id="ws-1", ontology_id="ont-1")) == 1
        assert len(reg.list()) == 3

    def test_names(self):
        reg = AppSkillRegistry()
        reg.register(RuntimeSkillAdapter("ws", "ont", name="x1"))
        reg.register(RuntimeSkillAdapter("ws", "ont", name="x2"))
        assert set(reg.names()) == {"x1", "x2"}

    def test_singleton(self):
        a = get_app_skill_registry()
        b = get_app_skill_registry()
        assert a is b

    def test_register_overwrite(self):
        reg = AppSkillRegistry()
        a1 = RuntimeSkillAdapter("ws", "ont", name="dup")
        a2 = RuntimeSkillAdapter("ws", "ont", name="dup")
        reg.register(a1)
        reg.register(a2)
        assert reg.get("dup") is a2
