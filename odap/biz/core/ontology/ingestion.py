"""
数据采集层 - 数据摄取与归纳模块
实现 ADR-031 L2: Data Ingestion & Normalization

组件:
- NewsIngester: 联网检索 → LLM 归纳 → OntologyDocument
- ManualInputHandler: 表单/JSON/自然语言 → OntologyDocument
- RandomEventGenerator: 涉事方行为模型 → OntologyDocument（参考 NetLogo）
- OntologyDocumentIO: 导入/导出 .odoc.json
- WebScraper: 网页内容抓取（免费方案，无需 API Key）

此文件为向后兼容层，实际功能已拆分到 ingestion_split 子模块。
如需使用单个组件，请直接从 ingestion_split 导入。
"""

# 导出所有组件和类型（向后兼容）
from odap.biz.core.ontology.ingestion_split import (
    NewsIngester,
    ManualInputHandler,
    BaseRandomGenerator,
    RandomEventGenerator,
    BusinessEventGenerator,
    TechEventGenerator,
    HealthEventGenerator,
    RandomEventGeneratorFactory,
    OntologyDocumentIO,
    WebScraper,
    FreeNewsIngester,
)

# 导出数据类型（向后兼容）
from odap.biz.core.ontology.schema.document import (
    OntologyDocument,
    OntologyEntity,
    OntologyRelation,
    OntologyEvent,
    OntologyAction,
    OntologyRule,
    OntologyConstraint,
    VersionRef,
    DataSource,
    DocumentMeta,
    TemporalInfo,
    SourceType,
    DocType,
    EntityType,
    ActionStatus,
    OntologyDocumentSchema,
    make_battle_event_document,
)

__all__ = [
    # 主组件
    "NewsIngester",
    "ManualInputHandler",
    "OntologyDocumentIO",
    "WebScraper",
    "FreeNewsIngester",
    # 生成器
    "BaseRandomGenerator",
    "RandomEventGenerator",
    "BusinessEventGenerator",
    "TechEventGenerator",
    "HealthEventGenerator",
    "RandomEventGeneratorFactory",
    # 类型（向后兼容）
    "OntologyDocument",
    "OntologyEntity",
    "OntologyRelation",
    "OntologyEvent",
    "OntologyAction",
    "OntologyRule",
    "OntologyConstraint",
    "VersionRef",
    "DataSource",
    "DocumentMeta",
    "TemporalInfo",
    "SourceType",
    "DocType",
    "EntityType",
    "ActionStatus",
    "OntologyDocumentSchema",
    "make_battle_event_document",
]
