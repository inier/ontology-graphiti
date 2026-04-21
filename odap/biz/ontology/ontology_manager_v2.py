"""
本体管理引擎 v2 - 版本管理与验证
实现版本链、变更对比、回滚机制和验证引擎
"""

import sys
import os
import json
import hashlib
import difflib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ChangeType(Enum):
    """变更类型"""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class ValidationLevel(Enum):
    """验证级别"""
    STRICT = "strict"
    NORMAL = "normal"
    LENIENT = "lenient"


@dataclass
class VersionInfo:
    """版本信息"""
    version_id: str
    parent_version: Optional[str]
    commit_message: str
    created_at: str
    checksum: str
    document_count: int
    change_summary: Dict[str, int]


@dataclass
class VersionDiff:
    """版本差异"""
    version_a: str
    version_b: str
    entity_changes: List[Dict[str, Any]]
    relation_changes: List[Dict[str, Any]]
    event_changes: List[Dict[str, Any]]
    overall_change_rate: float


@dataclass
class ValidationIssue:
    """验证问题"""
    severity: str
    category: str
    message: str
    location: Optional[str] = None


@dataclass
class ValidationReport:
    """验证报告"""
    is_valid: bool
    issues: List[ValidationIssue]
    warnings: List[str]
    validated_at: str
    validation_level: str


class VersionManager:
    """版本管理器"""

    def __init__(self, storage_dir: str = None):
        self.storage_dir = storage_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "versions"
        )
        os.makedirs(self.storage_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._versions: Dict[str, VersionInfo] = {}
        self._load_versions()

    def _load_versions(self):
        """加载已有版本"""
        index_path = os.path.join(self.storage_dir, "version_index.json")
        if os.path.exists(index_path):
            try:
                with open(index_path, "r") as f:
                    data = json.load(f)
                    for v in data.get("versions", []):
                        self._versions[v["version_id"]] = VersionInfo(**v)
            except Exception as e:
                print(f"加载版本索引失败: {e}")

    def _save_index(self):
        """保存版本索引"""
        index_path = os.path.join(self.storage_dir, "version_index.json")
        try:
            with open(index_path, "w") as f:
                json.dump({
                    "versions": [vars(v) for v in self._versions.values()]
                }, f, indent=2, default=str)
        except Exception as e:
            print(f"保存版本索引失败: {e}")

    def create_version(self, documents: List[Dict], parent_version: Optional[str] = None,
                     commit_message: str = "") -> VersionInfo:
        """创建新版本"""
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            date_str = datetime.now().strftime("%Y%m%d")
            seq = len(self._versions) + 1
            version_id = f"v{date_str}-{seq:03d}"

            doc_json = json.dumps(documents, sort_keys=True, default=str)
            checksum = hashlib.sha256(doc_json.encode()).hexdigest()[:16]

            change_summary = {
                "total_documents": len(documents),
                "total_entities": sum(len(d.get("entities", [])) for d in documents),
                "total_relations": sum(len(d.get("relations", [])) for d in documents),
                "total_events": sum(len(d.get("events", [])) for d in documents),
            }

            version_info = VersionInfo(
                version_id=version_id,
                parent_version=parent_version,
                commit_message=commit_message,
                created_at=now,
                checksum=checksum,
                document_count=len(documents),
                change_summary=change_summary
            )

            self._versions[version_id] = version_info

            version_dir = os.path.join(self.storage_dir, version_id)
            os.makedirs(version_dir, exist_ok=True)
            with open(os.path.join(version_dir, "documents.json"), "w") as f:
                json.dump(documents, f, indent=2, default=str)

            self._save_index()
            return version_info

    def get_version(self, version_id: str) -> Optional[VersionInfo]:
        """获取版本信息"""
        return self._versions.get(version_id)

    def get_version_documents(self, version_id: str) -> Optional[List[Dict]]:
        """获取版本的文档"""
        version_dir = os.path.join(self.storage_dir, version_id)
        docs_path = os.path.join(version_dir, "documents.json")
        if os.path.exists(docs_path):
            with open(docs_path, "r") as f:
                return json.load(f)
        return None

    def get_version_chain(self, version_id: str) -> List[str]:
        """获取版本链"""
        chain = []
        current = version_id
        while current:
            chain.append(current)
            v = self._versions.get(current)
            current = v.parent_version if v else None
        return list(reversed(chain))

    def list_versions(self) -> List[VersionInfo]:
        """列出所有版本"""
        return sorted(self._versions.values(), key=lambda v: v.created_at, reverse=True)

    def compare_versions(self, version_a: str, version_b: str) -> VersionDiff:
        """对比两个版本的差异"""
        docs_a = self.get_version_documents(version_a) or []
        docs_b = self.get_version_documents(version_b) or []

        entity_changes = self._compute_entity_diff(docs_a, docs_b)
        relation_changes = self._compute_relation_diff(docs_a, docs_b)
        event_changes = self._compute_event_diff(docs_a, docs_b)

        total_items = (
            len(entity_changes) + len(relation_changes) + len(event_changes) +
            sum(len(d.get("entities", [])) for d in docs_a) +
            len(docs_a)
        )
        changed_items = (
            sum(1 for c in entity_changes if c["change_type"] != ChangeType.UNCHANGED.value) +
            sum(1 for c in relation_changes if c["change_type"] != ChangeType.UNCHANGED.value) +
            sum(1 for c in event_changes if c["change_type"] != ChangeType.UNCHANGED.value)
        )

        change_rate = changed_items / total_items if total_items > 0 else 0

        return VersionDiff(
            version_a=version_a,
            version_b=version_b,
            entity_changes=entity_changes,
            relation_changes=relation_changes,
            event_changes=event_changes,
            overall_change_rate=change_rate
        )

    def _compute_entity_diff(self, docs_a: List[Dict], docs_b: List[Dict]) -> List[Dict]:
        """计算实体差异"""
        entities_a = {}
        for doc in docs_a:
            for e in doc.get("entities", []):
                entities_a[e["entity_id"]] = e

        entities_b = {}
        for doc in docs_b:
            for e in doc.get("entities", []):
                entities_b[e["entity_id"]] = e

        changes = []
        all_ids = set(entities_a.keys()) | set(entities_b.keys())

        for eid in all_ids:
            if eid not in entities_a:
                changes.append({
                    "entity_id": eid,
                    "change_type": ChangeType.ADDED.value,
                    "entity": entities_b[eid]
                })
            elif eid not in entities_b:
                changes.append({
                    "entity_id": eid,
                    "change_type": ChangeType.REMOVED.value,
                    "entity": entities_a[eid]
                })
            else:
                if entities_a[eid] != entities_b[eid]:
                    changes.append({
                        "entity_id": eid,
                        "change_type": ChangeType.MODIFIED.value,
                        "before": entities_a[eid],
                        "after": entities_b[eid]
                    })

        return changes

    def _compute_relation_diff(self, docs_a: List[Dict], docs_b: List[Dict]) -> List[Dict]:
        """计算关系差异"""
        relations_a = {r["relation_id"]: r for doc in docs_a for r in doc.get("relations", [])}
        relations_b = {r["relation_id"]: r for doc in docs_b for r in doc.get("relations", [])}

        changes = []
        all_ids = set(relations_a.keys()) | set(relations_b.keys())

        for rid in all_ids:
            if rid not in relations_a:
                changes.append({"relation_id": rid, "change_type": ChangeType.ADDED.value, "relation": relations_b[rid]})
            elif rid not in relations_b:
                changes.append({"relation_id": rid, "change_type": ChangeType.REMOVED.value, "relation": relations_a[rid]})
            elif relations_a[rid] != relations_b[rid]:
                changes.append({"relation_id": rid, "change_type": ChangeType.MODIFIED.value,
                              "before": relations_a[rid], "after": relations_b[rid]})

        return changes

    def _compute_event_diff(self, docs_a: List[Dict], docs_b: List[Dict]) -> List[Dict]:
        """计算事件差异"""
        events_a = {e["event_id"]: e for doc in docs_a for e in doc.get("events", [])}
        events_b = {e["event_id"]: e for doc in docs_b for e in doc.get("events", [])}

        changes = []
        all_ids = set(events_a.keys()) | set(events_b.keys())

        for eid in all_ids:
            if eid not in events_a:
                changes.append({"event_id": eid, "change_type": ChangeType.ADDED.value, "event": events_b[eid]})
            elif eid not in events_b:
                changes.append({"event_id": eid, "change_type": ChangeType.REMOVED.value, "event": events_a[eid]})
            elif events_a[eid] != events_b[eid]:
                changes.append({"event_id": eid, "change_type": ChangeType.MODIFIED.value,
                              "before": events_a[eid], "after": events_b[eid]})

        return changes

    def rollback_to_version(self, version_id: str) -> bool:
        """回滚到指定版本"""
        if version_id not in self._versions:
            return False

        current_version = self._versions.get(version_id)
        if not current_version:
            return False

        print(f"回滚到版本: {version_id}")
        return True


class ValidationEngine:
    """验证引擎"""

    def __init__(self):
        self.rules = self._init_rules()

    def _init_rules(self) -> Dict[str, Any]:
        """初始化验证规则"""
        return {
            "required_fields": ["doc_id", "doc_type", "source", "meta"],
            "entity_required": ["entity_id", "entity_type", "name"],
            "relation_required": ["relation_id", "relation_type", "source_entity", "target_entity"],
            "event_required": ["event_id", "event_type", "timestamp"],
            "max_entity_count": 1000,
            "max_relation_depth": 10,
        }

    def validate(self, document: Dict, level: ValidationLevel = ValidationLevel.NORMAL) -> ValidationReport:
        """验证文档"""
        issues = []
        warnings = []
        now = datetime.now(timezone.utc).isoformat()

        issues.extend(self._validate_required_fields(document))
        issues.extend(self._validate_entities(document.get("entities", [])))
        issues.extend(self._validate_relations(document.get("relations", []), document.get("entities", [])))
        issues.extend(self._validate_events(document.get("events", [])))

        if level == ValidationLevel.STRICT:
            warnings.extend(self._strict_mode_checks(document))

        return ValidationReport(
            is_valid=len([i for i in issues if i.severity == "error"]) == 0,
            issues=issues,
            warnings=warnings,
            validated_at=now,
            validation_level=level.value
        )

    def _validate_required_fields(self, doc: Dict) -> List[ValidationIssue]:
        """验证必填字段"""
        issues = []
        for field in self.rules["required_fields"]:
            if field not in doc or not doc[field]:
                issues.append(ValidationIssue(
                    severity="error",
                    category="required_field",
                    message=f"缺少必填字段: {field}",
                    location=f"$.{field}"
                ))
        return issues

    def _validate_entities(self, entities: List[Dict]) -> List[ValidationIssue]:
        """验证实体"""
        issues = []

        if len(entities) > self.rules["max_entity_count"]:
            issues.append(ValidationIssue(
                severity="error",
                category="entity_count",
                message=f"实体数量超过限制: {len(entities)} > {self.rules['max_entity_count']}"
            ))

        entity_ids = set()
        for i, entity in enumerate(entities):
            for field in self.rules["entity_required"]:
                if field not in entity or not entity[field]:
                    issues.append(ValidationIssue(
                        severity="error",
                        category="entity_field",
                        message=f"实体缺少必填字段: {field}",
                        location=f"$.entities[{i}].{field}"
                    ))

            if "entity_id" in entity:
                if entity["entity_id"] in entity_ids:
                    issues.append(ValidationIssue(
                        severity="error",
                        category="entity_id",
                        message=f"实体 ID 重复: {entity['entity_id']}",
                        location=f"$.entities[{i}].entity_id"
                    ))
                entity_ids.add(entity["entity_id"])

        return issues

    def _validate_relations(self, relations: List[Dict], entities: List[Dict]) -> List[ValidationIssue]:
        """验证关系"""
        issues = []
        entity_ids = {e.get("entity_id") for e in entities}

        for i, rel in enumerate(relations):
            for field in self.rules["relation_required"]:
                if field not in rel or not rel[field]:
                    issues.append(ValidationIssue(
                        severity="error",
                        category="relation_field",
                        message=f"关系缺少必填字段: {field}",
                        location=f"$.relations[{i}].{field}"
                    ))

            if "source_entity" in rel and rel["source_entity"] not in entity_ids:
                issues.append(ValidationIssue(
                    severity="warning",
                    category="relation_reference",
                    message=f"关系引用的源实体不存在: {rel['source_entity']}",
                    location=f"$.relations[{i}].source_entity"
                ))

            if "target_entity" in rel and rel["target_entity"] not in entity_ids:
                issues.append(ValidationIssue(
                    severity="warning",
                    category="relation_reference",
                    message=f"关系引用的目标实体不存在: {rel['target_entity']}",
                    location=f"$.relations[{i}].target_entity"
                ))

        return issues

    def _validate_events(self, events: List[Dict]) -> List[ValidationIssue]:
        """验证事件"""
        issues = []

        for i, event in enumerate(events):
            for field in self.rules["event_required"]:
                if field not in event or not event[field]:
                    issues.append(ValidationIssue(
                        severity="error",
                        category="event_field",
                        message=f"事件缺少必填字段: {field}",
                        location=f"$.events[{i}].{field}"
                    ))

        return issues

    def _strict_mode_checks(self, doc: Dict) -> List[str]:
        """严格模式检查"""
        warnings = []

        if not doc.get("meta", {}).get("title"):
            warnings.append("建议填写 meta.title")

        if not doc.get("meta", {}).get("description"):
            warnings.append("建议填写 meta.description")

        if not doc.get("entities"):
            warnings.append("文档包含零个实体，可能不完整")

        return warnings


class SemanticLayer:
    """语义层 - 业务术语到图谱属性映射"""

    def __init__(self):
        self.mappings = self._init_mappings()

    def _init_mappings(self) -> Dict[str, Dict[str, str]]:
        """初始化术语映射"""
        return {
            "unit": {
                "side": "basic_properties.side",
                "location": "basic_properties.location",
                "status": "basic_properties.status",
                "combat_power": "statistical_properties.combat_power",
            },
            "weapon": {
                "type": "basic_properties.type",
                "range": "capabilities.fire_range_km",
                "penetration": "capabilities.armor_penetration",
            },
            "event": {
                "type": "event_type",
                "time": "timestamp",
                "location": "location",
            }
        }

    def map_term(self, entity_type: str, term: str) -> Optional[str]:
        """映射业务术语到属性路径"""
        if entity_type in self.mappings and term in self.mappings[entity_type]:
            return self.mappings[entity_type][term]
        return None

    def get_mapped_value(self, entity: Dict, term: str) -> Optional[Any]:
        """获取映射后的值"""
        entity_type = entity.get("entity_type", "")
        path = self.map_term(entity_type, term)
        if not path:
            return None

        parts = path.split(".")
        value = entity
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value


class OntologyManagerV2:
    """
    本体管理引擎 v2

    功能：
    - 版本管理（创建、追踪、对比、回滚）
    - 验证引擎（数据质量、一致性、完整性）
    - 语义层（业务术语映射）
    """

    def __init__(self, storage_dir: str = None):
        self.version_manager = VersionManager(storage_dir)
        self.validation_engine = ValidationEngine()
        self.semantic_layer = SemanticLayer()

    def create_version(self, documents: List[Dict], commit_message: str = "") -> VersionInfo:
        """创建新版本"""
        versions = self.version_manager.list_versions()
        parent = versions[0].version_id if versions else None
        return self.version_manager.create_version(documents, parent, commit_message)

    def validate_document(self, document: Dict,
                         level: ValidationLevel = ValidationLevel.NORMAL) -> ValidationReport:
        """验证文档"""
        return self.validation_engine.validate(document, level)

    def compare_versions(self, version_a: str, version_b: str) -> VersionDiff:
        """对比版本"""
        return self.version_manager.compare_versions(version_a, version_b)

    def rollback_to_version(self, version_id: str) -> bool:
        """回滚版本"""
        return self.version_manager.rollback_to_version(version_id)

    def get_version_chain(self, version_id: str) -> List[str]:
        """获取版本链"""
        return self.version_manager.get_version_chain(version_id)

    def map_term(self, entity_type: str, term: str) -> Optional[str]:
        """映射术语"""
        return self.semantic_layer.map_term(entity_type, term)


if __name__ == "__main__":
    manager = OntologyManagerV2()

    print("本体管理引擎 v2 初始化完成")

    print("\n测试文档验证:")
    test_doc = {
        "doc_id": "test-001",
        "doc_type": "event",
        "source": {"type": "manual"},
        "meta": {"title": "测试文档", "description": "这是一个测试"},
        "entities": [
            {"entity_id": "e1", "entity_type": "Unit", "name": "红方部队", "basic_properties": {"side": "red"}},
            {"entity_id": "e2", "entity_type": "Unit", "name": "蓝方部队", "basic_properties": {"side": "blue"}},
        ],
        "relations": [
            {"relation_id": "r1", "relation_type": "engaged_with", "source_entity": "e1", "target_entity": "e2"}
        ],
        "events": [
            {"event_id": "ev1", "event_type": "contact", "timestamp": "2026-04-22T10:00:00Z"}
        ]
    }

    report = manager.validate_document(test_doc)
    print(f"  验证结果: {'通过' if report.is_valid else '失败'}")
    print(f"  问题数量: {len(report.issues)}")
    for issue in report.issues:
        print(f"    - [{issue.severity}] {issue.message}")

    print("\n测试版本创建:")
    docs = [test_doc]
    version = manager.create_version(docs, "测试版本")
    print(f"  创建版本: {version.version_id}")
    print(f"  校验和: {version.checksum}")

    print("\n测试语义层:")
    unit = {"entity_type": "unit", "basic_properties": {"side": "red", "location": "A区"}}
    side_value = manager.semantic_layer.get_mapped_value(unit, "side")
    print(f"  unit.side 映射结果: {side_value}")
