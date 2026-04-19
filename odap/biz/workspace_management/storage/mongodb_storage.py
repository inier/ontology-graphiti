"""MongoDB存储实现"""

from typing import Dict, Any, List, Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from ..models.workspace import Workspace
from ..models.import_export import ImportExportRecord


class MongoDBStorage:
    """MongoDB存储实现"""
    
    def __init__(self, connection_string: str = "mongodb://localhost:27017"):
        self.client = MongoClient(connection_string)
        self.db = self.client["workspace_management"]
        
        # 集合
        self.workspaces: Collection = self.db["workspaces"]
        self.isolation_policies: Collection = self.db["isolation_policies"]
        self.import_export_records: Collection = self.db["import_export_records"]
    
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
