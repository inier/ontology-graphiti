"""AuditExporter — PROV-O 溯源导出（扩展 ADR-074 §增补）。

零侵入：映射仅发生在导出层，unified_audit 写入路径不变。
只读旁路，按需触发。

导出格式：
- json-ld: rdflib JSON-LD 序列化
- turtle:  rdflib Turtle 序列化
- csv:     简化扁平导出（人工审计）

完整性（P0-3）：每条 Activity 附带 ``odap:sha256`` 内容指纹，并额外生成一个
``prov:Collection`` 清单节点，其 ``odap:sha256`` 是有序摘要集合的聚合指纹。
接收方可用同样的规范化 JSON 复算，判断导出内容是否被改动。
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, List, Optional

from .integrity import collection_digest, event_digest
from .prov_o_mapper import ODAP, PROV, ProvOMapper

logger = logging.getLogger(__name__)

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

# 宾语是 IRI（资源）而非字面量的谓词。显式列举，避免用 endswith 猜测。
_OBJECT_PROPERTIES = frozenset({
    _RDF_TYPE,
    f"{PROV}wasAssociatedWith",
    f"{PROV}wasGeneratedBy",
    f"{PROV}used",
    f"{PROV}wasDerivedFrom",
    f"{PROV}wasInformedBy",
    f"{PROV}hadMember",
    f"{ODAP}partOfExport",
})


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
        PROV_NS = Namespace(PROV)
        ODAP_NS = Namespace(ODAP)
        g.bind("prov", PROV_NS)
        g.bind("odap", ODAP_NS)

        digests: List[str] = []
        activities: List[str] = []

        for event in events:
            mapped = self.mapper.map_event(event)
            digest = event_digest(event)
            digests.append(digest)
            activities.append(mapped["activity"])

            triples = list(mapped["triples"]) + [
                (mapped["activity"], f"{ODAP}sha256", digest),
            ]
            for subj, pred, obj in triples:
                s = URIRef(subj)
                p = URIRef(pred)
                if pred in _OBJECT_PROPERTIES:
                    o = URIRef(obj)
                else:
                    # 字面量
                    o = Literal(str(obj).strip('"'))
                g.add((s, p, o))

        # 导出清单：聚合指纹 + 成员关系
        manifest_iri = f"{ODAP}export/{collection_digest(digests)}"
        g.add((URIRef(manifest_iri), URIRef(_RDF_TYPE), URIRef(f"{PROV}Collection")))
        g.add((URIRef(manifest_iri), URIRef(f"{ODAP}sha256"),
               Literal(collection_digest(digests))))
        g.add((URIRef(manifest_iri), URIRef(f"{ODAP}memberCount"), Literal(len(digests))))
        for activity in activities:
            g.add((URIRef(activity), URIRef(f"{ODAP}partOfExport"), URIRef(manifest_iri)))

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
            "activity_iri", "agent_iri", "entity_iri", "event_digest",
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
                event_digest(event),
            ])
        return output.getvalue()


__all__ = ["AuditExporter"]
