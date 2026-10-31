"""L2 向量召回（可选增强）：用真实 embedding 做术语近邻，补构词规则覆盖不到的说法。

能力探测结论（本轮实测，非假设）：
- 环境内存在 OpenAI 兼容端点（`llm.api_base`），`/v1/embeddings` 可用、768 维；
- 但 chat 模型在本机加载失败，因此 L3 只能走「不可用 → 澄清」路径（见 `intent_llm.py`）。

设计纪律：
- **不默认启用**：`L1IntentRouter(embedder=None)` 时不发任何网络请求，
  CI 与离线环境完全确定性（评测门禁跑的就是这条路径）；
- 注入 `embed_fn` 后才生效，且只在词典/形态都没命中时补召回（不与既有证据抢优先级）；
- 端点失败 → 返回空（并记录 degraded 原因），**不伪造相似度**。
"""

from __future__ import annotations

import logging
import math
from typing import Callable, Dict, List, Optional, Sequence

from odap.biz.core.ontology.orchestration.impl.intent_terms import TermSpan, classify_intent

logger = logging.getLogger(__name__)

#: 余弦相似度低于此值不召回（宁缺勿滥：向量召回最容易引入似是而非的术语）
MIN_SIMILARITY = 0.72
#: 向量召回的分数区间（低于形态规则，高于模糊匹配）
SCORE_FLOOR = 0.70
SCORE_CEIL = 0.89

EmbedFn = Callable[[Sequence[str]], List[List[float]]]


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if not norm_left or not norm_right:
        return 0.0
    return dot / (norm_left * norm_right)


class EmbeddingRecall:
    """术语向量近邻召回（术语向量按需懒加载并缓存）。"""

    name = "IntentEmbedding"

    def __init__(self, embed_fn: EmbedFn, mapping: Dict[str, Dict],
                 min_similarity: float = MIN_SIMILARITY) -> None:
        self._embed_fn = embed_fn
        self._mapping = mapping
        self.min_similarity = min_similarity
        self._vectors: Optional[List[tuple]] = None
        self.degraded_reason: Optional[str] = None

    # ── 对外 ──────────────────────────────────────────────────────────────
    def find_vector_spans(self, text: str, blocked: Sequence[TermSpan] = ()) -> List[TermSpan]:
        query = (text or "").strip()
        if not query:
            return []
        try:
            vectors = self._term_vectors()
            query_vector = self._embed([query])[0]
        except Exception as exc:  # noqa: BLE001 - 召回失败必须显式降级
            self.degraded_reason = f"{type(exc).__name__}: {exc}"
            logger.warning("向量召回不可用，降级为无向量 L2：%s", self.degraded_reason)
            return []
        scored = []
        for expression, entry, vector in vectors:
            similarity = cosine(query_vector, vector)
            if similarity < self.min_similarity:
                continue
            if any(expression in span.surface for span in blocked):
                continue  # 已被更可靠证据覆盖的术语不重复召回
            scored.append((similarity, expression, entry))
        scored.sort(key=lambda item: -item[0])
        spans: List[TermSpan] = []
        for similarity, expression, entry in scored[:3]:
            start = query.find(expression)
            if start < 0:
                continue  # 向量只用来"选术语"，位置仍需原文可定位
            score = round(min(SCORE_CEIL, SCORE_FLOOR + (similarity - self.min_similarity)), 3)
            spans.append(TermSpan(
                surface=expression, start=start, end=start + len(expression),
                intent=classify_intent(str(entry.get("semantic_type") or ""),
                                       str(entry.get("canonical") or expression)),
                score=score, source="vector",
                canonical=str(entry.get("canonical") or expression),
            ))
        return spans

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _term_vectors(self) -> List[tuple]:
        if self._vectors is None:
            expressions = list(self._mapping.keys())
            embeddings = self._embed(expressions)
            self._vectors = [
                (expression, self._mapping[expression], vector)
                for expression, vector in zip(expressions, embeddings)
            ]
        return self._vectors

    def _embed(self, texts: Sequence[str]) -> List[List[float]]:
        vectors = self._embed_fn(list(texts))
        if len(vectors) != len(texts):
            raise ValueError(f"embedding 返回条数不匹配：{len(vectors)} != {len(texts)}")
        return vectors


def build_http_embed_fn(base_url: str, model: str, api_key: str = "",
                        timeout: float = 15.0) -> EmbedFn:
    """OpenAI 兼容 `/v1/embeddings` 客户端（批量一次请求）。"""
    base = (base_url or "").rstrip("/")
    endpoint = f"{base}/embeddings" if base.endswith("/v1") else f"{base}/v1/embeddings"

    def _embed(texts: List[str]) -> List[List[float]]:
        import httpx

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = httpx.post(endpoint, headers=headers, timeout=timeout,
                              json={"model": model, "input": texts})
        response.raise_for_status()
        payload = response.json()
        return [item["embedding"] for item in payload.get("data", [])]

    return _embed


def build_default_recall(mapping: Dict[str, Dict]) -> Optional[EmbeddingRecall]:
    """按 `llm.*` 配置装配向量召回；未配置 → None（路由层不启用）。

    与 L3 同一纪律：`api_base` / `embedder_model` 都有内置默认值，只看它们会误判"已配置"，
    必须 api_key 也显式设置才启用，避免离线环境悄悄发外网请求。
    """
    try:
        from odap.infra.config_composer import get_config
    except Exception as exc:  # noqa: BLE001 - 配置层不可用即不启用
        logger.warning("向量召回装配失败（配置层不可用）：%s", exc)
        return None
    base_url = str(get_config("llm.api_base", "") or "")
    model = str(get_config("llm.embedder_model", "") or "")
    api_key = str(get_config("llm.api_key", "") or "")
    if not (base_url and model and api_key):
        return None
    embed_fn = build_http_embed_fn(base_url, model, api_key)
    return EmbeddingRecall(embed_fn=embed_fn, mapping=mapping)


__all__ = [
    "EmbeddingRecall",
    "MIN_SIMILARITY",
    "build_default_recall",
    "build_http_embed_fn",
    "cosine",
]
