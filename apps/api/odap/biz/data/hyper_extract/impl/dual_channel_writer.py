import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("dual_channel_writer")


class DualChannelWriter:
    """双通道写入器：Channel A 通过 GraphWriteProxy 写结构化实体/关系，
    Channel B 通过 GraphManager.add_episode 写自然语言 Episode。

    Channel B 失败不影响 Channel A 结果。
    """

    def __init__(self):
        self._write_proxy = None
        self._graph_manager = None

    @property
    def write_proxy(self):
        """惰性加载 GraphWriteProxy 单例"""
        if self._write_proxy is None:
            from odap.infra.query.graph_write_proxy import get_graph_write_proxy
            self._write_proxy = get_graph_write_proxy()
        return self._write_proxy

    @property
    def graph_manager(self):
        """惰性加载 GraphManager 单例"""
        if self._graph_manager is None:
            from odap.infra.graph.graph_service import GraphManager
            self._graph_manager = GraphManager.get_instance()
        return self._graph_manager

    async def write(
        self,
        doc: Dict[str, Any],
        workspace_id: str,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """将抽取结果写入图谱（双通道）。

        Args:
            doc: 包含 "entities" 和 "relations" 的抽取结果
            workspace_id: 工作空间 ID
            scenario_id: 场景 ID（可选）

        Returns:
            {"status": "ok"/"error", "entities_written": N, "relations_written": N, "valid_time": iso}
        """
        entities = doc.get("entities") or []
        relations = doc.get("relations") or []

        if not entities and not relations:
            return {"status": "error", "message": "No data to write"}

        valid_time = self._extract_valid_time(doc)
        valid_time_iso = (
            valid_time.isoformat() if valid_time else datetime.now().isoformat()
        )

        # ---- Channel A: 结构化写入 ----
        entities_written = 0
        for ent in entities:
            entity_id = ent.get("entity_id", "")
            entity_type = ent.get("entity_type", "")
            if not entity_id or not entity_type:
                logger.warning("实体缺少 entity_id 或 entity_type，跳过: %s", ent)
                continue

            properties: Dict[str, Any] = {"name": ent.get("name", "")}
            for key in (
                "basic_properties",
                "statistical_properties",
                "capabilities",
                "constraints",
            ):
                val = ent.get(key)
                if val:
                    properties[key] = val

            result = self.write_proxy.add_entity(
                entity_id, entity_type, properties, workspace_id
            )
            if result.get("status") == "success":
                entities_written += 1
            else:
                logger.warning(
                    "Channel A add_entity 失败: entity_id=%s, reason=%s",
                    entity_id,
                    result.get("message", "unknown"),
                )

        relations_written = 0
        for rel in relations:
            source = rel.get("source", "")
            target = rel.get("target", "")
            relation_type = rel.get("relation_type", "")
            if not source or not target or not relation_type:
                logger.warning(
                    "关系缺少 source/target/relation_type，跳过: %s", rel
                )
                continue

            rel_props = rel.get("properties")
            result = self.write_proxy.add_relationship(
                source, target, relation_type, rel_props, workspace_id
            )
            if result.get("status") == "success":
                relations_written += 1
            else:
                logger.warning(
                    "Channel A add_relationship 失败: %s→%s (%s), reason=%s",
                    source,
                    target,
                    relation_type,
                    result.get("message", "unknown"),
                )

        # ---- Channel B: Episode 写入 ----
        try:
            episode_body = self._build_episode_text(doc)
            if episode_body:
                gm = self.graph_manager
                if gm is not None:
                    await gm.add_episode(
                        name="hyper-extract",
                        content=episode_body,
                        source_description="hyper-extract",
                        reference_time=valid_time,
                    )
                    logger.info("Channel B add_episode 成功")
                else:
                    logger.warning("Channel B 跳过: GraphManager 不可用")
        except Exception as exc:
            logger.warning("Channel B add_episode 失败（不影响 Channel A）: %s", exc)

        return {
            "status": "ok",
            "entities_written": entities_written,
            "relations_written": relations_written,
            "valid_time": valid_time_iso,
        }

    def _build_episode_text(self, doc: Dict[str, Any]) -> str:
        """从抽取结果构建结构化摘要文本，供 Graphiti add_episode 使用。"""
        parts: list = []

        for ent in doc.get("entities") or []:
            name = ent.get("name", "")
            entity_type = ent.get("entity_type", "")
            description = ent.get("description", "") or ent.get("basic_properties", {}).get("description", "")
            line = f"实体: {name} 是一个 {entity_type}。"
            if description:
                line += description
            parts.append(line)

        for rel in doc.get("relations") or []:
            source = rel.get("source", "")
            target = rel.get("target", "")
            relation_type = rel.get("relation_type", "")
            parts.append(f"{source} 与 {target} 之间存在 {relation_type} 关系。")

        return "\n".join(parts)

    def _extract_valid_time(self, doc: Dict[str, Any]) -> Optional[datetime]:
        """从 doc 的 events 中提取有效时间，找不到则返回 None。"""
        events = doc.get("events") or []
        for event in events:
            time_str = event.get("time") if isinstance(event, dict) else None
            if time_str:
                try:
                    return datetime.fromisoformat(time_str)
                except (ValueError, TypeError):
                    continue
        return None
