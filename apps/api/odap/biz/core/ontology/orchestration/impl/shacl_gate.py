"""SHACL 输出契约分支（AC-31 / ADR-085 S4a-1）。

结构化回答必须可被机器校验：正文可以自由，但携带的 RDF 载荷（`DraftAnswer.payload_ttl`，
Turtle 文本）要满足 `semantic_admin/shacl_store` 中按
`(ontology_version_id, constraint_revision, target_type)` 登记的形状。

失败语义（fail-closed，不静默放行）：

    SHACL_PAYLOAD_EMPTY         声明了结构化载荷但内容为空
    SHACL_TARGET_CLASS_MISSING  未给出目标类型（无法定位形状）
    SHACL_SHAPE_MISSING         目标类型没有已登记形状
    SHACL_SHAPE_EMPTY           形状登记了但没有 shape_ttl 正文（无法校验）
    SHACL_UNAVAILABLE           校验器依赖不可用（pyshacl / rdflib 缺失）
    SHACL_PAYLOAD_INVALID       载荷不是合法 Turtle
    SHACL_SHAPE_INVALID         形状不是合法 Turtle
    SHACL_VIOLATION             校验不通过（附 pyshacl 报告摘要）

形状查找顺序：给定 `(ontology_version_id, constraint_revision)` 时精确命中缓存键；
未给定失效键时取该目标类型最近登记的一条（`created_at DESC`），并把实际命中的
版本键写回违约信息，便于定位是哪一版形状判定的。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TARGET_TYPE_LIMIT = 200


class ShaclPayloadValidator:
    """按已登记形状校验 RDF 载荷。"""

    def __init__(
        self,
        storage: Any = None,
        ontology_version_id: str = "",
        constraint_revision: str = "",
    ) -> None:
        self._storage = storage
        self._ontology_version_id = ontology_version_id
        self._constraint_revision = constraint_revision

    # ── 对外 ──────────────────────────────────────────────────────────────
    def validate(self, payload_ttl: str, target_type: str) -> List[str]:
        """返回违约原因列表；空列表表示通过。"""
        ttl = (payload_ttl or "").strip()
        if not ttl:
            return ["SHACL_PAYLOAD_EMPTY: 声明了结构化载荷但内容为空"]
        target = (target_type or "").strip()
        if not target:
            return ["SHACL_TARGET_CLASS_MISSING: 结构化载荷未声明目标类型（payload_class）"]

        try:
            shape = self._find_shape(target)
        except Exception as exc:  # noqa: BLE001 - 存储不可读必须显式暴露
            return [f"SHACL_UNAVAILABLE: 形状存储不可读（{type(exc).__name__}: {exc}）"]
        if shape is None:
            return [
                "SHACL_SHAPE_MISSING: 目标类型 "
                f"{target} 没有已登记的形状（ontology_version_id="
                f"{self._ontology_version_id or '*'}）"
            ]
        shape_ttl = (shape.get("shape_ttl") or "").strip()
        if not shape_ttl:
            return [
                f"SHACL_SHAPE_EMPTY: 形状 {shape.get('shape_id')} 无 shape_ttl 正文，无法校验"
            ]

        try:
            from pyshacl import validate as shacl_validate
            from rdflib import Graph
        except ImportError as exc:
            return [f"SHACL_UNAVAILABLE: pyshacl 不可用（{exc}）"]

        try:
            data_graph = Graph().parse(data=ttl, format="turtle")
        except Exception as exc:  # noqa: BLE001 - 解析失败即载荷非法
            return [f"SHACL_PAYLOAD_INVALID: 载荷不是合法 Turtle（{type(exc).__name__}: {exc}）"]
        try:
            shapes_graph = Graph().parse(data=shape_ttl, format="turtle")
        except Exception as exc:  # noqa: BLE001 - 形状本身坏了也要暴露
            return [f"SHACL_SHAPE_INVALID: 形状不是合法 Turtle（{type(exc).__name__}: {exc}）"]

        try:
            conforms, _, report = shacl_validate(data_graph, shacl_graph=shapes_graph)
        except Exception as exc:  # noqa: BLE001 - 引擎异常不得变成通过
            return [f"SHACL_UNAVAILABLE: 校验引擎异常（{type(exc).__name__}: {exc}）"]
        if conforms:
            return []
        return [f"SHACL_VIOLATION: {_summarize(report, shape)}"]

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _find_shape(self, target: str) -> Optional[Dict[str, Any]]:
        storage = self._storage if self._storage is not None else self._default_storage()
        if self._ontology_version_id and self._constraint_revision:
            hit = storage.get_shape(
                ontology_version_id=self._ontology_version_id,
                constraint_revision=self._constraint_revision,
                target_type=target,
            )
            if hit is not None:
                return hit
        rows, _ = storage.list_shapes(
            ontology_version_id=self._ontology_version_id or None,
            page=1,
            page_size=_TARGET_TYPE_LIMIT,
        )
        for row in rows:
            if _same_type(row.get("target_type"), target):
                return row
        return None

    def _default_storage(self) -> Any:
        from odap.biz.semantic_admin.shacl_store.storage.sqlite_shacl_storage import (
            SQLiteShaclStorage,
        )

        self._storage = SQLiteShaclStorage()
        return self._storage


def _same_type(stored: Any, target: str) -> bool:
    """形状 target_type 与载荷 target class 的对齐判定（IRI 或本地名都接受）。"""
    left = str(stored or "").strip()
    right = (target or "").strip()
    if not left or not right:
        return False
    if left == right:
        return True
    return _local_name(left) == _local_name(right)


def _local_name(value: str) -> str:
    cleaned = value.rstrip("/#")
    for separator in ("#", "/", ":"):
        if separator in cleaned:
            return cleaned.rsplit(separator, 1)[-1]
    return cleaned


def _summarize(report: Any, shape: Dict[str, Any]) -> str:
    """pyshacl 报告摘要（限长，避免把整份报告塞进 blocked_reasons）。"""
    text = " ".join(str(report or "").split())
    if len(text) > 600:
        text = text[:600] + "..."
    return f"[shape={shape.get('shape_id')} v={shape.get('ontology_version_id')}] {text}"


__all__ = ["ShaclPayloadValidator"]
