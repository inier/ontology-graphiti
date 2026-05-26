"""Hook系统接口"""

from .hook_manager import IHookManager
from .sandbox import ISandbox

__all__ = [
    "IHookManager",
    "ISandbox"
]
