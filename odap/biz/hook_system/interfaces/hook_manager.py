"""Hook管理器接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.hook import Hook, HookType, HookStatus, HookExecution


class IHookManager(ABC):
    """Hook管理器接口"""
    
    @abstractmethod
    def register_hook(self, name: str, hook_type: HookType, script: str, 
                    description: str = "", language: str = "python") -> Hook:
        """注册Hook"""
        pass
    
    @abstractmethod
    def get_hook(self, hook_id: str) -> Optional[Hook]:
        """获取Hook"""
        pass
    
    @abstractmethod
    def update_hook(self, hook_id: str, updates: Dict[str, Any]) -> Hook:
        """更新Hook"""
        pass
    
    @abstractmethod
    def delete_hook(self, hook_id: str) -> bool:
        """删除Hook"""
        pass
    
    @abstractmethod
    def list_hooks(self, filters: Dict[str, Any] = None, 
                  page: int = 1, page_size: int = 10) -> List[Hook]:
        """列出Hooks"""
        pass
    
    @abstractmethod
    def execute_hook(self, hook_id: str, context: Dict[str, Any] = None) -> HookExecution:
        """执行Hook"""
        pass
    
    @abstractmethod
    def get_hook_executions(self, hook_id: str, 
                           limit: int = 10) -> List[HookExecution]:
        """获取Hook执行记录"""
        pass
