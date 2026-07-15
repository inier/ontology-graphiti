"""敏感配置加密工具 - AES-256-GCM"""

import os
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 延迟导入，cryptography 可能未安装
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

_REDACTED = "***REDACTED***"


class ConfigEncryption:
    """AES-256-GCM 对称加密，密钥从 CONFIG_ENCRYPTION_KEY 环境变量读取"""

    def __init__(self):
        if not _HAS_CRYPTO:
            logger.warning("cryptography not installed, encryption disabled")
            self._aesgcm = None
            return

        key_b64 = os.getenv("CONFIG_ENCRYPTION_KEY")
        if not key_b64:
            # 自动生成密钥
            key = AESGCM.generate_key(bit_length=256)
            key_b64 = base64.b64encode(key).decode()
            os.environ["CONFIG_ENCRYPTION_KEY"] = key_b64
            logger.info("Generated new CONFIG_ENCRYPTION_KEY (auto-saved to env)")

        self._aesgcm = AESGCM(base64.b64decode(key_b64))

    @property
    def available(self) -> bool:
        return self._aesgcm is not None

    def encrypt(self, plaintext: str) -> str:
        """加密明文，返回 base64 编码的 nonce+ciphertext"""
        if not self._aesgcm or not plaintext:
            return plaintext
        nonce = os.urandom(12)
        ct = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """解密 base64 编码的 nonce+ciphertext，返回明文"""
        if not self._aesgcm or not ciphertext:
            return ciphertext
        try:
            data = base64.b64decode(ciphertext)
            nonce, ct = data[:12], data[12:]
            return self._aesgcm.decrypt(nonce, ct, None).decode("utf-8")
        except Exception as e:
            logger.warning("Decryption failed, returning raw value: %s", e)
            return ciphertext

    def is_encrypted(self, value: str) -> bool:
        """判断值是否为加密后的格式（base64 且长度 > 16）"""
        if not value or not self._aesgcm:
            return False
        try:
            data = base64.b64decode(value)
            return len(data) > 12  # nonce(12) + at least 1 byte ciphertext
        except Exception:
            return False

    @staticmethod
    def mask_value(value: Optional[str], show_last: int = 4) -> str:
        """脱敏展示：显示最后 N 位，其余用 **** 替代"""
        if not value:
            return ""
        if len(value) <= show_last:
            return "****"
        return "****" + value[-show_last:]


# 全局单例
_encryption: Optional[ConfigEncryption] = None


def get_encryption() -> ConfigEncryption:
    global _encryption
    if _encryption is None:
        _encryption = ConfigEncryption()
    return _encryption
