"""L1 术语抽取实现（纯 Python 零新依赖）。

核心：中文 2/3/4 gram N-gram + 英文单词识别 + 停用词过滤 + 词频置信度。
不引入 jieba/spacy 等新依赖，避免 `pip install` 阻塞 CI。
jieba 若已安装会自动走 jieba.lcut 增强（可在 config.use_jieba=True 开启，默认False）。

可选：BGE embedding + HDBSCAN 聚类（需额外安装 hdbscan），通过 config.extractor_type="bge_hdbscan" 启用。
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set


try:  # 可选：若外部已装 jieba 就走它（不强制依赖）
    import jieba  # type: ignore[import-untyped]  # pragma: no cover - 可选依赖
    _JIEBA_AVAILABLE = True
except Exception:  # pragma: no cover
    _JIEBA_AVAILABLE = False


try:  # 可选：BGE + HDBSCAN（需额外安装 hdbscan）
    from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
    import hdbscan  # type: ignore[import-untyped]
    _BGE_HDBSCAN_AVAILABLE = True
except Exception:  # pragma: no cover
    _BGE_HDBSCAN_AVAILABLE = False


# 中文停止词 + 中文功能词（内置，保证零依赖下可用）
_BUILTIN_STOPWORDS: Set[str] = {
    "的", "了", "和", "是", "在", "也", "不", "就", "都", "而", "及", "与",
    "着", "或", "一个", "没有", "我们", "你们", "他们", "这个", "那个", "这些",
    "那些", "但是", "因为", "所以", "如果", "虽然", "然而", "并且", "以及",
    "已经", "可以", "可能", "应该", "这是", "它", "之", "其", "于", "等",
    "被", "把", "让", "将", "从", "对", "为", "于", "给", "向", "跟",
    "自己", "什么", "怎么", "如何", "为什么", "哪里", "哪个", "这样", "那样",
    "通过", "进行", "成为", "表示", "具有", "包括", "根据", "关于", "对于",
    "但是", "不过", "可是", "还是", "以及", "还是", "然后", "接着", "最后",
    "的话", "如果说", "来说", "而言", "以上", "以下", "以前", "以后",
    "里面", "外面", "之间", "之后", "之前", "以内", "以外", "上面", "下面",
    "我", "你", "他", "她", "它", "们", "这", "那", "哪", "就", "要",
    "会", "能", "可以", "应当", "必须", "得", "地", "很", "太", "最",
    "更", "还", "又", "再", "只", "就是", "不是", "没有", "于是",
}


# 正则：中文（含标点前的字块） / 英文单词 / 数字序列
_CN_SEQ = re.compile(r"[\u4e00-\u9fff]{1,}")
_EN_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]{1,}")


class NgramTermExtractor:
    """零依赖 L1 抽取器：N-gram + 停用词 + 词频。

    满足 Protocol L1TermExtractor：
        def extract(self, *, text, extra_docs, workspace_id, ontology_id, stopwords, config)
    """

    def __init__(self) -> None:
        self._stopwords: Set[str] = set(_BUILTIN_STOPWORDS)

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
    ):  # -> List[RawToken]
        """Run extraction. 参数 workspace_id/ontology_id 保留给迭代 3 接入 KNN。"""
        cfg = config or {}
        all_texts: List[str] = [text or ""] + list(extra_docs or [])
        use_jieba = bool(cfg.get("use_jieba", False)) and _JIEBA_AVAILABLE
        min_freq = int(cfg.get("min_frequency", 1))
        max_candidates = int(cfg.get("max_candidates", 1000))
        ngram_range = tuple(cfg.get("ngram_range", (2, 4)))
        stopset = set(self._stopwords) | set(stopwords or set())

        # 1. 所有候选 surface 计数
        counter: Counter = Counter()
        spans: Dict[str, List[str]] = {}
        for doc in all_texts:
            if not doc:
                continue
            for sentence in self._split_sentences(doc):
                if not sentence:
                    continue
                for tok in self._tokenize_sentence(
                    sentence,
                    use_jieba=use_jieba,
                    ngram_range=ngram_range,
                ):
                    if not self._is_valid_token(tok, stopset):
                        continue
                    counter[tok] += 1
                    spans.setdefault(tok, []).append(sentence)

        # 2. 按频过滤 + 构造 RawToken[]
        results = []
        for surface, freq in counter.most_common(max_candidates):
            if freq < min_freq:
                break
            conf = self._score_confidence(surface, freq, counter.total() or 1)
            results.append({
                "surface": surface,
                "frequency": freq,
                "confidence": conf,
                "source_text": (spans.get(surface) or [""])[:3][0],
                "provenance": {
                    "sample_contexts": (spans.get(surface) or [])[:5],
                    "tokenizer": ("jieba" if use_jieba else f"ngram_{ngram_range[0]}-{ngram_range[1]}"),
                },
            })
        return results

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        # 中/英常见句末标点
        return [s.strip() for s in re.split(r"[。！？!?；;\n\r]+", text) if s.strip()]

    @staticmethod
    def _tokenize_sentence(
        sent: str, *, use_jieba: bool, ngram_range: tuple
    ) -> List[str]:
        tokens: List[str] = []

        # 中文序列
        for m in _CN_SEQ.finditer(sent):
            seq = m.group(0)
            if use_jieba:  # pragma: no cover - 依赖已安装分支
                tokens.extend(t.strip() for t in jieba.lcut(seq) if t.strip())
            else:
                lo, hi = ngram_range
                for size in range(lo, hi + 1):
                    if len(seq) < size:
                        break
                    for i in range(0, len(seq) - size + 1):
                        tokens.append(seq[i:i + size])

        # 英文序列
        for m in _EN_WORD.finditer(sent):
            w = m.group(0)
            if len(w) >= 2:  # 单个英文字母丢弃
                tokens.append(w.lower())

        return tokens

    @staticmethod
    def _is_valid_token(tok: str, stopset: Set[str]) -> bool:
        if not tok or tok in stopset:
            return False
        if len(tok) == 1:
            return False  # 单字忽略
        if tok.isdigit():
            return False
        # 纯标点
        if re.fullmatch(r"[\W_]+", tok):
            return False
        return True

    @staticmethod
    def _score_confidence(surface: str, freq: int, total: int) -> float:
        # 0~1：基于词频占比（上限 0.6）+ 长度偏好（2~4字最优，英文词加分）
        tf = min(freq / max(total, 1), 1.0)
        tf_score = 0.6 * (1 - pow(0.5, freq / max(total * 0.001, 1)))
        is_en = all(ord(c) < 128 for c in surface)
        if is_en:
            len_score = 0.4 if 3 <= len(surface) <= 12 else 0.2
        else:
            if 2 <= len(surface) <= 4:
                len_score = 0.4
            elif len(surface) == 5:
                len_score = 0.3
            else:
                len_score = 0.15
        # 字符多样性（避免"XXXX"之类重复字）
        uniq_ratio = len(set(surface)) / max(len(surface), 1)
        diversity = 0.0 if uniq_ratio < 0.4 else 0.1
        return round(min(tf_score + len_score + diversity, 0.99), 4)


class BgeHdbscanTermExtractor:
    """BGE embedding + HDBSCAN 聚类抽取器。

    满足 Protocol L1TermExtractor：
        def extract(self, *, text, extra_docs, workspace_id, ontology_id, stopwords, config)

    使用 BGE-base-zh 模型进行 embedding，HDBSCAN 进行语义聚类，
    从聚类中心附近的文本片段中提取术语候选。

    配置参数（config）：
        - model_name: BGE 模型名称，默认 "BAAI/bge-base-zh"
        - min_cluster_size: HDBSCAN 最小聚类大小，默认 3
        - min_samples: HDBSCAN 最小样本数，默认 2
        - top_k_per_cluster: 每聚类取前 K 个候选，默认 5
    """

    def __init__(self) -> None:
        self._stopwords: Set[str] = set(_BUILTIN_STOPWORDS)
        self._model: Any = None

    def _ensure_model(self, config: Optional[Dict[str, Any]] = None) -> Any:
        config = config or {}
        if self._model is None:
            model_name = str(config.get("model_name", "BAAI/bge-base-zh"))
            _ALLOWED_MODELS = {"BAAI/bge-base-zh", "BAAI/bge-small-zh", "BAAI/bge-large-zh"}
            if model_name not in _ALLOWED_MODELS:
                raise ValueError(f"Unsupported model_name: {model_name!r}")
            self._model = SentenceTransformer(model_name)
        return self._model

    def extract(
        self,
        *,
        text: str,
        extra_docs: Optional[List[str]] = None,
        workspace_id: Optional[str] = None,
        ontology_id: Optional[str] = None,
        stopwords: Optional[set] = None,
        config: Optional[Dict[str, Any]] = None,
    ):  # -> List[RawToken]
        if not _BGE_HDBSCAN_AVAILABLE:
            raise ValueError(
                "BGE+HDBSCAN 抽取器不可用，请安装依赖: pip install hdbscan"
            )

        cfg = config or {}
        all_texts: List[str] = [text or ""] + list(extra_docs or [])
        min_cluster_size = int(cfg.get("min_cluster_size", 3))
        min_samples = int(cfg.get("min_samples", 2))
        top_k_per_cluster = int(cfg.get("top_k_per_cluster", 5))
        stopset = set(self._stopwords) | set(stopwords or set())

        sentences: List[str] = []
        for doc in all_texts:
            if not doc:
                continue
            sentences.extend(s.strip() for s in re.split(r"[。！？!?；;\n\r]+", doc) if s.strip())

        if len(sentences) < min_cluster_size:
            return []

        model = self._ensure_model(cfg)
        embeddings = model.encode(sentences, show_progress_bar=False)

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric="cosine",
        )
        labels = clusterer.fit_predict(embeddings)

        cluster_sentences: Dict[int, List[str]] = {}
        for idx, label in enumerate(labels):
            if label >= 0:
                cluster_sentences.setdefault(label, []).append(sentences[idx])

        results = []
        for cluster_id, cluster_sents in cluster_sentences.items():
            cluster_text = " ".join(cluster_sents)
            counter: Counter = Counter()
            spans: Dict[str, List[str]] = {}

            for sent in cluster_sents:
                for tok in self._extract_ngrams(sent, stopset):
                    counter[tok] += 1
                    spans.setdefault(tok, []).append(sent)

            for surface, freq in counter.most_common(top_k_per_cluster):
                conf = self._score_confidence(surface, freq, counter.total() or 1)
                results.append({
                    "surface": surface,
                    "frequency": freq,
                    "confidence": conf,
                    "source_text": (spans.get(surface) or [""])[:3][0],
                    "provenance": {
                        "sample_contexts": (spans.get(surface) or [])[:5],
                        "tokenizer": "bge_hdbscan",
                        "cluster_id": cluster_id,
                        "cluster_size": len(cluster_sents),
                    },
                })

        results.sort(key=lambda x: x["confidence"], reverse=True)
        max_candidates = int(cfg.get("max_candidates", 1000))
        return results[:max_candidates]

    @staticmethod
    def _extract_ngrams(sent: str, stopset: Set[str]) -> List[str]:
        tokens: List[str] = []
        for m in _CN_SEQ.finditer(sent):
            seq = m.group(0)
            for size in range(2, min(5, len(seq) + 1)):
                for i in range(0, len(seq) - size + 1):
                    tok = seq[i:i + size]
                    if tok and tok not in stopset and len(tok) >= 2:
                        tokens.append(tok)
        for m in _EN_WORD.finditer(sent):
            w = m.group(0)
            if len(w) >= 2:
                tokens.append(w.lower())
        return tokens
