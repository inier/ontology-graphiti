"""ConfigValidator 连接验证测试"""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def validator():
    """创建 ConfigValidator"""
    from odap.biz.platform.config.impl.config_validator import ConfigValidator
    return ConfigValidator()


class TestConfigValidatorAuth:
    """Auth 服务验证测试（无需外部连接）"""

    @pytest.mark.asyncio
    async def test_auth_missing_secret(self, validator):
        """测试 JWT 密钥未配置"""
        from odap.biz.platform.config.models.config_models import ServiceCategory
        result = await validator.validate(ServiceCategory.AUTH, {})
        assert result.success is False
        assert "not configured" in result.message

    @pytest.mark.asyncio
    async def test_auth_short_secret(self, validator):
        """测试 JWT 密钥太短"""
        from odap.biz.platform.config.models.config_models import ServiceCategory
        result = await validator.validate(ServiceCategory.AUTH, {"auth.jwt_secret": "short"})
        assert result.success is False
        assert "too short" in result.message

    @pytest.mark.asyncio
    async def test_auth_valid_secret(self, validator):
        """测试有效的 JWT 密钥"""
        from odap.biz.platform.config.models.config_models import ServiceCategory
        result = await validator.validate(ServiceCategory.AUTH, {"auth.jwt_secret": "a" * 64})
        assert result.success is True


class TestConfigValidatorGeneral:
    """General 服务验证测试"""

    @pytest.mark.asyncio
    async def test_general_always_succeeds(self, validator):
        """测试通用配置总是成功"""
        from odap.biz.platform.config.models.config_models import ServiceCategory
        result = await validator.validate(ServiceCategory.GENERAL, {})
        assert result.success is True


class TestConfigValidatorLLM:
    """LLM 服务验证测试（mock 外部连接）"""

    @pytest.mark.asyncio
    async def test_llm_missing_api_key(self, validator):
        """测试 LLM API Key 未配置"""
        from odap.biz.platform.config.models.config_models import ServiceCategory
        result = await validator.validate(ServiceCategory.LLM, {})
        assert result.success is False
        assert "not configured" in result.message

    @pytest.mark.asyncio
    async def test_llm_connection_success(self, validator):
        """测试 LLM 连接成功（mock aiohttp）"""
        from odap.biz.platform.config.models.config_models import ServiceCategory

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value='{"id":"test"}')
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await validator.validate(ServiceCategory.LLM, {
                "llm.api_key": "sk-test",
                "llm.api_base": "https://api.openai.com/v1",
                "llm.model": "gpt-4",
            })
            assert result.success is True

    @pytest.mark.asyncio
    async def test_llm_connection_unauthorized(self, validator):
        """测试 LLM 连接认证失败（mock aiohttp）"""
        from odap.biz.platform.config.models.config_models import ServiceCategory

        mock_response = MagicMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value='{"error":"unauthorized"}')
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await validator.validate(ServiceCategory.LLM, {
                "llm.api_key": "sk-invalid",
                "llm.api_base": "https://api.openai.com/v1",
                "llm.model": "gpt-4",
            })
            assert result.success is False


class TestConfigValidatorGraphDB:
    """GraphDB 服务验证测试（mock 外部连接）"""

    @pytest.mark.asyncio
    async def test_graph_db_missing_uri(self, validator):
        """测试 Neo4j URI 未配置"""
        from odap.biz.platform.config.models.config_models import ServiceCategory
        result = await validator.validate(ServiceCategory.GRAPH_DB, {})
        assert result.success is False
        assert "not configured" in result.message

    @pytest.mark.asyncio
    async def test_graph_db_connection_success(self, validator):
        """测试 Neo4j 连接成功（mock）"""
        from odap.biz.platform.config.models.config_models import ServiceCategory

        mock_driver = MagicMock()
        mock_driver.verify_connectivity = MagicMock()
        mock_driver.close = MagicMock()

        with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
            result = await validator.validate(ServiceCategory.GRAPH_DB, {
                "graph_db.uri": "bolt://localhost:7687",
                "graph_db.user": "neo4j",
                "graph_db.password": "test",
            })
            assert result.success is True

    @pytest.mark.asyncio
    async def test_graph_db_connection_failure(self, validator):
        """测试 Neo4j 连接失败（mock）"""
        from odap.biz.platform.config.models.config_models import ServiceCategory

        with patch("neo4j.GraphDatabase.driver", side_effect=Exception("Connection refused")):
            result = await validator.validate(ServiceCategory.GRAPH_DB, {
                "graph_db.uri": "bolt://localhost:7687",
                "graph_db.user": "neo4j",
                "graph_db.password": "test",
            })
            assert result.success is False


class TestConfigValidatorCache:
    """Cache 服务验证测试（mock 外部连接）"""

    @pytest.mark.asyncio
    async def test_cache_missing_url(self, validator):
        """测试 Redis URL 未配置"""
        from odap.biz.platform.config.models.config_models import ServiceCategory
        result = await validator.validate(ServiceCategory.CACHE, {})
        assert result.success is False
        assert "not configured" in result.message

    @pytest.mark.asyncio
    async def test_cache_connection_success(self, validator):
        """测试 Redis 连接成功（mock）"""
        from odap.biz.platform.config.models.config_models import ServiceCategory
        try:
            import redis
        except ImportError:
            pytest.skip("redis not installed")

        mock_client = MagicMock()
        mock_client.ping = MagicMock(return_value=True)
        mock_client.from_url = MagicMock(return_value=mock_client)

        with patch("redis.from_url", return_value=mock_client):
            result = await validator.validate(ServiceCategory.CACHE, {
                "cache.redis_url": "redis://localhost:6379/0",
            })
            assert result.success is True


class TestConfigValidatorPolicyEngine:
    """PolicyEngine 服务验证测试（mock 外部连接）"""

    @pytest.mark.asyncio
    async def test_policy_engine_missing_url(self, validator):
        """测试 OPA URL 未配置"""
        from odap.biz.platform.config.models.config_models import ServiceCategory
        result = await validator.validate(ServiceCategory.POLICY_ENGINE, {})
        assert result.success is False
        assert "not configured" in result.message

    @pytest.mark.asyncio
    async def test_policy_engine_connection_success(self, validator):
        """测试 OPA 连接成功（mock aiohttp）"""
        from odap.biz.platform.config.models.config_models import ServiceCategory

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await validator.validate(ServiceCategory.POLICY_ENGINE, {
                "policy_engine.opa_url": "http://localhost:8181",
            })
            assert result.success is True
