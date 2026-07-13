"""
OpenHarness 深度整合适配器

完全基于 OpenHarness QueryEngine 实现 Agent Loop：
- GraphitiAgentLoop 委托给 OH QueryEngine.submit_message()
- 工具通过 GraphitiToolAdapter 注册到 OH ToolRegistry
- 权限检查通过 OH PermissionChecker
- 生命周期钩子通过 OH HookExecutor
- 韧性保障通过 CircuitBreaker + FaultRecovery

不再自建 Agent Loop 循环机制，完全复用 OpenHarness 运行时。
"""

import json
import os
import sys
import time
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from odap.infra.config_composer import get_config

logger = logging.getLogger("openharness")

# 配置 OpenHarness 路径
OPENHARNESS_SRC = os.environ.get(
    'OPENHARNESS_PATH',
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'openharness', 'src')
)
if os.path.exists(OPENHARNESS_SRC) and OPENHARNESS_SRC not in sys.path:
    sys.path.insert(0, OPENHARNESS_SRC)

# 导入 OpenHarness 核心组件
try:
    from openharness.tools.base import BaseTool, ToolRegistry, ToolExecutionContext, ToolResult
    from openharness.engine.query_engine import QueryEngine
    from openharness.engine.stream_events import AssistantTurnComplete, StreamEvent
    from openharness.engine.messages import ConversationMessage
    from openharness.config.settings import Settings, PermissionSettings
    from openharness.hooks.executor import HookExecutor, HookExecutionContext
    from openharness.hooks.loader import HookRegistry
    from openharness.hooks.events import HookEvent
    from openharness.permissions.checker import PermissionChecker
    from openharness.permissions.modes import PermissionMode
    from openharness.api.client import SupportsStreamingMessages
    OPENHARNESS_AVAILABLE = True
except ImportError as e:
    OPENHARNESS_AVAILABLE = False
    logger.debug("OpenHarness import failed: %s", e)

# 导入韧性基础设施
try:
    from odap.infra.resilience.circuit_breaker import get_circuit_breaker, CircuitOpenError
    from odap.infra.resilience.fault_tolerance import FaultRecoveryManager
    RESILIENCE_AVAILABLE = True
except ImportError as e:
    logger.debug("Resilience import failed: %s", e)
    RESILIENCE_AVAILABLE = False


# ---------------------------------------------------------------------------
# OpenAI 兼容客户端（适配 OH SupportsStreamingMessages 接口）
# ---------------------------------------------------------------------------

class OpenAICompatClient:
    """OpenAI 兼容客户端，适配 OpenHarness SupportsStreamingMessages 接口

    支持通过 OPENAI_API_BASE 配置的任意 OpenAI 兼容 API
    （DeepSeek / Qwen / 通义千问 / 任意 OpenAI 兼容端点）。
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        try:
            import openai
            # timeout: NVIDIA API 等部分端点响应较慢，设置 120s 超时
            self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
        except ImportError:
            raise ImportError("openai package required: pip install openai")
        self._model = model
        self._api_key = api_key
        self._base_url = base_url

    @staticmethod
    def _convert_tools_to_openai_format(tools):
        """将 OH ToolRegistry.to_api_schema() 返回的 Anthropic 格式转为 OpenAI 格式。

        OH 的 to_api_schema() 返回:
            [{"name": ..., "description": ..., "input_schema": {...}}]
        OpenAI 兼容 API 需要:
            [{"type": "function",
              "function": {"name": ..., "description": ..., "parameters": {...}}}]

        同时清理 input_schema 中的 anyOf（来自 str|None 联合类型），
        因为部分 OpenAI 兼容端点（如 NVIDIA）不接受 anyOf，要求每个属性
        都有直接的 type 字段。
        """
        if not tools:
            return None

        def _simplify_schema(schema):
            """递归清理 schema：把 anyOf 折叠为简单 type，去掉 title 等冗余字段。"""
            if not isinstance(schema, dict):
                return schema

            # anyOf: 取第一个非 null 的类型
            if "anyOf" in schema:
                for sub in schema["anyOf"]:
                    if isinstance(sub, dict) and sub.get("type") != "null":
                        simplified = _simplify_schema(sub)
                        if "default" in schema:
                            simplified = {**simplified, "default": schema["default"]}
                        if "description" in schema:
                            simplified.setdefault("description", schema["description"])
                        return simplified
                # 全部为 null 或空，回退为 string
                return {"type": "string"}

            result = {}
            for k, v in schema.items():
                if k == "properties" and isinstance(v, dict):
                    result["properties"] = {
                        prop: _simplify_schema(val) for prop, val in v.items()
                    }
                elif k == "items":
                    result["items"] = _simplify_schema(v)
                elif k in ("title",):
                    # 跳过冗余字段
                    continue
                else:
                    result[k] = v
            return result

        openai_tools = []
        for t in tools:
            if isinstance(t, dict):
                # 已经是 OpenAI 格式
                if t.get("type") == "function" and "function" in t:
                    openai_tools.append(t)
                    continue
                # Anthropic 格式转换
                input_schema = t.get("input_schema") or t.get("parameters") or {}
                parameters = _simplify_schema(input_schema)
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "parameters": parameters,
                    },
                })
        return openai_tools or None

    async def stream_message(self, request):
        """流式消息接口（适配 OpenHarness QueryEngine）

        完整支持 OpenAI tool calling：
        - 解析 delta.tool_calls 并组装为 ToolUseBlock
        - 将 ConversationMessage 中的 ToolUseBlock/ToolResultBlock 转为 OpenAI 格式
        """
        from openharness.api.client import (
            ApiMessageRequest,
            ApiTextDeltaEvent,
            ApiMessageCompleteEvent,
        )
        from openharness.engine.messages import (
            ConversationMessage,
            TextBlock,
            ToolUseBlock,
            ToolResultBlock,
        )

        # ── 将 OH ConversationMessage 列表转为 OpenAI messages 格式 ──
        formatted = []
        for msg in request.messages:
            if hasattr(msg, 'role') and hasattr(msg, 'content'):
                if isinstance(msg.content, list):
                    text_parts = []
                    tool_calls_openai = []
                    tool_result_blocks = []
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            text_parts.append(block.text)
                        elif isinstance(block, ToolUseBlock):
                            tool_calls_openai.append({
                                "id": block.id,
                                "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": json.dumps(block.input, ensure_ascii=False),
                                },
                            })
                        elif isinstance(block, ToolResultBlock):
                            tool_result_blocks.append(block)
                        elif isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif block.get("type") == "tool_use":
                                tool_calls_openai.append({
                                    "id": block.get("id", ""),
                                    "type": "function",
                                    "function": {
                                        "name": block.get("name", ""),
                                        "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                                    },
                                })
                            elif block.get("type") == "tool_result":
                                tool_result_blocks.append(ToolResultBlock(
                                    tool_use_id=block.get("tool_use_id", ""),
                                    content=block.get("content", ""),
                                    is_error=block.get("is_error", False),
                                ))

                    # tool_result 块需要作为独立的 "tool" role 消息发送
                    for trb in tool_result_blocks:
                        formatted.append({
                            "role": "tool",
                            "tool_call_id": trb.tool_use_id,
                            "content": trb.content,
                        })

                    # assistant 消息（可能含文本 + tool_calls）
                    if msg.role == "assistant":
                        msg_dict = {"role": "assistant", "content": "\n".join(text_parts) if text_parts else None}
                        if tool_calls_openai:
                            msg_dict["tool_calls"] = tool_calls_openai
                        formatted.append(msg_dict)
                    else:
                        # user 消息
                        formatted.append({"role": msg.role, "content": "\n".join(text_parts) if text_parts else ""})
                else:
                    formatted.append({"role": msg.role, "content": str(msg.content)})
            elif isinstance(msg, dict):
                formatted.append(msg)
            else:
                formatted.append({"role": "user", "content": str(msg)})

        params = {
            "model": request.model or self._model,
            "messages": formatted,
            "max_tokens": request.max_tokens or 4096,
            "stream": True,
        }
        if request.system_prompt:
            params["messages"] = [{"role": "system", "content": request.system_prompt}] + params["messages"]

        # 工具定义：将 OH Anthropic 格式转为 OpenAI 格式（清理 anyOf）
        openai_tools = self._convert_tools_to_openai_format(request.tools)
        if openai_tools:
            params["tools"] = openai_tools

        # ── 流式收集：文本 + 工具调用 ──
        response_text = ""
        # tool_calls_buffer: {index: {"id":..., "name":..., "arguments": "..."}}
        tool_calls_buffer: Dict[int, Dict[str, Any]] = {}
        finish_reason = None

        async for chunk in await self._client.chat.completions.create(**params):
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            if delta:
                # 文本增量
                if delta.content:
                    response_text += delta.content
                    yield ApiTextDeltaEvent(text=delta.content)

                # 工具调用增量（OpenAI 流式格式：分片到达）
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index if tc_delta.index is not None else 0
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc_delta.id:
                            tool_calls_buffer[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_buffer[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_buffer[idx]["arguments"] += tc_delta.function.arguments

            if choice.finish_reason:
                finish_reason = choice.finish_reason

        # ── 组装最终 ConversationMessage ──
        content_blocks = []
        if response_text.strip():
            content_blocks.append(TextBlock(text=response_text))

        # 将收集到的 tool_calls 转为 ToolUseBlock
        for idx in sorted(tool_calls_buffer.keys()):
            tc = tool_calls_buffer[idx]
            tc_id = tc["id"] or f"toolu_{idx}"
            tc_name = tc["name"]
            tc_args_str = tc["arguments"] or "{}"
            try:
                tc_input = json.loads(tc_args_str) if tc_args_str else {}
            except json.JSONDecodeError:
                logger.warning("Failed to parse tool call arguments: %s", tc_args_str)
                tc_input = {"_raw": tc_args_str}

            content_blocks.append(ToolUseBlock(
                id=tc_id,
                name=tc_name,
                input=tc_input,
            ))

        complete_msg = ConversationMessage(role="assistant", content=content_blocks)

        # stop_reason: "tool_calls" → "tool_use", "stop" → "end_turn"
        stop_reason = "tool_use" if finish_reason == "tool_calls" else (finish_reason or "end_turn")

        yield ApiMessageCompleteEvent(message=complete_msg, usage=None, stop_reason=stop_reason)


# ---------------------------------------------------------------------------
# GraphitiToolAdapter — 将 ODAP Skill 适配为 OH BaseTool
# ---------------------------------------------------------------------------

class GraphitiToolAdapter(BaseTool if OPENHARNESS_AVAILABLE else object):
    """将 Graphiti Skill 适配为 OpenHarness BaseTool

    这是 ODAP Skill → OH Tool 的统一适配层，合并了原 OpenHarnessToolAdapter 的功能：
    - QueryEngine 模式：继承 BaseTool，支持 execute() + input_model
    - 兼容接口：支持 run() 方法
    - OPA 权限检查
    - OpenAI function calling schema 生成
    """

    def __init__(self, name: str, description: str, handler: Callable,
                 category: str = "general", opa_manager=None):
        if OPENHARNESS_AVAILABLE:
            super().__init__()
            from pydantic import BaseModel, Field

            class DynamicInput(BaseModel):
                query: str = Field(default="", description="查询参数")
                params: Dict[str, Any] = Field(default_factory=dict, description="额外参数")

            self.input_model = DynamicInput
        self.name = name
        self.description = description
        self.handler = handler
        self.category = category
        self.opa_manager = opa_manager
        self.call_count = 0
        self._success_count = 0
        self._error_count = 0

    async def execute(self, arguments, context) -> Any:
        """执行工具调用（OpenHarness 接口）"""
        self.call_count += 1
        start = time.perf_counter()

        try:
            params = arguments.model_dump() if hasattr(arguments, 'model_dump') else dict(arguments)

            # OPA 权限检查
            if self.opa_manager:
                try:
                    allowed = self.opa_manager.check_permission(
                        resource=f"tool:{self.name}",
                        action="execute",
                        context={"tool_name": self.name, "params": params},
                    )
                    if not allowed:
                        return ToolResult(
                            output=f"权限拒绝: 工具 {self.name} 不允许执行",
                            error=True,
                        ) if OPENHARNESS_AVAILABLE else {"status": "error", "error": "Permission denied"}
                except Exception as e:
                    logger.debug("OPA check failed for %s: %s", self.name, e)

            if asyncio.iscoroutinefunction(self.handler):
                result = await self.handler(**params)
            else:
                result = self.handler(**params)

            elapsed_ms = (time.perf_counter() - start) * 1000
            self._success_count += 1

            if isinstance(result, (dict, list)):
                output = result
            else:
                output = {"result": str(result)}

            if OPENHARNESS_AVAILABLE:
                return ToolResult(output=json.dumps(output, ensure_ascii=False), error=False)

            return {
                "status": "success",
                "data": output,
                "tool": self.name,
                "execution_time_ms": round(elapsed_ms, 2),
            }

        except Exception as e:
            self._error_count += 1
            if OPENHARNESS_AVAILABLE:
                return ToolResult(output=str(e), error=True)
            return {"status": "error", "error": str(e), "tool": self.name}

    def to_openai_schema(self) -> Dict:
        """生成 OpenAI function calling 格式"""
        if OPENHARNESS_AVAILABLE and hasattr(self, 'to_api_schema'):
            try:
                return self.to_api_schema()
            except Exception:
                pass
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }
            }
        }

    def run(self, action: Dict[str, Any]) -> str:
        """执行工具调用（兼容接口）"""
        self.call_count += 1
        start = time.perf_counter()

        try:
            params = {k: v for k, v in action.items()
                      if k not in ("name", "type", "thought", "tool_name")}

            result = self.handler(**params)

            elapsed_ms = (time.perf_counter() - start) * 1000

            if isinstance(result, (dict, list)):
                output = result
            else:
                output = {"result": str(result)}

            return json.dumps({
                "status": "success",
                "data": output,
                "tool": self.name,
                "execution_time_ms": round(elapsed_ms, 2),
                "call_count": self.call_count,
            }, ensure_ascii=False, default=str)

        except TypeError as e:
            return json.dumps({
                "status": "error",
                "error": f"参数错误: {e}",
                "tool": self.name,
                "call_count": self.call_count,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": str(e),
                "tool": self.name,
                "call_count": self.call_count,
            }, ensure_ascii=False)

    # 别名：保持与 OpenHarnessToolAdapter 的兼容性
    to_openai_tool_schema = to_openai_schema


# ---------------------------------------------------------------------------
# OHQueryEngineFactory — 统一创建 QueryEngine 实例
# ---------------------------------------------------------------------------

class OHQueryEngineFactory:
    """OpenHarness QueryEngine 工厂

    统一创建配置好的 QueryEngine 实例，确保：
    1. 使用 OpenAI 兼容客户端（而非硬编码 Anthropic）
    2. 工具注册到 ToolRegistry
    3. 权限检查通过 PermissionChecker
    4. 生命周期钩子通过 HookExecutor
    5. CircuitBreaker 保护 LLM 调用
    """

    _instance: Optional['OHQueryEngineFactory'] = None

    def __init__(self):
        self._api_client: Optional[SupportsStreamingMessages] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._permission_checker: Optional[PermissionChecker] = None
        self._hook_executor: Optional[HookExecutor] = None
        self._model: str = ""
        self._api_key: str = ""
        self._base_url: str = ""
        self._initialized: bool = False
        self._hot_reload_subscribed: bool = False

    @classmethod
    def get_instance(cls) -> 'OHQueryEngineFactory':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def configure(self,
                  api_key: str = None,
                  base_url: str = None,
                  model: str = None,
                  opa_manager=None) -> bool:
        """配置工厂参数

        Args:
            api_key: OpenAI 兼容 API Key
            base_url: OpenAI 兼容 API 基地址
            model: 模型名称
            opa_manager: OPA 权限管理器
        """
        # 环境变量优先于 get_config：get_config 可能返回加密后无法解密的密文
        # （CONFIG_ENCRYPTION_KEY 在容器重启后重新生成，导致旧密文无法解密）
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "") or get_config("llm.api_key", "")
        self._base_url = base_url or os.environ.get("OPENAI_API_BASE", "") or get_config("llm.api_base", "")
        self._model = model or os.environ.get("OPENAI_MODEL", "") or get_config("llm.model", "")

        if not self._api_key:
            logger.warning("OHQueryEngineFactory: API key not configured")
            return False

        # 创建 OpenAI 兼容客户端
        try:
            self._api_client = OpenAICompatClient(
                api_key=self._api_key,
                base_url=self._base_url,
                model=self._model,
            )
            logger.info("OHQueryEngineFactory: OpenAI 兼容客户端创建成功 (model=%s)", self._model)
        except Exception as e:
            logger.warning("OHQueryEngineFactory: 客户端创建失败: %s", e)
            return False

        # 创建 ToolRegistry
        if OPENHARNESS_AVAILABLE:
            self._tool_registry = ToolRegistry()
            self._register_skills(opa_manager)
        else:
            self._tool_registry = None

        # 创建 PermissionChecker（full_auto 模式，OPA 作为上层检查）
        if OPENHARNESS_AVAILABLE:
            perm_settings = PermissionSettings(mode=PermissionMode.FULL_AUTO)
            self._permission_checker = PermissionChecker(perm_settings)
        else:
            self._permission_checker = None

        # 创建 HookExecutor
        if OPENHARNESS_AVAILABLE:
            hook_registry = HookRegistry()
            hook_context = HookExecutionContext(
                cwd=Path(os.getcwd()),
                api_client=self._api_client,
                default_model=self._model,
            )
            self._hook_executor = HookExecutor(hook_registry, hook_context)
        else:
            self._hook_executor = None

        self._initialized = True

        # 注册热更新订阅：当 LLM 配置变更时自动重新配置
        self._setup_hot_reload()

        return True

    def _register_skills(self, opa_manager=None):
        """注册工具到 OH ToolRegistry

        注册两个来源的工具：
        1. AI Assistant Plugin 的 16 个 BaseTool（本体查询/设计/写入）— Phase 1 迁移产物
        2. SKILL_CATALOG 中的领域 Skill（通过 GraphitiToolAdapter 适配）
        """
        count = 0

        # --- 1. AI Assistant Plugin BaseTools ---
        try:
            from odap.biz.core.assistant.plugins.ai_assistant.tools import ALL_TOOLS as AI_ASSISTANT_TOOLS
            for tool in AI_ASSISTANT_TOOLS:
                self._tool_registry.register(tool)
                count += 1
            logger.info(
                "OHQueryEngineFactory: %d 个 AI Assistant Plugin 工具注册到 ToolRegistry",
                count,
            )
        except Exception as e:
            logger.warning("OHQueryEngineFactory: AI Assistant Plugin 工具注册失败: %s", e)

        # --- 2. SKILL_CATALOG 领域 Skill（向后兼容） ---
        try:
            from odap.tools import SKILL_CATALOG
            skill_count = 0
            for name, entry in SKILL_CATALOG.items():
                # 跳过与 AI Assistant Plugin 同名的工具，避免重复注册
                if self._tool_registry.get(name) is not None:
                    continue
                tool = GraphitiToolAdapter(
                    name=name,
                    description=entry["description"],
                    handler=entry["handler"],
                    category=entry.get("category", "general"),
                    opa_manager=opa_manager,
                )
                self._tool_registry.register(tool)
                skill_count += 1
            count += skill_count
            logger.info(
                "OHQueryEngineFactory: %d 个 SKILL_CATALOG Skill 注册到 ToolRegistry",
                skill_count,
            )
        except Exception as e:
            logger.warning("OHQueryEngineFactory: SKILL_CATALOG Skill 注册失败: %s", e)

        logger.info("OHQueryEngineFactory: ToolRegistry 共注册 %d 个工具", count)

    def _setup_hot_reload(self):
        """注册配置热更新订阅。

        当用户通过 SettingsPage 修改 LLM 配置时，
        ConfigManager 会通知本工厂自动重新配置，无需重启服务。
        """
        if self._hot_reload_subscribed:
            return
        try:
            from odap.biz.platform.config.impl.config_manager import ConfigManager
            mgr = ConfigManager.get_instance()

            # 订阅 LLM 相关配置项的变更
            config_keys = ["llm.api_key", "llm.api_base", "llm.model", "llm.temperature"]
            for key in config_keys:
                mgr.subscribe(key, self._on_llm_config_changed)
            self._hot_reload_subscribed = True
            logger.info("OHQueryEngineFactory: 已注册 LLM 配置热更新订阅 (keys=%s)", config_keys)
        except Exception as e:
            logger.warning("OHQueryEngineFactory: 注册热更新订阅失败 (可能 ConfigManager 尚未初始化): %s", e)

    def _on_llm_config_changed(self, key: str, old_value: Optional[str], new_value: str):
        """LLM 配置变更回调 — 自动重新配置工厂"""
        logger.info(
            "OHQueryEngineFactory: LLM 配置变更 detected (key=%s), 开始热重载...",
            key,
        )
        try:
            # 重新读取所有 LLM 配置并重新配置工厂
            reconfigured = self.configure()
            if reconfigured:
                logger.info("OHQueryEngineFactory: 热重载成功 (model=%s)", self._model)
            else:
                logger.warning("OHQueryEngineFactory: 热重载失败，保持现有配置")
        except Exception as e:
            logger.error("OHQueryEngineFactory: 热重载异常: %s", e)

    def create_engine(self,
                      system_prompt: str = "",
                      max_turns: int = 8,
                      workspace_id: str = "",
                      scenario_id: str = "",
                      session_id: str = "") -> Any:
        """创建配置好的 QueryEngine 实例

        Args:
            system_prompt: 系统提示词
            max_turns: 最大工具调用轮次
            workspace_id: 工作空间 ID
            scenario_id: 场景 ID
            session_id: 会话 ID，用于恢复对话历史

        Returns:
            QueryEngine 实例，OH 不可用时返回 None
        """
        if not OPENHARNESS_AVAILABLE or not self._initialized:
            logger.warning("OHQueryEngineFactory: OpenHarness 不可用或未初始化")
            return None

        if not self._api_client:
            logger.warning("OHQueryEngineFactory: API 客户端未配置")
            return None

        # 注入 workspace/scenario 到 tool_metadata
        tool_metadata = {
            "workspace_id": workspace_id,
            "scenario_id": scenario_id,
        }

        try:
            engine = QueryEngine(
                api_client=self._api_client,
                tool_registry=self._tool_registry,
                permission_checker=self._permission_checker,
                cwd=os.getcwd(),
                model=self._model,
                system_prompt=system_prompt,
                max_tokens=4096,
                max_turns=max_turns,
                hook_executor=self._hook_executor,
                tool_metadata=tool_metadata,
            )

            # 恢复对话历史
            if session_id:
                self._load_session_into_engine(engine, session_id)

            logger.info("OHQueryEngineFactory: QueryEngine 创建成功 (max_turns=%d)", max_turns)
            return engine
        except Exception as e:
            logger.warning("OHQueryEngineFactory: QueryEngine 创建失败: %s", e)
            return None

    def _load_session_into_engine(self, engine: Any, session_id: str) -> None:
        """从 SessionMemoryService 加载历史消息到 QueryEngine"""
        try:
            from odap.biz.platform.session_memory.services.session_memory_service import get_session_memory_service

            sms = get_session_memory_service()
            session = sms.store.load_session(session_id)
            if not session or not session.messages:
                return

            # 将 ODAP ChatMessage 转换为 OH ConversationMessage
            oh_messages = []
            for msg in session.messages:
                if msg.role.value in ("user", "assistant"):
                    oh_msg = ConversationMessage(
                        role=msg.role.value,
                        content=[{"type": "text", "text": msg.content}],
                    )
                    oh_messages.append(oh_msg)

            if oh_messages:
                engine.load_messages(oh_messages)
                logger.info("OHQueryEngineFactory: 恢复 %d 条历史消息到 QueryEngine", len(oh_messages))
        except ImportError:
            logger.debug("OH ConversationMessage 不可用，跳过历史恢复")
        except Exception as e:
            logger.warning("OHQueryEngineFactory: 恢复历史消息失败: %s", e)

    @property
    def is_available(self) -> bool:
        return OPENHARNESS_AVAILABLE and self._initialized

    @property
    def tool_count(self) -> int:
        if self._tool_registry:
            return len(self._tool_registry._tools) if hasattr(self._tool_registry, '_tools') else 0
        return 0


# ---------------------------------------------------------------------------
# GraphitiAgentLoop — 完全基于 OH QueryEngine 的 Agent Loop
# ---------------------------------------------------------------------------

class GraphitiAgentLoop:
    """基于 OpenHarness QueryEngine 的 Agent Loop

    不再自建循环机制，完全委托给 OH QueryEngine.submit_message()。
    QueryEngine 内置：
    - LLM 调用 → 工具选择 → 执行 → 观察 → 循环
    - 自动压缩（auto_compact）
    - 权限检查（PermissionChecker）
    - 生命周期钩子（HookExecutor）
    - Token 追踪（CostTracker）

    本类仅负责：
    1. 创建配置好的 QueryEngine
    2. 将用户输入提交给 QueryEngine
    3. 收集流式事件并组装结果
    4. CircuitBreaker 保护 + FaultRecovery 降级
    """

    def __init__(self,
                 user_role: str = "intelligence_analyst",
                 opa_manager=None,
                 graph_manager=None,
                 llm_client=None,  # deprecated: kept for backward compat, not used in main path
                 workspace_id: str = "",
                 scenario_id: str = ""):
        self.user_role = user_role
        self.opa_manager = opa_manager
        self.graph_manager = graph_manager
        # llm_client is retained for backward compatibility only.
        # The fallback path now uses OpenAICompatClient (unified LLM client).
        self.llm_client = llm_client
        self.workspace_id = workspace_id
        self.scenario_id = scenario_id

        # 韧性基础设施
        if RESILIENCE_AVAILABLE:
            self._llm_circuit_breaker = get_circuit_breaker("agent_loop_llm", failure_threshold_pct=0.5)
            self._fault_manager = FaultRecoveryManager.get_instance()
        else:
            self._llm_circuit_breaker = None
            self._fault_manager = None

        # 初始化 OH QueryEngine 工厂
        self._factory = OHQueryEngineFactory.get_instance()
        self._engine: Optional[QueryEngine] = None
        self._current_session_id: str = ""
        self._fallback_tools: Dict[str, GraphitiToolAdapter] = {}

        # 尝试初始化工厂
        self._try_init_factory()

        # 构建 fallback 工具列表（OH 不可用时使用）
        self._build_fallback_tools()

    def _try_init_factory(self):
        """尝试初始化 QueryEngine 工厂"""
        if self._factory.is_available:
            return

        # 环境变量优先于 get_config：get_config 可能返回加密后无法解密的密文
        # （CONFIG_ENCRYPTION_KEY 在容器重启后重新生成，导致旧密文无法解密）
        api_key = os.environ.get("OPENAI_API_KEY", "") or get_config("llm.api_key", "")
        base_url = os.environ.get("OPENAI_API_BASE", "") or get_config("llm.api_base", "https://api.openai.com/v1")
        model = os.environ.get("OPENAI_MODEL", "") or get_config("llm.model", "gpt-4")

        self._factory.configure(
            api_key=api_key,
            base_url=base_url,
            model=model,
            opa_manager=self.opa_manager,
        )

    def _build_fallback_tools(self):
        """构建 fallback 工具列表（OH 不可用时使用）"""
        try:
            from odap.tools import SKILL_CATALOG
            for name, entry in SKILL_CATALOG.items():
                tool = GraphitiToolAdapter(
                    name=name,
                    description=entry["description"],
                    handler=entry["handler"],
                    category=entry.get("category", "general"),
                    opa_manager=self.opa_manager,
                )
                self._fallback_tools[name] = tool
        except Exception as e:
            logger.warning("Build fallback tools failed: %s", e)

    def _get_system_prompt(self, ontology_id: str = None) -> str:
        """构建系统提示词

        当 ontology_id 存在时，自动注入当前本体的类型列表，
        并启用本体设计辅助与增删改查能力。
        """
        base_prompt = f"""你是 ODAP 平台的领域分析智能体，当前角色: {self.user_role}

你的核心能力:
1. **查询知识图谱**: 查询实体、搜索关系、分析图谱结构
2. **本体设计辅助**: 获取本体上下文、建议属性、建议关系、检查完整性
3. **本体增删改查**: 你可以**直接修改**本体设计！包括：
   - 给对象类型新增/更新/删除属性 (add_property / update_property / remove_property)
   - 批量添加属性 (add_properties)
   - 创建/删除对象类型 (create_object_type / delete_object_type)
   - 创建/删除关系类型 (create_link_type / delete_link_type)
4. **日常问答**: 回答关于平台使用、本体设计最佳实践的问题

类型名称智能匹配:
- 用户可能用中文或英文指代类型（如「里程碑」=Milestone、「任务」=Task）
- 你只需将用户原始输入作为 object_type_name 参数传入，后端会自动进行中英文别名和模糊匹配

工作规则:
- 当用户问"有哪些对象类型""本体结构"时 → 调用 get_ontology_context
- 当用户问"完整性怎么样""缺什么"时 → 调用 check_completeness
- 当用户问"建议属性""还缺什么属性"时 → 调用 suggest_properties
- 当用户问"建议关系"时 → 调用 suggest_relations
- 当用户要求"新增""添加""创建""删除"等操作时 → **直接调用对应的写操作工具执行，不要只是建议**
- data_type 可选值: STRING, INTEGER, FLOAT, BOOLEAN, DATETIME, TEXT
- 返回清晰、结构化的回答，中文优先
- 写操作执行后，明确告诉用户操作是否成功，以及具体做了什么

工作空间: {self.workspace_id or '未指定'}
场景: {self.scenario_id or '未指定'}"""

        # 自动注入当前本体上下文
        if ontology_id:
            try:
                from odap.biz.core.assistant.plugins.ai_assistant.registry import (
                    get_ontology_context as _get_ctx,
                )
                ctx_result = _get_ctx(ontology_id)
                if ctx_result.get("status") == "success":
                    ctx = ctx_result.get("context", {})
                    type_lines = []
                    for t in ctx.get("object_types", []):
                        props = ", ".join(t.get("properties", [])[:8])
                        type_lines.append(f"  - {t.get('name','?')}: [{props}]")
                    link_lines = []
                    for l in ctx.get("link_types", []):
                        link_lines.append(
                            f"  - {l.get('name','?')}: {l.get('source','')} -> {l.get('target','')}"
                        )

                    base_prompt += (
                        f"\n\n【当前本体上下文（自动注入）】\n"
                        f"本体ID: {ontology_id}\n"
                        f"对象类型 ({ctx.get('object_type_count',0)} 个):\n"
                        + (chr(10).join(type_lines) if type_lines else "  (无)") + "\n\n"
                        f"关系类型 ({ctx.get('link_type_count',0)} 个):\n"
                        + (chr(10).join(link_lines) if link_lines else "  (无)") + "\n\n"
                        "重要: 用户可能用中文或英文指代类型（如「里程碑」=Milestone），"
                        "请根据上方类型列表智能匹配。object_type_name 参数传入用户原始输入即可。"
                    )
            except Exception as e:
                logger.warning("Auto-inject ontology context into system prompt failed: %s", e)

        return base_prompt

    async def run(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """运行 Agent Loop

        优先使用 OH QueryEngine（完全复用 OH 运行时），
        OH 不可用时降级到自建简单循环。
        """
        if self._factory.is_available:
            return await self._run_with_query_engine(user_input, context)
        else:
            return await self._run_fallback(user_input, context)

    async def _run_with_query_engine(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """通过 OH QueryEngine 运行 Agent Loop（主路径）"""
        max_turns = (context or {}).get("max_turns", 8)
        session_id = (context or {}).get("session_id", "")
        ontology_id = (context or {}).get("ontology_id")

        # 根据 session_id 决定是否复用或新建 QueryEngine
        if not self._engine or (session_id and session_id != self._current_session_id):
            self._engine = self._factory.create_engine(
                system_prompt=self._get_system_prompt(ontology_id),
                max_turns=max_turns,
                workspace_id=self.workspace_id,
                scenario_id=self.scenario_id,
                session_id=session_id,
            )
            self._current_session_id = session_id
        elif not session_id and not self._engine:
            self._engine = self._factory.create_engine(
                system_prompt=self._get_system_prompt(ontology_id),
                max_turns=max_turns,
                workspace_id=self.workspace_id,
                scenario_id=self.scenario_id,
            )

        if not self._engine:
            logger.warning("QueryEngine 创建失败，降级到 fallback")
            return await self._run_fallback(user_input, context)

        # 通过 CircuitBreaker 保护提交
        start_time = time.perf_counter()
        steps = []
        final_text = ""

        try:
            if self._llm_circuit_breaker:
                async def _submit():
                    results = []
                    text_parts = []
                    async for event in self._engine.submit_message(user_input):
                        if isinstance(event, AssistantTurnComplete):
                            pass  # 一轮完成
                        elif hasattr(event, 'text'):
                            text_parts.append(event.text)
                        results.append(event)
                    return results, "".join(text_parts)

                _, final_text = await self._llm_circuit_breaker.acall(_submit)
            else:
                text_parts = []
                async for event in self._engine.submit_message(user_input):
                    if hasattr(event, 'text'):
                        text_parts.append(event.text)
                    steps.append(str(type(event).__name__))
                final_text = "".join(text_parts)

        except CircuitOpenError:
            logger.warning("CircuitBreaker 打开，LLM 调用被熔断")
            return {
                "success": False,
                "error": "LLM 服务熔断中，请稍后重试",
                "steps": steps,
                "total_steps": len(steps),
            }
        except Exception as e:
            logger.warning("QueryEngine 执行失败: %s，降级到 fallback", e)
            return await self._run_fallback(user_input, context)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # 写入 Graphiti Episode（记忆持久化）
        await self._write_episode(user_input, final_text)

        return {
            "success": True,
            "response": final_text,
            "steps": steps,
            "total_steps": len(steps),
            "execution_time_ms": round(elapsed_ms, 2),
            "engine": "openharness_query_engine",
        }

    async def _run_fallback(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """降级路径：OH 不可用时的简单循环

        使用 OpenAICompatClient（统一 LLM 客户端）替代旧的 llm_client，
        确保 fallback 路径与主路径使用相同的 LLM 基础设施。
        """
        logger.info("使用 fallback 模式运行 Agent Loop")
        ontology_id = (context or {}).get("ontology_id")

        # 环境变量优先于 get_config（与 _try_init_factory 保持一致）
        api_key = os.environ.get("OPENAI_API_KEY", "") or get_config("llm.api_key", "")
        base_url = os.environ.get("OPENAI_API_BASE", "") or get_config("llm.api_base", "https://api.openai.com/v1")
        model = os.environ.get("OPENAI_MODEL", "") or get_config("llm.model", "gpt-4")

        if api_key:
            try:
                compat_client = OpenAICompatClient(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                )
                system_prompt = self._get_system_prompt(ontology_id)

                # 通过 OpenAI SDK 直接调用（非流式）
                import openai as _openai
                client = _openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input},
                    ],
                    max_tokens=4096,
                    temperature=0.7,
                )
                result_text = response.choices[0].message.content

                await self._write_episode(user_input, result_text)
                return {
                    "success": True,
                    "response": result_text,
                    "steps": ["openai_compat_direct"],
                    "total_steps": 1,
                    "engine": "fallback_openai_compat",
                }
            except Exception as e:
                logger.warning("OpenAICompatClient 直接调用失败: %s", e)

        # 最终降级：关键词匹配
        action = self._fallback_decide(user_input)
        if action and action["tool_name"] != "end_mission":
            tool = self._fallback_tools.get(action["tool_name"])
            if tool:
                try:
                    result = await tool.execute(
                        action["params"],
                        _FallbackContext(metadata={"workspace_id": self.workspace_id}),
                    )
                    return {
                        "success": True,
                        "response": str(result),
                        "steps": ["keyword_match"],
                        "total_steps": 1,
                        "engine": "fallback_keyword",
                    }
                except Exception as e:
                    return {"success": False, "error": str(e)}

        return {
            "success": False,
            "error": "无法处理请求：OpenHarness 不可用且 LLM 未配置",
            "engine": "none",
        }

    def _fallback_decide(self, user_input: str) -> Dict[str, Any]:
        """关键词匹配降级决策"""
        keywords = {
            "查询": "query_entities",
            "搜索": "search_graph",
            "分析": "analyze_graph",
            "工作空间": "list_workspaces",
        }
        for keyword, tool_name in keywords.items():
            if keyword in user_input:
                return {"tool_name": tool_name, "params": {"query": user_input}}
        return {"tool_name": "end_mission", "params": {}}

    async def _write_episode(self, user_input: str, response: str):
        """写入 Graphiti Episode（记忆持久化）"""
        if not self.graph_manager:
            return
        try:
            await self.graph_manager.add_episode(
                name=f"agent_loop_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                episode_body=f"用户: {user_input}\n助手: {response}",
                reference_id=self.workspace_id or "default",
            )
        except Exception as e:
            logger.debug("Graphiti episode write failed: %s", e)

    def list_tools(self) -> List[Dict]:
        """列出所有可用工具"""
        tools = self._fallback_tools
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "call_count": tool.call_count,
            }
            for tool in tools.values()
        ]


# ---------------------------------------------------------------------------
# _FallbackContext — OH 不可用时的 ToolExecutionContext 替代
# ---------------------------------------------------------------------------

class _FallbackContext:
    """OpenHarness 不可用时的 ToolExecutionContext 替代"""

    def __init__(self, metadata: Dict[str, Any] = None):
        self.cwd = Path(os.getcwd())
        self.metadata = metadata or {}
        self.hook_executor = None


# ---------------------------------------------------------------------------
# OpenHarnessIntegration — 集成管理器
# ---------------------------------------------------------------------------

class OpenHarnessIntegration:
    """OpenHarness 集成管理器

    统一管理 OpenHarness 的初始化、配置和使用。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self.agent_loop: Optional[GraphitiAgentLoop] = None
        self._initialized = True

    async def initialize(self,
                         user_role: str = "intelligence_analyst",
                         provider_config: Dict[str, Any] = None):
        try:
            self.agent_loop = GraphitiAgentLoop(
                user_role=user_role,
                opa_manager=provider_config.get("opa_manager") if provider_config else None,
                graph_manager=provider_config.get("graph_manager") if provider_config else None,
                workspace_id=provider_config.get("workspace_id", "") if provider_config else "",
                scenario_id=provider_config.get("scenario_id", "") if provider_config else "",
            )
            logger.info("OpenHarness integration initialized (OH available: %s)", OPENHARNESS_AVAILABLE)
            return True
        except Exception as e:
            logger.warning("OpenHarness integration init failed: %s", e)
            return False

    async def shutdown(self):
        self.agent_loop = None
        logger.info("OpenHarness integration shut down")
        return True

    async def run_agent(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.agent_loop:
            return {"success": False, "error": "Agent Loop 未初始化"}
        return await self.agent_loop.run(user_input, context)

    def get_status(self) -> Dict[str, Any]:
        return {
            "openharness_available": OPENHARNESS_AVAILABLE,
            "agent_loop_initialized": self.agent_loop is not None,
            "tools_count": len(self.agent_loop.list_tools()) if self.agent_loop else 0,
            "tools": self.agent_loop.list_tools() if self.agent_loop else [],
            "engine_type": "openharness_query_engine" if OPENHARNESS_AVAILABLE else "fallback",
        }


# ---------------------------------------------------------------------------
# 全局便捷函数
# ---------------------------------------------------------------------------

_integration_instance = None


def get_openharness_integration() -> OpenHarnessIntegration:
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = OpenHarnessIntegration()
    return _integration_instance


async def initialize_openharness(user_role: str = "intelligence_analyst",
                                 provider_config: Dict[str, Any] = None) -> bool:
    integration = get_openharness_integration()
    return await integration.initialize(user_role, provider_config)


async def run_agent(user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    integration = get_openharness_integration()
    return await integration.run_agent(user_input, context)


# 向后兼容：v2_adapter 模块名已弃用
OPENHARNESS_V2_AVAILABLE = OPENHARNESS_AVAILABLE
