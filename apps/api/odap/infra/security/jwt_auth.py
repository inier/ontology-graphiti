#!/usr/bin/env python3
"""
JWT认证中间件
"""

import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from odap.infra.security.config import security_config

logger = logging.getLogger(__name__)

security = HTTPBearer()


def decode_token(token: str) -> dict:
    """解码JWT令牌"""
    try:
        payload = jwt.decode(
            token,
            # P0-8 fix: use lazy-validated method that raises on placeholder in prod
            security_config.get_jwt_secret(),
            algorithms=[security_config.get_jwt_algorithm()]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取当前用户"""
    token = credentials.credentials
    payload = decode_token(token)
    return payload


async def optional_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """可选的当前用户获取"""
    try:
        token = credentials.credentials
        payload = decode_token(token)
        return payload
    except Exception as e:
        logger.debug(f"Auth optional check failed: {e}")
        return None


async def verify_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证管理员权限"""
    token = credentials.credentials
    payload = decode_token(token)
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return payload