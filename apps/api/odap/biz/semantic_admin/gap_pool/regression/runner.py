"""PairedReplayRunner —— 配对回放 + 信号收集器 + 差分判定（ADR-088 D3/D4/D5/D6）。

生产语义（实现期澄清，ADR-088 D3 附注）：
- before 轮 = **捕获证据**——回归集来自缺口，缺口即"当时答不上"的证据，
  before_answered=False 由集合语义给出（不重放历史、不造时间机器）；
- after 轮 = **现场回放**——逐 case 走真实查询管线，信号收集器判定 answered。
- 双轮均为现场执行的真·配对模式经 before_executor/after_executor 注入支持
  （测试/未来快照对），regressed 判定在该模式下可达。

信号收集器（D6）：回放期间以模块级补丁把 gap_emitter.report_gap_signal 替换为
内存收集器，QA_UNANSWERED / NL_QUERY_UNANSWERED 即 unanswered；结束恢复原函数
并**丢弃**收集结果（D5：绝不写 concept_gaps，heat 不变、REJECTED 不复活）。
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_UNANSWERED_SOURCES = {"qa_unanswered", "nl_query_unanswered"}


def current_model_fingerprint() -> Dict[str, str]:
    """backbone 指纹（ADR-088 D8）：model_id 取运行时 LLM 配置，
    prompt_version 取环境变量（运维显式声明，默认 'unversioned'）。
    换模型/prompt 后旧报告须重跑——报告侧比对 set 构建指纹给出警示。
    """
    model_id = ""
    try:
        from odap.infra.config_composer import get_config
        model_id = str(get_config("llm.model", "") or "")
    except Exception as e:  # 配置层不可用也要有指纹字段（显式空串，不隐藏）
        logger.warning("读取 llm.model 配置失败，model_id 置空: %s", e)
    return {
        "model_id": model_id,
        "prompt_version": os.environ.get("GAP_REGRESSION_PROMPT_VERSION",
                                         "unversioned"),
    }


class PairedReplayRunner:
    def __init__(self, pipeline: Optional[Any] = None):
        self._pipeline = pipeline

    def _get_pipeline(self):
        if self._pipeline is None:
            # 必须用共享单例：裸 QueryPipeline() 的向量与图谱支柱恒为空
            # （benchmark.py 同注）。
            from odap.biz.data.qa.pipeline.query_pipeline import get_query_pipeline
            self._pipeline = get_query_pipeline()
        return self._pipeline

    async def _live_round(self, cases: List[Dict[str, Any]],
                          workspace_id: Optional[str]) -> Dict[str, bool]:
        """现场回放一轮：逐 case 走管线，收集器判 answered（真实函数体）。"""
        from odap.biz.data.qa.models import QueryRequest
        from odap.biz.semantic_admin.gap_pool.services import gap_emitter

        pipeline = self._get_pipeline()
        collected: List[tuple] = []
        original = gap_emitter.report_gap_signal

        def collector(source, expression, **kw):
            collected.append((str(getattr(source, "value", source)), expression))

        per_case: Dict[str, bool] = {}
        gap_emitter.report_gap_signal = collector
        try:
            for case in cases:
                n_before = len(collected)
                request = QueryRequest(query=case["query"],
                                       workspace_id=workspace_id or None,
                                       user_id="gap-replay")
                response = await pipeline.query(request)
                if response is None:  # 规则 14：不允许被调方静默吞错
                    raise RuntimeError(
                        f"查询管线返回 None（query={case['query']!r}），"
                        "疑似幻影调用或静默降级，回放中止")
                fired = [s for s, _e in collected[n_before:]
                         if s in _UNANSWERED_SOURCES]
                per_case[case["query"]] = len(fired) == 0
        finally:
            # 恢复原函数；collected 丢弃（D5/D6：绝不落库）
            gap_emitter.report_gap_signal = original
        return per_case

    async def replay(self, cases: List[Dict[str, Any]], *,
                     workspace_id: Optional[str] = None,
                     before_executor: Optional[Callable[[Dict], Awaitable[bool]]] = None,
                     after_executor: Optional[Callable[[Dict], Awaitable[bool]]] = None,
                     ) -> Dict[str, Any]:
        """配对回放。verdict=pass ⇔ regressed=0 ∧ fixed≥1；执行异常 → error。"""
        fp = current_model_fingerprint()
        rounds: List[Dict[str, Any]] = []
        fixed = regressed = unchanged = 0
        error_detail: Optional[str] = None
        cost: Dict[str, Any] = {"before_mode": "captured_evidence",
                                "before_ms": 0.0, "after_ms": 0.0}

        try:
            # ---- before 轮 ----
            before_answered: Dict[str, bool] = {}
            if before_executor is not None:
                cost["before_mode"] = "live"
                t0 = time.perf_counter()
                for case in cases:
                    before_answered[case["query"]] = bool(
                        await before_executor(case))
                cost["before_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            else:
                # 捕获证据模式：缺口即"当时答不上"，before_answered=False
                before_answered = {c["query"]: False for c in cases}

            # ---- after 轮（现场回放 + 收集器） ----
            t1 = time.perf_counter()
            if after_executor is not None:
                after_answered = {
                    c["query"]: bool(await after_executor(c)) for c in cases
                }
            else:
                after_answered = await self._live_round(cases, workspace_id)
            cost["after_ms"] = round((time.perf_counter() - t1) * 1000, 1)

            # ---- 差分判定（真实计数，无推断） ----
            for case in cases:
                q = case["query"]
                b = before_answered.get(q, False)
                a = after_answered.get(q, False)
                rounds.append({"query": q, "before_answered": b,
                               "after_answered": a})
                if not b and a:
                    fixed += 1
                elif b and not a:
                    regressed += 1
                else:
                    unchanged += 1
        except Exception as e:  # 规则 14：失败显式，error_detail 必填具体原因
            error_detail = f"{type(e).__name__}: {e}"
            logger.warning("配对回放执行失败: %s", e, exc_info=True)

        if error_detail is not None:
            verdict = "error"
        elif regressed == 0 and fixed >= 1:
            verdict = "pass"
        else:
            verdict = "fail"

        return {
            "verdict": verdict,
            "fixed_count": fixed,
            "regressed_count": regressed,
            "unchanged_count": unchanged,
            "rounds": rounds,
            "cost": cost,
            "error_detail": error_detail,
            "model_id": fp["model_id"],
            "prompt_version": fp["prompt_version"],
        }
