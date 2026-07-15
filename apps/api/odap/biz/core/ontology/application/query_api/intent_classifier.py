"""
IntentClassifier — 自然语言查询意图分类器。

负责将 NL 查询分类为 4 类：
- STRUCTURED   走 QueryService（结构化数据）
- UNSTRUCTURED 走 semantic_retriever（非结构化数据/向量）
- HYBRID       双路并行 + 结果合并
- ACTION       调本体应用 skill

分级策略：
1. 规则匹配（关键词启发式）— 无依赖、零延迟
2. LLM 分类（如可用）— 通过环境变量 / 配置开关启用
3. 失败降级 — 退回 STRUCTURED 路径

设计原则：
- 不依赖具体 LLM SDK，通过注入 provider 实现
- 规则模式开箱即用
"""
import logging
import re
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class QueryIntent(str, Enum):
    STRUCTURED = "structured"
    UNSTRUCTURED = "unstructured"
    HYBRID = "hybrid"
    ACTION = "action"
    UNKNOWN = "unknown"


_RULES: list = [
    (QueryIntent.HYBRID, re.compile(
        r"(?:\s|.+)(?:和|与|以及)\s*(?:它的|他们的|相关的|对应的)?.{0,20}(?:文档|资料|实体|记录|信息|报告|类型)",
        re.IGNORECASE,
    )),
    (QueryIntent.ACTION, re.compile(
        r"(执行|触发|创建会话|新建session|启动演练|运行|发起|执行动作|创建function|注册function)",
        re.IGNORECASE,
    )),
    (QueryIntent.UNSTRUCTURED, re.compile(
        r"(文档|资料|内容|文本|关键词|相似|搜索|关于.*的|介绍|描述|含义|什么是|具体意思|说明|白皮书|报告|wiki|文章)",
        re.IGNORECASE,
    )),
]


class IntentClassifier:
    """NL 意图分类器。"""

    def __init__(self, llm_provider: Optional[Callable[[str], str]] = None) -> None:
        self._llm_provider = llm_provider

    def classify(
        self,
        query: str,
        hints: Optional[dict] = None,
    ) -> QueryIntent:
        """主入口：先规则，后 LLM，最后降级。"""
        if not query or not query.strip():
            return QueryIntent.UNKNOWN

        hint = (hints or {}).get("force_intent")
        if hint:
            try:
                return QueryIntent(hint)
            except ValueError:
                pass

        rule_intent = self._rule_classify(query)
        if rule_intent is not None:
            return rule_intent

        if self._llm_provider is not None:
            try:
                llm_intent = self._llm_classify(query)
                if llm_intent is not None:
                    return llm_intent
            except Exception as e:
                logger.warning("LLM intent classification failed, falling back: %s", e)

        return QueryIntent.STRUCTURED

    def _rule_classify(self, query: str) -> Optional[QueryIntent]:
        for intent, pattern in _RULES:
            if pattern.search(query):
                return intent
        return None

    def _llm_classify(self, query: str) -> Optional[QueryIntent]:
        if not self._llm_provider:
            return None
        prompt = (
            "Classify the following user query into one of: "
            "structured, unstructured, hybrid, action.\n"
            f"Query: {query}\nAnswer with one word only."
        )
        result = self._llm_provider(prompt).strip().lower()
        try:
            return QueryIntent(result)
        except ValueError:
            return None


__all__ = ["IntentClassifier", "QueryIntent"]
