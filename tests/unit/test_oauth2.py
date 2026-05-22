"""
OAuth2 认证流程单元测试 - 对齐 docs/03-modules/auth/DESIGN.md §2.2

覆盖:
- OAuth2 Provider 注册/发现
- 授权 URL 生成 (PKCE)
- Token 交换流程
- 用户信息获取
- AuthService OAuth2 集成
- API Key 边界测试
"""

import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odap.infra.security.auth_service import AuthService, LoginRateLimiter
from odap.infra.security.auth_models import AuthProvider, GlobalRole, APIKeyRecord
from odap.infra.security.oauth2_providers import (
    OAuth2ProviderConfig,
    OAuth2ProviderRegistry,
    OAuth2Service,
    OAuth2State,
    OAuth2TokenResponse,
    OAuth2UserInfo,
)


class TestOAuth2ProviderRegistry:
    def setup_method(self):
        self.registry = OAuth2ProviderRegistry()

    def test_register_provider(self):
        config = OAuth2ProviderConfig(
            provider_id="test_provider",
            display_name="Test Provider",
            authorization_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            userinfo_url="https://auth.example.com/userinfo",
            client_id="test_client_id",
            client_secret="test_client_secret",
        )
        self.registry.register_provider(config)

        provider = self.registry.get_provider("test_provider")
        assert provider is not None
        assert provider.provider_id == "test_provider"
        assert provider.client_id == "test_client_id"

    def test_get_nonexistent_provider(self):
        provider = self.registry.get_provider("nonexistent")
        assert provider is None

    def test_list_providers(self):
        config = OAuth2ProviderConfig(
            provider_id="custom",
            display_name="Custom",
            authorization_url="https://auth.custom.com/authorize",
            token_url="https://auth.custom.com/token",
            userinfo_url="https://auth.custom.com/userinfo",
            client_id="custom_id",
        )
        self.registry.register_provider(config)

        providers = self.registry.list_providers()
        provider_ids = [p.provider_id for p in providers]
        assert "custom" in provider_ids

    def test_remove_provider(self):
        config = OAuth2ProviderConfig(
            provider_id="to_remove",
            display_name="Remove Me",
            authorization_url="https://auth.remove.com/authorize",
            token_url="https://auth.remove.com/token",
            userinfo_url="https://auth.remove.com/userinfo",
            client_id="remove_id",
        )
        self.registry.register_provider(config)
        assert self.registry.get_provider("to_remove") is not None

        result = self.registry.remove_provider("to_remove")
        assert result is True
        assert self.registry.get_provider("to_remove") is None

    def test_remove_nonexistent_provider(self):
        result = self.registry.remove_provider("nonexistent")
        assert result is False


class TestOAuth2Service:
    def setup_method(self):
        self.registry = OAuth2ProviderRegistry()
        self.config = OAuth2ProviderConfig(
            provider_id="test_oidc",
            display_name="Test OIDC",
            authorization_url="https://auth.test.com/authorize",
            token_url="https://auth.test.com/token",
            userinfo_url="https://auth.test.com/userinfo",
            client_id="test_client",
            client_secret="test_secret",
            scopes=["openid", "profile", "email"],
            redirect_uri="http://localhost:8000/api/v1/auth/oidc/callback/test_oidc",
        )
        self.registry.register_provider(self.config)
        self.service = OAuth2Service(registry=self.registry)

    def test_get_authorize_url(self):
        result = self.service.get_authorize_url("test_oidc")

        assert "authorize_url" in result
        assert "state" in result
        assert "provider" in result
        assert result["provider"] == "test_oidc"
        assert "https://auth.test.com/authorize" in result["authorize_url"]
        assert "client_id=test_client" in result["authorize_url"]
        assert "code_challenge" in result["authorize_url"]
        assert "code_challenge_method=S256" in result["authorize_url"]

    def test_get_authorize_url_with_redirect_uri(self):
        result = self.service.get_authorize_url(
            "test_oidc",
            redirect_uri="http://custom.callback.com/oauth",
        )

        assert "authorize_url" in result
        assert "redirect_uri=http%3A%2F%2Fcustom.callback.com%2Foauth" in result["authorize_url"]

    def test_get_authorize_url_unknown_provider(self):
        result = self.service.get_authorize_url("unknown_provider")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_exchange_code_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "id_token": "test_id_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "test_refresh_token",
        }

        authorize_result = self.service.get_authorize_url("test_oidc")
        state = authorize_result["state"]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await self.service.exchange_code(
                "test_oidc", "test_code", state
            )

        assert result is not None
        assert result.access_token == "test_access_token"
        assert result.id_token == "test_id_token"
        assert result.expires_in == 3600

    @pytest.mark.asyncio
    async def test_exchange_code_invalid_state(self):
        result = await self.service.exchange_code(
            "test_oidc", "test_code", "invalid_state"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_exchange_code_unknown_provider(self):
        result = await self.service.exchange_code(
            "unknown", "test_code", "any_state"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_exchange_code_http_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "invalid_grant"}

        authorize_result = self.service.get_authorize_url("test_oidc")
        state = authorize_result["state"]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await self.service.exchange_code(
                "test_oidc", "bad_code", state
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_info_oidc(self):
        token_response = OAuth2TokenResponse(access_token="test_token")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sub": "user123",
            "email": "test@example.com",
            "name": "Test User",
            "picture": "https://avatar.example.com/test.png",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await self.service.get_user_info("test_oidc", token_response)

        assert result is not None
        assert result.provider_uid == "user123"
        assert result.email == "test@example.com"
        assert result.name == "Test User"
        assert result.provider_id == "test_oidc"

    @pytest.mark.asyncio
    async def test_get_user_info_github(self):
        github_config = OAuth2ProviderConfig(
            provider_id="github",
            display_name="GitHub",
            authorization_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            userinfo_url="https://api.github.com/user",
            client_id="gh_client",
            client_secret="gh_secret",
        )
        self.registry.register_provider(github_config)

        token_response = OAuth2TokenResponse(access_token="gh_token")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345,
            "login": "testuser",
            "name": "Test GitHub User",
            "email": "test@github.com",
            "avatar_url": "https://avatars.github.com/test.png",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await self.service.get_user_info("github", token_response)

        assert result is not None
        assert result.provider_uid == "12345"
        assert result.name == "testuser"
        assert result.avatar_url == "https://avatars.github.com/test.png"

    @pytest.mark.asyncio
    async def test_get_user_info_http_error(self):
        token_response = OAuth2TokenResponse(access_token="test_token")
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await self.service.get_user_info("test_oidc", token_response)

        assert result is None


class TestAuthServiceOAuth2:
    def setup_method(self):
        self.auth = AuthService()

    def test_list_oauth2_providers_empty(self):
        providers = self.auth.list_oauth2_providers()
        assert isinstance(providers, list)

    def test_list_oauth2_providers_with_config(self):
        config = OAuth2ProviderConfig(
            provider_id="custom_provider",
            display_name="Custom Provider",
            authorization_url="https://auth.custom.com/authorize",
            token_url="https://auth.custom.com/token",
            userinfo_url="https://auth.custom.com/userinfo",
            client_id="custom_id",
        )
        self.auth.oauth2.registry.register_provider(config)

        providers = self.auth.list_oauth2_providers()
        provider_ids = [p["provider_id"] for p in providers]
        assert "custom_provider" in provider_ids

    def test_get_oauth2_authorize_url(self):
        config = OAuth2ProviderConfig(
            provider_id="test_oidc",
            display_name="Test OIDC",
            authorization_url="https://auth.test.com/authorize",
            token_url="https://auth.test.com/token",
            userinfo_url="https://auth.test.com/userinfo",
            client_id="test_client",
            client_secret="test_secret",
        )
        self.auth.oauth2.registry.register_provider(config)

        result = self.auth.get_oauth2_authorize_url("test_oidc")
        assert "authorize_url" in result
        assert "state" in result

    def test_get_oauth2_authorize_url_unknown_provider(self):
        result = self.auth.get_oauth2_authorize_url("nonexistent")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_authenticate_oauth2_success(self):
        config = OAuth2ProviderConfig(
            provider_id="test_oidc",
            display_name="Test OIDC",
            authorization_url="https://auth.test.com/authorize",
            token_url="https://auth.test.com/token",
            userinfo_url="https://auth.test.com/userinfo",
            client_id="test_client",
            client_secret="test_secret",
        )
        self.auth.oauth2.registry.register_provider(config)

        authorize_result = self.auth.get_oauth2_authorize_url("test_oidc")
        state = authorize_result["state"]

        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "test_access",
            "id_token": "test_id",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        userinfo_resp = MagicMock()
        userinfo_resp.status_code = 200
        userinfo_resp.json.return_value = {
            "sub": "oidc_user_123",
            "email": "oidc@test.com",
            "name": "OIDC User",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = token_resp
            mock_client.get.return_value = userinfo_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await self.auth.authenticate_oauth2(
                provider_id="test_oidc",
                code="test_code",
                state=state,
            )

        assert result is not None
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.token_type == "Bearer"

    @pytest.mark.asyncio
    async def test_authenticate_oauth2_creates_user(self):
        config = OAuth2ProviderConfig(
            provider_id="test_oidc",
            display_name="Test OIDC",
            authorization_url="https://auth.test.com/authorize",
            token_url="https://auth.test.com/token",
            userinfo_url="https://auth.test.com/userinfo",
            client_id="test_client",
            client_secret="test_secret",
        )
        self.auth.oauth2.registry.register_provider(config)

        authorize_result = self.auth.get_oauth2_authorize_url("test_oidc")
        state = authorize_result["state"]

        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "test_access",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        userinfo_resp = MagicMock()
        userinfo_resp.status_code = 200
        userinfo_resp.json.return_value = {
            "sub": "new_user_456",
            "email": "newuser@test.com",
            "name": "New User",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = token_resp
            mock_client.get.return_value = userinfo_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await self.auth.authenticate_oauth2(
                provider_id="test_oidc",
                code="test_code",
                state=state,
            )

        assert result is not None

        user_found = False
        for user in self.auth._users.values():
            if user.get("provider_uid") == "new_user_456":
                user_found = True
                assert user["auth_provider"] == AuthProvider.OIDC.value
                assert user["email"] == "newuser@test.com"
                assert user["global_role"] == GlobalRole.OBSERVER.value
        assert user_found

    @pytest.mark.asyncio
    async def test_authenticate_oauth2_existing_user(self):
        config = OAuth2ProviderConfig(
            provider_id="test_oidc",
            display_name="Test OIDC",
            authorization_url="https://auth.test.com/authorize",
            token_url="https://auth.test.com/token",
            userinfo_url="https://auth.test.com/userinfo",
            client_id="test_client",
            client_secret="test_secret",
        )
        self.auth.oauth2.registry.register_provider(config)

        import uuid
        existing_uid = str(uuid.uuid4())
        self.auth._users["existing_oidc_user"] = {
            "id": existing_uid,
            "username": "existing_oidc_user",
            "password_hash": "",
            "email": "old@test.com",
            "global_role": GlobalRole.ANALYST.value,
            "auth_provider": AuthProvider.OIDC.value,
            "provider_id": "test_oidc",
            "provider_uid": "existing_sub_789",
            "is_active": True,
        }

        authorize_result = self.auth.get_oauth2_authorize_url("test_oidc")
        state = authorize_result["state"]

        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "test_access",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        userinfo_resp = MagicMock()
        userinfo_resp.status_code = 200
        userinfo_resp.json.return_value = {
            "sub": "existing_sub_789",
            "email": "updated@test.com",
            "name": "Existing User",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = token_resp
            mock_client.get.return_value = userinfo_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await self.auth.authenticate_oauth2(
                provider_id="test_oidc",
                code="test_code",
                state=state,
            )

        assert result is not None
        assert self.auth._users["existing_oidc_user"]["email"] == "updated@test.com"

    @pytest.mark.asyncio
    async def test_authenticate_oauth2_invalid_state(self):
        result = await self.auth.authenticate_oauth2(
            provider_id="test_oidc",
            code="test_code",
            state="invalid_state",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_oauth2_unknown_provider(self):
        result = await self.auth.authenticate_oauth2(
            provider_id="unknown",
            code="test_code",
            state="any_state",
        )
        assert result is None


class TestAPIKeyEdgeCases:
    def setup_method(self):
        self.auth = AuthService()

    def test_create_api_key_basic(self):
        user = self.auth.register_user("apikey_user", "password123")
        assert user is not None

        result = self.auth.create_api_key(user.id, "test-key")
        assert result is not None

    def test_verify_api_key_after_creation(self):
        user = self.auth.register_user("apikey_user2", "password123")
        raw_key_result = self.auth.create_api_key(user.id, "test-key-2")

        import hashlib
        all_keys = list(self.auth._api_keys.values())
        assert len(all_keys) > 0

        key_record = all_keys[-1]
        assert key_record.user_id == user.id
        assert key_record.name == "test-key-2"
        assert key_record.is_active is True

    def test_revoke_api_key(self):
        user = self.auth.register_user("apikey_user3", "password123")
        self.auth.create_api_key(user.id, "test-key-3")

        all_keys = list(self.auth._api_keys.values())
        key_record = all_keys[-1]

        result = self.auth.revoke_api_key(key_record.id)
        assert result is True

        updated = self.auth._api_keys.get(key_record.key_hash)
        assert updated.is_active is False

    def test_revoke_nonexistent_api_key(self):
        result = self.auth.revoke_api_key("nonexistent_id")
        assert result is False

    def test_verify_revoked_api_key(self):
        user = self.auth.register_user("apikey_user4", "password123")
        raw_key = f"odap_testkey1234567890abcdef"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        record = APIKeyRecord(
            user_id=user.id,
            name="revoked-key",
            key_hash=key_hash,
            prefix=raw_key[:12],
            is_active=False,
        )
        self.auth._api_keys[key_hash] = record

        result = self.auth.verify_api_key(raw_key)
        assert result is None

    def test_verify_expired_api_key(self):
        user = self.auth.register_user("apikey_user5", "password123")
        raw_key = f"odap_expiredkey1234567890abcd"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        record = APIKeyRecord(
            user_id=user.id,
            name="expired-key",
            key_hash=key_hash,
            prefix=raw_key[:12],
            is_active=True,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        self.auth._api_keys[key_hash] = record

        result = self.auth.verify_api_key(raw_key)
        assert result is None


class TestLoginRateLimiter:
    def test_allows_normal_login(self):
        limiter = LoginRateLimiter()
        assert limiter.check("192.168.1.1") is True

    def test_blocks_after_max_failures(self):
        limiter = LoginRateLimiter()
        ip = "10.0.0.1"
        for _ in range(limiter.MAX_ATTEMPTS):
            limiter.check(ip)
            limiter.record_failure(ip)

        assert limiter.check(ip) is False

    def test_resets_after_success(self):
        limiter = LoginRateLimiter()
        ip = "10.0.0.2"
        for _ in range(3):
            limiter.record_failure(ip)

        limiter.record_success(ip)
        assert limiter.check(ip) is True
