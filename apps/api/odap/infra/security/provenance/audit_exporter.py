"""AuditExporter — PROV-O 溯源导出（扩展 ADR-074 §增补）。

零侵入：映射仅发生在导出层，unified_audit 写入路径不变。
只读旁路，按需触发。

导出格式：
- json-ld: rdflib JSON-LD 序列化
- turtle:  rdflib Turtle 序列化
- csv:     简化扁平导出（人工审计）
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, List, Optional

from .prov_o_mapper import ProvOMapper

logger = logging.getLogger(__name__)


class AuditExporter:
    """审计事件 → PROV-O 多格式导出器"""

    def __init__(self, mapper: Optional[ProvOMapper] = None):
        self.mapper = mapper or ProvOMapper()

    def export(self, events: List[Dict[str, Any]], fmt: str = "json-ld") -> str:
        """导出审计事件为指定格式。

        Args:
            events: 审计事件 dict 列表
            fmt: json-ld | turtle | rdfxml | csv

        Returns:
            序列化文本
        """
        if fmt == "csv":
            return self._export_csv(events)
        return self._export_rdf(events, fmt)

    def _export_rdf(self, events: List[Dict[str, Any]], fmt: str) -> str:
        """RDF 序列化（json-ld/turtle/rdfxml）"""
        try:
            from rdflib import Graph, Namespace, URIRef, Literal
        except ImportError as e:
            raise RuntimeError("rdflib 未安装，无法导出 PROV-O") from e

        g = Graph()
        PROV = Namespace("http://www.w3.org/ns/prov#")
        g.bind("prov", PROV)

        for event in events:
            mapped = self.mapper.map_event(event)
            for subj, pred, obj in mapped["triples"]:
                s = URIRef(subj)
                p = URIRef(pred)
                if pred.endswith("type") or pred.endswith("wasAssociatedWith") or \
                   pred.endswith("wasGeneratedBy") or pred.endswith("used") or \
                   pred.endswith("wasDerivedFrom") or pred.endswith("wasInformedBy"):
                    o = URIRef(obj)
                else:
                    # 字面量
                    o = Literal(str(obj).strip('"'))
                g.add((s, p, o))

        fmt_map = {
            "json-ld": "json-ld",
            "turtle": "turtle",
            "rdfxml": "xml",
        }
        rdf_fmt = fmt_map.get(fmt, "json-ld")
        return g.serialize(format=rdf_fmt)

    def _export_csv(self, events: List[Dict[str, Any]]) -> str:
        """CSV 扁平导出"""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "event_id", "event_type", "action", "actor_id", "actor_name",
            "resource_type", "resource_id", "workspace_id", "timestamp",
            "activity_iri", "agent_iri", "entity_iri",
        ])
        for event in events:
            mapped = self.mapper.map_event(event)
            actor = event.get("actor", {}) or {}
            resource = event.get("resource", {}) or {}
            writer.writerow([
                event.get("id", ""),
                event.get("event_type", ""),
                event.get("action", ""),
                actor.get("actor_id", "") if isinstance(actor, dict) else "",
                actor.get("actor_name", "") if isinstance(actor, dict) else "",
                resource.get("resource_type", "") if isinstance(resource, dict) else "",
                resource.get("resource_id", "") if isinstance(resource, dict) else "",
                event.get("workspace_id", "default"),
                event.get("timestamp", ""),
                mapped["activity"],
                mapped["agent"],
                mapped["entity"],
            ])
        return output.getvalue()


__all__ = ["AuditExporter"]
