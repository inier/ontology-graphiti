"""
OntologyVersionManager — 本体版本管理器
实现 ADR-032 版本链机制

版本ID格式: v{YYYYMMDD}-{seq:03d}
版本链: 单向链表（parent_version 指针）
存储: 本地 JSON 快照 + 内存缓存
"""

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any

from odap.biz.ontology.schema.document import OntologyDocument

logger = logging.getLogger("ontology_version_manager")


@dataclass
class OntologyVersion:
    """本体版本快照"""
    version_id: str
    doc_id: str
    doc_type: str
    parent_version: Optional[str]
    commit_message: str
    created_at: str
    entity_count: int = 0
    relation_count: int = 0
    event_count: int = 0
    # 文档内容序列化（JSON字符串，可选存储）
    doc_snapshot: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("doc_snapshot", None)  # 摘要中不包含全量快照
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


class OntologyVersionManager:
    """
    本体版本管理器

    负责:
    1. 为每条 OntologyDocument 生成唯一版本ID
    2. 维护版本链（parent_version 指针）
    3. 本地 JSON 快照存储
    4. 版本差异对比
    5. 实体历史追踪
    """

    _instance: Optional['OntologyVersionManager'] = None

    def __init__(self, storage_path: str = "/tmp/ontology_versions"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        # 内存缓存: version_id -> OntologyVersion
        self._versions: Dict[str, OntologyVersion] = {}
        # 实体历史: entity_id -> List[EntitySnapshot]
        self._entity_history: Dict[str, List[EntitySnapshot]] = {}
        # 日序号计数: date_str -> counter
        self._daily_counters: Dict[str, int] = {}
        # 加载历史版本
        self._load_from_disk()

    @classmethod
    def get_instance(cls, storage_path: str = "/tmp/ontology_versions") -> 'OntologyVersionManager':
        if cls._instance is None:
            cls._instance = OntologyVersionManager(storage_path)
        return cls._instance

    def _generate_version_id(self) -> str:
        """生成版本ID: v{YYYYMMDD}-{seq:03d}"""
        date_str = datetime.now().strftime("%Y%m%d")
        count = self._daily_counters.get(date_str, 0) + 1
        self._daily_counters[date_str] = count
        return f"v{date_str}-{count:03d}"

    def _load_from_disk(self):
        """从磁盘加载历史版本索引"""
        index_file = os.path.join(self.storage_path, "version_index.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    index = json.load(f)
                for v in index.get("versions", []):
                    ver = OntologyVersion(**v)
                    self._versions[ver.version_id] = ver
                # 重建日序号
                for ver_id in self._versions:
                    # 格式: v20260414-001
                    parts = ver_id.split("-")
                    if len(parts) == 2:
                        date_str = parts[0][1:]  # 去掉v
                        seq = int(parts[1])
                        if date_str not in self._daily_counters:
                            self._daily_counters[date_str] = 0
                        self._daily_counters[date_str] = max(
                            self._daily_counters[date_str], seq
                        )
                logger.info(f"加载 {len(self._versions)} 条历史版本")
            except Exception as e:
                logger.warning(f"加载版本索引失败: {e}")

    def _save_index(self):
        """保存版本索引到磁盘"""
        index_file = os.path.join(self.storage_path, "version_index.json")
        versions_list = [v.to_dict() for v in self._versions.values()]
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump({"versions": versions_list}, f, ensure_ascii=False, indent=2, default=str)

    async def commit(
        self,
        doc: OntologyDocument,
        parent_version: Optional[str] = None,
        message: str = "",
    ) -> OntologyVersion:
        """
        提交版本快照

        Args:
            doc: 要版本化的 OntologyDocument
            parent_version: 父版本ID（可选，默认从 doc.ontology_version.parent_version 获取）
            message: 提交信息

        Returns:
            OntologyVersion: 创建的版本对象
        """
        version_id = self._generate_version_id()

        # 优先用参数传入的 parent_version，其次用文档自带的
        parent = parent_version or doc.ontology_version.parent_version

        commit_msg = message or doc.ontology_version.commit_message or f"写入 {doc.doc_type}: {doc.meta.title}"

        version = OntologyVersion(
            version_id=version_id,
            doc_id=doc.doc_id,
            doc_type=doc.doc_type,
            parent_version=parent,
            commit_message=commit_msg,
            created_at=datetime.now().isoformat(),
            entity_count=len(doc.entities),
            relation_count=len(doc.relations),
            event_count=len(doc.events),
            doc_snapshot=doc.to_json(),
        )

        # 内存缓存
        self._versions[version_id] = version

        # 更新文档的 version_id
        doc.ontology_version.version_id = version_id
        doc.ontology_version.parent_version = parent
        doc.ontology_version.commit_message = commit_msg

        # 磁盘存储
        snapshot_file = os.path.join(self.storage_path, f"{version_id}.json")
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump({
                "version": version.to_dict(),
                "doc": doc.to_dict(),
            }, f, ensure_ascii=False, indent=2, default=str)

        self._save_index()

        # 更新实体历史
        for entity in doc.entities:
            if entity.entity_id not in self._entity_history:
                self._entity_history[entity.entity_id] = []
            self._entity_history[entity.entity_id].append(EntitySnapshot(
                entity_id=entity.entity_id,
                version_id=version_id,
                timestamp=version.created_at,
                state=entity.to_dict(),
            ))

        logger.info(f"版本提交: {version_id} ← {parent} | {commit_msg}")
        return version

    async def get(self, version_id: str) -> Optional[OntologyVersion]:
        """获取指定版本"""
        if version_id in self._versions:
            return self._versions[version_id]

        # 尝试从磁盘加载
        snapshot_file = os.path.join(self.storage_path, f"{version_id}.json")
        if os.path.exists(snapshot_file):
            with open(snapshot_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            ver_data = data.get("version", {})
            ver = OntologyVersion(**ver_data)
            # 恢复 doc_snapshot
            ver.doc_snapshot = json.dumps(data.get("doc", {}), ensure_ascii=False)
            self._versions[version_id] = ver
            return ver

        return None

    async def list(self, limit: int = 50, offset: int = 0) -> List[OntologyVersion]:
        """列出所有版本（倒序）"""
        versions = sorted(
            self._versions.values(),
            key=lambda v: v.created_at,
            reverse=True
        )
        return versions[offset:offset + limit]

    async def get_doc(self, version_id: str) -> Optional[OntologyDocument]:
        """获取版本对应的 OntologyDocument"""
        version = await self.get(version_id)
        if version and version.doc_snapshot:
            return OntologyDocument.from_json(version.doc_snapshot)
        # 尝试从磁盘加载
        snapshot_file = os.path.join(self.storage_path, f"{version_id}.json")
        if os.path.exists(snapshot_file):
            with open(snapshot_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            doc_data = data.get("doc", {})
            if doc_data:
                return OntologyDocument.from_dict(doc_data)
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
        return len(self._versions)

    def get_latest_version_id(self) -> Optional[str]:
        """获取最新版本ID"""
        if not self._versions:
            return None
        return max(self._versions.values(), key=lambda v: v.created_at).version_id
