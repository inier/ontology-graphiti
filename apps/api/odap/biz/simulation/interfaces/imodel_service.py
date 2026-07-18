"""IModelService — 本体模型服务抽象接口

ADR-065: 舱壁先行。simulation 通过此接口依赖 core 层的模型服务。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class IModelService(ABC):
    """本体模型查询抽象接口"""

    @abstractmethod
    def list_entity_types(self, filters: Dict[str, Any] = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """列出实体类型定义"""
        ...
