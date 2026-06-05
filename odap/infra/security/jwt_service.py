"""
JWT 服务 - 对齐 docs/03-modules/auth/DESIGN.md §3

功能:
- Token 签发 (access + refresh)
- Token 验证
- Token 刷新 (Rotation)
- RS256 / HS256 支持
"""

import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

from .auth_models import JWTPayload


class JWTService:
    ACCESS_TTL = timedelta(minutes=15)
    REFRESH_TTL = timedelta(days=7)
    ALGORITHM = "HS256"

    def __init__(self, secret_key: str = None, algorithm: str = None):
        from .config import security_config
        # P0-8 fix: use lazy-validated method that raises on placeholder in prod
        if secret_key is None:
            secret_key = os.getenv("JWT_SECRET") or security_config.get_jwt_secret()
        self.secret_key = secret_key
        self.algorithm = algorithm or os.getenv("JWT_ALGORITHM", self.ALGORITHM)

    def issue_access_token(self, user_id: str, user_name: str, role: str,
                           workspace_id: str = "", workspace_role: str = "") -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "odap",
            "sub": user_id,
            "name": user_name,
            "exp": int((now + self.ACCESS_TTL).timestamp()),
            "iat": int(now.timestamp()),
            "role": role,
            "ws_id": workspace_id,
            "ws_role": workspace_role or role,
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def issue_refresh_token(self, user_id: str, workspace_id: str = "") -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "odap",
            "sub": user_id,
            "exp": int((now + self.REFRESH_TTL).timestamp()),
            "iat": int(now.timestamp()),
            "type": "refresh",
            "ws_id": workspace_id,
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> JWTPayload:
        payload_dict = jwt.decode(
            token,
            self.secret_key,
            algorithms=[self.algorithm],
            options={"require": ["exp", "sub"]},
        )
        return JWTPayload.from_dict(payload_dict)

    def verify_token_raw(self, token: str) -> dict:
        return jwt.decode(
            token,
            self.secret_key,
            algorithms=[self.algorithm],
            options={"require": ["exp", "sub"]},
        )
