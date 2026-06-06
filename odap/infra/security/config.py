#!/usr/bin/env python3
"""
安全配置模块

所有敏感配置必须通过环境变量或密钥管理服务提供。
禁止使用硬编码默认值。

辅助函数: odap.infra.security.secret_helpers
"""

import os
import logging
from .secret_helpers import (
    get_required_secret,
    get_optional_secret,
    PLACEHOLDER_VALUES,
    SecretValidationError,
)

logger = logging.getLogger(__name__)

# 尝试加载环境变量
try:
    from dotenv import load_dotenv

    # 检测环境
    in_docker = os.getenv('IN_DOCKER', 'false').lower() == 'true'

    if in_docker:
        # Docker 环境：优先 .env.docker
        logger.info("检测到 Docker 环境，使用 .env.docker")
        load_dotenv('.env.docker', override=True)
    else:
        # 本地环境：优先 .env.local
        logger.info("检测到本地环境，使用 .env.local")
        load_dotenv('.env.local', override=True)
        load_dotenv('.env', override=False)
except ImportError:
    # 如果没有dotenv，使用默认值
    pass


class SecurityConfig:
    """安全配置类

    所有敏感字段（密码、密钥、Token）必须通过环境变量显式提供。
    严禁使用硬编码默认值。详见 P0-8 架构原则。
    """

    # LLM 配置（API key 不视为敏感默认值——它本身是用户输入）
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.siliconflow.cn/v1/chat/completions')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'Pro/MiniMaxAI/MiniMax-M2.5')

    # Neo4j 配置
    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')

    # CORS 配置
    CORS_ORIGINS = [origin.strip() for origin in os.getenv('CORS_ORIGINS', 'http://localhost,http://localhost:80,http://localhost:3000,http://localhost:8000,http://localhost:5173').split(',')]

    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'app.log')

    @classmethod
    def get_jwt_secret(cls) -> str:
        """Get JWT secret from environment. Raises if missing/placeholder.

        Lazy validation: only validates on access, allowing the application
        to start (and test fixtures to import) without the secret being set.
        Production code paths MUST call this method.
        """
        # RFC 7518 §3.2: HMAC-SHA256 keys MUST be at least 32 bytes (256 bits).
        # Enforce minimum 32 to prevent InsecureKeyLengthWarning from PyJWT.
        return get_required_secret("JWT_SECRET", min_length=32)

    @classmethod
    def get_jwt_algorithm(cls) -> str:
        return os.getenv('JWT_ALGORITHM', 'HS256')

    @classmethod
    def get_jwt_expiration(cls) -> int:
        return int(os.getenv('JWT_EXPIRATION', '3600'))

    @classmethod
    def get_neo4j_password(cls) -> str:
        """Get Neo4j password from environment. Raises if missing.

        NOTE: unlike other secrets, Neo4j may be configured with empty/no
        password in dev (e.g. local Docker with default config). We allow
        that in non-production only.
        """
        try:
            return get_required_secret("NEO4J_PASSWORD", min_length=1)
        except SecretValidationError:
            # Empty/missing Neo4j password is OK in dev (local Docker)
            if os.environ.get("ENV", "").lower() in ("production", "prod", "live"):
                raise
            logger.warning(
                "NEO4J_PASSWORD is not set. This is allowed in non-production "
                "but MUST be set in production."
            )
            return ""

    @classmethod
    def validate(cls):
        """验证配置有效性

        在生产环境启动时调用。开发/测试环境可跳过。
        """
        env = os.environ.get("ENV", os.environ.get("ENVIRONMENT", "")).lower()
        if env in ("production", "prod", "live"):
            errors = []
            for name, fn in [
                ("JWT_SECRET", cls.get_jwt_secret),
            ]:
                try:
                    fn()
                except SecretValidationError as e:
                    errors.append(str(e))
            if errors:
                raise SecretValidationError(
                    "Production configuration invalid:\n" + "\n".join(errors)
                )
        else:
            # Non-production: warn but don't fail
            try:
                cls.get_jwt_secret()
            except SecretValidationError as e:
                logger.warning(f"Configuration warning: {e}")

    @classmethod
    def get_api_key(cls, service):
        """获取指定服务的 API 密钥"""
        if service == 'openai':
            return cls.OPENAI_API_KEY
        elif service == 'neo4j':
            return cls.get_neo4j_password()
        else:
            return None


# 全局安全配置实例
security_config = SecurityConfig()

# 在生产环境验证；开发环境只警告
try:
    security_config.validate()
except SecretValidationError as e:
    logger.error(f"Configuration error: {e}")
    # Re-raise in production so the process fails to start
    if os.environ.get("ENV", "").lower() in ("production", "prod", "live"):
        raise
