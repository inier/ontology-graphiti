"""
BlueprintRuntimeEngine 默认节点处理器（ADR-074 接线层）。

将蓝图可视化节点（BlueprintNodeType）桥接到 L2 Construction 的真实能力：

    data_source  -> UnifiedIngestionService（纯采集，不做抽取，ADR-074 §1.3）
    transform    -> ExtractService（Hyper-Extract 全链路抽取，ADR-074 §2）
    ontology     -> OntologyBuilderService（TBox/ABox 构建/映射）

所有 handler 签名统一为 ``handler(node_id, node_type, execution) -> Dict``，
与 ``BlueprintRuntimeEngine._advance_execution`` 的调用约定一致。

设计要点：
    - 处理器是"编排引用"，只负责把蓝图节点的 config 翻译成对既有服务的调用，
      不在此处重新实现摄入/抽取/构建逻辑。
    - 真实服务多为 async，这里用 ``asyncio.run`` 包装（与
      ``UnifiedIngestionService.generate_random_events`` 等既有风格一致）。
    - 每个 handler 内部做 try/except，把异常转成 dict 返回（含 status=error），
      避免运行时因为某个节点失败而抛出未捕获异常。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict

logger = logging.getLogger("blueprint_node_handlers")


def _node_config(execution, node_id: str) -> Dict[str, Any]:
    """从执行上下文中取回当前节点的 config。

    ``BlueprintExecution`` 本身不直接持有节点 config；这里从执行对象的
    metadata.nodes 反查（``BlueprintRuntimeEngine.start_execution`` 已把
    ``metadata`` 透传进来），调用方可在 metadata.nodes[node_id].config
    放置节点配置。
    """
    meta = getattr(execution, "metadata", {}) or {}
    nodes_meta = meta.get("nodes", {}) if isinstance(meta, dict) else {}
    if isinstance(nodes_meta, dict) and node_id in nodes_meta:
        node_meta = nodes_meta.get(node_id) or {}
        return node_meta.get("config") or {}
    return {}


def _run(coro) -> Any:
    """统一执行 async 协程（无事件循环时用 asyncio.run 包装）。"""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # 已存在运行中的事件循环（如被 FastAPI 调用），退化为新建 loop 执行
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def make_data_source_handler() -> Callable:
    """data_source 节点 -> 纯采集（无 LLM 抽取）。

    按 config.source_type 分发到 UnifiedIngestionService：
        natural_language -> ingest_from_natural_language
        json             -> ingest_from_json
        manual           -> ingest_from_manual
        database         -> ingest_from_database

    返回 ingest_id，供下游 transform 节点消费。
    """

    def handler(node_id: str, node_type: str, execution) -> Dict[str, Any]:
        from odap.biz.core.ontology.construction.ingestion.services import (
            get_unified_ingestion_service,
        )

        config = _node_config(execution, node_id)
        source_type = config.get("source_type", "natural_language")
        scenario_id = config.get("scenario_id")
        workspace_id = config.get("workspace_id", "default")

        try:
            svc = get_unified_ingestion_service()
            if source_type == "json":
                raw = config.get("content", config.get("raw_json", ""))
                result = _run(svc.ingest_from_json(raw, scenario_id=scenario_id))
            elif source_type == "manual":
                form_data = config.get("content", {})
                result = _run(
                    svc.ingest_from_manual(form_data, scenario_id=scenario_id)
                )
            elif source_type == "database":
                connection_id = config.get("connection_id", "")
                table_patterns = config.get("table_patterns")
                result = _run(
                    svc.ingest_from_database(
                        connection_id,
                        table_patterns=table_patterns,
                        scenario_id=scenario_id,
                        workspace_id=workspace_id,
                    )
                )
            else:  # natural_language
                text = config.get("content", "")
                result = _run(
                    svc.ingest_from_natural_language(text, scenario_id=scenario_id)
                )

            return {
                "status": "success",
                "ingest_id": result,
                "source_type": source_type,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("data_source handler failed for node=%s: %s", node_id, exc)
            return {"status": "error", "error": str(exc)}

    return handler


def make_transform_handler() -> Callable:
    """transform 节点 -> Hyper-Extract 全链路抽取（ADR-074 §2）。

    调用 ExtractService.extract_from_nl 完成
    评估 → 多模板解析 → 合并映射 → LLM 补充 → 冲突检测 的完整链路，
    产出映射到 ODAP 5 类的 Knowledge Abstract，供 ontology 节点消费。

    需要 config.ontology_id 作为目标本体；文本优先取 config.content，
    其次从上游 data_source 节点产出里取。
    """

    def handler(node_id: str, node_type: str, execution) -> Dict[str, Any]:
        config = _node_config(execution, node_id)
        ontology_id = config.get("ontology_id", "")
        text = config.get("content", config.get("text", ""))

        upstream = _upstream_output(execution, "data_source")
        if upstream:
            text = text or upstream.get("content") or upstream.get("text") or text

        if not text:
            return {"status": "error", "error": "transform 节点缺少待抽取文本"}
        if not ontology_id:
            return {"status": "error", "error": "transform 节点缺少 ontology_id 配置"}

        try:
            from odap.biz.data.hyper_extract.services.extract_service import (
                ExtractService,
            )

            svc = ExtractService()
            result = _run(
                svc.extract_from_nl(
                    text=text,
                    ontology_id=ontology_id,
                    template_id=config.get("template_id"),
                    mode=config.get("mode"),
                )
            )
            if result.get("status") != "ok":
                return {"status": "error", "error": result.get("message", "抽取失败")}

            return {
                "status": "success",
                "session_id": result.get("session_id"),
                "result": result.get("result", {}),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("transform handler failed for node=%s: %s", node_id, exc)
            return {"status": "error", "error": str(exc)}

    return handler


def make_ontology_handler() -> Callable:
    """ontology 节点 -> 本体构建/映射。

    消费上游 transform 节点产出的 Knowledge Abstract（ODAP 5 类），
    调用 OntologyBuilderService.build_ontology 构建本体实例（ABox）。

    需要 config.scenario_id / config.ontology_id。
    """

    def handler(node_id: str, node_type: str, execution) -> Dict[str, Any]:
        config = _node_config(execution, node_id)
        scenario_id = config.get("scenario_id", "default")
        workspace_id = config.get("workspace_id", "default")
        ontology_id = config.get("ontology_id")

        try:
            from odap.biz.core.ontology.construction.pipeline.services import (
                get_builder_service,
            )

            builder = get_builder_service()
            result = _run(
                builder.build_ontology(
                    document=None,
                    scenario_id=scenario_id,
                    workspace_id=workspace_id,
                    create_new_version=True,
                    ontology_id=ontology_id,
                )
            )
            return {
                "status": "success",
                "build_id": result.get("build_id") if isinstance(result, dict) else None,
                "detail": result,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("ontology handler failed for node=%s: %s", node_id, exc)
            return {"status": "error", "error": str(exc)}

    return handler


def _upstream_output(execution, node_type: str) -> Dict[str, Any]:
    """从执行对象中查找第一个指定类型的已完成节点的输出。"""
    node_executions = getattr(execution, "node_executions", {}) or {}
    for ne in node_executions.values():
        if getattr(ne, "node_type", "") == node_type and getattr(ne, "output", None):
            return ne.output
    return {}


def register_default_node_handlers(runtime) -> None:
    """向 BlueprintRuntimeEngine 注册 ADR-074 数据流的默认处理器（兜底语义）。

    仅对"尚未注册 handler 的节点类型"注入默认实现，不覆盖调用方显式注册的
    handler（setdefault 语义）。这样既保证蓝图默认执行能走真实能力，
    又保留测试/调用方自定义 handler 的自由度。

    默认处理器：
        data_source -> 纯采集（UnifiedIngestionService）
        transform   -> Hyper-Extract 抽取（ExtractService）
        ontology    -> 本体构建（OntologyBuilderService）
    """
    defaults = {
        "data_source": make_data_source_handler(),
        "transform": make_transform_handler(),
        "ontology": make_ontology_handler(),
    }
    for node_type, handler in defaults.items():
        if node_type not in runtime._node_handlers:
            runtime.register_node_handler(node_type, handler)
