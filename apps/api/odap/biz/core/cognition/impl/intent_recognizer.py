import logging
import re
import uuid
from typing import Dict, Any, List, Optional

from odap.infra.config_composer import get_config
from odap.biz.core.ontology.common.types import IntentType
from odap.biz.platform.roles.api.schemas import RoleType

logger = logging.getLogger(__name__)


class IntentRecognizer:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._intent_patterns = {
            IntentType.QUERY: [
                r"什么|哪个|哪里|谁|如何|怎么",
                r"查询|搜索|查找|检索",
                r"\?$",
            ],
            IntentType.ACTION: [
                r"执行|运行|启动|创建|删除",
                r"完成|处理|开始|停止",
                r"\bdo\b|\brun\b|\bexecute\b",
            ],
            IntentType.EXPLAIN: [
                r"为什么|原因|解释|说明",
                r"\bwhy\b|\bexplain\b",
            ],
            IntentType.RECOMMEND: [
                r"建议|推荐",
                r"应该|最好",
                r"\brecommend\b|\bsuggest\b",
            ],
            IntentType.NAVIGATE: [
                r"导航|查看|转到|去",
                r"打开|显示",
                r"\bnavigate\b|\bshow\b",
            ],
            IntentType.COMPARE: [
                r"比较|对比|差异",
                r"区别|不同",
                r"\bcompare\b|\bdiff\b",
            ],
            IntentType.ANALYZE: [
                r"分析|评估|统计",
                r"总结|归纳",
                r"\banalyze\b|\bevaluate\b",
            ],
        }
        self._ontology_facts: Dict[str, List[str]] = {}
        self._initialized = True

    def recognize(self, query: str, role: RoleType = RoleType.GUEST, ontology_facts: Optional[List[str]] = None) -> Dict[str, Any]:
        query_lower = query.lower()
        intent_scores = {}
        for intent_type, patterns in self._intent_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    score += 1
            intent_scores[intent_type] = score / len(patterns)

        if ontology_facts:
            for fact in ontology_facts:
                fact_lower = fact.lower()
                for word in query_lower.split():
                    if word in fact_lower:
                        for it in intent_scores:
                            intent_scores[it] += 0.05

        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        primary_intent = sorted_intents[0][0] if sorted_intents else IntentType.QUERY
        primary_confidence = min(1.0, (sorted_intents[0][1] if sorted_intents else 0.5) + 0.2)

        entities = self._extract_entities(query)
        attributes = self._extract_attributes(query)
        alternative_intents = [i[0] for i in sorted_intents[1:3] if i[1] > 0]

        if primary_confidence < 0.4:
            llm_result = self._recognize_with_llm(query, role, ontology_facts)
            if llm_result and llm_result.get("confidence", 0) > primary_confidence:
                return {
                    "intent_id": str(uuid.uuid4()),
                    "primary_intent": llm_result["primary_intent"],
                    "confidence": llm_result["confidence"],
                    "entities": llm_result.get("entities", entities),
                    "attributes": llm_result.get("attributes", attributes),
                    "alternative_intents": llm_result.get("alternative_intents", [i.value for i in alternative_intents]),
                    "role": role.value,
                }

        return {
            "intent_id": str(uuid.uuid4()),
            "primary_intent": primary_intent.value,
            "confidence": primary_confidence,
            "entities": entities,
            "attributes": attributes,
            "alternative_intents": [i.value for i in alternative_intents],
            "role": role.value,
        }

    def _recognize_with_llm(self, query, role, ontology_facts):
        try:
            import requests
            import json
            api_key = get_config("llm.api_key", "")
            base_url = get_config("llm.api_base", "https://api.openai.com/v1")
            model = get_config("llm.model", "deepseek-ai/deepseek-v4-pro")
            if not api_key:
                return None
            prompt = f"""分析以下用户查询的意图，返回JSON格式：
{{"intent": "query|action|explain|recommend|navigate|compare|analyze", "confidence": 0.0-1.0, "entities": [], "attributes": {{}}}}

用户查询：{query}
用户角色：{role.value}
已知本体事实：{ontology_facts or []}

仅返回JSON，不要其他内容。"""
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 256},
                timeout=8,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                parsed = json.loads(json_match.group())
                intent_str = parsed.get("intent", "query")
                intent_map = {
                    "query": IntentType.QUERY,
                    "action": IntentType.ACTION,
                    "explain": IntentType.EXPLAIN,
                    "recommend": IntentType.RECOMMEND,
                    "navigate": IntentType.NAVIGATE,
                    "compare": IntentType.COMPARE,
                    "analyze": IntentType.ANALYZE,
                }
                return {
                    "primary_intent": intent_map.get(intent_str, IntentType.QUERY).value,
                    "confidence": min(1.0, parsed.get("confidence", 0.5)),
                    "entities": parsed.get("entities", []),
                    "attributes": parsed.get("attributes", {}),
                    "alternative_intents": [],
                }
        except Exception:
            return None

    def _extract_entities(self, query: str) -> List[str]:
        entities = []
        patterns = [
            r"监测站?[A-Z]?", r"传感器\d+", r"[A-Z]+-?\d+传感器",
            r"目标[一二三四五六七八九十\d]+", r"目标[A-Z]?", r"target\d*",
            r"单位\d+", r"[A-Z]+连", r"[A-Z]+营",
            r"[A-Z]区", r"[A-Z]地带", r"坐标[\d,\.]+",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, query)
            entities.extend(matches)
        return list(set(entities))

    def _extract_attributes(self, query: str) -> Dict[str, Any]:
        attributes = {}
        time_patterns = [
            (r"今天", "today"), (r"昨天", "yesterday"),
            (r"上周", "last_week"), (r"本月", "this_month"), (r"最近", "recent"),
        ]
        for pattern, attr in time_patterns:
            if re.search(pattern, query):
                attributes["time"] = attr
        if "详细" in query or "完整" in query:
            attributes["detail_level"] = "high"
        elif "简要" in query or "简单" in query:
            attributes["detail_level"] = "low"
        return attributes

    def load_ontology_facts(self, ontology_id: str, facts: List[str]):
        self._ontology_facts[ontology_id] = facts
