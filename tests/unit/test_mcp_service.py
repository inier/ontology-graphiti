"""test_mcp_service.py - MCPService 单元测试

测试 MCP 服务的 retry 逻辑、circuit breaker 和回退机制。
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# 延迟导入 fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mcp_service():
    """创建 MCPService 实例"""
    try:
        from odap.biz.integration.mcp_adapter.services.mcp_service import MCPService
    except ImportError:
        pytest.skip("MCPService not importable")
    return MCPService()


# ---------------------------------------------------------------------------
# TestSuccessfulV2Call
# ---------------------------------------------------------------------------

class TestSuccessfulV2Call:
    @pytest.mark.asyncio
    async def test_v2_call_success(self, mcp_service):
        """v2 调用成功时返回结果"""
        mock_v2 = AsyncMock()
        mock_v2.execute_tool = AsyncMock(return_value={"status": "ok", "data": "result"})
        mcp_service._v2_manager = mock_v2

        result = await mcp_service.call_tool("server-1", "tool-1", {"arg": "val"})
        assert result["status"] == "ok"
        assert result["data"] == "result"

    @pytest.mark.asyncio
    async def test_v2_success_resets_failure_count(self, mcp_service):
        """v2 成功后重置失败计数"""
        mcp_service._v2_failure_count = 3
        mock_v2 = AsyncMock()
        mock_v2.execute_tool = AsyncMock(return_value={"status": "ok"})
        mcp_service._v2_manager = mock_v2

        await mcp_service.call_tool("server-1", "tool-1")
        assert mcp_service._v2_failure_count == 0
        assert mcp_service._v2_circuit_open is False


# ---------------------------------------------------------------------------
# TestRetryOnTransientErrors
# ---------------------------------------------------------------------------

class TestRetryOnTransientErrors:
    @pytest.mark.asyncio
    async def test_retry_on_timeout_error(self, mcp_service):
        """TimeoutError 触发重试，最终成功"""
        mock_v2 = AsyncMock()
        # 第一次 TimeoutError，第二次成功
        mock_v2.execute_tool = AsyncMock(
            side_effect=[TimeoutError("timeout"), {"status": "ok"}]
        )
        mcp_service._v2_manager = mock_v2

        # 使用很短的 delay 加速测试
        mcp_service.RETRY_DELAY_BASE = 0.01
        result = await mcp_service.call_tool("server-1", "tool-1")
        assert result["status"] == "ok"
        assert mock_v2.execute_tool.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, mcp_service):
        """ConnectionError 触发重试"""
        mock_v2 = AsyncMock()
        mock_v2.execute_tool = AsyncMock(
            side_effect=[ConnectionError("refused"), {"status": "ok"}]
        )
        mcp_service._v2_manager = mock_v2

        mcp_service.RETRY_DELAY_BASE = 0.01
        result = await mcp_service.call_tool("server-1", "tool-1")
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_exhausted_retries_records_failure(self, mcp_service):
        """重试耗尽后记录失败"""
        mock_v2 = AsyncMock()
        mock_v2.execute_tool = AsyncMock(side_effect=TimeoutError("timeout"))
        mcp_service._v2_manager = mock_v2
        mcp_service.RETRY_DELAY_BASE = 0.01

        # 需要设置 ToolRegistry fallback 也失败，否则会走到 fallback
        # 先验证 failure count 递增
        await mcp_service.call_tool("server-1", "tool-1")
        assert mcp_service._v2_failure_count > 0

    @pytest.mark.asyncio
    async def test_non_transient_error_no_retry(self, mcp_service):
        """非瞬态错误（如 ValueError）不重试"""
        mock_v2 = AsyncMock()
        mock_v2.execute_tool = AsyncMock(side_effect=ValueError("bad input"))
        mcp_service._v2_manager = mock_v2

        await mcp_service.call_tool("server-1", "tool-1")
        # ValueError 不应触发重试，只调用一次
        assert mock_v2.execute_tool.call_count == 1
        assert mcp_service._v2_failure_count == 1


# ---------------------------------------------------------------------------
# TestCircuitBreaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self, mcp_service):
        """连续失败达到阈值后 circuit breaker 打开"""
        mcp_service.CIRCUIT_BREAKER_THRESHOLD = 3
        mock_v2 = AsyncMock()
        mock_v2.execute_tool = AsyncMock(side_effect=ValueError("fail"))
        mcp_service._v2_manager = mock_v2

        # 连续调用 3 次
        for _ in range(3):
            await mcp_service.call_tool("server-1", "tool-1")

        assert mcp_service._v2_circuit_open is True

    @pytest.mark.asyncio
    async def test_circuit_open_skips_v2(self, mcp_service):
        """circuit breaker 打开后跳过 v2 调用"""
        mcp_service._v2_circuit_open = True
        mcp_service._v2_circuit_open_until = time.time() + 3600  # 1小时后重置

        mock_v2 = AsyncMock()
        mcp_service._v2_manager = mock_v2

        await mcp_service.call_tool("server-1", "tool-1")
        # v2 不应被调用
        mock_v2.execute_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_circuit_resets_after_timeout(self, mcp_service):
        """circuit breaker 超时后重置为半开状态"""
        mcp_service._v2_circuit_open = True
        # 设置为已过期
        mcp_service._v2_circuit_open_until = time.time() - 1

        mock_v2 = AsyncMock()
        mock_v2.execute_tool = AsyncMock(return_value={"status": "ok"})
        mcp_service._v2_manager = mock_v2

        result = await mcp_service.call_tool("server-1", "tool-1")
        # 半开状态允许 v2 调用
        mock_v2.execute_tool.assert_called_once()
        assert mcp_service._v2_circuit_open is False

    @pytest.mark.asyncio
    async def test_circuit_success_resets_failure_count(self, mcp_service):
        """circuit breaker 半开后成功调用重置失败计数"""
        mcp_service._v2_failure_count = 4
        mcp_service._v2_circuit_open = True
        mcp_service._v2_circuit_open_until = time.time() - 1  # 已过期

        mock_v2 = AsyncMock()
        mock_v2.execute_tool = AsyncMock(return_value={"status": "ok"})
        mcp_service._v2_manager = mock_v2

        await mcp_service.call_tool("server-1", "tool-1")
        assert mcp_service._v2_failure_count == 0
        assert mcp_service._v2_circuit_open is False
