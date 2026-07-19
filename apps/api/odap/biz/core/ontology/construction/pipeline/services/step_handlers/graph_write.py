"""Step 5: 写入 Graphiti — 创建节点+关系+事务时间戳"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class GraphWriteResult:
    batch_id: str = ""
    nodes_written: int = 0
    edges_written: int = 0
    node_ids: List[str] = field(default_factory=list)
    edge_ids: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return len(self.errors) == 0


class GraphWriteStep:
    """图谱写入处理器"""

    async def execute(
        self,
        entities: List[Dict],
        relations: List[Dict],
        pipeline_run_id: str = "",
        workspace_id: str = "default",
    ) -> GraphWriteResult:
        batch_id = f"build-{uuid.uuid4().hex[:12]}"
        result = GraphWriteResult(batch_id=batch_id)

        try:
            from odap.infra.graph.graph_service import get_graph_manager

            gm = get_graph_manager()
            timestamp = datetime.now(timezone.utc).isoformat()

            # 写入节点
            for entity in entities:
                try:
                    eid = entity.get("id", entity.get("entity_id", str(uuid.uuid4())))
                    etype = entity.get("entity_type", entity.get("type", "Unknown"))
                    name = entity.get("name", entity.get("entity_name", ""))
                    props = entity.get("properties", {})
                    props["batch_id"] = batch_id
                    props["pipeline_run_id"] = pipeline_run_id
                    props["transaction_time"] = timestamp

                    gm.add_entity(
                        entity_id=eid,
                        entity_type=etype,
                        entity_name=name,
                        properties=props,
                    )
                    result.node_ids.append(eid)
                    result.nodes_written += 1
                except Exception as e:
                    result.errors.append(f"Node write error ({eid}): {e}")

            # 写入关系
            for relation in relations:
                try:
                    rid = relation.get("id", str(uuid.uuid4()))
                    rtype = relation.get(
                        "relation_type", relation.get("type", "ASSOCIATED_WITH")
                    )
                    source = relation.get(
                        "source_entity_id", relation.get("source", "")
                    )
                    target = relation.get(
                        "target_entity_id", relation.get("target", "")
                    )
                    rprops = relation.get("properties", {})
                    rprops["batch_id"] = batch_id
                    rprops["pipeline_run_id"] = pipeline_run_id

                    gm.add_relationship(
                        source_id=source,
                        target_id=target,
                        relationship_type=rtype,
                        properties=rprops,
                    )
                    result.edge_ids.append(rid)
                    result.edges_written += 1
                except Exception as e:
                    result.errors.append(f"Edge write error: {e}")

            logger.info(
                "GraphWrite: batch=%s, nodes=%d, edges=%d, errors=%d",
                batch_id,
                result.nodes_written,
                result.edges_written,
                len(result.errors),
            )
        except Exception as e:
            result.errors.append(f"GraphWrite step failed: {e}")
            logger.error("GraphWrite step failed: %s", e)

        return result
