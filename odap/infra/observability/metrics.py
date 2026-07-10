"""Prometheus 指标定义与端点 — ADR-064

核心指标:
    - HTTP 请求：延迟直方图 + 错误计数器
    - Graphiti 查询：延迟 + 错误计数器
    - Skill 执行：延迟 + 错误计数器
    - OPA 策略评估：延迟 + 错误计数器
    - Agent 任务：延迟 + 状态计数器

若 prometheus-client 未安装，所有指标降级为空操作。
"""
import os
import logging
from typing import Optional, Callable

logger = logging.getLogger("odap.observability.metrics")

try:
    import prometheus_client
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY, multiprocess

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False


# ---------------------------------------------------------------------------
# 真实指标（仅当 prometheus-client 可用时创建）
# ---------------------------------------------------------------------------

class _NoopMetric:
    """空操作指标（降级用）"""
    def labels(self, **kwargs): return self
    def observe(self, amount): pass
    def inc(self, amount=1): pass
    def dec(self, amount=1): pass
    def set(self, value): pass


if _PROMETHEUS_AVAILABLE:
    _METRICS_PREFIX = "odap"

    http_request_duration_seconds = Histogram(
        f"{_METRICS_PREFIX}_http_request_duration_seconds",
        "HTTP 请求延迟",
        labelnames=["method", "endpoint", "status_code"],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    )
    http_requests_total = Counter(
        f"{_METRICS_PREFIX}_http_requests_total",
        "HTTP 请求总数",
        labelnames=["method", "endpoint", "status_code"],
    )
    http_request_errors_total = Counter(
        f"{_METRICS_PREFIX}_http_request_errors_total",
        "HTTP 请求错误数",
        labelnames=["method", "endpoint", "error_type"],
    )

    graphiti_query_duration_seconds = Histogram(
        f"{_METRICS_PREFIX}_graphiti_query_duration_seconds",
        "Graphiti 查询延迟",
        labelnames=["operation", "source"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    )
    graphiti_query_errors_total = Counter(
        f"{_METRICS_PREFIX}_graphiti_query_errors_total",
        "Graphiti 查询错误数",
        labelnames=["operation", "error_type"],
    )

    skill_execution_duration_seconds = Histogram(
        f"{_METRICS_PREFIX}_skill_execution_duration_seconds",
        "Skill 执行延迟",
        labelnames=["skill_name", "status"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    )
    skill_execution_total = Counter(
        f"{_METRICS_PREFIX}_skill_execution_total",
        "Skill 执行次数",
        labelnames=["skill_name", "status"],
    )

    opa_evaluation_duration_seconds = Histogram(
        f"{_METRICS_PREFIX}_opa_evaluation_duration_seconds",
        "OPA 策略评估延迟",
        labelnames=["package", "decision"],
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    )
    opa_evaluation_total = Counter(
        f"{_METRICS_PREFIX}_opa_evaluation_total",
        "OPA 策略评估次数",
        labelnames=["package", "decision"],
    )

    agent_mission_duration_seconds = Histogram(
        f"{_METRICS_PREFIX}_agent_mission_duration_seconds",
        "Agent 任务延迟",
        labelnames=["mission_type", "status"],
        buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    )
    agent_mission_total = Counter(
        f"{_METRICS_PREFIX}_agent_mission_total",
        "Agent 任务次数",
        labelnames=["mission_type", "status"],
    )

    # 运行时指标
    neo4j_pool_size = Gauge(
        f"{_METRICS_PREFIX}_neo4j_pool_size",
        "Neo4j 连接池当前大小",
        labelnames=["state"],  # active, idle, total
    )
    graph_node_count = Gauge(
        f"{_METRICS_PREFIX}_graph_node_count",
        "图谱节点数（估算）",
        labelnames=["workspace_id"],
    )
    registered_skills = Gauge(
        f"{_METRICS_PREFIX}_registered_skills",
        "已注册 Skill 数量",
    )
    active_tenants = Gauge(
        f"{_METRICS_PREFIX}_active_tenants",
        "活跃租户数",
    )

else:
    # 降级：所有指标为 noop
    _noop = _NoopMetric()
    http_request_duration_seconds = _noop
    http_requests_total = _noop
    http_request_errors_total = _noop
    graphiti_query_duration_seconds = _noop
    graphiti_query_errors_total = _noop
    skill_execution_duration_seconds = _noop
    skill_execution_total = _noop
    opa_evaluation_duration_seconds = _noop
    opa_evaluation_total = _noop
    agent_mission_duration_seconds = _noop
    agent_mission_total = _noop
    neo4j_pool_size = _noop
    graph_node_count = _noop
    registered_skills = _noop
    active_tenants = _noop


# ---------------------------------------------------------------------------
# /metrics 端点
# ---------------------------------------------------------------------------

def setup_metrics(enable_multiprocess: bool = False) -> bool:
    """初始化 Prometheus 指标系统。

    Args:
        enable_multiprocess: 是否启用多进程模式（uvicorn --workers > 1 时需开启）
            - 需设置环境变量 PROMETHEUS_MULTIPROC_DIR
            - 需安装 prometheus-client[multiprocess]
    Returns:
        True if initialized, False if packages not available
    """
    if not _PROMETHEUS_AVAILABLE:
        logger.info("prometheus-client 未安装，指标功能已禁用")
        return False

    if enable_multiprocess:
        mp_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")
        if mp_dir:
            os.makedirs(mp_dir, exist_ok=True)
            prometheus_client.values.ValueClass = prometheus_client.values.MultiProcessValue()
            logger.info(f"Prometheus 多进程模式已启用: dir={mp_dir}")

    logger.info("Prometheus 指标系统已初始化")
    return True


async def metrics_endpoint() -> bytes:
    """生成 /metrics 响应（Prometheus text format）。

    用法:
        from fastapi import Response
        @app.get("/metrics")
        async def metrics():
            return Response(content=await metrics_endpoint(), media_type="text/plain")
    """
    if _PROMETHEUS_AVAILABLE:
        return generate_latest(REGISTRY)
    return b"# prometheus-client not installed\n"


def get_metrics_app() -> Optional[Callable]:
    """返回一个 ASGI app for /metrics（用于纯指标端点服务器）。

    返回 None 表示 prometheus-client 不可用。
    """
    if not _PROMETHEUS_AVAILABLE:
        return None
    from prometheus_client import make_asgi_app
    return make_asgi_app()
