"""工作空间管理实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.workspace import IWorkspaceManager
from ..models.workspace import Workspace, WorkspaceStatus, WorkspaceType, WorkspaceConfig
from ..storage import Storage


class WorkspaceManager(IWorkspaceManager):
    """工作空间管理实现"""
    
    def __init__(self):
        self.storage = Storage()
    
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

    def bind_ontology(self, workspace_id: str, ontology_id: str) -> Workspace:
        """绑定本体到工作空间（支持共享绑定）"""
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")

        if ontology_id not in workspace.bound_ontology_ids:
            workspace.bound_ontology_ids.append(ontology_id)
            workspace.updated_at = datetime.now()
            self.storage.update_workspace(workspace)

        return workspace

    def unbind_ontology(self, workspace_id: str, ontology_id: str) -> Workspace:
        """解绑本体"""
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")

        if ontology_id in workspace.bound_ontology_ids:
            workspace.bound_ontology_ids.remove(ontology_id)
            workspace.updated_at = datetime.now()
            self.storage.update_workspace(workspace)

        return workspace

    def get_bound_ontologies(self, workspace_id: str) -> List[Dict[str, Any]]:
        """获取工作空间绑定的所有本体（含共享本体信息）"""
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")

        result = []
        for ontology_id in workspace.bound_ontology_ids:
            ontology_info = {"ontology_id": ontology_id, "source": "private"}
            try:
                from odap.biz.core.ontology.version_manager import OntologyVersionManager
                vm = OntologyVersionManager.get_instance()
                versions = vm.list_versions(ontology_id)
                if versions:
                    ontology_info["latest_version"] = versions[0].get("version_id", "unknown")
                    ontology_info["name"] = versions[0].get("name", ontology_id)
            except Exception:
                pass

            other_workspaces = self._find_workspaces_sharing_ontology(ontology_id, exclude_workspace_id=workspace_id)
            if other_workspaces:
                ontology_info["source"] = "shared"
                ontology_info["shared_with"] = [w.name for w in other_workspaces]

            result.append(ontology_info)

        return result

    def _find_workspaces_sharing_ontology(self, ontology_id: str, exclude_workspace_id: str = None) -> List[Workspace]:
        """查找共享同一本体的其他工作空间"""
        all_workspaces = self.storage.list_workspaces()
        shared = []
        for ws in all_workspaces:
            if ws.id == exclude_workspace_id:
                continue
            if hasattr(ws, 'bound_ontology_ids') and ontology_id in ws.bound_ontology_ids:
                shared.append(ws)
        return shared