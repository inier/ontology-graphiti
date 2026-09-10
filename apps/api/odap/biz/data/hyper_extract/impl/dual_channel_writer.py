import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("dual_channel_writer")


class DualChannelWriter:
    """双通道写入器：Channel A 通过 GraphWriteProxy 写结构化实体/关系，
    Channel B 通过 GraphManager.save_audit_episode 写审计 Episode（零 LLM，ADR-074）。

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
            # D5 修复：GraphManager 靠 __new__ 实现单例，无 get_instance() 类方法；
            # 直接实例化即可拿到单例（原调用 get_instance() 抛 AttributeError 被静默吞掉）。
            self._graph_manager = GraphManager()
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

        # ---- Channel B: 审计 Episode 写入（零 LLM，ADR-074）----
        try:
            audit_event = self._build_audit_event(
                doc, entities_written, relations_written, valid_time, workspace_id
            )
            gm = self.graph_manager
            if gm is not None:
                success = await gm.save_audit_episode(
                    audit_data=audit_event,
                    valid_at=valid_time,
                    source_description="hyper-extract",
                )
                if success:
                    logger.info("Channel B 审计 Episode 保存成功（零 LLM）")
                else:
                    logger.warning("Channel B 审计 Episode 保存失败")
            else:
                logger.warning("Channel B 跳过: GraphManager 不可用")
        except Exception as exc:
            logger.warning("Channel B 审计写入失败（不影响 Channel A）: %s", exc)

        return {
            "status": "ok",
            "entities_written": entities_written,
            "relations_written": relations_written,
            "valid_time": valid_time_iso,
        }

    def _build_audit_event(
        self,
        doc: Dict[str, Any],
        entities_written: int,
        relations_written: int,
        valid_time: Optional[datetime],
        workspace_id: str,
    ) -> Dict[str, Any]:
        """构建审计事件数据（ADR-074，替代 _build_episode_text）。

        产出结构化审计事件，由 Graphiti EpisodicNode.save 零 LLM 保存。
        """
        return {
            "event_type": "extraction_completed",
            "workspace_id": workspace_id,
            "entities_total": len(doc.get("entities") or []),
            "relations_total": len(doc.get("relations") or []),
            "entities_written": entities_written,
            "relations_written": relations_written,
            "valid_time": valid_time.isoformat() if valid_time else None,
            "recorded_at": datetime.now().isoformat(),
        }

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
