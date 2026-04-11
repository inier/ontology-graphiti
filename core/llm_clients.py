"""
智谱 AI (Zhipu AI) LLM 客户端适配器
解决 graphiti 只能使用 OpenAI 官方 API 的问题

智谱 AI 兼容 OpenAI Chat Completions API，但不支持 Responses API
"""

import json
from typing import Any, Optional

import httpx

from graphiti_core.llm_client.config import LLMConfig, ModelSize
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.prompts.models import Message


class ZhipuAIClient(OpenAIClient):
    """
    智谱 AI 客户端适配器
    继承 OpenAIClient，覆盖 _generate_response 方法使用智谱 AI API
    """

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        cache: bool = False,
        client: Any = None,
        max_tokens: int = 4096,
        reasoning: str = 'minimal',
        verbosity: str = 'low'
    ):
        # 先用父类初始化
        super().__init__(config, cache, client, max_tokens, reasoning, verbosity)

        # 然后覆盖为智谱 AI 的配置
        if config:
            self.base_url = config.base_url.rstrip('/')
            self.api_key = config.api_key
            self.model = config.model
            self.temperature = config.temperature
        else:
            self.base_url = "https://open.bigmodel.cn/api/paas/v4"
            self.api_key = ""
            self.model = "glm-4"
            self.temperature = 0.7

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: Any = None,
        max_tokens: int = 4096,
        model_size: ModelSize = ModelSize.medium
    ) -> tuple[dict[str, Any], int, int]:
        """
        生成响应 - 使用智谱 AI Chat Completions API

        Returns:
            tuple: (response_dict, input_tokens, output_tokens)
        """
        # 将 messages 转换为智谱 AI 格式
        zhipu_messages = []
        for msg in messages:
            zhipu_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # 使用智谱 AI 的 Chat Completions API (不是 Responses API)
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": zhipu_messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens
        }

        async with httpx.AsyncClient(timeout=120.0) as http_client:
            response = await http_client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise Exception(f"API request failed with status {response.status_code}: {response.text}")

            result = response.json()

            # 提取响应内容
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
            else:
                content = str(result)

            # 提取 token 使用量
            prompt_tokens = result.get('usage', {}).get('prompt_tokens', 0)
            completion_tokens = result.get('usage', {}).get('completion_tokens', 0)

            # 解析 JSON 响应
            try:
                response_dict = json.loads(content)
            except:
                response_dict = {"response": content}

            return response_dict, prompt_tokens, completion_tokens
