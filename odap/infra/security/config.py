#!/usr/bin/env python3
"""
安全配置模块
"""

import os

# 尝试加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 如果没有dotenv，使用默认值
    pass


class SecurityConfig:
    """安全配置类"""

    # LLM 配置
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.siliconflow.cn/v1/chat/completions')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'Pro/MiniMaxAI/MiniMax-M2.5')

    # Neo4j 配置
    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '')

    # JWT 配置
    JWT_SECRET = os.getenv('JWT_SECRET', 'your_jwt_secret_here')
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRATION = int(os.getenv('JWT_EXPIRATION', '3600'))

    # CORS 配置
    CORS_ORIGINS = [origin.strip() for origin in os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:8000,http://localhost:5173').split(',')]

    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'app.log')

    @classmethod
    def validate(cls):
        """验证配置有效性"""
        if not cls.OPENAI_API_KEY:
            print("警告: OPENAI_API_KEY 未配置")
        if not cls.NEO4J_PASSWORD:
            print("警告: NEO4J_PASSWORD 未配置")
        if cls.JWT_SECRET == 'your_jwt_secret_here':
            print("警告: JWT_SECRET 仍使用默认值，建议修改")

    @classmethod
    def get_api_key(cls, service):
        """获取指定服务的 API 密钥"""
        if service == 'openai':
            return cls.OPENAI_API_KEY
        elif service == 'neo4j':
            return cls.NEO4J_PASSWORD
        else:
            return None


# 全局安全配置实例
security_config = SecurityConfig()

# 验证配置
security_config.validate()
