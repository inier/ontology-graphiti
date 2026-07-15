"""Regression tests for R-P1-005: cryptographic downgrade safeguards.

Verifies that the application fails-closed (raises ``RuntimeError``) when
``bcrypt`` or ``cryptography`` are missing, instead of silently falling
back to insecure alternatives.
"""
import importlib
import sys
from unittest import mock

import pytest


def test_bcrypt_assertion_raises_when_missing(monkeypatch):
    """``assert_bcrypt_available`` raises RuntimeError when bcrypt is missing.

    This is the critical fail-closed behavior — silent SHA-256 fallback is
    forbidden because SHA-256 is fast and unsalted.
    """
    from odap.infra.security import auth_service

    monkeypatch.setattr(auth_service, "BCRYPT_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="bcrypt is not installed"):
        auth_service.assert_bcrypt_available()


def test_bcrypt_assertion_passes_when_available():
    """``assert_bcrypt_available`` is a no-op when bcrypt is present."""
    from odap.infra.security import auth_service

    if not auth_service.BCRYPT_AVAILABLE:
        pytest.skip("bcrypt not installed in this environment")
    auth_service.assert_bcrypt_available()  # must not raise


def test_cryptography_assertion_raises_when_missing(monkeypatch):
    """``assert_cryptography_available`` raises when cryptography is missing.

    Falls back to base64 (no encryption) is forbidden because base64 is
    trivially reversible and provides zero confidentiality.
    """
    import builtins
    from odap.infra.security import encryption

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cryptography" or name.startswith("cryptography."):
            raise ImportError("simulated missing cryptography")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="cryptography is not installed"):
        encryption.assert_cryptography_available()


def test_cryptography_assertion_passes_when_installed():
    """``assert_cryptography_available`` is a no-op when cryptography is present."""
    from odap.infra.security import encryption

    encryption.assert_cryptography_available()  # must not raise


def test_encrypt_field_uses_aesgcm_with_real_key():
    """Happy path: encrypt_field returns dict with nonce/tag, no fallback marker."""
    from odap.infra.security.encryption import encrypt_field, decrypt_field, generate_key

    key = generate_key()
    enc = encrypt_field("top-secret", key)
    assert "encrypted" in enc
    assert enc.get("nonce"), "nonce must be set (AESGCM 12-byte nonce)"
    assert enc.get("tag"), "tag must be set (AESGCM 16-byte tag)"
    assert "fallback" not in enc, "must not use insecure base64 fallback"

    # Roundtrip
    out = decrypt_field(enc["encrypted"], key, enc["nonce"], enc["tag"])
    assert out == "top-secret"


def test_auth_service_password_hash_is_bcrypt_format():
    """When bcrypt is available, the stored hash uses the $2 prefix (bcrypt)."""
    from odap.infra.security import auth_service

    if not auth_service.BCRYPT_AVAILABLE:
        pytest.skip("bcrypt not installed in this environment")

    # Set required env vars for admin password resolution
    import os
    os.environ.setdefault("ODAP_ADMIN_PASSWORD", "test-admin-password-12345")
    os.environ.setdefault("JWT_SECRET", "x" * 32)
    os.environ.setdefault("NEO4J_PASSWORD", "x" * 16)

    svc = auth_service.AuthService()
    hashed = svc._hash_password("test-password-12345")
    assert hashed.startswith("$2"), f"expected bcrypt $2 prefix, got {hashed[:5]!r}"

    # Verify accepts it
    assert svc._verify_password("test-password-12345", hashed) is True
    assert svc._verify_password("wrong-password", hashed) is False


def test_no_silent_sha256_password_fallback_in_source():
    """Static check: _hash_password / _verify_password must not silently SHA-256.

    Forbidden patterns:
      - ``return hashlib.sha256(password.encode()).hexdigest()`` in auth_service
      - ``return hashlib.sha256(...).hexdigest() == password_hash`` in auth_service
    """
    import ast
    from pathlib import Path

    src = Path("e:/DEMO/AI/ontology-graphiti/odap/infra/security/auth_service.py")
    assert src.exists(), f"auth_service.py not found at {src}"
    source = src.read_text(encoding="utf-8")
    tree = ast.parse(source)

    bad_patterns = (
        "hashlib.sha256(password.encode()).hexdigest()",
    )

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return):
            continue
        src_line = ast.get_source_segment(source, node) or ""
        for pat in bad_patterns:
            if pat in src_line:
                offenders.append(f"line {node.lineno}: {src_line.strip()}")
    assert not offenders, (
        "Silent SHA-256 password fallback detected in auth_service.py "
        "(forbidden by R-P1-005):\n  " + "\n  ".join(offenders)
    )


def test_no_silent_base64_encryption_fallback_in_source():
    """Static check: encrypt_field / decrypt_field must not silently base64.

    Forbidden patterns:
      - ``return {"encrypted": base64.b64encode(value.encode()).decode(), ...}`` in encryption.py
    """
    import ast
    from pathlib import Path

    src = Path("e:/DEMO/AI/ontology-graphiti/odap/infra/security/encryption.py")
    assert src.exists(), f"encryption.py not found at {src}"
    source = src.read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return):
            continue
        src_line = ast.get_source_segment(source, node) or ""
        # Specifically catch the legacy base64 fallback dict.
        if '"fallback": True' in src_line or "'fallback': True" in src_line:
            offenders.append(f"line {node.lineno}: {src_line.strip()}")
    assert not offenders, (
        "Silent base64 encryption fallback detected in encryption.py "
        "(forbidden by R-P1-005):\n  " + "\n  ".join(offenders)
    )
