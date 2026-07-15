"""
JWT 服务单元测试 - 对齐 odap/infra/security/jwt_service.py

覆盖:
- Token 生成 (access + refresh)
- Token 验证 (有效、过期、畸形、错误密钥)
- Token 刷新流程
- 角色提取
- 工作空间隔离
- jwt_auth 中间件解码
"""

import time
import pytest
import jwt as pyjwt
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Test-only JWT secret. MUST be ≥ 32 bytes per RFC 7518 §3.2
# (HMAC-SHA256 key length recommendation).
TEST_JWT_SECRET = "test_secret_key_for_unit_tests_padded_to_32bytes"  # 43 bytes


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def jwt_service():
    """创建使用固定密钥的 JWTService 实例"""
    from odap.infra.security.jwt_service import JWTService
    return JWTService(secret_key=TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def sample_access_token(jwt_service):
    """生成一个示例 access token"""
    return jwt_service.issue_access_token(
        user_id="user-001",
        user_name="testuser",
        role="admin",
        workspace_id="ws-001",
        workspace_role="commander",
    )


@pytest.fixture
def sample_refresh_token(jwt_service):
    """生成一个示例 refresh token"""
    return jwt_service.issue_refresh_token(
        user_id="user-001",
        workspace_id="ws-001",
    )


# ===========================================================================
# TestJWTService - Token 生成
# ===========================================================================

class TestJWTServiceTokenGeneration:
    """Token 生成测试"""

    def test_issue_access_token_returns_string(self, jwt_service):
        """access token 应返回非空字符串"""
        token = jwt_service.issue_access_token(
            user_id="user-001", user_name="testuser", role="admin"
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_issue_access_token_contains_required_claims(self, jwt_service):
        """access token 应包含 iss, sub, name, exp, iat, role, ws_id, ws_role"""
        token = jwt_service.issue_access_token(
            user_id="user-001",
            user_name="testuser",
            role="admin",
            workspace_id="ws-001",
            workspace_role="commander",
        )
        decoded = pyjwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
        assert decoded["iss"] == "odap"
        assert decoded["sub"] == "user-001"
        assert decoded["name"] == "testuser"
        assert decoded["role"] == "admin"
        assert decoded["ws_id"] == "ws-001"
        assert decoded["ws_role"] == "commander"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_issue_access_token_default_workspace_fields(self, jwt_service):
        """access token 未指定 workspace 时 ws_id 为空, ws_role 等于 role"""
        token = jwt_service.issue_access_token(
            user_id="user-002", user_name="guest", role="observer"
        )
        decoded = pyjwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
        assert decoded["ws_id"] == ""
        assert decoded["ws_role"] == "observer"

    def test_issue_refresh_token_returns_string(self, jwt_service):
        """refresh token 应返回非空字符串"""
        token = jwt_service.issue_refresh_token(user_id="user-001")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_issue_refresh_token_contains_required_claims(self, jwt_service):
        """refresh token 应包含 iss, sub, exp, iat, type, ws_id"""
        token = jwt_service.issue_refresh_token(
            user_id="user-001", workspace_id="ws-001"
        )
        decoded = pyjwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
        assert decoded["iss"] == "odap"
        assert decoded["sub"] == "user-001"
        assert decoded["type"] == "refresh"
        assert decoded["ws_id"] == "ws-001"
        assert "exp" in decoded
        assert "iat" in decoded


# ===========================================================================
# TestJWTService - Token 验证
# ===========================================================================

class TestJWTServiceTokenValidation:
    """Token 验证测试"""

    def test_verify_valid_access_token(self, jwt_service, sample_access_token):
        """验证有效的 access token 应返回 JWTPayload"""
        payload = jwt_service.verify_token(sample_access_token)
        assert payload.sub == "user-001"
        assert payload.role == "admin"
        assert payload.ws_id == "ws-001"
        assert payload.ws_role == "commander"

    def test_verify_valid_refresh_token(self, jwt_service, sample_refresh_token):
        """验证有效的 refresh token 应返回 JWTPayload"""
        payload = jwt_service.verify_token(sample_refresh_token)
        assert payload.sub == "user-001"

    def test_verify_expired_token_raises_error(self, jwt_service):
        """验证过期的 token 应抛出 ExpiredSignatureError"""
        # 手动构造一个已过期的 token
        now = datetime.now(timezone.utc)
        expired_payload = {
            "iss": "odap",
            "sub": "user-001",
            "exp": int((now - timedelta(hours=1)).timestamp()),
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "role": "admin",
        }
        expired_token = pyjwt.encode(expired_payload, TEST_JWT_SECRET, algorithm="HS256")

        with pytest.raises(pyjwt.ExpiredSignatureError):
            jwt_service.verify_token(expired_token)

    def test_verify_malformed_token_raises_error(self, jwt_service):
        """验证畸形 token 应抛出 InvalidTokenError"""
        with pytest.raises(pyjwt.InvalidTokenError):
            jwt_service.verify_token("this.is.not.a.valid.token")

    def test_verify_token_with_wrong_secret_raises_error(self, jwt_service):
        """使用错误密钥签名的 token 应验证失败"""
        # 用另一个 ≥32 字节的密钥签名（避免 PyJWT InsecureKeyLengthWarning）
        wrong_token = pyjwt.encode(
            {"iss": "odap", "sub": "user-001", "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()), "iat": int(datetime.now(timezone.utc).timestamp())},
            "wrong_secret_but_long_enough_to_be_secure_2026",
            algorithm="HS256",
        )
        with pytest.raises(pyjwt.InvalidSignatureError):
            jwt_service.verify_token(wrong_token)

    def test_verify_token_raw_returns_dict(self, jwt_service, sample_access_token):
        """verify_token_raw 应返回原始 dict"""
        result = jwt_service.verify_token_raw(sample_access_token)
        assert isinstance(result, dict)
        assert result["sub"] == "user-001"
        assert result["role"] == "admin"


# ===========================================================================
# TestJWTService - Token 刷新流程
# ===========================================================================

class TestJWTServiceTokenRefresh:
    """Token 刷新流程测试"""

    def test_access_token_ttl_is_15_minutes(self, jwt_service):
        """access token TTL 应为 15 分钟"""
        assert jwt_service.ACCESS_TTL == timedelta(minutes=15)

    def test_refresh_token_ttl_is_7_days(self, jwt_service):
        """refresh token TTL 应为 7 天"""
        assert jwt_service.REFRESH_TTL == timedelta(days=7)

    def test_access_and_refresh_tokens_are_different(self, jwt_service):
        """同一用户同时签发的 access 和 refresh token 应不同"""
        access = jwt_service.issue_access_token("user-001", "test", "admin")
        refresh = jwt_service.issue_refresh_token("user-001")
        assert access != refresh


# ===========================================================================
# TestJWTService - 角色提取
# ===========================================================================

class TestJWTRoleExtraction:
    """角色提取测试"""

    def test_role_extraction_from_access_token(self, jwt_service):
        """从 access token 中提取 role"""
        token = jwt_service.issue_access_token(
            user_id="user-001", user_name="test", role="commander"
        )
        payload = jwt_service.verify_token(token)
        assert payload.role == "commander"

    def test_role_extraction_observer_default(self, jwt_service):
        """未指定 role 时 JWTPayload 默认为 observer"""
        # 手动构造不含 role 的 token（绕过 issue 方法默认值）
        now = datetime.now(timezone.utc)
        payload_dict = {
            "iss": "odap",
            "sub": "user-001",
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iat": int(now.timestamp()),
        }
        token = pyjwt.encode(payload_dict, TEST_JWT_SECRET, algorithm="HS256")
        payload = jwt_service.verify_token(token)
        assert payload.role == "observer"


# ===========================================================================
# TestJWTService - 工作空间隔离
# ===========================================================================

class TestJWTWorkspaceIsolation:
    """工作空间隔离测试"""

    def test_workspace_id_in_token(self, jwt_service):
        """token 中应包含 ws_id"""
        token = jwt_service.issue_access_token(
            user_id="user-001", user_name="test", role="admin",
            workspace_id="ws-42"
        )
        payload = jwt_service.verify_token(token)
        assert payload.ws_id == "ws-42"

    def test_different_workspaces_produce_different_tokens(self, jwt_service):
        """不同工作空间应产生不同的 token"""
        time.sleep(1.1)  # 确保 iat 不同
        token_ws1 = jwt_service.issue_access_token(
            user_id="user-001", user_name="test", role="admin",
            workspace_id="ws-001"
        )
        time.sleep(1.1)
        token_ws2 = jwt_service.issue_access_token(
            user_id="user-001", user_name="test", role="admin",
            workspace_id="ws-002"
        )
        assert token_ws1 != token_ws2

    def test_workspace_role_in_token(self, jwt_service):
        """token 中应包含 ws_role"""
        token = jwt_service.issue_access_token(
            user_id="user-001", user_name="test", role="admin",
            workspace_id="ws-001", workspace_role="analyst"
        )
        payload = jwt_service.verify_token(token)
        assert payload.ws_role == "analyst"


# ===========================================================================
# TestJWTAuthMiddleware - jwt_auth 解码
# ===========================================================================

class TestJWTAuthMiddleware:
    """jwt_auth 中间件解码测试"""

    def test_decode_valid_token(self, jwt_service, monkeypatch):
        """decode_token 应成功解码有效 token"""
        from odap.infra.security.jwt_auth import decode_token

        # P0-8: JWT_SECRET is no longer a class attribute. Use env var.
        monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
        monkeypatch.setenv("JWT_ALGORITHM", "HS256")

        token = jwt_service.issue_access_token("user-001", "test", "admin")
        payload = decode_token(token)
        assert payload["sub"] == "user-001"
        assert payload["role"] == "admin"

    def test_decode_expired_token_raises_401(self, jwt_service, monkeypatch):
        """decode_token 对过期 token 应抛出 401 HTTPException"""
        from odap.infra.security.jwt_auth import decode_token
        from fastapi import HTTPException

        monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
        monkeypatch.setenv("JWT_ALGORITHM", "HS256")

        now = datetime.now(timezone.utc)
        expired_payload = {
            "iss": "odap",
            "sub": "user-001",
            "exp": int((now - timedelta(hours=1)).timestamp()),
            "iat": int((now - timedelta(hours=2)).timestamp()),
        }
        expired_token = pyjwt.encode(expired_payload, TEST_JWT_SECRET, algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            decode_token(expired_token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_decode_invalid_token_raises_401(self):
        """decode_token 对无效 token 应抛出 401 HTTPException"""
        from odap.infra.security.jwt_auth import decode_token
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid.token.string")
        assert exc_info.value.status_code == 401
        assert "invalid" in exc_info.value.detail.lower()
