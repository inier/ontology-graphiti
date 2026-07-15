"""ODAP 可观测性模块 — ADR-064

提供统一的 OpenTelemetry 追踪、Prometheus 指标、结构化日志桥接。

导出:
    setup_observability()     — 初始化 OTel SDK + Prometheus 端点
    TraceMiddleware           — FastAPI 中间件（trace_id 注入/提取）
    get_tracer()              — 获取命名 tracer
    get_current_trace_id()    — 从 OTel context 获取当前 trace_id
    get_current_span_id()     — 从 OTel context 获取当前 span_id
"""
from odap.infra.observability.setup import (
    setup_observability,
    get_tracer,
    get_current_trace_id,
    get_current_span_id,
    OBSERVABILITY_AVAILABLE,
)
from odap.infra.observability.middleware import TraceMiddleware
from odap.infra.observability.metrics import (
    setup_metrics,
    http_request_duration_seconds,
    graphiti_query_duration_seconds,
    skill_execution_duration_seconds,
    opa_evaluation_duration_seconds,
    agent_mission_duration_seconds,
)

__all__ = [
    "setup_observability",
    "get_tracer",
    "get_current_trace_id",
    "get_current_span_id",
    "OBSERVABILITY_AVAILABLE",
    "TraceMiddleware",
    "setup_metrics",
    "http_request_duration_seconds",
    "graphiti_query_duration_seconds",
    "skill_execution_duration_seconds",
    "opa_evaluation_duration_seconds",
    "agent_mission_duration_seconds",
]
