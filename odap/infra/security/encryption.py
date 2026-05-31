import os
import base64


def generate_key() -> bytes:
    return os.urandom(32)


def encrypt_field(value: str, key: bytes) -> dict:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        return {"encrypted": base64.b64encode(value.encode()).decode(), "nonce": "", "tag": "", "fallback": True}

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
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        return base64.b64decode(encrypted).decode()

    aesgcm = AESGCM(key)
    ciphertext = base64.b64decode(encrypted) + base64.b64decode(tag)
    nonce_bytes = base64.b64decode(nonce)
    plaintext = aesgcm.decrypt(nonce_bytes, ciphertext, None)
    return plaintext.decode()
