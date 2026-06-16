"""配置管理编排层"""

import logging
from typing import Dict, Any, List, Optional

from odap.biz.platform.config.impl.config_manager import ConfigManager
from odap.biz.platform.config.impl.config_validator import ConfigValidator
from odap.biz.platform.config.models.config_models import (
    ServiceConfig, ConfigValidationResult, ServiceCategory,
)

logger = logging.getLogger(__name__)


class ConfigService:
    """配置管理编排层：委托 ConfigManager 和 ConfigValidator"""

    def __init__(self):
        self._manager = ConfigManager.get_instance()
        self._validator = ConfigValidator()

    def get_all_configs(self) -> List[ServiceConfig]:
        """获取所有服务类别配置"""
        return self._manager.get_service_configs()

    def get_configs_by_category(self, category: str) -> Optional[ServiceConfig]:
        """获取指定服务类别配置"""
        return self._manager.get_service_config_by_category(category)

    async def update_configs(
        self,
        items: List[Dict[str, str]],
        test_connection: bool = False,
        operator_id: str = "",
        operator_name: str = "",
    ) -> Dict[str, Any]:
        """批量更新配置"""
        # 验证所有 key 是否合法
        for item in items:
            key = item.get("key", "")
            schema = self._manager._storage.get_schema(key)
            if not schema:
                return {"status": "error", "message": f"Unknown config key: {key}"}

        # 如果需要测试连接，先测试再保存
        validation_results: List[ConfigValidationResult] = []
        if test_connection:
            # 收集受影响的服务类别
            affected_categories = set()
            for item in items:
                schema = self._manager._storage.get_schema(item["key"])
                if schema:
                    affected_categories.add(schema.get("category", "general"))

            # 构建测试配置（合并现有 + 新值）
            for cat in affected_categories:
                config = self._manager.get_all()
                for item in items:
                    config[item["key"]] = item.get("value", "")
                result = await self._validator.validate(ServiceCategory(cat), config)
                validation_results.append(result)

            # 如果有验证失败，不保存
            failed = [r for r in validation_results if not r.success]
            if failed:
                return {
                    "status": "validation_failed",
                    "saved_count": 0,
                    "validation_results": [r.model_dump() for r in validation_results],
                }

        # 批量保存
        result = self._manager.batch_update(items, operator_id, operator_name)

        # 写入统一审计日志
        try:
            from odap.infra.security.unified_audit import audit_log
            audit_log(
                action="config_update",
                resource_type="system_config",
                resource_id=",".join(i["key"] for i in items),
                operator_id=operator_id,
                details={"revision_number": result.get("revision_number")},
            )
        except Exception as e:
            logger.warning("Failed to write audit log: %s", e)

        result["validation_results"] = [r.model_dump() for r in validation_results]
        return result

    async def test_connection(
        self,
        categories: List[str],
        items: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """测试服务连接"""
        # 如果提供了 items，临时合并到配置中
        temp_config = self._manager.get_all()
        if items:
            for item in items:
                temp_config[item["key"]] = item.get("value", "")

        results = []
        for cat_str in categories:
            try:
                cat = ServiceCategory(cat_str)
            except ValueError:
                results.append({
                    "category": cat_str, "success": False,
                    "message": f"Unknown category: {cat_str}",
                })
                continue

            result = await self._validator.validate(cat, temp_config)
            results.append(result.model_dump())

        return results

    def list_revisions(
        self, category: Optional[str] = None, limit: int = 50, offset: int = 0,
    ) -> Dict[str, Any]:
        """查询变更历史"""
        return self._manager._storage.list_revisions(category, limit, offset)

    def get_revision(self, revision_number: int) -> Optional[Dict[str, Any]]:
        """获取指定修订号"""
        return self._manager._storage.get_revision(revision_number)

    async def rollback_to_revision(
        self, revision_number: int, operator_id: str = "", operator_name: str = "",
    ) -> Dict[str, Any]:
        """回滚到指定修订号"""
        revision = self._manager._storage.get_revision(revision_number)
        if not revision:
            return {"status": "error", "message": f"Revision {revision_number} not found"}

        changes = revision.get("changes", [])
        rollback_items = []
        for change in changes:
            # 回滚：将值恢复为 old_value
            # 注意：old_value 可能是脱敏的，需要从存储中获取原始值
            rollback_items.append({
                "key": change["key"],
                "value": change.get("old_value", ""),
            })

        # 执行回滚
        result = self._manager.batch_update(rollback_items, operator_id, operator_name)
        result["rolled_back_to"] = revision_number
        return result

    def export_configs(self) -> Dict[str, Any]:
        """导出配置（敏感字段替换为占位符）"""
        configs = self._manager.get_service_configs()
        items = []
        for svc in configs:
            for item in svc.items:
                export_value = "***REDACTED***" if item.is_sensitive and item.has_value else (item.value or "")
                items.append({
                    "key": item.key,
                    "value": export_value,
                    "value_type": item.value_type.value,
                    "category": item.category.value,
                })
        return {
            "exported_at": __import__("datetime").datetime.now().isoformat(),
            "version": "1.0",
            "items": items,
        }

    def import_configs(
        self, items: List[Dict[str, str]], operator_id: str = "", operator_name: str = "",
    ) -> Dict[str, Any]:
        """导入配置（跳过 REDACTED 字段）"""
        import_items = []
        skipped_keys = []
        for item in items:
            if item.get("value") == "***REDACTED***":
                skipped_keys.append(item["key"])
                continue
            import_items.append(item)

        if not import_items:
            return {
                "status": "success", "imported_count": 0,
                "skipped_count": len(skipped_keys), "skipped_keys": skipped_keys,
            }

        result = self._manager.batch_update(import_items, operator_id, operator_name)
        result["skipped_count"] = len(skipped_keys)
        result["skipped_keys"] = skipped_keys
        return result

    def get_config_status(self) -> List[Dict[str, Any]]:
        """获取所有服务类别的连接状态摘要"""
        configs = self._manager.get_service_configs()
        return [
            {
                "category": cfg.category.value,
                "label": cfg.label,
                "connection_status": cfg.connection_status.value,
                "item_count": len(cfg.items),
                "configured_count": sum(1 for i in cfg.items if i.has_value),
                "required_count": sum(1 for i in cfg.items if i.is_required),
            }
            for cfg in configs
        ]
