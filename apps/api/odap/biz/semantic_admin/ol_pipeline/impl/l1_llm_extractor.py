"""L1 术语抽取 —— LLM 版（替代 N-gram 字滑窗）。

设计动机（ADR-079）：
  NgramTermExtractor 对字序列做 (2~4)-gram 滑窗，把"任意子串"当候选，
  噪声是 O(n²) 组合爆炸（"的结义兄"/"备的结义"/"羽和张"），规则黑名单追不上。

  正确手段：复用 006 Hyper-Extract 的 LLM 抽取能力（HEAdapter.parse），
  LLM 天然理解词边界，配合其 _CUSTOM_NODE_PROMPT（禁止介词/连词开头、
  动词短语、截断片段）+ _post_validate_entities（长度<2 过滤 + 幻觉标记），
  从源头消除碎片噪声。

错误策略：
  LLM 不可用（hyperextract 未安装 / 无 API key / 调用异常）时直接抛出
  RuntimeError，不做静默降级 —— 由 PipelineService 统一捕获并标记 run 失败，
  保证抽取质量不被静默劣化。

依赖：packages/hyper-extract（006 HEAdapter），零新增第三方依赖。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class LlmTermExtractor:
    """LLM 驱动的 L1 抽取器（默认实现）。

    满足 Protocol L1TermExtractor：
        def extract(self, *, text, extra_docs, workspace_id, ontology_id, stopwords, config)

    内部调用 006 HEAdapter.parse()（LLM 抽取），将 entities 转为 RawToken 格式。
    LLM 不可用或失败时抛 RuntimeError，由调用方（PipelineService）标记 run 失败。
    """

    def __init__(self) -> None:
        self._adapter = None  # 延迟初始化，避免 import 时加载 hyperextract
        self._adapter_tried = False

    # ------------------------------------------------------------------
    # Public API (Protocol 契约)
    # ------------------------------------------------------------------
    def extract(
        self,
        *,
        text: str,
        extra_docs: Optional[List[str]] = None,
        workspace_id: Optional[str] = None,
        ontology_id: Optional[str] = None,
        stopwords: Optional[set] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        cfg = config or {}
        all_texts: List[str] = [t for t in ([text or ""] + list(extra_docs or [])) if t and t.strip()]

        if not all_texts:
            return []

        adapter = self._get_adapter()
        if adapter is None:
            raise RuntimeError(
                "L1 LLM 抽取不可用：hyperextract 未安装或 HEAdapter 初始化失败"
            )

        # 合并所有文本喂给 LLM（HEAdapter.parse 单次处理一段文本）
        combined = "\n".join(all_texts)
        # 限制输入长度，避免超长文本导致 LLM 超时/超 token
        max_input = int(cfg.get("max_input_chars", 8000))
        if len(combined) > max_input:
            combined = combined[:max_input]

        parsed = adapter.parse(combined)
        if not parsed:
            raise RuntimeError("L1 LLM 抽取返回空结果")

        tokens = self._entities_to_tokens(parsed.get("entities", []))
        if not tokens:
            raise RuntimeError("L1 LLM 抽取未产生任何有效实体")

        # 标记来源
        for tok in tokens:
            tok["provenance"]["tokenizer"] = "llm_he"
            tok["provenance"]["extractor"] = "LlmTermExtractor"
            if workspace_id:
                tok["provenance"]["workspace_id"] = workspace_id
            if ontology_id:
                tok["provenance"]["ontology_id"] = ontology_id

        max_candidates = int(cfg.get("max_candidates", 1000))
        return tokens[:max_candidates]

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _get_adapter(self):
        """延迟初始化 HEAdapter（首次调用才 import hyperextract）。"""
        if self._adapter_tried:
            return self._adapter
        self._adapter_tried = True
        try:
            from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
            adapter = HEAdapter()
            if not adapter.is_available():
                logger.error("hyperextract 未安装，HEAdapter 不可用")
                self._adapter = None
            else:
                self._adapter = adapter
        except Exception as e:  # noqa: BLE001
            logger.error("HEAdapter 初始化失败: %s", e)
            self._adapter = None
        return self._adapter

    @staticmethod
    def _entities_to_tokens(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将 HEAdapter 产出的 entities 转成 L1 RawToken 格式。

        entity: {name, display_name, type, description, properties, possible_hallucination?}
        RawToken: {surface, frequency, confidence, source_text, provenance}
        """
        tokens: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        for e in entities:
            if not isinstance(e, dict):
                continue
            name = str(e.get("name") or "").strip()
            if not name or len(name) < 2:
                continue
            if name in seen:
                continue
            seen.add(name)

            # 幻觉实体（LLM 编造、不在原文中的）降低置信度
            hallucinated = bool(e.get("possible_hallucination"))
            confidence = 0.85 if not hallucinated else 0.4

            tokens.append({
                "surface": name,
                "frequency": 1,
                "confidence": confidence,
                "source_text": str(e.get("description") or ""),
                "provenance": {
                    "sample_contexts": [str(e.get("description") or "")],
                    "entity_type": str(e.get("type") or ""),
                    "possible_hallucination": hallucinated,
                },
            })
        return tokens


__all__ = ["LlmTermExtractor"]
