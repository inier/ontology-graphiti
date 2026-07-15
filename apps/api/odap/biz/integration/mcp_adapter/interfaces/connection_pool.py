"""连接池接口"""

from typing import Dict, Any, Optional


class IConnectionPool:
    """连接池接口"""

    def acquire(self, server_id: str) -> Optional[str]:
        """获取连接"""
        raise NotImplementedError

    def release(self, connection_id: str) -> bool:
        """释放连接"""
        raise NotImplementedError

    def get_pool_status(self, server_id: str) -> Dict[str, Any]:
        """获取连接池状态"""
        raise NotImplementedError
