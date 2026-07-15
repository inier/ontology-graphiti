"""Hook管理器接口"""

from typing import Dict, Any, List, Optional
from ..models.hook import Hook, HookType, HookStatus, HookExecution


class IHookManager:
    """Hook管理器接口"""

    def register_hook(self, name: str, hook_type: HookType, script: str,
                    description: str = "", language: str = "python") -> Hook:
        """注册Hook"""
        raise NotImplementedError

    def get_hook(self, hook_id: str) -> Optional[Hook]:
        """获取Hook"""
        raise NotImplementedError

    def update_hook(self, hook_id: str, updates: Dict[str, Any]) -> Hook:
        """更新Hook"""
        raise NotImplementedError

    def delete_hook(self, hook_id: str) -> bool:
        """删除Hook"""
        raise NotImplementedError

    def list_hooks(self, filters: Dict[str, Any] = None,
                  page: int = 1, page_size: int = 10) -> List[Hook]:
        """列出Hooks"""
        raise NotImplementedError

    def execute_hook(self, hook_id: str, context: Dict[str, Any] = None) -> HookExecution:
        """执行Hook"""
        raise NotImplementedError

    def get_hook_executions(self, hook_id: str,
                           limit: int = 10) -> List[HookExecution]:
        """获取Hook执行记录"""
        raise NotImplementedError
