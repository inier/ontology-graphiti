"""Hook服务"""

from typing import Dict, Any, List
from ..impl.hook_manager import HookManager
from ..impl.sandbox import Sandbox
from ..models.hook import HookType


class HookService:
    """Hook服务"""
    
    def __init__(self):
        self.manager = HookManager()
        self.sandbox = Sandbox()
    
    def register_hook(self, name: str, hook_type: HookType, script: str, 
                    description: str = "", language: str = "python") -> Dict[str, Any]:
        """注册Hook"""
        hook = self.manager.register_hook(name, hook_type, script, description, language)
        
        return {
            "hook_id": hook.id,
            "name": hook.name,
            "hook_type": hook.hook_type.value,
            "status": hook.status.value,
            "created_at": hook.created_at.isoformat()
        }
    
    def get_hook(self, hook_id: str) -> Dict[str, Any]:
        """获取Hook"""
        hook = self.manager.get_hook(hook_id)
        if not hook:
            return {"status": "error", "message": "Hook not found"}
        
        return {
            "hook_id": hook.id,
            "name": hook.name,
            "description": hook.description,
            "hook_type": hook.hook_type.value,
            "status": hook.status.value,
            "script": hook.script,
            "language": hook.language,
            "timeout_ms": hook.timeout_ms,
            "created_at": hook.created_at.isoformat()
        }
    
    def execute_hook(self, hook_id: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行Hook"""
        try:
            execution = self.manager.execute_hook(hook_id, context)
            return {
                "execution_id": execution.id,
                "hook_id": execution.hook_id,
                "status": execution.status,
                "duration_ms": execution.duration_ms,
                "result": execution.result,
                "error": execution.error
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def set_enabled(self, hook_id: str, enabled: bool) -> Dict[str, Any]:
        """启用/禁用 Hook（P0-C4 整改）。

        原 enable/disable 端点是 no-op；本方法真正调用 manager.set_enabled 切换状态。
        """
        try:
            hook = self.manager.set_enabled(hook_id, enabled)
            return {
                "status": "success",
                "hook_id": hook.id,
                "enabled": enabled,
                "hook_status": hook.status.value,
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def list_hooks(self, filters: Dict[str, Any] = None,
                  page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """列出Hooks（P0-M3 整改：total 返回真实总数而非当前页长度）。"""
        hooks = self.manager.list_hooks(filters, page, page_size)
        # P0-M3 fix: 用 count_hooks 取真实总数，而非 len(当前页)
        total = self.manager.count_hooks(filters)

        hook_list = []
        for hook in hooks:
            hook_list.append({
                "hook_id": hook.id,
                "name": hook.name,
                "hook_type": hook.hook_type.value,
                "status": hook.status.value
            })

        return {
            "hooks": hook_list,
            "page": page,
            "page_size": page_size,
            "total": total
        }
