"""版本管理实现"""

from typing import Dict, Any, List, Optional
from ..interfaces.version import IVersionManager
from ..models.version import OntologyVersion, VersionChange, VersionComparison
from ..storage.mongodb_storage import MongoDBStorage


class VersionManager(IVersionManager):
    """版本管理实现"""
    
    def __init__(self):
        self.storage = MongoDBStorage()
    
    def create_version(self, ontology_id: str, version_number: str, 
                      parent_version_id: Optional[str] = None, 
                      change_summary: str = "") -> OntologyVersion:
        """创建版本"""
        version = OntologyVersion(
            ontology_id=ontology_id,
            version_number=version_number,
            parent_version_id=parent_version_id,
            change_summary=change_summary
        )
        self.storage.save_version(version)
        
        # 更新其他版本的is_current标志
        self._update_current_version(ontology_id, version.id)
        
        return version
    
    def get_version(self, version_id: str) -> Optional[OntologyVersion]:
        """获取版本"""
        return self.storage.get_version(version_id)
    
    def list_versions(self, ontology_id: str, 
                     filters: Dict[str, Any] = None, 
                     page: int = 1, page_size: int = 10) -> List[OntologyVersion]:
        """列出版本"""
        return self.storage.list_versions(ontology_id, filters, page, page_size)
    
    def rollback_version(self, ontology_id: str, target_version_id: str) -> OntologyVersion:
        """回滚版本"""
        target_version = self.get_version(target_version_id)
        if not target_version:
            raise ValueError("Target version not found")
        
        # 创建新的回滚版本
        new_version = OntologyVersion(
            ontology_id=ontology_id,
            version_number=f"{target_version.version_number}-rollback",
            parent_version_id=target_version_id,
            change_summary=f"Rollback to version {target_version.version_number}"
        )
        
        self.storage.save_version(new_version)
        self._update_current_version(ontology_id, new_version.id)
        
        return new_version
    
    def compare_versions(self, source_version_id: str, target_version_id: str) -> VersionComparison:
        """对比版本"""
        source_version = self.get_version(source_version_id)
        target_version = self.get_version(target_version_id)
        
        if not source_version or not target_version:
            raise ValueError("Version not found")
        
        # 这里实现版本对比逻辑
        # 实际项目中需要比较实体、关系等的差异
        comparison = VersionComparison(
            source_version_id=source_version_id,
            target_version_id=target_version_id
        )
        
        # 简单的示例实现
        comparison.compatibility_score = 0.8
        
        return comparison
    
    def merge_versions(self, ontology_id: str, source_version_id: str, 
                      target_version_id: str, conflict_resolution: Dict[str, Any] = None) -> OntologyVersion:
        """合并版本"""
        source_version = self.get_version(source_version_id)
        target_version = self.get_version(target_version_id)
        
        if not source_version or not target_version:
            raise ValueError("Version not found")
        
        # 创建新的合并版本
        new_version = OntologyVersion(
            ontology_id=ontology_id,
            version_number=f"{target_version.version_number}-merged",
            parent_version_id=target_version_id,
            change_summary=f"Merged with version {source_version.version_number}"
        )
        
        self.storage.save_version(new_version)
        self._update_current_version(ontology_id, new_version.id)
        
        return new_version
    
    def get_version_history(self, ontology_id: str) -> List[Dict[str, Any]]:
        """获取版本历史"""
        versions = self.list_versions(ontology_id)
        history = []
        
        for version in versions:
            history.append({
                "version_id": version.id,
                "version_number": version.version_number,
                "status": version.status.value,
                "created_at": version.created_at.isoformat(),
                "change_summary": version.change_summary,
                "is_current": version.is_current
            })
        
        return history
    
    def _update_current_version(self, ontology_id: str, current_version_id: str):
        """更新当前版本标志"""
        versions = self.list_versions(ontology_id)
        for version in versions:
            version.is_current = (version.id == current_version_id)
            self.storage.update_version(version)
