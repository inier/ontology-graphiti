import logging
import os
import json
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    QUERY = "query"
    ANALYSIS = "analysis"
    ACTION = "action"
    DECISION = "decision"
    UNKNOWN = "unknown"


INTENT_KEYWORD_MAP = {
    IntentType.QUERY: ["查询", "搜索", "查找", "什么", "多少", "哪个", "query", "search", "find", "what", "how many", "which"],
    IntentType.ANALYSIS: ["分析", "统计", "趋势", "对比", "比较", "analyze", "statistics", "trend", "compare", "comparison"],
    IntentType.ACTION: ["执行", "操作", "创建", "删除", "更新", "修改", "添加", "execute", "create", "delete", "update", "modify", "add", "remove"],
    IntentType.DECISION: ["决策", "推荐", "建议", "方案", "选择", "decide", "recommend", "suggest", "plan", "choose", "option"],
}


class IntentRouter:
    def __init__(self):
        self._rule_map: Dict[str, str] = {}
        self._intent_type_map: Dict[str, IntentType] = {}
        self._llm_available = False
        self._init_llm()
        self._init_default_rules()

    def _init_llm(self):
        api_key = os.environ.get("OPENAI_API_KEY", "")
        api_base = os.environ.get("OPENAI_API_BASE", "")
        if api_key and api_base:
            self._llm_available = True

    def _init_default_rules(self):
        for intent_type, keywords in INTENT_KEYWORD_MAP.items():
            for kw in keywords:
                self._intent_type_map[kw.lower()] = intent_type

    def register_rule(self, intent_keyword: str, target_role: str,
                      intent_type: IntentType = None) -> Dict[str, Any]:
        self._rule_map[intent_keyword.lower()] = target_role
        if intent_type:
            self._intent_type_map[intent_keyword.lower()] = intent_type
        return {"status": "success", "keyword": intent_keyword, "role": target_role}

    def route(self, text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        text_lower = text.lower()

        # Phase 1: Rule-based routing (exact keyword match from registered rules)
        for keyword, role in self._rule_map.items():
            if keyword in text_lower:
                intent_type = self._intent_type_map.get(keyword, IntentType.QUERY)
                return {
                    "status": "success",
                    "intent_type": intent_type.value,
                    "target_role": role,
                    "method": "rule",
                    "confidence": 0.9,
                }

        # Phase 2: Intent type classification from keyword map
        best_intent = IntentType.UNKNOWN
        best_count = 0
        for intent_type, keywords in INTENT_KEYWORD_MAP.items():
            count = sum(1 for kw in keywords if kw.lower() in text_lower)
            if count > best_count:
                best_count = count
                best_intent = intent_type

        if best_count > 0:
            role = self._intent_type_to_role(best_intent)
            confidence = min(0.5 + best_count * 0.1, 0.85)
            return {
                "status": "success",
                "intent_type": best_intent.value,
                "target_role": role,
                "method": "keyword",
                "confidence": confidence,
            }

        # Phase 3: LLM fallback for uncertain intents
        if self._llm_available:
            llm_result = self._route_with_llm(text, context)
            if llm_result:
                return llm_result

        # Phase 4: Default fallback
        return {
            "status": "success",
            "intent_type": IntentType.UNKNOWN.value,
            "target_role": "intelligence",
            "method": "default",
            "confidence": 0.3,
        }

    def _route_with_llm(self, text: str, context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        try:
            import httpx

            api_base = os.environ.get("OPENAI_API_BASE", "").rstrip("/")
            api_key = os.environ.get("OPENAI_API_KEY", "")
            model = os.environ.get("OPENAI_MODEL", "gpt-4")

            system_prompt = (
                "Classify the following user intent into one of these categories: "
                "query, analysis, action, decision. "
                "Also suggest which agent role should handle it: commander, intelligence, operations. "
                "Respond in JSON format: {\"intent_type\": \"...\", \"target_role\": \"...\", \"confidence\": 0.0-1.0}"
            )

            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 100,
                    },
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    result = json.loads(content)
                    intent_type_str = result.get("intent_type", "unknown")
                    try:
                        intent_type = IntentType(intent_type_str)
                    except ValueError:
                        intent_type = IntentType.UNKNOWN
                    return {
                        "status": "success",
                        "intent_type": intent_type.value,
                        "target_role": result.get("target_role", "intelligence"),
                        "method": "llm",
                        "confidence": result.get("confidence", 0.6),
                    }
        except Exception as e:
            logger.warning(f"LLM routing failed: {e}")
        return None

    @staticmethod
    def _intent_type_to_role(intent_type: IntentType) -> str:
        mapping = {
            IntentType.QUERY: "intelligence",
            IntentType.ANALYSIS: "intelligence",
            IntentType.ACTION: "operations",
            IntentType.DECISION: "commander",
            IntentType.UNKNOWN: "intelligence",
        }
        return mapping.get(intent_type, "intelligence")


_intent_router: Optional[IntentRouter] = None


def get_intent_router() -> IntentRouter:
    global _intent_router
    if _intent_router is None:
        _intent_router = IntentRouter()
    return _intent_router
