"""沙箱接口"""

from typing import Dict, Any, Optional
from ..models.sandbox import SandboxConfig, SandboxResult


class ISandbox:
    """沙箱接口"""

    def create_sandbox(self, config: SandboxConfig) -> SandboxConfig:
        """创建沙箱"""
        raise NotImplementedError

    def execute(self, sandbox_id: str, code: str, timeout_ms: int = 5000) -> SandboxResult:
        """在沙箱中执行代码"""
        raise NotImplementedError

    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """销毁沙箱"""
        raise NotImplementedError

    def get_sandbox_status(self, sandbox_id: str) -> Dict[str, Any]:
        """获取沙箱状态"""
        raise NotImplementedError
