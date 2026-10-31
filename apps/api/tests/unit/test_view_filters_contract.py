"""视图 `filters` 契约归一测试（契约裁定 2026-10-17）。

背景：设计器提交规则数组 `[{field, op, value}]`，而查询引擎消费字典
`{field: {op: value}}`。此前数组会在 `_compile_filters` 里 `dict.items()` 崩成 500。
现在请求边界归一，并保证既有字典调用方零影响。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from odap.biz.core.ontology.view.api.schemas import (
    CreateViewRequest,
    UpdateViewRequest,
    normalize_view_filters,
)


class TestNormalizeRulesToDict:
    def test_single_equality_rule(self):
        assert normalize_view_filters(
            [{"field": "category", "op": "=", "value": "生鲜"}]
        ) == {"category": {"eq": "生鲜"}}

    def test_operator_aliases(self):
        got = normalize_view_filters([
            {"field": "status", "op": "!=", "value": "void"},
            {"field": "return_rate", "op": ">", "value": "0.15"},
            {"field": "stock_turnover", "op": "<", "value": "2"},
            {"field": "supplier", "op": "contains", "value": "华东"},
        ])
        assert got == {
            "status": {"ne": "void"},
            "return_rate": {"gt": "0.15"},
            "stock_turnover": {"lt": "2"},
            "supplier": {"contains": "华东"},
        }

    def test_same_field_rules_merge_into_one_bucket(self):
        got = normalize_view_filters([
            {"field": "category", "op": "=", "value": "生鲜"},
            {"field": "category", "op": "contains", "value": "果"},
        ])
        assert got == {"category": {"eq": "生鲜", "contains": "果"}}

    def test_missing_op_defaults_to_equality(self):
        assert normalize_view_filters(
            [{"field": "category", "value": "生鲜"}]
        ) == {"category": {"eq": "生鲜"}}

    def test_empty_array_becomes_empty_dict(self):
        assert normalize_view_filters([]) == {}


class TestBackwardCompatibility:
    def test_dict_form_passes_through_unchanged(self):
        original = {"status": {"eq": "active"}, "amount": 100}
        assert normalize_view_filters(original) == original

    def test_none_and_empty(self):
        assert normalize_view_filters(None) == {}


class TestRejections:
    def test_unsupported_operator_is_rejected(self):
        with pytest.raises(ValueError) as exc:
            normalize_view_filters([{"field": "amount", "op": ">=", "value": 1}])
        assert "filters[0].op" in str(exc.value)

    def test_rule_without_field_is_rejected(self):
        with pytest.raises(ValueError) as exc:
            normalize_view_filters([{"op": "=", "value": "x"}])
        assert "field" in str(exc.value)

    def test_non_list_non_dict_is_rejected(self):
        with pytest.raises(ValueError):
            normalize_view_filters("category=生鲜")

    def test_string_rule_item_is_rejected(self):
        with pytest.raises(ValueError):
            normalize_view_filters(["category=生鲜"])


class TestSchemaLevel:
    def test_update_request_accepts_rule_array(self):
        request = UpdateViewRequest(filters=[
            {"field": "category", "op": "=", "value": "生鲜"},
        ])
        assert request.filters == {"category": {"eq": "生鲜"}}

    def test_update_request_keeps_none(self):
        assert UpdateViewRequest().filters is None

    def test_create_request_accepts_rule_array(self):
        request = CreateViewRequest(
            name="订单退货率看板", base_type_id="Order", role="analyst",
            filters=[{"field": "return_rate", "op": ">", "value": "0.15"}],
        )
        assert request.filters == {"return_rate": {"gt": "0.15"}}

    def test_invalid_rule_fails_validation(self):
        with pytest.raises(ValidationError):
            CreateViewRequest(
                name="x", base_type_id="Order", role="analyst",
                filters=[{"field": "return_rate", "op": "~=", "value": 1}],
            )
