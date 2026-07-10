"""OpenTelemetry SDK 初始化 — ADR-064

支持:
    - OTLP HTTP exporter（生产）
    - Console exporter（开发，OTEL_EXPORTER_OTLP_ENDPOINT 为空时自动启用）
    - FastAPI 自动 instrumentation
    - 无依赖优雅降级（OTEL 包未安装时所有 API 降级为 noop）
"""
import os
import logging
from typing import Optional

logger = logging.getLogger("odap.observability")

# 检测 OTel 依赖是否可用
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.trace import SpanContext, NonRecordingSpan

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    logger.debug("OpenTelemetry SDK 不可用，追踪功能降级为 noop")

OBSERVABILITY_AVAILABLE = _OTEL_AVAILABLE

# 全局 tracer 实例
_tracer: Optional["trace.Tracer"] = None
_tracer_provider: Optional["TracerProvider"] = None


def setup_observability(
    service_name: str = "odap",
    otlp_endpoint: Optional[str] = None,
    sample_ratio: float = 1.0,
) -> bool:
    """初始化 OpenTelemetry SDK。

    环境变量优先级:
        OTEL_SERVICE_NAME          → service_name
        OTEL_EXPORTER_OTLP_ENDPOINT → otlp_endpoint (有值则启用 OTLP，否则 console)
        OTEL_SAMPLE_RATIO          → sample_ratio

    Args:
        service_name: 服务名，默认 "odap"
        otlp_endpoint: OTLP collector endpoint，为空则使用 console exporter
        sample_ratio: 采样率，1.0 = 全量

    Returns:
        True if OTel initialized, False if noop (packages not installed)
    """
    global _tracer, _tracer_provider

    if not _OTEL_AVAILABLE:
        logger.info("OpenTelemetry SDK 未安装，追踪功能已禁用")
        return False

    service_name = os.getenv("OTEL_SERVICE_NAME", service_name)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", otlp_endpoint)

    try:
        sample_ratio_str = os.getenv("OTEL_SAMPLE_RATIO")
        if sample_ratio_str:
            sample_ratio = float(sample_ratio_str)
    except (ValueError, TypeError):
        pass

    resource = Resource.create({SERVICE_NAME: service_name})

    _tracer_provider = TracerProvider(
        resource=resource,
        sampler=trace.sampling.TraceIdRatioBased(sample_ratio),
    )

    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        _tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info(f"OTel OTLP exporter 已配置: {otlp_endpoint}")
    else:
        console_exporter = ConsoleSpanExporter()
        _tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("OTel Console exporter 已配置（开发模式）")

    trace.set_tracer_provider(_tracer_provider)
    _tracer = trace.get_tracer(__name__)
    logger.info(
        f"OpenTelemetry 已初始化: service={service_name}, "
        f"sample_ratio={sample_ratio}, exporter={'otlp' if otlp_endpoint else 'console'}"
    )
    return True


def get_tracer(name: str = "odap") -> "trace.Tracer":
    """获取命名 tracer。

    若 OTel 不可用，返回 noop tracer（所有 span 操作均为空）。
    """
    global _tracer
    if _tracer is not None:
        return _tracer
    if _OTEL_AVAILABLE:
        return trace.get_tracer(name)
    # noop fallback: use a dummy
    return _NoopTracer()


def get_current_trace_id() -> str:
    """从当前 OTel context 获取 trace_id（hex 格式）。

    Returns:
        trace_id hex string，或空字符串（无活跃 span）
    """
    if not _OTEL_AVAILABLE:
        return ""
    current_span = trace.get_current_span()
    if current_span and current_span.get_span_context().is_valid:
        return format(current_span.get_span_context().trace_id, "032x")
    return ""


def get_current_span_id() -> str:
    """从当前 OTel context 获取 span_id（hex 格式）。

    Returns:
        span_id hex string，或空字符串（无活跃 span）
    """
    if not _OTEL_AVAILABLE:
        return ""
    current_span = trace.get_current_span()
    if current_span and current_span.get_span_context().is_valid:
        return format(current_span.get_span_context().span_id, "016x")
    return ""


def _get_provider() -> Optional["TracerProvider"]:
    """获取全局 TracerProvider（仅供内部使用，如手动 shutdown）。"""
    global _tracer_provider
    return _tracer_provider


def shutdown_observability():
    """优雅关闭 OTel SDK，flush 所有待发送 span。"""
    global _tracer_provider
    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        logger.info("OpenTelemetry SDK 已关闭")
        _tracer_provider = None


# ---------------------------------------------------------------------------
# Noop fallback
# ---------------------------------------------------------------------------

class _NoopSpan:
    """无操作 span，模拟 OTel span 接口（关键方法）。"""
    def __init__(self, *args, **kwargs): pass
    def set_attribute(self, k, v): pass
    def set_status(self, s): pass
    def record_exception(self, e): pass
    def add_event(self, name, attributes=None): pass
    def end(self, end_time=None): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def is_recording(self): return False


class _NoopTracer:
    """无操作 tracer，所有 start_as_current_span 返回 _NoopSpan。"""
    def start_as_current_span(self, name, **kwargs):
        return _NoopSpan()
    def start_span(self, name, **kwargs):
        return _NoopSpan()
