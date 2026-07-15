"""LLM-powered Unified Chat Service.

Replaces the keyword-based NL parser with real LLM intent detection
using a tool-calling agent pattern.

Supports:
- Natural language queries over the knowledge graph
- Ontology design suggestions (properties, relationships, actions)
- Multi-turn conversation with context
- Dynamic context extraction from current ontology design state
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from odap.biz.core.assistant.plugins.ai_assistant.registry import (
    TOOL_REGISTRY,
    get_tools_for_llm,
    execute_tool_async,
    get_ontology_context as _get_ontology_context,
)
from odap.infra.config_composer import get_config

logger = logging.getLogger(__name__)


def _build_tool_result_summary(results: list) -> str:
    """Build a readable summary from raw tool execution results."""
    parts = []
    for r in results:
        data = r.get("result", {})
        if not isinstance(data, dict):
            continue

        tool = r.get("tool", "")
        if tool == "check_completeness":
            s = data.get("summary", {})
            hint = data.get("hint", "")
            if hint:
                parts.append(hint)
            else:
                parts.append(
                    f"📊 完整性分析完成：\n"
                    f"  对象类型: {s.get('total_object_types', 0)} 个\n"
                    f"  孤儿类型: {s.get('orphan_count', 0)} 个\n"
                    f"  缺失审计字段: {s.get('missing_audit_count', 0)} 个\n"
                    f"  缺少状态: {s.get('missing_status_count', 0)} 个\n"
                    f"  缺少描述: {s.get('missing_description_count', 0)} 个"
                )
        elif tool == "get_ontology_context":
            ctx = data.get("context", {})
            if ctx:
                types = ctx.get("object_types", [])
                parts.append(
                    f"📋 本体包含 {ctx.get('object_type_count', 0)} 个对象类型、"
                    f"{ctx.get('link_type_count', 0)} 个关系类型、"
                    f"{ctx.get('action_type_count', 0)} 个动作类型。"
                )
                for t in types[:5]:
                    parts.append(f"  - {t.get('name', '?')}: {', '.join(t.get('properties', [])[:5])}")
        elif tool == "suggest_properties":
            suggestions = data.get("suggestions", [])
            hint = data.get("hint", "")
            if hint:
                parts.append(hint)
            elif suggestions:
                names = [f"{s.get('name', '?')}({s.get('data_type', 'string')})" for s in suggestions]
                parts.append(f"💡 建议添加属性: {', '.join(names)}")
            else:
                parts.append("✅ 该类型属性已配置完整。")
        elif tool == "suggest_relations":
            suggestions = data.get("suggestions", [])
            hint = data.get("hint", "")
            if hint:
                parts.append(hint)
            elif suggestions:
                rels = [f"{s.get('name', '?')} → {s.get('target_type', '?')}" for s in suggestions]
                parts.append(f"🔗 建议关系 ({len(suggestions)} 条):\n  " + "\n  ".join(rels))
            else:
                parts.append("✅ 暂无明确的关系建议。")

        # ── 写操作结果 ──
        elif tool == "add_property":
            if data.get("status") == "success":
                parts.append(data.get("message", "属性已新增"))
            else:
                parts.append(f"❌ {data.get('message', '新增属性失败')}")

        elif tool == "update_property":
            if data.get("status") == "success":
                parts.append(data.get("message", "属性已更新"))
            else:
                parts.append(f"❌ {data.get('message', '更新属性失败')}")

        elif tool == "remove_property":
            if data.get("status") == "success":
                parts.append(data.get("message", "属性已删除"))
            else:
                parts.append(f"❌ {data.get('message', '删除属性失败')}")

        elif tool == "create_object_type":
            if data.get("status") == "success":
                parts.append(data.get("message", "对象类型已创建"))
            else:
                parts.append(f"❌ {data.get('message', '创建对象类型失败')}")

        elif tool == "delete_object_type":
            if data.get("status") == "success":
                parts.append(data.get("message", "对象类型已删除"))
            else:
                parts.append(f"❌ {data.get('message', '删除对象类型失败')}")

        elif tool == "create_link_type":
            if data.get("status") == "success":
                parts.append(data.get("message", "关系类型已创建"))
            else:
                parts.append(f"❌ {data.get('message', '创建关系类型失败')}")

        elif tool == "delete_link_type":
            if data.get("status") == "success":
                parts.append(data.get("message", "关系类型已删除"))
            else:
                parts.append(f"❌ {data.get('message', '删除关系类型失败')}")

        elif tool == "add_properties":
            if data.get("status") == "success":
                parts.append(data.get("message", "属性已批量新增"))
            else:
                parts.append(f"❌ {data.get('message', '批量新增属性失败')}")

    return "\n\n".join(parts) if parts else "已为您完成分析。"


SYSTEM_PROMPT = """你是 ODAP 本体驱动分析决策平台的 AI 助手。

你的能力:
1. **查询知识图谱**: 列出实体、搜索实体、查询关系、查询时序数据
2. **本体设计辅助**: 获取本体上下文、建议属性、建议关系、检查完整性
3. **本体增删改查**: 你可以**直接修改**本体设计！包括：
   - 给对象类型新增/更新/删除属性 (add_property / update_property / remove_property)
   - **批量添加属性** (add_properties) — 当用户一次要加多个属性时用这个，更高效
   - 创建/删除对象类型 (create_object_type / delete_object_type)
   - 创建/删除关系类型 (create_link_type / delete_link_type)
4. **日常问答**: 回答关于平台使用、本体设计最佳实践的问题

类型名称智能匹配:
- 用户可能用中文或英文指代类型（如「里程碑」=Milestone、「任务」=Task、「用户」=User）
- 你只需将用户原始输入作为 object_type_name 参数传入，后端会自动进行中英文别名和模糊匹配
- 上方已注入当前本体的类型列表，请参考列表中的实际类型名

工作规则:
- 用户可以用自然语言提问，如"有哪些实体""User类型少了什么属性""本体完整性怎么样"
- 当用户问"建议属性"或"还缺什么属性"时，调用 suggest_properties；问"建议关系"时，调用 suggest_relations
- **当用户要求"新增""添加""创建""删除"等操作时，直接调用对应的写操作工具执行，不要只是建议**
  - 例："帮我在里程碑类型下新增name属性" → 调用 add_property(ontology_id, "里程碑", "name", "STRING")
  - 例："给里程碑加 status、priority、due_date 三个属性" → 调用 add_properties(ontology_id, "里程碑", '[{"name":"status","data_type":"STRING"},{"name":"priority","data_type":"STRING"},{"name":"due_date","data_type":"DATETIME"}]')
  - 例："给里程碑加这些字段: {status:'STRING', priority:'STRING'}" → 调用 add_properties(ontology_id, "里程碑", '{"status":"STRING","priority":"STRING"}')
  - 例："创建一个用户类型" → 调用 create_object_type(ontology_id, "用户")
  - 例："删除User类型" → 调用 delete_object_type(ontology_id, "User")
  - 例："建立User和Order的关系" → 调用 create_link_type(ontology_id, "has_order", "User", "Order")
- **当用户一次输入多个字段/属性/JSON时，使用 add_properties 批量写入，不要逐个调用 add_property**
- data_type 可选值: STRING, INTEGER, FLOAT, BOOLEAN, DATETIME, TEXT
- cardinality 可选值: ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY
- 返回清晰、结构化的回答，中文优先，包含具体的类型名和属性名
- 如果用户问的问题需要查询数据，优先调用查询工具而不是猜测
- **写操作执行后，明确告诉用户操作是否成功，以及具体做了什么**
"""


class ChatService:
    """LLM-powered unified chat service with tool calling."""

    def __init__(self):
        self._llm = None

    @property
    def llm(self):
        """Lazy-init LLM client."""
        if self._llm is None:
            try:
                from odap.infra.llm.llm_service import ZhipuAIClient
                from graphiti_core.llm_client.config import LLMConfig
                import os as _os
                # 环境变量优先：get_config 可能返回加密后无法解密的密文
                api_key = _os.environ.get("OPENAI_API_KEY", "") or get_config("llm.api_key", "")
                base_url = _os.environ.get("OPENAI_API_BASE", "") or get_config("llm.api_base", "https://open.bigmodel.cn/api/paas/v4")
                model = _os.environ.get("OPENAI_MODEL", "") or get_config("llm.model", "glm-4-flash")

                if api_key:
                    config = LLMConfig(
                        api_key=api_key,
                        base_url=base_url,
                        model=model,
                    )
                    self._llm = ZhipuAIClient(config=config)
                else:
                    logger.warning("No LLM API key configured, using rule-based fallback")
                    self._llm = None
            except Exception as e:
                logger.warning("LLM init failed: %s, using rule-based fallback", e)
                self._llm = None
        return self._llm

    async def chat(
        self,
        message: str,
        ontology_id: str = None,
        workspace_id: str = "default",
        session_id: str = None,
        user_id: str = "anonymous",
        context: Dict[str, Any] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Main chat entry point - streaming SSE response.

        Args:
            message: User's natural language message
            ontology_id: Current ontology being designed (for context)
            workspace_id: Current workspace
            session_id: Conversation session ID
            user_id: User identifier
            context: Additional context (selected object type, current page, etc.)
        """
        run_id = str(uuid.uuid4())
        if not session_id:
            session_id = f"sess-{uuid.uuid4().hex[:12]}"

        yield {"type": "RUN_STARTED", "run_id": run_id, "session_id": session_id}

        msg_id = str(uuid.uuid4())
        yield {"type": "TEXT_MESSAGE_START", "message_id": msg_id, "role": "assistant"}

        # Build context string
        context_str = ""
        if ontology_id:
            context_str += f"\n当前本体ID: {ontology_id}"
        if workspace_id and workspace_id != "default":
            context_str += f"\n工作空间: {workspace_id}"
        if context:
            if context.get("object_type"):
                context_str += f"\n当前选中的对象类型: {context['object_type']}"
            if context.get("page"):
                context_str += f"\n当前页面: {context['page']}"
            if context.get("selected_types"):
                context_str += f"\n已选择的对象类型: {', '.join(context['selected_types'][:5])}"

        try:
            if self.llm:
                async for event in self._llm_chat(message, context_str, ontology_id, workspace_id):
                    yield event
            else:
                async for event in self._rule_based_chat(message, context_str, ontology_id, workspace_id, context):
                    yield event
        except Exception as e:
            logger.exception("Chat failed")
            yield {
                "type": "TEXT_MESSAGE_CONTENT",
                "message_id": msg_id,
                "delta": f"抱歉，处理您的请求时出现错误：{e}",
            }

        yield {"type": "TEXT_MESSAGE_END", "message_id": msg_id}
        yield {"type": "RUN_FINISHED", "run_id": run_id}

    async def _llm_chat(
        self, message: str, context_str: str,
        ontology_id: str, workspace_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """LLM-powered chat with function calling."""
        tools = get_tools_for_llm()

        # ── 自动注入本体上下文，让 LLM 知道当前本体有哪些类型 ──
        ontology_context_str = ""
        if ontology_id:
            try:
                ctx_result = _get_ontology_context(ontology_id)
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

                    ontology_context_str = (
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
                logger.warning("Auto-inject ontology context failed: %s", e)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + ontology_context_str},
            {"role": "user", "content": f"用户问题: {message}\n{context_str}".strip()},
        ]

        try:
            import httpx
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Step 1: Get LLM response with tool calls
                response = await client.post(
                    f"{self.llm.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.llm.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.llm.model,
                        "messages": messages,
                        "tools": tools,
                        "temperature": 0.3,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                choice = data.get("choices", [{}])[0]
                llm_message = choice.get("message", {})
                tool_calls = llm_message.get("tool_calls", [])

                if tool_calls:
                    # Execute tool calls
                    results = []
                    for tc in tool_calls:
                        func = tc.get("function", {})
                        tool_name = func.get("name", "")
                        try:
                            args = json.loads(func.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            args = {}

                        # Inject ontology_id and workspace_id
                        args.setdefault("ontology_id", ontology_id)
                        args.setdefault("workspace_id", workspace_id)

                        yield {
                            "type": "TOOL_CALL_START",
                            "tool_call_id": tc.get("id", str(uuid.uuid4())),
                            "tool_name": tool_name,
                        }

                        result = await execute_tool_async(tool_name, args)
                        results.append({"tool": tool_name, "result": result})

                        yield {
                            "type": "TOOL_CALL_END",
                            "tool_call_id": tc.get("id", ""),
                            "tool_name": tool_name,
                        }

                        # 写操作成功后，通知前端刷新本体设计器
                        if isinstance(result, dict) and result.get("_ontology_changed"):
                            yield {
                                "type": "CUSTOM",
                                "custom_type": "ONTOLOGY_CHANGED",
                                "tool_name": tool_name,
                                "action": result.get("action", tool_name),
                                "message": result.get("message", "本体已更新"),
                            }

                    # Step 2: Get LLM summary of tool results
                    summary_prompt = f"""用户问题: {message}
工具执行结果:
{json.dumps(results, ensure_ascii=False, indent=2)}

请用中文简洁地回答用户的问题，引用工具返回的数据。"""

                    summary_resp = await client.post(
                        f"{self.llm.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.llm.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.llm.model,
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": summary_prompt},
                            ],
                            "temperature": 0.5,
                            "stream": False,
                        },
                    )
                    summary_resp.raise_for_status()
                    summary_data = summary_resp.json()
                    summary_text = (
                        summary_data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "已为您完成分析。")
                    )

                    # Also emit structured results for analysis tools
                    for r in results:
                        if r["tool"] in ("check_completeness",):
                            yield {
                                "type": "CUSTOM",
                                "custom_type": "ANALYSIS_RESULT",
                                "tool_name": r["tool"],
                                "result": r["result"],
                            }

                    # Generate a useful summary if LLM returned something too short
                    if len(summary_text.strip()) < 20:
                        summary_text = _build_tool_result_summary(results)

                    yield {
                        "type": "TEXT_MESSAGE_CONTENT",
                        "message_id": str(uuid.uuid4()),
                        "delta": summary_text,
                    }
                else:
                    # Direct text response
                    content = llm_message.get("content", "已收到您的消息。")
                    yield {
                        "type": "TEXT_MESSAGE_CONTENT",
                        "message_id": str(uuid.uuid4()),
                        "delta": content,
                    }

        except Exception as e:
            logger.warning("LLM chat failed, falling back to rule-based: %s", e)
            async for event in self._rule_based_chat(message, context_str, ontology_id, workspace_id):
                yield event

    async def _rule_based_chat(
        self, message: str, context_str: str,
        ontology_id: str, workspace_id: str,
        context: Dict[str, Any] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Rule-based fallback when LLM is unavailable."""
        msg_lower = message.lower().strip()

        # Helper: extract object type from message (e.g., "User类型还缺少哪些属性" → "User")
        def _extract_obj_type(text: str) -> str | None:
            import re
            m = re.search(r'([A-Za-z\u4e00-\u9fa5]+)\s*类型', text)
            return m.group(1) if m else None

        # Determine intent from keywords
        intent = self._classify_intent(message, msg_lower)

        if intent == "query_entities":
            yield {"type": "TEXT_MESSAGE_CONTENT",
                   "message_id": str(uuid.uuid4()),
                   "delta": "正在查询知识图谱实体..."}
            result = await execute_tool_async("list_entities",
                                  {"workspace_id": workspace_id, "limit": 10})
            if result["status"] == "success":
                count = result.get("count", 0)
                rows = result.get("rows", [])
                summary = f"找到 {count} 个实体。\n"
                for r in rows[:10]:
                    summary += f"  - {r}\n" if isinstance(r, str) else f"  - {json.dumps(r, ensure_ascii=False)[:100]}\n"
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": summary[:1500]}
            else:
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": f"查询失败: {result.get('message', '')}"}

        elif intent == "search":
            search_term = self._extract_search_term(message)
            yield {"type": "TEXT_MESSAGE_CONTENT",
                   "message_id": str(uuid.uuid4()),
                   "delta": f"正在搜索「{search_term}」..."}
            result = await execute_tool_async("search_entities",
                                  {"query": search_term, "workspace_id": workspace_id, "limit": 10})
            if result["status"] == "success":
                count = result.get("count", 0)
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": f"搜索「{search_term}」: 找到 {count} 个结果。"}

        elif intent == "design_context" and ontology_id:
            result = await execute_tool_async("get_ontology_context", {"ontology_id": ontology_id})
            if result["status"] == "success":
                ctx = result.get("context", {})
                summary = (
                    f"当前本体包含 {ctx.get('object_type_count', 0)} 个对象类型、"
                    f"{ctx.get('link_type_count', 0)} 个关系类型、"
                    f"{ctx.get('action_type_count', 0)} 个动作类型。"
                )
                types = ctx.get("object_types", [])
                if types:
                    summary += "\n\n对象类型:"
                    for t in types[:10]:
                        props = ", ".join(t.get("properties", [])[:5])
                        summary += f"\n  - {t['name']}: [{props}]"
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": summary[:1500]}

        elif intent == "completeness" and ontology_id:
            result = await execute_tool_async("check_completeness", {"ontology_id": ontology_id})
            yield {
                "type": "CUSTOM",
                "custom_type": "ANALYSIS_RESULT",
                "tool_name": "completeness_check",
                "result": result,
            }
            if result.get("status") == "success":
                summary = result.get("summary", {})
                hint = result.get("hint", "")
                if hint:
                    yield {"type": "TEXT_MESSAGE_CONTENT",
                           "message_id": str(uuid.uuid4()),
                           "delta": hint}
                else:
                    yield {"type": "TEXT_MESSAGE_CONTENT",
                           "message_id": str(uuid.uuid4()),
                           "delta": f"完整性检查: 孤儿类型{summary.get('orphan_count',0)}个, "
                                    f"缺失审计字段{summary.get('missing_audit_count',0)}个, "
                                    f"缺失状态{summary.get('missing_status_count',0)}个, "
                                    f"缺失描述{summary.get('missing_description_count',0)}个。"}

        elif intent == "suggest_properties" and ontology_id:
            obj_type = (context or {}).get("object_type") or _extract_obj_type(message)
            if not obj_type:
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": "请指定要分析的对象类型，例如「User类型还缺少哪些属性」。"}
            else:
                result = await execute_tool_async("suggest_properties",
                                      {"ontology_id": ontology_id, "object_type_name": obj_type})
                if result.get("status") in ("success", "ok"):
                    suggestions = result.get("suggestions", [])
                    hint = result.get("hint", "")
                    if suggestions:
                        summary = f"建议为「{obj_type}」添加以下属性:\n"
                        for s in suggestions[:10]:
                            name = s.get('name', s) if isinstance(s, dict) else s
                            dtype = s.get('data_type', 'STRING') if isinstance(s, dict) else 'STRING'
                            summary += f"  - {name} ({dtype})\n"
                    elif hint:
                        summary = hint
                    else:
                        summary = "  ✅ 该类型的常用属性已配置完整。\n"
                    yield {"type": "TEXT_MESSAGE_CONTENT",
                           "message_id": str(uuid.uuid4()),
                           "delta": summary}
                else:
                    yield {"type": "TEXT_MESSAGE_CONTENT",
                           "message_id": str(uuid.uuid4()),
                           "delta": f"属性建议失败: {result.get('message', '未知错误')}"}

        elif intent == "suggest_relations" and ontology_id:
            obj_type = (context or {}).get("object_type") or _extract_obj_type(message)
            if not obj_type:
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": "请指定要分析的对象类型，例如「User需要添加哪些关系」。"}
            else:
                result = await execute_tool_async("suggest_relations",
                                      {"ontology_id": ontology_id, "object_type_name": obj_type})
                if result.get("status") == "success":
                    suggestions = result.get("suggestions", [])
                    hint = result.get("hint", "")
                    if suggestions:
                        summary = f"建议为「{obj_type}」添加以下关系:\n"
                        for s in suggestions[:10]:
                            if isinstance(s, dict):
                                summary += f"  - {s.get('name')}: {s.get('source_type')} → {s.get('target_type')}\n"
                    elif hint:
                        summary = hint
                    else:
                        summary = "  ✅ 暂无明确的关系建议。\n"
                    yield {"type": "TEXT_MESSAGE_CONTENT",
                           "message_id": str(uuid.uuid4()),
                           "delta": summary[:1500]}
                else:
                    yield {"type": "TEXT_MESSAGE_CONTENT",
                           "message_id": str(uuid.uuid4()),
                           "delta": f"关系建议失败: {result.get('message', '未知错误')}"}

        elif intent == "query_relations" and ontology_id:
            yield {"type": "TEXT_MESSAGE_CONTENT",
                   "message_id": str(uuid.uuid4()),
                   "delta": "正在查询关系数据..."}
            result = await execute_tool_async("query_relations", {"workspace_id": workspace_id, "limit": 10})
            if result["status"] == "success":
                count = result.get("count", 0)
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": f"找到 {count} 条关系。"}

        # ── 写操作：规则回退模式 ──
        elif intent == "add_properties" and ontology_id:
            import re
            import json as json_mod

            # 提取类型名
            type_match = re.search(r'([A-Za-z\u4e00-\u9fa5]+)\s*(?:类型|对象)', message)
            obj_type = type_match.group(1) if type_match else (context or {}).get("object_type")

            # 提取 JSON（优先）
            json_match = re.search(r'(\{.*\}|\[.*\])', message, re.DOTALL)
            if json_match:
                props_json = json_match.group(1)
            else:
                # 尝试从消息中提取多个字段名（如 "加 status priority due_date"）
                field_candidates = re.findall(r'[A-Za-z_]\w*', message)
                fields = [f for f in field_candidates
                          if len(f) > 1 and f.lower() not in
                          ("新增", "添加", "属性", "字段", "类型", "对象",
                           "add", "create", "property", "field", "type")]
                if len(fields) >= 2:
                    props_json = json_mod.dumps({f: "STRING" for f in fields})
                else:
                    props_json = None

            if not obj_type or not props_json:
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": "请明确指定类型名和属性列表，例如「给里程碑加 status, priority, due_date 三个属性」"}
            else:
                result = await execute_tool_async("add_properties", {
                    "ontology_id": ontology_id,
                    "object_type_name": obj_type,
                    "properties": props_json,
                })
                if result.get("_ontology_changed"):
                    yield {"type": "CUSTOM", "custom_type": "ONTOLOGY_CHANGED",
                           "action": "add_properties", "message": result.get("message", "")}
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": result.get("message", "操作完成")}

        elif intent == "add_property" and ontology_id:
            import re
            # 提取类型名和属性名
            type_match = re.search(r'([A-Za-z\u4e00-\u9fa5]+)\s*(?:类型|对象)', message)
            prop_match = re.search(r'(?:新增|添加|增加)\s*(\w+)\s*(?:属性|字段)', message)
            if not prop_match:
                prop_match = re.search(r'(\w+)\s*(?:属性|字段)', message)

            obj_type = type_match.group(1) if type_match else (context or {}).get("object_type")
            prop_name = prop_match.group(1) if prop_match else None

            if not obj_type or not prop_name:
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": "请明确指定类型名和属性名，例如「在里程碑类型下新增name属性」"}
            else:
                result = await execute_tool_async("add_property", {
                    "ontology_id": ontology_id,
                    "object_type_name": obj_type,
                    "property_name": prop_name,
                    "data_type": "STRING",
                })
                if result.get("_ontology_changed"):
                    yield {"type": "CUSTOM", "custom_type": "ONTOLOGY_CHANGED",
                           "action": "add_property", "message": result.get("message", "")}
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": result.get("message", result.get("message", "操作完成"))}

        elif intent == "remove_property" and ontology_id:
            import re
            type_match = re.search(r'([A-Za-z\u4e00-\u9fa5]+)\s*(?:类型|对象)', message)
            prop_match = re.search(r'(?:删除|移除|去掉)\s*(\w+)\s*(?:属性|字段)', message)
            obj_type = type_match.group(1) if type_match else (context or {}).get("object_type")
            prop_name = prop_match.group(1) if prop_match else None

            if not obj_type or not prop_name:
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": "请明确指定类型名和属性名，例如「删除里程碑类型的name属性」"}
            else:
                result = await execute_tool_async("remove_property", {
                    "ontology_id": ontology_id,
                    "object_type_name": obj_type,
                    "property_name": prop_name,
                })
                if result.get("_ontology_changed"):
                    yield {"type": "CUSTOM", "custom_type": "ONTOLOGY_CHANGED",
                           "action": "remove_property", "message": result.get("message", "")}
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": result.get("message", "操作完成")}

        elif intent == "create_object_type" and ontology_id:
            import re
            name_match = re.search(r'(?:创建|建一个|新增)\s*(?:一个\s*)?([A-Za-z\u4e00-\u9fa5]+)\s*(?:类型|对象|object)', message)
            type_name = name_match.group(1) if name_match else None

            if not type_name:
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": "请指定要创建的类型名，例如「创建一个用户类型」"}
            else:
                result = await execute_tool_async("create_object_type", {
                    "ontology_id": ontology_id,
                    "name": type_name,
                    "description": f"AI助手创建的{type_name}类型",
                })
                if result.get("_ontology_changed"):
                    yield {"type": "CUSTOM", "custom_type": "ONTOLOGY_CHANGED",
                           "action": "create_object_type", "message": result.get("message", "")}
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": result.get("message", "操作完成")}

        elif intent == "delete_object_type" and ontology_id:
            import re
            name_match = re.search(r'(?:删除|移除)\s*([A-Za-z\u4e00-\u9fa5]+)\s*(?:类型|对象)', message)
            type_name = name_match.group(1) if name_match else None

            if not type_name:
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": "请指定要删除的类型名"}
            else:
                result = await execute_tool_async("delete_object_type", {
                    "ontology_id": ontology_id,
                    "object_type_name": type_name,
                })
                if result.get("_ontology_changed"):
                    yield {"type": "CUSTOM", "custom_type": "ONTOLOGY_CHANGED",
                           "action": "delete_object_type", "message": result.get("message", "")}
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": result.get("message", "操作完成")}

        elif intent == "create_link" and ontology_id:
            import re
            # 尝试提取两个类型名
            names = re.findall(r'([A-Za-z\u4e00-\u9fa5]+)\s*(?:类型|对象)?', message)
            names = [n for n in names if n not in ("类型", "对象", "关系", "关联")]
            if len(names) >= 2:
                src, tgt = names[0], names[1]
                link_name = f"has_{tgt.lower()}"
                result = await execute_tool_async("create_link_type", {
                    "ontology_id": ontology_id,
                    "name": link_name, "source_type": src, "target_type": tgt,
                })
                if result.get("_ontology_changed"):
                    yield {"type": "CUSTOM", "custom_type": "ONTOLOGY_CHANGED",
                           "action": "create_link_type", "message": result.get("message", "")}
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": result.get("message", "操作完成")}
            else:
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": "请指定两个类型名，例如「建立User和Order的关系」"}

        elif intent == "delete_link" and ontology_id:
            import re
            name_match = re.search(r'(?:删除|移除)\s*(\w+)\s*(?:关系|关联)', message)
            link_name = name_match.group(1) if name_match else None
            if not link_name:
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": "请指定要删除的关系名"}
            else:
                result = await execute_tool_async("delete_link_type", {
                    "ontology_id": ontology_id, "link_name": link_name,
                })
                if result.get("_ontology_changed"):
                    yield {"type": "CUSTOM", "custom_type": "ONTOLOGY_CHANGED",
                           "action": "delete_link_type", "message": result.get("message", "")}
                yield {"type": "TEXT_MESSAGE_CONTENT",
                       "message_id": str(uuid.uuid4()),
                       "delta": result.get("message", "操作完成")}

        elif intent == "update_property" and ontology_id:
            yield {"type": "TEXT_MESSAGE_CONTENT",
                   "message_id": str(uuid.uuid4()),
                   "delta": "更新属性功能正在完善中。您可以在本体设计器中手动修改属性，或用自然语言描述具体需求。"}

        elif intent == "help":
            help_text = (
                "我是 ODAP AI 助手，可以帮助您:\n\n"
                "📊 **查询数据**\n"
                "- 「有哪些实体」→ 列出所有实体\n"
                "- 「搜索 XXX」→ 按关键词搜索\n"
                "- 「查询关系」→ 查看实体间的关系\n\n"
                "🔧 **本体设计**(需要先选择本体)\n"
                "- 「本体概况」→ 查看当前设计状态\n"
                "- 「完整性检查」→ 检查设计完整度\n"
                "- 「建议属性」→ 推荐缺失的属性\n"
                "- 「建议关系」→ 推荐可能的关系\n\n"
                "💡 **提示**: 您可以用自然语言随时提问！"
            )
            yield {"type": "TEXT_MESSAGE_CONTENT",
                   "message_id": str(uuid.uuid4()),
                   "delta": help_text}

        else:
            # Generic response
            yield {"type": "TEXT_MESSAGE_CONTENT",
                   "message_id": str(uuid.uuid4()),
                   "delta": (
                       "我理解您的问题。当前我可以帮助您：\n\n"
                       "1. **查询数据**: 列出/搜索实体，查询关系\n"
                       "2. **本体设计**: 检查完整性、建议属性/关系\n"
                       "3. **设计建议**: 分析当前本体状态并给出优化建议\n\n"
                       f"{'⚠️ 当前未选择本体，部分功能受限。请先打开本体设计页面。' if not ontology_id else ''}\n\n"
                       "请用更具体的自然语言描述您的需求，例如：\n"
                       "- 「有哪些实体」\n"
                       "- 「User类型还少了哪些属性」\n"
                       "- 「帮我检查一下本体完整性」"
                   )}

    def _classify_intent(self, message: str, msg_lower: str) -> str:
        """Classify user intent from message content."""
        # ── 写操作意图（优先级最高）──
        if any(kw in message for kw in ["新增", "添加", "增加", "创建", "建一个", "create", "add"]):
            if any(kw in message for kw in ["属性", "字段", "property", "field"]):
                # 检测批量写入：包含 JSON 或多个逗号/顿号分隔的字段
                import re
                if "{" in message or "[" in message:
                    return "add_properties"
                # 检测多个字段名（如 "status, priority, due_date"）
                field_candidates = re.findall(r'[A-Za-z_]\w*', message)
                field_like = [f for f in field_candidates
                              if len(f) > 1 and f.lower() not in
                              ("新增", "添加", "属性", "字段", "类型", "对象",
                               "add", "create", "property", "field", "type")]
                if len(field_like) >= 3:
                    return "add_properties"
                return "add_property"
            if any(kw in message for kw in ["关系", "关联", "连接", "link", "relation"]):
                return "create_link"
            if any(kw in message for kw in ["类型", "对象", "type", "object"]):
                return "create_object_type"

        if any(kw in message for kw in ["删除", "移除", "去掉", "remove", "delete"]):
            if any(kw in message for kw in ["属性", "字段", "property", "field"]):
                return "remove_property"
            if any(kw in message for kw in ["关系", "关联", "link", "relation"]):
                return "delete_link"
            if any(kw in message for kw in ["类型", "对象", "type", "object"]):
                return "delete_object_type"

        if any(kw in message for kw in ["修改", "更新", "改为", "改成", "update", "change"]):
            if any(kw in message for kw in ["属性", "字段", "property", "field"]):
                return "update_property"

        # ── 查询意图 ──
        if any(kw in message for kw in ["有哪些", "列出", "显示", "查询", "查找"]):
            if any(kw in message for kw in ["实体", "entity", "类型", "type", "有哪些"]):
                return "query_entities"
            if any(kw in message for kw in ["关系", "relation", "连接", "link"]):
                return "query_relations"
            return "query_entities"

        if any(kw in msg_lower for kw in ["搜索", "search", "查找", "find"]):
            return "search"

        # Design intents
        if any(kw in message for kw in ["完整性", "检查", "completeness", "check"]):
            return "completeness"

        if any(kw in message for kw in ["建议", "推荐", "缺少", "缺失", "少了", "suggest", "recommend"]):
            if any(kw in message for kw in ["属性", "字段", "property", "field"]):
                return "suggest_properties"
            if any(kw in message for kw in ["关系", "relation", "link", "关联"]):
                return "suggest_relations"
            return "suggest_properties"

        if any(kw in message for kw in ["概况", "概览", "状态", "当前", "现在", "overview", "context"]):
            return "design_context"

        if any(kw in message for kw in ["关系", "关联", "连接"]):
            return "query_relations"

        # Help
        if any(kw in message for kw in ["帮助", "help", "功能", "能做什么", "可以做什么"]):
            return "help"

        return "unknown"

    def _extract_search_term(self, message: str) -> str:
        """Extract search term from message."""
        import re
        for pattern in [r'搜索["「](.+?)["」]', r'搜索(.+?)(?:$|，|。|,|\.)',
                       r'查找["「](.+?)["」]', r'查找(.+?)(?:$|，|。|,|\.)',
                       r'["「](.+?)["」]']:
            match = re.search(pattern, message)
            if match:
                return match.group(1).strip()
        return message[:30]
