"""FactLoader — Neo4j ABox → Datalog facts 提取 (ADR-075 §2)。

将图库中的实体/关系/属性抽取为 Datalog 事实项：
- entity(eid, type_name)
- type_prop(eid, prop, value)
- rel(subject_eid, predicate, object_eid)
- interval(eid, start, end)        （时态区间，可选用）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Fact:
    """一条 Datalog 事实：predicate + 参数元组"""
    predicate: str
    args: tuple

    def to_clause(self) -> str:
        """渲染为 pyDatalog 事实子句: pred(a, b, ...)"""
        rendered = ", ".join(_render_arg(a) for a in self.args)
        return f"{self.predicate}({rendered})"


def _render_arg(arg: Any) -> str:
    """将参数渲染为 pyDatalog 字面量：
    - str → "quoted"
    - int/float → 原样
    - None → "None"
    """
    if arg is None:
        return "None"
    if isinstance(arg, bool):
        return "True" if arg else "False"
    if isinstance(arg, (int, float)):
        return repr(arg)
    if isinstance(arg, str):
        # 转义引号
        escaped = arg.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return f'"{repr(arg)}"'


class FactLoader:
    """图事实提取器（默认从 GraphManager 的实体/关系索引读取）"""

    def __init__(self):
        pass

    def load_entity_facts(self, entity_type_id: str, workspace_id: str = "default", limit: int = 1000) -> List[Fact]:
        """从统一查询服务加载指定类型实体 → entity / type_prop / interval 事实"""
        facts: List[Fact] = []
        try:
            from odap.infra.query import get_query_service
            qs = get_query_service()
            result = qs.execute(
                "default",
                f".entity with(type='{entity_type_id}')",
                limit=limit,
            )
            entities = result.rows
            for ent in entities:
                eid = str(ent.get("id", ""))
                if not eid:
                    continue
                etype = ent.get("type") or entity_type_id
                facts.append(Fact("entity", (eid, etype)))

                props = ent.get("properties") or {}
                for key, val in props.items():
                    if isinstance(val, (list, dict)):
                        continue  # 复杂属性暂不导入
                    facts.append(Fact("type_prop", (eid, key, val)))

                # 时态区间（若属性含 start/end）
                start = props.get("start")
                end = props.get("end")
                if start is not None and end is not None:
                    facts.append(Fact("interval", (eid, start, end)))
        except Exception as e:
            logger.warning("FactLoader.load_entity_facts failed for %s: %s", entity_type_id, e)
        return facts

    def load_relationship_facts(self, workspace_id: str = "default", limit: int = 2000) -> List[Fact]:
        """加载关系 → rel(subject, predicate, object) 事实"""
        facts: List[Fact] = []
        try:
            from odap.infra.query import get_query_service
            qs = get_query_service()
            result = qs.execute("default", ".relationship", limit=limit)
            rels = result.rows
            for rel in rels:
                subj = str(rel.get("source_id") or rel.get("subject_id") or "")
                obj = str(rel.get("target_id") or rel.get("object_id") or "")
                pred = str(rel.get("type") or rel.get("predicate") or "related_to")
                if subj and obj:
                    facts.append(Fact("rel", (subj, pred, obj)))
        except Exception as e:
            logger.warning("FactLoader.load_relationship_facts failed: %s", e)
        return facts

    def load_all(self, entity_type_ids: Optional[List[str]] = None, workspace_id: str = "default") -> List[Fact]:
        """加载全部事实（实体+关系）。entity_type_ids 为空时尝试全量。"""
        facts: List[Fact] = []
        if entity_type_ids:
            for et in entity_type_ids:
                facts.extend(self.load_entity_facts(et, workspace_id=workspace_id))
        facts.extend(self.load_relationship_facts(workspace_id=workspace_id))
        return facts


def facts_to_clauses(facts: List[Fact]) -> List[str]:
    """将事实列表转为 pyDatalog 子句文本列表"""
    return [f.to_clause() for f in facts]


__all__ = ["Fact", "FactLoader", "facts_to_clauses"]
