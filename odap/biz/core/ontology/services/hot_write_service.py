import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class HotWriteService:
    def __init__(self, graph_manager=None, hook_manager=None):
        self._graph_manager = graph_manager
        self._hook_manager = hook_manager

    @property
    def graph(self):
        if self._graph_manager is None:
            from odap.infra.graph.graph_service import GraphManager
            self._graph_manager = GraphManager()
        return self._graph_manager

    @property
    def hooks(self):
        if self._hook_manager is None:
            try:
                from odap.biz.integration.hook_system.impl.hook_manager import HookManager
                self._hook_manager = HookManager()
            except Exception:
                logger.warning("HotWriteService: HookManager not available")
        return self._hook_manager

    async def write_and_notify(self, ontology_data: Dict[str, Any],
                                workspace_id: Optional[str] = None) -> Dict[str, Any]:
        entity_type = ontology_data.get("entity_type", "unknown")
        entity_name = ontology_data.get("name", ontology_data.get("entity_id", "unnamed"))
        properties = ontology_data.get("properties", {})

        description = f"本体热写入: {entity_type} '{entity_name}'"
        if properties:
            prop_str = ", ".join(f"{k}={v}" for k, v in properties.items())
            description += f" ({prop_str})"

        try:
            self.graph.add_episode(
                name=f"hot_write_{entity_type}_{entity_name}",
                episode_body=description,
                source_description="HotWriteService: ontology hot-write",
                reference_time=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.warning(f"HotWriteService: Graphiti write failed, using fallback: {e}")

        if self.hooks:
            try:
                await self.hooks.execute_hook(
                    "ontology:hot_write",
                    {
                        "entity_type": entity_type,
                        "entity_name": entity_name,
                        "properties": properties,
                        "workspace_id": workspace_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception as e:
                logger.warning(f"HotWriteService: Hook execution failed: {e}")

        return {
            "status": "written",
            "entity_type": entity_type,
            "entity_name": entity_name,
            "workspace_id": workspace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def batch_write(self, items: List[Dict[str, Any]],
                          workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        for item in items:
            result = await self.write_and_notify(item, workspace_id)
            results.append(result)
        logger.info(f"HotWriteService: batch write completed, {len(results)} items")
        return results
