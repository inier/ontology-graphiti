"""
认证服务 - 对齐 docs/03-modules/auth/DESIGN.md

功能:
- 本地账号密码认证 (bcrypt)
- JWT Token 签发/刷新/吊销
- API Key 管理
- OAuth2/OIDC Authorization Code Flow
- 登录限流
"""

import os
import uuid
import hashlib
import time
import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from collections import defaultdict

from .auth_models import (
    AuthProvider, GlobalRole, LoginRequest, TokenPair,
    UserInfo, WorkspaceMembership, RefreshTokenRecord, APIKeyRecord,
)
from .jwt_service import JWTService
from .oauth2_providers import OAuth2Service, OAuth2ProviderRegistry, OAuth2TokenResponse, OAuth2UserInfo

logger = logging.getLogger(__name__)


def _is_production_env() -> bool:
    """Check whether the current process is running in production."""
    env = os.environ.get("ENV", os.environ.get("ENVIRONMENT", "")).lower()
    return env in ("production", "prod", "live")


def _generate_random_password(length: int = 16) -> str:
    """Generate a cryptographically-random password for first-startup use."""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False


def assert_bcrypt_available() -> None:
    """Fail-closed assertion that ``bcrypt`` is installed.

    R-P1-005: P0-7 (cryptographic downgrade) requires that the application
    refuses to start (or to hash/verify passwords) when bcrypt is missing,
    instead of silently falling back to plain SHA-256. The fallback path is
    insecure because SHA-256 is fast and unsalted.
    """
    if not BCRYPT_AVAILABLE:
        raise RuntimeError(
            "SECURITY: bcrypt is not installed. ODAP requires bcrypt for password "
            "hashing. Install it with `pip install bcrypt` and restart."
        )


class LoginRateLimiter:
    """登录限流器 - 5次失败 / 15分钟 / IP"""

    MAX_ATTEMPTS = 5
    WINDOW_SECONDS = 15 * 60
    LOCK_SECONDS = 30 * 60

    def __init__(self):
        self._attempts: Dict[str, list[float]] = defaultdict(list)
        self._locks: Dict[str, float] = {}
        self._lock = threading.Lock()

    def check(self, identifier: str) -> bool:
        with self._lock:
            now = time.time()

            if identifier in self._locks:
                if now - self._locks[identifier] < self.LOCK_SECONDS:
                    return False
                del self._locks[identifier]

            attempts = self._attempts[identifier]
            cutoff = now - self.WINDOW_SECONDS
            self._attempts[identifier] = [t for t in attempts if t > cutoff]

            if len(self._attempts[identifier]) >= self.MAX_ATTEMPTS:
                self._locks[identifier] = now
                return False

            return True

    def record_failure(self, identifier: str):
        with self._lock:
            self._attempts[identifier].append(time.time())

    def record_success(self, identifier: str):
        with self._lock:
            if identifier in self._attempts:
                del self._attempts[identifier]
            if identifier in self._locks:
                del self._locks[identifier]


class AuthService:
    """认证服务 - 核心入口"""

    def __init__(self, jwt_service: JWTService = None, oauth2_registry: OAuth2ProviderRegistry = None):
        self.jwt = jwt_service or JWTService()
        self.rate_limiter = LoginRateLimiter()
        self.oauth2 = OAuth2Service(registry=oauth2_registry or OAuth2ProviderRegistry())
        self._refresh_tokens: Dict[str, RefreshTokenRecord] = {}
        self._api_keys: Dict[str, APIKeyRecord] = {}
        self._lock = threading.RLock()

        self._users: Dict[str, Dict[str, Any]] = {}
        self._init_default_users()

    def _init_default_users(self):
        # P0-8 fix: NEVER seed a default admin with a hardcoded password.
        # Two strategies depending on environment:
        #   1. Production: refuse to create admin without explicit password
        #   2. Dev/test: read from env var (e.g. ODAP_ADMIN_PASSWORD)
        #   3. First-time setup: generate a random password and log it
        admin_password = self._resolve_admin_password()
        admin_hash = self._hash_password(admin_password)
        self._users["admin"] = {
            "id": str(uuid.uuid4()),
            "username": "admin",
            "password_hash": admin_hash,
            "email": "admin@odap.local",
            "global_role": GlobalRole.ADMIN.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "is_active": True,
        }

    def _resolve_admin_password(self) -> str:
        """Resolve the admin password. NEVER use a hardcoded default.

        Priority:
          1. ODAP_ADMIN_PASSWORD env var (test/dev)
          2. Generated random password (logged once at startup)
          3. In production, refuse to start without env var
        """
        env_password = os.environ.get("ODAP_ADMIN_PASSWORD", "").strip()
        if env_password and len(env_password) >= 8:
            return env_password

        if _is_production_env():
            raise RuntimeError(
                "SECURITY: ODAP_ADMIN_PASSWORD must be set in production. "
                "Refusing to start with a default admin password."
            )
        random_pw = _generate_random_password()
        logger.warning(
            "ODAP_ADMIN_PASSWORD is not set. Generated random admin password: %s. "
            "Set ODAP_ADMIN_PASSWORD env var to fix this.",
            random_pw,
        )
        return random_pw

    def _hash_password(self, password: str) -> str:
        # R-P1-005: fail-closed if bcrypt is missing rather than silently
        # downgrading to unsalted SHA-256 (insecure for password storage).
        assert_bcrypt_available()
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        # R-P1-005: fail-closed if bcrypt is missing. We deliberately do NOT
        # support verifying legacy SHA-256 hashes — operators must reset
        # passwords (or the upgrade tooling must re-hash) on first deploy.
        assert_bcrypt_available()
        return bcrypt.checkpw(password.encode(), password_hash.encode())

    def login(self, username: str, password: str, ip_address: str = "",
              workspace_id: str = "") -> Optional[TokenPair]:
        if not self.rate_limiter.check(ip_address):
            return None

        user = self._users.get(username)
        if not user or not user.get("is_active"):
            self.rate_limiter.record_failure(ip_address)
            return None

        if not self._verify_password(password, user["password_hash"]):
            self.rate_limiter.record_failure(ip_address)
            return None

        self.rate_limiter.record_success(ip_address)

        access = self.jwt.issue_access_token(
            user["id"], user["username"], user["global_role"],
            workspace_id=workspace_id,
        )
        refresh = self.jwt.issue_refresh_token(user["id"], workspace_id)

        token_hash = hashlib.sha256(refresh.encode()).hexdigest()
        record = RefreshTokenRecord(
            id=str(uuid.uuid4()),
            user_id=user["id"],
            token_hash=token_hash,
            workspace_id=workspace_id,
            expires_at=datetime.now(timezone.utc) + self.jwt.REFRESH_TTL,
        )
        with self._lock:
            self._refresh_tokens[token_hash] = record

        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            token_type="Bearer",
            expires_in=int(self.jwt.ACCESS_TTL.total_seconds()),
        )

    def refresh(self, refresh_token: str) -> Optional[TokenPair]:
        try:
            payload = self.jwt.verify_token_raw(refresh_token)
        except Exception:
            return None

        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        with self._lock:
            record = self._refresh_tokens.get(token_hash)

        if not record or record.revoked:
            return None

        expire_ts = record.expires_at
        if isinstance(expire_ts, datetime):
            expire_ts = expire_ts.timestamp()
        if time.time() > expire_ts:
            return None

        user = self._get_user_by_id(record.user_id)
        if not user:
            return None

        with self._lock:
            record.revoked = True

        w_id = payload.get("ws_id", "")

        new_access = self.jwt.issue_access_token(
            record.user_id, user["username"], user["global_role"],
            workspace_id=w_id,
        )
        new_refresh = self.jwt.issue_refresh_token(record.user_id, w_id)

        new_hash = hashlib.sha256(new_refresh.encode()).hexdigest()
        new_record = RefreshTokenRecord(
            id=str(uuid.uuid4()),
            user_id=record.user_id,
            token_hash=new_hash,
            workspace_id=w_id,
            expires_at=datetime.now(timezone.utc) + self.jwt.REFRESH_TTL,
        )
        with self._lock:
            self._refresh_tokens[new_hash] = new_record

        return TokenPair(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="Bearer",
            expires_in=int(self.jwt.ACCESS_TTL.total_seconds()),
        )

    def logout(self, refresh_token: str) -> bool:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        with self._lock:
            record = self._refresh_tokens.get(token_hash)
            if record:
                record.revoked = True
                return True
        return False

    def logout_all(self, user_id: str):
        with self._lock:
            for record in self._refresh_tokens.values():
                if record.user_id == user_id:
                    record.revoked = True

    def get_user_info(self, user_id: str) -> Optional[UserInfo]:
        user = self._get_user_by_id(user_id)
        if not user:
            return None
        return UserInfo(
            id=user["id"],
            username=user["username"],
            email=user.get("email"),
            global_role=GlobalRole(user["global_role"]),
            workspaces=user.get("workspaces", []),
        )

    def _get_user_by_id(self, user_id: str) -> Optional[Dict]:
        for user in self._users.values():
            if user["id"] == user_id:
                return user
        return None

    def register_user(self, username: str, password: str, email: str = None,
                      role: GlobalRole = GlobalRole.OBSERVER) -> Optional[UserInfo]:
        if username in self._users:
            return None
        uid = str(uuid.uuid4())
        self._users[username] = {
            "id": uid,
            "username": username,
            "password_hash": self._hash_password(password),
            "email": email,
            "global_role": role.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "is_active": True,
        }
        return UserInfo(id=uid, username=username, email=email, global_role=role)

    def list_users(self) -> list[dict]:
        return [
            {
                "id": u["id"],
                "username": u["username"],
                "email": u.get("email", ""),
                "global_role": u.get("global_role", "observer"),
                "auth_provider": u.get("auth_provider", "local"),
                "is_active": u.get("is_active", True),
            }
            for u in self._users.values()
        ]

    def update_user(self, user_id: str, **kwargs) -> Optional[dict]:
        for u in self._users.values():
            if u["id"] == user_id:
                if "email" in kwargs and kwargs["email"] is not None:
                    u["email"] = kwargs["email"]
                if "global_role" in kwargs and kwargs["global_role"] is not None:
                    u["global_role"] = kwargs["global_role"]
                if "is_active" in kwargs and kwargs["is_active"] is not None:
                    u["is_active"] = kwargs["is_active"]
                if "password" in kwargs and kwargs["password"]:
                    u["password_hash"] = self._hash_password(kwargs["password"])
                return {
                    "id": u["id"],
                    "username": u["username"],
                    "email": u.get("email", ""),
                    "global_role": u.get("global_role", "observer"),
                    "auth_provider": u.get("auth_provider", "local"),
                    "is_active": u.get("is_active", True),
                }
        return None

    def delete_user(self, user_id: str) -> bool:
        to_delete = None
        for username, u in self._users.items():
            if u["id"] == user_id:
                to_delete = username
                break
        if to_delete:
            del self._users[to_delete]
            return True
        return False

    def create_api_key(self, user_id: str, name: str, scopes: list[str] = None) -> Optional[APIKeyRecord]:
        raw_key = f"odap_{uuid.uuid4().hex}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        prefix = raw_key[:12]

        record = APIKeyRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            scopes=scopes or ["*"],
        )
        with self._lock:
            self._api_keys[key_hash] = record

        raw_key_field = f"{prefix}...{raw_key[-8:]}"
        full_key_for_return = raw_key

        result = record.model_dump()
        result["api_key"] = full_key_for_return
        return APIKeyRecord(**{k: v for k, v in result.items() if k in APIKeyRecord.model_fields})

    def verify_api_key(self, api_key: str) -> Optional[APIKeyRecord]:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        with self._lock:
            record = self._api_keys.get(key_hash)
        if not record or not record.is_active:
            return None
        if record.expires_at and datetime.now(timezone.utc) > record.expires_at:
            return None
        return record

    def revoke_api_key(self, api_key_id: str) -> bool:
        with self._lock:
            for record in self._api_keys.values():
                if record.id == api_key_id:
                    record.is_active = False
                    return True
        return False

    def get_oauth2_authorize_url(self, provider_id: str, redirect_uri: str = "") -> Dict[str, str]:
        result = self.oauth2.get_authorize_url(provider_id, redirect_uri)
        if "error" in result:
            logger.warning(f"OAuth2 authorize URL error: {result['error']}")
        return result

    def list_oauth2_providers(self) -> list[Dict[str, str]]:
        providers = self.oauth2.registry.list_providers()
        return [
            {"provider_id": p.provider_id, "display_name": p.display_name}
            for p in providers
        ]

    async def authenticate_oauth2(
        self,
        provider_id: str,
        code: str,
        state: str,
        redirect_uri: str = "",
        workspace_id: str = "",
    ) -> Optional[TokenPair]:
        token_response = await self.oauth2.exchange_code(provider_id, code, state, redirect_uri)
        if not token_response or not token_response.access_token:
            logger.warning(f"OAuth2 token exchange failed for provider '{provider_id}'")
            return None

        oauth2_user = await self.oauth2.get_user_info(provider_id, token_response)
        if not oauth2_user or not oauth2_user.provider_uid:
            logger.warning(f"OAuth2 user info retrieval failed for provider '{provider_id}'")
            return None

        user = self._find_or_create_oauth2_user(oauth2_user)
        if not user or not user.get("is_active"):
            return None

        access = self.jwt.issue_access_token(
            user["id"], user["username"], user["global_role"],
            workspace_id=workspace_id,
        )
        refresh = self.jwt.issue_refresh_token(user["id"], workspace_id)

        token_hash = hashlib.sha256(refresh.encode()).hexdigest()
        record = RefreshTokenRecord(
            id=str(uuid.uuid4()),
            user_id=user["id"],
            token_hash=token_hash,
            workspace_id=workspace_id,
            expires_at=datetime.now(timezone.utc) + self.jwt.REFRESH_TTL,
        )
        with self._lock:
            self._refresh_tokens[token_hash] = record

        logger.info(f"OAuth2 login successful: provider={provider_id}, user={user['username']}")
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            token_type="Bearer",
            expires_in=int(self.jwt.ACCESS_TTL.total_seconds()),
        )

    def _find_or_create_oauth2_user(self, oauth2_user: OAuth2UserInfo) -> Optional[Dict[str, Any]]:
        with self._lock:
            for user in self._users.values():
                if (user.get("auth_provider") == AuthProvider.OIDC.value
                        and user.get("provider_uid") == oauth2_user.provider_uid
                        and user.get("provider_id") == oauth2_user.provider_id):
                    if oauth2_user.name and oauth2_user.name != user.get("username"):
                        pass
                    if oauth2_user.email and oauth2_user.email != user.get("email"):
                        user["email"] = oauth2_user.email
                    return user

            username = oauth2_user.name or f"{oauth2_user.provider_id}_{oauth2_user.provider_uid}"
            base_username = username
            counter = 1
            while username in self._users:
                username = f"{base_username}_{counter}"
                counter += 1

            uid = str(uuid.uuid4())
            self._users[username] = {
                "id": uid,
                "username": username,
                "password_hash": "",
                "email": oauth2_user.email,
                "global_role": GlobalRole.OBSERVER.value,
                "auth_provider": AuthProvider.OIDC.value,
                "provider_id": oauth2_user.provider_id,
                "provider_uid": oauth2_user.provider_uid,
                "is_active": True,
            }
            logger.info(f"Created new OAuth2 user: {username} from {oauth2_user.provider_id}")
            return self._users[username]
