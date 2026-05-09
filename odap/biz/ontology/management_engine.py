"""
本体管理引擎 - 对齐 docs/03-modules/ontology_management_engine/DESIGN.md

核心引擎，包含：
- 数据摄入审计
- 本体构建
- 版本管理
- 验证引擎
- 审计仪表盘
"""

import json
import uuid
import time
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

from .models.ontology_engine import (
    DataSource, ProcessingStatus, OntologyStatus, VersionStatus,
    VersionOperation, QualityMetricType, AnomalyType, OntologyHealthStatus,
    DataIngestRecord, AuditLog, OntologyBuildResult, OntologyDocument,
    VersionRecord, VersionChange, ValidationRule, ValidationError,
    ValidationResult, AnomalyRecord, AuditDashboardData,
)


class DataIngestAudit:
    """数据摄入审计器"""

    def __init__(self):
        self._records: Dict[str, DataIngestRecord] = {}
        self._logs: List[AuditLog] = []
        self._lock = threading.Lock()

    def start_ingest(self, source: DataSource, source_details: Dict = None,
                     data_schema: Dict = None, created_by: str = "system") -> DataIngestRecord:
        record = DataIngestRecord(
            source=source,
            source_details=source_details or {},
            data_schema=data_schema or {},
            created_by=created_by,
        )
        with self._lock:
            self._records[record.id] = record
        self._add_log(record.id, "info", f"Data ingest started from {source.value}", created_by)
        return record

    def update_progress(self, ingest_id: str, records_processed: int, records_failed: int = 0):
        with self._lock:
            record = self._records.get(ingest_id)
            if record:
                record.processed_count += records_processed
                record.failed_count += records_failed
                record.status = ProcessingStatus.PROCESSING

    def complete_ingest(self, ingest_id: str, total_records: int,
                        errors: List[Dict] = None, quality_metrics: Dict = None) -> DataIngestRecord:
        with self._lock:
            record = self._records.get(ingest_id)
            if record:
                record.record_count = total_records
                record.status = ProcessingStatus.COMPLETED
                record.end_time = datetime.now()
                if record.start_time:
                    record.duration_seconds = (record.end_time - record.start_time).total_seconds()
                if errors:
                    record.errors = errors
                    if record.failed_count > 0:
                        record.status = ProcessingStatus.FAILED
                if quality_metrics:
                    record.quality_metrics = quality_metrics
            return record

    def get_record(self, ingest_id: str) -> Optional[DataIngestRecord]:
        return self._records.get(ingest_id)

    def get_all_records(self) -> List[DataIngestRecord]:
        return list(self._records.values())

    def _add_log(self, ingest_id: str, level: str, message: str, actor: str = "system"):
        log = AuditLog(ingest_id=ingest_id, level=level, message=message, actor=actor)
        with self._lock:
            self._logs.append(log)


class ValidationEngine:
    """验证引擎 - 数据质量和一致性检查"""

    def __init__(self):
        self._rules: Dict[str, ValidationRule] = {}
        self._results: List[ValidationResult] = []
        self._lock = threading.Lock()
        self._init_default_rules()

    def _init_default_rules(self):
        defaults = [
            ValidationRule(
                name="require_id", description="Each entity must have a unique id",
                rule_type="completeness", severity="error",
                condition={"field": "id", "operator": "exists"},
            ),
            ValidationRule(
                name="require_name", description="Each entity must have a name",
                rule_type="completeness", severity="error",
                condition={"field": "name", "operator": "exists"},
            ),
            ValidationRule(
                name="require_type", description="Each entity must have a type",
                rule_type="completeness", severity="error",
                condition={"field": "type", "operator": "exists"},
            ),
            ValidationRule(
                name="no_duplicate_id", description="Entity ids must be unique",
                rule_type="consistency", severity="error",
                condition={"field": "id", "operator": "unique"},
            ),
        ]
        for rule in defaults:
            self._rules[rule.name] = rule

    def add_rule(self, rule: ValidationRule):
        with self._lock:
            self._rules[rule.name] = rule

    def remove_rule(self, name: str):
        with self._lock:
            self._rules.pop(name, None)

    def validate(self, ontology: OntologyDocument) -> ValidationResult:
        result = ValidationResult(ontology_id=ontology.id)
        start = time.time()

        errors = []
        warnings = []
        total = len([r for r in self._rules.values() if r.enabled])
        passed = 0

        entities = ontology.entities
        ids = [e.get("id") for e in entities]

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            rule_errors = []
            if rule.name == "require_id":
                for i, entity in enumerate(entities):
                    if not entity.get("id"):
                        rule_errors.append(ValidationError(
                            rule_id=rule.name, entity_id=f"entity[{i}]",
                            field="id", message="Missing required field: id",
                            severity=rule.severity,
                        ))
            elif rule.name == "require_name":
                for i, entity in enumerate(entities):
                    if not entity.get("name"):
                        rule_errors.append(ValidationError(
                            rule_id=rule.name, entity_id=entity.get("id", f"entity[{i}]"),
                            field="name", message="Missing required field: name",
                            severity=rule.severity,
                        ))
            elif rule.name == "require_type":
                for i, entity in enumerate(entities):
                    if not entity.get("type"):
                        rule_errors.append(ValidationError(
                            rule_id=rule.name, entity_id=entity.get("id", f"entity[{i}]"),
                            field="type", message="Missing required field: type",
                            severity=rule.severity,
                        ))
            elif rule.name == "no_duplicate_id":
                seen = set()
                for eid in ids:
                    if eid in seen:
                        rule_errors.append(ValidationError(
                            rule_id=rule.name, entity_id=eid,
                            field="id", message=f"Duplicate id: {eid}",
                            severity=rule.severity,
                        ))
                    seen.add(eid)

            if not rule_errors:
                passed += 1
            else:
                for e in rule_errors:
                    if e.severity == "error":
                        errors.append(e)
                    else:
                        warnings.append(e)

        result.passed = len(errors) == 0
        result.total_rules = total
        result.passed_rules = passed
        result.failed_rules = total - passed
        result.errors = errors
        result.warnings = warnings
        result.duration_seconds = time.time() - start
        result.quality_scores = self._compute_quality_scores(ontology)

        with self._lock:
            self._results.append(result)

        return result

    def _compute_quality_scores(self, ontology: OntologyDocument) -> Dict[str, float]:
        scores = {
            QualityMetricType.COMPLETENESS.value: 100.0,
            QualityMetricType.CONSISTENCY.value: 100.0,
            QualityMetricType.UNIQUENESS.value: 100.0,
        }
        entities = ontology.entities
        if not entities:
            return scores

        complete_count = sum(1 for e in entities if e.get("id") and e.get("name") and e.get("type"))
        scores[QualityMetricType.COMPLETENESS.value] = round(complete_count / len(entities) * 100, 1)

        ids = [e.get("id") for e in entities if e.get("id")]
        unique_count = len(set(ids))
        if ids:
            scores[QualityMetricType.UNIQUENESS.value] = round(unique_count / len(ids) * 100, 1)

        return scores

    def get_last_result(self) -> Optional[ValidationResult]:
        return self._results[-1] if self._results else None


class VersionManager:
    """版本管理器"""

    def __init__(self):
        self._versions: Dict[str, VersionRecord] = {}
        self._current: Optional[str] = None
        self._lock = threading.Lock()

    def create_version(self, snapshot: Dict, description: str = "",
                       created_by: str = "system") -> VersionRecord:
        number = f"{len(self._versions) + 1}.0.0"
        record = VersionRecord(
            version_number=number,
            snapshot=snapshot,
            description=description,
            created_by=created_by,
        )
        if self._current:
            record.parent_version = self._versions[self._current].version_number

        with self._lock:
            self._versions[record.id] = record
            self._current = record.id
        return record

    def rollback(self, version_id: str, changed_by: str = "system") -> Optional[VersionRecord]:
        target = self._versions.get(version_id)
        if not target:
            return None

        new_record = VersionRecord(
            snapshot=target.snapshot,
            description=f"Rollback to version {target.version_number}",
            created_by=changed_by,
            parent_version=target.version_number,
            version_number=f"{len(self._versions) + 1}.0.0",
        )
        change = VersionChange(
            field="version", old_value=self._current, new_value=version_id,
            change_type=VersionOperation.ROLLBACK.value, changed_by=changed_by,
        )
        new_record.changes = [change]

        with self._lock:
            self._versions[new_record.id] = new_record
            self._current = new_record.id
        return new_record

    def get_version(self, version_id: str) -> Optional[VersionRecord]:
        return self._versions.get(version_id)

    def get_current(self) -> Optional[VersionRecord]:
        return self._versions.get(self._current) if self._current else None

    def list_versions(self) -> List[VersionRecord]:
        return sorted(self._versions.values(), key=lambda v: v.created_at, reverse=True)


class AuditDashboard:
    """审计仪表盘"""

    def __init__(self, ingest_audit: DataIngestAudit, validation_engine: ValidationEngine,
                 version_manager: VersionManager):
        self._ingest = ingest_audit
        self._validation = validation_engine
        self._version = version_manager
        self._anomalies: List[AnomalyRecord] = []

    def get_dashboard_data(self) -> AuditDashboardData:
        records = self._ingest.get_all_records()
        total_ingests = len(records)
        completed = sum(1 for r in records if r.status == ProcessingStatus.COMPLETED)
        success_rate = (completed / total_ingests * 100) if total_ingests > 0 else 100.0

        current = self._version.get_current()
        total_entities = len(current.snapshot.get("entities", [])) if current else 0
        total_relations = len(current.snapshot.get("relations", [])) if current else 0

        last_validation = self._validation.get_last_result()
        validation_pass_rate = (
            (last_validation.passed_rules / last_validation.total_rules * 100)
            if last_validation and last_validation.total_rules > 0 else 100.0
        )

        version_history = [
            {"version": v.version_number, "description": v.description, "created_at": v.created_at.isoformat()}
            for v in self._version.list_versions()[:10]
        ]

        return AuditDashboardData(
            total_ingests=total_ingests,
            total_entities=total_entities,
            total_relations=total_relations,
            build_success_rate=round(success_rate, 1),
            validation_pass_rate=round(validation_pass_rate, 1),
            recent_anomalies=self._anomalies[-10:],
            version_history=version_history,
        )

    def record_anomaly(self, anomaly: AnomalyRecord):
        self._anomalies.append(anomaly)
        if len(self._anomalies) > 1000:
            self._anomalies = self._anomalies[-500:]

    def get_health_status(self) -> OntologyHealthStatus:
        data = self.get_dashboard_data()
        if data.build_success_rate < 50 or data.validation_pass_rate < 50:
            return OntologyHealthStatus.CRITICAL
        if data.build_success_rate < 80 or data.validation_pass_rate < 80:
            return OntologyHealthStatus.WARNING
        return OntologyHealthStatus.HEALTHY


class OntologyManagementEngine:
    """本体管理引擎 - 核心入口"""

    def __init__(self):
        self.ingest_audit = DataIngestAudit()
        self.validation = ValidationEngine()
        self.version = VersionManager()
        self.dashboard = AuditDashboard(self.ingest_audit, self.validation, self.version)

        self.ontology_documents: Dict[str, OntologyDocument] = {}
        self._lock = threading.Lock()

    def create_ontology(self, name: str, description: str = "",
                        created_by: str = "system") -> OntologyDocument:
        doc = OntologyDocument(name=name, description=description, created_by=created_by)
        with self._lock:
            self.ontology_documents[doc.id] = doc
        return doc

    def build_ontology(self, doc_id: str, entities: List[Dict], relations: List[Dict] = None,
                       properties: List[Dict] = None) -> OntologyBuildResult:
        with self._lock:
            doc = self.ontology_documents.get(doc_id)
        if not doc:
            return OntologyBuildResult(status=ProcessingStatus.FAILED,
                                       errors=[{"msg": "Document not found"}])

        build = OntologyBuildResult(source_ingest_id=doc_id)
        try:
            doc.entities = entities
            doc.relations = relations or []
            doc.properties = properties or []
            doc.updated_at = datetime.now()

            build.entity_count = len(entities)
            build.relation_count = len(relations) if relations else 0
            build.property_count = len(properties) if properties else 0
            build.status = ProcessingStatus.COMPLETED
            build.end_time = datetime.now()
            build.duration_seconds = (build.end_time - build.start_time).total_seconds() if build.start_time else 0

            valid_result = self.validation.validate(doc)
            build.warnings = [e.model_dump() for e in valid_result.warnings]

            if not valid_result.passed:
                build.errors = [e.model_dump() for e in valid_result.errors]
                build.status = ProcessingStatus.FAILED

            self.version.create_version(
                snapshot=doc.model_dump(),
                description=f"Build completed: {doc.name}",
            )
        except Exception as e:
            build.status = ProcessingStatus.FAILED
            build.errors.append({"msg": str(e)})

        return build

    def get_ontology(self, doc_id: str) -> Optional[OntologyDocument]:
        return self.ontology_documents.get(doc_id)

    def get_dashboard_data(self) -> AuditDashboardData:
        return self.dashboard.get_dashboard_data()

    def get_health_status(self) -> OntologyHealthStatus:
        return self.dashboard.get_health_status()
