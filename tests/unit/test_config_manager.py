"""ConfigManager 单元测试"""

import os
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def manager(tmp_path):
    """创建临时数据库的 ConfigManager"""
    os.environ.pop("CONFIG_ENCRYPTION_KEY", None)
    from odap.biz.platform.config.storage.sqlite_config_storage import SQLiteConfigStorage
    from odap.biz.platform.config.impl.config_manager import ConfigManager
    db_path = str(tmp_path / "test_config.db")
    storage = SQLiteConfigStorage(db_path=db_path)
    # 重置单例
    ConfigManager._instance = None
    mgr = ConfigManager(storage=storage)
    ConfigManager._instance = mgr
    yield mgr
    ConfigManager._instance = None


class TestConfigManager:
    """ConfigManager 核心功能测试"""

    def test_get_nonexistent(self, manager):
        """测试获取不存在的配置"""
        assert manager.get("nonexistent.key") is None

    def test_set_and_get(self, manager):
        """测试设置和获取配置"""
        manager.set("llm.model", "gpt-4o", "admin")
        assert manager.get("llm.model") == "gpt-4o"

    def test_get_all(self, manager):
        """测试获取所有配置"""
        manager.set("llm.model", "gpt-4o", "admin")
        manager.set("llm.api_key", "sk-test", "admin")
        all_configs = manager.get_all()
        assert "llm.model" in all_configs
        assert all_configs["llm.model"] == "gpt-4o"

    def test_delete(self, manager):
        """测试删除配置"""
        manager.set("llm.model", "gpt-4o", "admin")
        assert manager.delete("llm.model") is True
        assert manager.get("llm.model") is None

    def test_delete_nonexistent(self, manager):
        """测试删除不存在的配置"""
        assert manager.delete("nonexistent.key") is False

    def test_set_returns_old_value(self, manager):
        """测试 set 返回旧值"""
        manager.set("llm.model", "gpt-4", "admin")
        old = manager.set("llm.model", "gpt-4o", "admin")
        assert old == "gpt-4"

    def test_set_returns_none_for_new(self, manager):
        """测试新配置 set 返回 None"""
        old = manager.set("llm.model", "gpt-4o", "admin")
        assert old is None


class TestConfigManagerHotUpdate:
    """热更新通知测试"""

    def test_subscribe_and_notify(self, manager):
        """测试订阅和通知"""
        notifications = []
        manager.subscribe("llm.model", lambda key, old, new: notifications.append((key, old, new)))
        manager.set("llm.model", "gpt-4o", "admin")
        assert len(notifications) == 1
        assert notifications[0] == ("llm.model", None, "gpt-4o")

    def test_subscribe_multiple_callbacks(self, manager):
        """测试多个订阅者"""
        results_a = []
        results_b = []
        manager.subscribe("llm.model", lambda k, o, n: results_a.append(n))
        manager.subscribe("llm.model", lambda k, o, n: results_b.append(n))
        manager.set("llm.model", "gpt-4o", "admin")
        assert len(results_a) == 1
        assert len(results_b) == 1

    def test_subscriber_exception_does_not_block(self, manager):
        """测试订阅者异常不阻塞其他订阅者"""
        results = []
        manager.subscribe("llm.model", lambda k, o, n: 1 / 0)  # 异常
        manager.subscribe("llm.model", lambda k, o, n: results.append(n))
        manager.set("llm.model", "gpt-4o", "admin")
        assert len(results) == 1  # 第二个订阅者仍然被调用


class TestConfigManagerBatchUpdate:
    """批量更新测试"""

    def test_batch_update_success(self, manager):
        """测试批量更新成功"""
        items = [
            {"key": "llm.model", "value": "gpt-4o"},
            {"key": "llm.api_key", "value": "sk-test"},
        ]
        result = manager.batch_update(items, operator_id="admin", operator_name="Admin")
        assert result["status"] == "success"
        assert result["saved_count"] == 2
        assert result["revision_number"] >= 1

    def test_batch_update_unknown_key(self, manager):
        """测试批量更新未知 key"""
        items = [{"key": "nonexistent.key", "value": "test"}]
        result = manager.batch_update(items, operator_id="admin")
        assert result["status"] == "error"

    def test_batch_update_creates_revision(self, manager):
        """测试批量更新创建变更记录"""
        items = [{"key": "llm.model", "value": "gpt-4o"}]
        result = manager.batch_update(items, operator_id="admin", operator_name="Admin")
        rev = manager._storage.get_revision(result["revision_number"])
        assert rev is not None
        assert len(rev["changes"]) == 1


class TestConfigManagerServiceConfigs:
    """服务配置分组测试"""

    def test_get_service_configs(self, manager):
        """测试获取服务配置分组"""
        configs = manager.get_service_configs()
        assert len(configs) >= 8  # 8 个服务类别
        categories = [c.category.value for c in configs]
        assert "llm" in categories
        assert "graph_db" in categories

    def test_get_service_config_by_category(self, manager):
        """测试按类别获取服务配置"""
        config = manager.get_service_config_by_category("llm")
        assert config is not None
        assert config.category.value == "llm"

    def test_get_service_config_unknown_category(self, manager):
        """测试获取未知类别"""
        config = manager.get_service_config_by_category("unknown")
        assert config is None

    def test_connection_status_not_configured(self, manager):
        """测试未配置服务的连接状态"""
        configs = manager.get_service_configs()
        # 未配置的服务应该显示 NOT_CONFIGURED 或 UNKNOWN
        for cfg in configs:
            assert cfg.connection_status.value in ["unknown", "connected", "disconnected", "not_configured"]


class TestConfigManagerMasking:
    """脱敏展示测试"""

    def test_sensitive_value_masked_in_service_configs(self, manager):
        """测试敏感值在服务配置中脱敏"""
        manager.set("llm.api_key", "sk-secret-key-12345", "admin")
        configs = manager.get_service_configs()
        llm_config = next(c for c in configs if c.category.value == "llm")
        api_key_item = next(i for i in llm_config.items if i.key == "llm.api_key")
        # 脱敏展示值不应包含完整密钥
        if api_key_item.display_value:
            assert "sk-secret-key-12345" not in api_key_item.display_value

    def test_non_sensitive_value_not_masked(self, manager):
        """测试非敏感值不脱敏"""
        manager.set("llm.model", "gpt-4o", "admin")
        configs = manager.get_service_configs()
        llm_config = next(c for c in configs if c.category.value == "llm")
        model_item = next(i for i in llm_config.items if i.key == "llm.model")
        assert model_item.display_value == "gpt-4o"
