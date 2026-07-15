import os
import base64
import json
import logging
from typing import Any, Optional


logger = logging.getLogger(__name__)


def assert_cryptography_available() -> None:
    """Fail-closed assertion that the ``cryptography`` package is installed.

    R-P1-005: P0-7 (cryptographic downgrade) requires that the application
    refuses to encrypt/decrypt classified fields when the ``cryptography``
    library is missing, instead of silently falling back to plain base64.
    Base64 is not encryption; it provides no confidentiality.
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "SECURITY: cryptography is not installed. ODAP requires cryptography "
            "for AES-GCM encryption of classified fields. Install it with "
            "`pip install cryptography` and restart."
        ) from exc


def generate_key() -> bytes:
    return os.urandom(32)


def encrypt_field(value: str, key: bytes) -> dict:
    assert_cryptography_available()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, value.encode(), None)
    tag = ct[-16:]
    ciphertext = ct[:-16]
    return {
        "encrypted": base64.b64encode(ciphertext).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "tag": base64.b64encode(tag).decode(),
    }


def decrypt_field(encrypted: str, key: bytes, nonce: str, tag: str) -> str:
    assert_cryptography_available()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aesgcm = AESGCM(key)
    ciphertext = base64.b64decode(encrypted) + base64.b64decode(tag)
    nonce_bytes = base64.b64decode(nonce)
    plaintext = aesgcm.decrypt(nonce_bytes, ciphertext, None)
    return plaintext.decode()


class ClassifiedFieldEncryptor:
    _instance: Optional["ClassifiedFieldEncryptor"] = None
    _key: Optional[bytes] = None

    @classmethod
    def get_instance(cls) -> "ClassifiedFieldEncryptor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        key_base = os.environ.get("ENCRYPTION_KEY", "")
        if key_base:
            self._key = base64.b64decode(key_base)
        else:
            self._key = generate_key()

    def encrypt_if_classified(self, value: Any, classification_level: str) -> Any:
        if classification_level in ("TS", "S") and value is not None:
            str_value = json.dumps(value) if not isinstance(value, str) else value
            encrypted_dict = encrypt_field(str_value, self._key)
            return json.dumps(encrypted_dict)
        return value

    def decrypt_if_classified(self, value: Any, classification_level: str) -> Any:
        if classification_level in ("TS", "S") and value is not None:
            if isinstance(value, str):
                try:
                    encrypted_dict = json.loads(value)
                    decrypted = decrypt_field(
                        encrypted_dict["encrypted"],
                        self._key,
                        encrypted_dict["nonce"],
                        encrypted_dict["tag"],
                    )
                    try:
                        return json.loads(decrypted)
                    except (json.JSONDecodeError, TypeError):
                        return decrypted
                except Exception:
                    return value
        return value
