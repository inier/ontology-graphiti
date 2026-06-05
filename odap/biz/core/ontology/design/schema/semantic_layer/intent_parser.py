import logging
import re
import uuid
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class StructuredQuery:
    def __init__(self, intent: str, entities: List[str], filters: Dict[str, Any],
                 sort: Optional[str] = None, limit: int = 20):
        self.query_id = str(uuid.uuid4())
        self.intent = intent
        self.entities = entities
        self.filters = filters
        self.sort = sort
        self.limit = limit

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "intent": self.intent,
            "entities": self.entities,
            "filters": self.filters,
            "sort": self.sort,
            "limit": self.limit,
        }


class IntentParser:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._intent_map = {
            "query": ["什么", "哪个", "哪里", "谁", "如何", "怎么", "查询", "搜索", "查找"],
            "action": ["执行", "运行", "启动", "创建", "删除", "完成", "处理"],
            "explain": ["为什么", "原因", "解释", "说明"],
            "recommend": ["建议", "推荐", "应该", "最好"],
            "analyze": ["分析", "评估", "统计", "总结"],
            "compare": ["比较", "对比", "差异", "区别"],
        }
        self._initialized = True

    def parse(self, natural_language: str) -> StructuredQuery:
        intent = self._detect_intent(natural_language)
        entities = self._extract_entities(natural_language)
        filters = self._extract_filters(natural_language)
        sort = self._extract_sort(natural_language)
        return StructuredQuery(
            intent=intent,
            entities=entities,
            filters=filters,
            sort=sort,
        )

    def _detect_intent(self, text: str) -> str:
        text_lower = text.lower()
        best_intent = "query"
        best_score = 0
        for intent, keywords in self._intent_map.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_intent = intent
        return best_intent

    def _extract_entities(self, text: str) -> List[str]:
        entities = []
        patterns = [
            r"雷达站?[A-Z]?", r"雷达\d+", r"目标[A-Z]?",
            r"单位\d+", r"[A-Z]+连", r"[A-Z]+营",
            r"[A-Z]区", r"坐标[\d,\.]+",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            entities.extend(matches)
        return list(set(entities))

    def _extract_filters(self, text: str) -> Dict[str, Any]:
        filters = {}
        time_patterns = [(r"今天", "today"), (r"昨天", "yesterday"), (r"最近", "recent")]
        for pattern, value in time_patterns:
            if re.search(pattern, text):
                filters["time"] = value
        if "详细" in text:
            filters["detail_level"] = "high"
        elif "简要" in text:
            filters["detail_level"] = "low"
        return filters

    def _extract_sort(self, text: str) -> Optional[str]:
        if "最新" in text or "最近" in text:
            return "time_desc"
        if "重要" in text:
            return "priority_desc"
        return None
