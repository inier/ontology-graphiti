"""隔离服务"""

from typing import Dict, Any, List, Optional
from ..impl.isolation import IsolationManager
from ..models.isolation import IsolationLevel, ResourceQuota, NetworkPolicy


class IsolationService:
    """隔离服务"""
    
    def __init__(self):
        self.manager = IsolationManager()
    
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
        policy = self.manager.create_isolation_policy(
            workspace_id=workspace_id,
            isolation_level=isolation_level,
            resource_quota=resource_quota,
            network_policy=network_policy
        )
        
        return policy
    
    def get_isolation_policy(self, workspace_id: str) -> Dict[str, Any]:
        """获取隔离策略
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            隔离策略信息
        """
        policy = self.manager.get_isolation_policy(workspace_id)
        if not policy:
            return {"status": "error", "message": "Isolation policy not found"}
        
        return policy
    
    def update_isolation_policy(self, workspace_id: str, 
                              updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新隔离策略
        
        Args:
            workspace_id: 工作空间ID
            updates: 更新内容
            
        Returns:
            更新后的隔离策略
        """
        try:
            policy = self.manager.update_isolation_policy(workspace_id, updates)
            return policy
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    
    def enforce_isolation(self, workspace_id: str) -> Dict[str, Any]:
        """执行隔离
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            执行结果
        """
        success = self.manager.enforce_isolation(workspace_id)
        return {
            "status": "success" if success else "error",
            "message": "Isolation enforced" if success else "Failed to enforce isolation"
        }
    
    def validate_isolation(self, workspace_id: str) -> Dict[str, Any]:
        """验证隔离
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            验证结果
        """
        return self.manager.validate_isolation(workspace_id)
    
    def get_resource_usage(self, workspace_id: str) -> Dict[str, Any]:
        """获取资源使用情况
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            资源使用情况
        """
        return self.manager.get_resource_usage(workspace_id)
    
    def check_quota_violation(self, workspace_id: str) -> Dict[str, Any]:
        """检查配额违规
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            违规检查结果
        """
        violations = self.manager.check_quota_violation(workspace_id)
        return {
            "workspace_id": workspace_id,
            "violations": violations,
            "violation_count": len(violations)
        }
