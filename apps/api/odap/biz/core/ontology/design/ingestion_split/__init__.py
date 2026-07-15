"""
数据采集层 - 统一导出
实现 ADR-031 L2: Data Ingestion & Normalization

从 ingestion_split 子模块统一导出所有类，保持向后兼容
"""

from .news_ingester import NewsIngester
from .manual_input import ManualInputHandler
from .base_generator import BaseRandomGenerator
from .conflict_generator import ConflictEventGenerator
from .business_generator import BusinessEventGenerator
from .tech_generator import TechEventGenerator
from .health_generator import HealthEventGenerator
from .generator_factory import RandomEventGeneratorFactory
from .document_io import OntologyDocumentIO
from .web_scraper import WebScraper
from .free_news_ingester import FreeNewsIngester
from .db_schema_ingester import DatabaseSchemaExtractor

__all__ = [
    "NewsIngester",
    "ManualInputHandler",
    "BaseRandomGenerator",
    "ConflictEventGenerator",
    "BusinessEventGenerator",
    "TechEventGenerator",
    "HealthEventGenerator",
    "RandomEventGeneratorFactory",
    "OntologyDocumentIO",
    "WebScraper",
    "FreeNewsIngester",
    "DatabaseSchemaExtractor",
]


def __getattr__(name):
    """延迟导入 + 向后兼容别名"""
    if name == "RandomEventGenerator":
        from .conflict_generator import ConflictEventGenerator
        return ConflictEventGenerator
    # Backward compatibility: ConflictEventGeneratorFactory → RandomEventGeneratorFactory
    if name == "ConflictEventGeneratorFactory":
        from .generator_factory import RandomEventGeneratorFactory
        return RandomEventGeneratorFactory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
