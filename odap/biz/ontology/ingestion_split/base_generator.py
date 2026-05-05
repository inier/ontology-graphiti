"""
数据采集层 - 基础随机生成器抽象类
实现 ADR-031 L2: Data Ingestion & Normalization

BaseRandomGenerator: 随机事件生成器抽象基类
"""

import abc
from typing import Dict, List, Optional

from odap.biz.ontology.schema.document import OntologyDocument


class BaseRandomGenerator(abc.ABC):
    """随机事件生成器抽象基类"""

    @abc.abstractmethod
    async def generate(
        self,
        parties: List[str] = None,
        scenario_context: dict = None,
        count: int = 1,
        scenario_id: str = None,
    ) -> List[OntologyDocument]:
        """
        生成随机事件

        Args:
            parties: 参与方列表（可选，军事类使用）
            scenario_context: 场景上下文
            count: 生成数量
            scenario_id: 场景ID

        Returns:
            List[OntologyDocument]: 生成的事件文档列表
        """
        pass

    @abc.abstractmethod
    def get_generator_name(self) -> str:
        """获取生成器名称"""
        pass

    @abc.abstractmethod
    def get_generator_description(self) -> str:
        """获取生成器描述"""
        pass
