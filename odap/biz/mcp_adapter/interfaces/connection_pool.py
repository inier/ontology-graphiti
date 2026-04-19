"""连接池接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class IConnectionPool(ABC):
    """连接池接口"""
    
    @abstractmethod
    def acquire(self, server_id: str) -> Optional[str]:
        """获取连接"""
        pass
    
    @abstractmethod
    def release(self, connection_id: str) -> bool:
        """释放连接"""
        pass
    
    @abstractmethod
    def get_pool_status(self, server_id: str) -> Dict[str, Any]:
        """获取连接池状态"""
        pass
