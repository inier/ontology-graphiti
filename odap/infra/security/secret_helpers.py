"""
Secret validation helpers (P0-8 hardening).

Provides a single source of truth for validating that secrets are properly
configured. Centralizes the list of known placeholder values and ensures
the application refuses to start with insecure defaults.

This module is the canonical way to read secrets in ODAP. Direct use of
`os.getenv("SOME_SECRET", "default_value")` is FORBIDDEN for any field whose
name matches the patterns in `SECRET_NAME_PATTERNS`.
"""
import os
import logging
from typing import Optional, FrozenSet

logger = logging.getLogger(__name__)


# ============ Known-insecure placeholder values ============
# These are sentinel strings that look like secrets but are obviously defaults.
# ANY match against this set means the secret is unconfigured.
PLACEHOLDER_VALUES: FrozenSet[str] = frozenset({
    "",
    "change-me",
    "your_jwt_secret_here",
    "default-secret-key",
    "default",
    "changeme",
    "please-change-me",
    "your-secret-here",
    "your-secret",
    "your-key-here",
    "secret",
    "your_password",
    "yourpassword",
    "password",
    "admin123",
    "admin",
    "minioadmin",
    "minio",
    "neo4j",
    "neo4jpassword",
    "test",
    "demo",
})

# ============ Substring patterns that indicate a default value ============
# These catch cases like "change-me-in-production" or "TODO-set-secret".
PLACEHOLDER_SUBSTRINGS: FrozenSet[str] = frozenset({
    "change-me",
    "changeme",
    "your-",
    "your_",
    "please-change",
    "set-me",
    "todo-",
    "todo:",
    "fixme-",
})


# ============ Field name patterns that trigger strict validation ============
SECRET_NAME_PATTERNS: FrozenSet[str] = frozenset({
    "secret",
    "password",
    "key",
    "token",
    "credential",
})


class SecretValidationError(RuntimeError):
    """Raised when a required secret is missing or has a placeholder value."""
    pass


def _is_placeholder(value: str) -> bool:
    """Check if a secret value is a known-insecure placeholder."""
    if not value:
        return True
    val_lower = value.lower().strip()
    if val_lower in PLACEHOLDER_VALUES:
        return True
    for pattern in PLACEHOLDER_SUBSTRINGS:
        if pattern in val_lower:
            return True
    # Length check: real secrets are typically >= 16 chars
    if len(value) < 8:
        return True
    return False


def _is_secret_field_name(name: str) -> bool:
    """Check if a field name suggests it holds a secret."""
    name_lower = name.lower()
    return any(pattern in name_lower for pattern in SECRET_NAME_PATTERNS)


def get_required_secret(
    env_var: str,
    *,
    min_length: int = 16,
    allow_dev_placeholder: bool = False,
) -> str:
    """
    Get a required secret from environment variables with strict validation.

    Args:
        env_var: Name of the environment variable to read.
        min_length: Minimum length of the secret (default 16).
        allow_dev_placeholder: If True, allows placeholder values in non-production.
            Should only be used for test fixtures.

    Returns:
        The validated secret value.

    Raises:
        SecretValidationError: If the env var is missing, has a placeholder value,
            or is shorter than `min_length`.
    """
    value = os.getenv(env_var)

    if value is None or value == "":
        raise SecretValidationError(
            f"SECURITY: {env_var} is not set. "
            f"Set {env_var} in your environment or secrets manager."
        )

    if _is_placeholder(value):
        # Allow placeholder in dev/test, but NEVER in production
        if allow_dev_placeholder and not _is_production_env():
            logger.warning(
                f"SECURITY: {env_var} is a placeholder value, "
                f"but allow_dev_placeholder=True. This must NEVER be set in production."
            )
            return value
        raise SecretValidationError(
            f"SECURITY: {env_var} has a placeholder value. "
            f"Replace with a real secret of at least {min_length} characters."
        )

    if len(value) < min_length:
        raise SecretValidationError(
            f"SECURITY: {env_var} is too short (got {len(value)} chars, "
            f"need >= {min_length})."
        )

    return value


def get_optional_secret(env_var: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get an optional secret (e.g. for third-party API keys).

    Returns the env var value if set and not a placeholder, otherwise the default.
    Returns None if no default is given and the env var is unset.
    """
    value = os.getenv(env_var)
    if value is None or value == "" or _is_placeholder(value):
        return default
    return value


def generate_random_secret(length: int = 32) -> str:
    """Generate a cryptographically-random secret for first-startup use."""
    import secrets
    return secrets.token_urlsafe(length)


def is_valid_secret(env_var: str) -> bool:
    """Non-raising check: is the env var set to a non-placeholder value?"""
    try:
        get_required_secret(env_var)
        return True
    except SecretValidationError:
        return False


def _is_production_env() -> bool:
    """Check whether the current process is running in production."""
    env = os.environ.get("ENV", os.environ.get("ENVIRONMENT", "")).lower()
    return env in ("production", "prod", "live")
