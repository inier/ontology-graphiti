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
            # D5 修复：graph_service 中不存在 get_graph_manager 工厂函数；GraphManager 通过
            # __new__ 实现单例，直接实例化即可。原代码 `from ... import get_graph_manager`
            # 触发 ImportError 被下方 except 吞掉，导致本步骤从未成功执行。
            from odap.infra.graph.graph_service import GraphManager
            # span schema 冻结（prov-span-v1，见 provenance/provenance_schema.py）：
            # 所有写图路径统一从此归一化溯源字段，把上游已有的
            # source_doc_ids/chunk_id/char_span/confidence/evidence_text 收敛到冻结键
            # 并落图，同时盖上 prov_schema_version 版本戳（区分历史裸边）。
            from odap.biz.core.ontology.construction.provenance.provenance_schema import (
                build_provenance_props,
            )

            gm = GraphManager()
            timestamp = datetime.now(timezone.utc).isoformat()

            # 写入节点
            for entity in entities:
                eid = entity.get("id", entity.get("entity_id", str(uuid.uuid4())))
                try:
                    etype = entity.get("entity_type", entity.get("type", "Unknown"))
                    name = entity.get("name", entity.get("entity_name", ""))
                    props = dict(entity.get("properties", {}) or {})
                    props["batch_id"] = batch_id
                    props["pipeline_run_id"] = pipeline_run_id
                    props["transaction_time"] = timestamp
                    # D5 修复：add_entity 真实签名是 (entity_id, entity_type, properties)，
                    # 无 entity_name 参数；把 name 合并进 properties 保留语义。
                    if name and "name" not in props:
                        props["name"] = name

                    # span schema 冻结：合并溯源占位字段（只写有真值的冻结键 + 版本戳）。
                    # 置于 batch/pipeline 之后——溯源键与它们互不覆盖。
                    props.update(build_provenance_props(entity))

                    gm.add_entity(
                        entity_id=eid,
                        entity_type=etype,
                        properties=props,
                    )
                    result.node_ids.append(eid)
                    result.nodes_written += 1
                except Exception as e:
                    result.errors.append(f"Node write error ({eid}): {e}")
                    logger.warning("GraphWriteStep: node write failed eid=%s: %s", eid, e)

            # 写入关系
            for relation in relations:
                rid = relation.get("id", str(uuid.uuid4()))
                try:
                    rtype = relation.get(
                        "relation_type", relation.get("type", "ASSOCIATED_WITH")
                    )
                    source = relation.get(
                        "source_entity_id", relation.get("source", "")
                    )
                    target = relation.get(
                        "target_entity_id", relation.get("target", "")
                    )
                    rprops = dict(relation.get("properties", {}) or {})
                    rprops["batch_id"] = batch_id
                    rprops["pipeline_run_id"] = pipeline_run_id

                    # span schema 冻结：边级溯源是"最小信任闭环"的关键——结论文档指出
                    # 图谱边此前是零溯源裸边。这里把上游边携带的 source_doc_ids 等
                    # 冻结键落图（P1 可事后 join 回填文档级来源），并盖版本戳。
                    rprops.update(build_provenance_props(relation))

                    # D5 修复：add_relationship 真实签名是 (source_id, target_id, relationship, properties)，
                    # 参数名是 relationship 不是 relationship_type；原代码传错关键字触发 TypeError
                    # 被逐条吞进 result.errors，边级 batch_id/pipeline_run_id 从未真正落图。
                    gm.add_relationship(
                        source_id=source,
                        target_id=target,
                        relationship=rtype,
                        properties=rprops,
                    )
                    result.edge_ids.append(rid)
                    result.edges_written += 1
                except Exception as e:
                    result.errors.append(f"Edge write error ({rid}): {e}")
                    logger.warning("GraphWriteStep: edge write failed rid=%s: %s", rid, e)

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
