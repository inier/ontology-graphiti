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

    def set_enabled(self, hook_id: str, enabled: bool) -> Hook:
        """启用/禁用 Hook（P0-C4 整改：原 enable/disable 端点为 no-op）。

        Args:
            hook_id: Hook ID
            enabled: True → ACTIVE，False → INACTIVE

        Raises:
            ValueError: Hook 不存在
        """
        raise NotImplementedError

    def list_hooks(self, filters: Dict[str, Any] = None,
                  page: int = 1, page_size: int = 10) -> List[Hook]:
        """列出Hooks"""
        raise NotImplementedError

    def count_hooks(self, filters: Dict[str, Any] = None) -> int:
        """统计符合 filters 条件的 Hook 总数（P0-M3 整改：用于分页 total）。

        Args:
            filters: 同 list_hooks 的 filters，必须保持一致的过滤逻辑

        Returns:
            符合条件的 Hook 总数（不分页）
        """
        raise NotImplementedError

    def execute_hook(self, hook_id: str, context: Dict[str, Any] = None) -> HookExecution:
        """执行Hook"""
        raise NotImplementedError

    def get_hook_executions(self, hook_id: str,
                           limit: int = 10) -> List[HookExecution]:
        """获取Hook执行记录"""
        raise NotImplementedError
