"""
LLM Provider 客户端

支持多种 LLM Provider：
- Anthropic Claude
- OpenAI GPT
- OpenRouter
- DeepSeek
- Ollama (本地)
"""

import os
import json
import yaml
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

# 尝试导入各 Provider 的 SDK
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class BaseLLMClient(ABC):
    """LLM 客户端基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = config.get("model", "")
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.7)

    @abstractmethod
    async def complete(self, prompt: str, **kwargs) -> str:
        """完成提示"""
        pass

    @abstractmethod
    async def chat(self, messages: list, **kwargs) -> str:
        """对话模式"""
        pass


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude 客户端"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package not installed")
        
        api_key = config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key not configured")
        
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(self, prompt: str, **kwargs) -> str:
        """完成提示"""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.content[0].text
        except Exception as e:
            return f"Error: {str(e)}"

    async def chat(self, messages: list, **kwargs) -> str:
        """对话模式"""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=messages,
                **kwargs
            )
            return response.content[0].text
        except Exception as e:
            return f"Error: {str(e)}"


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT 客户端"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed")
        
        api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=config.get("base_url"),
        )

    async def complete(self, prompt: str, **kwargs) -> str:
        """完成提示"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {str(e)}"

    async def chat(self, messages: list, **kwargs) -> str:
        """对话模式"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {str(e)}"


class HTTPClient(BaseLLMClient):
    """通用 HTTP 客户端（用于 OpenRouter、DeepSeek 等）"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx package not installed")
        
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url", "")
        self.client = httpx.AsyncClient(timeout=60.0)

    async def complete(self, prompt: str, **kwargs) -> str:
        """完成提示"""
        try:
            headers = {
                "Content-Type": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }
            data.update(kwargs)
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error: {str(e)}"

    async def chat(self, messages: list, **kwargs) -> str:
        """对话模式"""
        try:
            headers = {
                "Content-Type": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            data = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }
            data.update(kwargs)
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error: {str(e)}"


class LLMClientFactory:
    """LLM 客户端工厂"""

    _clients: Dict[str, BaseLLMClient] = {}

    @classmethod
    def create_client(cls, provider: str, config: Dict[str, Any]) -> BaseLLMClient:
        """创建客户端"""
        if provider in cls._clients:
            return cls._clients[provider]
        
        if provider == "anthropic":
            client = AnthropicClient(config)
        elif provider == "openai":
            client = OpenAIClient(config)
        elif provider in ["openrouter", "deepseek", "ollama"]:
            client = HTTPClient(config)
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        cls._clients[provider] = client
        return client

    @classmethod
    def get_client(cls, provider: str) -> Optional[BaseLLMClient]:
        """获取已创建的客户端"""
        return cls._clients.get(provider)


def load_agent_config(config_path: str = "config/agent_config.yaml") -> Dict[str, Any]:
    """加载 Agent 配置"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"加载配置失败: {e}")
        return {}


def get_llm_client(config_path: str = "config/agent_config.yaml") -> Optional[BaseLLMClient]:
    """
    获取 LLM 客户端
    
    根据配置自动选择合适的 Provider。
    """
    config = load_agent_config(config_path)
    
    providers = config.get("providers", {})
    default_provider = config.get("default_provider", "anthropic")
    
    # 查找启用的 Provider
    for provider_name, provider_config in providers.items():
        if provider_config.get("enabled", False):
            try:
                return LLMClientFactory.create_client(provider_name, provider_config)
            except Exception as e:
                print(f"创建 {provider_name} 客户端失败: {e}")
                continue
    
    # 如果没有启用的 Provider，尝试默认 Provider
    default_config = providers.get(default_provider, {})
    if default_config:
        try:
            # 尝试使用环境变量
            return LLMClientFactory.create_client(default_provider, default_config)
        except Exception as e:
            print(f"创建默认 Provider 失败: {e}")
    
    return None


# 便捷函数
async def llm_complete(prompt: str, provider: str = None, **kwargs) -> str:
    """
    使用 LLM 完成提示
    
    Args:
        prompt: 提示文本
        provider: Provider 名称（可选）
        **kwargs: 额外参数
        
    Returns:
        完成结果
    """
    if provider:
        client = LLMClientFactory.get_client(provider)
        if client:
            return await client.complete(prompt, **kwargs)
    
    # 自动选择
    client = get_llm_client()
    if client:
        return await client.complete(prompt, **kwargs)
    
    return "Error: No LLM client available"


async def llm_chat(messages: list, provider: str = None, **kwargs) -> str:
    """
    使用 LLM 进行对话
    
    Args:
        messages: 消息列表
        provider: Provider 名称（可选）
        **kwargs: 额外参数
        
    Returns:
        回复内容
    """
    if provider:
        client = LLMClientFactory.get_client(provider)
        if client:
            return await client.chat(messages, **kwargs)
    
    # 自动选择
    client = get_llm_client()
    if client:
        return await client.chat(messages, **kwargs)
    
    return "Error: No LLM client available"
