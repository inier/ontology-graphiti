"""
本体管理引擎 v3 - Ontology Management Engine
Phase 5 MOD-05 - Complete Ontology Management System

WR-23: 数据摄入审计模块
WR-24: 本体构建器模块
WR-25: 版本管理器模块
WR-26: 验证引擎模块
WR-27: 本体管理引擎 UI

功能：
- 数据来源追踪
- 处理过程记录
- 异常检测
- 实体提取
- 关系识别
- 属性映射
- 版本追踪与回滚
- 数据质量检查
- 一致性验证
- 完整性验证
"""

import sys
import os
import json
import time
import threading
import hashlib
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class DataSourceType(Enum):
    """数据来源类型"""
    API = "api"
    FILE = "file"
    STREAM = "stream"
    MANUAL = "manual"
    CRAWLER = "crawler"


class ProcessingStatus(Enum):
    """处理状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class QualityLevel(Enum):
    """质量等级"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass
class DataSource:
    """数据来源"""
    source_id: str
    source_type: DataSourceType
    name: str
    description: str = ""
    endpoint: Optional[str] = None
    credentials: Optional[Dict] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


@dataclass
class IngestRecord:
    """摄入记录"""
    record_id: str
    source_id: str
    source_name: str
    status: ProcessingStatus
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: float = 0
    records_processed: int = 0
    records_failed: int = 0
    entities_extracted: int = 0
    relationships_extracted: int = 0
    quality_score: float = 0
    errors: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEvent:
    """审计事件"""
    event_id: str
    ingest_id: str
    timestamp: str
    level: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    actor: str = "system"


@dataclass
class Anomaly:
    """异常"""
    anomaly_id: str
    ingest_id: str
    anomaly_type: str
    severity: str
    description: str
    timestamp: str
    detected_at: str
    resolved: bool = False
    resolution: Optional[str] = None


@dataclass
class ExtractedEntity:
    """提取的实体"""
    entity_id: str
    entity_type: str
    name: str
    confidence: float
    attributes: Dict[str, Any] = field(default_factory=dict)
    source_text: Optional[str] = None
    position: Optional[Dict] = None


@dataclass
class ExtractedRelationship:
    """提取的关系"""
    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    confidence: float
    properties: Dict[str, Any] = field(default_factory=dict)
    bidirectional: bool = False


@dataclass
class OntologyVersion:
    """本体版本"""
    version_id: str
    version_number: str
    created_at: str
    created_by: str
    changes_summary: str
    entities_count: int
    relationships_count: int
    parent_version_id: Optional[str] = None
    is_current: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VersionDiff:
    """版本差异"""
    version_a_id: str
    version_b_id: str
    entities_added: List[str] = field(default_factory=list)
    entities_removed: List[str] = field(default_factory=list)
    entities_modified: List[Dict] = field(default_factory=list)
    relationships_added: List[str] = field(default_factory=list)
    relationships_removed: List[str] = field(default_factory=list)
    relationships_modified: List[Dict] = field(default_factory=list)


@dataclass
class QualityCheck:
    """质量检查"""
    check_id: str
    check_type: str
    passed: bool
    score: float
    details: str
    failed_items: List[Dict] = field(default_factory=list)


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    quality_level: QualityLevel
    overall_score: float
    checks: List[QualityCheck]
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class DataSourceTracker:
    """数据来源追踪器"""

    def __init__(self):
        self._sources: Dict[str, DataSource] = {}
        self._lock = threading.RLock()

    def register_source(self, source: DataSource) -> str:
        """注册数据来源"""
        with self._lock:
            self._sources[source.source_id] = source
            return source.source_id

    def get_source(self, source_id: str) -> Optional[DataSource]:
        """获取数据来源"""
        return self._sources.get(source_id)

    def list_sources(self) -> List[DataSource]:
        """列出所有数据来源"""
        return list(self._sources.values())


class ProcessingRecorder:
    """处理过程记录器"""

    def __init__(self):
        self._records: Dict[str, IngestRecord] = {}
        self._events: Dict[str, List[AuditEvent]] = {}
        self._lock = threading.RLock()

    def start_processing(self, source: DataSource) -> str:
        """开始处理"""
        with self._lock:
            record = IngestRecord(
                record_id=str(uuid.uuid4()),
                source_id=source.source_id,
                source_name=source.name,
                status=ProcessingStatus.PROCESSING,
                start_time=datetime.now(timezone.utc).isoformat()
            )
            self._records[record.record_id] = record
            self._events[record.record_id] = []
            return record.record_id

    def update_progress(self, record_id: str, processed: int, failed: int):
        """更新进度"""
        with self._lock:
            record = self._records.get(record_id)
            if record:
                record.records_processed = processed
                record.records_failed = failed

    def complete_processing(self, record_id: str, status: ProcessingStatus,
                          errors: List[Dict] = None):
        """完成处理"""
        with self._lock:
            record = self._records.get(record_id)
            if record:
                record.status = status
                record.end_time = datetime.now(timezone.utc).isoformat()
                if record.start_time:
                    start = datetime.fromisoformat(record.start_time.replace('Z', '+00:00'))
                    end = datetime.fromisoformat(record.end_time.replace('Z', '+00:00'))
                    record.duration_seconds = (end - start).total_seconds()
                if errors:
                    record.errors = errors

    def log_event(self, record_id: str, level: str, message: str,
                  details: Dict = None, actor: str = "system"):
        """记录事件"""
        with self._lock:
            if record_id not in self._events:
                self._events[record_id] = []
            event = AuditEvent(
                event_id=str(uuid.uuid4()),
                ingest_id=record_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                level=level,
                message=message,
                details=details or {},
                actor=actor
            )
            self._events[record_id].append(event)

    def get_record(self, record_id: str) -> Optional[IngestRecord]:
        """获取记录"""
        return self._records.get(record_id)

    def get_events(self, record_id: str) -> List[AuditEvent]:
        """获取事件"""
        return self._events.get(record_id, [])

    def get_records(self, limit: int = 100) -> List[IngestRecord]:
        """获取记录列表"""
        records = sorted(self._records.values(),
                        key=lambda r: r.start_time, reverse=True)
        return records[:limit]


class AnomalyDetector:
    """异常检测器"""

    def __init__(self):
        self._anomalies: Dict[str, List[Anomaly]] = {}
        self._thresholds = {
            "error_rate_warning": 0.05,
            "error_rate_critical": 0.15,
            "quality_score_warning": 0.7,
            "quality_score_critical": 0.5,
            "processing_time_deviation": 2.0
        }

    def detect_anomalies(self, record: IngestRecord) -> List[Anomaly]:
        """检测异常"""
        anomalies = []

        total = record.records_processed + record.records_failed
        if total > 0:
            error_rate = record.records_failed / total

            if error_rate >= self._thresholds["error_rate_critical"]:
                anomalies.append(Anomaly(
                    anomaly_id=str(uuid.uuid4()),
                    ingest_id=record.record_id,
                    anomaly_type="high_error_rate",
                    severity="critical",
                    description=f"错误率 {error_rate:.1%} 超过阈值",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    detected_at=datetime.now(timezone.utc).isoformat()
                ))
            elif error_rate >= self._thresholds["error_rate_warning"]:
                anomalies.append(Anomaly(
                    anomaly_id=str(uuid.uuid4()),
                    ingest_id=record.record_id,
                    anomaly_type="elevated_error_rate",
                    severity="warning",
                    description=f"错误率 {error_rate:.1%} 偏高",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    detected_at=datetime.now(timezone.utc).isoformat()
                ))

        if record.quality_score < self._thresholds["quality_score_critical"]:
            anomalies.append(Anomaly(
                anomaly_id=str(uuid.uuid4()),
                ingest_id=record.record_id,
                anomaly_type="low_quality",
                severity="critical",
                description=f"质量分数 {record.quality_score:.2f} 过低",
                timestamp=datetime.now(timezone.utc).isoformat(),
                detected_at=datetime.now(timezone.utc).isoformat()
            ))

        with self._lock:
            self._anomalies[record.record_id] = anomalies

        return anomalies

    def get_anomalies(self, record_id: str) -> List[Anomaly]:
        """获取异常"""
        return self._anomalies.get(record_id, [])


class EntityExtractor:
    """实体提取器"""

    def __init__(self):
        self._extractors: Dict[str, Callable] = {}

    def register_extractor(self, entity_type: str, extractor: Callable):
        """注册提取器"""
        self._extractors[entity_type] = extractor

    def extract(self, data: Any, entity_type: str) -> List[ExtractedEntity]:
        """提取实体"""
        if entity_type in self._extractors:
            return self._extractors[entity_type](data)

        return self._default_extraction(data, entity_type)

    def _default_extraction(self, data: Any, entity_type: str) -> List[ExtractedEntity]:
        """默认提取逻辑"""
        entities = []

        if isinstance(data, list):
            for item in data:
                entity = ExtractedEntity(
                    entity_id=str(uuid.uuid4()),
                    entity_type=entity_type,
                    name=str(item.get("name", item.get("id", "Unknown"))),
                    confidence=0.8,
                    attributes=item if isinstance(item, dict) else {}
                )
                entities.append(entity)
        elif isinstance(data, dict):
            entity = ExtractedEntity(
                entity_id=str(uuid.uuid4()),
                entity_type=entity_type,
                name=str(data.get("name", data.get("id", "Unknown"))),
                confidence=0.8,
                attributes=data
            )
            entities.append(entity)

        return entities


class RelationshipExtractor:
    """关系提取器"""

    def __init__(self):
        self._patterns: Dict[str, Callable] = {}

    def register_pattern(self, relation_type: str, pattern: Callable):
        """注册关系模式"""
        self._patterns[relation_type] = pattern

    def extract_relationships(self, entities: List[ExtractedEntity],
                            data: Any) -> List[ExtractedRelationship]:
        """提取关系"""
        relationships = []

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and "id" in item:
                            rel = ExtractedRelationship(
                                relationship_id=str(uuid.uuid4()),
                                source_entity_id=entities[0].entity_id if entities else "",
                                target_entity_id=item["id"],
                                relationship_type=key,
                                confidence=0.7,
                                properties={}
                            )
                            relationships.append(rel)

        return relationships


class AttributeMapper:
    """属性映射器"""

    def __init__(self):
        self._mappings: Dict[str, Dict[str, str]] = {}

    def register_mapping(self, source_type: str, target_type: str,
                       mapping: Dict[str, str]):
        """注册映射"""
        key = f"{source_type}->{target_type}"
        self._mappings[key] = mapping

    def map_attributes(self, attributes: Dict[str, Any],
                      source_type: str, target_type: str) -> Dict[str, Any]:
        """映射属性"""
        key = f"{source_type}->{target_type}"
        mapping = self._mappings.get(key, {})

        mapped = {}
        for source_attr, target_attr in mapping.items():
            if source_attr in attributes:
                mapped[target_attr] = attributes[source_attr]

        for k, v in attributes.items():
            if k not in mapping:
                mapped[k] = v

        return mapped


class VersionTracker:
    """版本追踪器"""

    def __init__(self):
        self._versions: Dict[str, OntologyVersion] = {}
        self._history: List[OntologyVersion] = []
        self._lock = threading.RLock()

    def create_version(self, version_number: str, created_by: str,
                     changes_summary: str, entities_count: int,
                     relationships_count: int) -> OntologyVersion:
        """创建版本"""
        with self._lock:
            version = OntologyVersion(
                version_id=str(uuid.uuid4()),
                version_number=version_number,
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by=created_by,
                changes_summary=changes_summary,
                entities_count=entities_count,
                relationships_count=relationships_count
            )

            for v in self._versions.values():
                v.is_current = False

            version.is_current = True
            self._versions[version.version_id] = version
            self._history.append(version)

            return version

    def get_version(self, version_id: str) -> Optional[OntologyVersion]:
        """获取版本"""
        return self._versions.get(version_id)

    def get_current_version(self) -> Optional[OntologyVersion]:
        """获取当前版本"""
        for v in self._versions.values():
            if v.is_current:
                return v
        return None

    def list_versions(self) -> List[OntologyVersion]:
        """列出所有版本"""
        return sorted(self._history, key=lambda v: v.created_at, reverse=True)


class ChangeComparator:
    """变更对比器"""

    def __init__(self):
        self._versions: Dict[str, OntologyVersion] = {}

    def compare(self, version_a_id: str, version_b_id: str,
              entities_a: List[Dict], entities_b: List[Dict],
              rels_a: List[Dict], rels_b: List[Dict]) -> VersionDiff:
        """对比两个版本"""
        entities_a_ids = {e.get("id"): e for e in entities_a}
        entities_b_ids = {e.get("id"): e for e in entities_b}

        rels_a_ids = {r.get("id"): r for r in rels_a}
        rels_b_ids = {r.get("id"): r for r in rels_b}

        added_entities = [eid for eid in entities_b_ids if eid not in entities_a_ids]
        removed_entities = [eid for eid in entities_a_ids if eid not in entities_b_ids]

        modified_entities = []
        for eid in entities_a_ids:
            if eid in entities_b_ids:
                if entities_a_ids[eid] != entities_b_ids[eid]:
                    modified_entities.append({
                        "entity_id": eid,
                        "before": entities_a_ids[eid],
                        "after": entities_b_ids[eid]
                    })

        added_rels = [rid for rid in rels_b_ids if rid not in rels_a_ids]
        removed_rels = [rid for rid in rels_a_ids if rid not in rels_b_ids]

        modified_rels = []
        for rid in rels_a_ids:
            if rid in rels_b_ids:
                if rels_a_ids[rid] != rels_b_ids[rid]:
                    modified_rels.append({
                        "relationship_id": rid,
                        "before": rels_a_ids[rid],
                        "after": rels_b_ids[rid]
                    })

        return VersionDiff(
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            entities_added=added_entities,
            entities_removed=removed_entities,
            entities_modified=modified_entities,
            relationships_added=added_rels,
            relationships_removed=removed_rels,
            relationships_modified=modified_rels
        )


class RollbackManager:
    """回滚管理器"""

    def __init__(self, version_tracker: VersionTracker):
        self._version_tracker = version_tracker
        self._snapshots: Dict[str, Dict] = {}

    def create_snapshot(self, version_id: str, data: Dict):
        """创建快照"""
        self._snapshots[version_id] = {
            "version_id": version_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
            "checksum": hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
        }

    def rollback(self, target_version_id: str) -> Optional[Dict]:
        """回滚到指定版本"""
        snapshot = self._snapshots.get(target_version_id)
        if snapshot:
            return snapshot["data"]
        return None

    def get_snapshot_info(self, version_id: str) -> Optional[Dict]:
        """获取快照信息"""
        return self._snapshots.get(version_id)


class QualityChecker:
    """数据质量检查器"""

    def __init__(self):
        self._rules: List[Dict] = []

    def add_rule(self, rule_type: str, check_func: Callable, threshold: float):
        """添加规则"""
        self._rules.append({
            "type": rule_type,
            "check": check_func,
            "threshold": threshold
        })

    def check_quality(self, entities: List[Dict], relationships: List[Dict]) -> List[QualityCheck]:
        """检查质量"""
        checks = []

        checks.append(self._check_completeness(entities))
        checks.append(self._check_consistency(entities, relationships))
        checks.append(self._check_integrity(entities, relationships))
        checks.append(self._check_accuracy(entities))

        return checks

    def _check_completeness(self, entities: List[Dict]) -> QualityCheck:
        """检查完整性"""
        total = len(entities)
        complete = sum(1 for e in entities if e.get("name") and e.get("type"))

        score = complete / total if total > 0 else 0
        passed = score >= 0.8

        return QualityCheck(
            check_id=str(uuid.uuid4()),
            check_type="completeness",
            passed=passed,
            score=score,
            details=f"完整实体: {complete}/{total}",
            failed_items=[e["id"] for e in entities if not e.get("name") or not e.get("type")]
        )

    def _check_consistency(self, entities: List[Dict], relationships: List[Dict]) -> QualityCheck:
        """检查一致性"""
        entity_ids = {e.get("id") for e in entities}

        valid_rels = []
        for r in relationships:
            if r.get("source") in entity_ids and r.get("target") in entity_ids:
                valid_rels.append(r)

        score = len(valid_rels) / len(relationships) if relationships else 1
        passed = score >= 0.95

        return QualityCheck(
            check_id=str(uuid.uuid4()),
            check_type="consistency",
            passed=passed,
            score=score,
            details=f"一致关系: {len(valid_rels)}/{len(relationships)}"
        )

    def _check_integrity(self, entities: List[Dict], relationships: List[Dict]) -> QualityCheck:
        """检查完整性"""
        orphaned_rels = []
        entity_ids = {e.get("id") for e in entities}

        for r in relationships:
            if r.get("source") not in entity_ids or r.get("target") not in entity_ids:
                orphaned_rels.append(r.get("id"))

        score = 1 - (len(orphaned_rels) / len(relationships)) if relationships else 1
        passed = score >= 0.98

        return QualityCheck(
            check_id=str(uuid.uuid4()),
            check_type="integrity",
            passed=passed,
            score=score,
            details=f"孤立关系: {len(orphaned_rels)}"
        )

    def _check_accuracy(self, entities: List[Dict]) -> QualityCheck:
        """检查准确性"""
        accurate = sum(1 for e in entities if e.get("confidence", 1) >= 0.7)

        score = accurate / len(entities) if entities else 1
        passed = score >= 0.85

        return QualityCheck(
            check_id=str(uuid.uuid4()),
            check_type="accuracy",
            passed=passed,
            score=score,
            details=f"准确实体: {accurate}/{len(entities)}"
        )


class OntologyManagementEngine:
    """
    本体管理引擎
    Phase 5 MOD-05 完整实现
    """

    def __init__(self):
        self._source_tracker = DataSourceTracker()
        self._processor = ProcessingRecorder()
        self._anomaly_detector = AnomalyDetector()
        self._entity_extractor = EntityExtractor()
        self._relationship_extractor = RelationshipExtractor()
        self._attribute_mapper = AttributeMapper()
        self._version_tracker = VersionTracker()
        self._comparator = ChangeComparator()
        self._rollback_manager = RollbackManager(self._version_tracker)
        self._quality_checker = QualityChecker()

        self._entities: Dict[str, Dict] = {}
        self._relationships: Dict[str, Dict] = {}
        self._lock = threading.RLock()

    def register_data_source(self, source_type: DataSourceType, name: str,
                           endpoint: str = None, description: str = "") -> str:
        """注册数据来源"""
        source = DataSource(
            source_id=str(uuid.uuid4()),
            source_type=source_type,
            name=name,
            description=description,
            endpoint=endpoint,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        return self._source_tracker.register_source(source)

    def ingest_data(self, source_id: str, data: Any,
                   entity_types: List[str] = None) -> str:
        """摄入数据"""
        source = self._source_tracker.get_source(source_id)
        if not source:
            raise ValueError(f"Data source not found: {source_id}")

        record_id = self._processor.start_processing(source)

        self._processor.log_event(record_id, "INFO", "开始数据摄入",
                                 {"data_size": len(str(data))})

        try:
            entity_types = entity_types or ["default"]

            for entity_type in entity_types:
                entities = self._entity_extractor.extract(data, entity_type)
                relationships = self._relationship_extractor.extract_relationships(
                    entities, data
                )

                with self._lock:
                    for entity in entities:
                        self._entities[entity.entity_id] = {
                            "id": entity.entity_id,
                            "type": entity.entity_type,
                            "name": entity.name,
                            "confidence": entity.confidence,
                            "attributes": entity.attributes
                        }

                    for rel in relationships:
                        self._relationships[rel.relationship_id] = {
                            "id": rel.relationship_id,
                            "source": rel.source_entity_id,
                            "target": rel.target_entity_id,
                            "type": rel.relationship_type,
                            "confidence": rel.confidence,
                            "properties": rel.properties
                        }

                self._processor.update_progress(
                    record_id,
                    len(entities) + len(relationships),
                    0
                )

            record = self._processor.get_record(record_id)
            if record:
                record.entities_extracted = len(self._entities)
                record.relationships_extracted = len(self._relationships)
                record.quality_score = self._calculate_quality_score()

            self._processor.complete_processing(record_id, ProcessingStatus.COMPLETED)

            anomalies = self._anomaly_detector.detect_anomalies(record)
            for anomaly in anomalies:
                self._processor.log_event(record_id, anomaly.severity.upper(),
                                         anomaly.description)

            self._processor.log_event(record_id, "INFO", "数据摄入完成",
                                     {"entities": len(self._entities),
                                      "relationships": len(self._relationships)})

            return record_id

        except Exception as e:
            self._processor.log_event(record_id, "ERROR", f"数据摄入失败: {str(e)}")
            self._processor.complete_processing(record_id, ProcessingStatus.FAILED,
                                               [{"error": str(e)}])
            raise

    def _calculate_quality_score(self) -> float:
        """计算质量分数"""
        if not self._entities:
            return 0.0

        checks = self._quality_checker.check_quality(
            list(self._entities.values()),
            list(self._relationships.values())
        )

        if not checks:
            return 0.0

        return sum(c.score for c in checks) / len(checks)

    def create_version(self, version_number: str, created_by: str,
                      changes_summary: str) -> OntologyVersion:
        """创建版本"""
        data = {
            "entities": list(self._entities.values()),
            "relationships": list(self._relationships.values())
        }

        version = self._version_tracker.create_version(
            version_number=version_number,
            created_by=created_by,
            changes_summary=changes_summary,
            entities_count=len(self._entities),
            relationships_count=len(self._relationships)
        )

        self._rollback_manager.create_snapshot(version.version_id, data)

        return version

    def compare_versions(self, version_a_id: str, version_b_id: str) -> VersionDiff:
        """对比版本"""
        version_a = self._version_tracker.get_version(version_a_id)
        version_b = self._version_tracker.get_version(version_b_id)

        if not version_a or not version_b:
            raise ValueError("Version not found")

        snapshot_a = self._rollback_manager.get_snapshot_info(version_a_id)
        snapshot_b = self._rollback_manager.get_snapshot_info(version_b_id)

        entities_a = snapshot_a["data"]["entities"] if snapshot_a else []
        entities_b = snapshot_b["data"]["entities"] if snapshot_b else []
        rels_a = snapshot_a["data"]["relationships"] if snapshot_a else []
        rels_b = snapshot_b["data"]["relationships"] if snapshot_b else []

        return self._comparator.compare(
            version_a_id, version_b_id,
            entities_a, entities_b,
            rels_a, rels_b
        )

    def rollback_to_version(self, version_id: str) -> bool:
        """回滚到指定版本"""
        data = self._rollback_manager.rollback(version_id)
        if not data:
            return False

        with self._lock:
            self._entities = {e["id"]: e for e in data["entities"]}
            self._relationships = {r["id"]: r for r in data["relationships"]}

        return True

    def validate(self) -> ValidationResult:
        """验证本体"""
        entities = list(self._entities.values())
        relationships = list(self._relationships.values())

        checks = self._quality_checker.check_quality(entities, relationships)

        all_passed = all(c.passed for c in checks)
        overall_score = sum(c.score for c in checks) / len(checks) if checks else 0

        if overall_score >= 0.9:
            quality_level = QualityLevel.EXCELLENT
        elif overall_score >= 0.75:
            quality_level = QualityLevel.GOOD
        elif overall_score >= 0.6:
            quality_level = QualityLevel.FAIR
        else:
            quality_level = QualityLevel.POOR

        issues = []
        for check in checks:
            if not check.passed:
                issues.append(f"{check.check_type}: {check.details}")

        recommendations = []
        if overall_score < 0.8:
            recommendations.append("建议进行数据清洗")
        if any(c.check_type == "completeness" and not c.passed for c in checks):
            recommendations.append("补充缺失的实体信息")

        return ValidationResult(
            is_valid=all_passed,
            quality_level=quality_level,
            overall_score=overall_score,
            checks=checks,
            issues=issues,
            recommendations=recommendations
        )

    def get_ingest_records(self, limit: int = 100) -> List[IngestRecord]:
        """获取摄入记录"""
        return self._processor.get_records(limit)

    def get_audit_events(self, record_id: str) -> List[AuditEvent]:
        """获取审计事件"""
        return self._processor.get_events(record_id)

    def get_anomalies(self, record_id: str) -> List[Anomaly]:
        """获取异常"""
        return self._anomaly_detector.get_anomalies(record_id)

    def get_current_entities(self) -> List[Dict]:
        """获取当前实体"""
        return list(self._entities.values())

    def get_current_relationships(self) -> List[Dict]:
        """获取当前关系"""
        return list(self._relationships.values())

    def get_versions(self) -> List[OntologyVersion]:
        """获取版本列表"""
        return self._version_tracker.list_versions()

    def get_current_version(self) -> Optional[OntologyVersion]:
        """获取当前版本"""
        return self._version_tracker.get_current_version()


_global_ontology_engine: Optional[OntologyManagementEngine] = None


def get_ontology_engine() -> OntologyManagementEngine:
    """获取全局本体管理引擎"""
    global _global_ontology_engine
    if _global_ontology_engine is None:
        _global_ontology_engine = OntologyManagementEngine()
    return _global_ontology_engine


if __name__ == "__main__":
    engine = get_ontology_engine()

    print("=" * 60)
    print("本体管理引擎 v3 测试")
    print("=" * 60)

    print("\n1. 注册数据来源:")
    source_id = engine.register_data_source(
        DataSourceType.API,
        "测试数据源",
        "https://api.example.com/data",
        "用于测试的数据来源"
    )
    print(f"   数据来源ID: {source_id}")

    print("\n2. 摄入数据:")
    test_data = [
        {"id": "e1", "name": "雷达站A", "type": "radar", "location": "A区"},
        {"id": "e2", "name": "指挥中心", "type": "command", "location": "B区"},
        {"id": "e3", "name": "补给站", "type": "logistics", "location": "C区"},
    ]
    record_id = engine.ingest_data(source_id, test_data, ["radar", "command", "logistics"])
    print(f"   摄入记录ID: {record_id}")

    print("\n3. 摄入记录:")
    records = engine.get_ingest_records()
    if records:
        print(f"   记录数: {len(records)}")
        print(f"   状态: {records[0].status.value}")
        print(f"   提取实体: {records[0].entities_extracted}")

    print("\n4. 验证本体:")
    validation = engine.validate()
    print(f"   有效: {validation.is_valid}")
    print(f"   质量等级: {validation.quality_level.value}")
    print(f"   整体分数: {validation.overall_score:.2f}")

    print("\n5. 创建版本:")
    version = engine.create_version("1.0.0", "system", "初始版本")
    print(f"   版本ID: {version.version_id}")
    print(f"   版本号: {version.version_number}")

    print("\n" + "=" * 60)
    print("本体管理引擎 v3 测试完成")
    print("=" * 60)