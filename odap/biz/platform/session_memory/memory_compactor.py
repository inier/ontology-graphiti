import logging
from typing import List, Optional

from odap.infra.config_composer import get_config

from .context_window import ContextWindow, ChatMessage

logger = logging.getLogger(__name__)


class MemoryCompactor:
    COMPACTION_THRESHOLD = 0.7
    RECENT_KEEP_COUNT = 4

    def __init__(self, llm_client=None):
        self._llm_client = llm_client

    def should_compact(self, window: ContextWindow) -> bool:
        return window.usage_ratio > self.COMPACTION_THRESHOLD

    async def compact(self, window: ContextWindow) -> ContextWindow:
        if len(window.messages) <= self.RECENT_KEEP_COUNT:
            return window

        older_messages = window.messages[:-self.RECENT_KEEP_COUNT]
        recent_messages = window.messages[-self.RECENT_KEEP_COUNT:]

        summary = await self._summarize(older_messages, existing_summary=window.summary)

        return ContextWindow(
            max_tokens=window.max_tokens,
            system_prompt_tokens=window.system_prompt_tokens,
            messages=recent_messages,
            summary=summary,
        )

    async def _summarize(self, messages: List[ChatMessage], existing_summary: str = "") -> str:
        if self._llm_client:
            try:
                return await self._llm_summarize(messages, existing_summary)
            except Exception as e:
                logger.warning(f"MemoryCompactor: LLM summarization failed: {e}, falling back to extractive")

        return self._extractive_summarize(messages, existing_summary)

    async def _llm_summarize(self, messages: List[ChatMessage], existing_summary: str) -> str:
        conversation = "\n".join(f"[{m.role.value}]: {m.content[:200]}" for m in messages)
        prompt = f"请简洁总结以下对话的关键信息（200字以内）：\n"
        if existing_summary:
            prompt += f"已有摘要：{existing_summary}\n"
        prompt += f"新增对话：\n{conversation}"

        try:
            from odap.infra.llm.llm_service import ZhipuAIClient
            api_key = get_config('llm.api_key', '')
            if api_key and self._llm_client:
                result = await self._llm_client.complete(prompt, max_tokens=200)
                return result
        except Exception as e:
            logger.warning(f"LLM summarize error: {e}")

        return self._extractive_summarize(messages, existing_summary)

    def _extractive_summarize(self, messages: List[ChatMessage], existing_summary: str) -> str:
        key_points = []
        for m in messages:
            content = m.content.strip()
            if len(content) > 100:
                content = content[:100] + "..."
            key_points.append(f"[{m.role.value}]: {content}")

        new_summary = "\n".join(key_points[-10:])

        if existing_summary:
            return existing_summary + "\n---\n" + new_summary

        return new_summary
