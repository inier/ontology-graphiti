"""SQLiteChannelStorage 单元测试"""

import os
import pytest
from pathlib import Path
import base64

# 设置测试用加密密钥（base64 编码的 32 字节）
TEST_KEY = "VavLQFDozPRGCA/rzlWtg+loG4Yr3kq4qrS+SRqjY8k="
os.environ["CHANNEL_ENCRYPTION_KEY"] = TEST_KEY


@pytest.fixture
def storage(tmp_path):
    """创建临时数据库的 SQLiteChannelStorage"""
    from odap.biz.integration.channel_management.storage.sqlite_channel_storage import SQLiteChannelStorage

    db_path = str(tmp_path / "test_channel.db")
    return SQLiteChannelStorage(db_path=db_path)


@pytest.fixture
def sample_channel_config(storage):
    """创建示例渠道配置"""
    from odap.biz.integration.channel_management.models.channel import (
        ChannelConfig,
        ChannelType,
        ChannelStatus,
    )

    config = ChannelConfig(
        workspace_id="test-workspace-001",
        channel_type=ChannelType.FEISHU,
        name="测试飞书渠道",
        config={
            "app_id": "cli_test123",
            "app_secret": "test_secret_value",
            "encrypt_key": "test_encrypt_key",
        },
        enabled=False,
        allow_from=["user1", "user2"],
        status=ChannelStatus.DISCONNECTED,
    )
    return storage.save(config)


class TestSQLiteChannelStorage:
    """SQLiteChannelStorage CRUD 测试"""

    def test_save_and_get(self, storage, sample_channel_config):
        """测试保存和获取"""
        retrieved = storage.get(sample_channel_config.id)
        assert retrieved is not None
        assert retrieved.id == sample_channel_config.id
        assert retrieved.name == "测试飞书渠道"
        assert retrieved.channel_type.value == "feishu"

    def test_get_nonexistent(self, storage):
        """测试获取不存在的配置"""
        result = storage.get("nonexistent-id")
        assert result is None

    def test_get_by_workspace(self, storage, sample_channel_config):
        """测试按工作空间获取"""
        channels = storage.get_by_workspace("test-workspace-001")
        assert len(channels) == 1
        assert channels[0].id == sample_channel_config.id

    def test_get_by_workspace_and_type(self, storage, sample_channel_config):
        """测试按工作空间和类型过滤"""
        from odap.biz.integration.channel_management.models.channel import ChannelType

        channels = storage.get_by_workspace("test-workspace-001", ChannelType.FEISHU)
        assert len(channels) == 1

        channels = storage.get_by_workspace("test-workspace-001", ChannelType.TELEGRAM)
        assert len(channels) == 0

    def test_get_by_workspace_empty(self, storage):
        """测试获取不存在的工作空间"""
        channels = storage.get_by_workspace("nonexistent-workspace")
        assert len(channels) == 0

    def test_delete(self, storage, sample_channel_config):
        """测试删除"""
        result = storage.delete(sample_channel_config.id)
        assert result is True

        retrieved = storage.get(sample_channel_config.id)
        assert retrieved is None

    def test_delete_nonexistent(self, storage):
        """测试删除不存在的配置"""
        result = storage.delete("nonexistent-id")
        assert result is False

    def test_update_status(self, storage, sample_channel_config):
        """测试更新状态"""
        from odap.biz.integration.channel_management.models.channel import ChannelStatus

        result = storage.update_status(sample_channel_config.id, ChannelStatus.CONNECTED)
        assert result is True

        retrieved = storage.get(sample_channel_config.id)
        assert retrieved is not None
        assert retrieved.status == ChannelStatus.CONNECTED

    def test_update_status_nonexistent(self, storage):
        """测试更新不存在配置的状态"""
        from odap.biz.integration.channel_management.models.channel import ChannelStatus

        result = storage.update_status("nonexistent-id", ChannelStatus.CONNECTED)
        assert result is False

    def test_multiple_channels_same_workspace(self, storage):
        """测试同一工作空间多个渠道"""
        from odap.biz.integration.channel_management.models.channel import (
            ChannelConfig,
            ChannelType,
        )

        config1 = ChannelConfig(
            workspace_id="test-ws",
            channel_type=ChannelType.FEISHU,
            name="飞书1",
        )
        config2 = ChannelConfig(
            workspace_id="test-ws",
            channel_type=ChannelType.DINGTALK,
            name="钉钉1",
        )
        config3 = ChannelConfig(
            workspace_id="test-ws",
            channel_type=ChannelType.TELEGRAM,
            name="TG1",
        )

        storage.save(config1)
        storage.save(config2)
        storage.save(config3)

        channels = storage.get_by_workspace("test-ws")
        assert len(channels) == 3

    def test_config_encryption(self, storage, sample_channel_config):
        """测试配置加密存储"""
        # 获取解密后的配置
        decrypted = storage.get_decrypted_config(sample_channel_config.id)
        assert decrypted is not None
        assert decrypted["app_secret"] == "test_secret_value"
        assert decrypted["encrypt_key"] == "test_encrypt_key"

    def test_config_encryption_nonexistent(self, storage):
        """测试解密不存在的配置"""
        result = storage.get_decrypted_config("nonexistent-id")
        assert result is None

    def test_upsert(self, storage, sample_channel_config):
        """测试 upsert (更新现有配置)"""
        from odap.biz.integration.channel_management.models.channel import ChannelStatus

        # 更新配置
        sample_channel_config.name = "更新的名称"
        sample_channel_config.status = ChannelStatus.CONNECTED
        storage.save(sample_channel_config)

        # 验证更新
        retrieved = storage.get(sample_channel_config.id)
        assert retrieved.name == "更新的名称"
        assert retrieved.status == ChannelStatus.CONNECTED


class TestChannelConfigModel:
    """ChannelConfig 领域模型测试"""

    def test_mask_credentials(self):
        """测试凭证脱敏"""
        from odap.biz.integration.channel_management.models.channel import (
            ChannelConfig,
            ChannelType,
        )

        config = ChannelConfig(
            workspace_id="test-ws",
            channel_type=ChannelType.FEISHU,
            name="测试",
            config={
                "app_id": "cli_123",
                "app_secret": "secret_value",
                "has_custom_field": True,
            },
        )

        masked = config.mask_credentials()

        # app_secret 应该被脱敏为 has_app_secret
        assert masked["has_app_secret"] is True
        # 非敏感字段应该保留
        assert masked["app_id"] == "cli_123"
        assert masked["has_custom_field"] is True

    def test_has_any_credential(self):
        """测试是否有凭证"""
        from odap.biz.integration.channel_management.models.channel import (
            ChannelConfig,
            ChannelType,
        )

        config_with_creds = ChannelConfig(
            workspace_id="test-ws",
            channel_type=ChannelType.FEISHU,
            name="测试",
            config={"app_secret": "secret"},
        )
        assert config_with_creds.has_any_credential() is True

        config_without_creds = ChannelConfig(
            workspace_id="test-ws",
            channel_type=ChannelType.FEISHU,
            name="测试",
            config={"app_id": "cli_123"},
        )
        assert config_without_creds.has_any_credential() is False

    def test_to_storage_dict(self):
        """测试转换为存储字典"""
        from odap.biz.integration.channel_management.models.channel import (
            ChannelConfig,
            ChannelType,
        )

        config = ChannelConfig(
            workspace_id="test-ws",
            channel_type=ChannelType.TELEGRAM,
            name="测试",
            config={"token": "secret"},
        )

        storage_dict = config.to_storage_dict()

        assert storage_dict["workspace_id"] == "test-ws"
        assert storage_dict["channel_type"] == "telegram"
        assert storage_dict["name"] == "测试"

    def test_from_storage_dict(self):
        """测试从存储字典恢复"""
        from odap.biz.integration.channel_management.models.channel import (
            ChannelConfig,
            ChannelType,
            ChannelStatus,
        )

        data = {
            "id": "test-id",
            "workspace_id": "test-ws",
            "channel_type": "slack",
            "name": "测试 Slack",
            "enabled": True,
            "allow_from": ["*"],
            "config": {"bot_token": "secret"},
            "status": "connected",
            "created_at": "2026-06-22T10:00:00",
            "updated_at": "2026-06-22T10:00:00",
        }

        config = ChannelConfig.from_storage_dict(data)

        assert config.id == "test-id"
        assert config.channel_type == ChannelType.SLACK
        assert config.status == ChannelStatus.CONNECTED


class TestChannelTypes:
    """渠道类型枚举和常量测试"""

    def test_all_channel_types(self):
        """测试所有渠道类型"""
        from odap.biz.integration.channel_management.models.channel import ChannelType

        expected_types = [
            "telegram",
            "slack",
            "discord",
            "feishu",
            "dingtalk",
            "email",
            "qq",
            "matrix",
            "whatsapp",
            "mochat",
        ]

        actual_types = [ct.value for ct in ChannelType]
        for expected in expected_types:
            assert expected in actual_types

    def test_channel_type_names(self):
        """测试渠道名称映射"""
        from odap.biz.integration.channel_management.models.channel import (
            CHANNEL_TYPE_NAMES,
            ChannelType,
        )

        assert CHANNEL_TYPE_NAMES[ChannelType.FEISHU] == "飞书"
        assert CHANNEL_TYPE_NAMES[ChannelType.DINGTALK] == "钉钉"
        assert CHANNEL_TYPE_NAMES[ChannelType.TELEGRAM] == "Telegram"

    def test_required_fields(self):
        """测试必填字段"""
        from odap.biz.integration.channel_management.models.channel import (
            CHANNEL_REQUIRED_FIELDS,
            ChannelType,
        )

        # 飞书必填
        assert "app_id" in CHANNEL_REQUIRED_FIELDS[ChannelType.FEISHU]
        assert "app_secret" in CHANNEL_REQUIRED_FIELDS[ChannelType.FEISHU]

        # Telegram 必填
        assert "token" in CHANNEL_REQUIRED_FIELDS[ChannelType.TELEGRAM]
