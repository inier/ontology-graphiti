"""工作空间管理实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.workspace import IWorkspaceManager
from ..models.workspace import Workspace, WorkspaceStatus, WorkspaceType, WorkspaceConfig
from ..storage.mongodb_storage import MongoDBStorage


class WorkspaceManager(IWorkspaceManager):
    """工作空间管理实现"""
    
    def __init__(self):
        self.storage = MongoDBStorage()
    
    def create_workspace(self, name: str, description: str = "", 
                       workspace_type: WorkspaceType = WorkspaceType.DEFAULT, 
                       config: WorkspaceConfig = None, 
                       owner: str = "system") -> Workspace:
        """创建工作空间"""
        workspace = Workspace(
            name=name,
            description=description,
            type=workspace_type,
            config=config or WorkspaceConfig(),
            owner=owner
        )
        
        # 保存到存储
        self.storage.save_workspace(workspace)
        
        # 模拟创建过程
        workspace.status = WorkspaceStatus.ACTIVE
        self.storage.update_workspace(workspace)
        
        return workspace
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """获取工作空间"""
        return self.storage.get_workspace(workspace_id)
    
    def update_workspace(self, workspace_id: str, updates: Dict[str, Any]) -> Workspace:
        """更新工作空间"""
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")
        
        # 更新字段
        for key, value in updates.items():
            if hasattr(workspace, key):
                setattr(workspace, key, value)
        
        workspace.updated_at = datetime.now()
        self.storage.update_workspace(workspace)
        
        return workspace
    
    def delete_workspace(self, workspace_id: str) -> bool:
        """删除工作空间"""
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            return False
        
        # 标记为删除中
        workspace.status = WorkspaceStatus.DELETING
        self.storage.update_workspace(workspace)
        
        # 执行删除操作
        # 实际项目中可能需要清理资源
        
        # 从存储中删除
        self.storage.delete_workspace(workspace_id)
        
        return True
    
    def list_workspaces(self, filters: Dict[str, Any] = None, 
                       page: int = 1, page_size: int = 10) -> List[Workspace]:
        """列出工作空间"""
        return self.storage.list_workspaces(filters, page, page_size)
    
    def activate_workspace(self, workspace_id: str) -> Workspace:
        """激活工作空间"""
        return self.update_workspace(workspace_id, {"status": WorkspaceStatus.ACTIVE})
    
    def deactivate_workspace(self, workspace_id: str) -> Workspace:
        """停用工作空间"""
        return self.update_workspace(workspace_id, {"status": WorkspaceStatus.INACTIVE})
    
    def add_member(self, workspace_id: str, user_id: str) -> Workspace:
        """添加成员"""
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")
        
        if user_id not in workspace.members:
            workspace.members.append(user_id)
            workspace.updated_at = datetime.now()
            self.storage.update_workspace(workspace)
        
        return workspace
    
    def remove_member(self, workspace_id: str, user_id: str) -> Workspace:
        """移除成员"""
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")
        
        if user_id in workspace.members:
            workspace.members.remove(user_id)
            workspace.updated_at = datetime.now()
            self.storage.update_workspace(workspace)
        
        return workspace
