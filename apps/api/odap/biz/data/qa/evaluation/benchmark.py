"""评估体系 - QA 质量 + 检索质量评估"""

import json
import logging
import math
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── 数据模型 ──────────────────────────────────────────────────────────

class BenchmarkCase(BaseModel):
    """基准测试用例"""
    query: str
    expected_intent: str = ""
    expected_entities: List[str] = Field(default_factory=list)
    relevant_doc_ids: List[str] = Field(default_factory=list)
    reference_answer: Optional[str] = None


class BenchmarkDataset(BaseModel):
    """基准测试数据集"""
    name: str
    workspace_id: str = ""
    scenario_id: Optional[str] = None
    cases: List[BenchmarkCase] = Field(default_factory=list)


class RetrievalMetrics(BaseModel):
    """检索质量指标"""
    mrr: float = 0.0
    ndcg_at_k: float = 0.0
    recall_at_k: float = 0.0
    avg_results: float = 0.0


class QAMetrics(BaseModel):
    """QA 质量指标"""
    exact_match: float = 0.0
    f1: float = 0.0
    faithfulness: float = 0.0
    avg_answer_length: float = 0.0


class EvaluationReport(BaseModel):
    """评估报告"""
    dataset_name: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    total_cases: int = 0
    retrieval_metrics: RetrievalMetrics = Field(default_factory=RetrievalMetrics)
    qa_metrics: QAMetrics = Field(default_factory=QAMetrics)
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    pillar_usage: Dict[str, int] = Field(default_factory=dict)
    details: List[Dict[str, Any]] = Field(default_factory=list)


# ── 检索评估器 ────────────────────────────────────────────────────────

class RetrievalEvaluator:
    """检索质量评估: MRR / NDCG@K / Recall@K"""

    def evaluate(self, results: List[Dict[str, Any]],
                 relevant_ids: List[str], k: int = 10) -> RetrievalMetrics:
        """评估单次检索结果"""
        if not relevant_ids:
            return RetrievalMetrics()

        # MRR: 第一个相关结果的排名倒数
        mrr = 0.0
        for i, r in enumerate(results[:k], 1):
            doc_id = r.get("doc_id", "")
            if doc_id in relevant_ids:
                mrr = 1.0 / i
                break

        # Recall@K
        retrieved_relevant = sum(
            1 for r in results[:k]
            if r.get("doc_id", "") in relevant_ids
        )
        recall_at_k = retrieved_relevant / len(relevant_ids) if relevant_ids else 0.0

        # NDCG@K
        dcg = 0.0
        for i, r in enumerate(results[:k], 1):
            if r.get("doc_id", "") in relevant_ids:
                dcg += 1.0 / math.log2(i + 1)
        # Ideal DCG
        ideal_count = min(len(relevant_ids), k)
        idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_count + 1))
        ndcg_at_k = dcg / idcg if idcg > 0 else 0.0

        return RetrievalMetrics(
            mrr=mrr,
            ndcg_at_k=ndcg_at_k,
            recall_at_k=recall_at_k,
            avg_results=len(results),
        )


# ── QA 评估器 ─────────────────────────────────────────────────────────

class QAEvaluator:
    """QA 质量评估: EM / F1 / Faithfulness"""

    def evaluate(self, answer: str, reference: str,
                 sources: Optional[List[Dict]] = None) -> QAMetrics:
        """评估单次 QA 结果"""
        if not reference:
            return QAMetrics()

        # Exact Match
        exact_match = 1.0 if self._normalize(answer) == self._normalize(reference) else 0.0

        # Token-level F1
        answer_tokens = set(self._normalize(answer).split())
        ref_tokens = set(self._normalize(reference).split())
        if answer_tokens and ref_tokens:
            common = answer_tokens & ref_tokens
            precision = len(common) / len(answer_tokens) if answer_tokens else 0.0
            recall = len(common) / len(ref_tokens) if ref_tokens else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        else:
            f1 = 0.0

        # Faithfulness (简单实现: 检查答案中的关键实体是否出现在来源中)
        faithfulness = 0.0
        if sources:
            source_text = " ".join(s.get("content", "") for s in sources)
            answer_words = self._normalize(answer).split()
            if answer_words:
                covered = sum(1 for w in answer_words if w in source_text)
                faithfulness = covered / len(answer_words)

        return QAMetrics(
            exact_match=exact_match,
            f1=f1,
            faithfulness=faithfulness,
            avg_answer_length=len(answer),
        )

    def _normalize(self, text: str) -> str:
        """文本归一化"""
        import re
        text = text.lower().strip()
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text


# ── 基准测试运行器 ────────────────────────────────────────────────────

class BenchmarkRunner:
    """基准测试运行器"""

    def __init__(self, pipeline=None):
        self.pipeline = pipeline
        self.retrieval_evaluator = RetrievalEvaluator()
        self.qa_evaluator = QAEvaluator()

    async def run(self, dataset: BenchmarkDataset) -> EvaluationReport:
        """运行完整基准测试"""
        import time as _time

        if not self.pipeline:
            from odap.biz.data.qa.pipeline.query_pipeline import QueryPipeline
            self.pipeline = QueryPipeline()

        report = EvaluationReport(dataset_name=dataset.name, total_cases=len(dataset.cases))
        latencies: List[float] = []
        all_retrieval = RetrievalMetrics()
        all_qa = QAMetrics()
        pillar_usage: Dict[str, int] = {}

        for case in dataset.cases:
            start = _time.time()
            try:
                from odap.biz.data.qa.models import QueryRequest
                request = QueryRequest(
                    query=case.query,
                    workspace_id=dataset.workspace_id,
                    scenario_id=dataset.scenario_id,
                )
                response = await self.pipeline.query(request)
                elapsed = (_time.time() - start) * 1000
                latencies.append(elapsed)

                # 检索评估
                if case.relevant_doc_ids and response.sources:
                    results = [{"doc_id": s.doc_id} for s in response.sources]
                    ret_metrics = self.retrieval_evaluator.evaluate(results, case.relevant_doc_ids)
                    all_retrieval.mrr += ret_metrics.mrr
                    all_retrieval.ndcg_at_k += ret_metrics.ndcg_at_k
                    all_retrieval.recall_at_k += ret_metrics.recall_at_k
                    all_retrieval.avg_results += ret_metrics.avg_results

                # QA 评估
                if case.reference_answer:
                    sources = [{"content": s.content} for s in response.sources]
                    qa_metrics = self.qa_evaluator.evaluate(
                        response.answer, case.reference_answer, sources
                    )
                    all_qa.exact_match += qa_metrics.exact_match
                    all_qa.f1 += qa_metrics.f1
                    all_qa.faithfulness += qa_metrics.faithfulness
                    all_qa.avg_answer_length += qa_metrics.avg_answer_length

                # 支柱使用统计
                for pillar, contrib in response.pillar_contributions.items():
                    pillar_usage[pillar] = pillar_usage.get(pillar, 0) + 1

                # 意图准确率
                intent_match = response.understanding and response.understanding.intent.value == case.expected_intent

                report.details.append({
                    "query": case.query,
                    "answer_length": len(response.answer),
                    "intent_match": intent_match,
                    "time_ms": elapsed,
                })

            except Exception as e:
                logger.error(f"Benchmark case failed: {case.query} - {e}")
                report.details.append({"query": case.query, "error": str(e)})

        # 汇总
        n = len(dataset.cases) or 1
        report.retrieval_metrics = RetrievalMetrics(
            mrr=round(all_retrieval.mrr / n, 4),
            ndcg_at_k=round(all_retrieval.ndcg_at_k / n, 4),
            recall_at_k=round(all_retrieval.recall_at_k / n, 4),
            avg_results=round(all_retrieval.avg_results / n, 1),
        )
        report.qa_metrics = QAMetrics(
            exact_match=round(all_qa.exact_match / n, 4),
            f1=round(all_qa.f1 / n, 4),
            faithfulness=round(all_qa.faithfulness / n, 4),
            avg_answer_length=round(all_qa.avg_answer_length / n, 1),
        )
        report.pillar_usage = pillar_usage

        # 延迟统计
        if latencies:
            latencies.sort()
            report.latency_p50_ms = round(latencies[len(latencies) // 2], 1)
            p95_idx = int(len(latencies) * 0.95)
            report.latency_p95_ms = round(latencies[min(p95_idx, len(latencies) - 1)], 1)

        return report


# ── 内置基准数据集 ────────────────────────────────────────────────────

def get_default_benchmark() -> BenchmarkDataset:
    """获取默认基准测试数据集"""
    return BenchmarkDataset(
        name="default_nl_query_benchmark",
        cases=[
            BenchmarkCase(query="查找孙悟空", expected_intent="keyword_lookup",
                          expected_entities=["孙悟空"]),
            BenchmarkCase(query="什么是齐天大圣", expected_intent="semantic_search",
                          expected_entities=["齐天大圣"]),
            BenchmarkCase(query="孙悟空的关联实体有哪些", expected_intent="graph_traverse",
                          expected_entities=["孙悟空"]),
            BenchmarkCase(query="分析对比孙悟空和猪八戒", expected_intent="complex_analysis",
                          expected_entities=["孙悟空", "猪八戒"]),
            BenchmarkCase(query="上周发生了什么变化", expected_intent="temporal_query"),
            BenchmarkCase(query="执行模拟演练", expected_intent="action"),
            BenchmarkCase(query="唐僧的敌人", expected_intent="graph_traverse",
                          expected_entities=["唐僧"]),
            BenchmarkCase(query="猪八戒的武器叫什么", expected_intent="keyword_lookup",
                          expected_entities=["猪八戒"]),
        ],
    )
