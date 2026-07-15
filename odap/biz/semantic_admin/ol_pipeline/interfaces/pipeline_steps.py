"""Pipeline Steps Protocol 抽象定义。

Spec 007 Iter 2 §2 OL Pipeline - 6 Layers：
  L1 Term Extraction       → 本体/文本 → 候选术语列表（RawToken[]）
  L2 Concept Extraction    → RawToken[]  → 归并同义词、去重、生成准规范术语
  L3 Classification        → 规范术语   → 语义类型 (SemanticType) + 领域(domain_id)预测
  L4 Quality Gate          → candidate  → 质量报告 (QualityReport)
  L5 HITL Approval         → candidate  → 一级/二级审批结果
  L6 WriteBack             → approved   → 写入 USL 正式表 + 审计

本模块为 L1~L3 定义 Python Protocol（鸭子类型抽象），
让 PipelineService 可无改动地接入不同实现（如 jieba → spacy → LLM 模型版本）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# 公共数据结构（轻量 TypedDict 等价，避免 Pydantic 序列化开销，用纯 dict 传输）
# ---------------------------------------------------------------------------

class RawToken(Dict[str, Any]):
    """L1 产出的原始术语 token：
    {
        "surface": "孙悟空",                # 原文文本片段
        "start": 12,                         # 在原文的 char 起始位置（可选）
        "end": 15,                           # 在原文的 char 结束位置（可选）
        "frequency": 3,                      # 在输入文本集中出现次数
        "confidence": 0.85,                  # L1 抽取置信度（基于频率/模式）
        "source_text": "孙悟空三打白骨精...",  # 来源句/段
    }
    """


class ConceptCandidate(Dict[str, Any]):
    """L2 产出的准规范术语（去重 + 同义词归并）：
    {
        "canonical": "孙悟空",                # 选定的规范术语
        "synonyms": ["孙行者", "美猴王"],      # 归并得到的同义词集合
        "near_synonyms": [],                  # 近似同义词（置信度 < 0.8）
        "aliases": [],                        # 其他别名
        "frequency": 5,                       # 含同义词合计出现次数
        "confidence": 0.92,                   # L2 归并后的最终置信度
        "source_text": "...",                 # 样本来源
        "provenance": {"segments": []},       # 溯源（对应 L1 的 segment ID）
    }
    """


class ClassifiedCandidate(Dict[str, Any]):
    """L3 产出的分类候选：
    {
        "canonical": "孙悟空",
        "semantic_type": "对象类型",          # 中文枚举对齐 USL SemanticType
        "domain_id": "sanguo",               # 所属语义域 code（可能 None）
        "definition": "...",                 # 可选：抽取到的定义句
        "confidence": 0.9,                   # 综合置信度 L1*L2*L3
        "examples": [],                      # 例句
        "stoplist_flag": False,              # 是否命中停用词表
        ** L2 其它字段（synonyms/near_synonyms/...）
    }
    """


# ---------------------------------------------------------------------------
# 三步 Protocol：PipelineService 按此契约编排
# ---------------------------------------------------------------------------

@runtime_checkable
class L1TermExtractor(Protocol):
    """L1 术语抽取：原始文本 → RawToken[]。

    实现需保证输入为纯 Python dict 上下文，不依赖 FastAPI/HTTP。
    """

    def extract(
        self,
        *,
        text: str,
        extra_docs: Optional[List[str]] = None,
        workspace_id: Optional[str] = None,
        ontology_id: Optional[str] = None,
        stopwords: Optional[set] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[RawToken]:
        """抽取 RawToken 列表。"""


@runtime_checkable
class L2ConceptExtractor(Protocol):
    """L2 概念归并：RawToken[] → ConceptCandidate[]。

    负责：同义词归一、多 token 指代同一个术语合并、低置信度剔除。
    """

    def merge(
        self,
        tokens: List[RawToken],
        *,
        existing_usl_terms: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[ConceptCandidate]:
        """归并得到 ConceptCandidate 列表。"""


@runtime_checkable
class L3Classifier(Protocol):
    """L3 分类器：ConceptCandidate → ClassifiedCandidate。

    负责：语义类型 OBJECT_TYPE/LINK_TYPE 等（中文枚举） + domain_id 归属预测。
    """

    def classify(
        self,
        concepts: List[ConceptCandidate],
        *,
        domains: Optional[List[Dict[str, Any]]] = None,
        existing_examples: Optional[Dict[str, List[str]]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[ClassifiedCandidate]:
        """分类得到 ClassifiedCandidate 列表。"""
