"""SQLiteConfigStorage 单元测试"""

import os
import json
import pytest
from pathlib import Path


@pytest.fixture
def storage(tmp_path):
    """创建临时数据库的 SQLiteConfigStorage"""
    os.environ.pop("CONFIG_ENCRYPTION_KEY", None)
    from odap.biz.platform.config.storage.sqlite_config_storage import SQLiteConfigStorage
    db_path = str(tmp_path / "test_config.db")
    return SQLiteConfigStorage(db_path=db_path)


class TestSQLiteConfigStorage:
    """SQLiteConfigStorage CRUD 测试"""

    def test_register_schema(self, storage):
        """测试 schema 注册"""
        schema = storage.get_schema("llm.api_key")
        assert schema is not None
        assert schema["key"] == "llm.api_key"
        assert schema["category"] == "llm"
        assert schema["is_sensitive"] == 1

    def test_list_schemas(self, storage):
        """测试列出所有 schema"""
        schemas = storage.list_schemas()
        assert len(schemas) >= 21  # 预定义 21 个配置项

    def test_list_schemas_by_category(self, storage):
        """测试按类别列出 schema"""
        schemas = storage.list_schemas(category="llm")
        assert len(schemas) >= 3
        assert all(s["category"] == "llm" for s in schemas)

    def test_save_and_get_config(self, storage):
        """测试保存和读取配置"""
        storage.save_config("llm.api_key", "sk-test-key-123", "admin")
        value = storage.get_config("llm.api_key")
        assert value == "sk-test-key-123"

    def test_get_nonexistent_config(self, storage):
        """测试获取不存在的配置"""
        value = storage.get_config("nonexistent.key")
        assert value is None

    def test_save_sensitive_config_encrypted(self, storage):
        """测试敏感配置加密存储"""
        storage.save_config("llm.api_key", "sk-secret-key", "admin")
        raw = storage.get_raw_config("llm.api_key")
        # 加密后应该不等于原始值
        assert raw != "sk-secret-key"

    def test_save_non_sensitive_config(self, storage):
        """测试非敏感配置不加密"""
        storage.save_config("llm.model", "gpt-4o", "admin")
        raw = storage.get_raw_config("llm.model")
        assert raw == "gpt-4o"

    def test_list_configs(self, storage):
        """测试列出所有配置"""
        storage.save_config("llm.model", "gpt-4o", "admin")
        storage.save_config("llm.api_key", "sk-test", "admin")
        configs = storage.list_configs()
        assert len(configs) >= 2

    def test_list_configs_by_category(self, storage):
        """测试按类别列出配置"""
        storage.save_config("llm.model", "gpt-4o", "admin")
        configs = storage.list_configs(category="llm")
        assert len(configs) >= 1

    def test_delete_config(self, storage):
        """测试删除配置"""
        storage.save_config("llm.model", "gpt-4o", "admin")
        assert storage.delete_config("llm.model") is True
        assert storage.get_config("llm.model") is None

    def test_delete_nonexistent_config(self, storage):
        """测试删除不存在的配置"""
        assert storage.delete_config("nonexistent.key") is False

    def test_save_revision(self, storage):
        """测试保存变更记录"""
        revision = {
            "id": "rev-001",
            "revision_number": 1,
            "operator_id": "admin",
            "operator_name": "Admin",
            "changed_at": "2026-06-14T12:00:00",
            "changes": [{"key": "llm.model", "old_value": "gpt-4", "new_value": "gpt-4o", "is_sensitive": False}],
        }
        storage.save_revision(revision)
        result = storage.get_revision(1)
        assert result is not None
        assert result["revision_number"] == 1

    def test_list_revisions(self, storage):
        """测试列出变更历史"""
        for i in range(3):
            storage.save_revision({
                "id": f"rev-{i:03d}",
                "revision_number": i + 1,
                "operator_id": "admin",
                "operator_name": "Admin",
                "changed_at": f"2026-06-14T12:0{i}:00",
                "changes": [],
            })
        result = storage.list_revisions(limit=2, offset=0)
        assert result["total"] == 3
        assert len(result["revisions"]) == 2

    def test_get_next_revision_number(self, storage):
        """测试获取下一个修订号"""
        assert storage.get_next_revision_number() == 1
        storage.save_revision({
            "id": "rev-001", "revision_number": 1,
            "operator_id": "admin", "operator_name": "Admin",
            "changed_at": "2026-06-14T12:00:00", "changes": [],
        })
        assert storage.get_next_revision_number() == 2

    def test_load_all_to_dict(self, storage):
        """测试加载所有配置为字典"""
        storage.save_config("llm.model", "gpt-4o", "admin")
        storage.save_config("llm.api_key", "sk-test", "admin")
        result = storage.load_all_to_dict()
        assert "llm.model" in result
        assert result["llm.model"] == "gpt-4o"

    def test_upsert_config(self, storage):
        """测试 INSERT OR REPLACE (upsert)"""
        storage.save_config("llm.model", "gpt-4", "admin")
        storage.save_config("llm.model", "gpt-4o", "admin")
        assert storage.get_config("llm.model") == "gpt-4o"

    def test_json_choices_serialization(self, storage):
        """测试 choices 字段 JSON 序列化"""
        schema = storage.get_schema("auth.jwt_algorithm")
        assert schema is not None
        # choices 应该是 JSON 字符串或 None
        if schema.get("choices"):
            choices = json.loads(schema["choices"])
            assert "HS256" in choices


class TestConfigEncryption:
    """加密/解密测试"""

    def test_encrypt_decrypt(self):
        """测试加密和解密"""
        from odap.infra.security.config_encryption import ConfigEncryption
        enc = ConfigEncryption()
        if not enc.available:
            pytest.skip("cryptography not installed")

        plaintext = "sk-test-secret-key-12345"
        encrypted = enc.encrypt(plaintext)
        assert encrypted != plaintext
        decrypted = enc.decrypt(encrypted)
        assert decrypted == plaintext

    def test_mask_value(self):
        """测试脱敏展示"""
        from odap.infra.security.config_encryption import ConfigEncryption
        assert ConfigEncryption.mask_value("sk-1234567890abcd") == "****abcd"
        assert ConfigEncryption.mask_value("ab") == "****"
        assert ConfigEncryption.mask_value("") == ""
        assert ConfigEncryption.mask_value(None) == ""

    def test_is_encrypted(self):
        """测试判断是否加密"""
        from odap.infra.security.config_encryption import ConfigEncryption
        enc = ConfigEncryption()
        if not enc.available:
            pytest.skip("cryptography not installed")

        encrypted = enc.encrypt("test")
        assert enc.is_encrypted(encrypted) is True
        assert enc.is_encrypted("plain text") is False
        assert enc.is_encrypted("") is False
