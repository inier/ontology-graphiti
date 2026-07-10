"""Span 辅助工具 — ADR-064

为四大核心模块提供统一的 span 创建与度量收集。

用法:
    # Agent 任务
    with agent_span("execute_mission", mission_type="intel") as span:
        result = await swarm.execute_mission(...)
        span.set_attribute("mission.status", "success")

    # Graphiti 查询
    with graphiti_span("search", source="graphiti") as span:
        edges = await graph.search(query, limit)
        span.set_attribute("graphiti.result_count", len(edges))

    # Skill 执行
    with skill_span("radar_search") as span:
        output = await skill.run(input_data)
        span.set_attribute("skill.duration_ms", elapsed)

    # OPA 评估
    with opa_span("check_permission", package="domain") as span:
        result = await opa.check_permission(...)
        span.set_attribute("opa.result", str(result))
"""
import time
import logging
from contextlib import contextmanager
from typing import Optional, Generator

from odap.infra.observability.setup import (
    get_tracer,
    get_current_trace_id,
    get_current_span_id,
    OBSERVABILITY_AVAILABLE,
)
from odap.infra.observability.metrics import (
    graphiti_query_duration_seconds,
    graphiti_query_errors_total,
    skill_execution_duration_seconds,
    skill_execution_total,
    opa_evaluation_duration_seconds,
    opa_evaluation_total,
    agent_mission_duration_seconds,
    agent_mission_total,
)

logger = logging.getLogger("odap.observability.instruments")


@contextmanager
def agent_span(
    operation: str,
    mission_type: str = "unknown",
    attributes: Optional[dict] = None,
) -> Generator:
    """为 Agent 任务创建一个 tracing span + 收集延迟指标。

    Args:
        operation: 操作名（如 "execute_mission", "execute_streaming", "observe"）
        mission_type: 任务类型标识
        attributes: 附加 span attributes

    Yields:
        OTel Span 对象（或 NoopSpan）
    """
    tracer = get_tracer("odap.agent")
    start = time.monotonic()
    status = "success"
    try:
        with tracer.start_as_current_span(f"agent.{operation}") as span:
            if span.is_recording():
                span.set_attribute("agent.operation", operation)
                span.set_attribute("agent.mission_type", mission_type)
                span.set_attribute("agent.trace_id", get_current_trace_id())
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
            yield span
    except Exception:
        status = "error"
        raise
    finally:
        elapsed = time.monotonic() - start
        agent_mission_duration_seconds.labels(
            mission_type=mission_type, status=status
        ).observe(elapsed)
        agent_mission_total.labels(
            mission_type=mission_type, status=status
        ).inc()


@contextmanager
def graphiti_span(
    operation: str,
    source: str = "graphiti",
    attributes: Optional[dict] = None,
) -> Generator:
    """为 Graphiti 操作创建一个 tracing span + 收集延迟指标。

    Args:
        operation: graphiti.search / graphiti.add_episode / graphiti.traverse
        source: 数据来源标识
        attributes: 附加 span attributes
    """
    tracer = get_tracer("odap.graphiti")
    start = time.monotonic()
    status = "success"
    try:
        with tracer.start_as_current_span(f"graphiti.{operation}") as span:
            if span.is_recording():
                span.set_attribute("graphiti.operation", operation)
                span.set_attribute("graphiti.source", source)
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
            yield span
    except Exception:
        status = "error"
        graphiti_query_errors_total.labels(
            operation=operation, error_type=type(Exception).__name__
        ).inc()
        raise
    finally:
        elapsed = time.monotonic() - start
        graphiti_query_duration_seconds.labels(
            operation=operation, source=source
        ).observe(elapsed)


@contextmanager
def skill_span(
    skill_name: str,
    attributes: Optional[dict] = None,
) -> Generator:
    """为 Skill 执行创建一个 tracing span + 收集延迟指标。

    Args:
        skill_name: Skill 名称（如 "radar_search", "threat_assess"）
        attributes: 附加 span attributes
    """
    tracer = get_tracer("odap.skill")
    start = time.monotonic()
    status = "success"
    try:
        with tracer.start_as_current_span(f"skill.{skill_name}") as span:
            if span.is_recording():
                span.set_attribute("skill.name", skill_name)
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
            yield span
    except Exception:
        status = "error"
        raise
    finally:
        elapsed = time.monotonic() - start
        skill_execution_duration_seconds.labels(
            skill_name=skill_name, status=status
        ).observe(elapsed)
        skill_execution_total.labels(
            skill_name=skill_name, status=status
        ).inc()


@contextmanager
def opa_span(
    operation: str,
    package: str = "domain",
    attributes: Optional[dict] = None,
) -> Generator:
    """为 OPA 策略评估创建一个 tracing span + 收集延迟指标。

    Args:
        operation: check_permission / check_package_permission
        package: OPA 包名
        attributes: 附加 span attributes
    """
    tracer = get_tracer("odap.opa")
    start = time.monotonic()
    decision = "unknown"
    try:
        with tracer.start_as_current_span(f"opa.{operation}") as span:
            if span.is_recording():
                span.set_attribute("opa.operation", operation)
                span.set_attribute("opa.package", package)
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
            yield span
    except Exception:
        decision = "error"
        raise
    finally:
        elapsed = time.monotonic() - start
        opa_evaluation_duration_seconds.labels(
            package=package, decision=decision
        ).observe(elapsed)
        opa_evaluation_total.labels(
            package=package, decision=decision
        ).inc()


# ---------------------------------------------------------------------------
# 追踪上下文桥接：为日志/审计注入 trace/span id
# ---------------------------------------------------------------------------

def inject_trace_context(log_record_extra: dict) -> dict:
    """向日志/审计记录的 extra 字段注入当前 OTel trace 上下文。

    用法:
        logger.info("processing", extra=inject_trace_context({
            "workspace_id": ws_id,
            "operation": "search",
        }))

    Args:
        log_record_extra: 已有的 extra dict

    Returns:
        追加了 trace_id / span_id 的 dict
    """
    trace_id = get_current_trace_id()
    span_id = get_current_span_id()
    if trace_id:
        log_record_extra["trace_id"] = trace_id
        log_record_extra["span_id"] = span_id
    return log_record_extra
