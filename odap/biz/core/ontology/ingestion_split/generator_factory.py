"""
数据采集层 - 随机事件生成器工厂
实现 ADR-031 L2: Data Ingestion & Normalization

RandomEventGeneratorFactory: 随机事件生成器工厂
"""

from odap.biz.core.ontology.ingestion_split.base_generator import BaseRandomGenerator
from odap.biz.core.ontology.ingestion_split.military_generator import RandomEventGenerator
from odap.biz.core.ontology.ingestion_split.business_generator import BusinessEventGenerator
from odap.biz.core.ontology.ingestion_split.tech_generator import TechEventGenerator
from odap.biz.core.ontology.ingestion_split.health_generator import HealthEventGenerator


class RandomEventGeneratorFactory:
    """随机事件生成器工厂"""

    _generators = {
        "military": RandomEventGenerator,
        "business": BusinessEventGenerator,
        "tech": TechEventGenerator,
        "healthcare": HealthEventGenerator,
    }

    _descriptions = {
        "military": "军事战争事件生成器 - 生成进攻、巡逻、增援、撤退等军事行动",
        "business": "商业事件生成器 - 生成投资、并购、产品发布等商业事件",
        "tech": "科技事件生成器 - 生成技术突破、产品发布等科技事件",
        "healthcare": "医疗健康事件生成器 - 生成新药研发、临床试验等医疗事件",
    }

    @classmethod
    def get_generator(cls, generator_type: str, llm_client=None) -> BaseRandomGenerator:
        """获取指定类型的生成器"""
        generator_class = cls._generators.get(generator_type)
        if not generator_class:
            raise ValueError(f"未知的生成器类型: {generator_type}")
        return generator_class(llm_client=llm_client)

    @classmethod
    def get_available_generators(cls) -> dict:
        """获取所有可用的生成器及其描述"""
        return {
            gen_type: {
                "class": gen_class,
                "description": cls._descriptions.get(gen_type, ""),
            }
            for gen_type, gen_class in cls._generators.items()
        }

    @classmethod
    def list_generator_types(cls) -> list:
        """列出所有可用的生成器类型"""
        return list(cls._generators.keys())
