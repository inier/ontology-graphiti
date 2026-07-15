"""ISaConfigStorage ABC：sa_config 的存储契约。"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from odap.biz.semantic_admin.sa_config.models import SaConfigEntry


class ISaConfigStorage(ABC):
    @abstractmethod
    def save_config(self, entry: SaConfigEntry) -> SaConfigEntry:
        ...

    @abstractmethod
    def get_config(
        self, scope: str, config_key: str
    ) -> Optional[SaConfigEntry]:
        ...

    @abstractmethod
    def get_value(
        self, scope: str, config_key: str
    ) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_configs(
        self, scope: Optional[str] = None
    ) -> List[SaConfigEntry]:
        ...

    @abstractmethod
    def delete_config(self, scope: str, config_key: str) -> bool:
        ...


__all__ = ["ISaConfigStorage"]
