"""配置存储抽象接口"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class ConfigRepository(ABC):
    """配置存储抽象基类"""

    @abstractmethod
    def save_config(self, key: str, value: str, updated_by: str = "") -> None:
        """保存单个配置项"""

    @abstractmethod
    def get_config(self, key: str) -> Optional[str]:
        """获取单个配置项的值（解密后）"""

    @abstractmethod
    def get_raw_config(self, key: str) -> Optional[str]:
        """获取单个配置项的原始值（可能加密）"""

    @abstractmethod
    def list_configs(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出配置项，可按类别筛选"""

    @abstractmethod
    def delete_config(self, key: str) -> bool:
        """删除配置项，返回是否成功"""

    @abstractmethod
    def save_revision(self, revision: Dict[str, Any]) -> None:
        """保存变更记录"""

    @abstractmethod
    def list_revisions(self, category: Optional[str] = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """查询变更历史，返回 {revisions: [...], total: int}"""

    @abstractmethod
    def get_revision(self, revision_number: int) -> Optional[Dict[str, Any]]:
        """获取指定修订号的变更记录"""

    @abstractmethod
    def get_next_revision_number(self) -> int:
        """获取下一个修订号"""

    @abstractmethod
    def register_schema(self, item: Dict[str, Any]) -> None:
        """注册配置项 schema"""

    @abstractmethod
    def list_schemas(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出已注册的配置项 schema"""

    @abstractmethod
    def get_schema(self, key: str) -> Optional[Dict[str, Any]]:
        """获取单个配置项的 schema"""

    @abstractmethod
    def load_all_to_dict(self) -> Dict[str, str]:
        """加载所有配置项为 {key: decrypted_value} 字典"""
