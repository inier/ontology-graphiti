"""Iter 2.2: Celery worker configuration with three-tier priority queues.

Queue routing:
    high_priority — user-triggered, latency-sensitive (manual input, HITL)
    normal        — regular ingestion (news scrape, file upload)
    batch         — bulk/background (KB iteration, large document sets)

Graceful degradation:
    If celery is not installed, ``CELERY_AVAILABLE`` is False and
    ``get_celery_app()`` returns None. The dispatcher falls back to
    synchronous execution.
"""

import logging
from typing import Optional

from odap.infra.config_composer import get_config

logger = logging.getLogger("queue_worker")

# ------------------------------------------------------------------
# Queue name constants
# ------------------------------------------------------------------

QUEUE_HIGH_PRIORITY = "high_priority"
QUEUE_NORMAL = "normal"
QUEUE_BATCH = "batch"

_ALL_QUEUES = (QUEUE_HIGH_PRIORITY, QUEUE_NORMAL, QUEUE_BATCH)


# ------------------------------------------------------------------
# Celery availability check (graceful degradation)
# ------------------------------------------------------------------

CELERY_AVAILABLE = False
_celery_app_singleton = None

try:
    from celery import Celery
    CELERY_AVAILABLE = True
except ImportError as exc:
    Celery = None  # type: ignore[assignment, misc]
    logger.info("celery 未安装 (%s) — 队列任务将同步执行", exc)


def get_celery_app():
    """Return the singleton Celery app instance, or None if unavailable.

    The app is lazily created on first call. If celery is not installed,
    returns None — callers must check ``CELERY_AVAILABLE`` or handle None.
    """
    global _celery_app_singleton
    if not CELERY_AVAILABLE:
        return None
    if _celery_app_singleton is not None:
        return _celery_app_singleton

    redis_url = get_config("cache.redis_url", "redis://localhost:6379/0")

    app = Celery(
        "odap_queue",
        broker=redis_url,
        backend=redis_url,
        include=["odap.infra.queue.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        enable_utc=True,
        # Three-tier queue routing
        task_queues={
            QUEUE_HIGH_PRIORITY: {
                "exchange": QUEUE_HIGH_PRIORITY,
                "routing_key": QUEUE_HIGH_PRIORITY,
            },
            QUEUE_NORMAL: {
                "exchange": QUEUE_NORMAL,
                "routing_key": QUEUE_NORMAL,
            },
            QUEUE_BATCH: {
                "exchange": QUEUE_BATCH,
                "routing_key": QUEUE_BATCH,
            },
        },
        task_default_queue=QUEUE_NORMAL,
        task_default_routing_key=QUEUE_NORMAL,
        # Reliability
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    _celery_app_singleton = app
    logger.info("Celery app initialized (broker=%s)", redis_url)
    return app


def resolve_queue(priority: Optional[str]) -> str:
    """Resolve a priority string to a valid queue name.

    Args:
        priority: One of "high", "normal", "batch" (case-insensitive),
            or None/empty for default.

    Returns:
        One of QUEUE_HIGH_PRIORITY / QUEUE_NORMAL / QUEUE_BATCH.
    """
    if not priority:
        return QUEUE_NORMAL
    p = priority.lower().strip()
    if p in ("high", "high_priority", "urgent"):
        return QUEUE_HIGH_PRIORITY
    if p in ("batch", "low", "background"):
        return QUEUE_BATCH
    return QUEUE_NORMAL
