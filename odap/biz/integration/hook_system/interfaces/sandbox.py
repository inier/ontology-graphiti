"""沙箱接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ..models.sandbox import SandboxConfig, SandboxResult


class ISandbox(ABC):
    """沙箱接口"""
    
    @abstractmethod
    def create_sandbox(self, config: SandboxConfig) -> SandboxConfig:
        """创建沙箱"""
        pass
    
    @abstractmethod
    def execute(self, sandbox_id: str, code: str, timeout_ms: int = 5000) -> SandboxResult:
        """在沙箱中执行代码"""
        pass
    
    @abstractmethod
    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """销毁沙箱"""
        pass
    
    @abstractmethod
    def get_sandbox_status(self, sandbox_id: str) -> Dict[str, Any]:
        """获取沙箱状态"""
        pass
