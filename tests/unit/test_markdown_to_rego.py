import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.infra.opa.routes import MarkdownPolicyConverter


class TestMarkdownPolicyConverter:
    @pytest.fixture
    def converter(self):
        return MarkdownPolicyConverter()

    def test_basic_role_policy(self, converter):
        md = """# Commander Policy

## 角色: commander

## 允许的操作
- 查询
- 攻击（需确认）
- 防御

## 规则
如果 角色是 commander 且 操作是 attack 那么 允许
"""
        rego = converter.convert(md)
        assert "package policies.commander_policy" in rego
        assert 'input.user.role == "commander"' in rego
        assert '"view"' in rego
        assert '"attack"' in rego
        assert "default allow := false" in rego

    def test_action_with_conditions(self, converter):
        md = """# Test Policy

## 允许的操作
- 攻击（需确认）
- 撤退（需审批）
- 增援（高风险）
"""
        rego = converter.convert(md)
        assert "input.confirmed == true" in rego
        assert "input.approved == true" in rego
        assert 'input.risk_level != "high"' in rego

    def test_rule_with_conditions(self, converter):
        md = """# Test Policy

## 规则
- 如果 角色是 commander 且 操作是 attack 那么 允许
"""
        rego = converter.convert(md)
        assert 'input.user.role == "commander"' in rego
        assert 'input.action == "attack"' in rego

    def test_deny_rule(self, converter):
        md = """# Test Policy

## 规则
- 如果 角色是 guest 且 操作是 attack 那么 拒绝
"""
        rego = converter.convert(md)
        assert "deny if" in rego

    def test_empty_markdown(self, converter):
        md = ""
        rego = converter.convert(md)
        assert "package domain.custom" in rego
        assert "default allow := false" in rego

    def test_action_name_mapping(self, converter):
        md = """# Test

## 允许的操作
- 查询
- 移动
- 观察
- 通信
"""
        rego = converter.convert(md)
        assert '"view"' in rego
        assert '"move"' in rego
        assert '"observe"' in rego
        assert '"communicate"' in rego

    def test_english_role(self, converter):
        md = """# Test

## Role: admin

## Allowed
- 查询
- 攻击
"""
        rego = converter.convert(md)
        assert 'input.user.role == "admin"' in rego

    def test_generates_valid_rego_structure(self, converter):
        md = """# Commander Policy

## 角色: commander

## 允许的操作
- 查询
- 攻击（需确认）
"""
        rego = converter.convert(md)
        assert "import future.keywords.if" in rego
        assert "import future.keywords.in" in rego
        assert "allowed_actions :=" in rego
