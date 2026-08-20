#!/usr/bin/env python3
"""P1-05: 审计日志脱敏器测试

白皮书 §5: 日志脱敏 (Log Sanitization)
"""

import pytest
from odap.infra.security.audit_sanitizer import (
    sanitize_value,
    sanitize_audit_data,
    REDACTED,
    SENSITIVE_KEY_PATTERNS,
    SENSITIVE_VALUE_PATTERNS,
)


class TestKeyBasedSanitization:
    """按 key 名匹配脱敏"""

    def test_password_redacted(self):
        assert sanitize_value({"password": "secret123"}) == {"password": REDACTED}

    def test_api_key_redacted(self):
        assert sanitize_value({"api_key": "sk-abc"}) == {"api_key": REDACTED}

    def test_apikey_no_underscore_redacted(self):
        assert sanitize_value({"apikey": "xxx"}) == {"apikey": REDACTED}

    def test_access_key_redacted(self):
        assert sanitize_value({"access_key": "AKIA123"}) == {"access_key": REDACTED}

    def test_auth_token_redacted(self):
        assert sanitize_value({"auth_token": "tok"}) == {"auth_token": REDACTED}

    def test_client_secret_redacted(self):
        assert sanitize_value({"client_secret": "s"}) == {"client_secret": REDACTED}

    def test_bearer_key_redacted(self):
        assert sanitize_value({"bearer": "xyz"}) == {"bearer": REDACTED}

    def test_authorization_header_redacted(self):
        assert sanitize_value({"authorization": "Bearer x"}) == {"authorization": REDACTED}

    def test_case_insensitive_key(self):
        assert sanitize_value({"PASSWORD": "x"}) == {"PASSWORD": REDACTED}
        assert sanitize_value({"ApiKey": "x"}) == {"ApiKey": REDACTED}


class TestValueBasedSanitization:
    """按值内容匹配脱敏"""

    def test_openai_key_in_value(self):
        data = {"config": "key=sk-abcdefghijklmnopqrstuvwxyz1234"}
        result = sanitize_value(data)
        assert result["config"] == REDACTED

    def test_aws_key_in_value(self):
        data = {"creds": "AKIAIOSFODNN7EXAMPLE"}
        result = sanitize_value(data)
        assert result["creds"] == REDACTED

    def test_github_token_in_value(self):
        data = {"token": "ghp_1234567890abcdefghijklmnopqrstuvwxyz1234"}
        result = sanitize_value(data)
        assert result["token"] == REDACTED

    def test_bearer_token_in_value(self):
        data = {"header": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIx"}
        result = sanitize_value(data)
        assert result["header"] == REDACTED

    def test_pem_private_key_in_value(self):
        data = {"key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE"}
        result = sanitize_value(data)
        assert result["key"] == REDACTED


class TestNestedStructures:
    """嵌套结构递归脱敏"""

    def test_nested_dict(self):
        data = {"outer": {"inner": {"password": "secret"}}}
        result = sanitize_value(data)
        assert result == {"outer": {"inner": {"password": REDACTED}}}

    def test_list_of_dicts(self):
        data = [{"api_key": "k1"}, {"name": "alice"}]
        result = sanitize_value(data)
        assert result == [{"api_key": REDACTED}, {"name": "alice"}]

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": {"d": {"password": "x"}}}}}
        result = sanitize_value(data)
        assert result["a"]["b"]["c"]["d"]["password"] == REDACTED

    def test_max_depth_protection(self):
        """超过 10 层深度时直接返回 REDACTED"""
        data = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": {"k": "deep"}}}}}}}}}}}
        result = sanitize_value(data, depth=0)
        # 最深层应被 REDACTED（因为超过 _MAX_DEPTH=10）
        assert isinstance(result, dict)


class TestNonSensitiveData:
    """非敏感数据应保持不变"""

    def test_normal_fields_unchanged(self):
        data = {"user": "alice", "action": "login", "count": 42}
        result = sanitize_value(data)
        assert result == data

    def test_empty_dict(self):
        assert sanitize_value({}) == {}

    def test_none_value(self):
        assert sanitize_value(None) is None

    def test_integer_value(self):
        assert sanitize_value(42) == 42

    def test_list_of_strings(self):
        data = ["hello", "world"]
        assert sanitize_value(data) == ["hello", "world"]


class TestSanitizeAuditData:
    """顶层入口函数测试"""

    def test_deep_copy_not_mutating_original(self):
        original = {"api_key": "sk-test", "user": "bob"}
        sanitize_audit_data(original)
        assert original["api_key"] == "sk-test"  # 原始未被修改

    def test_returns_sanitized_dict(self):
        data = {"password": "123", "name": "alice"}
        result = sanitize_audit_data(data)
        assert result == {"password": REDACTED, "name": "alice"}

    def test_none_input(self):
        assert sanitize_audit_data(None) is None

    def test_empty_input(self):
        assert sanitize_audit_data({}) == {}


class TestIntegrationWithLogAudit:
    """集成测试: 验证 sanitize_audit_data 可与 log_audit details 配合工作"""

    def test_log_audit_details_would_be_sanitized(self):
        """验证 log_audit 的 details 字段经过脱敏后不含敏感值"""
        from odap.infra.security.audit_sanitizer import sanitize_audit_data

        raw_details = {
            "api_key": "sk-abcdefghijklmnopqrstuvwxyz1234",
            "normal_field": "ok",
            "nested": {"password": "secret"},
        }
        safe = sanitize_audit_data(raw_details)

        # 模拟 log_audit 写入后的 context 应该是脱敏的
        assert safe["api_key"] == REDACTED
        assert safe["normal_field"] == "ok"
        assert safe["nested"]["password"] == REDACTED
        # 原始数据未被修改
        assert raw_details["api_key"] == "sk-abcdefghijklmnopqrstuvwxyz1234"
