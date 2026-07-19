"""
L2 Construction BuildResultContract — 构建产物只读契约。

供 +AI Reasoning 和 L3 Application 层读取构建产物。
所有返回值为 Frozen Dataclass Views，禁止直接引用内部实现类。

写入操作走 construction/contract/bridge.py，不走此契约。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


class ContractError(Exception):
    """Contract layer base exception."""


class ContractNotFoundError(ContractError):
    """Requested build result not found."""


@dataclass(frozen=True)
class EntityInstanceView:
    """构建产出的实体实例视图 (Frozen)"""
    instance_id: str
    entity_type_id: str       # 对应 L1 Design 的 EntityType
    properties: Dict[str, Any] = field(default_factory=dict)
    source_trace: str = ""    # 数据来源追溯
    confidence: float = 1.0   # 置信度 [0, 1]
    created_at: str = ""      # ISO format
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RelationInstanceView:
    """构建产出的关系实例视图 (Frozen)"""
    relation_id: str
    relation_type_id: str     # 对应 L1 Design 的 RelationType
    source_instance_id: str
    target_instance_id: str
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BuildStatusView:
    """构建流水线状态视图 (Frozen)"""
    pipeline_run_id: str
    status: str               # pending / running / completed / failed
    stages: tuple = ()        # tuple of stage names
    current_stage: str = ""
    progress: float = 0.0     # 0-100
    errors: tuple = ()        # tuple of error messages
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True)
class QualityReportView:
    """构建质量报告视图 (Frozen)"""
    pipeline_run_id: str
    total_entities: int = 0
    pass_count: int = 0
    fail_count: int = 0
    anomaly_details: tuple = ()  # tuple of anomaly dicts
    severity: str = "info"       # info / warning / error
    generated_at: str = ""


@dataclass(frozen=True)
class IngestionSourceView:
    """数据摄入源视图 (Frozen)"""
    source_id: str
    source_type: str         # DataSourceType as string
    workspace_id: str
    last_run_at: str = ""
    record_count: int = 0
    status: str = "inactive"
    metadata: Dict[str, Any] = field(default_factory=dict)


class BuildResultContract:
    """
    L2 Construction 对外只读契约.

    +AI Reasoning 和 L3 Application 层依赖此抽象，
    而非 construction/ 内部具体实现。
    """

    def list_entity_instances(
        self, entity_type_id: str,
        limit: int = 100, offset: int = 0,
    ) -> List[EntityInstanceView]:
        raise NotImplementedError

    def get_entity_instance(self, instance_id: str) -> EntityInstanceView:
        raise NotImplementedError

    def list_relation_instances(
        self, source_entity_id: str, relation_type: str = "",
        limit: int = 100, offset: int = 0,
    ) -> List[RelationInstanceView]:
        raise NotImplementedError

    def get_build_status(self, pipeline_run_id: str) -> BuildStatusView:
        raise NotImplementedError

    def get_quality_report(self, pipeline_run_id: str) -> QualityReportView:
        raise NotImplementedError

    def list_ingestion_sources(self, workspace_id: str) -> List[IngestionSourceView]:
        raise NotImplementedError
