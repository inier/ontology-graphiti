"""异步任务定义。

W0-2 / W0-3（SPEC-v2 §2.1、§11）整改要点：
  1. `generate_graph_task` 原为 `time.sleep(10)` + 硬编码 `entities_generated=100 /
     relations_generated=150` 的伪实现 —— 已删除。真实图谱抽取能力当前**不存在**，
     故改为：注册表中有真实抽取 provider 则真实调用；否则显式抛 `NotImplementedError`
     并带 `error_code=GRAPH_EXTRACTOR_NOT_IMPLEMENTED`，由路由层翻译为 501。
     严禁返回假数字（SPEC §10「不允许伪实现」）。
  2. `process_file_upload_task` 原为 `time.sleep(3)` 解析后不落库 —— 已改为真实落库
     （复用既有 ingest 存储 `IngestService().storage.add_scenario_document`），
     无 scenario_id / 场景不存在 / 落库失败均显式失败，不假成功。
  3. 三处裸 `except` 一律记录 `error_code` + 具体异常类型与消息（禁止模糊文案），
     并修正缺 `f` 前缀的 f-string（`"{exc}"` 不会被插值）。

图谱抽取 provider 契约（未来接入真实能力时注册到 `odap.infra.providers`）：

    register_provider("graph_entity_extractor", factory)
    # factory() -> 对象，需实现：
    #   extract(scenario_id: str, config: dict) -> {
    #       "entities_generated": int, "relations_generated": int, "component_version": str
    #   }
    # 计数必须来自真实写入结果，禁止估算或常量。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from odap.celery_app import celery_app
from odap.infra.data_pipeline.file_parsers import parse_uploaded_file

logger = logging.getLogger(__name__)

#: 图谱抽取 provider 的注册名（未注册 = 真实能力不存在，任务必须 501）。
GRAPH_EXTRACTOR_PROVIDER = "graph_entity_extractor"

#: 明确的错误码（禁止 "处理失败" 式模糊文案，SPEC §5 错误契约 / AC-56）。
ERR_TASK_FAILED = "INGEST_TASK_FAILED"
ERR_SCENARIO_REQUIRED = "SCENARIO_REQUIRED"
ERR_SCENARIO_NOT_FOUND = "SCENARIO_NOT_FOUND"
ERR_PERSIST_FAILED = "SCENARIO_PERSIST_FAILED"
ERR_GRAPH_NOT_IMPLEMENTED = "GRAPH_EXTRACTOR_NOT_IMPLEMENTED"
ERR_GRAPH_FAILED = "GRAPH_GENERATION_FAILED"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _failure(task_id: str, error_code: str, exc: Optional[BaseException] = None,
             message: str = "") -> Dict[str, Any]:
    """构造显式失败结果（含 error_code 与具体原因）。"""
    detail = message or (f"{type(exc).__name__}: {exc}" if exc is not None else "")
    return {
        "task_id": task_id,
        "status": "failed",
        "error_code": error_code,
        "error": detail,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 场景文档落库（真实 ingest 存储；不吞异常）
# ─────────────────────────────────────────────────────────────────────────────

def _get_ingest_storage():
    """取既有 ingest 存储（真实 SQLite 落库路径）。

    经 ontology 公共门面取 IngestService —— 跨域只走 public 门面（C3）。
    """
    from odap.biz.core.ontology.public import IngestService
    return IngestService().storage


def _persist_scenario_document(scenario_id: str, doc: Dict[str, Any]) -> int:
    """把解析结果写入场景文档表，返回落库行 id。

    失败必须上抛（由调用方翻译为显式失败），禁止静默丢弃数据。
    """
    storage = _get_ingest_storage()
    scenario = storage.get_scenario(scenario_id)
    if not scenario:
        raise LookupError(f"scenario {scenario_id} 不存在，拒绝写入孤儿文档")
    return int(storage.add_scenario_document(scenario_id, doc) or 0)


def _save_to_scenario(scenario_id: str, doc_type: str, data: Dict[str, Any]) -> int:
    """保存数据到场景（真实落库）。"""
    doc = {
        "doc_id": f"{doc_type}-{int(time.time() * 1000)}",
        "meta": {"doc_type": doc_type, "data": data},
        "entities": [],
        "events": [],
        "relations": [],
        "created_at": _now_iso(),
    }
    return _persist_scenario_document(scenario_id, doc)


# 文件解析已抽到 infra/data_pipeline/file_parsers（纯函数，无 IO），本模块只做编排与落库

# ─────────────────────────────────────────────────────────────────────────────
# Celery 任务
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task
def process_ingest_task(task_id, ingest_type, data, scenario_id=None):
    """处理数据摄入任务（真实落库）。"""
    try:
        result = {
            "task_id": task_id,
            "ingest_type": ingest_type,
            "status": "completed",
            "processed_count": 1,
            "scenario_id": scenario_id,
        }

        if ingest_type == "text":
            result["content_length"] = len(data.get("text", ""))
            if scenario_id:
                _save_to_scenario(scenario_id, "text", data)

        elif ingest_type == "news":
            result["url"] = data.get("url", "")
            if data.get("url") and scenario_id:
                from odap.infra.utils.web_scraper import WebScraper

                news_data = WebScraper().scrape_news(data.get("url"))
                if news_data:
                    result["title"] = news_data.get("title", "")
                    result["content_length"] = len(news_data.get("content", ""))
                    _save_to_scenario(scenario_id, "news", news_data)
                    result["processed_count"] = 1

        elif ingest_type == "random":
            count = data.get("count", 10)
            result["generated_count"] = count
            if scenario_id:
                from odap.infra.utils.data_generator import DataGenerator

                sample_data = DataGenerator().generate_sample_data(count)
                _save_to_scenario(scenario_id, "random", sample_data)
                result["processed_count"] = len(sample_data.get("entities", []))

        elif ingest_type == "manual":
            result["data_type"] = data.get("type", "entity")
            if scenario_id:
                _save_to_scenario(scenario_id, "manual", data)

        elif ingest_type == "file":
            result["filename"] = data.get("filename", "")
            result["file_size"] = data.get("file_size", 0)

        return result
    except Exception as exc:  # noqa: BLE001 - 任务边界必须兜底并显式记录
        logger.error(
            "process_ingest_task failed: error_code=%s task_id=%s ingest_type=%s "
            "scenario_id=%s error_type=%s error=%s",
            ERR_TASK_FAILED, task_id, ingest_type, scenario_id,
            type(exc).__name__, exc, exc_info=True,
        )
        return _failure(task_id, ERR_TASK_FAILED, exc)


def graph_generation_capability() -> Dict[str, Any]:
    """探测真实图谱抽取能力是否可用。

    Returns:
        {"available": bool, "error_code": str|None, "reason": str}

    说明：当前仓库**没有**「场景文档 → 实体/关系抽取」的真实实现（只有把已抽取的
    实体写入 Graphiti 的 `ScenarioStore.sync_to_graphiti`）。因此默认不可用，
    必须显式 501，而不是返回假计数（SPEC §10）。
    """
    from odap.infra.providers import is_registered

    if not is_registered(GRAPH_EXTRACTOR_PROVIDER):
        return {
            "available": False,
            "error_code": ERR_GRAPH_NOT_IMPLEMENTED,
            "reason": (
                "图谱抽取 provider 未注册（graph_entity_extractor）。"
                "真实抽取能力待实现：需实现 extract(scenario_id, config) 并统计真实写入数，"
                "注册到 odap.infra.providers 后方可启用该端点（SPEC-v2 W0-2 / F6）。"
            ),
        }
    return {"available": True, "error_code": None, "reason": ""}


@celery_app.task
def generate_graph_task(task_id, scenario_id, config=None):
    """生成图谱任务（真实抽取；能力缺失时显式 NotImplementedError）。"""
    cap = graph_generation_capability()
    if not cap["available"]:
        logger.error(
            "generate_graph_task rejected: error_code=%s task_id=%s scenario_id=%s reason=%s",
            cap["error_code"], task_id, scenario_id, cap["reason"],
        )
        raise NotImplementedError(f"{cap['error_code']}: {cap['reason']}")

    try:
        from odap.infra.providers import resolve_provider

        extractor = resolve_provider(GRAPH_EXTRACTOR_PROVIDER)
        outcome = extractor.extract(scenario_id, config or {})
        entities = int(outcome.get("entities_generated", 0))
        relations = int(outcome.get("relations_generated", 0))
        return {
            "task_id": task_id,
            "scenario_id": scenario_id,
            "status": "completed",
            "entities_generated": entities,
            "relations_generated": relations,
            "component": GRAPH_EXTRACTOR_PROVIDER,
            "component_version": str(outcome.get("component_version", "")),
            "config": config or {},
        }
    except NotImplementedError:
        raise
    except Exception as exc:  # noqa: BLE001 - 任务边界必须兜底并显式记录
        logger.error(
            "generate_graph_task failed: error_code=%s task_id=%s scenario_id=%s "
            "error_type=%s error=%s",
            ERR_GRAPH_FAILED, task_id, scenario_id, type(exc).__name__, exc, exc_info=True,
        )
        return _failure(task_id, ERR_GRAPH_FAILED, exc)


@celery_app.task
def process_file_upload_task(task_id, filename, file_content, file_extension, scenario_id=None):
    """处理文件上传任务：解析 + 真实落库为场景文档。"""
    try:
        if not scenario_id:
            return _failure(
                task_id, ERR_SCENARIO_REQUIRED,
                message="缺少 scenario_id，无法落库；拒绝返回未持久化的假成功",
            )

        parsed = parse_uploaded_file(
            file_content if isinstance(file_content, bytes) else file_content.encode("utf-8"),
            file_extension,
        )
        doc = {
            "doc_id": f"file-{int(time.time() * 1000)}",
            "meta": {
                "doc_type": "file",
                "filename": filename,
                "file_extension": file_extension,
                "file_size": len(file_content),
                "parsed": parsed,
            },
            "entities": [],
            "events": [],
            "relations": [],
            "created_at": _now_iso(),
        }
        try:
            row_id = _persist_scenario_document(scenario_id, doc)
        except LookupError as exc:
            return _failure(task_id, ERR_SCENARIO_NOT_FOUND, exc)

        return {
            "task_id": task_id,
            "filename": filename,
            "file_size": len(file_content),
            "file_extension": file_extension,
            "scenario_id": scenario_id,
            "doc_row_id": row_id,
            "status": "completed",
            **parsed,
        }
    except ValueError as exc:
        logger.warning(
            "process_file_upload_task rejected: error_code=%s task_id=%s filename=%s error=%s",
            "UNSUPPORTED_FILE_TYPE", task_id, filename, exc,
        )
        return _failure(task_id, "UNSUPPORTED_FILE_TYPE", exc)
    except Exception as exc:  # noqa: BLE001 - 任务边界必须兜底并显式记录
        logger.error(
            "process_file_upload_task failed: error_code=%s task_id=%s filename=%s "
            "scenario_id=%s error_type=%s error=%s",
            ERR_PERSIST_FAILED, task_id, filename, scenario_id,
            type(exc).__name__, exc, exc_info=True,
        )
        return _failure(task_id, ERR_PERSIST_FAILED, exc)
