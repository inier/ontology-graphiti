"""工作空间管理接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.workspace import Workspace, WorkspaceStatus, WorkspaceType, WorkspaceConfig


class IWorkspaceManager(ABC):
    """工作空间管理接口"""
    
    @abstractmethod
    def create_workspace(self, name: str, description: str = "", 
                       workspace_type: WorkspaceType = WorkspaceType.DEFAULT, 
                       config: WorkspaceConfig = None, 
                       owner: str = "system") -> Workspace:
        """创建工作空间
        
        Args:
            name: 工作空间名称
            description: 工作空间描述
            workspace_type: 工作空间类型
            config: 工作空间配置
            owner: 所有者
            
        Returns:
            创建的工作空间
        """
        pass
    
    @abstractmethod
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """获取工作空间
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            工作空间对象
        """
        pass
    
    @abstractmethod
    def update_workspace(self, workspace_id: str, updates: Dict[str, Any]) -> Workspace:
        """更新工作空间
        
        Args:
            workspace_id: 工作空间ID
            updates: 更新内容
            
        Returns:
            更新后的工作空间
        """
        pass
    
    @abstractmethod
    def delete_workspace(self, workspace_id: str) -> bool:
        """删除工作空间
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            是否删除成功
        """
        pass
    
    @abstractmethod
    def list_workspaces(self, filters: Dict[str, Any] = None, 
                       page: int = 1, page_size: int = 10) -> List[Workspace]:
        """列出工作空间
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            工作空间列表
        """
        pass
    
    @abstractmethod
    def activate_workspace(self, workspace_id: str) -> Workspace:
        """激活工作空间
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            激活后的工作空间
        """
        pass
    
    @abstractmethod
    def deactivate_workspace(self, workspace_id: str) -> Workspace:
        """停用工作空间
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            停用后的工作空间
        """
        pass
    
    @abstractmethod
    def add_member(self, workspace_id: str, user_id: str) -> Workspace:
        """添加成员
        
        Args:
            workspace_id: 工作空间ID
            user_id: 用户ID
            
        Returns:
            更新后的工作空间
        """
        pass
    
    @abstractmethod
    def remove_member(self, workspace_id: str, user_id: str) -> Workspace:
        """移除成员
        
        Args:
            workspace_id: 工作空间ID
            user_id: 用户ID
            
        Returns:
            更新后的工作空间
        """
        pass
