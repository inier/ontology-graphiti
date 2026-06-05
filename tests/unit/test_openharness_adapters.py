import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestSwarmAdapter:
    def setup_method(self):
        from odap.infra.openharness.swarm_adapter import SwarmAdapter
        self.adapter = SwarmAdapter()

    def test_available_property_when_no_openharness(self):
        assert isinstance(self.adapter.available, bool)

    @pytest.mark.asyncio
    async def test_create_swarm_unavailable(self):
        from odap.infra.openharness.swarm_adapter import SwarmAdapter
        adapter = SwarmAdapter()
        adapter._available = False
        result = await adapter.create_swarm([])
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_run_swarm_unavailable(self):
        from odap.infra.openharness.swarm_adapter import SwarmAdapter
        adapter = SwarmAdapter()
        adapter._available = False
        result = await adapter.run_swarm(0, "test task")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_list_agents_unavailable(self):
        from odap.infra.openharness.swarm_adapter import SwarmAdapter
        adapter = SwarmAdapter()
        adapter._available = False
        result = await adapter.list_agents()
        assert result["status"] == "error"

    def test_get_swarm_adapter_singleton(self):
        from odap.infra.openharness.swarm_adapter import get_swarm_adapter
        adapter1 = get_swarm_adapter()
        adapter2 = get_swarm_adapter()
        assert adapter1 is adapter2


class TestSkillAdapter:
    def setup_method(self):
        from odap.infra.openharness.skill_adapter import SkillAdapter
        self.adapter = SkillAdapter()

    def test_register_skill(self):
        handler = lambda: None
        result = self.adapter.register_skill("test_skill", "Test skill", handler, category="test")
        assert result["status"] == "success"
        assert result["skill"] == "test_skill"

    def test_discover_skills(self):
        handler = lambda: None
        self.adapter.register_skill("skill_a", "Skill A", handler, category="cat1")
        self.adapter.register_skill("skill_b", "Skill B", handler, category="cat2")
        result = self.adapter.discover_skills()
        assert result["status"] == "success"
        assert result["count"] == 2

    def test_discover_skills_by_category(self):
        handler = lambda: None
        self.adapter.register_skill("skill_a", "Skill A", handler, category="cat1")
        self.adapter.register_skill("skill_b", "Skill B", handler, category="cat2")
        result = self.adapter.discover_skills(category="cat1")
        assert result["status"] == "success"
        assert result["count"] == 1

    def test_get_skill(self):
        handler = lambda: None
        self.adapter.register_skill("test_skill", "Test skill", handler)
        result = self.adapter.get_skill("test_skill")
        assert result["status"] == "success"
        assert result["skill"]["name"] == "test_skill"

    def test_get_skill_not_found(self):
        result = self.adapter.get_skill("nonexistent")
        assert result["status"] == "error"

    def test_unregister_skill(self):
        handler = lambda: None
        self.adapter.register_skill("test_skill", "Test skill", handler)
        result = self.adapter.unregister_skill("test_skill")
        assert result["status"] == "success"
        assert self.adapter.get_skill("test_skill")["status"] == "error"

    def test_unregister_skill_not_found(self):
        result = self.adapter.unregister_skill("nonexistent")
        assert result["status"] == "error"

    def test_list_categories(self):
        handler = lambda: None
        self.adapter.register_skill("skill_a", "Skill A", handler, category="cat1")
        self.adapter.register_skill("skill_b", "Skill B", handler, category="cat2")
        result = self.adapter.list_categories()
        assert result["status"] == "success"
        assert "cat1" in result["categories"]
        assert "cat2" in result["categories"]

    def test_available_property(self):
        assert isinstance(self.adapter.available, bool)

    def test_get_skill_adapter_singleton(self):
        from odap.infra.openharness.skill_adapter import get_skill_adapter
        adapter1 = get_skill_adapter()
        adapter2 = get_skill_adapter()
        assert adapter1 is adapter2


class TestHookAdapter:
    def setup_method(self):
        from odap.infra.openharness.hook_adapter import HookAdapter
        self.adapter = HookAdapter()

    def test_register_hook(self):
        handler = lambda ctx: None
        result = self.adapter.register_hook("pre_execute", handler)
        assert result["status"] == "success"
        assert result["event"] == "pre_execute"

    @pytest.mark.asyncio
    async def test_trigger_hook(self):
        call_log = []
        def handler(ctx):
            call_log.append(ctx)
        self.adapter.register_hook("pre_execute", handler)
        result = await self.adapter.trigger_hook("pre_execute", {"action": "test"})
        assert result["status"] == "success"
        assert result["count"] == 1
        assert len(call_log) == 1

    @pytest.mark.asyncio
    async def test_trigger_hook_async_handler(self):
        call_log = []
        async def handler(ctx):
            call_log.append(ctx)
        self.adapter.register_hook("post_execute", handler)
        result = await self.adapter.trigger_hook("post_execute", {"result": "ok"})
        assert result["status"] == "success"
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_trigger_hook_error_handling(self):
        def bad_handler(ctx):
            raise ValueError("test error")
        self.adapter.register_hook("on_error", bad_handler)
        result = await self.adapter.trigger_hook("on_error", {})
        assert result["status"] == "success"
        assert len(result["results"]) == 1
        assert "error" in result["results"][0]

    def test_unregister_hook(self):
        handler = lambda ctx: None
        self.adapter.register_hook("pre_execute", handler)
        result = self.adapter.unregister_hook("pre_execute", handler)
        assert result["status"] == "success"
        assert result["removed"] is True

    def test_unregister_hook_not_found(self):
        handler = lambda ctx: None
        result = self.adapter.unregister_hook("pre_execute", handler)
        assert result["status"] == "error"

    def test_list_hooks(self):
        handler = lambda ctx: None
        self.adapter.register_hook("pre_execute", handler)
        result = self.adapter.list_hooks("pre_execute")
        assert result["status"] == "success"
        assert len(result["handlers"]) == 1

    def test_list_all_hooks(self):
        result = self.adapter.list_hooks()
        assert result["status"] == "success"
        assert "pre_execute" in result["hooks"]

    def test_available_property(self):
        assert isinstance(self.adapter.available, bool)

    def test_get_hook_adapter_singleton(self):
        from odap.infra.openharness.hook_adapter import get_hook_adapter
        adapter1 = get_hook_adapter()
        adapter2 = get_hook_adapter()
        assert adapter1 is adapter2


class TestMemoryAdapter:
    def setup_method(self):
        from odap.infra.openharness.memory_adapter import GraphitiMemoryAdapter
        self.adapter = GraphitiMemoryAdapter()

    @pytest.mark.asyncio
    async def test_read_without_graph(self):
        result = await self.adapter.read("test query")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_count_without_graph(self):
        result = await self.adapter.count()
        assert isinstance(result, int)

    @pytest.mark.asyncio
    async def test_delete_not_supported(self):
        result = await self.adapter.delete("test_episode")
        assert result is False


class TestV2AdapterShutdown:
    @pytest.mark.asyncio
    async def test_shutdown(self):
        from odap.infra.openharness.v2_adapter import OpenHarnessIntegration
        OpenHarnessIntegration._instance = None
        integration = OpenHarnessIntegration()
        result = await integration.shutdown()
        assert result is True
        assert integration.agent_loop is None
        assert integration.llm_client is None
        OpenHarnessIntegration._instance = None

    @pytest.mark.asyncio
    async def test_initialize_and_shutdown(self):
        from odap.infra.openharness.v2_adapter import OpenHarnessIntegration
        OpenHarnessIntegration._instance = None
        integration = OpenHarnessIntegration()
        init_result = await integration.initialize()
        shutdown_result = await integration.shutdown()
        assert isinstance(init_result, bool)
        assert shutdown_result is True
        OpenHarnessIntegration._instance = None
