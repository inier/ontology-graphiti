"""版本管理接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.version import OntologyVersion, VersionChange, VersionComparison, VersionOperation


class IVersionManager(ABC):
    """版本管理接口"""
    
    @abstractmethod
    def create_version(self, ontology_id: str, version_number: str, 
                      parent_version_id: Optional[str] = None, 
                      change_summary: str = "") -> OntologyVersion:
        """创建版本
        
        Args:
            ontology_id: 本体ID
            version_number: 版本号
            parent_version_id: 父版本ID
            change_summary: 变更摘要
            
        Returns:
            本体版本
        """
        pass
    
    @abstractmethod
    def get_version(self, version_id: str) -> Optional[OntologyVersion]:
        """获取版本
        
        Args:
            version_id: 版本ID
            
        Returns:
            本体版本
        """
        pass
    
    @abstractmethod
    def list_versions(self, ontology_id: str, 
                     filters: Dict[str, Any] = None, 
                     page: int = 1, page_size: int = 10) -> List[OntologyVersion]:
        """列出版本
        
        Args:
            ontology_id: 本体ID
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            版本列表
        """
        pass
    
    @abstractmethod
    def rollback_version(self, ontology_id: str, target_version_id: str) -> OntologyVersion:
        """回滚版本
        
        Args:
            ontology_id: 本体ID
            target_version_id: 目标版本ID
            
        Returns:
            新版本
        """
        pass
    
    @abstractmethod
    def compare_versions(self, source_version_id: str, target_version_id: str) -> VersionComparison:
        """对比版本
        
        Args:
            source_version_id: 源版本ID
            target_version_id: 目标版本ID
            
        Returns:
            版本对比结果
        """
        pass
    
    @abstractmethod
    def merge_versions(self, ontology_id: str, source_version_id: str, 
                      target_version_id: str, conflict_resolution: Dict[str, Any] = None) -> OntologyVersion:
        """合并版本
        
        Args:
            ontology_id: 本体ID
            source_version_id: 源版本ID
            target_version_id: 目标版本ID
            conflict_resolution: 冲突解决策略
            
        Returns:
            合并后的版本
        """
        pass
    
    @abstractmethod
    def get_version_history(self, ontology_id: str) -> List[Dict[str, Any]]:
        """获取版本历史
        
        Args:
            ontology_id: 本体ID
            
        Returns:
            版本历史记录
        """
        pass
