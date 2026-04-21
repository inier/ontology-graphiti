"""版本管理服务"""

from typing import Dict, Any, List, Optional
from ..impl.version import VersionManager
from ..models.version import VersionStatus


class VersionManagementService:
    """版本管理服务"""
    
    def __init__(self):
        self.manager = VersionManager()
    
    def create_version(self, ontology_id: str, version_number: str, 
                      parent_version_id: Optional[str] = None, 
                      change_summary: str = "") -> Dict[str, Any]:
        """创建版本
        
        Args:
            ontology_id: 本体ID
            version_number: 版本号
            parent_version_id: 父版本ID
            change_summary: 变更摘要
            
        Returns:
            版本信息
        """
        version = self.manager.create_version(
            ontology_id=ontology_id,
            version_number=version_number,
            parent_version_id=parent_version_id,
            change_summary=change_summary
        )
        
        return {
            "version_id": version.id,
            "ontology_id": version.ontology_id,
            "version_number": version.version_number,
            "parent_version_id": version.parent_version_id,
            "status": version.status.value,
            "change_summary": version.change_summary,
            "created_at": version.created_at.isoformat(),
            "is_current": version.is_current
        }
    
    def get_version(self, version_id: str) -> Dict[str, Any]:
        """获取版本
        
        Args:
            version_id: 版本ID
            
        Returns:
            版本信息
        """
        version = self.manager.get_version(version_id)
        if not version:
            return {"status": "error", "message": "Version not found"}
        
        return {
            "version_id": version.id,
            "ontology_id": version.ontology_id,
            "version_number": version.version_number,
            "parent_version_id": version.parent_version_id,
            "status": version.status.value,
            "changes": [change.model_dump() for change in version.changes],
            "change_summary": version.change_summary,
            "created_at": version.created_at.isoformat(),
            "is_current": version.is_current,
            "is_stable": version.is_stable
        }
    
    def list_versions(self, ontology_id: str, 
                     filters: Dict[str, Any] = None, 
                     page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """列出版本
        
        Args:
            ontology_id: 本体ID
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            版本列表和分页信息
        """
        versions = self.manager.list_versions(ontology_id, filters, page, page_size)
        
        version_list = []
        for version in versions:
            version_list.append({
                "version_id": version.id,
                "version_number": version.version_number,
                "status": version.status.value,
                "change_summary": version.change_summary,
                "created_at": version.created_at.isoformat(),
                "is_current": version.is_current,
                "is_stable": version.is_stable
            })
        
        return {
            "versions": version_list,
            "page": page,
            "page_size": page_size,
            "total": len(versions)  # 实际项目中应该返回总记录数
        }
    
    def rollback_version(self, ontology_id: str, target_version_id: str) -> Dict[str, Any]:
        """回滚版本
        
        Args:
            ontology_id: 本体ID
            target_version_id: 目标版本ID
            
        Returns:
            新创建的版本信息
        """
        try:
            new_version = self.manager.rollback_version(ontology_id, target_version_id)
            return {
                "status": "success",
                "version_id": new_version.id,
                "version_number": new_version.version_number,
                "change_summary": new_version.change_summary
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def compare_versions(self, source_version_id: str, target_version_id: str) -> Dict[str, Any]:
        """对比版本
        
        Args:
            source_version_id: 源版本ID
            target_version_id: 目标版本ID
            
        Returns:
            版本对比结果
        """
        try:
            comparison = self.manager.compare_versions(source_version_id, target_version_id)
            return {
                "status": "success",
                "source_version_id": comparison.source_version_id,
                "target_version_id": comparison.target_version_id,
                "added_entities": comparison.added_entities,
                "removed_entities": comparison.removed_entities,
                "modified_entities": comparison.modified_entities,
                "added_relations": comparison.added_relations,
                "removed_relations": comparison.removed_relations,
                "modified_relations": comparison.modified_relations,
                "compatibility_score": comparison.compatibility_score,
                "comparison_time": comparison.comparison_time.isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def merge_versions(self, ontology_id: str, source_version_id: str, 
                      target_version_id: str, conflict_resolution: Dict[str, Any] = None) -> Dict[str, Any]:
        """合并版本
        
        Args:
            ontology_id: 本体ID
            source_version_id: 源版本ID
            target_version_id: 目标版本ID
            conflict_resolution: 冲突解决策略
            
        Returns:
            合并后的版本信息
        """
        try:
            new_version = self.manager.merge_versions(
                ontology_id=ontology_id,
                source_version_id=source_version_id,
                target_version_id=target_version_id,
                conflict_resolution=conflict_resolution
            )
            return {
                "status": "success",
                "version_id": new_version.id,
                "version_number": new_version.version_number,
                "change_summary": new_version.change_summary
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def get_version_history(self, ontology_id: str) -> List[Dict[str, Any]]:
        """获取版本历史
        
        Args:
            ontology_id: 本体ID
            
        Returns:
            版本历史记录
        """
        return self.manager.get_version_history(ontology_id)
