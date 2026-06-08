"""AG-UI Transport Layer latency benchmark.

Per plan v2.0 T048: 目标 SSE TTFB < 200ms (P95)。

本测试绕开 HTTP/JWT 鉴权，直接测量 AG-UI transport 层（dataclass → dict → SSE 编码）
的纯协议处理延迟。这是 SSE TTFB 的核心开销，比 HTTP 端到端测量更纯净。

测试方法：
1. 构造各类 OpenHarness StreamEvent mock
2. 走 to_agui_events + encode_sse 路径
3. 测量 N 次调用的延迟
4. 报告：min / p50 / p95 / max

成功条件：单次 9 事件 run 翻译 < 50ms（p95），单事件 encode < 100us
"""

from __future__ import annotations

import time
import statistics
import sys
import os
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from odap.infra.openharness.agui.agui_extensions import (
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    StepFinishedEvent,
    MessagesSnapshotEvent,
)
from odap.infra.openharness.agui.agui_transport import (
    TransportState,
    encode_sse,
    to_agui_events,
)


# === Mock OpenHarness 原生事件（duck-typed） ===

@dataclass
class _MockTextDelta:
    """模拟 openharness.AssistantTextDelta"""
    text: str


@dataclass
class _MockToolStart:
    """模拟 openharness.ToolExecutionStarted"""
    tool_name: str
    tool_input: dict


@dataclass
class _MockToolEnd:
    """模拟 openharness.ToolExecutionCompleted"""
    tool_name: str
    tool_input: dict
    output: dict


def _measure_translation_loop(n: int = 200) -> list[float]:
    """模拟一次完整 run 的事件序列，测量每次翻译延迟。"""
    samples = []
    state = TransportState(thread_id="perf-t", run_id="perf-r", model="gpt-4o")

    # 完整 12 事件 run：包含 lifecycle + step + text + tool + snapshot
    events = [
        RunStartedEvent(thread_id="perf-t", run_id="perf-r"),
        StepFinishedEvent(step_name="init"),
        TextMessageStartEvent(message_id="m-1", role="assistant"),
        _MockTextDelta(text="你好"),
        _MockTextDelta(text="，"),
        _MockTextDelta(text="世界"),
        TextMessageEndEvent(message_id="m-1"),
        _MockToolStart(tool_name="query", tool_input={"q": "test"}),
        _MockToolEnd(tool_name="query", tool_input={"q": "test"}, output={"result": 42}),
        MessagesSnapshotEvent(messages=[{"role": "user", "content": "test"}]),
        StepFinishedEvent(step_name="finalize"),
        RunFinishedEvent(thread_id="perf-t", run_id="perf-r", outcome="success"),
    ]

    for _ in range(n):
        t0 = time.perf_counter()
        for ev in events:
            out = to_agui_events(ev, state)
            if out:
                encode_sse(out[0])
        samples.append((time.perf_counter() - t0) * 1000.0)  # ms
    return samples


def test_translation_p95_under_50ms_for_full_run(capsys):
    """完整 12 事件 run 的 transport 翻译应在 50ms 内完成（p95）。"""
    samples = _measure_translation_loop(n=200)
    samples.sort()
    p50 = statistics.median(samples)
    p95 = samples[int(len(samples) * 0.95) - 1]
    p99 = samples[int(len(samples) * 0.99) - 1]
    avg = statistics.mean(samples)
    mn, mx = samples[0], samples[-1]

    with capsys.disabled():
        print(
            f"\n=== AG-UI Transport Latency (full 12-event run, n={len(samples)}) ===\n"
            f"  min: {mn:8.3f}ms\n"
            f"  p50: {p50:8.3f}ms\n"
            f"  p95: {p95:8.3f}ms  (target: < 50ms)\n"
            f"  p99: {p99:8.3f}ms\n"
            f"  max: {mx:8.3f}ms\n"
            f"  avg: {avg:8.3f}ms\n"
        )

    # 软阈值：完整 12 事件 run p95 < 50ms
    assert p95 < 50.0, f"p95 transport latency = {p95:.3f}ms 超出 50ms 阈值"


def test_sse_encode_throughput(capsys):
    """SSE 编码吞吐量：单事件 encode_sse 应 < 100us。"""
    state = TransportState(thread_id="t", run_id="r", model="gpt-4o")
    event = RunStartedEvent(thread_id="t", run_id="r")
    event_dict = to_agui_events(event, state)[0]

    n = 5000
    t0 = time.perf_counter()
    for _ in range(n):
        encode_sse(event_dict)
    elapsed = (time.perf_counter() - t0) * 1000.0

    per_event_us = (elapsed * 1000.0) / n
    with capsys.disabled():
        print(
            f"\n=== SSE Encode Throughput ===\n"
            f"  Total:   {elapsed:.2f}ms for {n} events\n"
            f"  Per evt: {per_event_us:.2f}us  (target: < 100us)\n"
        )
    assert per_event_us < 100.0, f"SSE encode = {per_event_us:.2f}us/event 超出 100us 阈值"


def test_pydantic_serialization_speed(capsys):
    """Pydantic .model_dump() 序列化速度 — 验证模型 JSON 编码无瓶颈。"""
    from odap.infra.openharness.agui.agui_models import (
        RunAgentInput,
        Message,
        Tool,
    )

    n = 1000
    t0 = time.perf_counter()
    for i in range(n):
        req = RunAgentInput(
            threadId=f"t-{i}",
            runId=f"r-{i}",
            workspaceId="ws-1",
            messages=[Message(id=f"m{i}", role="user", content="你好")],
            tools=[Tool(name="test", description="test tool")],
        )
        req.model_dump(by_alias=True, exclude_none=True)
    elapsed = (time.perf_counter() - t0) * 1000.0

    per_req_us = (elapsed * 1000.0) / n
    with capsys.disabled():
        print(
            f"\n=== Pydantic Serialization ===\n"
            f"  Total:   {elapsed:.2f}ms for {n} requests\n"
            f"  Per req: {per_req_us:.2f}us  (target: < 1ms)\n"
        )
    assert per_req_us < 1000.0, f"Pydantic dump = {per_req_us:.2f}us/req 超出 1ms 阈值"
