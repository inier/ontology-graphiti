"""加密工具模块 - AES-256-GCM 加密/解密。

用于安全存储渠道配置中的敏感凭证。
"""

from __future__ import annotations

import base64
import os
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 环境变量名
ENCRYPTION_KEY_ENV = "CHANNEL_ENCRYPTION_KEY"

# 常量
KEY_LENGTH = 32  # 256 bits
IV_LENGTH = 12  # 96 bits
TAG_LENGTH = 16  # 128 bits


class CryptoError(Exception):
    """加密/解密相关错误。"""
    pass


def _get_encryption_key() -> bytes:
    """获取加密密钥。

    Returns:
        32字节加密密钥

    Raises:
        CryptoError: 密钥未配置或格式错误
    """
    key_str = os.environ.get(ENCRYPTION_KEY_ENV)
    if not key_str:
        raise CryptoError(
            f"环境变量 {ENCRYPTION_KEY_ENV} 未配置。"
            "请设置 32 字节 (base64 64字符) 的加密密钥。"
        )

    try:
        key = base64.b64decode(key_str)
        if len(key) != KEY_LENGTH:
            raise CryptoError(
                f"密钥长度错误: 期望 {KEY_LENGTH} 字节, 实际 {len(key)} 字节"
            )
        return key
    except Exception as e:
        raise CryptoError(f"密钥解码失败: {e}") from e


def encrypt(plaintext: str) -> dict[str, str]:
    """加密明文字符串。

    Args:
        plaintext: 要加密的明文字符串

    Returns:
        加密结果字典，包含 ciphertext, iv, tag (均为 base64 编码)

    Raises:
        CryptoError: 加密失败
    """
    if not plaintext:
        return {}

    try:
        key = _get_encryption_key()
        iv = os.urandom(IV_LENGTH)
        aesgcm = AESGCM(key)

        ciphertext_with_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)

        # GCM 模式下，密文后 16 字节是 auth tag
        ciphertext = ciphertext_with_tag[:-TAG_LENGTH]
        tag = ciphertext_with_tag[-TAG_LENGTH:]

        return {
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "iv": base64.b64encode(iv).decode("ascii"),
            "tag": base64.b64encode(tag).decode("ascii"),
        }
    except CryptoError:
        raise
    except Exception as e:
        raise CryptoError(f"加密失败: {e}") from e


def decrypt(encrypted: dict[str, str]) -> str:
    """解密密文。

    Args:
        encrypted: 加密结果字典，包含 ciphertext, iv, tag

    Returns:
        解密后的明文字符串

    Raises:
        CryptoError: 解密失败
    """
    if not encrypted or not encrypted.get("ciphertext"):
        return ""

    try:
        key = _get_encryption_key()
        ciphertext = base64.b64decode(encrypted["ciphertext"])
        iv = base64.b64decode(encrypted["iv"])
        tag = base64.b64decode(encrypted["tag"])

        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(iv, ciphertext + tag, None)

        return plaintext.decode("utf-8")
    except CryptoError:
        raise
    except Exception as e:
        raise CryptoError(f"解密失败: {e}") from e


def encrypt_config(config: dict[str, Any]) -> str:
    """加密配置字典为字符串存储。

    Args:
        config: 配置字典

    Returns:
        JSON 字符串形式的加密数据

    Raises:
        CryptoError: 加密失败
    """
    import json

    json_str = json.dumps(config, ensure_ascii=False)
    encrypted = encrypt(json_str)
    return json.dumps(encrypted, ensure_ascii=False)


def decrypt_config(encrypted_str: str) -> dict[str, Any]:
    """解密配置字符串为字典。

    Args:
        encrypted_str: JSON 字符串形式的加密数据

    Returns:
        解密后的配置字典

    Raises:
        CryptoError: 解密失败
    """
    import json

    encrypted = json.loads(encrypted_str)
    json_str = decrypt(encrypted)
    return json.loads(json_str)


def generate_key() -> str:
    """生成新的加密密钥。

    Returns:
        Base64 编码的 32 字节密钥
    """
    key = os.urandom(KEY_LENGTH)
    return base64.b64encode(key).decode("ascii")
