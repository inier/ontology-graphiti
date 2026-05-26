"""
OntologyVersionManager — 本体版本管理器
实现 ADR-032 版本链机制

两种操作模式:
  append()  — 数据追加到当前版本，版本ID不变（热写入自动触发）
  commit()  — 锁定当前版本 + 创建新版本（用户手动触发）

版本ID:   v{YYYYMMDD}-{seq:03d}  机器标识，全局唯一
版本号:   {major}.{minor}.{patch} 语义版本，人类可读
版本链:   单向链表（parent_version_id 指针）
存储:     SQLite (统一单源)
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any

from odap.biz.core.ontology.schema.document import OntologyDocument
from odap.biz.core.ontology.storage.sqlite_ingest_storage import SQLiteIngestStorage
from odap.biz.core.ontology.entity_resolver import EntityResolver

logger = logging.getLogger("ontology_version_manager")


@dataclass
class OntologyVersion:
    """本体版本快照"""
    version_id: str
    ontology_id: str
    version_number: str
    doc_id: str
    doc_type: str
    parent_version: Optional[str]
    commit_message: str
    created_at: str
    is_current: bool = False
    is_stable: bool = False
    entity_count: int = 0
    relation_count: int = 0
    event_count: int = 0
    doc_snapshot: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("doc_snapshot", None)
        return d


@dataclass
class OntologyDiff:
    """版本差异"""
    version_a: str
    version_b: str
    added_entities: List[str] = field(default_factory=list)
    removed_entities: List[str] = field(default_factory=list)
    added_relations: List[str] = field(default_factory=list)
    removed_relations: List[str] = field(default_factory=list)
    added_events: List[str] = field(default_factory=list)
    removed_events: List[str] = field(default_factory=list)


@dataclass
class EntitySnapshot:
    """实体历史快照"""
    entity_id: str
    version_id: str
    timestamp: str
    state: Dict[str, Any]


def _bump_version(version_number: str) -> str:
    """递增语义版本号 minor: 1.0.0 → 1.1.0"""
    try:
        parts = version_number.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        return f"{major}.{minor + 1}.0"
    except (ValueError, IndexError):
        return "1.0.0"


class OntologyVersionManager:
    """
    本体版本管理器

    两种操作:
    1. append() — 数据追加到当前版本，版本ID不变（热写入自动触发）
    2. commit() — 锁定当前版本 + 创建新版本（用户手动触发）

    版本号规则:
    - 初始版本: 1.0.0
    - 每次 commit: minor 递增 (1.0.0 → 1.1.0 → 1.2.0)
    - append 不改变版本号
    """

    _instance: Optional['OntologyVersionManager'] = None

    def __init__(self, storage=None):
        if storage is None:
            storage = SQLiteIngestStorage()
        self._storage: SQLiteIngestStorage = storage
        self._resolver: EntityResolver = EntityResolver(storage)
        self._entity_history: Dict[str, List[EntitySnapshot]] = {}

    @classmethod
    def get_instance(cls, storage=None) -> 'OntologyVersionManager':
        if cls._instance is None:
            cls._instance = OntologyVersionManager(storage)
        return cls._instance

    def _generate_version_id(self) -> str:
        """生成版本ID: v{YYYYMMDD}-{seq:03d}"""
        date_str = datetime.now().strftime("%Y%m%d")
        prefix = f"v{date_str}-"
        max_seq = 0
        for v in self._storage.list_all_versions():
            vid = v.get("id", "")
            if vid.startswith(prefix):
                try:
                    seq = int(vid.split("-")[1])
                    max_seq = max(max_seq, seq)
                except (IndexError, ValueError):
                    pass
        return f"v{date_str}-{max_seq + 1:03d}"

    def _sqlite_row_to_version(self, row: Dict[str, Any]) -> OntologyVersion:
        """将 SQLite 行转换为 OntologyVersion"""
        snapshot = row.get("doc_snapshot")
        if snapshot and not isinstance(snapshot, str):
            snapshot = json.dumps(snapshot, ensure_ascii=False)

        return OntologyVersion(
            version_id=row.get("id") or "",
            ontology_id=row.get("ontology_id") or "",
            version_number=row.get("version_number") or "1.0.0",
            doc_id=row.get("doc_id") or "",
            doc_type=row.get("doc_type") or "",
            parent_version=row.get("parent_version_id"),
            commit_message=row.get("change_summary") or "",
            created_at=row.get("created_at") or "",
            is_current=bool(row.get("is_current")),
            is_stable=bool(row.get("is_stable")),
            entity_count=row.get("entity_count") or 0,
            relation_count=row.get("relation_count") or 0,
            event_count=row.get("event_count") or 0,
            doc_snapshot=snapshot,
        )

    async def append(
        self,
        ontology_id: str,
        doc: OntologyDocument,
        message: str = "",
    ) -> OntologyVersion:
        """
        追加数据到当前版本（版本ID不变，内容更新）

        热写入自动触发: 每次数据输入都追加到当前版本快照，
        版本号和版本ID保持不变，直到用户手动 commit。

        如果当前没有版本，自动创建初始版本。
        """
        current = self._storage.get_current_version(ontology_id)

        if current is None:
            return await self._create_initial_version(ontology_id, doc, message)

        doc = self._resolver.resolve(doc, ontology_id)

        commit_msg = message or f"追加 {doc.doc_type}: {doc.meta.title}"

        existing_snapshot = current.get("doc_snapshot")
        merged_doc = self._merge_doc_into_snapshot(existing_snapshot, doc)

        self._storage.append_version_snapshot(ontology_id, {
            'doc_snapshot': merged_doc.to_dict(),
            'doc_id': merged_doc.doc_id,
            'doc_type': merged_doc.doc_type,
            'entity_count': len(merged_doc.entities),
            'relation_count': len(merged_doc.relations),
            'event_count': len(merged_doc.events),
            'change_summary': commit_msg,
            'status': 'draft',
        })

        now = datetime.now().isoformat()
        for entity in doc.entities:
            if entity.entity_id not in self._entity_history:
                self._entity_history[entity.entity_id] = []
            self._entity_history[entity.entity_id].append(EntitySnapshot(
                entity_id=entity.entity_id,
                version_id=current.get("id", ""),
                timestamp=now,
                state=entity.to_dict(),
            ))

        refreshed = self._storage.get_current_version(ontology_id)
        version = self._sqlite_row_to_version(refreshed) if refreshed else self._sqlite_row_to_version(current)

        logger.info(f"版本追加: {version.version_id} ({version.version_number}) | {commit_msg}")
        return version

    async def commit(
        self,
        ontology_id: str,
        message: str = "",
    ) -> OntologyVersion:
        """
        锁定当前版本 + 创建新版本（用户手动触发）

        流程:
        1. 获取当前版本，标记为 is_stable=True (锁定)
        2. 创建新版本，version_number 递增
        3. 新版本继承旧版本的 doc_snapshot 作为起点
        4. 新版本设为 is_current=True
        """
        current = self._storage.get_current_version(ontology_id)

        if current is None:
            return await self._create_initial_version(ontology_id, None, message or "初始版本")

        current_version_id = current.get("id", "")
        current_version_number = current.get("version_number", "1.0.0")
        current_snapshot = current.get("doc_snapshot")

        self._storage.lock_version(current_version_id)

        new_version_id = self._generate_version_id()
        new_version_number = _bump_version(current_version_number)
        now = datetime.now().isoformat()
        commit_msg = message or f"版本提交: {current_version_number} → {new_version_number}"

        new_version_data = {
            'id': new_version_id,
            'ontology_id': ontology_id,
            'version_number': new_version_number,
            'parent_version_id': current_version_id,
            'status': 'draft',
            'changes': None,
            'change_summary': commit_msg,
            'created_at': now,
            'created_by': 'system',
            'is_current': True,
            'is_stable': False,
            'doc_snapshot': current_snapshot,
            'doc_id': current.get("doc_id"),
            'doc_type': current.get("doc_type"),
            'entity_count': current.get("entity_count", 0),
            'relation_count': current.get("relation_count", 0),
            'event_count': current.get("event_count", 0),
        }

        self._storage.set_current_version(ontology_id, new_version_id)
        self._storage.save_version(new_version_data)

        version = OntologyVersion(
            version_id=new_version_id,
            ontology_id=ontology_id,
            version_number=new_version_number,
            doc_id=current.get("doc_id") or "",
            doc_type=current.get("doc_type") or "",
            parent_version=current_version_id,
            commit_message=commit_msg,
            created_at=now,
            is_current=True,
            is_stable=False,
            entity_count=current.get("entity_count", 0),
            relation_count=current.get("relation_count", 0),
            event_count=current.get("event_count", 0),
            doc_snapshot=current_snapshot,
        )

        logger.info(f"版本提交: {current_version_id} ({current_version_number}) → {new_version_id} ({new_version_number})")
        return version

    async def _create_initial_version(
        self,
        ontology_id: str,
        doc: Optional[OntologyDocument],
        message: str = "",
    ) -> OntologyVersion:
        """创建初始版本"""
        version_id = self._generate_version_id()
        now = datetime.now().isoformat()
        commit_msg = message or "初始版本"

        doc_snapshot_dict = doc.to_dict() if doc else None
        doc_snapshot_json = json.dumps(doc_snapshot_dict, ensure_ascii=False, default=str) if doc_snapshot_dict else None

        version_data = {
            'id': version_id,
            'ontology_id': ontology_id,
            'version_number': '1.0.0',
            'parent_version_id': None,
            'status': 'draft',
            'changes': None,
            'change_summary': commit_msg,
            'created_at': now,
            'created_by': 'system',
            'is_current': True,
            'is_stable': False,
            'doc_snapshot': doc_snapshot_json,
            'doc_id': doc.doc_id if doc else None,
            'doc_type': doc.doc_type if doc else None,
            'entity_count': len(doc.entities) if doc else 0,
            'relation_count': len(doc.relations) if doc else 0,
            'event_count': len(doc.events) if doc else 0,
        }
        self._storage.save_version(version_data)

        return OntologyVersion(
            version_id=version_id,
            ontology_id=ontology_id,
            version_number='1.0.0',
            doc_id=doc.doc_id if doc else "",
            doc_type=doc.doc_type if doc else "",
            parent_version=None,
            commit_message=commit_msg,
            created_at=now,
            is_current=True,
            is_stable=False,
            entity_count=len(doc.entities) if doc else 0,
            relation_count=len(doc.relations) if doc else 0,
            event_count=len(doc.events) if doc else 0,
        )

    def _merge_doc_into_snapshot(
        self,
        existing_snapshot: Any,
        new_doc: OntologyDocument,
    ) -> OntologyDocument:
        """将新文档数据合并到已有快照中（追加+属性合并模式）"""
        if existing_snapshot is None:
            return new_doc

        try:
            if isinstance(existing_snapshot, str):
                existing_doc = OntologyDocument.from_json(existing_snapshot)
            elif isinstance(existing_snapshot, dict):
                existing_doc = OntologyDocument.from_dict(existing_snapshot)
            else:
                return new_doc
        except Exception:
            return new_doc

        existing_entity_map = {e.entity_id: e for e in existing_doc.entities}
        for entity in new_doc.entities:
            if entity.entity_id in existing_entity_map:
                existing = existing_entity_map[entity.entity_id]
                existing.basic_properties = {**existing.basic_properties, **entity.basic_properties}
                existing.statistical_properties = {**existing.statistical_properties, **entity.statistical_properties}
                existing.capabilities = {**existing.capabilities, **entity.capabilities}
                existing.aliases = list(set(existing.aliases + entity.aliases))
                if entity.name_en and not existing.name_en:
                    existing.name_en = entity.name_en
            else:
                existing_doc.entities.append(entity)
                existing_entity_map[entity.entity_id] = entity

        existing_rel_ids = {r.relation_id for r in existing_doc.relations}
        for relation in new_doc.relations:
            if relation.relation_id not in existing_rel_ids:
                existing_doc.relations.append(relation)

        existing_evt_ids = {e.event_id for e in existing_doc.events}
        for event in new_doc.events:
            if event.event_id not in existing_evt_ids:
                existing_doc.events.append(event)

        return existing_doc

    async def get(self, version_id: str) -> Optional[OntologyVersion]:
        """获取指定版本"""
        row = self._storage.get_version(version_id)
        if row is None:
            return None
        return self._sqlite_row_to_version(row)

    async def list(self, limit: int = 50, offset: int = 0) -> List[OntologyVersion]:
        """列出所有版本（倒序）"""
        rows = self._storage.list_all_versions()
        versions = [self._sqlite_row_to_version(r) for r in rows]
        return versions[offset:offset + limit]

    async def get_doc(self, version_id: str) -> Optional[OntologyDocument]:
        """获取版本对应的 OntologyDocument"""
        row = self._storage.get_version(version_id)
        if row is None:
            return None

        doc_snapshot = row.get("doc_snapshot")
        if doc_snapshot:
            if isinstance(doc_snapshot, str):
                return OntologyDocument.from_json(doc_snapshot)
            elif isinstance(doc_snapshot, dict):
                return OntologyDocument.from_dict(doc_snapshot)
        return None

    async def diff(self, version_a: str, version_b: str) -> OntologyDiff:
        """对比两版本的差异"""
        doc_a = await self.get_doc(version_a)
        doc_b = await self.get_doc(version_b)

        d = OntologyDiff(version_a=version_a, version_b=version_b)

        if doc_a and doc_b:
            entities_a = {e.entity_id for e in doc_a.entities}
            entities_b = {e.entity_id for e in doc_b.entities}
            d.added_entities = list(entities_b - entities_a)
            d.removed_entities = list(entities_a - entities_b)

            rels_a = {r.relation_id for r in doc_a.relations}
            rels_b = {r.relation_id for r in doc_b.relations}
            d.added_relations = list(rels_b - rels_a)
            d.removed_relations = list(rels_a - rels_b)

            evts_a = {e.event_id for e in doc_a.events}
            evts_b = {e.event_id for e in doc_b.events}
            d.added_events = list(evts_b - evts_a)
            d.removed_events = list(evts_a - evts_b)

        return d

    async def get_entity_history(self, entity_id: str) -> List[EntitySnapshot]:
        """获取实体跨版本历史变化"""
        return self._entity_history.get(entity_id, [])

    def get_version_count(self) -> int:
        return len(self._storage.list_all_versions())

    async def list_by_ontology(self, ontology_id: str, limit: int = 50, offset: int = 0) -> List[OntologyVersion]:
        """列出指定本体的所有版本（倒序）"""
        rows = self._storage.get_versions(ontology_id)
        versions = [self._sqlite_row_to_version(r) for r in rows]
        return versions[offset:offset + limit]

    def get_latest_version_id(self) -> Optional[str]:
        """获取最新版本ID"""
        rows = self._storage.list_all_versions()
        if not rows:
            return None
        return rows[0].get("id")

    def get_latest_version_id_by_ontology(self, ontology_id: str) -> Optional[str]:
        """获取指定本体的最新版本ID"""
        rows = self._storage.get_versions(ontology_id)
        if not rows:
            return None
        return rows[0].get("id")

    def ensure_initial_version(self, ontology_id: str, scenario_name: str = "") -> OntologyVersion:
        """确保本体有初始版本，如果不存在则创建"""
        existing = self._storage.get_versions(ontology_id)
        if existing:
            return self._sqlite_row_to_version(existing[0])

        version_id = self._generate_version_id()
        now = datetime.now().isoformat()
        commit_msg = f'初始版本 - {scenario_name}' if scenario_name else '初始版本'

        version_data = {
            'id': version_id,
            'ontology_id': ontology_id,
            'version_number': '1.0.0',
            'parent_version_id': None,
            'status': 'draft',
            'changes': None,
            'change_summary': commit_msg,
            'created_at': now,
            'created_by': 'system',
            'is_current': True,
            'is_stable': False,
            'doc_snapshot': None,
            'doc_id': None,
            'doc_type': None,
            'entity_count': 0,
            'relation_count': 0,
            'event_count': 0,
        }
        self._storage.save_version(version_data)

        return OntologyVersion(
            version_id=version_id,
            ontology_id=ontology_id,
            version_number='1.0.0',
            doc_id="",
            doc_type="",
            parent_version=None,
            commit_message=commit_msg,
            created_at=now,
            is_current=True,
            is_stable=False,
            entity_count=0,
            relation_count=0,
            event_count=0,
        )
