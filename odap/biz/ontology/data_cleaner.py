"""
DataCleaner — 历史数据冲突扫描与修复工具

扫描所有版本快照中的实体，找出同名同类型但不同 entity_id 的冲突，
统一替换为确定性 ID 并合并属性，重建实体注册表。

使用场景:
  - 服务升级后，清理旧数据中的随机 entity_id
  - 定期维护，确保数据一致性
  - 手动触发修复
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

from odap.biz.ontology.schema.document import OntologyDocument, deterministic_entity_id
from odap.biz.ontology.storage.sqlite_ingest_storage import SQLiteIngestStorage

logger = logging.getLogger("data_cleaner")


class DataCleaner:
    """
    历史数据冲突扫描与修复

    扫描流程:
    1. 遍历所有 ontology_versions 的 doc_snapshot
    2. 收集所有实体，按 (entity_type, name) 分组
    3. 找出同组内有多个不同 entity_id 的冲突
    4. 统一替换为确定性 ID，合并属性
    5. 更新版本快照和实体注册表
    """

    def __init__(self, storage=None):
        if storage is None:
            storage = SQLiteIngestStorage()
        self._storage: SQLiteIngestStorage = storage

    def scan(self) -> Dict[str, Any]:
        """
        扫描所有版本快照，找出实体冲突

        Returns:
            {
                "total_versions": int,
                "total_entities": int,
                "conflicts": [
                    {
                        "entity_type": "Location",
                        "name": "C区",
                        "duplicate_ids": ["entity-abc123", "entity-def456"],
                        "canonical_id": "entity-loc-a3f2b1c4",
                        "affected_versions": ["v20260517-001", ...]
                    },
                    ...
                ],
                "conflict_count": int
            }
        """
        versions = self._storage.list_all_versions()
        entity_groups: Dict[Tuple[str, str], Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

        for v in versions:
            vid = v.get("id", "")
            snapshot = v.get("doc_snapshot")
            if not snapshot:
                continue

            doc = self._parse_snapshot(snapshot)
            if doc is None:
                continue

            for entity_data in doc.get("entities", []):
                etype = entity_data.get("entity_type", "")
                name = entity_data.get("name", "")
                eid = entity_data.get("entity_id", "")
                if etype and name and eid:
                    key = (etype, name)
                    entity_groups[key][eid].append(vid)

        total_entities = sum(len(ids) for ids in entity_groups.values())

        conflicts = []
        for (etype, name), id_map in entity_groups.items():
            if len(id_map) > 1:
                canonical = deterministic_entity_id(etype, name)
                all_versions = set()
                for vids in id_map.values():
                    all_versions.update(vids)
                conflicts.append({
                    "entity_type": etype,
                    "name": name,
                    "duplicate_ids": list(id_map.keys()),
                    "canonical_id": canonical,
                    "affected_versions": sorted(all_versions),
                })

        return {
            "total_versions": len(versions),
            "total_entities": total_entities,
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
        }

    def repair(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        修复所有冲突实体

        对每个冲突:
        1. 计算确定性 canonical_id
        2. 遍历所有版本快照，替换冲突 entity_id
        3. 合并同名实体的属性
        4. 重建实体注册表

        Args:
            dry_run: True=只报告不修改，False=实际修改

        Returns:
            修复报告
        """
        scan_result = self.scan()
        conflicts = scan_result["conflicts"]

        if not conflicts:
            return {
                "status": "clean",
                "message": "没有发现冲突",
                "conflict_count": 0,
                "repaired": 0,
            }

        if dry_run:
            return {
                "status": "dry_run",
                "message": f"发现 {len(conflicts)} 个冲突（dry_run 模式，未修改）",
                "conflict_count": len(conflicts),
                "conflicts": conflicts,
                "repaired": 0,
            }

        id_remap: Dict[str, str] = {}
        for conflict in conflicts:
            canonical = conflict["canonical_id"]
            for old_id in conflict["duplicate_ids"]:
                if old_id != canonical:
                    id_remap[old_id] = canonical

        versions = self._storage.list_all_versions()
        repaired_versions = 0

        for v in versions:
            vid = v.get("id", "")
            snapshot = v.get("doc_snapshot")
            if not snapshot:
                continue

            modified = self._repair_snapshot(vid, snapshot, id_remap)
            if modified:
                repaired_versions += 1

        self._rebuild_registry()

        return {
            "status": "repaired",
            "message": f"修复 {len(id_remap)} 个实体 ID 映射，影响 {repaired_versions} 个版本",
            "conflict_count": len(conflicts),
            "id_remap": id_remap,
            "repaired_versions": repaired_versions,
        }

    def _repair_snapshot(self, version_id: str, snapshot: Any, id_remap: Dict[str, str]) -> bool:
        """修复单个版本快照中的实体 ID"""
        doc = self._parse_snapshot(snapshot)
        if doc is None:
            return False

        modified = False

        entity_map: Dict[str, Dict] = {}
        for entity_data in doc.get("entities", []):
            old_id = entity_data.get("entity_id", "")
            new_id = id_remap.get(old_id, old_id)
            if old_id != new_id:
                entity_data["entity_id"] = new_id
                modified = True

            if new_id in entity_map:
                existing = entity_map[new_id]
                existing["basic_properties"] = {**existing.get("basic_properties", {}), **entity_data.get("basic_properties", {})}
                existing["statistical_properties"] = {**existing.get("statistical_properties", {}), **entity_data.get("statistical_properties", {})}
                existing["capabilities"] = {**existing.get("capabilities", {}), **entity_data.get("capabilities", {})}
                existing_aliases = set(existing.get("aliases", []) + entity_data.get("aliases", []))
                existing["aliases"] = list(existing_aliases)
                entity_data["_merged"] = True
                modified = True
            else:
                entity_map[new_id] = entity_data

        doc["entities"] = [e for e in doc.get("entities", []) if not e.get("_merged")]

        for rel in doc.get("relations", []):
            src = rel.get("source_entity", "")
            tgt = rel.get("target_entity", "")
            if src in id_remap:
                rel["source_entity"] = id_remap[src]
                modified = True
            if tgt in id_remap:
                rel["target_entity"] = id_remap[tgt]
                modified = True

        if modified:
            self._storage.update_version(version_id, {
                "doc_snapshot": doc,
            })

        return modified

    def _rebuild_registry(self):
        """从所有版本快照重建实体注册表"""
        versions = self._storage.list_all_versions()
        seen: Dict[str, Dict] = {}

        for v in versions:
            snapshot = v.get("doc_snapshot")
            if not snapshot:
                continue

            doc = self._parse_snapshot(snapshot)
            if doc is None:
                continue

            ontology_id = v.get("ontology_id", "")

            for entity_data in doc.get("entities", []):
                eid = entity_data.get("entity_id", "")
                etype = entity_data.get("entity_type", "")
                name = entity_data.get("name", "")

                if not eid or not etype or not name:
                    continue

                if eid in seen:
                    existing = seen[eid]
                    existing["basic_properties"] = {**existing.get("basic_properties", {}), **entity_data.get("basic_properties", {})}
                    existing["statistical_properties"] = {**existing.get("statistical_properties", {}), **entity_data.get("statistical_properties", {})}
                    existing["capabilities"] = {**existing.get("capabilities", {}), **entity_data.get("capabilities", {})}
                    existing_aliases = set(existing.get("aliases", []) + entity_data.get("aliases", []))
                    existing["aliases"] = list(existing_aliases)
                    existing["mention_count"] = existing.get("mention_count", 0) + 1
                    existing["last_seen_at"] = v.get("created_at", datetime.now().isoformat())
                else:
                    seen[eid] = {
                        "canonical_id": eid,
                        "entity_type": etype,
                        "name": name,
                        "name_en": entity_data.get("name_en", ""),
                        "aliases": entity_data.get("aliases", []),
                        "ontology_id": ontology_id,
                        "basic_properties": entity_data.get("basic_properties", {}),
                        "statistical_properties": entity_data.get("statistical_properties", {}),
                        "capabilities": entity_data.get("capabilities", {}),
                        "source_doc_id": None,
                        "mention_count": 1,
                        "first_seen_at": v.get("created_at", datetime.now().isoformat()),
                        "last_seen_at": v.get("created_at", datetime.now().isoformat()),
                        "confidence": 1.0,
                    }

        for entity in seen.values():
            self._storage.register_entity(entity)

        logger.info(f"实体注册表重建完成: {len(seen)} 个实体")

    def _parse_snapshot(self, snapshot: Any) -> Optional[Dict[str, Any]]:
        """解析快照为 dict"""
        if isinstance(snapshot, dict):
            return snapshot
        if isinstance(snapshot, str):
            try:
                return json.loads(snapshot)
            except Exception:
                return None
        return None
