"""LLM 客户端适配器 - 为 NL 查询管线提供统一同步接口"""

import logging
import os
from odap.infra.config_composer import get_config
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NLQueryLLMClient:
    """NL 查询管线 LLM 客户端: 封装 ZhipuAIClient 为同步 generate 接口

    提供统一的 `generate(prompt, max_tokens, timeout)` 同步方法，
    内部使用 ZhipuAIClient 的异步接口 + 事件循环桥接。
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: Optional[str] = None):
        self.api_key = api_key or get_config("llm.api_key", "")
        self.base_url = base_url or get_config("llm.api_base", "")
        self.model = model or get_config("llm.model", "glm-4")
        self._client = None

    def _get_client(self):
        """延迟初始化 ZhipuAIClient"""
        if self._client is not None:
            return self._client
        try:
            from odap.infra.llm.llm_service import ZhipuAIClient
            self._client = ZhipuAIClient(
                config=None,  # 使用环境变量默认值
            )
            # 覆盖配置
            if self.api_key:
                self._client.api_key = self.api_key
            if self.base_url:
                self._client.base_url = self.base_url
            if self.model:
                self._client.model = self.model
            return self._client
        except Exception as e:
            logger.warning(f"ZhipuAIClient init failed: {e}")
            return None

    def generate(self, prompt: str, max_tokens: int = 512,
                 timeout: float = 10.0) -> Optional[str]:
        """同步生成文本。返回生成的文本或 None。"""
        client = self._get_client()
        if client is None:
            return None

        try:
            import asyncio

            async def _call():
                from graphiti_core.llm_client.types import Message
                messages = [Message(role="user", content=prompt)]
                result, _, _ = await client._generate_response(
                    messages=messages,
                    max_tokens=max_tokens,
                )
                if isinstance(result, dict):
                    # 尝试提取文本内容
                    content = result.get("content", "")
                    if isinstance(content, list):
                        # OpenAI 格式: [{"type": "text", "text": "..."}]
                        return " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                    return str(content) if content else str(result)
                return str(result)

            # 尝试在已有事件循环中运行
            try:
                loop = asyncio.get_running_loop()
                # 已有事件循环，使用 run_in_executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _call())
                    return future.result(timeout=timeout)
            except RuntimeError:
                # 没有运行中的事件循环
                return asyncio.run(_call())

        except Exception as e:
            logger.debug(f"LLM generate failed: {e}")
            return None

    def is_available(self) -> bool:
        """检查 LLM 客户端是否可用"""
        return bool(self.api_key) or self._get_client() is not None


class MockLLMClient:
    """Mock LLM 客户端 - 用于测试"""

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        self.responses = responses or {}
        self.call_count = 0

    def generate(self, prompt: str, max_tokens: int = 512,
                 timeout: float = 10.0) -> Optional[str]:
        self.call_count += 1
        # 按关键词匹配预设响应
        for keyword, response in self.responses.items():
            if keyword in prompt:
                return response
        return None

    def is_available(self) -> bool:
        return True


def create_llm_client() -> NLQueryLLMClient:
    """工厂函数: 创建 LLM 客户端"""
    return NLQueryLLMClient()
