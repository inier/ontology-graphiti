"""Hook管理器实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.hook_manager import IHookManager
from ..models.hook import Hook, HookType, HookStatus, HookExecution


class HookManager(IHookManager):
    """Hook管理器实现"""
    
    def __init__(self):
        self._hooks: Dict[str, Hook] = {}
        self._executions: Dict[str, List[HookExecution]] = {}
    
    def register_hook(self, name: str, hook_type: HookType, script: str, 
                    description: str = "", language: str = "python") -> Hook:
        """注册Hook"""
        hook = Hook(
            name=name,
            hook_type=hook_type,
            script=script,
            description=description,
            language=language
        )
        self._hooks[hook.id] = hook
        self._executions[hook.id] = []
        return hook
    
    def get_hook(self, hook_id: str) -> Optional[Hook]:
        """获取Hook"""
        return self._hooks.get(hook_id)
    
    def update_hook(self, hook_id: str, updates: Dict[str, Any]) -> Hook:
        """更新Hook"""
        hook = self._hooks.get(hook_id)
        if not hook:
            raise ValueError("Hook not found")
        
        for key, value in updates.items():
            if hasattr(hook, key):
                setattr(hook, key, value)
        
        hook.updated_at = datetime.now()
        return hook
    
    def delete_hook(self, hook_id: str) -> bool:
        """删除Hook"""
        if hook_id in self._hooks:
            del self._hooks[hook_id]
            return True
        return False
    
    def list_hooks(self, filters: Dict[str, Any] = None, 
                  page: int = 1, page_size: int = 10) -> List[Hook]:
        """列出Hooks"""
        filters = filters or {}
        hooks = list(self._hooks.values())
        
        if "type" in filters:
            hooks = [h for h in hooks if h.hook_type.value == filters["type"]]
        if "status" in filters:
            hooks = [h for h in hooks if h.status.value == filters["status"]]
        
        start = (page - 1) * page_size
        end = start + page_size
        return hooks[start:end]
    
    def execute_hook(self, hook_id: str, context: Dict[str, Any] = None) -> HookExecution:
        """执行Hook"""
        hook = self._hooks.get(hook_id)
        if not hook:
            raise ValueError("Hook not found")
        
        execution = HookExecution(hook_id=hook_id)
        
        try:
            # 模拟执行
            start_time = datetime.now()
            execution.status = "success"
            execution.result = {"output": "Hook executed"}
            execution.duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        except Exception as e:
            execution.status = "error"
            execution.error = str(e)
        
        # 保存执行记录
        if hook_id in self._executions:
            self._executions[hook_id].append(execution)
        
        return execution
    
    def get_hook_executions(self, hook_id: str, limit: int = 10) -> List[HookExecution]:
        """获取Hook执行记录"""
        executions = self._executions.get(hook_id, [])
        return executions[-limit:]
