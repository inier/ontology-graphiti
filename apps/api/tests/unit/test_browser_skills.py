"""浏览器自动化 Skill 单元测试

测试 BrowserAutomateSkill 的 MCP 调用、超时控制、OPA 权限、
以及 browser_tool_server 的 API 端点。
"""

import pytest
from unittest.mock import patch, MagicMock
import json


class TestBrowserAutomateSkillMetadata:
    """BrowserAutomateSkill 元数据测试"""

    def test_skill_metadata(self):
        from odap.tools.web.web_skills import BrowserAutomateSkill
        skill = BrowserAutomateSkill()
        assert skill.metadata.name == "browser_automate"
        assert skill.metadata.category == "web"
        assert skill.metadata.danger_level == "high"
        assert skill.metadata.requires_opa_check is True
        assert skill.metadata.opa_action == "data_collection:browser"

    def test_skill_registered_in_catalog(self):
        from odap.tools import SKILL_CATALOG
        assert "browser_automate" in SKILL_CATALOG

    def test_skill_registered_in_registry(self):
        from odap.tools.base import get_registry
        skill = get_registry().get("browser_automate")
        assert skill is not None

    def test_input_schema(self):
        from odap.tools.web.web_skills import BrowserAutomateInput
        inp = BrowserAutomateInput(task="Go to example.com and extract title")
        assert inp.task == "Go to example.com and extract title"
        assert inp.max_steps == 25
        assert inp.timeout_seconds == 300
        assert inp.url is None

    def test_input_schema_with_url(self):
        from odap.tools.web.web_skills import BrowserAutomateInput
        inp = BrowserAutomateInput(task="Login", url="https://example.com/login", max_steps=10)
        assert inp.url == "https://example.com/login"
        assert inp.max_steps == 10


class TestBrowserAutomateSkillExecution:
    """BrowserAutomateSkill 执行测试（MCP 调用 mock）"""

    def test_successful_execution(self):
        """MCP Server 返回成功"""
        from odap.tools.web.web_skills import _browser_automate_skill

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {"session_id": "test-123", "result": "Title: Example", "steps_taken": 5},
            "execution_time_ms": 3200,
        }

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = _browser_automate_skill.run({
                "task": "Go to example.com and extract title",
                "url": "https://example.com",
            })

        assert result.success is True
        assert result.data["session_id"] == "test-123"
        assert result.execution_time_ms == 3200

    def test_mcp_server_error(self):
        """MCP Server 返回错误"""
        from odap.tools.web.web_skills import _browser_automate_skill

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": False,
            "error": "Browser task failed: navigation timeout",
        }

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = _browser_automate_skill.run({"task": "Login to site"})

        assert result.success is False
        assert "navigation timeout" in result.error

    def test_timeout_control(self):
        """超时控制：httpx.TimeoutException 被正确处理"""
        import httpx
        from odap.tools.web.web_skills import _browser_automate_skill

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.TimeoutException("Request timed out")
            mock_client_cls.return_value = mock_client

            result = _browser_automate_skill.run({
                "task": "Long running task",
                "timeout_seconds": 60,
            })

        assert result.success is False
        assert "timed out" in result.error

    def test_connection_error_server_unavailable(self):
        """MCP Server 不可用：httpx.ConnectError"""
        import httpx
        from odap.tools.web.web_skills import _browser_automate_skill

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client_cls.return_value = mock_client

            result = _browser_automate_skill.run({"task": "Test task"})

        assert result.success is False
        assert "unavailable" in result.error.lower()

    def test_timeout_hard_limit(self):
        """超时硬限制：timeout_seconds 被截断为 300"""
        from odap.tools.web.web_skills import _browser_automate_skill

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": {}}

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            # 传入超过 300 的超时
            result = _browser_automate_skill.run({
                "task": "Test",
                "timeout_seconds": 600,
            })

            # 验证 payload 中 timeout_seconds 被截断为 300
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["timeout_seconds"] == 300


class TestBrowserAutomateOPA:
    """浏览器自动化 OPA 权限测试"""

    def test_browser_action_only_for_admin(self):
        """browser 操作仅 admin 允许"""
        from tests.unit.test_data_collection_opa import check_data_collection_policy
        assert check_data_collection_policy("admin", "browser") is True
        assert check_data_collection_policy("analyst", "browser") is False
        assert check_data_collection_policy("guest", "browser") is False

    def test_skill_danger_level_high(self):
        """danger_level 为 high，需要高危操作确认"""
        from odap.tools.web.web_skills import BrowserAutomateSkill
        skill = BrowserAutomateSkill()
        assert skill.metadata.danger_level == "high"


class TestBrowserToolServer:
    """browser_tool_server API 端点测试"""

    def test_health_endpoint(self):
        """健康检查端点"""
        from odap.biz.integration.mcp_adapter.browser_tool_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "browser_use_available" in data

    def test_capabilities_endpoint(self):
        """能力发现端点"""
        from odap.biz.integration.mcp_adapter.browser_tool_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        tool_names = [t["name"] for t in data["tools"]]
        assert "browse_task" in tool_names
        assert "browser_screenshot" in tool_names
        assert "browser_extract" in tool_names

    def test_tools_endpoint(self):
        """工具列表端点"""
        from odap.biz.integration.mcp_adapter.browser_tool_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/tools")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_browse_task_schema(self):
        """browse_task 输入 schema 验证"""
        from odap.biz.integration.mcp_adapter.browser_tool_server import BrowseTaskRequest
        req = BrowseTaskRequest(task="Test task")
        assert req.max_steps == 25
        assert req.timeout_seconds == 300

    def test_browse_task_timeout_limit(self):
        """browse_task 超时限制验证"""
        from odap.biz.integration.mcp_adapter.browser_tool_server import BrowseTaskRequest
        with pytest.raises(Exception):
            BrowseTaskRequest(task="Test", timeout_seconds=600)  # 超过 300 上限

    def test_screenshot_schema(self):
        """screenshot 输入 schema 验证"""
        from odap.biz.integration.mcp_adapter.browser_tool_server import BrowserScreenshotRequest
        req = BrowserScreenshotRequest(url="https://example.com")
        assert req.full_page is False
        assert req.width == 1280

    def test_extract_schema(self):
        """extract 输入 schema 验证"""
        from odap.biz.integration.mcp_adapter.browser_tool_server import BrowserExtractRequest
        req = BrowserExtractRequest(url="https://example.com", extraction_prompt="Extract titles")
        assert req.max_steps == 15


class TestMCPServiceBuiltinRegistration:
    """MCPService 内置服务器注册测试"""

    def test_register_builtin_servers(self):
        """注册内置 MCP 服务器"""
        from odap.biz.integration.mcp_adapter.services.mcp_service import MCPService
        service = MCPService()
        result = service.register_builtin_servers()
        assert len(result) >= 1
        assert result[0]["name"] == "browser-use"

    def test_browser_use_server_registered(self):
        """browser-use 服务器已注册"""
        from odap.biz.integration.mcp_adapter.services.mcp_service import MCPService
        service = MCPService()
        service.register_builtin_servers()
        servers = service.list_servers()
        browser_servers = [s for s in servers if s.get("name") == "browser-use"]
        assert len(browser_servers) >= 1
