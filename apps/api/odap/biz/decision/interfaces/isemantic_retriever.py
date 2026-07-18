"""ISemanticRetriever — 语义检索抽象接口

ADR-065: 舱壁先行。decision 通过此接口依赖 data 层的语义检索服务。
"""

from abc import ABC, abstractmethod
from typing import Any


class ISemanticRetriever(ABC):
    """语义检索抽象接口"""

    @abstractmethod
    async def retrieve(self, query_text: str, top_k: int = 10) -> Any:
        """检索相关实体和上下文

        Args:
            query_text: 查询文本
            top_k: 返回结果数

        Returns:
            SemanticRetrievalResult 对象，含 objects 和 answer_context 属性
        """
        ...
