"""VersionStorageAdapter - 双存储版本适配器

将版本数据同时写入主存储和备用存储，
读取时优先查主存储，回退到备用存储，
列表时合并去重。
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VersionStorageAdapter:
    """双存储版本适配器

    - save_version: 写入主存储和备用存储
    - get_version: 优先查主存储，回退到备用存储
    - list_versions: 合并两个存储的结果并去重
    """

    def __init__(self, primary, secondary):
        """
        Args:
            primary: 主存储（必须实现 save_version / get_version / list_versions）
            secondary: 备用存储（同上接口）
        """
        self._primary = primary
        self._secondary = secondary

    @property
    def primary(self):
        return self._primary

    @property
    def secondary(self):
        return self._secondary

    def save_version(self, version: Dict[str, Any]) -> Dict[str, Any]:
        """写入两个存储"""
        # 先写主存储
        result = self._primary.save_version(version)
        # 再写备用存储（失败不影响主存储）
        try:
            self._secondary.save_version(version)
        except Exception as e:
            logger.warning("VersionStorageAdapter: secondary save failed: %s", e)
        return result

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """优先查主存储，回退到备用存储"""
        result = self._primary.get_version(version_id)
        if result is not None:
            return result
        # 回退到备用存储
        try:
            return self._secondary.get_version(version_id)
        except Exception as e:
            logger.warning("VersionStorageAdapter: secondary get failed: %s", e)
            return None

    def list_versions(self, ontology_id: str, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        """合并两个存储的结果并去重"""
        primary_results = []
        secondary_results = []

        try:
            primary_results = self._primary.list_versions(ontology_id, page, page_size)
        except Exception as e:
            logger.warning("VersionStorageAdapter: primary list failed: %s", e)

        try:
            secondary_results = self._secondary.list_versions(ontology_id, page, page_size)
        except Exception as e:
            logger.warning("VersionStorageAdapter: secondary list failed: %s", e)

        # 按 version_id 去重（主存储优先）
        seen_ids = set()
        merged = []
        for item in primary_results + secondary_results:
            vid = item.get("version_id", "")
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                merged.append(item)

        return merged
