import pytest
from odap.biz.core.ontology.application.runtime.state_machine.impl.expression_evaluator import safe_eval, SafeExpressionEvaluator


class TestSafeExpressionEvaluator:
    def test_simple_comparison(self):
        assert safe_eval("x > 5", {"x": 10}) is True
        assert safe_eval("x > 5", {"x": 3}) is False

    def test_equality(self):
        assert safe_eval("status == 'active'", {"status": "active"}) is True
        assert safe_eval("status == 'active'", {"status": "inactive"}) is False

    def test_boolean_and(self):
        assert safe_eval("x > 0 and y > 0", {"x": 1, "y": 1}) is True
        assert safe_eval("x > 0 and y > 0", {"x": 1, "y": -1}) is False

    def test_boolean_or(self):
        assert safe_eval("x > 0 or y > 0", {"x": -1, "y": 1}) is True
        assert safe_eval("x > 0 or y > 0", {"x": -1, "y": -1}) is False

    def test_not_operator(self):
        assert safe_eval("not active", {"active": False}) is True
        assert safe_eval("not active", {"active": True}) is False

    def test_in_operator(self):
        assert safe_eval("role in roles", {"role": "admin", "roles": ["admin", "user"]}) is True
        assert safe_eval("role in roles", {"role": "guest", "roles": ["admin", "user"]}) is False

    def test_attribute_access(self):
        assert safe_eval("obj.value > 0", {"obj": type("O", (), {"value": 5})()}) is True

    def test_subscript_access(self):
        assert safe_eval("data['key'] == 'val'", {"data": {"key": "val"}}) is True

    def test_arithmetic(self):
        assert safe_eval("count * price > 100", {"count": 10, "price": 15}) is True

    def test_empty_expression(self):
        assert safe_eval("", {}) is True
        assert safe_eval("  ", {}) is True

    def test_dangerous_code_blocked(self):
        assert safe_eval("__import__('os').system('ls')", {}) is False

    def test_dangerous_code_blocked_open(self):
        assert safe_eval("open('/etc/passwd')", {}) is False

    def test_safe_names(self):
        assert safe_eval("len(items) > 0", {"items": [1, 2, 3]}) is True
        assert safe_eval("abs(x) == 5", {"x": -5}) is True

    def test_chained_comparison(self):
        assert safe_eval("0 < x < 10", {"x": 5}) is True
        assert safe_eval("0 < x < 10", {"x": 15}) is False

    def test_if_expression(self):
        assert safe_eval("a if condition else b", {"a": True, "b": False, "condition": True}) is True
        assert safe_eval("a if condition else b", {"a": True, "b": False, "condition": False}) is False
