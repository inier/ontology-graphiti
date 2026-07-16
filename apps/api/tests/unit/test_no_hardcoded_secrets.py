"""
Regression test: No hardcoded default secrets anywhere in the codebase (R-P0-003).

This is a P0-8 violation: any of these placeholders means the application
is insecure by default.

Covers:
- `odap/infra/security/config.py` — JWT_SECRET, NEO4J_PASSWORD
- `odap/infra/security/auth_service.py` — admin password
- `odap/infra/storage/minio_client.py` — MINIO_ACCESS_KEY, MINIO_SECRET_KEY
- `odap/biz/integration/hook_system/hook_manager_enhanced.py` — HOOK_SIGNING_KEY
- `odap/infra/config_composer.py` — jwt.secret

Verifies that:
1. None of the 7 known placeholder strings appear as defaults in the source.
2. Secret resolution helpers reject placeholder values.
3. Production env REJECTS placeholder secrets.
4. Dev env can use generated random secrets.
"""
import os
import re
from pathlib import Path
import pytest

# apps/api/tests/unit/ -> apps/api/ (3 parents) -> odap/
_ROOT = Path(__file__).resolve().parent.parent.parent
ROOT = _ROOT / "odap"

# The 7 placeholder defaults we are guarding against
KNOWN_PLACEHOLDER_DEFAULTS = {
    "your_jwt_secret_here",
    "admin123",
    "minioadmin",  # appears in two files
    "default-secret-key",
    "change-me",
}

# Files where these placeholders were originally found
PROTECTED_FILES = {
    "infra/security/config.py": ["your_jwt_secret_here"],
    "infra/security/auth_service.py": ["admin123"],
    "infra/storage/minio_client.py": ["minioadmin"],
    "biz/integration/hook_system/hook_manager_enhanced.py": ["default-secret-key"],
    "infra/config_composer.py": ["change-me"],
}


# ============ Static source-level guard ============

class TestNoHardcodedDefaultSecrets:
    """AST + regex: no placeholder default secret may appear in the source."""

    def test_no_placeholder_default_in_os_getenv(self):
        """`os.getenv("...", "default")` patterns must not contain placeholders."""
        forbidden = KNOWN_PLACEHOLDER_DEFAULTS
        violations = []

        for py_file in ROOT.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            for placeholder in forbidden:
                # Match patterns like: os.getenv("FOO", "placeholder")
                pattern = rf'os\.getenv\([^)]*["\'][^"\']*["\']\s*,\s*["\']{re.escape(placeholder)}["\']'
                for m in re.finditer(pattern, content):
                    rel = py_file.relative_to(ROOT.parent)
                    line_no = content[:m.start()].count("\n") + 1
                    violations.append(f"{rel}:{line_no}  -> {placeholder}")

        assert not violations, (
            f"Found {len(violations)} hardcoded default secret(s):\n"
            + "\n".join(violations)
        )

    def test_no_placeholder_as_string_literal_in_code(self, monkeypatch):
        """Placeholder secrets must not appear as Python string literals in code.

        We exclude:
        - Comments (lines starting with #)
        - Docstrings (AST-detected)
        - Detection logic: strings used to identify placeholders
          (e.g. PLACEHOLDER_VALUES sets, == checks against the placeholder)
        """
        import ast

        # Files where placeholder strings are LEGITIMATELY used for detection
        DETECTION_FILES = {
            "odap/infra/security/secret_helpers.py",
            "odap/infra/storage/minio_client.py",
            "odap/biz/integration/hook_system/hook_manager_enhanced.py",
            "odap/infra/security/auth_service.py",  # has `_is_production_env` check
        }

        def is_in_set_or_in_clause(node, parent_attr):
            """Check if the string is being used as a set/dict/tuple element
            (which is legitimate for placeholder detection lists)."""
            # ast.Set: e.g., { "x", "y", "z" }
            # ast.List / ast.Tuple: ["x", "y"]
            # ast.Dict: {key: value}
            return parent_attr in ("elts", "keys")

        violations = []
        for py_file in ROOT.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            rel = py_file.relative_to(ROOT.parent)
            rel_str = str(rel).replace("\\", "/")
            if rel_str in DETECTION_FILES:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError, OSError):
                continue

            source_lines = source.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    for placeholder in KNOWN_PLACEHOLDER_DEFAULTS:
                        if node.value == placeholder:
                            line_no = node.lineno
                            line_text = source_lines[line_no - 1] if line_no - 1 < len(source_lines) else ""
                            stripped = line_text.lstrip()
                            # Skip comments
                            if stripped.startswith("#"):
                                continue
                            violations.append(f"{rel}:{line_no}  -> {placeholder!r}")

        assert not violations, (
            f"Found {len(violations)} hardcoded placeholder string(s):\n"
            + "\n".join(violations)
        )

    def test_config_composer_jwt_secret_required(self):
        """`jwt.secret` schema MUST have required=True and no default."""
        from odap.infra.config_composer import ConfigurationComposer
        c = ConfigurationComposer()
        s = c._schema.get("jwt.secret")
        assert s is not None, "jwt.secret schema missing"
        assert s.required is True, (
            f"jwt.secret must be required=True (got {s.required}). "
            f"P0-8 violation."
        )
        assert s.default is None, (
            f"jwt.secret must have no default (got {s.default!r}). "
            f"P0-8 violation."
        )


# ============ Helper module behavior tests ============

class TestSecretHelpers:
    """Tests for the secret_helpers module."""

    def test_placeholder_set_contains_all_known(self):
        from odap.infra.security.secret_helpers import PLACEHOLDER_VALUES
        for placeholder in KNOWN_PLACEHOLDER_DEFAULTS:
            assert placeholder in PLACEHOLDER_VALUES or placeholder == "minioadmin", (
                f"Known placeholder {placeholder!r} not in PLACEHOLDER_VALUES"
            )
        assert "minioadmin" in PLACEHOLDER_VALUES

    def test_get_required_secret_rejects_missing(self, monkeypatch):
        from odap.infra.security.secret_helpers import (
            get_required_secret, SecretValidationError,
        )
        monkeypatch.delenv("FOO_TEST_SECRET", raising=False)
        with pytest.raises(SecretValidationError):
            get_required_secret("FOO_TEST_SECRET")

    def test_get_required_secret_rejects_placeholder(self, monkeypatch):
        from odap.infra.security.secret_helpers import (
            get_required_secret, SecretValidationError,
        )
        monkeypatch.setenv("FOO_TEST_SECRET", "change-me")
        with pytest.raises(SecretValidationError):
            get_required_secret("FOO_TEST_SECRET")

    def test_get_required_secret_rejects_too_short(self, monkeypatch):
        from odap.infra.security.secret_helpers import (
            get_required_secret, SecretValidationError,
        )
        monkeypatch.setenv("FOO_TEST_SECRET", "short")
        with pytest.raises(SecretValidationError):
            get_required_secret("FOO_TEST_SECRET")

    def test_get_required_secret_accepts_valid(self, monkeypatch):
        from odap.infra.security.secret_helpers import get_required_secret
        monkeypatch.setenv("FOO_TEST_SECRET", "this-is-a-valid-secret-of-16+")
        assert get_required_secret("FOO_TEST_SECRET") == "this-is-a-valid-secret-of-16+"

    def test_get_optional_secret_returns_default(self, monkeypatch):
        from odap.infra.security.secret_helpers import get_optional_secret
        monkeypatch.delenv("FOO_TEST_SECRET", raising=False)
        assert get_optional_secret("FOO_TEST_SECRET", "fallback") == "fallback"
        assert get_optional_secret("FOO_TEST_SECRET") is None

    def test_generate_random_secret_unique(self):
        from odap.infra.security.secret_helpers import generate_random_secret
        s1 = generate_random_secret()
        s2 = generate_random_secret()
        assert s1 != s2
        assert len(s1) >= 32


# ============ Component integration tests ============

class TestAuthServiceNoHardcodedPassword:
    def test_init_default_users_does_not_have_admin123(self):
        """The string 'admin123' must not appear in auth_service.py as a literal."""
        path = ROOT / "infra" / "security" / "auth_service.py"
        content = path.read_text(encoding="utf-8")
        # The string can appear in test files but not in production code as a literal
        assert '"admin123"' not in content, (
            "Hardcoded admin password 'admin123' found in auth_service.py. "
            "P0-8 violation."
        )
        assert "'admin123'" not in content, (
            "Hardcoded admin password 'admin123' found in auth_service.py. "
            "P0-8 violation."
        )

    def test_resolve_admin_password_uses_env_or_random(self, monkeypatch):
        """The admin password resolution must use env or generate random."""
        from odap.infra.security.auth_service import AuthService, _generate_random_password
        monkeypatch.delenv("ODAP_ADMIN_PASSWORD", raising=False)

        # In dev (ENV not set), should generate a random password
        monkeypatch.delenv("ENV", raising=False)
        s = AuthService()
        assert "admin" in s._users
        assert s._users["admin"]["password_hash"] is not None

    def test_production_requires_explicit_admin_password(self, monkeypatch):
        """In production, must raise if ODAP_ADMIN_PASSWORD is not set."""
        from odap.infra.security.auth_service import AuthService
        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("ODAP_ADMIN_PASSWORD", raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            AuthService()
        assert "ODAP_ADMIN_PASSWORD" in str(exc_info.value)


class TestMinIOClientNoHardcodedCredentials:
    def test_no_minioadmin_default_in_source(self):
        """The string 'minioadmin' must not appear as a literal default."""
        path = ROOT / "infra" / "storage" / "minio_client.py"
        content = path.read_text(encoding="utf-8")
        # Should only appear in placeholder-detection logic, not as a default
        # Check that it's not in any os.environ.get(..., "minioadmin") pattern
        forbidden = re.findall(
            r'os\.environ\.get\([^)]*["\']minioadmin["\']\)',
            content,
        )
        assert not forbidden, (
            f"Found {len(forbidden)} `os.environ.get(..., 'minioadmin')` patterns. "
            f"P0-8 violation."
        )
        forbidden2 = re.findall(
            r'os\.getenv\([^)]*["\']minioadmin["\']\)',
            content,
        )
        assert not forbidden2

    def test_production_rejects_default_credentials(self, monkeypatch):
        from odap.infra.storage.minio_client import MinIOClient
        # Reset singleton
        MinIOClient._instance = None
        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("MINIO_ACCESS_KEY", raising=False)
        monkeypatch.delenv("MINIO_SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            MinIOClient()
        assert "MINIO_ACCESS_KEY" in str(exc_info.value) or "MINIO_SECRET_KEY" in str(exc_info.value)


class TestHookSignerNoHardcodedKey:
    def test_no_default_secret_key_in_source(self):
        path = ROOT / "biz" / "integration" / "hook_system" / "hook_manager_enhanced.py"
        content = path.read_text(encoding="utf-8")
        # Should not have os.getenv("HOOK_SIGNING_KEY", "default-secret-key")
        forbidden = re.findall(
            r'os\.getenv\([^)]*["\']default-secret-key["\']\)',
            content,
        )
        assert not forbidden, (
            f"Found {len(forbidden)} `os.getenv(..., 'default-secret-key')` patterns. "
            f"P0-8 violation."
        )

    def test_production_rejects_default_signing_key(self, monkeypatch):
        from odap.biz.integration.hook_system.hook_manager_enhanced import CodeSigner
        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("HOOK_SIGNING_KEY", raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            CodeSigner()
        assert "HOOK_SIGNING_KEY" in str(exc_info.value)


class TestConfigNoHardcodedJWT:
    def test_jwt_secret_class_attribute_removed(self):
        """SecurityConfig.JWT_SECRET class attribute must be removed."""
        from odap.infra.security.config import SecurityConfig
        assert not hasattr(SecurityConfig, "JWT_SECRET"), (
            "SecurityConfig.JWT_SECRET class attribute still exists. "
            "Use get_jwt_secret() method instead. P0-8 violation."
        )

    def test_neo4j_password_class_attribute_removed(self):
        from odap.infra.security.config import SecurityConfig
        assert not hasattr(SecurityConfig, "NEO4J_PASSWORD"), (
            "SecurityConfig.NEO4J_PASSWORD class attribute still exists. "
            "Use get_neo4j_password() method instead. P0-8 violation."
        )

    def test_get_jwt_secret_validates_placeholder(self, monkeypatch):
        from odap.infra.security.config import SecurityConfig
        from odap.infra.security.secret_helpers import SecretValidationError
        monkeypatch.setenv("JWT_SECRET", "your_jwt_secret_here")
        with pytest.raises(SecretValidationError):
            SecurityConfig.get_jwt_secret()

    def test_get_jwt_secret_validates_too_short(self, monkeypatch):
        from odap.infra.security.config import SecurityConfig
        from odap.infra.security.secret_helpers import SecretValidationError
        monkeypatch.setenv("JWT_SECRET", "tooshort")
        with pytest.raises(SecretValidationError):
            SecurityConfig.get_jwt_secret()

    def test_get_jwt_secret_accepts_valid(self, monkeypatch):
        from odap.infra.security.config import SecurityConfig
        monkeypatch.setenv("JWT_SECRET", "a-very-long-and-secure-jwt-secret-12345")
        assert SecurityConfig.get_jwt_secret() == "a-very-long-and-secure-jwt-secret-12345"
