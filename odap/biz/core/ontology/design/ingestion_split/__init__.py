"""
数据采集层 - 统一导出
实现 ADR-031 L2: Data Ingestion & Normalization

从 ingestionsplit 子模块统一导出所有类，保持向后兼容
"""

from .news_ingester import NewsIngester
from .manual_input import ManualInputHandler
from .base_generator import BaseRandomGenerator
from .military_generator import RandomEventGenerator
from .business_generator import BusinessEventGenerator
from .tech_generator import TechEventGenerator
from .health_generator import HealthEventGenerator
from .generator_factory import RandomEventGeneratorFactory
from .document_io import OntologyDocumentIO
from .web_scraper import WebScraper
from .free_news_ingester import FreeNewsIngester

__all__ = [
    "NewsIngester",
    "ManualInputHandler",
    "BaseRandomGenerator",
    "RandomEventGenerator",
    "BusinessEventGenerator",
    "TechEventGenerator",
    "HealthEventGenerator",
    "RandomEventGeneratorFactory",
    "OntologyDocumentIO",
    "WebScraper",
    "FreeNewsIngester",
]
