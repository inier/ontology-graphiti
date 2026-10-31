"""本体映射：把意图槽位落到 TBox（AC-26 / AC-27）。

规则（ARCHITECTURE-v2 §2.2 输入侧约束）：
- 只接受能在 TBox 中找到 `ObjectType` / `RelationType` / 指标定义的槽位；
- 映射不到的槽位进 `unmapped[]`（**禁止**静默丢弃，也禁止用 LLM 幻觉补全后执行）；
- 匹配为**精确等值**（经 TBoxCatalog 归一化索引），不做相似度猜测。

TBox 不可读时 fail-closed：抛 `ApiError(503, TBOX_UNAVAILABLE)`，不返回空映射冒充成功。
"""

from __future__ import annotations

import logging
from typing import Optional

from odap.common.api_errors import ApiError
from odap.biz.core.ontology.orchestration.contracts import (
    Evidence,
    IntentFrame,
    MappedQuery,
    MappedRef,
    StepProv,
    UnmappedSlot,
)
from odap.biz.core.ontology.orchestration.tbox import (
    _KIND_METRIC,
    _KIND_OBJECT,
    _KIND_RELATION,
    TBoxCatalog,
)

logger = logging.getLogger(__name__)


class TBoxOntologyAligner:
    """基于 TBox 目录的映射器（插槽实现）。"""

    name = "OntologyAligner"
    version = "v2.0"

    def __init__(self, catalog: Optional[TBoxCatalog] = None) -> None:
        self.catalog = catalog or TBoxCatalog()

    async def align(self, intent: IntentFrame, workspace_id: str) -> MappedQuery:
        prov = StepProv(component=self.name, version=self.version)
        terms = [str(t) for t in (intent.slots.get("terms") or []) if str(t).strip()]

        try:
            self.catalog.load(workspace_id)
        except Exception as exc:  # noqa: BLE001 - TBox 不可读必须 fail-closed
            logger.error("TBox 目录不可读，映射 fail-closed：%s", exc)
            raise ApiError(
                "TBOX_UNAVAILABLE",
                f"TBox 不可读，无法把槽位映射到本体（fail-closed）：{type(exc).__name__}: {exc}",
                status_code=503,
                detail={"workspace_id": workspace_id},
            ) from exc

        mapped = MappedQuery(intent=intent, prov=prov)
        for term in terms:
            hit = self.catalog.lookup(term, workspace_id)
            if hit is None:
                mapped.unmapped.append(UnmappedSlot(slot="term", raw=term))
                continue
            ref, element = hit
            kind = element["kind"]
            mapped_ref = MappedRef(slot=term, kind=kind, ref=ref)
            if kind == _KIND_OBJECT:
                mapped.object_types.append(mapped_ref)
            elif kind == _KIND_RELATION:
                mapped.relation_types.append(mapped_ref)
            elif kind == _KIND_METRIC:
                mapped.metrics.append(mapped_ref)
            prov.evidence.append(Evidence(kind="tbox_node", ref=ref))

        if mapped.unmapped:
            # 概念缺口回路（ADR-086 gap_pool）写入属 F6 后续范围，本轮先保证可见性
            prov.evidence.append(
                Evidence(
                    kind="decision",
                    ref="decision:unmapped_to_gap_pool",
                )
            )
        return mapped


__all__ = ["TBoxOntologyAligner"]
