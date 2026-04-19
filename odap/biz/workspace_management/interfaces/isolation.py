"""隔离管理接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.isolation import IsolationLevel, ResourceQuota, NetworkPolicy


class IIsolationManager(ABC):
    """隔离管理接口"""
    
    @abstractmethod
    def create_isolation_policy(self, workspace_id: str, 
                              isolation_level: IsolationLevel = IsolationLevel.STANDARD, 
                              resource_quota: ResourceQuota = None, 
                              network_policy: NetworkPolicy = None) -> Dict[str, Any]:
        """创建隔离策略
        
        Args:
            workspace_id: 工作空间ID
            isolation_level: 隔离级别
            resource_quota: 资源配额
            network_policy: 网络策略
            
        Returns:
            隔离策略信息
        """
        pass
    
    @abstractmethod
    def get_isolation_policy(self, workspace_id: str) -> Dict[str, Any]:
        """获取隔离策略
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            隔离策略信息
        """
        pass
    
    @abstractmethod
    def update_isolation_policy(self, workspace_id: str, 
                              updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新隔离策略
        
        Args:
            workspace_id: 工作空间ID
            updates: 更新内容
            
        Returns:
            更新后的隔离策略
        """
        pass
    
    @abstractmethod
    def enforce_isolation(self, workspace_id: str) -> bool:
        """执行隔离
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            是否执行成功
        """
        pass
    
    @abstractmethod
    def validate_isolation(self, workspace_id: str) -> Dict[str, Any]:
        """验证隔离
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            验证结果
        """
        pass
    
    @abstractmethod
    def get_resource_usage(self, workspace_id: str) -> Dict[str, Any]:
        """获取资源使用情况
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            资源使用情况
        """
        pass
    
    @abstractmethod
    def check_quota_violation(self, workspace_id: str) -> List[Dict[str, Any]]:
        """检查配额违规
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            违规列表
        """
        pass
