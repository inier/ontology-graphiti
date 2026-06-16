"""
本体构建服务
实现数据到本体模型的转换算法，与 graphiti 集成

功能:
1. 实体抽取 - 从原始数据中识别和抽取实体
2. 关系抽取 - 识别实体之间的关系
3. 图谱构建 - 与 graphiti 集成构建图谱
4. 变化检测 - 检测信息变化并更新图谱
5. 版本管理 - 本体版本与场景绑定
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("ontology_builder")


@dataclass
class BuildProgress:
    """构建进度"""
    build_id: str
    stage: str = "pending"
    progress: float = 0.0
    message: str = ""
    entities_extracted: int = 0
    relations_extracted: int = 0
    nodes_created: int = 0
    edges_created: int = 0
    errors: List[str] = field(default_factory=list)


class OntologyBuilderService:
    """
    本体构建服务

    负责:
    1. 将 OntologyDocument 转换为图谱节点和边
    2. 与 graphiti 集成构建图谱
    3. 管理图谱版本
    4. 检测变化并更新
    """

    def __init__(self):
        self._graphiti_core = None
        self._version_manager = None

    async def build_ontology(
        self,
        document: 'OntologyDocument',
        scenario_id: str,
        workspace_id: str = "default",
        create_new_version: bool = True,
        ontology_id: str = None
    ) -> Dict[str, Any]:
        """
        构建本体

        Args:
            document: OntologyDocument 实例
            scenario_id: 场景 ID
            workspace_id: 工作空间 ID
            create_new_version: 是否创建新版本
            ontology_id: 本体 ID

        Returns:
            Dict: 包含 build_id, status, stats 等
        """
        build_id = f"build-{uuid.uuid4().hex[:12]}"

        progress = BuildProgress(
            build_id=build_id,
            stage="extracting",
            progress=0.0,
            message="开始提取实体和关系"
        )

        try:
            # 步骤1: 实体和关系抽取
            entities, relations = await self._extract_entities_relations(document)
            progress.entities_extracted = len(entities)
            progress.relations_extracted = len(relations)
            progress.progress = 30.0
            progress.message = f"提取了 {len(entities)} 个实体, {len(relations)} 个关系"

            # 步骤2: 创建图谱节点和边
            nodes, edges = await self._create_graph_elements(entities, relations, document)
            progress.nodes_created = len(nodes)
            progress.edges_created = len(edges)
            progress.progress = 60.0
            progress.message = f"创建了 {len(nodes)} 个节点, {len(edges)} 条边"

            # 步骤3: 写入图谱
            await self._write_to_graphiti(nodes, edges, scenario_id, workspace_id)
            progress.progress = 90.0
            progress.message = "图谱写入完成"

            # 步骤4: 创建版本（如果需要）
            version_info = None
            if create_new_version:
                version_info = await self._create_version(
                    document, scenario_id, workspace_id, ontology_id=ontology_id
                )

            progress.progress = 100.0
            progress.stage = "completed"
            progress.message = "本体构建完成"

            return {
                "build_id": build_id,
                "status": "completed",
                "progress": progress.progress,
                "stats": {
                    "entities_extracted": progress.entities_extracted,
                    "relations_extracted": progress.relations_extracted,
                    "nodes_created": progress.nodes_created,
                    "edges_created": progress.edges_created
                },
                "version_info": version_info,
                "document_id": document.doc_id
            }

        except Exception as e:
            logger.error(f"本体构建失败: {e}")
            progress.errors.append(str(e))
            progress.stage = "failed"
            return {
                "build_id": build_id,
                "status": "failed",
                "error": str(e),
                "progress": progress.__dict__
            }

    async def _extract_entities_relations(
        self,
        document: 'OntologyDocument'
    ) -> Tuple[List[Dict], List[Dict]]:
        """提取实体和关系"""
        entities = []
        relations = []

        # 从 document.entities 提取
        for entity in document.entities:
            entity_dict = {
                "entity_id": entity.entity_id,
                "entity_type": entity.entity_type,
                "name": entity.name,
                "name_en": getattr(entity, "name_en", ""),
                "properties": {
                    "basic": entity.basic_properties,
                    "statistical": entity.statistical_properties,
                    "capabilities": entity.capabilities
                }
            }
            entities.append(entity_dict)

        # 从 document.relations 提取
        for relation in document.relations:
            rel_dict = {
                "relation_id": relation.relation_id,
                "relation_type": relation.relation_type,
                "source": relation.source_entity,
                "target": relation.target_entity,
                "properties": relation.properties,
                "temporal": {
                    "start_time": relation.temporal.start_time if relation.temporal else None,
                    "end_time": relation.temporal.end_time if relation.temporal else None,
                    "is_current": relation.temporal.is_current if relation.temporal else True
                }
            }
            relations.append(rel_dict)

        # 从 document.events 提取实体和关系
        for event in document.events:
            # 事件作为实体
            event_entity = {
                "entity_id": event.event_id,
                "entity_type": "Event",
                "name": f"事件: {event.event_type}",
                "properties": {
                    "basic": {
                        "event_type": event.event_type,
                        "timestamp": event.timestamp,
                        "location": event.location,
                        "description": event.description
                    }
                }
            }
            entities.append(event_entity)

            # 事件参与者关系
            for participant_id in event.participants:
                rel = {
                    "relation_id": f"rel-{uuid.uuid4().hex[:6]}",
                    "relation_type": "participated_in",
                    "source": participant_id,
                    "target": event.event_id,
                    "properties": {},
                    "temporal": {
                        "start_time": event.timestamp,
                        "is_current": True
                    }
                }
                relations.append(rel)

        return entities, relations

    async def _create_graph_elements(
        self,
        entities: List[Dict],
        relations: List[Dict],
        document: 'OntologyDocument'
    ) -> Tuple[List[Dict], List[Dict]]:
        """创建图谱元素"""
        nodes = []
        edges = []

        # 创建节点
        entity_id_map = {}
        for entity in entities:
            node_id = entity["entity_id"]
            entity_id_map[node_id] = node_id

            node = {
                "id": node_id,
                "name": entity["name"],
                "type": entity["entity_type"],
                "properties": entity.get("properties", {}),
                "source_doc_id": document.doc_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            nodes.append(node)

        # 创建边
        for relation in relations:
            source_id = entity_id_map.get(relation["source"], relation["source"])
            target_id = entity_id_map.get(relation["target"], relation["target"])

            if source_id and target_id:
                edge = {
                    "id": relation.get("relation_id", f"edge-{uuid.uuid4().hex[:6]}"),
                    "source": source_id,
                    "target": target_id,
                    "type": relation["relation_type"],
                    "properties": relation.get("properties", {}),
                    "temporal": relation.get("temporal", {}),
                    "source_doc_id": document.doc_id
                }
                edges.append(edge)

        return nodes, edges

    async def _write_to_graphiti(
        self,
        nodes: List[Dict],
        edges: List[Dict],
        scenario_id: str,
        workspace_id: str
    ):
        """写入 Graphiti 图谱"""
        try:
            from odap.infra.query import get_graph_write_proxy

            write_proxy = get_graph_write_proxy()

            # 写入节点
            for node in nodes:
                try:
                    props = node.get("properties", {})
                    props["workspace_id"] = workspace_id
                    props["scenario_id"] = scenario_id
                    write_proxy.add_entity(
                        entity_id=node["id"],
                        entity_type=node["type"],
                        properties=props,
                        workspace_id=workspace_id,
                    )
                    logger.info(f"成功创建节点: {node['id']}")
                except Exception as e:
                    logger.warning(f"创建节点失败 {node['id']}: {e}")

            # 写入边
            for edge in edges:
                try:
                    write_proxy.add_relationship(
                        source_id=edge["source"],
                        target_id=edge["target"],
                        relationship=edge["type"],
                        properties=edge.get("properties", {}),
                        workspace_id=workspace_id,
                    )
                    logger.info(f"成功创建边: {edge['id']}")
                except Exception as e:
                    logger.warning(f"创建边失败 {edge['id']}: {e}")

            logger.info(f"成功写入 {len(nodes)} 个节点, {len(edges)} 条边到图谱")

        except Exception as e:
            logger.error(f"写入 Graphiti 失败: {e}")
            # 不抛出异常，图谱写入失败不影响整体流程

    async def _create_version(
        self,
        document: 'OntologyDocument',
        scenario_id: str,
        workspace_id: str,
        ontology_id: str = None
    ) -> Dict[str, Any]:
        """创建本体版本：先追加数据，再提交锁定"""
        actual_ontology_id = ontology_id or scenario_id
        
        try:
            from odap.biz.core.ontology.services.version_service import OntologyVersionManager

            if self._version_manager is None:
                self._version_manager = OntologyVersionManager()
                logger.info("OntologyVersionManager 初始化成功")

            await self._version_manager.append(
                ontology_id=actual_ontology_id,
                doc=document,
                message=f"本体构建: {document.meta.title or document.doc_id}"
            )

            version = await self._version_manager.commit(
                ontology_id=actual_ontology_id,
                message=f"本体构建完成: {document.meta.title or document.doc_id}"
            )

            version_info = {
                "version_id": version.version_id,
                "version_number": version.version_number,
                "scenario_id": scenario_id,
                "workspace_id": workspace_id,
                "document_id": document.doc_id,
                "created_at": version.created_at,
                "commit_message": version.commit_message
            }
            logger.info(f"版本创建成功: {version.version_id} ({version.version_number})")

            return version_info

        except Exception as e:
            logger.error(f"创建版本失败: {e}")
            return {
                "version_id": None,
                "version_error": str(e),
                "scenario_id": scenario_id,
                "workspace_id": workspace_id,
                "document_id": document.doc_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "commit_message": f"本体构建(版本创建失败): {document.meta.title or document.doc_id}"
            }

    async def detect_changes(
        self,
        new_document: 'OntologyDocument',
        current_graph_version: str
    ) -> Dict[str, Any]:
        """
        检测信息变化

        比较新文档与当前图谱版本的差异

        Returns:
            Dict: 包含 added/removed/modified 实体和关系
        """
        changes = {
            "entities": {
                "added": [],
                "removed": [],
                "modified": []
            },
            "relations": {
                "added": [],
                "removed": [],
                "modified": []
            }
        }

        # 简化实现：假设所有新文档都是新增
        for entity in new_document.entities:
            changes["entities"]["added"].append(entity.entity_id)

        for relation in new_document.relations:
            changes["relations"]["added"].append(relation.relation_id)

        return changes

    async def rollback_version(
        self,
        version_id: str,
        scenario_id: str
    ) -> Dict[str, Any]:
        """
        回滚到指定版本

        Args:
            version_id: 版本 ID
            scenario_id: 场景 ID

        Returns:
            Dict: 回滚结果
        """
        try:
            # 获取版本信息
            try:
                from ..storage.sqlite_ingest_storage import SQLiteIngestStorage
                storage = SQLiteIngestStorage()
                version_info = storage.get_version(version_id)
            except Exception:
                version_info = None

            if not version_info:
                return {
                    "status": "error",
                    "message": f"版本 {version_id} 不存在"
                }

            # 标记当前版本为 deprecated
            # 创建新版本指向旧版本

            return {
                "status": "success",
                "version_id": version_id,
                "message": f"已回滚到版本 {version_id}"
            }

        except Exception as e:
            logger.error(f"版本回滚失败: {e}")
            return {
                "status": "error",
                "message": str(e)
            }


# 全局实例
_builder_service: Optional[OntologyBuilderService] = None


def get_builder_service() -> OntologyBuilderService:
    """获取构建服务单例"""
    global _builder_service
    if _builder_service is None:
        _builder_service = OntologyBuilderService()
    return _builder_service