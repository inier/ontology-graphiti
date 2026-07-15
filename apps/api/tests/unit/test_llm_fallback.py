"""LLMFallback 单元测试

测试 LLM 降级策略统一模块的核心功能。
"""

import sys
import pytest


# 直接导入 llm_fallback 模块，避免通过 __init__.py 触发 graphiti_core 依赖
from odap.infra.llm.llm_fallback import LLMFallback


class TestLLMFallbackHandleUnavailable:
    """测试 LLMFallback.handle_unavailable 方法"""

    def test_returns_error_status(self):
        """handle_unavailable 应返回 status=error"""
        result = LLMFallback.handle_unavailable("LLM", RuntimeError("连接超时"))
        assert result["status"] == "error"

    def test_returns_service_name_in_message(self):
        """返回消息中应包含服务名称"""
        result = LLMFallback.handle_unavailable("ZhipuAI", RuntimeError("连接超时"))
        assert "ZhipuAI" in result["message"]
        assert "暂不可用" in result["message"]

    def test_returns_llm_unavailable_error_type(self):
        """error_type 应为 llm_unavailable"""
        result = LLMFallback.handle_unavailable("LLM", RuntimeError("test"))
        assert result["error_type"] == "llm_unavailable"

    def test_returns_retry_after(self):
        """retry_after 应为 30 秒"""
        result = LLMFallback.handle_unavailable("LLM", RuntimeError("test"))
        assert result["retry_after"] == 30

    def test_different_exception_types(self):
        """应支持不同类型的异常"""
        # TimeoutError
        result1 = LLMFallback.handle_unavailable("LLM", TimeoutError("超时"))
        assert result1["status"] == "error"
        assert result1["error_type"] == "llm_unavailable"

        # ValueError
        result2 = LLMFallback.handle_unavailable("LLM", ValueError("参数错误"))
        assert result2["status"] == "error"

        # ConnectionError
        result3 = LLMFallback.handle_unavailable("LLM", ConnectionError("连接断开"))
        assert result3["status"] == "error"

    def test_returns_dict_type(self):
        """返回值应为 Dict[str, Any] 类型"""
        result = LLMFallback.handle_unavailable("LLM", RuntimeError("test"))
        assert isinstance(result, dict)
        assert "status" in result
        assert "message" in result
        assert "error_type" in result
        assert "retry_after" in result

    def test_does_not_return_mock_data(self):
        """不应返回 mock 数据或静默降级结果"""
        result = LLMFallback.handle_unavailable("LLM", RuntimeError("test"))
        # 确保没有返回模拟数据字段
        assert "data" not in result
        assert "entities" not in result
        assert "relations" not in result
        # 确保明确是错误状态
        assert result["status"] != "ok"
        assert result["status"] != "success"
