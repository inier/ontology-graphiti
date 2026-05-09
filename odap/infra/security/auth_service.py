"""
认证服务 - 对齐 docs/03-modules/auth/DESIGN.md

功能:
- 本地账号密码认证 (bcrypt)
- JWT Token 签发/刷新/吊销
- API Key 管理
- OAuth2/OIDC 预留接口
- 登录限流
"""

import os
import uuid
import hashlib
import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from collections import defaultdict

from .auth_models import (
    AuthProvider, GlobalRole, LoginRequest, TokenPair,
    UserInfo, WorkspaceMembership, RefreshTokenRecord, APIKeyRecord,
)
from .jwt_service import JWTService


try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False


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

    def __init__(self, jwt_service: JWTService = None):
        self.jwt = jwt_service or JWTService()
        self.rate_limiter = LoginRateLimiter()
        self._refresh_tokens: Dict[str, RefreshTokenRecord] = {}
        self._api_keys: Dict[str, APIKeyRecord] = {}
        self._lock = threading.RLock()

        self._users: Dict[str, Dict[str, Any]] = {}
        self._init_default_users()

    def _init_default_users(self):
        admin_hash = self._hash_password("admin123") if BCRYPT_AVAILABLE else "admin123"
        self._users["admin"] = {
            "id": str(uuid.uuid4()),
            "username": "admin",
            "password_hash": admin_hash,
            "email": "admin@odap.local",
            "global_role": GlobalRole.ADMIN.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "is_active": True,
        }

    def _hash_password(self, password: str) -> str:
        if BCRYPT_AVAILABLE:
            return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
        return hashlib.sha256(password.encode()).hexdigest()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        if BCRYPT_AVAILABLE and password_hash.startswith("$2"):
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        return hashlib.sha256(password.encode()).hexdigest() == password_hash

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
