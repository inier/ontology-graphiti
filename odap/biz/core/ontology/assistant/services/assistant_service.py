"""T061 AssistantService — AG-UI protocol handler for ontology assistant.

Manages AG-UI run/resume flow, tool_call dispatch, and HITL confirmation.
Returns Dict[str, Any] (AGENTS.md rule 2).
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from odap.biz.core.ontology.assistant.rules.type_inference import TypeInferenceEngine
from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
    ConstraintSuggester,
)
from odap.biz.core.ontology.assistant.services.suggestion_service import (
    SuggestionService,
)
from odap.biz.core.ontology.assistant.storage import Storage

logger = logging.getLogger(__name__)

_type_engine = TypeInferenceEngine()
_constraint_engine = ConstraintSuggester()


class AssistantService:
    """AG-UI protocol handler for ontology design assistant."""

    def __init__(self, db_path: str = None):
        self.storage = Storage(db_path=db_path) if db_path else Storage()
        self.suggestion_service = SuggestionService(db_path=db_path)

    def health_check(self) -> Dict[str, Any]:
        try:
            from odap.infra.llm import get_llm_client

            llm_available = True
        except Exception:
            llm_available = False
        return {
            "status": "available" if llm_available else "degraded",
            "llm_available": llm_available,
            "rule_engine_available": True,
            "ag_ui_protocol": "v1",
        }

    def infer_type(self, property_name: str) -> Dict[str, Any]:
        return _type_engine.infer_type(property_name)

    def suggest_constraints(self, property_name: str, data_type: str) -> Dict[str, Any]:
        return _constraint_engine.suggest(property_name, data_type)

    def create_session(
        self,
        ontology_id: str,
        user_id: str,
        context_type: str,
        context_id: str = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        session = {
            "ontology_id": ontology_id,
            "user_id": user_id,
            "context_type": context_type,
            "context_id": context_id,
            "messages": [],
            "tool_calls": [],
            "hitl_pending": False,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        return self.storage.save_session(session)

    def get_session(self, session_id: str) -> Dict[str, Any]:
        session = self.storage.get_session(session_id)
        if not session:
            return {"status": "error", "message": f"session not found: {session_id}"}
        return session

    async def run(
        self,
        ontology_id: str,
        context_type: str,
        message: str,
        context_id: str = None,
        session_id: str = None,
        user_id: str = "anonymous",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """AG-UI run flow: parse message → dispatch tool_call → HITL confirm."""
        if not session_id:
            session_result = self.create_session(
                ontology_id=ontology_id,
                user_id=user_id,
                context_type=context_type,
                context_id=context_id,
            )
            session_id = session_result.get("session_id")
        run_id = str(uuid.uuid4())
        yield {"type": "RUN_STARTED", "run_id": run_id, "session_id": session_id}
        msg_id = str(uuid.uuid4())
        yield {
            "type": "TEXT_MESSAGE_START",
            "message_id": msg_id,
            "role": "assistant",
        }
        tool_call = self._parse_natural_language(message, ontology_id, context_id, session_id)
        if tool_call.get("status") == "error":
            yield {
                "type": "TEXT_MESSAGE_CONTENT",
                "message_id": msg_id,
                "delta": f"抱歉，无法处理您的请求：{tool_call.get('message', '未知错误')}",
            }
            yield {"type": "TEXT_MESSAGE_END", "message_id": msg_id}
            yield {"type": "RUN_FINISHED", "run_id": run_id}
            return
        tool_name = tool_call.get("tool", "unknown")
        tc_id = str(uuid.uuid4())
        yield {
            "type": "TOOL_CALL_START",
            "tool_call_id": tc_id,
            "tool_name": tool_name,
        }
        args_json = json.dumps(tool_call.get("content", tool_call.get("suggestions", {})), ensure_ascii=False)
        yield {
            "type": "TOOL_CALL_ARGS",
            "tool_call_id": tc_id,
            "delta": args_json,
        }
        yield {"type": "TOOL_CALL_END", "tool_call_id": tc_id}
        # T085: For read-only analysis tools, emit a CUSTOM event with the
        # full result so the frontend can render structured visualizations.
        if tool_name in ("pattern_discovery", "completeness_check"):
            yield {
                "type": "CUSTOM",
                "custom_type": "ANALYSIS_RESULT",
                "tool_call_id": tc_id,
                "tool_name": tool_name,
                "result": tool_call,
            }
        if tool_call.get("hitl_required"):
            self.storage.update_session(session_id, hitl_pending=True)
            yield {
                "type": "TEXT_MESSAGE_CONTENT",
                "message_id": msg_id,
                "delta": tool_call.get("hitl_prompt", "请确认操作"),
            }
            yield {"type": "TEXT_MESSAGE_END", "message_id": msg_id}
            yield {
                "type": "RUN_FINISHED",
                "run_id": run_id,
                "interrupts": [
                    {
                        "type": "hitl",
                        "tool_call_id": tc_id,
                        "tool_name": tool_name,
                        "suggestion_id": tool_call.get("suggestion_id"),
                        "description": tool_call.get("hitl_prompt", "确认操作？"),
                    }
                ],
            }
        else:
            yield {
                "type": "TEXT_MESSAGE_CONTENT",
                "message_id": msg_id,
                "delta": self._build_summary_message(tool_call),
            }
            yield {"type": "TEXT_MESSAGE_END", "message_id": msg_id}
            yield {"type": "RUN_FINISHED", "run_id": run_id}

    async def resume(
        self,
        run_id: str,
        tool_call_id: str,
        response: str,
        suggestion_id: str = None,
        user_id: str = "anonymous",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """AG-UI resume flow: process HITL confirmation."""
        yield {"type": "RUN_STARTED", "run_id": run_id}
        msg_id = str(uuid.uuid4())
        yield {
            "type": "TEXT_MESSAGE_START",
            "message_id": msg_id,
            "role": "assistant",
        }
        if response == "approved" and suggestion_id:
            result = self.suggestion_service.accept_suggestion(suggestion_id, user_id=user_id)
            if result.get("status") == "accepted":
                yield {
                    "type": "TEXT_MESSAGE_CONTENT",
                    "message_id": msg_id,
                    "delta": "操作已确认并应用。",
                }
            else:
                yield {
                    "type": "TEXT_MESSAGE_CONTENT",
                    "message_id": msg_id,
                    "delta": f"确认失败：{result.get('message', '未知错误')}",
                }
        elif response == "rejected" and suggestion_id:
            self.suggestion_service.reject_suggestion(suggestion_id, user_id=user_id)
            yield {
                "type": "TEXT_MESSAGE_CONTENT",
                "message_id": msg_id,
                "delta": "操作已取消。",
            }
        else:
            yield {
                "type": "TEXT_MESSAGE_CONTENT",
                "message_id": msg_id,
                "delta": "未识别的响应。",
            }
        yield {"type": "TEXT_MESSAGE_END", "message_id": msg_id}
        yield {"type": "RUN_FINISHED", "run_id": run_id}

    def _parse_natural_language(
        self,
        message: str,
        ontology_id: str,
        context_id: str,
        session_id: str,
    ) -> Dict[str, Any]:
        """Parse natural language message and dispatch to appropriate tool_call.

        This is a rule-based parser for common patterns. In production,
        this would call LLM for intent detection.
        """
        from odap.biz.core.ontology.assistant.tools import TOOL_REGISTRY

        msg_lower = message.lower().strip()

        # T085: Pattern discovery intent — "分析模式/发现模式/pattern/analyze"
        if (
            "分析" in message
            or "模式" in message
            or "pattern" in msg_lower
            or "analyze" in msg_lower
        ):
            types_data = self._fetch_ontology_types(ontology_id)
            if types_data.get("status") == "error":
                return types_data
            return TOOL_REGISTRY["pattern_discovery"](
                ontology_id=ontology_id,
                object_types=types_data["object_types"],
                link_types=types_data["link_types"],
            )

        # T085: Completeness check intent — "完整性/检查/completeness/check"
        if (
            "完整性" in message
            or "检查" in message
            or "completeness" in msg_lower
            or "check" in msg_lower
        ):
            types_data = self._fetch_ontology_types(ontology_id)
            if types_data.get("status") == "error":
                return types_data
            return TOOL_REGISTRY["completeness_check"](
                ontology_id=ontology_id,
                object_types=types_data["object_types"],
                link_types=types_data["link_types"],
                action_types=types_data["action_types"],
            )

        if "推荐" in message or "suggest" in msg_lower:
            return TOOL_REGISTRY["suggest_properties"](
                suggestion_service=self.suggestion_service,
                ontology_id=ontology_id,
                object_type_id=context_id or "unknown",
                object_type_name="user",
                session_id=session_id,
            )
        if "属性" in message or "property" in msg_lower:
            import re

            name_match = re.search(r"[a-zA-Z_][a-zA-Z0-9_]*", message)
            prop_name = name_match.group(0) if name_match else "new_property"
            return TOOL_REGISTRY["add_property"](
                suggestion_service=self.suggestion_service,
                ontology_id=ontology_id,
                object_type_id=context_id or "unknown",
                name=prop_name,
                session_id=session_id,
            )
        if "关系" in message or "relation" in msg_lower or "link" in msg_lower:
            import re

            name_match = re.search(r"[a-zA-Z_][a-zA-Z0-9_]*", message)
            link_name = name_match.group(0) if name_match else "new_link"
            return TOOL_REGISTRY["add_link_type"](
                suggestion_service=self.suggestion_service,
                ontology_id=ontology_id,
                name=link_name,
                source_type="source_type",
                target_type="target_type",
                session_id=session_id,
            )
        if "动作" in message or "action" in msg_lower:
            import re

            name_match = re.search(r"[a-zA-Z_][a-zA-Z0-9_]*", message)
            action_name = name_match.group(0) if name_match else "new_action"
            return TOOL_REGISTRY["add_action_type"](
                suggestion_service=self.suggestion_service,
                ontology_id=ontology_id,
                name=action_name,
                target_object_type=context_id or "unknown",
                session_id=session_id,
            )
        return {
            "status": "error",
            "message": f"无法识别的操作意图: {message}",
        }

    def _fetch_ontology_types(self, ontology_id: str) -> Dict[str, Any]:
        """Fetch object_types, link_types, action_types for an ontology.

        T085: Used by pattern_discovery and completeness_check dispatch.
        Returns a dict with keys: object_types, link_types, action_types.
        On failure, returns {"status": "error", "message": ...}.
        """
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import (
                OntologyService,
            )

            svc = OntologyService()
            ot_result = svc.list_object_types(ontology_id)
            if ot_result.get("status") == "error":
                return {
                    "status": "error",
                    "message": f"fetch object_types failed: {ot_result.get('message', '')}",
                }
            lt_result = svc.list_link_types(ontology_id)
            if lt_result.get("status") == "error":
                return {
                    "status": "error",
                    "message": f"fetch link_types failed: {lt_result.get('message', '')}",
                }
            at_result = svc.list_action_types(ontology_id)
            if at_result.get("status") == "error":
                return {
                    "status": "error",
                    "message": f"fetch action_types failed: {at_result.get('message', '')}",
                }
            return {
                "object_types": ot_result.get("object_types", []),
                "link_types": lt_result.get("link_types", []),
                "action_types": at_result.get("action_types", []),
            }
        except Exception as exc:
            logger.exception("_fetch_ontology_types failed")
            return {"status": "error", "message": f"fetch ontology types failed: {exc}"}

    def _build_summary_message(self, tool_call: Dict[str, Any]) -> str:
        """Build a human-readable summary for a read-only tool_call result.

        T085: pattern_discovery and completeness_check return structured
        analysis results; this method formats them into a concise message
        for the AG-UI TEXT_MESSAGE_CONTENT event.
        """
        tool_name = tool_call.get("tool", "")
        if tool_name == "pattern_discovery":
            summary = tool_call.get("summary", {})
            attr_count = summary.get("common_attribute_count", 0)
            fk_count = summary.get("foreign_key_pattern_count", 0)
            total = summary.get("total_object_types", 0)
            return (
                f"已分析 {total} 个对象类型：发现 {attr_count} 个公共属性，"
                f"{fk_count} 个外键模式。详见分析结果。"
            )
        if tool_name == "completeness_check":
            summary = tool_call.get("summary", {})
            orphan = summary.get("orphan_count", 0)
            missing_audit = summary.get("missing_audit_count", 0)
            missing_status = summary.get("missing_status_count", 0)
            missing_desc = summary.get("missing_description_count", 0)
            total_issues = orphan + missing_audit + missing_status + missing_desc
            return (
                f"完整性检查完成，共发现 {total_issues} 个待改进项："
                f"孤立类型 {orphan}，缺失审计字段 {missing_audit}，"
                f"缺失状态字段 {missing_status}，缺失描述 {missing_desc}。"
            )
        # Default: suggest_properties and other read tools
        count = tool_call.get("count", 0)
        return f"已为您找到 {count} 条建议。"
