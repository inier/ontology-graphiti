"""配置管理核心 - 内存缓存 + 热更新通知 + 加密存储/解密读取"""

import logging
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from odap.biz.platform.config.interfaces.config_repository import ConfigRepository
from odap.biz.platform.config.storage import Storage
from odap.biz.platform.config.models.config_models import (
    ConfigItem, ServiceConfig, ConfigRevision, ConfigChange,
    ConfigValidationResult, ConnectionStatus, ServiceCategory,
    SERVICE_CATEGORY_META, PREDEFINED_CONFIG_ITEMS,
)
from odap.infra.security.config_encryption import get_encryption
from odap.infra.config_composer import get_config_composer

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理核心：内存缓存 + 热更新通知"""

    _instance: Optional["ConfigManager"] = None

    def __init__(self, storage: Optional[ConfigRepository] = None):
        self._storage = storage or Storage()
        self._cache: Dict[str, str] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
        self._load_cache()

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_cache(self):
        """启动时从数据库加载所有配置到内存缓存"""
        self._cache = self._storage.load_all_to_dict()
        # 自动从环境变量初始化未配置的项
        self._auto_populate_from_env()
        # 同步到 ConfigurationComposer DB 层
        self._sync_to_composer()
        logger.info("Loaded %d config items into cache", len(self._cache))

    def _auto_populate_from_env(self):
        """将环境变量中已存在但 DB 中为空的配置项自动写入 DB。

        遍历 config_schema_registry 中所有带 env_mapping 的项，
        如果该 env 已设置且 DB 中尚无记录，则自动保存。
        """
        import os
        schemas = self._storage.list_schemas()
        populated = 0
        for schema in schemas:
            env_name = schema.get("env_mapping")
            if not env_name:
                continue
            env_value = os.environ.get(env_name, "")
            if not env_value:
                continue
            key = schema["key"]
            if key in self._cache:
                continue  # DB 已有记录，不覆盖
            # 写入 DB 和缓存
            self._storage.save_config(key, env_value, "system_init")
            self._cache[key] = env_value
            populated += 1
        if populated:
            logger.info("Auto-populated %d config items from environment variables", populated)

    def _sync_to_composer(self):
        """将缓存同步到 ConfigurationComposer 的 DB 层"""
        try:
            composer = get_config_composer()
            composer.set_db_config(self._cache)
        except Exception as e:
            logger.warning("Failed to sync config to composer: %s", e)

    def get(self, key: str) -> Optional[str]:
        """获取配置值（解密后）"""
        with self._lock:
            return self._cache.get(key)

    def get_all(self) -> Dict[str, str]:
        """获取所有配置值"""
        with self._lock:
            return dict(self._cache)

    def set(self, key: str, value: str, updated_by: str = "") -> Optional[str]:
        """设置配置值，返回旧值"""
        with self._lock:
            old_value = self._cache.get(key)
            self._storage.save_config(key, value, updated_by)
            self._cache[key] = value
            # 同步到 composer
            try:
                composer = get_config_composer()
                composer.update_db_config(key, value)
            except Exception as e:
                logger.warning("Failed to update composer: %s", e)
            # 通知订阅者
            self._notify_subscribers(key, old_value, value)
        return old_value

    def delete(self, key: str) -> bool:
        """删除配置项"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            result = self._storage.delete_config(key)
            if result:
                try:
                    composer = get_config_composer()
                    composer.update_db_config(key, None)
                except Exception as e:
                    logger.warning("Failed to update composer: %s", e)
            return result

    def subscribe(self, key: str, callback: Callable[[str, Optional[str], str], None]) -> None:
        """订阅配置变更通知"""
        with self._lock:
            self._subscribers.setdefault(key, []).append(callback)

    def _notify_subscribers(self, key: str, old_value: Optional[str], new_value: str) -> None:
        """通知订阅者"""
        callbacks = self._subscribers.get(key, [])
        for callback in callbacks:
            try:
                callback(key, old_value, new_value)
            except Exception as e:
                logger.warning("Subscriber callback failed for %s: %s", key, e)

    def get_service_configs(self) -> List[ServiceConfig]:
        """获取按服务类别分组的配置"""
        schemas = self._storage.list_schemas()
        categories: Dict[str, List[ConfigItem]] = {}

        for schema in schemas:
            cat = schema.get("category", "general")
            key = schema["key"]
            value = self._cache.get(key)
            encryption = get_encryption()

            item = ConfigItem(
                key=key,
                value=value,
                display_value=encryption.mask_value(value) if schema.get("is_sensitive") and value else value,
                value_type=schema.get("value_type", "string"),
                category=ServiceCategory(cat) if cat in [c.value for c in ServiceCategory] else ServiceCategory.GENERAL,
                label=schema.get("label", ""),
                description=schema.get("description", ""),
                is_sensitive=bool(schema.get("is_sensitive", 0)),
                is_required=bool(schema.get("is_required", 0)),
                default_value=schema.get("default_value"),
                choices=schema["choices"] if isinstance(schema.get("choices"), list) else (json.loads(schema["choices"]) if isinstance(schema.get("choices"), str) else []),
                min_val=schema.get("min_val"),
                max_val=schema.get("max_val"),
                sort_order=schema.get("sort_order", 0),
                group=schema.get("config_group", ""),
                has_value=value is not None,
            )
            categories.setdefault(cat, []).append(item)

        result = []
        for cat in ServiceCategory:
            meta = SERVICE_CATEGORY_META.get(cat, {})
            items = categories.get(cat.value, [])
            # 判断连接状态
            status = self._determine_connection_status(cat.value, items)
            result.append(ServiceConfig(
                category=cat,
                label=meta.get("label", cat.value),
                description=meta.get("description", ""),
                icon=meta.get("icon", ""),
                items=items,
                connection_status=status,
            ))
        return result

    def get_service_config_by_category(self, category: str) -> Optional[ServiceConfig]:
        """获取指定服务类别的配置"""
        configs = self.get_service_configs()
        for cfg in configs:
            if cfg.category.value == category:
                return cfg
        return None

    def _determine_connection_status(self, category: str, items: List[ConfigItem]) -> ConnectionStatus:
        """判断服务连接状态"""
        required_items = [i for i in items if i.is_required]
        if required_items and not all(i.has_value for i in required_items):
            return ConnectionStatus.NOT_CONFIGURED
        if not any(i.has_value for i in items):
            return ConnectionStatus.NOT_CONFIGURED
        return ConnectionStatus.UNKNOWN

    def batch_update(
        self,
        items: List[Dict[str, str]],
        operator_id: str = "",
        operator_name: str = "",
    ) -> Dict[str, Any]:
        """批量更新配置（all-or-nothing）"""
        changes: List[ConfigChange] = []
        updated_keys: List[str] = []

        with self._lock:
            for item in items:
                key = item["key"]
                value = item.get("value", "")
                schema = self._storage.get_schema(key)
                if not schema:
                    return {"status": "error", "message": f"Unknown config key: {key}"}

                old_value = self._cache.get(key)
                is_sensitive = bool(schema.get("is_sensitive", 0))

                # 敏感字段脱敏记录
                encryption = get_encryption()
                changes.append(ConfigChange(
                    key=key,
                    old_value=encryption.mask_value(old_value) if is_sensitive and old_value else old_value,
                    new_value=encryption.mask_value(value) if is_sensitive else value,
                    is_sensitive=is_sensitive,
                ))

                # 保存到存储和缓存
                self._storage.save_config(key, value, operator_id)
                self._cache[key] = value
                updated_keys.append(key)

            # 同步到 composer
            self._sync_to_composer()

            # 通知订阅者
            for change in changes:
                new_val = self._cache.get(change.key)
                if new_val is not None:
                    self._notify_subscribers(change.key, None, new_val)

        # 保存变更记录
        revision = ConfigRevision(
            revision_number=self._storage.get_next_revision_number(),
            operator_id=operator_id,
            operator_name=operator_name,
            changes=changes,
        )
        self._storage.save_revision(revision.model_dump())

        return {
            "status": "success",
            "saved_count": len(updated_keys),
            "revision_number": revision.revision_number,
        }


import json
