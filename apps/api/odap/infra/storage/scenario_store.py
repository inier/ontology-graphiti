"""ScenarioStore — 场景持久化存储（SQLite 单源）

ADR-067: 从 biz/shared/ 迁移到 infra/storage/，明确其基础设施定位。
"""

import os
import json
import copy
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("simulator_web")


def _scenario_audit(action: str, *, result_status: str = "success",
                    result_message: str = "", resource: str = None,
                    details: Dict[str, Any] = None) -> None:
    """Scenario 存储操作审计（actor=system），失败不阻断业务"""
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="simulation_sandbox",
        )
    except Exception as e:
        logger.warning(f"Audit write failed for action={action}: {e}")

SCENARIOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "storage",
    "versions",
    "scenarios"
)


class ScenarioStore:
    """
    场景持久化存储 — SQLite 单源
    管理场景元数据和关联的 OntologyDocument
    所有数据存储在 ingest.db 中
    """

    def __init__(self, storage_dir: str = SCENARIOS_DIR, graph_manager=None):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self._graph_manager = graph_manager
        from odap.biz.core.ontology.construction.pipeline.services import IngestService
        self._db = IngestService().storage
        self._migrate_from_json()

    def _migrate_from_json(self):
        """一次性迁移: scenarios.json → SQLite（含实体消歧）"""
        json_file = os.path.join(self.storage_dir, "scenarios.json")
        if not os.path.exists(json_file):
            return

        existing = self._db.list_scenarios()
        if existing:
            return

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            from odap.biz.core.ontology.design.schema.document import deterministic_entity_id

            for sid, scenario in data.get("scenarios", {}).items():
                self._db.save_scenario(scenario)

            for sid, docs in data.get("documents", {}).items():
                for doc in docs:
                    resolved_entities = []
                    id_remap = {}
                    for entity in doc.get("entities", []):
                        old_id = entity.get("entity_id", "")
                        name = entity.get("name", "")
                        etype = entity.get("entity_type", "Unit")
                        if name:
                            new_id = deterministic_entity_id(etype, name)
                            if old_id != new_id:
                                id_remap[old_id] = new_id
                            entity["entity_id"] = new_id
                        resolved_entities.append(entity)
                    doc["entities"] = resolved_entities

                    for event in doc.get("events", []):
                        participants = event.get("participants", [])
                        event["participants"] = [id_remap.get(p, p) for p in participants]

                    self._db.add_scenario_document(sid, doc)

            logger.info(f"JSON → SQLite 迁移完成: {len(data.get('scenarios', {}))} 场景")
        except Exception as e:
            logger.warning(f"JSON 迁移失败: {e}")

    def create(self, name: str, description: str = "") -> str:
        """创建场景"""
        scenario_id = f"scenario-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

        ontology_id = str(uuid.uuid4())

        scenario = {
            "scenario_id": scenario_id,
            "name": name,
            "description": description,
            "workspace_id": "default",
            "ontology_id": ontology_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "doc_count": 0,
            "event_count": 0,
            "entity_count": 0,
        }

        try:
            self._db.save_scenario(scenario)
            self._ensure_initial_version(ontology_id, name)
            _scenario_audit(
                "scenario_create",
                result_status="success",
                resource=scenario_id,
                details={"scenario_id": scenario_id, "ontology_id": ontology_id},
            )
            return scenario_id
        except Exception as e:
            _scenario_audit(
                "scenario_create",
                result_status="failure",
                resource=scenario_id,
                result_message=str(e),
                details={"scenario_id": scenario_id, "ontology_id": ontology_id},
            )
            raise

    def _ensure_initial_version(self, ontology_id: str, scenario_name: str = "") -> None:
        """确保本体有初始版本"""
        try:
            from odap.biz.core.ontology import OntologyVersionManager
            vm = OntologyVersionManager.get_instance()
            vm.ensure_initial_version(ontology_id, scenario_name)
        except Exception as e:
            logger.warning(f"Failed to ensure initial version for {ontology_id}: {e}")

    def add_document(self, scenario_id: str, doc):
        """添加文档到场景"""
        doc_dict = {
            "doc_id": doc.doc_id,
            "meta": doc.meta.model_dump() if hasattr(doc.meta, 'model_dump') else vars(doc.meta),
            "entities": [e.to_dict() if hasattr(e, 'to_dict') else e for e in doc.entities],
            "events": [ev.to_dict() if hasattr(ev, 'to_dict') else ev for ev in doc.events],
            "ontology_version": doc.ontology_version.__dict__ if doc.ontology_version else None,
        }

        self._db.add_scenario_document(scenario_id, doc_dict)

    def get_timeline(self, scenario_id: str) -> List[Dict[str, Any]]:
        """获取时间线（所有事件按时间戳排序）"""
        return self._db.get_scenario_timeline(scenario_id)

    def get_entities(self, scenario_id: str, snapshot_time: str = None) -> List[Dict[str, Any]]:
        """获取实体快照"""
        return self._db.get_scenario_entities(scenario_id)

    def get_relations(self, scenario_id: str) -> Dict[str, Any]:
        """获取关系图谱"""
        return self._db.get_scenario_relations(scenario_id)

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """列出所有场景"""
        return self._db.list_scenarios()

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """获取场景"""
        return self._db.get_scenario(scenario_id)

    def update_scenario(self, scenario_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新场景"""
        audit_updates = {k: v for k, v in updates.items()
                         if k in ("doc_count", "event_count", "entity_count",
                                  "synced_entities", "synced_events", "last_synced")}
        try:
            success = self._db.update_scenario(scenario_id, updates)
            if success:
                result = self._db.get_scenario(scenario_id)
                _scenario_audit(
                    "scenario_update",
                    result_status="success",
                    resource=scenario_id,
                    details={
                        "scenario_id": scenario_id,
                        "updated_fields_count": len(updates),
                        **({"doc_count": result.get("doc_count")} if result and "doc_count" in result else {}),
                        **({"entity_count": result.get("entity_count")} if result and "entity_count" in result else {}),
                        **({"event_count": result.get("event_count")} if result and "event_count" in result else {}),
                    },
                )
                return result
            _scenario_audit(
                "scenario_update",
                result_status="failure",
                resource=scenario_id,
                result_message="Scenario not found or no-op update",
                details={"scenario_id": scenario_id},
            )
            return None
        except Exception as e:
            _scenario_audit(
                "scenario_update",
                result_status="failure",
                resource=scenario_id,
                result_message=str(e),
                details={"scenario_id": scenario_id, "updated_fields_count": len(updates)},
            )
            raise

    def delete_scenario(self, scenario_id: str) -> bool:
        """删除场景"""
        try:
            result = self._db.delete_scenario(scenario_id)
            _scenario_audit(
                "scenario_delete",
                result_status="success" if result else "failure",
                resource=scenario_id,
                result_message="" if result else "Scenario not found",
                details={"scenario_id": scenario_id},
            )
            return result
        except Exception as e:
            _scenario_audit(
                "scenario_delete",
                result_status="failure",
                resource=scenario_id,
                result_message=str(e),
                details={"scenario_id": scenario_id},
            )
            raise

    def clone_scenario(self, source_scenario_id: str, new_name: str = "") -> Optional[str]:
        """克隆场景（关键操作，必记审计）"""
        source = self._db.get_scenario(source_scenario_id)
        if not source:
            _scenario_audit(
                "scenario_clone",
                result_status="failure",
                resource=source_scenario_id,
                result_message="Source scenario not found",
                details={"source_scenario_id": source_scenario_id},
            )
            return None
        try:
            new_scenario_id = f"scenario-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
            cloned = copy.deepcopy(source)
            cloned["scenario_id"] = new_scenario_id
            cloned["name"] = new_name or f"{source.get('name', 'scenario')} (clone)"
            cloned["created_at"] = datetime.now(timezone.utc).isoformat()
            cloned["cloned_from"] = source_scenario_id
            cloned["ontology_id"] = str(uuid.uuid4())

            self._db.save_scenario(cloned)

            docs = self._db.get_scenario_documents(source_scenario_id)
            for doc in docs:
                self._db.add_scenario_document(new_scenario_id, copy.deepcopy(doc))

            _scenario_audit(
                "scenario_clone",
                result_status="success",
                resource=new_scenario_id,
                details={
                    "source_scenario_id": source_scenario_id,
                    "new_scenario_id": new_scenario_id,
                    "doc_count": len(docs),
                    "entity_count": source.get("entity_count", 0),
                    "event_count": source.get("event_count", 0),
                },
            )
            return new_scenario_id
        except Exception as e:
            _scenario_audit(
                "scenario_clone",
                result_status="failure",
                resource=source_scenario_id,
                result_message=str(e),
                details={"source_scenario_id": source_scenario_id},
            )
            raise

    def get_documents(self, scenario_id: str) -> List[Dict[str, Any]]:
        """获取场景文档"""
        return self._db.get_scenario_documents(scenario_id)

    def sync_to_graphiti(self, scenario_id: str) -> Dict[str, Any]:
        """将场景同步到 Graphiti"""
        scenario = self._db.get_scenario(scenario_id)
        if not scenario:
            return {"status": "error", "error": f"Scenario {scenario_id} not found"}

        documents = self._db.get_scenario_documents(scenario_id)

        if not self._graph_manager:
            return {"status": "warning", "message": "GraphManager not initialized, using fallback", "synced_scenario": scenario_id}

        try:
            synced_entities = 0
            synced_events = 0

            for doc in documents:
                if "entities" in doc:
                    for entity_dict in doc["entities"]:
                        entity_id = entity_dict.get("entity_id", "")
                        entity_type = entity_dict.get("entity_type", "Entity")
                        properties = entity_dict.get("basic_properties", {})

                        if entity_id:
                            if "name" in entity_dict and "name" not in properties:
                                properties["name"] = entity_dict["name"]

                            self._graph_manager.add_entity(
                                entity_id=entity_id,
                                entity_type=entity_type,
                                properties=properties
                            )
                            synced_entities += 1

                if "events" in doc:
                    for event_dict in doc["events"]:
                        participants = event_dict.get("participants", [])
                        event_type = event_dict.get("event_type", "ASSOCIATION")

                        if len(participants) >= 2:
                            for i in range(len(participants) - 1):
                                source = participants[i]
                                target = participants[i + 1]

                                rel_properties = {
                                    "event_id": event_dict.get("event_id"),
                                    "timestamp": event_dict.get("timestamp"),
                                    "event_type": event_type,
                                    "description": event_dict.get("description"),
                                    "scenario_id": scenario_id
                                }

                                self._graph_manager.add_relationship(
                                    source_id=source,
                                    target_id=target,
                                    relationship=event_type.upper().replace(" ", "_"),
                                    properties=rel_properties
                                )
                                synced_events += 1

            self._db.update_scenario(scenario_id, {
                "last_synced": datetime.now(timezone.utc).isoformat(),
                "synced_entities": synced_entities,
                "synced_events": synced_events,
            })

            return {
                "status": "success",
                "synced_scenario": scenario_id,
                "synced_entities": synced_entities,
                "synced_events": synced_events,
                "graph_mode": self._graph_manager._mode
            }

        except Exception as e:
            logger.error(f"Sync to Graphiti failed: {e}")
            return {"status": "error", "error": str(e), "synced_scenario": scenario_id}


# 模块级单例 — 全项目共享
scenario_store = ScenarioStore()
