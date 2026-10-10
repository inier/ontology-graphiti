"""inject vs query 成本/效果对比（ADR-089 C-D5 / E-9）。

离线可跑（不接 LLM，llm_client=None）：对同一批 query 分别以 inject / query
两种模式跑 EntityExtractor.extract，记录 wall_ms 与 round trip（query 模式经
provider 调用计数），输出逐 query 对比 + 汇总 + 裁决。

裁决：query 模式均摊 wall_ms ≤ inject 模式 × 1.5 → "ok"；否则 "regression"。
（容许多出的一次 round trip 与冷启动，与 spec 验收口径一致。）

CLI：python -m odap.biz.data.qa.evaluation.compare_inject_vs_query  （打印 JSON）
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

REGRESSION_FACTOR = 1.5


@dataclass
class ModeRun:
    mode: str
    per_query: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def summary(self) -> Dict[str, Any]:
        n = len(self.per_query)
        walls = [r["wall_ms"] for r in self.per_query]
        rounds = [r["round_trips"] for r in self.per_query]
        hits = [r["entities"] for r in self.per_query]
        return {
            "mode": self.mode,
            "count": n,
            "avg_wall_ms": round(sum(walls) / n, 3) if n else 0.0,
            "total_round_trips": sum(rounds),
            "total_entities": sum(hits),
        }


def _counter_provider(mapping: Dict[str, str], counter: List[str]):
    def _q(expression, domain_id="", kinds=("content",)):
        counter.append(expression)
        return {"content": {"canonical": mapping.get(expression)}}
    return _q


def run_mode(extractor, queries: List[str], *, mode: str,
             domain_id: str = "", round_counter: Optional[List[str]] = None) -> ModeRun:
    run = ModeRun(mode=mode)
    before = len(round_counter) if round_counter is not None else 0
    for q in queries:
        t0 = time.perf_counter()
        entities = extractor.extract(q, domain_id=domain_id)
        wall = (time.perf_counter() - t0) * 1000.0
        trips = (len(round_counter) - before) if round_counter is not None else 0
        run.per_query.append({
            "query": q, "entities": len(entities),
            "wall_ms": round(wall, 3), "round_trips": trips,
        })
        if round_counter is not None:
            before = len(round_counter)
    return run


def compare_inject_vs_query(
    queries: List[str],
    *,
    inject_extractor_factory: Callable[[], Any],
    query_extractor_factory: Callable[[], Any],
    domain_id: str = "",
    provider_map: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """跑两模式并给出逐 query + 汇总 + 裁决。"""
    counter: List[str] = []

    inject_ex = inject_extractor_factory()
    query_ex = query_extractor_factory()
    # query 模式的 round trip 计数：包一层 provider（不改变被测逻辑）
    if provider_map is not None and hasattr(query_ex, "set_entity_context"):
        query_ex.set_entity_context(mode="query", semantics_provider=_ProviderAdapter(
            _counter_provider(provider_map, counter)))

    inject_run = run_mode(inject_ex, queries, mode="inject", domain_id=domain_id)
    query_run = run_mode(query_ex, queries, mode="query", domain_id=domain_id,
                         round_counter=counter)

    a, b = inject_run.summary, query_run.summary
    ok = True
    if a["avg_wall_ms"] > 0:
        ok = b["avg_wall_ms"] <= a["avg_wall_ms"] * REGRESSION_FACTOR
    return {
        "inject": {"summary": a, "per_query": inject_run.per_query},
        "query": {"summary": b, "per_query": query_run.per_query},
        "verdict": "ok" if ok else "regression",
    }


class _ProviderAdapter:
    """把 (expression, domain_id, kinds)->dict 的纯函数适配成 provider.query。"""

    def __init__(self, fn):
        self._fn = fn

    def query(self, expression, domain_id="", kinds=("content",)):
        return self._fn(expression, domain_id, kinds)


def main() -> None:  # pragma: no cover - CLI 入口
    import json
    from odap.biz.data.qa.pipeline.understanding.intent_recognizer import EntityExtractor
    queries = ["「司马懿」是谁", "「诸葛亮」的谋略", "「关羽」的武器"]
    result = compare_inject_vs_query(
        queries,
        inject_extractor_factory=lambda: _mk(mode="inject"),
        query_extractor_factory=lambda: _mk(mode="query"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _mk(mode: str):  # pragma: no cover - CLI helper
    from odap.biz.data.qa.pipeline.understanding.intent_recognizer import EntityExtractor
    ex = EntityExtractor()
    ex.set_entity_context(mode=mode)
    return ex


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = ["compare_inject_vs_query", "run_mode", "ModeRun", "REGRESSION_FACTOR"]
