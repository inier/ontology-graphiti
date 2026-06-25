"""Crypto Utils 单元测试"""

import os
import pytest
import base64

# 设置测试用加密密钥（base64 编码的 32 字节）
TEST_KEY = "VavLQFDozPRGCA/rzlWtg+loG4Yr3kq4qrS+SRqjY8k="
os.environ["CHANNEL_ENCRYPTION_KEY"] = TEST_KEY


class TestCryptoUtils:
    """加密工具测试"""

    def test_encrypt_decrypt(self):
        """测试加密和解密"""
        from odap.biz.integration.channel_management.crypto_utils import encrypt, decrypt

        plaintext = "this is a secret message"
        encrypted = encrypt(plaintext)

        # 加密后应该是字典格式
        assert isinstance(encrypted, dict)
        assert "ciphertext" in encrypted
        assert "iv" in encrypted
        assert "tag" in encrypted

        # 解密后应该等于原文
        decrypted = decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_empty_string(self):
        """测试加密空字符串"""
        from odap.biz.integration.channel_management.crypto_utils import encrypt, decrypt

        encrypted = encrypt("")
        assert encrypted == {}

        decrypted = decrypt({})
        assert decrypted == ""

    def test_encrypt_different_outputs(self):
        """测试相同输入产生不同输出（随机 IV）"""
        from odap.biz.integration.channel_management.crypto_utils import encrypt

        plaintext = "same message"
        encrypted1 = encrypt(plaintext)
        encrypted2 = encrypt(plaintext)

        # IV 应该不同
        assert encrypted1["iv"] != encrypted2["iv"]
        # ciphertext 也应该不同
        assert encrypted1["ciphertext"] != encrypted2["ciphertext"]

    def test_decrypt_wrong_key(self):
        """测试用错误密钥解密"""
        from odap.biz.integration.channel_management.crypto_utils import (
            encrypt,
            decrypt,
            CryptoError,
        )

        # 加密
        encrypted = encrypt("secret")

        # 修改密钥为另一个有效密钥
        wrong_key = base64.b64encode(b"wrong key for testing 1234567890123456").decode()
        os.environ["CHANNEL_ENCRYPTION_KEY"] = wrong_key

        # 解密应该失败
        with pytest.raises(CryptoError):
            decrypt(encrypted)

        # 恢复原密钥
        os.environ["CHANNEL_ENCRYPTION_KEY"] = TEST_KEY

    def test_decrypt_corrupted_data(self):
        """测试解密被篡改的数据"""
        from odap.biz.integration.channel_management.crypto_utils import (
            encrypt,
            decrypt,
            CryptoError,
        )

        encrypted = encrypt("secret")
        # 篡改 ciphertext
        encrypted["ciphertext"] = "corrupted" + encrypted["ciphertext"][8:]

        with pytest.raises(CryptoError):
            decrypt(encrypted)

    def test_generate_key(self):
        """测试生成新密钥"""
        from odap.biz.integration.channel_management.crypto_utils import generate_key

        key = generate_key()

        # 密钥应该是 base64 编码的 32 字节
        decoded = base64.b64decode(key)
        assert len(decoded) == 32

    def test_generate_key_unique(self):
        """测试每次生成唯一密钥"""
        from odap.biz.integration.channel_management.crypto_utils import generate_key

        key1 = generate_key()
        key2 = generate_key()

        assert key1 != key2

    def test_encrypt_config_dict(self):
        """测试加密配置字典"""
        from odap.biz.integration.channel_management.crypto_utils import (
            encrypt_config,
            decrypt_config,
        )

        config = {"app_id": "cli_123", "app_secret": "secret_value"}
        encrypted_str = encrypt_config(config)

        # 应该返回 JSON 字符串
        assert isinstance(encrypted_str, str)

        # 解密后应该等于原始字典
        decrypted = decrypt_config(encrypted_str)
        assert decrypted == config

    def test_encrypt_config_empty(self):
        """测试加密空配置"""
        from odap.biz.integration.channel_management.crypto_utils import (
            encrypt_config,
            decrypt_config,
        )

        encrypted = encrypt_config({})
        # 空字典也会被加密，不是 "{}"
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

        decrypted = decrypt_config(encrypted)
        assert decrypted == {}

    def test_missing_encryption_key(self):
        """测试未配置加密密钥"""
        from odap.biz.integration.channel_management.crypto_utils import (
            encrypt,
            CryptoError,
        )

        # 清除密钥
        original = os.environ.pop("CHANNEL_ENCRYPTION_KEY", None)
        try:
            with pytest.raises(CryptoError) as exc_info:
                encrypt("test")
            assert "CHANNEL_ENCRYPTION_KEY" in str(exc_info.value)
        finally:
            if original:
                os.environ["CHANNEL_ENCRYPTION_KEY"] = original

    def test_invalid_key_length(self):
        """测试无效密钥长度"""
        from odap.biz.integration.channel_management.crypto_utils import (
            encrypt,
            CryptoError,
        )

        original = os.environ.get("CHANNEL_ENCRYPTION_KEY")
        try:
            # 设置错误长度的密钥（短于 32 字节）
            short_key = base64.b64encode(b"short").decode()
            os.environ["CHANNEL_ENCRYPTION_KEY"] = short_key

            # _get_encryption_key 在调用时读取环境变量，无需重新加载模块
            with pytest.raises(CryptoError) as exc_info:
                encrypt("test")
            assert "32 字节" in str(exc_info.value)
        finally:
            if original:
                os.environ["CHANNEL_ENCRYPTION_KEY"] = original
                os.environ["CHANNEL_ENCRYPTION_KEY"] = original
