"""审计日志系统接口"""

from .logger import IAuditLogger
from .channel import IChannelManager
from .storage import ILogStorage
from .validation import ILogValidator
from .chain import IBlockChainManager

__all__ = [
    "IAuditLogger",
    "IChannelManager",
    "ILogStorage",
    "ILogValidator",
    "IBlockChainManager"
]
