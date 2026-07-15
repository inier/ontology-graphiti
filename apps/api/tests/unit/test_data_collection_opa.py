"""OPA 数据采集策略单元测试

测试 data_collection.rego 策略的权限控制逻辑：
- 搜索权限：admin/analyst 允许，其他角色拒绝
- 爬取权限：admin 允许，analyst 需域名白名单，其他角色拒绝
- 浏览器自动化：仅 admin 允许
- 域名白名单：在白名单内允许，不在白名单拒绝
- OPA 桥接：SkillExecutorV2 的 package:action 路由
"""

import pytest
from unittest.mock import MagicMock, patch


# ============================================================
# Rego 策略逻辑的 Python 等价测试
# （无需 OPA 服务运行，直接验证策略规则逻辑）
# ============================================================

# 域名白名单（与 data_collection.rego 保持同步）
ALLOWED_DOMAINS = [
    "reuters.com",
    "bbc.com",
    "bloomberg.com",
    "xinhuanet.com",
    "people.com.cn",
    "thepaper.cn",
    "36kr.com",
    "caixin.com",
    "gov.cn",
    "nature.com",
    "science.org",
    "arxiv.org",
    "github.com",
    "wikipedia.org",
]


def check_data_collection_policy(role: str, action: str, target_domain: str = "") -> bool:
    """Python 等价实现 data_collection.rego 策略逻辑

    用于单元测试验证，与 Rego 策略规则一一对应。
    """
    # 搜索：admin 和 analyst 均可
    if action == "search" and role in ("admin", "analyst"):
        return True

    # 爬取：admin 直接允许
    if action == "crawl" and role == "admin":
        return True

    # 爬取：analyst 需域名白名单
    if action == "crawl" and role == "analyst":
        if target_domain in ALLOWED_DOMAINS:
            return True

    # 浏览器自动化：仅 admin
    if action == "browser" and role == "admin":
        return True

    # 默认拒绝
    return False


class TestDataCollectionOPASearch:
    """搜索权限测试"""

    def test_admin_search_allowed(self):
        assert check_data_collection_policy("admin", "search") is True

    def test_analyst_search_allowed(self):
        assert check_data_collection_policy("analyst", "search") is True

    def test_operator_search_denied(self):
        assert check_data_collection_policy("operator", "search") is False

    def test_guest_search_denied(self):
        assert check_data_collection_policy("guest", "search") is False

    def test_viewer_search_denied(self):
        assert check_data_collection_policy("viewer", "search") is False


class TestDataCollectionOPACrawl:
    """爬取权限测试"""

    def test_admin_crawl_any_domain_allowed(self):
        """admin 可以爬取任意域名"""
        assert check_data_collection_policy("admin", "crawl", "evil.com") is True

    def test_admin_crawl_no_domain_allowed(self):
        """admin 爬取不需要域名参数"""
        assert check_data_collection_policy("admin", "crawl") is True

    def test_analyst_crawl_whitelisted_domain_allowed(self):
        """analyst 爬取白名单域名允许"""
        for domain in ALLOWED_DOMAINS:
            assert check_data_collection_policy("analyst", "crawl", domain) is True, \
                f"analyst should be allowed to crawl {domain}"

    def test_analyst_crawl_non_whitelisted_domain_denied(self):
        """analyst 爬取非白名单域名拒绝"""
        assert check_data_collection_policy("analyst", "crawl", "evil.com") is False

    def test_analyst_crawl_empty_domain_denied(self):
        """analyst 爬取空域名拒绝"""
        assert check_data_collection_policy("analyst", "crawl", "") is False

    def test_guest_crawl_denied(self):
        assert check_data_collection_policy("guest", "crawl", "reuters.com") is False

    def test_operator_crawl_denied(self):
        assert check_data_collection_policy("operator", "crawl", "bbc.com") is False


class TestDataCollectionOPABrowser:
    """浏览器自动化权限测试"""

    def test_admin_browser_allowed(self):
        assert check_data_collection_policy("admin", "browser") is True

    def test_analyst_browser_denied(self):
        assert check_data_collection_policy("analyst", "browser") is False

    def test_guest_browser_denied(self):
        assert check_data_collection_policy("guest", "browser") is False


class TestDataCollectionOPADomainWhitelist:
    """域名白名单完整性测试"""

    def test_all_whitelisted_domains_allowed_for_analyst_crawl(self):
        """验证白名单中所有域名对 analyst 爬取均允许"""
        for domain in ALLOWED_DOMAINS:
            assert check_data_collection_policy("analyst", "crawl", domain) is True

    def test_non_whitelisted_domains_denied_for_analyst_crawl(self):
        """验证非白名单域名对 analyst 爬取均拒绝"""
        non_whitelisted = [
            "evil.com", "malware.org", "phishing.net",
            "facebook.com", "twitter.com", "google.com",
        ]
        for domain in non_whitelisted:
            assert check_data_collection_policy("analyst", "crawl", domain) is False

    def test_subdomain_not_auto_allowed(self):
        """子域名不自动允许（如 sub.reuters.com 不在白名单中）"""
        assert check_data_collection_policy("analyst", "crawl", "sub.reuters.com") is False

    def test_www_prefix_not_in_whitelist(self):
        """www 前缀不在白名单中（需在应用层 strip www.）"""
        assert check_data_collection_policy("analyst", "crawl", "www.reuters.com") is False


class TestDataCollectionOPADefaultDeny:
    """默认拒绝测试"""

    def test_unknown_action_denied(self):
        """未知操作默认拒绝"""
        assert check_data_collection_policy("admin", "unknown_action") is False

    def test_unknown_role_denied(self):
        """未知角色默认拒绝"""
        assert check_data_collection_policy("stranger", "search") is False

    def test_empty_action_denied(self):
        assert check_data_collection_policy("admin", "") is False

    def test_empty_role_denied(self):
        assert check_data_collection_policy("", "search") is False


# ============================================================
# OPA 桥接集成测试（SkillExecutorV2 层面）
# ============================================================

class TestSkillExecutorOPABridge:
    """测试 SkillExecutorV2 的 OPA 包级检查桥接"""

    def test_opa_action_format_parsed_correctly(self):
        """验证 opa_action "package:action" 格式被正确解析"""
        from odap.tools.base import SkillExecutorV2, SkillHotSwapper, SkillRegistry

        registry = SkillRegistry()
        hot_swapper = SkillHotSwapper(registry)
        executor = SkillExecutorV2(hot_swapper)

        # 模拟 opa_manager
        mock_opa = MagicMock()
        mock_opa.check_package_permission.return_value = True
        executor.opa_manager = mock_opa

        # 注册一个带 data_collection:search opa_action 的 Skill
        from odap.tools.web.web_skills import _web_search_skill
        hot_swapper.register(_web_search_skill)

        # 执行 OPA 检查
        result = executor._check_opa_permission(
            "web_search",
            user={"role": "analyst"},
            input_data={"query": "test"},
        )

        assert result is True
        # 验证调用了包级检查，传入正确的 package 和 action
        mock_opa.check_package_permission.assert_called_once()
        call_args = mock_opa.check_package_permission.call_args
        assert call_args[0][0] == "data_collection"  # package
        assert call_args[0][1]["action"] == "search"  # action
        assert call_args[0][1]["role"] == "analyst"  # role

    def test_crawl_opa_extracts_target_domain(self):
        """验证爬取 OPA 检查从 URL 提取 target_domain"""
        from odap.tools.base import SkillExecutorV2, SkillHotSwapper, SkillRegistry

        registry = SkillRegistry()
        hot_swapper = SkillHotSwapper(registry)
        executor = SkillExecutorV2(hot_swapper)

        mock_opa = MagicMock()
        mock_opa.check_package_permission.return_value = True
        executor.opa_manager = mock_opa

        from odap.tools.web.web_skills import _web_crawl_skill
        hot_swapper.register(_web_crawl_skill)

        result = executor._check_opa_permission(
            "web_crawl",
            user={"role": "analyst"},
            input_data={"url": "https://www.reuters.com/article/123"},
        )

        assert result is True
        call_args = mock_opa.check_package_permission.call_args
        opa_input = call_args[0][1]
        assert opa_input["action"] == "crawl"
        assert opa_input["target_domain"] == "reuters.com"  # www. 已被 strip

    def test_crawl_opa_without_url_no_target_domain(self):
        """验证无 URL 时不传 target_domain"""
        from odap.tools.base import SkillExecutorV2, SkillHotSwapper, SkillRegistry

        registry = SkillRegistry()
        hot_swapper = SkillHotSwapper(registry)
        executor = SkillExecutorV2(hot_swapper)

        mock_opa = MagicMock()
        mock_opa.check_package_permission.return_value = True
        executor.opa_manager = mock_opa

        from odap.tools.web.web_skills import _web_crawl_skill
        hot_swapper.register(_web_crawl_skill)

        result = executor._check_opa_permission(
            "web_crawl",
            user={"role": "analyst"},
            input_data={},
        )

        assert result is True
        call_args = mock_opa.check_package_permission.call_args
        opa_input = call_args[0][1]
        assert "target_domain" not in opa_input

    def test_legacy_opa_action_without_colon(self):
        """验证旧格式 opa_action（无冒号）走 domain 包"""
        from odap.tools.base import SkillExecutorV2, SkillHotSwapper, SkillRegistry

        registry = SkillRegistry()
        hot_swapper = SkillHotSwapper(registry)
        executor = SkillExecutorV2(hot_swapper)

        mock_opa = MagicMock()
        mock_opa.check_permission.return_value = True
        executor.opa_manager = mock_opa

        # 创建一个旧格式 opa_action 的 Skill
        from odap.tools.base import BaseSkill, SkillMetadata, SkillInput

        class LegacySkill(BaseSkill):
            metadata = SkillMetadata(
                name="legacy_test",
                description="test",
                opa_action="some_action",  # 无冒号
                requires_opa_check=True,
            )

            def execute(self, input_data):
                from odap.tools.base import SkillOutput
                return SkillOutput(success=True, skill_name="legacy_test")

        hot_swapper.register(LegacySkill())

        result = executor._check_opa_permission(
            "legacy_test",
            user={"role": "admin"},
        )

        assert result is True
        # 应该调用 check_permission 而非 check_package_permission
        mock_opa.check_permission.assert_called_once()
        mock_opa.check_package_permission.assert_not_called()

    def test_opa_deny_returns_false(self):
        """验证 OPA 拒绝时返回 False"""
        from odap.tools.base import SkillExecutorV2, SkillHotSwapper, SkillRegistry

        registry = SkillRegistry()
        hot_swapper = SkillHotSwapper(registry)
        executor = SkillExecutorV2(hot_swapper)

        mock_opa = MagicMock()
        mock_opa.check_package_permission.return_value = False
        executor.opa_manager = mock_opa

        from odap.tools.web.web_skills import _web_search_skill
        hot_swapper.register(_web_search_skill)

        result = executor._check_opa_permission(
            "web_search",
            user={"role": "guest"},
            input_data={"query": "test"},
        )

        assert result is False


class TestSkillHealthStatusTracking:
    """测试 Skill 健康状态自动降级"""

    def test_health_starts_healthy(self):
        """新注册的 Skill 健康状态为 healthy"""
        from odap.tools.base import (
            SkillHotSwapper, SkillRegistry, HealthStatus,
        )
        from odap.tools.web.web_skills import _web_search_skill

        registry = SkillRegistry()
        hot_swapper = SkillHotSwapper(registry)
        hot_swapper.register(_web_search_skill)

        health = hot_swapper.get_health_info("web_search")
        assert health is not None
        assert health.health == HealthStatus.HEALTHY.value

    def test_health_degrades_on_failures(self):
        """连续失败后健康状态降级为 degraded"""
        from odap.tools.base import (
            SkillExecutorV2, SkillHotSwapper, SkillRegistry,
            SkillOutput, HealthStatus,
        )

        registry = SkillRegistry()
        hot_swapper = SkillHotSwapper(registry)
        executor = SkillExecutorV2(hot_swapper)

        # 创建一个总是失败的 Skill
        from odap.tools.base import BaseSkill, SkillMetadata, SkillInput

        class FailingSkill(BaseSkill):
            metadata = SkillMetadata(name="failing_test", description="test")
            input_schema = SkillInput

            def execute(self, input_data):
                return SkillOutput(success=False, error="always fails", skill_name="failing_test", execution_time_ms=0)

        hot_swapper.register(FailingSkill())

        # 执行 3 次失败
        for _ in range(3):
            executor.execute("failing_test", {}, retry=False)

        health = hot_swapper.get_health_info("failing_test")
        assert health.health == HealthStatus.DEGRADED.value
        assert health.failed_calls == 3

    def test_health_unhealthy_on_many_failures(self):
        """大量失败后健康状态降级为 unhealthy"""
        from odap.tools.base import (
            SkillExecutorV2, SkillHotSwapper, SkillRegistry,
            SkillOutput, HealthStatus,
        )

        registry = SkillRegistry()
        hot_swapper = SkillHotSwapper(registry)
        executor = SkillExecutorV2(hot_swapper)

        from odap.tools.base import BaseSkill, SkillMetadata, SkillInput

        class FailingSkill(BaseSkill):
            metadata = SkillMetadata(name="very_failing_test", description="test")
            input_schema = SkillInput

            def execute(self, input_data):
                return SkillOutput(success=False, error="always fails", skill_name="very_failing_test", execution_time_ms=0)

        hot_swapper.register(FailingSkill())

        # 执行 6 次失败（成功率 0% < 50%）
        for _ in range(6):
            executor.execute("very_failing_test", {}, retry=False)

        health = hot_swapper.get_health_info("very_failing_test")
        assert health.health == HealthStatus.UNHEALTHY.value

    def test_health_stays_healthy_on_success(self):
        """成功调用后健康状态保持 healthy"""
        from odap.tools.base import (
            SkillExecutorV2, SkillHotSwapper, SkillRegistry,
            SkillOutput, HealthStatus,
        )

        registry = SkillRegistry()
        hot_swapper = SkillHotSwapper(registry)
        executor = SkillExecutorV2(hot_swapper)

        from odap.tools.base import BaseSkill, SkillMetadata, SkillInput

        class SuccessSkill(BaseSkill):
            metadata = SkillMetadata(name="success_test", description="test")
            input_schema = SkillInput

            def execute(self, input_data):
                return SkillOutput(success=True, skill_name="success_test", execution_time_ms=0)

        hot_swapper.register(SuccessSkill())

        for _ in range(5):
            executor.execute("success_test", {}, retry=False)

        health = hot_swapper.get_health_info("success_test")
        assert health.health == HealthStatus.HEALTHY.value
        assert health.success_calls == 5

    def test_health_report_includes_web_skills(self):
        """健康报告包含 web skills"""
        from odap.tools.base import SkillRegistryV2
        from odap.tools.web.web_skills import _web_search_skill, _web_crawl_skill

        reg_v2 = SkillRegistryV2()
        reg_v2.register(_web_search_skill)
        reg_v2.register(_web_crawl_skill)

        report = reg_v2.get_health_report()
        assert report["total_skills"] >= 2
        skill_names = [s.name for s in report["skills"]]
        assert "web_search" in skill_names
        assert "web_crawl" in skill_names
