"""VersionStorageAdapter — 版本存储统一适配器

解决 OntologyVersionManager (design) 使用 SQLiteIngestStorage
和 OntologyService (ontology_api) 使用 SQLiteOntologyStorage
两个独立存储后端导致的版本数据分裂问题。

适配器策略：
- 写入时双写两个存储后端，确保数据一致性
- 读取时优先查主存储，回退查次存储
- 列表查询合并两个来源并去重
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VersionStorageAdapter:
    """版本存储统一适配器

    将 SQLiteIngestStorage (design 模块) 和 SQLiteOntologyStorage (ontology_api 模块)
    的版本操作统一到一个接口，确保双写和读取合并。

    用法:
        from odap.biz.core.ontology.design.storage import Storage as DesignStorage
        from odap.biz.core.ontology.ontology_api.storage import Storage as OntologyStorage

        adapter = VersionStorageAdapter(
            primary=DesignStorage(),
            secondary=OntologyStorage(),
        )
    """

    def __init__(
        self,
        primary: Any = None,
        secondary: Any = None,
    ) -> None:
        """
        Args:
            primary: 主存储后端 (SQLiteIngestStorage)，用于 design 模块版本操作
            secondary: 次存储后端 (SQLiteOntologyStorage)，用于 ontology_api 版本操作
        """
        if primary is None:
            from odap.biz.core.ontology.design.storage import Storage as DesignStorage
            primary = DesignStorage()
        if secondary is None:
            from odap.biz.core.ontology.ontology_api.storage import Storage as OntologyStorage
            secondary = OntologyStorage()

        self._primary = primary
        self._secondary = secondary

    # ------------------------------------------------------------------
    # 写入操作：双写
    # ------------------------------------------------------------------

    def save_version(self, version_data: Dict[str, Any]) -> str:
        """保存版本到两个存储后端

        主存储使用 save_version()，次存储使用 save_schema_version()。
        字段映射在内部完成。
        """
        result_id = ""

        # 写入主存储 (SQLiteIngestStorage)
        try:
            result_id = self._primary.save_version(version_data)
            logger.debug("VersionStorageAdapter: primary save_version ok, id=%s", result_id)
        except Exception as e:
            logger.warning("VersionStorageAdapter: primary save_version failed: %s", e)

        # 写入次存储 (SQLiteOntologyStorage) — 字段映射
        try:
            mapped = self._map_to_schema_version(version_data)
            self._secondary.save_schema_version(mapped)
            logger.debug("VersionStorageAdapter: secondary save_schema_version ok")
        except Exception as e:
            logger.warning("VersionStorageAdapter: secondary save_schema_version failed: %s", e)

        return result_id

    def lock_version(self, version_id: str) -> bool:
        """锁定版本（仅主存储支持）"""
        try:
            return self._primary.lock_version(version_id)
        except Exception as e:
            logger.warning("VersionStorageAdapter: lock_version failed: %s", e)
            return False

    def set_current_version(self, ontology_id: str, version_id: str) -> bool:
        """设置当前版本（仅主存储支持）"""
        try:
            return self._primary.set_current_version(ontology_id, version_id)
        except Exception as e:
            logger.warning("VersionStorageAdapter: set_current_version failed: %s", e)
            return False

    def append_version_snapshot(self, ontology_id: str, snapshot_data: Dict[str, Any]) -> bool:
        """追加版本快照（仅主存储支持）"""
        try:
            return self._primary.append_version_snapshot(ontology_id, snapshot_data)
        except Exception as e:
            logger.warning("VersionStorageAdapter: append_version_snapshot failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # 读取操作：优先主存储，回退次存储
    # ------------------------------------------------------------------

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """获取版本，优先主存储，回退次存储"""
        # 尝试主存储
        try:
            result = self._primary.get_version(version_id)
            if result is not None:
                return result
        except Exception as e:
            logger.debug("VersionStorageAdapter: primary get_version miss: %s", e)

        # 回退次存储
        try:
            result = self._secondary.get_schema_version(version_id)
            if result is not None:
                return self._map_from_schema_version(result)
        except Exception as e:
            logger.debug("VersionStorageAdapter: secondary get_schema_version miss: %s", e)

        return None

    def get_current_version(self, ontology_id: str) -> Optional[Dict[str, Any]]:
        """获取当前版本，优先主存储"""
        try:
            result = self._primary.get_current_version(ontology_id)
            if result is not None:
                return result
        except Exception as e:
            logger.debug("VersionStorageAdapter: primary get_current_version miss: %s", e)

        # 次存储没有 get_current_version，通过 list_schema_versions 模拟
        try:
            versions = self._secondary.list_schema_versions(ontology_id)
            for v in versions:
                if not v.get("is_stable"):
                    return self._map_from_schema_version(v)
            if versions:
                return self._map_from_schema_version(versions[0])
        except Exception as e:
            logger.debug("VersionStorageAdapter: secondary list_schema_versions miss: %s", e)

        return None

    def get_versions(self, ontology_id: str) -> List[Dict[str, Any]]:
        """获取指定本体的版本列表，合并两个来源并去重"""
        primary_versions: List[Dict[str, Any]] = []
        secondary_versions: List[Dict[str, Any]] = []

        try:
            primary_versions = self._primary.get_versions(ontology_id)
        except Exception as e:
            logger.debug("VersionStorageAdapter: primary get_versions failed: %s", e)

        try:
            raw = self._secondary.list_schema_versions(ontology_id)
            secondary_versions = [self._map_from_schema_version(v) for v in raw]
        except Exception as e:
            logger.debug("VersionStorageAdapter: secondary list_schema_versions failed: %s", e)

        return self._merge_and_deduplicate(primary_versions, secondary_versions)

    def list_all_versions(self) -> List[Dict[str, Any]]:
        """列出所有版本，合并两个来源并去重"""
        primary_versions: List[Dict[str, Any]] = []
        secondary_versions: List[Dict[str, Any]] = []

        try:
            primary_versions = self._primary.list_all_versions()
        except Exception as e:
            logger.debug("VersionStorageAdapter: primary list_all_versions failed: %s", e)

        try:
            raw = self._secondary.list_schema_versions("")
            secondary_versions = [self._map_from_schema_version(v) for v in raw]
        except Exception as e:
            logger.debug("VersionStorageAdapter: secondary list_schema_versions failed: %s", e)

        return self._merge_and_deduplicate(primary_versions, secondary_versions)

    def get_latest_version(self, ontology_id: str) -> Optional[Dict[str, Any]]:
        """获取指定本体的最新版本"""
        versions = self.get_versions(ontology_id)
        if not versions:
            return None
        # 列表按 created_at DESC 排序，第一个即为最新
        return versions[0]

    # ------------------------------------------------------------------
    # 字段映射
    # ------------------------------------------------------------------

    @staticmethod
    def _map_to_schema_version(version_data: Dict[str, Any]) -> Dict[str, Any]:
        """将主存储字段映射为次存储 (schema_version) 字段

        主存储字段: id, ontology_id, version_number, parent_version_id,
                   status, change_summary, created_at, is_current, is_stable,
                   doc_snapshot, doc_id, doc_type, entity_count, ...
        次存储字段: version_id, ontology_id, version_number, parent_version_id,
                   is_stable, changelog, schema_snapshot, created_at
        """
        return {
            "version_id": version_data.get("id", ""),
            "ontology_id": version_data.get("ontology_id", ""),
            "version_number": version_data.get("version_number", ""),
            "parent_version_id": version_data.get("parent_version_id"),
            "is_stable": version_data.get("is_stable", False),
            "changelog": version_data.get("change_summary", ""),
            "schema_snapshot": version_data.get("doc_snapshot"),
            "created_at": version_data.get("created_at", ""),
        }

    @staticmethod
    def _map_from_schema_version(schema_version: Dict[str, Any]) -> Dict[str, Any]:
        """将次存储 (schema_version) 字段映射回主存储字段格式"""
        return {
            "id": schema_version.get("version_id", ""),
            "ontology_id": schema_version.get("ontology_id", ""),
            "version_number": schema_version.get("version_number", ""),
            "parent_version_id": schema_version.get("parent_version_id"),
            "status": "released" if schema_version.get("is_stable") else "draft",
            "change_summary": schema_version.get("changelog", ""),
            "created_at": schema_version.get("created_at", ""),
            "is_current": False,
            "is_stable": schema_version.get("is_stable", False),
            "doc_snapshot": schema_version.get("schema_snapshot"),
            "doc_id": None,
            "doc_type": None,
            "entity_count": 0,
            "relation_count": 0,
            "event_count": 0,
        }

    @staticmethod
    def _merge_and_deduplicate(
        primary: List[Dict[str, Any]],
        secondary: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """合并两个版本列表并按 id 去重，主存储优先"""
        seen_ids: set = set()
        merged: List[Dict[str, Any]] = []

        for v in primary:
            vid = v.get("id", "")
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                merged.append(v)

        for v in secondary:
            vid = v.get("id", "")
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                merged.append(v)

        # 按 created_at DESC 排序
        merged.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return merged
