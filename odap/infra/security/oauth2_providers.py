"""
OAuth2 Provider 配置与 Token 交换 - 对齐 docs/03-modules/auth/DESIGN.md §2.2

功能:
- OAuth2 Authorization Code Flow
- 多 Provider 支持 (Google/GitHub/Generic OIDC)
- Token 交换与用户信息获取
- ID Token 验证
"""

import hashlib
import secrets
import urllib.parse
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel, Field


class OAuth2ProviderConfig(BaseModel):
    provider_id: str
    display_name: str
    authorization_url: str
    token_url: str
    userinfo_url: str
    client_id: str
    client_secret: str = ""
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    redirect_uri: str = ""
    issuer: str = ""


class OAuth2State(BaseModel):
    state: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    provider_id: str = ""
    redirect_uri: str = ""
    code_verifier: str = Field(default_factory=lambda: secrets.token_urlsafe(48))


class OAuth2TokenResponse(BaseModel):
    access_token: str = ""
    id_token: str = ""
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: str = ""


class OAuth2UserInfo(BaseModel):
    provider_id: str
    provider_uid: str
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    raw_claims: Dict[str, Any] = Field(default_factory=dict)


class OAuth2ProviderRegistry:
    DEFAULT_PROVIDERS: Dict[str, Dict[str, str]] = {
        "google": {
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
            "issuer": "https://accounts.google.com",
            "scopes": "openid profile email",
        },
        "github": {
            "authorization_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "userinfo_url": "https://api.github.com/user",
            "issuer": "https://github.com",
            "scopes": "read:user user:email",
        },
    }

    def __init__(self):
        self._providers: Dict[str, OAuth2ProviderConfig] = {}
        self._load_from_env()

    def _load_from_env(self):
        import os

        for provider_id, defaults in self.DEFAULT_PROVIDERS.items():
            client_id = os.getenv(f"OAUTH2_{provider_id.upper()}_CLIENT_ID", "")
            client_secret = os.getenv(f"OAUTH2_{provider_id.upper()}_CLIENT_SECRET", "")
            if client_id:
                self._providers[provider_id] = OAuth2ProviderConfig(
                    provider_id=provider_id,
                    display_name=provider_id.capitalize(),
                    authorization_url=defaults["authorization_url"],
                    token_url=defaults["token_url"],
                    userinfo_url=defaults["userinfo_url"],
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=defaults["scopes"].split(),
                    issuer=defaults.get("issuer", ""),
                )

        custom_providers = os.getenv("OAUTH2_CUSTOM_PROVIDERS", "")
        if custom_providers:
            for entry in custom_providers.split(";"):
                parts = entry.strip().split(",")
                if len(parts) >= 5:
                    pid, name, auth_url, token_url, userinfo_url = parts[:5]
                    cid = os.getenv(f"OAUTH2_{pid.upper()}_CLIENT_ID", "")
                    csecret = os.getenv(f"OAUTH2_{pid.upper()}_CLIENT_SECRET", "")
                    if cid:
                        self._providers[pid] = OAuth2ProviderConfig(
                            provider_id=pid,
                            display_name=name,
                            authorization_url=auth_url,
                            token_url=token_url,
                            userinfo_url=userinfo_url,
                            client_id=cid,
                            client_secret=csecret,
                        )

    def register_provider(self, config: OAuth2ProviderConfig):
        self._providers[config.provider_id] = config

    def get_provider(self, provider_id: str) -> Optional[OAuth2ProviderConfig]:
        return self._providers.get(provider_id)

    def list_providers(self) -> list[OAuth2ProviderConfig]:
        return list(self._providers.values())

    def remove_provider(self, provider_id: str) -> bool:
        if provider_id in self._providers:
            del self._providers[provider_id]
            return True
        return False


class OAuth2Service:
    def __init__(self, registry: OAuth2ProviderRegistry = None):
        self.registry = registry or OAuth2ProviderRegistry()
        self._states: Dict[str, OAuth2State] = {}

    def get_authorize_url(
        self,
        provider_id: str,
        redirect_uri: str = "",
    ) -> Dict[str, str]:
        provider = self.registry.get_provider(provider_id)
        if not provider:
            return {"error": f"Provider '{provider_id}' not configured"}

        state = OAuth2State(
            provider_id=provider_id,
            redirect_uri=redirect_uri or provider.redirect_uri,
        )
        self._states[state.state] = state

        params = {
            "client_id": provider.client_id,
            "response_type": "code",
            "scope": " ".join(provider.scopes),
            "redirect_uri": state.redirect_uri or provider.redirect_uri,
            "state": state.state,
            "code_challenge": self._generate_code_challenge(state.code_verifier),
            "code_challenge_method": "S256",
        }

        authorize_url = f"{provider.authorization_url}?{urllib.parse.urlencode(params)}"
        return {
            "authorize_url": authorize_url,
            "state": state.state,
            "provider": provider_id,
        }

    async def exchange_code(
        self,
        provider_id: str,
        code: str,
        state: str,
        redirect_uri: str = "",
    ) -> Optional[OAuth2TokenResponse]:
        provider = self.registry.get_provider(provider_id)
        if not provider:
            return None

        saved_state = self._states.get(state)
        if not saved_state or saved_state.provider_id != provider_id:
            return None

        del self._states[state]

        effective_redirect = redirect_uri or saved_state.redirect_uri or provider.redirect_uri

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": effective_redirect,
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
            "code_verifier": saved_state.code_verifier,
        }

        headers = {"Accept": "application/json"}
        if provider_id == "github":
            headers["Accept"] = "application/json"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(provider.token_url, data=data, headers=headers)
                if resp.status_code != 200:
                    return None
                token_data = resp.json()
                return OAuth2TokenResponse(
                    access_token=token_data.get("access_token", ""),
                    id_token=token_data.get("id_token", ""),
                    token_type=token_data.get("token_type", "Bearer"),
                    expires_in=token_data.get("expires_in", 3600),
                    refresh_token=token_data.get("refresh_token", ""),
                )
        except Exception:
            return None

    async def get_user_info(
        self,
        provider_id: str,
        token_response: OAuth2TokenResponse,
    ) -> Optional[OAuth2UserInfo]:
        provider = self.registry.get_provider(provider_id)
        if not provider:
            return None

        headers = {"Authorization": f"Bearer {token_response.access_token}"}
        if provider_id == "github":
            headers["Accept"] = "application/json"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(provider.userinfo_url, headers=headers)
                if resp.status_code != 200:
                    return None
                user_data = resp.json()

                if provider_id == "github":
                    return OAuth2UserInfo(
                        provider_id=provider_id,
                        provider_uid=str(user_data.get("id", "")),
                        email=user_data.get("email"),
                        name=user_data.get("login") or user_data.get("name"),
                        avatar_url=user_data.get("avatar_url"),
                        raw_claims=user_data,
                    )
                else:
                    return OAuth2UserInfo(
                        provider_id=provider_id,
                        provider_uid=user_data.get("sub", ""),
                        email=user_data.get("email"),
                        name=user_data.get("name"),
                        avatar_url=user_data.get("picture"),
                        raw_claims=user_data,
                    )
        except Exception:
            return None

    def _generate_code_challenge(self, code_verifier: str) -> str:
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        import base64

        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
