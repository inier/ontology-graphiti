"""MongoDB存储实现"""

from typing import Dict, Any, List, Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from ..models.workspace import Workspace
from ..models.import_export import ImportExportRecord
import os


class MongoDBStorage:
    """MongoDB存储实现"""
    
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string or os.getenv("MONGODB_URI", "mongodb://graphiti-mongodb:27017")
        self.client = MongoClient(self.connection_string)
        self.db = self.client["workspace"]
        
        # 集合
        self.workspaces: Collection = self.db["workspaces"]
        self.isolation_policies: Collection = self.db["isolation_policies"]
        self.import_export_records: Collection = self.db["import_export_records"]
        self.scenarios: Collection = self.db["scenarios"]
        self.scenario_documents: Collection = self.db["scenario_documents"]
    
    # 工作空间相关
    def save_workspace(self, workspace: Workspace) -> None:
        """保存工作空间"""
        self.workspaces.insert_one(workspace.model_dump())
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """获取工作空间"""
        data = self.workspaces.find_one({"id": workspace_id})
        return Workspace(**data) if data else None
    
    def update_workspace(self, workspace: Workspace) -> None:
        """更新工作空间"""
        self.workspaces.update_one({"id": workspace.id}, {"$set": workspace.model_dump()})
    
    def delete_workspace(self, workspace_id: str) -> None:
        """删除工作空间"""
        self.workspaces.delete_one({"id": workspace_id})
    
    def list_workspaces(self, filters: Dict[str, Any] = None, 
                      page: int = 1, page_size: int = 10) -> List[Workspace]:
        """列出工作空间"""
        query = filters or {}
        workspaces = self.workspaces.find(query).skip((page - 1) * page_size).limit(page_size)
        return [Workspace(**ws) for ws in workspaces]
    
    # 隔离策略相关
    def save_isolation_policy(self, policy: Dict[str, Any]) -> None:
        """保存隔离策略"""
        self.isolation_policies.insert_one(policy)
    
    def get_isolation_policy(self, workspace_id: str) -> Dict[str, Any]:
        """获取隔离策略"""
        return self.isolation_policies.find_one({"workspace_id": workspace_id}) or {}
    
    def update_isolation_policy(self, workspace_id: str, policy: Dict[str, Any]) -> None:
        """更新隔离策略"""
        self.isolation_policies.update_one({"workspace_id": workspace_id}, {"$set": policy}, upsert=True)
    
    # 导入导出记录相关
    def save_import_export_record(self, record: ImportExportRecord) -> None:
        """保存导入导出记录"""
        self.import_export_records.insert_one(record.model_dump())
    
    def get_import_export_record(self, record_id: str) -> Optional[ImportExportRecord]:
        """获取导入导出记录"""
        data = self.import_export_records.find_one({"id": record_id})
        return ImportExportRecord(**data) if data else None
    
    def update_import_export_record(self, record: ImportExportRecord) -> None:
        """更新导入导出记录"""
        self.import_export_records.update_one({"id": record.id}, {"$set": record.model_dump()})
    
    def list_import_export_records(self, filters: Dict[str, Any] = None, 
                                 page: int = 1, page_size: int = 10) -> List[ImportExportRecord]:
        """列出导入导出记录"""
        query = filters or {}
        records = self.import_export_records.find(query).skip((page - 1) * page_size).limit(page_size)
        return [ImportExportRecord(**record) for record in records]
    
    # 场景相关
    def save_scenario(self, scenario: Dict[str, Any]) -> str:
        """保存场景"""
        # 过滤掉 _id 字段，避免 MongoDB ObjectId 序列化问题
        scenario_to_save = {k: v for k, v in scenario.items() if k != '_id'}
        
        if "scenario_id" not in scenario_to_save:
            import uuid
            from datetime import datetime, timezone
            scenario_id = f"scenario-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
            scenario_to_save["scenario_id"] = scenario_id
            scenario_to_save["created_at"] = datetime.now(timezone.utc).isoformat()
            scenario_to_save["doc_count"] = 0
            scenario_to_save["event_count"] = 0
            scenario_to_save["entity_count"] = 0
        
        result = self.scenarios.insert_one(scenario_to_save)
        return scenario_to_save["scenario_id"]
    
    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """获取场景"""
        scenario = self.scenarios.find_one({"scenario_id": scenario_id})
        if scenario and '_id' in scenario:
            del scenario['_id']
        return scenario
    
    def update_scenario(self, scenario_id: str, updates: Dict[str, Any]) -> None:
        """更新场景"""
        self.scenarios.update_one({"scenario_id": scenario_id}, {"$set": updates})
    
    def delete_scenario(self, scenario_id: str) -> None:
        """删除场景"""
        self.scenarios.delete_one({"scenario_id": scenario_id})
        self.scenario_documents.delete_many({"scenario_id": scenario_id})
    
    def list_scenarios(self) -> List[Dict[str, Any]]:
        """列出场景"""
        scenarios = list(self.scenarios.find())
        # 过滤掉 _id 字段，因为 ObjectId 无法被 JSON 序列化
        for scenario in scenarios:
            if '_id' in scenario:
                del scenario['_id']
        return scenarios
    
    def get_scenarios_by_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        """获取工作空间的场景"""
        scenarios = list(self.scenarios.find({"workspace_id": workspace_id}))
        # 过滤掉 _id 字段
        for scenario in scenarios:
            if '_id' in scenario:
                del scenario['_id']
        return scenarios
    
    def add_scenario_document(self, scenario_id: str, document: Dict[str, Any]) -> None:
        """添加场景文档"""
        # 过滤掉 _id 字段，避免 MongoDB ObjectId 序列化问题
        doc_to_save = {k: v for k, v in document.items() if k != '_id'}
        doc_to_save["scenario_id"] = scenario_id
        self.scenario_documents.insert_one(doc_to_save)
        
        # 更新场景统计信息
        doc_count = self.scenario_documents.count_documents({"scenario_id": scenario_id})
        
        # 计算事件和实体数量
        docs = list(self.scenario_documents.find({"scenario_id": scenario_id}))
        event_count = sum(len(d.get("events", [])) for d in docs)
        entity_count = sum(len(d.get("entities", [])) for d in docs)
        
        self.scenarios.update_one(
            {"scenario_id": scenario_id},
            {"$set": {
                "doc_count": doc_count,
                "event_count": event_count,
                "entity_count": entity_count
            }}
        )
    
    def get_scenario_documents(self, scenario_id: str) -> List[Dict[str, Any]]:
        """获取场景文档"""
        documents = list(self.scenario_documents.find({"scenario_id": scenario_id}))
        for doc in documents:
            if '_id' in doc:
                del doc['_id']
        return documents
    
    def get_scenario_timeline(self, scenario_id: str) -> List[Dict[str, Any]]:
        """获取场景时间线"""
        docs = self.get_scenario_documents(scenario_id)
        events = []
        for doc in docs:
            if "events" in doc:
                events.extend(doc["events"])
        events.sort(key=lambda x: x.get("timestamp", ""))
        return events
    
    def get_scenario_entities(self, scenario_id: str) -> List[Dict[str, Any]]:
        """获取场景实体"""
        docs = self.get_scenario_documents(scenario_id)
        entity_map = {}
        for doc in docs:
            if "entities" in doc:
                for entity in doc["entities"]:
                    entity_id = entity.get("entity_id")
                    if entity_id:
                        entity_map[entity_id] = entity
        return list(entity_map.values())
    
    def get_scenario_relations(self, scenario_id: str) -> Dict[str, Any]:
        """获取场景关系"""
        entities = self.get_scenario_entities(scenario_id)
        docs = self.get_scenario_documents(scenario_id)
        nodes = []
        links = []
        node_ids = set()
        
        import uuid
        
        for entity in entities:
            entity_id = entity.get("entity_id")
            if entity_id and entity_id not in node_ids:
                nodes.append({
                    "id": entity_id,
                    "name": entity.get("name", entity_id),
                    "type": entity.get("entity_type", "Entity"),
                    "side": entity.get("basic_properties", {}).get("side"),
                })
                node_ids.add(entity_id)
        
        for doc in docs:
            if "events" in doc:
                for event in doc["events"]:
                    participants = event.get("participants", [])
                    if len(participants) >= 2:
                        for i in range(len(participants) - 1):
                            source = participants[i]
                            target = participants[i + 1]
                            if source in node_ids and target in node_ids:
                                links.append({
                                    "id": f"rel-{uuid.uuid4().hex[:8]}",
                                    "source": source,
                                    "target": target,
                                    "type": event.get("event_type", "association"),
                                    "event_id": event.get("event_id"),
                                })
        
        return {"nodes": nodes, "links": links}
