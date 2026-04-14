"""
OntologyDocument 标准化数据模型
实现 ADR-032 定义的统一本体文档格式

格式规范:
- 实体四层属性: basic_properties / statistical_properties / capabilities / constraints
- 关系时序标注: temporal.start_time / is_current
- 事件序列: timestamp 排序 + outcome
- 行动/规则/约束: Palantir AIP 四层本体结构
- 版本链: v{YYYYMMDD}-{seq:03d} + parent_version 指针
"""

import uuid
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger("ontology_document")

SCHEMA_URL = "https://odap.local/schemas/ontology-document/v1.json"
SCHEMA_VERSION = "1.0.0"


# ─────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────

class DocType(str, Enum):
    EVENT = "event"
    ENTITY = "entity"
    SCENARIO = "scenario"
    BATCH = "batch"


class SourceType(str, Enum):
    NEWS_INGEST = "news_ingest"
    MANUAL = "manual"
    RANDOM_GEN = "random_gen"
    IMPORT = "import"
    SIMULATION = "simulation"


class EntityType(str, Enum):
    UNIT = "Unit"
    EQUIPMENT = "Equipment"
    LOCATION = "Location"
    PERSON = "Person"
    ORGANIZATION = "Organization"
    EVENT_NODE = "EventNode"


class ActionStatus(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    FAILED = "failed"


# ─────────────────────────────────────────────────
# Sub-dataclasses
# ─────────────────────────────────────────────────

@dataclass
class DataSource:
    type: str = SourceType.MANUAL.value
    url: Optional[str] = None
    collected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence: float = 1.0
    author: Optional[str] = None


@dataclass
class DocumentMeta:
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    language: str = "zh"
    classification: str = "SIM"


@dataclass
class TemporalInfo:
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_current: bool = True


@dataclass
class OntologyEntity:
    entity_id: str = field(default_factory=lambda: f"entity-{uuid.uuid4().hex[:8]}")
    entity_type: str = EntityType.UNIT.value
    name: str = ""
    name_en: str = ""
    basic_properties: Dict[str, Any] = field(default_factory=dict)
    statistical_properties: Dict[str, Any] = field(default_factory=dict)
    capabilities: Dict[str, Any] = field(default_factory=dict)
    constraints: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OntologyRelation:
    relation_id: str = field(default_factory=lambda: f"rel-{uuid.uuid4().hex[:8]}")
    relation_type: str = "related_to"
    source_entity: str = ""
    target_entity: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    temporal: TemporalInfo = field(default_factory=TemporalInfo)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class OntologyEvent:
    event_id: str = field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:8]}")
    event_type: str = "generic"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    location: str = ""
    coordinates: Optional[List[float]] = None
    participants: List[str] = field(default_factory=list)
    description: str = ""
    outcome: Dict[str, Any] = field(default_factory=dict)
    phase: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OntologyAction:
    action_id: str = field(default_factory=lambda: f"act-{uuid.uuid4().hex[:8]}")
    action_type: str = "generic"
    actor: str = ""
    target: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parameters: Dict[str, Any] = field(default_factory=dict)
    opa_required: bool = False
    status: str = ActionStatus.EXECUTED.value

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OntologyRule:
    rule_id: str = field(default_factory=lambda: f"rule-{uuid.uuid4().hex[:8]}")
    rule_type: str = "engagement_rule"
    description: str = ""
    condition: str = ""
    consequence: str = ""
    priority: str = "medium"
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OntologyConstraint:
    constraint_id: str = field(default_factory=lambda: f"cst-{uuid.uuid4().hex[:8]}")
    constraint_type: str = "operational"
    description: str = ""
    scope: Dict[str, Any] = field(default_factory=dict)
    violation_consequence: str = "warning"
    legal_basis: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VersionRef:
    version_id: str = ""
    parent_version: Optional[str] = None
    commit_message: str = ""
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────
# OntologyDocument - 核心数据单元
# ─────────────────────────────────────────────────

@dataclass
class OntologyDocument:
    """
    标准化本体文档（ADR-032）

    每条数据写入的原子单元，承载实体/关系/事件/行动/规则/约束。
    通过 OntologyHotWritePipeline 写入 Graphiti/Neo4j 并广播 Hook。
    """
    # 文档标识
    schema: str = SCHEMA_URL
    version: str = SCHEMA_VERSION
    doc_id: str = field(default_factory=lambda: f"doc-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}")
    doc_type: str = DocType.EVENT.value

    # 元数据
    source: DataSource = field(default_factory=DataSource)
    meta: DocumentMeta = field(default_factory=DocumentMeta)

    # 内容体
    entities: List[OntologyEntity] = field(default_factory=list)
    relations: List[OntologyRelation] = field(default_factory=list)
    events: List[OntologyEvent] = field(default_factory=list)
    actions: List[OntologyAction] = field(default_factory=list)
    rules: List[OntologyRule] = field(default_factory=list)
    constraints: List[OntologyConstraint] = field(default_factory=list)

    # 版本链
    ontology_version: VersionRef = field(default_factory=VersionRef)

    # 内部：场景归属
    scenario_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict，兼容 JSON"""
        return {
            "$schema": self.schema,
            "$version": self.version,
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "source": asdict(self.source),
            "meta": asdict(self.meta),
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "events": [e.to_dict() for e in self.events],
            "actions": [a.to_dict() for a in self.actions],
            "rules": [r.to_dict() for r in self.rules],
            "constraints": [c.to_dict() for c in self.constraints],
            "ontology_version": self.ontology_version.to_dict(),
            "scenario_id": self.scenario_id,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)

    def to_episode_text(self) -> str:
        """
        转换为 Graphiti Episode 文本（人机可读摘要）
        写入 Graphiti 时的 content 字段
        """
        lines = [
            f"[OntologyDocument] {self.meta.title}",
            f"类型: {self.doc_type} | 来源: {self.source.type} | 版本: {self.ontology_version.version_id}",
            f"描述: {self.meta.description}",
            "",
        ]
        if self.entities:
            lines.append(f"实体 ({len(self.entities)}):")
            for e in self.entities:
                side = e.basic_properties.get("side", "")
                status = e.basic_properties.get("status", "")
                loc = e.basic_properties.get("location", "")
                lines.append(f"  - {e.name} [{e.entity_type}] 归属:{side} 状态:{status} 位置:{loc}")
        if self.relations:
            lines.append(f"关系 ({len(self.relations)}):")
            for r in self.relations:
                lines.append(f"  - {r.source_entity} --[{r.relation_type}]--> {r.target_entity}")
        if self.events:
            lines.append(f"事件 ({len(self.events)}):")
            for ev in sorted(self.events, key=lambda x: x.timestamp):
                lines.append(f"  - [{ev.timestamp}] {ev.event_type}: {ev.description}")
        if self.actions:
            lines.append(f"行动 ({len(self.actions)}):")
            for a in self.actions:
                lines.append(f"  - {a.actor} 执行 {a.action_type} → {a.target}")
        if self.rules:
            lines.append(f"规则 ({len(self.rules)}):")
            for r in self.rules:
                lines.append(f"  - [{r.rule_type}] {r.description}")
        if self.constraints:
            lines.append(f"约束 ({len(self.constraints)}):")
            for c in self.constraints:
                lines.append(f"  - [{c.constraint_type}] {c.description}")
        return "\n".join(lines)

    def extract_relations(self) -> List[Dict[str, Any]]:
        """提取实体关系边，用于 Graphiti entity edges"""
        edges = []
        for rel in self.relations:
            edges.append({
                "source": rel.source_entity,
                "target": rel.target_entity,
                "type": rel.relation_type,
                "properties": rel.properties,
                "temporal": asdict(rel.temporal),
            })
        return edges

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OntologyDocument':
        """从 dict 反序列化"""
        source_data = data.get("source", {})
        meta_data = data.get("meta", {})
        version_data = data.get("ontology_version", {})

        doc = cls(
            schema=data.get("$schema", SCHEMA_URL),
            version=data.get("$version", SCHEMA_VERSION),
            doc_id=data.get("doc_id", f"doc-{uuid.uuid4().hex[:8]}"),
            doc_type=data.get("doc_type", DocType.EVENT.value),
            source=DataSource(**{k: v for k, v in source_data.items() if k in DataSource.__dataclass_fields__}),
            meta=DocumentMeta(**{k: v for k, v in meta_data.items() if k in DocumentMeta.__dataclass_fields__}),
            scenario_id=data.get("scenario_id"),
        )

        # 实体
        for e in data.get("entities", []):
            doc.entities.append(OntologyEntity(**{
                k: v for k, v in e.items() if k in OntologyEntity.__dataclass_fields__
            }))

        # 关系
        for r in data.get("relations", []):
            temporal_data = r.pop("temporal", {}) if isinstance(r, dict) else {}
            r_copy = {k: v for k, v in r.items() if k in OntologyRelation.__dataclass_fields__ and k != "temporal"}
            rel = OntologyRelation(**r_copy)
            if temporal_data:
                rel.temporal = TemporalInfo(**{k: v for k, v in temporal_data.items() if k in TemporalInfo.__dataclass_fields__})
            doc.relations.append(rel)

        # 事件
        for e in data.get("events", []):
            doc.events.append(OntologyEvent(**{
                k: v for k, v in e.items() if k in OntologyEvent.__dataclass_fields__
            }))

        # 行动
        for a in data.get("actions", []):
            doc.actions.append(OntologyAction(**{
                k: v for k, v in a.items() if k in OntologyAction.__dataclass_fields__
            }))

        # 规则
        for r in data.get("rules", []):
            doc.rules.append(OntologyRule(**{
                k: v for k, v in r.items() if k in OntologyRule.__dataclass_fields__
            }))

        # 约束
        for c in data.get("constraints", []):
            doc.constraints.append(OntologyConstraint(**{
                k: v for k, v in c.items() if k in OntologyConstraint.__dataclass_fields__
            }))

        # 版本
        if version_data:
            doc.ontology_version = VersionRef(**{
                k: v for k, v in version_data.items() if k in VersionRef.__dataclass_fields__
            })

        return doc

    @classmethod
    def from_json(cls, json_str: str) -> 'OntologyDocument':
        return cls.from_dict(json.loads(json_str))


# ─────────────────────────────────────────────────
# Schema 验证器
# ─────────────────────────────────────────────────

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class OntologyDocumentSchema:
    """OntologyDocument Schema 验证器"""

    REQUIRED_FIELDS = ["doc_id", "doc_type", "source", "meta", "entities", "relations", "events"]
    VALID_DOC_TYPES = [t.value for t in DocType]
    VALID_SOURCE_TYPES = [t.value for t in SourceType]
    VALID_ENTITY_TYPES = [t.value for t in EntityType]

    @classmethod
    def validate(cls, doc) -> ValidationResult:
        """验证 OntologyDocument（接受 OntologyDocument 实例或 dict）"""
        errors = []
        warnings = []

        if isinstance(doc, dict):
            return cls._validate_dict(doc)

        # 实例验证
        if not doc.doc_id:
            errors.append("doc_id 不能为空")
        if doc.doc_type not in cls.VALID_DOC_TYPES:
            errors.append(f"无效的 doc_type: {doc.doc_type}，合法值: {cls.VALID_DOC_TYPES}")
        if not doc.meta.title and not doc.meta.description:
            warnings.append("建议填写 meta.title 或 meta.description")

        # 实体验证
        entity_ids = set()
        for i, entity in enumerate(doc.entities):
            if not entity.entity_id:
                errors.append(f"entities[{i}].entity_id 不能为空")
            elif entity.entity_id in entity_ids:
                errors.append(f"实体 ID 重复: {entity.entity_id}")
            else:
                entity_ids.add(entity.entity_id)
            if not entity.name:
                warnings.append(f"entities[{i}] 缺少 name")

        # 关系验证
        for i, rel in enumerate(doc.relations):
            if rel.source_entity and rel.source_entity not in entity_ids:
                warnings.append(f"relations[{i}].source_entity '{rel.source_entity}' 未在实体列表中")
            if rel.target_entity and rel.target_entity not in entity_ids:
                warnings.append(f"relations[{i}].target_entity '{rel.target_entity}' 未在实体列表中")

        # 事件验证
        for i, event in enumerate(doc.events):
            if not event.event_id:
                errors.append(f"events[{i}].event_id 不能为空")
            if not event.timestamp:
                warnings.append(f"events[{i}] 缺少 timestamp")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    @classmethod
    def _validate_dict(cls, data: dict) -> ValidationResult:
        """验证 dict 格式"""
        errors = []
        warnings = []

        required = ["doc_id", "doc_type"]
        for field_name in required:
            if field_name not in data or not data[field_name]:
                errors.append(f"缺少必填字段: {field_name}")

        if "doc_type" in data and data["doc_type"] not in cls.VALID_DOC_TYPES:
            errors.append(f"无效的 doc_type: {data['doc_type']}")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


class OntologyValidationError(Exception):
    """本体验证失败异常"""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"OntologyDocument 验证失败: {'; '.join(errors)}")


# ─────────────────────────────────────────────────
# 工厂函数 — 快速创建示例文档
# ─────────────────────────────────────────────────

def make_battle_event_document(
    title: str,
    red_unit: str,
    blue_unit: str,
    location: str,
    event_type: str = "contact",
    source_type: str = SourceType.RANDOM_GEN.value,
    scenario_id: Optional[str] = None,
) -> OntologyDocument:
    """快速创建一个战斗事件 OntologyDocument"""
    now = datetime.now(timezone.utc).isoformat()
    date_str = datetime.now().strftime("%Y%m%d")

    red_id = f"unit-red-{uuid.uuid4().hex[:6]}"
    blue_id = f"unit-blue-{uuid.uuid4().hex[:6]}"
    rel_id = f"rel-{uuid.uuid4().hex[:6]}"
    evt_id = f"evt-{uuid.uuid4().hex[:6]}"
    doc_id = f"evt-{date_str}-{uuid.uuid4().hex[:6]}"
    ver_id = f"v{date_str}-{uuid.uuid4().hex[:4]}"

    doc = OntologyDocument(
        doc_id=doc_id,
        doc_type=DocType.EVENT.value,
        source=DataSource(type=source_type, collected_at=now, confidence=0.9),
        meta=DocumentMeta(
            title=title,
            description=f"{red_unit} 与 {blue_unit} 在 {location} 发生 {event_type}",
            tags=["战斗", event_type, location],
        ),
        entities=[
            OntologyEntity(
                entity_id=red_id,
                entity_type=EntityType.UNIT.value,
                name=red_unit,
                name_en=red_unit,
                basic_properties={"side": "red", "location": location, "status": "engaged"},
                statistical_properties={"combat_power": 0.75, "morale": 0.80, "supply_level": 0.65},
                capabilities={"fire_range_km": 8, "armor_penetration": "high", "air_defense": False},
            ),
            OntologyEntity(
                entity_id=blue_id,
                entity_type=EntityType.UNIT.value,
                name=blue_unit,
                name_en=blue_unit,
                basic_properties={"side": "blue", "location": location, "status": "engaged"},
                statistical_properties={"combat_power": 0.65, "morale": 0.72, "supply_level": 0.80},
                capabilities={"fire_range_km": 3, "armor_penetration": "medium", "air_defense": True},
            ),
        ],
        relations=[
            OntologyRelation(
                relation_id=rel_id,
                relation_type="engaged_with",
                source_entity=red_id,
                target_entity=blue_id,
                properties={"engagement_type": "direct_fire", "initiated_by": "red"},
                temporal=TemporalInfo(start_time=now, is_current=True),
            )
        ],
        events=[
            OntologyEvent(
                event_id=evt_id,
                event_type=event_type,
                timestamp=now,
                location=location,
                participants=[red_id, blue_id],
                description=f"{red_unit} 与 {blue_unit} 在 {location} 发生 {event_type}",
            )
        ],
        ontology_version=VersionRef(
            version_id=ver_id,
            commit_message=title,
        ),
        scenario_id=scenario_id,
    )
    return doc
