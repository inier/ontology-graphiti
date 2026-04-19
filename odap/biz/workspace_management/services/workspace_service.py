"""工作空间服务"""

from typing import Dict, Any, List, Optional
from ..impl.workspace import WorkspaceManager
from ..impl.import_export import ImportExportManager
from ..models.workspace import Workspace, WorkspaceStatus, WorkspaceType, WorkspaceConfig
from ..models.import_export import ImportExportRecord, ImportExportStatus


class WorkspaceService:
    """工作空间服务"""
    
    def __init__(self):
        self.manager = WorkspaceManager()
        self.import_export = ImportExportManager()
    
    def create_workspace(self, name: str, description: str = "", 
                       workspace_type: WorkspaceType = WorkspaceType.DEFAULT, 
                       config: WorkspaceConfig = None, 
                       owner: str = "system") -> Dict[str, Any]:
        """创建工作空间
        
        Args:
            name: 工作空间名称
            description: 工作空间描述
            workspace_type: 工作空间类型
            config: 工作空间配置
            owner: 所有者
            
        Returns:
            工作空间信息
        """
        workspace = self.manager.create_workspace(
            name=name,
            description=description,
            workspace_type=workspace_type,
            config=config,
            owner=owner
        )
        
        return {
            "workspace_id": workspace.id,
            "name": workspace.name,
            "description": workspace.description,
            "type": workspace.type.value,
            "status": workspace.status.value,
            "owner": workspace.owner,
            "created_at": workspace.created_at.isoformat(),
            "updated_at": workspace.updated_at.isoformat()
        }
    
    def get_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """获取工作空间
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            工作空间信息
        """
        workspace = self.manager.get_workspace(workspace_id)
        if not workspace:
            return {"status": "error", "message": "Workspace not found"}
        
        return {
            "workspace_id": workspace.id,
            "name": workspace.name,
            "description": workspace.description,
            "type": workspace.type.value,
            "status": workspace.status.value,
            "config": workspace.config.model_dump(),
            "owner": workspace.owner,
            "members": workspace.members,
            "resources": workspace.resources,
            "created_at": workspace.created_at.isoformat(),
            "updated_at": workspace.updated_at.isoformat(),
            "last_accessed_at": workspace.last_accessed_at.isoformat() if workspace.last_accessed_at else None,
            "tags": workspace.tags
        }
    
    def update_workspace(self, workspace_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新工作空间
        
        Args:
            workspace_id: 工作空间ID
            updates: 更新内容
            
        Returns:
            更新后的工作空间信息
        """
        try:
            workspace = self.manager.update_workspace(workspace_id, updates)
            return {
                "workspace_id": workspace.id,
                "name": workspace.name,
                "description": workspace.description,
                "status": workspace.status.value,
                "updated_at": workspace.updated_at.isoformat()
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    
    def delete_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """删除工作空间
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            删除结果
        """
        success = self.manager.delete_workspace(workspace_id)
        return {
            "status": "success" if success else "error",
            "message": "Workspace deleted" if success else "Workspace not found"
        }
    
    def list_workspaces(self, filters: Dict[str, Any] = None, 
                       page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """列出工作空间
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            工作空间列表和分页信息
        """
        workspaces = self.manager.list_workspaces(filters, page, page_size)
        
        workspace_list = []
        for workspace in workspaces:
            workspace_list.append({
                "workspace_id": workspace.id,
                "name": workspace.name,
                "description": workspace.description,
                "type": workspace.type.value,
                "status": workspace.status.value,
                "owner": workspace.owner,
                "member_count": len(workspace.members),
                "created_at": workspace.created_at.isoformat()
            })
        
        return {
            "workspaces": workspace_list,
            "page": page,
            "page_size": page_size,
            "total": len(workspace_list)  # 实际项目中应该返回总记录数
        }
    
    def activate_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """激活工作空间
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            激活后的工作空间信息
        """
        try:
            workspace = self.manager.activate_workspace(workspace_id)
            return {
                "workspace_id": workspace.id,
                "status": workspace.status.value
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    
    def deactivate_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """停用工作空间
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            停用后的工作空间信息
        """
        try:
            workspace = self.manager.deactivate_workspace(workspace_id)
            return {
                "workspace_id": workspace.id,
                "status": workspace.status.value
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    
    def add_member(self, workspace_id: str, user_id: str) -> Dict[str, Any]:
        """添加成员
        
        Args:
            workspace_id: 工作空间ID
            user_id: 用户ID
            
        Returns:
            更新后的工作空间信息
        """
        try:
            workspace = self.manager.add_member(workspace_id, user_id)
            return {
                "workspace_id": workspace.id,
                "members": workspace.members
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    
    def remove_member(self, workspace_id: str, user_id: str) -> Dict[str, Any]:
        """移除成员
        
        Args:
            workspace_id: 工作空间ID
            user_id: 用户ID
            
        Returns:
            更新后的工作空间信息
        """
        try:
            workspace = self.manager.remove_member(workspace_id, user_id)
            return {
                "workspace_id": workspace.id,
                "members": workspace.members
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    
    def export_workspace(self, workspace_id: str, 
                        export_path: str = None, 
                        include_resources: bool = True, 
                        include_data: bool = False, 
                        created_by: str = "system") -> Dict[str, Any]:
        """导出工作空间
        
        Args:
            workspace_id: 工作空间ID
            export_path: 导出路径
            include_resources: 是否包含资源
            include_data: 是否包含数据
            created_by: 创建人
            
        Returns:
            导出记录信息
        """
        record = self.import_export.export_workspace(
            workspace_id=workspace_id,
            export_path=export_path,
            include_resources=include_resources,
            include_data=include_data,
            created_by=created_by
        )
        
        return {
            "record_id": record.id,
            "workspace_id": record.workspace_id,
            "operation": record.operation,
            "status": record.status.value,
            "progress": record.progress,
            "start_time": record.start_time.isoformat()
        }
    
    def import_workspace(self, import_path: str, 
                        workspace_name: str = None, 
                        overwrite: bool = False, 
                        created_by: str = "system") -> Dict[str, Any]:
        """导入工作空间
        
        Args:
            import_path: 导入路径
            workspace_name: 工作空间名称
            overwrite: 是否覆盖
            created_by: 创建人
            
        Returns:
            导入记录信息
        """
        record = self.import_export.import_workspace(
            import_path=import_path,
            workspace_name=workspace_name,
            overwrite=overwrite,
            created_by=created_by
        )
        
        return {
            "record_id": record.id,
            "workspace_id": record.workspace_id,
            "operation": record.operation,
            "status": record.status.value,
            "progress": record.progress,
            "start_time": record.start_time.isoformat()
        }
