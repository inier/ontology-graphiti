"""导入导出管理接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.import_export import ImportExportRecord, ImportExportStatus


class IImportExportManager(ABC):
    """导入导出管理接口"""
    
    @abstractmethod
    def export_workspace(self, workspace_id: str, 
                        export_path: str = None, 
                        include_resources: bool = True, 
                        include_data: bool = False, 
                        created_by: str = "system") -> ImportExportRecord:
        """导出工作空间
        
        Args:
            workspace_id: 工作空间ID
            export_path: 导出路径
            include_resources: 是否包含资源
            include_data: 是否包含数据
            created_by: 创建人
            
        Returns:
            导出记录
        """
        pass
    
    @abstractmethod
    def import_workspace(self, import_path: str, 
                        workspace_name: str = None, 
                        overwrite: bool = False, 
                        created_by: str = "system") -> ImportExportRecord:
        """导入工作空间
        
        Args:
            import_path: 导入路径
            workspace_name: 工作空间名称
            overwrite: 是否覆盖
            created_by: 创建人
            
        Returns:
            导入记录
        """
        pass
    
    @abstractmethod
    def get_import_export_record(self, record_id: str) -> Optional[ImportExportRecord]:
        """获取导入导出记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            导入导出记录
        """
        pass
    
    @abstractmethod
    def list_import_export_records(self, workspace_id: str = None, 
                                  operation: str = None, 
                                  status: ImportExportStatus = None, 
                                  page: int = 1, page_size: int = 10) -> List[ImportExportRecord]:
        """列出导入导出记录
        
        Args:
            workspace_id: 工作空间ID
            operation: 操作类型
            status: 状态
            page: 页码
            page_size: 每页数量
            
        Returns:
            导入导出记录列表
        """
        pass
    
    @abstractmethod
    def cancel_import_export(self, record_id: str) -> bool:
        """取消导入导出
        
        Args:
            record_id: 记录ID
            
        Returns:
            是否取消成功
        """
        pass
    
    @abstractmethod
    def get_import_export_progress(self, record_id: str) -> Dict[str, Any]:
        """获取导入导出进度
        
        Args:
            record_id: 记录ID
            
        Returns:
            进度信息
        """
        pass
    
    @abstractmethod
    def validate_import_file(self, import_path: str) -> Dict[str, Any]:
        """验证导入文件
        
        Args:
            import_path: 导入文件路径
            
        Returns:
            验证结果
        """
        pass
