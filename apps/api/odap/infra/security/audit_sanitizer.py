#!/usr/bin/env python3
"""
审计日志脱敏器

白皮书 §5: 日志脱敏 (Log Sanitization)
审计日志在写入前，对敏感凭证（API Key、密码、Token）自动脱敏，防止二次泄露。

用法:
    from odap.infra.security.audit_sanitizer import sanitize_audit_data
    safe_data = sanitize_audit_data({"api_key": "sk-xxx", "user": "alice"})
    # → {"api_key": "***REDACTED***", "user": "alice"}
"""

import re
import copy
from typing import Any, Dict

# ---------------------------------------------------------------------------
# 敏感字段名模式（大小写不敏感，匹配 key 名）
# ---------------------------------------------------------------------------
SENSITIVE_KEY_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(?i)(password|passwd|pwd|secret|api[_-]?key|access[_-]?key|"
        r"auth[_-]?token|bearer|credential|private[_-]?key|client[_-]?secret|"
        r"refresh[_-]?token|session[_-]?token|jwt|authorization)"
    ),
]

# ---------------------------------------------------------------------------
# 敏感值模式（直接匹配值内容）
# ---------------------------------------------------------------------------
SENSITIVE_VALUE_PATTERNS: list[re.Pattern] = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),                     # OpenAI API Key
    re.compile(r"AKIA[A-Z0-9]{16}"),                        # AWS Access Key ID
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),              # GitHub Token
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"),     # Bearer Token
    re.compile(r"(?i)-----BEGIN [A-Z ]+PRIVATE KEY-----"),  # PEM 私钥头
]

REDACTED = "***REDACTED***"

_MAX_DEPTH = 10


def sanitize_value(value: Any, depth: int = 0) -> Any:
    """递归脱敏任意值。

    - dict: 逐 key 检查，key 名命中模式则整体脱敏，否则递归处理 value
    - list: 逐元素递归
    - str: 检查值是否匹配敏感值模式
    - 其他类型: 原样返回
    """
    if depth > _MAX_DEPTH:
        return REDACTED

    if isinstance(value, dict):
        return {k: _sanitize_key_value(k, v, depth + 1) for k, v in value.items()}

    if isinstance(value, list):
        return [sanitize_value(v, depth + 1) for v in value]

    if isinstance(value, str):
        for pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(value):
                return REDACTED

    return value


def _sanitize_key_value(key: Any, value: Any, depth: int) -> Any:
    """如果 key 名匹配敏感模式，整体脱敏 value；否则递归处理 value。"""
    key_str = str(key)
    for pattern in SENSITIVE_KEY_PATTERNS:
        if pattern.search(key_str):
            return REDACTED
    return sanitize_value(value, depth)


def sanitize_audit_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """脱敏审计数据的顶层入口。

    深拷贝后递归脱敏，不修改原始数据。
    """
    if not data or not isinstance(data, dict):
        return data
    sanitized = copy.deepcopy(data)
    return sanitize_value(sanitized)


__all__ = [
    "SENSITIVE_KEY_PATTERNS",
    "SENSITIVE_VALUE_PATTERNS",
    "REDACTED",
    "sanitize_value",
    "sanitize_audit_data",
]
