"""
数据采集层 - 统一导出
实现 ADR-031 L2: Data Ingestion & Normalization

从 ingestionsplit 子模块统一导出所有类，保持向后兼容
"""

from odap.biz.ontology.ingestion_split.news_ingester import NewsIngester
from odap.biz.ontology.ingestion_split.manual_input import ManualInputHandler
from odap.biz.ontology.ingestion_split.base_generator import BaseRandomGenerator
from odap.biz.ontology.ingestion_split.military_generator import RandomEventGenerator
from odap.biz.ontology.ingestion_split.business_generator import BusinessEventGenerator
from odap.biz.ontology.ingestion_split.tech_generator import TechEventGenerator
from odap.biz.ontology.ingestion_split.health_generator import HealthEventGenerator
from odap.biz.ontology.ingestion_split.generator_factory import RandomEventGeneratorFactory
from odap.biz.ontology.ingestion_split.document_io import OntologyDocumentIO
from odap.biz.ontology.ingestion_split.web_scraper import WebScraper
from odap.biz.ontology.ingestion_split.free_news_ingester import FreeNewsIngester

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
