"""Iter 4.2: RetrievalAGUIAdapter — bridges RetrievalService to AG-UI events.

ADR-074 §4.2 / ADR-073 §2.1: 统一检索服务通过 AG-UI 协议对外暴露，
使智能体（CopilotKit / AWS Bedrock / Google ADK 等）可直接消费检索结果。

架构（复用已有 AG-UI 基础设施 + RetrievalService）：
    ┌──────────────────────────────────────────────────────────┐
    │ RetrievalAGUIAdapter                                     │
    │   stream_search(query, mode) → AsyncIterator[AGUIEvent]  │
    │   stream_chain_search(query, rules) → AsyncIterator      │
    │ ┌──────────────────────────────────────────────────────┐ │
    │ │ 1. RUN_STARTED                                       │ │
    │ │ 2. STEP_STARTED("retrieval")                          │ │
    │ │ 3. RetrievalService.search() / chain_search()         │ │
    │ │ 4. TEXT_MESSAGE_* (results as readable text)          │ │
    │ │ 5. STEP_FINISHED                                      │ │
    │ │ 6. RUN_FINISHED (with Interrupt if low confidence)    │ │
    │ │ + query_audit 埋点（Iter 3.2 #5 查询审计）            │ │
    │ └──────────────────────────────────────────────────────┘ │
    └──────────────────────────────────────────────────────────┘

HITL Interrupt 触发条件：
- 检索结果置信度 < CONFIDENCE_THRESHOLD（默认 0.5）
- 触发 Interrupt(reason=CONFIRMATION)，要求用户确认低置信度事实

设计要点（AGENTS.md / project_memory）：
- 函数 ≤40 行（Constitution I）
- 复用 agui_models 事件类型，不新建协议
- query_audit 埋点不阻塞流式返回（fire-and-forget）
- 审计不记明文（FR-013）
"""

import json
import logging
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from odap.infra.security.audit_helper import query_audit

from ..agui.agui_models import (
    Interrupt,
    InterruptReason,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)

logger = logging.getLogger("agui.retrieval_adapter")

# 低置信度事实触发 HITL 的阈值
CONFIDENCE_THRESHOLD = 0.5


class RetrievalAGUIAdapter:
    """将 RetrievalService 的检索结果转换为 AG-UI 事件流。

    Usage:
        adapter = RetrievalAGUIAdapter(retrieval_service)
        async for event in adapter.stream_search(workspace_id, query, mode="auto"):
            await websocket.send_json(event)
    """

    def __init__(
        self,
        retrieval_service: Any = None,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ):
        self._retrieval = retrieval_service
        self._confidence_threshold = confidence_threshold

    def _get_service(self) -> Any:
        """懒加载 RetrievalService 单例。"""
        if self._retrieval is not None:
            return self._retrieval
        try:
            from odap.biz.core.ontology.public import (
                RetrievalService,
            )
            self._retrieval = RetrievalService()
        except Exception as exc:
            logger.error("RetrievalService 初始化失败: %s", exc)
            self._retrieval = None
        return self._retrieval

    # ------------------------------------------------------------------
    # 统一检索 → AG-UI 事件流
    # ------------------------------------------------------------------

    async def stream_search(
        self,
        workspace_id: str,
        query: str,
        mode: str = "auto",
        limit: int = 20,
        operator: str = "anonymous",
        thread_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """统一检索 → AG-UI 事件流。

        Yields AG-UI events in order:
            RUN_STARTED → STEP_STARTED → TEXT_MESSAGE_* → STEP_FINISHED → RUN_FINISHED

        If result confidence < threshold, RUN_FINISHED carries an Interrupt.
        """
        tid = thread_id or str(uuid.uuid4())
        rid = run_id or str(uuid.uuid4())

        # 1. RUN_STARTED
        yield RunStartedEvent(
            threadId=tid, runId=rid, input={"query": query, "mode": mode}
        ).model_dump(by_alias=True, exclude_none=True)

        service = self._get_service()
        if service is None:
            yield self._build_error_event(tid, rid, "RetrievalService unavailable")
            return

        # 2. STEP_STARTED
        yield StepStartedEvent(stepName="retrieval").model_dump(
            by_alias=True, exclude_none=True
        )

        # 7. query_audit 埋点（提前声明，在 finally 中保证执行 — m4 修复）
        audit_emitted = False

        try:
            # 3. 执行检索
            try:
                from odap.biz.core.ontology.public import (
                    SearchRequest,
                )
                request = SearchRequest(query=query, mode=mode, limit=limit)
                result = await service.search(workspace_id, request)
            except Exception as exc:
                # M3 修复：检索异常时补发 STEP_FINISHED 再发 RUN_ERROR（协议一致性）
                logger.exception("stream_search 检索失败")
                yield StepFinishedEvent(stepName="retrieval").model_dump(
                    by_alias=True, exclude_none=True
                )
                yield self._build_error_event(tid, rid, str(exc))
                return

            # 4. TEXT_MESSAGE_* (结果文本化)
            message_id = str(uuid.uuid4())
            text = self._format_search_result(result)

            yield TextMessageStartEvent(messageId=message_id, role="assistant").model_dump(
                by_alias=True, exclude_none=True
            )

            # 分块发送（模拟流式，每块 ~200 字符）
            for chunk in self._chunk_text(text, 200):
                yield TextMessageContentEvent(
                    messageId=message_id, delta=chunk
                ).model_dump(by_alias=True, exclude_none=True)

            yield TextMessageEndEvent(messageId=message_id).model_dump(
                by_alias=True, exclude_none=True
            )

            # 5. STEP_FINISHED
            yield StepFinishedEvent(stepName="retrieval").model_dump(
                by_alias=True, exclude_none=True
            )

            # 6. RUN_FINISHED (检查是否需要 HITL Interrupt)
            interrupt = self._check_confidence(result)
            outcome: Dict[str, Any] = {"type": "success"}
            if interrupt is not None:
                outcome = {"type": "interrupt", "interrupts": [interrupt.model_dump(by_alias=True, exclude_none=True)]}

            yield RunFinishedEvent(
                threadId=tid,
                runId=rid,
                outcome=outcome,
                result={
                    "total": result.total,
                    "mode": result.mode,
                    "has_interrupt": interrupt is not None,
                },
            ).model_dump(by_alias=True, exclude_none=True)

            # query_audit 埋点（Iter 3.2 #5 查询审计，使用 result.mode 而非请求 mode）
            self._emit_query_audit(
                operator=operator,
                workspace_id=workspace_id,
                query=query,
                mode=result.mode,
                result=result,
                interrupt_triggered=interrupt is not None,
            )
            audit_emitted = True
        finally:
            # m4 修复：客户端断连时 GeneratorExit 触发 finally，保证审计执行
            if not audit_emitted:
                self._emit_query_audit(
                    operator=operator,
                    workspace_id=workspace_id,
                    query=query,
                    mode=mode,
                    result={"total": 0, "mode": mode},
                    interrupt_triggered=False,
                )

    # ------------------------------------------------------------------
    # 链式推理 → AG-UI 事件流（STEP 事件可视化多跳推理）
    # ------------------------------------------------------------------

    async def stream_chain_search(
        self,
        workspace_id: str,
        query: str,
        rules: Optional[List[str]] = None,
        max_depth: int = 5,
        operator: str = "anonymous",
        thread_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """链式推理 → AG-UI 事件流（每个推理步骤一个 STEP）。

        Yields:
            RUN_STARTED → (STEP_STARTED → TEXT_MESSAGE_CONTENT → STEP_FINISHED)* → RUN_FINISHED
        """
        tid = thread_id or str(uuid.uuid4())
        rid = run_id or str(uuid.uuid4())

        yield RunStartedEvent(
            threadId=tid, runId=rid,
            input={"query": query, "rules": rules or [], "max_depth": max_depth},
        ).model_dump(by_alias=True, exclude_none=True)

        service = self._get_service()
        if service is None:
            yield self._build_error_event(tid, rid, "RetrievalService unavailable")
            return

        try:
            raw = await service.chain_search(
                workspace_id,
                query=query,
                rules=rules or [],
                max_depth=max_depth,
            )
        except Exception as exc:
            logger.exception("stream_chain_search 失败")
            yield self._build_error_event(tid, rid, str(exc))
            return

        # 为每个推理步骤发射 STEP 事件
        reasoning = raw.get("reasoning", {})
        steps = reasoning.get("steps", [])
        message_id = str(uuid.uuid4())

        if steps:
            yield TextMessageStartEvent(messageId=message_id, role="assistant").model_dump(
                by_alias=True, exclude_none=True
            )

        for i, step in enumerate(steps):
            step_name = f"step_{i + 1}"
            yield StepStartedEvent(stepName=step_name).model_dump(
                by_alias=True, exclude_none=True
            )

            step_text = self._format_step(step, i + 1)
            yield TextMessageContentEvent(
                messageId=message_id, delta=step_text
            ).model_dump(by_alias=True, exclude_none=True)

            yield StepFinishedEvent(stepName=step_name).model_dump(
                by_alias=True, exclude_none=True
            )

        if steps:
            yield TextMessageEndEvent(messageId=message_id).model_dump(
                by_alias=True, exclude_none=True
            )

        # 循环检测 → Interrupt
        cycle_detected = reasoning.get("cycle_detected", False)
        interrupt = None
        if cycle_detected:
            interrupt = Interrupt(
                id=str(uuid.uuid4()),
                reason=InterruptReason.CONFIRMATION,
                message="检测到推理循环，请确认是否继续或调整规则",
                metadata={"cycle_detected": True, "step_count": len(steps)},
            )

        outcome: Dict[str, Any] = {"type": "success"}
        if interrupt is not None:
            outcome = {"type": "interrupt", "interrupts": [interrupt.model_dump(by_alias=True, exclude_none=True)]}

        yield RunFinishedEvent(
            threadId=tid, runId=rid, outcome=outcome,
            result={
                "total_steps": len(steps),
                "cycle_detected": cycle_detected,
                "has_interrupt": interrupt is not None,
            },
        ).model_dump(by_alias=True, exclude_none=True)

        self._emit_query_audit(
            operator=operator,
            workspace_id=workspace_id,
            query=query,
            mode="chain",
            result=raw,
            interrupt_triggered=interrupt is not None,
        )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _format_search_result(self, result: Any) -> str:
        """将 SearchResult 格式化为可读文本。"""
        lines = [
            f"检索模式: {result.mode}",
            f"结果数量: {result.total}",
            "",
        ]
        for i, row in enumerate(result.rows[:20], 1):  # 限制 20 条
            if isinstance(row, dict):
                title = row.get("name") or row.get("title") or row.get("id", f"item_{i}")
                summary = row.get("summary") or row.get("description") or ""
                confidence = row.get("confidence")
                conf_str = f" (置信度: {confidence:.2f})" if isinstance(confidence, (int, float)) else ""
                lines.append(f"{i}. {title}{conf_str}")
                if summary:
                    lines.append(f"   {summary[:200]}")
            else:
                lines.append(f"{i}. {str(row)[:200]}")
        return "\n".join(lines)

    def _format_step(self, step: Any, step_num: int) -> str:
        """格式化单个推理步骤。"""
        if isinstance(step, dict):
            action = step.get("action", step.get("thought", ""))
            result_text = step.get("result") or step.get("output") or ""
            text = f"[步骤 {step_num}] {action}"
            if result_text:
                text += f"\n结果: {result_text}"
            return text + "\n\n"
        return f"[步骤 {step_num}] {str(step)}\n\n"

    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """将文本分块（模拟流式输出）。"""
        if not text:
            return [""]
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    def _check_confidence(self, result: Any) -> Optional[Interrupt]:
        """检查结果置信度，低于阈值返回 HITL Interrupt。"""
        low_confidence_rows = []
        for row in result.rows:
            if isinstance(row, dict):
                conf = row.get("confidence")
                if isinstance(conf, (int, float)) and conf < self._confidence_threshold:
                    low_confidence_rows.append({
                        "id": row.get("id", "unknown"),
                        "confidence": conf,
                    })

        if not low_confidence_rows:
            return None

        return Interrupt(
            id=str(uuid.uuid4()),
            reason=InterruptReason.CONFIRMATION,
            message=(
                f"检测到 {len(low_confidence_rows)} 条低置信度结果"
                f"（置信度 < {self._confidence_threshold}），请确认是否采纳"
            ),
            metadata={
                "low_confidence_count": len(low_confidence_rows),
                "threshold": self._confidence_threshold,
                "items": low_confidence_rows[:10],  # 限制 10 条
            },
        )

    def _build_error_event(self, thread_id: str, run_id: str, message: str) -> Dict[str, Any]:
        """构建错误事件。"""
        from ..agui.agui_models import RunErrorEvent
        return RunErrorEvent(message=message, code="RETRIEVAL_ERROR").model_dump(
            by_alias=True, exclude_none=True
        )

    def _emit_query_audit(
        self,
        operator: str,
        workspace_id: str,
        query: str,
        mode: str,
        result: Any,
        interrupt_triggered: bool,
    ) -> None:
        """Iter 3.2 #5 查询审计埋点（fire-and-forget，不阻塞流式返回）。"""
        try:
            total = getattr(result, "total", 0) if not isinstance(result, dict) else result.get("total", 0)
            query_params = {
                "query": query[:100],  # 截断，不记全文（FR-013）
                "retrieval_type": mode,
                "workspace_id": workspace_id,
            }
            result_summary = {
                "count": total,
                "mode": mode,
                "interrupt_triggered": interrupt_triggered,
            }
            query_audit(
                operator=operator,
                query_params=query_params,
                result_summary=result_summary,
                workspace_id=workspace_id,
            )
        except Exception as exc:
            logger.warning("query_audit 埋点失败（不影响检索）: %s", exc)


# ------------------------------------------------------------------
# 模块级单例
# ------------------------------------------------------------------

_adapter_singleton: Optional[RetrievalAGUIAdapter] = None


def get_retrieval_agui_adapter() -> RetrievalAGUIAdapter:
    """返回 RetrievalAGUIAdapter 单例。"""
    global _adapter_singleton
    if _adapter_singleton is None:
        _adapter_singleton = RetrievalAGUIAdapter()
    return _adapter_singleton


__all__ = [
    "RetrievalAGUIAdapter",
    "CONFIDENCE_THRESHOLD",
    "get_retrieval_agui_adapter",
]
