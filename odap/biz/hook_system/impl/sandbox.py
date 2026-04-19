"""沙箱实现"""

from typing import Dict, Any, Optional
from datetime import datetime
from ..interfaces.sandbox import ISandbox
from ..models.sandbox import SandboxConfig, SandboxResult


class Sandbox(ISandbox):
    """沙箱实现"""
    
    def __init__(self):
        self._sandboxes: Dict[str, SandboxConfig] = {}
        self._results: Dict[str, SandboxResult] = {}
    
    def create_sandbox(self, config: SandboxConfig) -> SandboxConfig:
        """创建沙箱"""
        self._sandboxes[config.id] = config
        return config
    
    def execute(self, sandbox_id: str, code: str, timeout_ms: int = 5000) -> SandboxResult:
        """在沙箱中执行代码"""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            raise ValueError("Sandbox not found")
        
        result = SandboxResult(sandbox_config_id=sandbox_id)
        
        try:
            # 模拟执行
            start_time = datetime.now()
            result.status = "success"
            result.output = "Code executed in sandbox"
            result.execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        except Exception as e:
            result.status = "error"
            result.error = str(e)
        
        self._results[result.id] = result
        return result
    
    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """销毁沙箱"""
        if sandbox_id in self._sandboxes:
            del self._sandboxes[sandbox_id]
            return True
        return False
    
    def get_sandbox_status(self, sandbox_id: str) -> Dict[str, Any]:
        """获取沙箱状态"""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            return {"status": "not_found"}
        
        return {
            "sandbox_id": sandbox.id,
            "name": sandbox.name,
            "max_memory_mb": sandbox.max_memory_mb,
            "max_cpu_percent": sandbox.max_cpu_percent,
            "network_enabled": sandbox.network_enabled,
            "filesystem_enabled": sandbox.filesystem_enabled
        }
