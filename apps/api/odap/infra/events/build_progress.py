"""本体构建进度事件发射器（领域事件便捷封装）.

背景（Stage G · C2-3 烧账）：
    ``emit_build_progress`` 原本定义在 ``odap.web.ws.routes`` 中，与 WebSocket
    端点物理同处一文件。但它本身**只依赖** ``odap.infra.events.event_bus``
    （infra 叶子层），与 web 层无任何耦合——纯属"工具函数放错层"。

    两个 biz 消费者（construction.ingestion.services.unified_ingest_service /
    design.services.ingest_service）通过 ``from odap.web.ws.routes import
    emit_build_progress`` 反向 reach-up 到 web 层，构成 C2 契约的 ignore 债。

    本模块把该函数**逐字下沉**到 infra/events 层（biz 的合法下游），
    使 biz→infra 成为向下的合法依赖，C2 债清零。行为、签名、事件负载
    与原实现完全一致，无任何兜底/降级逻辑（遵守规则 14）。

    ``odap.web.ws.routes`` 保留对本函数的再导出 shim，确保任何历史
    ``from odap.web.ws.routes import emit_build_progress`` 调用点仍可解析
    （web→infra 为向下依赖，不产生 C2 边）。
"""

from __future__ import annotations

from odap.infra.events.event_bus import get_event_bus


async def emit_build_progress(
    stage: str,
    progress: float,
    message: str,
    ingest_id: str = "",
    scenario_id: str = "",
):
    """向所有构建进度订阅者推送进度事件。

    此函数可被 IngestService / PipelineService 的 progress_callback 调用。
    通过 DomainEventBus 发射 ``ontology:build_progress`` 事件，
    由 ``odap.web.ws.routes.ontology_build_progress`` WebSocket 端点转发给前端。
    """
    bus = get_event_bus()
    await bus.emit("ontology:build_progress", {
        "stage": stage,
        "progress": progress,
        "message": message,
        "ingest_id": ingest_id,
        "scenario_id": scenario_id,
    })


__all__ = ["emit_build_progress"]
