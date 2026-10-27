"""存量 `:Decision` 节点幂等迁移（ADR-091 §4.3）

三条硬要求：
1. **幂等**：二次运行匹配 0 行（每条语句都带 `WHERE ... IS NULL` 守卫）
2. **不猜流程状态**：无法判定的存量数据标 `status_assumed=true`，数据层就不满足
   队列条件（队列 Cypher 恒带 `coalesce(n.status_assumed,false)=false`），
   不靠前端过滤——否则导出、计数、批量裁决三处都会漏
3. **不靠 Cypher 判 JSON**：`outcome_details` 在图上是 JSON **字符串**，
   写成属性取值会恒为 null 让规则静默失效，故把 JSON 解析放到 Python 侧

与架构初稿的差异（有意）：初稿把规则写成一条 Cypher `CASE`+`CONTAINS`。
改为"扫描 -> Python 推导 -> 带守卫回写"，一是避开上面第 3 条的字符串陷阱，
二是推导逻辑可被单测逐行对照规则表。
"""

import json
import logging
from typing import Any, Callable, Dict, List

from odap.biz.decision.decision_record.impl import neo4j_driver
from odap.biz.decision.decision_record.models.timestamps import iso_utc, parse_iso, utcnow

logger = logging.getLogger(__name__)

MAX_BATCHES = 100


def _has_execution_trace(props: Dict[str, Any]) -> bool:
    """`outcome_details` 含 `action_status` 说明已派发未终结（`_perform` 之后才写该键）。"""
    details = props.get("outcome_details")
    if isinstance(details, dict):
        return "action_status" in details
    if isinstance(details, str):
        try:
            parsed = json.loads(details)
        except (TypeError, ValueError):
            return "action_status" in details
        return isinstance(parsed, dict) and "action_status" in parsed
    return False


def _derive_status(props: Dict[str, Any]) -> tuple:
    """按 §4.3 规则表推导 (status, status_assumed)。"""
    outcome = (props.get("outcome") or "").strip()
    if outcome in ("success", "partial_success"):
        return "executed", False
    if outcome == "failure":
        return "failed", False
    if outcome == "rejected":
        return "rejected", False
    if _has_execution_trace(props):
        return "executing", False
    # 无法判定"待裁决"还是"已裁决未派发"：标记推定并排除出队列
    return "pending", True


def _normalized_time(props: Dict[str, Any], key: str) -> str:
    return iso_utc(parse_iso(props.get(key))) or ""


def derive_legacy_fields(props: Dict[str, Any]) -> Dict[str, Any]:
    """推导存量节点缺失字段（status / entry_source / status_assumed / 时态 / 证据数）。"""
    status, assumed = _derive_status(props)
    patch: Dict[str, Any] = {
        "status": status,
        "status_assumed": assumed,
        "entry_source": props.get("entry_source") or "legacy",
    }
    created = _normalized_time(props, "created_at")
    updated = _normalized_time(props, "updated_at")
    if created:
        patch["created_at"] = created
    patch["updated_at"] = updated or created or iso_utc(utcnow())
    patch.update(derive_evidence_count(props))
    return patch


def derive_evidence_count(props: Dict[str, Any]) -> Dict[str, Any]:
    """派生 `evidence_count`（排序键；`size()` 对 JSON 字符串无效，故 Python 侧算）。"""
    if props.get("evidence_count") is not None:
        return {}
    raw = props.get("evidence_entity_ids")
    if isinstance(raw, list):
        return {"evidence_count": len(raw)}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return {"evidence_count": len(parsed)} if isinstance(parsed, list) else {}
    return {}


class Neo4jDecisionMigrationMixin:
    """迁移入口：`ensure_indices()` 与读路径首行调用，保证只读启动也能自愈。"""

    async def migrate_legacy_fields(self, batch: int = 500) -> Dict[str, int]:
        """返回各阶段实际写入条数；二次运行两阶段均为 0。"""
        return {
            "migrated_status": await self._migrate_phase(
                guard="n.status IS NULL", derive=derive_legacy_fields, batch=batch
            ),
            "migrated_evidence_count": await self._migrate_phase(
                guard="n.status IS NOT NULL AND n.evidence_count IS NULL",
                derive=derive_evidence_count,
                batch=batch,
            ),
        }

    async def _migrate_phase(
        self, guard: str, derive: Callable[[Dict[str, Any]], Dict[str, Any]], batch: int
    ) -> int:
        applied = 0
        for _ in range(MAX_BATCHES):
            nodes = await self._scan_unmigrated(guard, batch)
            if not nodes:
                break
            applied += await self._apply_batch(guard, nodes, derive)
            if len(nodes) < batch:
                break
        return applied

    async def _scan_unmigrated(self, guard: str, batch: int) -> List[Dict[str, Any]]:
        records, _, _ = await neo4j_driver.get_decision_driver().execute_query(
            f"MATCH (n:Decision) WHERE {guard} RETURN n LIMIT $batch", batch=batch
        )
        return [neo4j_driver.node_props(r["n"]) for r in records]

    async def _apply_batch(
        self,
        guard: str,
        nodes: List[Dict[str, Any]],
        derive: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> int:
        driver = neo4j_driver.get_decision_driver()
        applied = 0
        for node in nodes:
            patch = derive(node)
            uuid = node.get("uuid")
            if not patch or not uuid:
                continue
            records, _, _ = await driver.execute_query(
                f"MATCH (n:Decision {{uuid: $uuid}}) WHERE {guard} "
                "SET n += $patch RETURN n.uuid AS uuid",
                uuid=uuid,
                patch=patch,
            )
            applied += len(records)
        return applied
