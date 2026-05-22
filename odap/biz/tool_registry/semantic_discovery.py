import math
import logging
from typing import Dict, Any, List, Optional
from collections import Counter

logger = logging.getLogger(__name__)


class SemanticDiscovery:
    STOP_WORDS = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
                  "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
                  "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                  "have", "has", "had", "do", "does", "did", "will", "would", "could",
                  "should", "may", "might", "shall", "can", "need", "dare", "ought",
                  "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
                  "as", "into", "through", "during", "before", "after", "above", "below"}

    def discover(self, query: str, tools: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        if not tools:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return tools[:top_k]

        scored = []
        for tool in tools:
            score = self._compute_score(query_tokens, tool)
            scored.append({"tool": tool, "score": score})

        scored.sort(key=lambda x: x["score"], reverse=True)

        return [
            {
                **item["tool"],
                "relevance_score": round(item["score"], 4),
            }
            for item in scored[:top_k]
        ]

    def _tokenize(self, text: str) -> List[str]:
        tokens = []
        current = ""
        for ch in text.lower():
            if '\u4e00' <= ch <= '\u9fff':
                if current:
                    tokens.extend(current.split())
                    current = ""
                tokens.append(ch)
            elif ch.isalnum():
                current += ch
            else:
                if current:
                    tokens.extend(current.split())
                    current = ""
        if current:
            tokens.extend(current.split())

        return [t for t in tokens if t not in self.STOP_WORDS and len(t) > 0]

    def _compute_score(self, query_tokens: List[str], tool: Dict[str, Any]) -> float:
        score = 0.0
        name = tool.get("name", "").lower()
        description = tool.get("description", "").lower()
        category = tool.get("category", "").lower()
        tags = [t.lower() for t in tool.get("tags", [])]

        tool_text = f"{name} {description} {category} {' '.join(tags)}"
        tool_tokens = self._tokenize(tool_text)

        query_counter = Counter(query_tokens)
        tool_counter = Counter(tool_tokens)

        all_tokens = set(query_counter.keys()) & set(tool_counter.keys())
        if not all_tokens:
            return 0.0

        dot_product = sum(query_counter[t] * tool_counter[t] for t in all_tokens)
        query_norm = math.sqrt(sum(v ** 2 for v in query_counter.values()))
        tool_norm = math.sqrt(sum(v ** 2 for v in tool_counter.values()))

        if query_norm > 0 and tool_norm > 0:
            score = dot_product / (query_norm * tool_norm)

        for qt in query_tokens:
            if qt in name:
                score += 0.3
            if qt in category:
                score += 0.2

        return score
