"""外部服务连接验证器"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any

from odap.biz.platform.config.models.config_models import (
    ConfigValidationResult, ServiceCategory,
)

logger = logging.getLogger(__name__)


class ConfigValidator:
    """外部服务连接验证器"""

    def __init__(self):
        self._timeout = 10  # 秒

    async def validate(self, category: ServiceCategory, config: Dict[str, str]) -> ConfigValidationResult:
        """验证指定服务类别的连接"""
        validators = {
            ServiceCategory.LLM: self._test_llm,
            ServiceCategory.GRAPH_DB: self._test_graph_db,
            ServiceCategory.OBJECT_STORAGE: self._test_object_storage,
            ServiceCategory.POLICY_ENGINE: self._test_policy_engine,
            ServiceCategory.CACHE: self._test_cache,
            ServiceCategory.SEARCH: self._test_search,
            ServiceCategory.AUTH: self._test_auth,
            ServiceCategory.GENERAL: self._test_general,
        }
        validator = validators.get(category)
        if not validator:
            return ConfigValidationResult(
                category=category, success=False,
                message=f"No validator for category: {category.value}",
            )
        return await validator(config)

    async def validate_all(self, configs: Dict[str, Dict[str, str]]) -> List[ConfigValidationResult]:
        """验证所有服务类别"""
        tasks = []
        for cat in ServiceCategory:
            config = configs.get(cat.value, {})
            if config:
                tasks.append(self.validate(cat, config))
        if not tasks:
            return []
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _test_llm(self, config: Dict[str, str]) -> ConfigValidationResult:
        """测试 LLM 服务连接"""
        api_key = config.get("llm.api_key", "")
        api_base = config.get("llm.api_base", "")
        model = config.get("llm.model", "gpt-4")

        if not api_key:
            return ConfigValidationResult(
                category=ServiceCategory.LLM, success=False,
                message="API Key not configured",
            )

        start = time.time()
        try:
            import aiohttp
            url = f"{api_base.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1,
            }
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self._timeout)) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    elapsed = int((time.time() - start) * 1000)
                    if resp.status == 200:
                        return ConfigValidationResult(
                            category=ServiceCategory.LLM, success=True,
                            message="Connection successful", response_time_ms=elapsed,
                        )
                    else:
                        text = await resp.text()
                        return ConfigValidationResult(
                            category=ServiceCategory.LLM, success=False,
                            message=f"HTTP {resp.status}: {text[:200]}", response_time_ms=elapsed,
                        )
        except asyncio.TimeoutError:
            return ConfigValidationResult(
                category=ServiceCategory.LLM, success=False,
                message="Connection timeout", response_time_ms=self._timeout * 1000,
            )
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return ConfigValidationResult(
                category=ServiceCategory.LLM, success=False,
                message=str(e)[:200], response_time_ms=elapsed,
            )

    async def _test_graph_db(self, config: Dict[str, str]) -> ConfigValidationResult:
        """测试 Neo4j 连接"""
        uri = config.get("graph_db.uri", "")
        user = config.get("graph_db.user", "neo4j")
        password = config.get("graph_db.password", "")

        if not uri:
            return ConfigValidationResult(
                category=ServiceCategory.GRAPH_DB, success=False,
                message="URI not configured",
            )

        start = time.time()
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(uri, auth=(user, password))
            try:
                driver.verify_connectivity()
                elapsed = int((time.time() - start) * 1000)
                return ConfigValidationResult(
                    category=ServiceCategory.GRAPH_DB, success=True,
                    message="Connection successful", response_time_ms=elapsed,
                )
            finally:
                driver.close()
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return ConfigValidationResult(
                category=ServiceCategory.GRAPH_DB, success=False,
                message=str(e)[:200], response_time_ms=elapsed,
            )

    async def _test_object_storage(self, config: Dict[str, str]) -> ConfigValidationResult:
        """测试 MinIO 连接"""
        endpoint = config.get("object_storage.endpoint", "")
        access_key = config.get("object_storage.access_key", "")
        secret_key = config.get("object_storage.secret_key", "")
        secure = config.get("object_storage.secure", "false").lower() == "true"

        if not endpoint:
            return ConfigValidationResult(
                category=ServiceCategory.OBJECT_STORAGE, success=False,
                message="Endpoint not configured",
            )

        start = time.time()
        try:
            from minio import Minio
            client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
            client.list_buckets()
            elapsed = int((time.time() - start) * 1000)
            return ConfigValidationResult(
                category=ServiceCategory.OBJECT_STORAGE, success=True,
                message="Connection successful", response_time_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return ConfigValidationResult(
                category=ServiceCategory.OBJECT_STORAGE, success=False,
                message=str(e)[:200], response_time_ms=elapsed,
            )

    async def _test_policy_engine(self, config: Dict[str, str]) -> ConfigValidationResult:
        """测试 OPA 连接"""
        opa_url = config.get("policy_engine.opa_url", "")
        if not opa_url:
            return ConfigValidationResult(
                category=ServiceCategory.POLICY_ENGINE, success=False,
                message="OPA URL not configured",
            )

        start = time.time()
        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{opa_url.rstrip('/')}/v1/policies") as resp:
                    elapsed = int((time.time() - start) * 1000)
                    if resp.status == 200:
                        return ConfigValidationResult(
                            category=ServiceCategory.POLICY_ENGINE, success=True,
                            message="Connection successful", response_time_ms=elapsed,
                        )
                    return ConfigValidationResult(
                        category=ServiceCategory.POLICY_ENGINE, success=False,
                        message=f"HTTP {resp.status}", response_time_ms=elapsed,
                    )
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return ConfigValidationResult(
                category=ServiceCategory.POLICY_ENGINE, success=False,
                message=str(e)[:200], response_time_ms=elapsed,
            )

    async def _test_cache(self, config: Dict[str, str]) -> ConfigValidationResult:
        """测试 Redis 连接"""
        redis_url = config.get("cache.redis_url", "")
        if not redis_url:
            return ConfigValidationResult(
                category=ServiceCategory.CACHE, success=False,
                message="Redis URL not configured",
            )

        start = time.time()
        try:
            import redis
            client = redis.from_url(redis_url, socket_timeout=3)
            client.ping()
            elapsed = int((time.time() - start) * 1000)
            return ConfigValidationResult(
                category=ServiceCategory.CACHE, success=True,
                message="Connection successful", response_time_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return ConfigValidationResult(
                category=ServiceCategory.CACHE, success=False,
                message=str(e)[:200], response_time_ms=elapsed,
            )

    async def _test_search(self, config: Dict[str, str]) -> ConfigValidationResult:
        """测试搜索服务连接"""
        tavily_key = config.get("search.tavily_api_key", "")
        if tavily_key:
            start = time.time()
            try:
                import aiohttp
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self._timeout)) as session:
                    async with session.post(
                        "https://api.tavily.com/search",
                        json={"api_key": tavily_key, "query": "test", "max_results": 1},
                    ) as resp:
                        elapsed = int((time.time() - start) * 1000)
                        if resp.status == 200:
                            return ConfigValidationResult(
                                category=ServiceCategory.SEARCH, success=True,
                                message="Tavily connection successful", response_time_ms=elapsed,
                            )
                        return ConfigValidationResult(
                            category=ServiceCategory.SEARCH, success=False,
                            message=f"Tavily HTTP {resp.status}", response_time_ms=elapsed,
                        )
            except Exception as e:
                elapsed = int((time.time() - start) * 1000)
                return ConfigValidationResult(
                    category=ServiceCategory.SEARCH, success=False,
                    message=str(e)[:200], response_time_ms=elapsed,
                )

        return ConfigValidationResult(
            category=ServiceCategory.SEARCH, success=False,
            message="No search service configured",
        )

    async def _test_auth(self, config: Dict[str, str]) -> ConfigValidationResult:
        """测试认证配置"""
        secret = config.get("auth.jwt_secret", "")
        if not secret:
            return ConfigValidationResult(
                category=ServiceCategory.AUTH, success=False,
                message="JWT secret not configured",
            )
        if len(secret) < 32:
            return ConfigValidationResult(
                category=ServiceCategory.AUTH, success=False,
                message="JWT secret too short (minimum 32 characters)",
            )
        return ConfigValidationResult(
            category=ServiceCategory.AUTH, success=True,
            message="JWT configuration valid",
        )

    async def _test_general(self, config: Dict[str, str]) -> ConfigValidationResult:
        """通用配置无需连接测试"""
        return ConfigValidationResult(
            category=ServiceCategory.GENERAL, success=True,
            message="General settings (no connection test needed)",
        )
