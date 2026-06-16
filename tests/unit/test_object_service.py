"""ObjectService 单元测试

覆盖:
- _match_filters: EQ / NE / CONTAINS / IN / IS_NULL / IS_NOT_NULL 操作符
- _apply_sorts: 升序 / 降序 / 多字段排序
- query_objects: 按类型查询 / 全源查询 / 分页 / 排序 / links / actions
- semantic_query: 图谱搜索 / 结果去重 / 异常降级
- get_object: 单对象获取 / 未找到返回 None
- Schemas: ObjectQuery / ObjectQueryResult / ObjectQueryOperator 等
"""
from __future__ import annotations

import asyncio
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from odap.infra.object_service.schemas import (
    ObjectQuery,
    ObjectQueryFilter,
    ObjectQueryOperator,
    ObjectQueryResult,
    ObjectQueryResponse,
    ObjectQuerySort,
    SemanticQuery,
    SemanticQueryResponse,
)
from odap.infra.object_service.object_service import ObjectService


# ============================================================
# 工厂函数
# ============================================================


def _make_filter(
    field: str = "name",
    operator: ObjectQueryOperator = ObjectQueryOperator.EQ,
    value: Any = None,
) -> ObjectQueryFilter:
    """构造测试用 ObjectQueryFilter"""
    return ObjectQueryFilter(field=field, operator=operator, value=value)


def _make_result(
    object_id: str = "obj-1",
    object_type: str = "Entity",
    properties: Dict[str, Any] | None = None,
    source: str = "graph",
) -> ObjectQueryResult:
    """构造测试用 ObjectQueryResult"""
    if properties is None:
        properties = {"name": "test"}
    return ObjectQueryResult(
        object_id=object_id,
        object_type=object_type,
        properties=properties,
        links=[],
        available_actions=[],
        source=source,
    )


def _make_query(**overrides) -> ObjectQuery:
    """构造测试用 ObjectQuery"""
    defaults = dict(
        object_type=None,
        filters=[],
        sorts=[],
        limit=50,
        offset=0,
        include_links=False,
        include_actions=False,
        link_depth=1,
    )
    defaults.update(overrides)
    return ObjectQuery(**defaults)


# ============================================================
# 1. Schemas 模型测试
# ============================================================


class TestObjectQueryOperatorSchema(unittest.TestCase):
    """ObjectQueryOperator 枚举必须 (str, Enum) 双继承"""

    def test_str_enum_compatibility(self):
        self.assertEqual(ObjectQueryOperator.EQ, "eq")
        self.assertEqual(ObjectQueryOperator.NE.value, "ne")
        self.assertEqual(ObjectQueryOperator.CONTAINS.value, "contains")

    def test_all_operators_exist(self):
        expected = {"eq", "ne", "gt", "gte", "lt", "lte", "contains",
                    "starts_with", "in", "not_in", "is_null", "is_not_null"}
        actual = {op.value for op in ObjectQueryOperator}
        self.assertEqual(actual, expected)


class TestObjectQueryFilterSchema(unittest.TestCase):
    """ObjectQueryFilter 默认值与字段验证"""

    def test_default_operator_is_eq(self):
        f = ObjectQueryFilter(field="name")
        self.assertEqual(f.operator, ObjectQueryOperator.EQ)

    def test_default_value_is_none(self):
        f = ObjectQueryFilter(field="name")
        self.assertIsNone(f.value)

    def test_custom_operator_and_value(self):
        f = ObjectQueryFilter(field="status", operator=ObjectQueryOperator.IN, value=["a", "b"])
        self.assertEqual(f.operator, ObjectQueryOperator.IN)
        self.assertEqual(f.value, ["a", "b"])


class TestObjectQuerySortSchema(unittest.TestCase):
    """ObjectQuerySort 默认升序"""

    def test_default_ascending_true(self):
        s = ObjectQuerySort(field="name")
        self.assertTrue(s.ascending)

    def test_descending(self):
        s = ObjectQuerySort(field="name", ascending=False)
        self.assertFalse(s.ascending)


class TestObjectQuerySchema(unittest.TestCase):
    """ObjectQuery 默认值与容器字段 default_factory"""

    def test_default_values(self):
        q = ObjectQuery()
        self.assertIsNone(q.object_type)
        self.assertEqual(q.filters, [])
        self.assertEqual(q.sorts, [])
        self.assertEqual(q.limit, 50)
        self.assertEqual(q.offset, 0)
        self.assertFalse(q.include_links)
        self.assertFalse(q.include_actions)
        self.assertEqual(q.link_depth, 1)

    def test_default_factory_container_fields(self):
        """容器字段必须用 default_factory（规则 5）"""
        q1 = ObjectQuery()
        q1.filters.append(_make_filter())
        q2 = ObjectQuery()
        self.assertEqual(len(q2.filters), 0)

    def test_limit_bounds(self):
        with self.assertRaises(Exception):
            ObjectQuery(limit=0)
        with self.assertRaises(Exception):
            ObjectQuery(limit=1001)

    def test_offset_bounds(self):
        with self.assertRaises(Exception):
            ObjectQuery(offset=-1)


class TestObjectQueryResultSchema(unittest.TestCase):
    """ObjectQueryResult 默认值与容器字段"""

    def test_minimal_construction(self):
        r = ObjectQueryResult(object_id="id-1", object_type="Entity")
        self.assertEqual(r.object_id, "id-1")
        self.assertEqual(r.properties, {})
        self.assertEqual(r.links, [])
        self.assertEqual(r.available_actions, [])
        self.assertEqual(r.source, "")
        self.assertIsNone(r.score)

    def test_default_factory_isolation(self):
        r1 = ObjectQueryResult(object_id="id-1", object_type="Entity")
        r1.properties["key"] = "v"
        r2 = ObjectQueryResult(object_id="id-2", object_type="Entity")
        self.assertNotIn("key", r2.properties)


class TestObjectQueryResponseSchema(unittest.TestCase):
    """ObjectQueryResponse 字段"""

    def test_construction(self):
        resp = ObjectQueryResponse(
            results=[_make_result()],
            total=1,
            limit=50,
            offset=0,
        )
        self.assertEqual(resp.total, 1)
        self.assertEqual(len(resp.results), 1)


class TestSemanticQuerySchema(unittest.TestCase):
    """SemanticQuery 默认值"""

    def test_defaults(self):
        q = SemanticQuery(query_text="hello")
        self.assertEqual(q.query_text, "hello")
        self.assertIsNone(q.object_type)
        self.assertEqual(q.top_k, 10)
        self.assertTrue(q.include_links)
        self.assertEqual(q.link_depth, 1)


class TestSemanticQueryResponseSchema(unittest.TestCase):
    """SemanticQueryResponse 字段"""

    def test_construction(self):
        resp = SemanticQueryResponse(results=[_make_result()], total=1)
        self.assertEqual(resp.total, 1)


# ============================================================
# 2. _match_filters 测试
# ============================================================


class TestMatchFilters(unittest.TestCase):
    """_match_filters 各种操作符匹配逻辑"""

    def setUp(self):
        self.service = ObjectService()

    def test_empty_filters_returns_true(self):
        self.assertTrue(self.service._match_filters({"name": "Alice"}, []))

    def test_eq_match(self):
        filters = [_make_filter(field="status", operator=ObjectQueryOperator.EQ, value="active")]
        self.assertTrue(self.service._match_filters({"status": "active"}, filters))

    def test_eq_no_match(self):
        filters = [_make_filter(field="status", operator=ObjectQueryOperator.EQ, value="active")]
        self.assertFalse(self.service._match_filters({"status": "inactive"}, filters))

    def test_ne_match(self):
        filters = [_make_filter(field="status", operator=ObjectQueryOperator.NE, value="inactive")]
        self.assertTrue(self.service._match_filters({"status": "active"}, filters))

    def test_ne_no_match(self):
        filters = [_make_filter(field="status", operator=ObjectQueryOperator.NE, value="active")]
        self.assertFalse(self.service._match_filters({"status": "active"}, filters))

    def test_contains_match(self):
        filters = [_make_filter(field="name", operator=ObjectQueryOperator.CONTAINS, value="ali")]
        self.assertTrue(self.service._match_filters({"name": "Alice"}, filters))

    def test_contains_case_insensitive(self):
        filters = [_make_filter(field="name", operator=ObjectQueryOperator.CONTAINS, value="ALI")]
        self.assertTrue(self.service._match_filters({"name": "alice"}, filters))

    def test_contains_no_match(self):
        filters = [_make_filter(field="name", operator=ObjectQueryOperator.CONTAINS, value="bob")]
        self.assertFalse(self.service._match_filters({"name": "Alice"}, filters))

    def test_in_match(self):
        filters = [_make_filter(field="status", operator=ObjectQueryOperator.IN, value=["active", "pending"])]
        self.assertTrue(self.service._match_filters({"status": "active"}, filters))

    def test_in_no_match(self):
        filters = [_make_filter(field="status", operator=ObjectQueryOperator.IN, value=["inactive"])]
        self.assertFalse(self.service._match_filters({"status": "active"}, filters))

    def test_in_empty_list_no_match(self):
        filters = [_make_filter(field="status", operator=ObjectQueryOperator.IN, value=[])]
        self.assertFalse(self.service._match_filters({"status": "active"}, filters))

    def test_in_null_value_no_match(self):
        filters = [_make_filter(field="status", operator=ObjectQueryOperator.IN, value=None)]
        self.assertFalse(self.service._match_filters({"status": "active"}, filters))

    def test_is_null_match(self):
        filters = [_make_filter(field="email", operator=ObjectQueryOperator.IS_NULL)]
        self.assertTrue(self.service._match_filters({"name": "Alice"}, filters))

    def test_is_null_no_match(self):
        filters = [_make_filter(field="email", operator=ObjectQueryOperator.IS_NULL)]
        self.assertFalse(self.service._match_filters({"email": "a@x.com"}, filters))

    def test_is_not_null_match(self):
        filters = [_make_filter(field="email", operator=ObjectQueryOperator.IS_NOT_NULL)]
        self.assertTrue(self.service._match_filters({"email": "a@x.com"}, filters))

    def test_is_not_null_no_match(self):
        filters = [_make_filter(field="email", operator=ObjectQueryOperator.IS_NOT_NULL)]
        self.assertFalse(self.service._match_filters({"name": "Alice"}, filters))

    def test_multiple_filters_all_must_match(self):
        filters = [
            _make_filter(field="status", operator=ObjectQueryOperator.EQ, value="active"),
            _make_filter(field="name", operator=ObjectQueryOperator.CONTAINS, value="ali"),
        ]
        self.assertTrue(self.service._match_filters({"status": "active", "name": "Alice"}, filters))

    def test_multiple_filters_one_fails(self):
        filters = [
            _make_filter(field="status", operator=ObjectQueryOperator.EQ, value="active"),
            _make_filter(field="name", operator=ObjectQueryOperator.CONTAINS, value="bob"),
        ]
        self.assertFalse(self.service._match_filters({"status": "active", "name": "Alice"}, filters))

    def test_missing_field_eq_fails(self):
        """字段不存在时 EQ 比较应失败（None != target）"""
        filters = [_make_filter(field="missing", operator=ObjectQueryOperator.EQ, value="x")]
        self.assertFalse(self.service._match_filters({"name": "Alice"}, filters))


# ============================================================
# 3. _apply_sorts 测试
# ============================================================


class TestApplySorts(unittest.TestCase):
    """_apply_sorts 升序 / 降序 / 多字段排序"""

    def setUp(self):
        self.service = ObjectService()

    def test_ascending_sort(self):
        results = [
            _make_result(object_id="2", properties={"name": "Banana"}),
            _make_result(object_id="1", properties={"name": "Apple"}),
        ]
        sorts = [ObjectQuerySort(field="name", ascending=True)]
        sorted_results = self.service._apply_sorts(results, sorts)
        self.assertEqual(sorted_results[0].properties["name"], "Apple")
        self.assertEqual(sorted_results[1].properties["name"], "Banana")

    def test_descending_sort(self):
        results = [
            _make_result(object_id="1", properties={"name": "Apple"}),
            _make_result(object_id="2", properties={"name": "Banana"}),
        ]
        sorts = [ObjectQuerySort(field="name", ascending=False)]
        sorted_results = self.service._apply_sorts(results, sorts)
        self.assertEqual(sorted_results[0].properties["name"], "Banana")
        self.assertEqual(sorted_results[1].properties["name"], "Apple")

    def test_multiple_sorts_last_takes_priority(self):
        """多字段排序：reversed(sorts) 意味着最后一个 sort 优先级最高"""
        results = [
            _make_result(object_id="1", properties={"name": "B", "age": "1"}),
            _make_result(object_id="2", properties={"name": "A", "age": "2"}),
            _make_result(object_id="3", properties={"name": "A", "age": "1"}),
        ]
        sorts = [
            ObjectQuerySort(field="name", ascending=True),
            ObjectQuerySort(field="age", ascending=True),
        ]
        sorted_results = self.service._apply_sorts(results, sorts)
        # 先按 name 升序，再按 age 升序（Python sort stable）
        self.assertEqual(sorted_results[0].object_id, "3")  # A, age=1
        self.assertEqual(sorted_results[1].object_id, "2")  # A, age=2
        self.assertEqual(sorted_results[2].object_id, "1")  # B, age=1

    def test_empty_sorts_returns_same(self):
        results = [_make_result(object_id="1"), _make_result(object_id="2")]
        sorted_results = self.service._apply_sorts(results, [])
        self.assertEqual(len(sorted_results), 2)

    def test_missing_field_sorts_as_empty_string(self):
        """缺失字段按空字符串排序"""
        results = [
            _make_result(object_id="1", properties={"name": "Beta"}),
            _make_result(object_id="2", properties={}),  # 无 name
        ]
        sorts = [ObjectQuerySort(field="name", ascending=True)]
        sorted_results = self.service._apply_sorts(results, sorts)
        self.assertEqual(sorted_results[0].object_id, "2")  # "" < "Beta"


# ============================================================
# 4. query_objects 测试
# ============================================================


class TestQueryObjects(unittest.TestCase):
    """query_objects 按类型查询 / 全源查询 / 分页 / 排序"""

    def _make_service(self) -> ObjectService:
        """构造带 mock 依赖的 ObjectService"""
        svc = ObjectService()
        svc._oms = MagicMock()
        svc._graph_manager = MagicMock()
        svc._business_storage = MagicMock()
        svc._agent_storage = MagicMock()
        svc._kb_storage = MagicMock()
        return svc

    def test_query_by_type_with_results(self):
        """按 object_type 查询，oms 返回类型定义，graph 返回实体"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}

        mock_entity = MagicMock()
        mock_entity.to_dict.return_value = {
            "id": "e-1",
            "properties": {"name": "Alice", "status": "active"},
        }
        svc.graph.query_entities.return_value = [mock_entity]

        query = _make_query(object_type="Customer")
        result = asyncio.run(svc.query_objects(query))

        self.assertIsInstance(result, ObjectQueryResponse)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.results[0].object_id, "e-1")
        self.assertEqual(result.results[0].object_type, "Customer")
        self.assertEqual(result.results[0].source, "graph")

    def test_query_by_type_no_type_def(self):
        """oms 返回 None 时，结果为空"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = None

        query = _make_query(object_type="NonExistent")
        result = asyncio.run(svc.query_objects(query))

        self.assertEqual(result.total, 0)
        self.assertEqual(result.results, [])

    def test_query_by_type_with_filters(self):
        """按类型查询时应用 filter"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}

        mock_entity = MagicMock()
        mock_entity.to_dict.return_value = {
            "id": "e-1",
            "properties": {"name": "Alice", "status": "inactive"},
        }
        svc.graph.query_entities.return_value = [mock_entity]

        filters = [_make_filter(field="status", operator=ObjectQueryOperator.EQ, value="active")]
        query = _make_query(object_type="Customer", filters=filters)
        result = asyncio.run(svc.query_objects(query))

        self.assertEqual(result.total, 0)

    def test_query_all_sources_graph(self):
        """无 object_type 时从 graph 获取"""
        svc = self._make_service()

        mock_entity = MagicMock()
        mock_entity.to_dict.return_value = {
            "id": "e-1",
            "type": "Entity",
            "properties": {"name": "Node1"},
        }
        svc.graph.query_entities.return_value = [mock_entity]
        svc.business.list_processes.return_value = []
        svc.business.list_rules.return_value = []
        svc.business.list_logics.return_value = []
        svc.business.list_indicators.return_value = []

        query = _make_query()
        result = asyncio.run(svc.query_objects(query))

        self.assertGreaterEqual(result.total, 1)

    def test_query_all_sources_business(self):
        """无 object_type 时从 business 获取"""
        svc = self._make_service()
        svc.graph.query_entities.return_value = []
        svc.business.list_processes.return_value = [
            {"process_id": "p-1", "display_name": "Proc1", "description": "desc"}
        ]
        svc.business.list_rules.return_value = []
        svc.business.list_logics.return_value = []
        svc.business.list_indicators.return_value = []

        query = _make_query()
        result = asyncio.run(svc.query_objects(query))

        self.assertGreaterEqual(result.total, 1)
        # 找到 BusinessProcess 类型
        bp_results = [r for r in result.results if r.object_type == "BusinessProcess"]
        self.assertEqual(len(bp_results), 1)
        self.assertEqual(bp_results[0].source, "business_sqlite")

    def test_query_pagination(self):
        """分页：offset 和 limit"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}

        entities = []
        for i in range(5):
            e = MagicMock()
            e.to_dict.return_value = {
                "id": f"e-{i}",
                "properties": {"name": f"Item{i}"},
            }
            entities.append(e)
        svc.graph.query_entities.return_value = entities

        query = _make_query(object_type="Customer", limit=2, offset=1)
        result = asyncio.run(svc.query_objects(query))

        self.assertEqual(result.total, 5)  # total 是全部数量
        self.assertEqual(len(result.results), 2)  # 分页后只有 2 条
        self.assertEqual(result.limit, 2)
        self.assertEqual(result.offset, 1)

    def test_query_with_sorts(self):
        """查询结果应用排序"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}

        entities = []
        for name in ["Charlie", "Alice", "Bob"]:
            e = MagicMock()
            e.to_dict.return_value = {
                "id": f"e-{name}",
                "properties": {"name": name},
            }
            entities.append(e)
        svc.graph.query_entities.return_value = entities

        sorts = [ObjectQuerySort(field="name", ascending=True)]
        query = _make_query(object_type="Customer", sorts=sorts)
        result = asyncio.run(svc.query_objects(query))

        self.assertEqual(result.results[0].properties["name"], "Alice")
        self.assertEqual(result.results[1].properties["name"], "Bob")
        self.assertEqual(result.results[2].properties["name"], "Charlie")

    def test_query_with_include_links(self):
        """include_links=True 时获取 links"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}

        mock_entity = MagicMock()
        mock_entity.to_dict.return_value = {
            "id": "e-1",
            "properties": {"name": "Alice"},
        }
        svc.graph.query_entities.return_value = [mock_entity]
        svc.graph._mode = "fallback"
        svc.graph.fallback_graph = None

        query = _make_query(object_type="Customer", include_links=True, link_depth=1)
        result = asyncio.run(svc.query_objects(query))

        self.assertEqual(result.results[0].links, [])

    def test_query_with_include_actions(self):
        """include_actions=True 时获取 available_actions"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}

        mock_entity = MagicMock()
        mock_entity.to_dict.return_value = {
            "id": "e-1",
            "properties": {"name": "Alice"},
        }
        svc.graph.query_entities.return_value = [mock_entity]
        svc.oms.list_action_types.return_value = [
            {"action_type_id": "a-1", "name": "delete", "display_name": "Delete", "confirmation_required": True}
        ]

        query = _make_query(object_type="Customer", include_actions=True)
        result = asyncio.run(svc.query_objects(query))

        self.assertEqual(len(result.results[0].available_actions), 1)
        self.assertEqual(result.results[0].available_actions[0]["action_type_id"], "a-1")

    def test_query_graph_exception_degrades_gracefully(self):
        """graph 查询异常时降级，不抛出"""
        svc = self._make_service()
        svc.graph.query_entities.side_effect = RuntimeError("graph down")
        svc.business.list_processes.side_effect = RuntimeError("biz down")
        svc.business.list_rules.side_effect = RuntimeError("biz down")
        svc.business.list_logics.side_effect = RuntimeError("biz down")
        svc.business.list_indicators.side_effect = RuntimeError("biz down")

        # Mock 内部导入的 KB 和 Agent 服务
        with patch("odap.biz.data.knowledge_base.services.get_kb_service") as mock_kb, \
             patch("odap.biz.management.agent_management.api.routes.agent_service") as mock_agent:
            mock_kb_svc = MagicMock()
            mock_kb_svc.list_knowledge_bases.side_effect = RuntimeError("kb down")
            mock_kb.return_value = mock_kb_svc
            mock_agent.list_agents.side_effect = RuntimeError("agent down")

            query = _make_query()
            result = asyncio.run(svc.query_objects(query))

            self.assertEqual(result.total, 0)
            self.assertEqual(result.results, [])


# ============================================================
# 5. semantic_query 测试
# ============================================================


class TestSemanticQuery(unittest.TestCase):
    """semantic_query 图谱搜索 / 结果去重 / 异常降级"""

    def _make_service(self) -> ObjectService:
        svc = ObjectService()
        svc._oms = MagicMock()
        svc._graph_manager = MagicMock()
        svc._business_storage = MagicMock()
        svc._agent_storage = MagicMock()
        svc._kb_storage = MagicMock()
        return svc

    def test_semantic_query_with_dict_result(self):
        """graph.search_hybrid 返回 dict 格式"""
        svc = self._make_service()
        svc.graph.search_hybrid.return_value = {
            "results": [
                {"id": "e-1", "type": "Person", "properties": {"name": "Alice", "status": "active"}},
                {"id": "e-2", "type": "Organization", "properties": {"name": "Acme"}},
            ]
        }

        query = SemanticQuery(query_text="Alice", top_k=10)
        result = asyncio.run(svc.semantic_query(query))

        self.assertIsInstance(result, SemanticQueryResponse)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.results[0].object_id, "e-1")
        self.assertEqual(result.results[0].object_type, "Person")

    def test_semantic_query_with_list_result(self):
        """graph.search_hybrid 返回 list 格式"""
        svc = self._make_service()
        svc.graph.search_hybrid.return_value = [
            {"entity_id": "e-1", "entity_type": "Person", "name": "Alice", "properties": {}},
        ]

        query = SemanticQuery(query_text="Alice", top_k=10)
        result = asyncio.run(svc.semantic_query(query))

        self.assertEqual(result.total, 1)
        self.assertEqual(result.results[0].object_id, "e-1")

    def test_semantic_query_with_object_result(self):
        """graph.search_hybrid 返回带 .entities 属性的对象"""
        svc = self._make_service()
        mock_result = MagicMock()
        mock_result.entities = [
            {"id": "e-1", "type": "Person", "properties": {"name": "Bob"}},
        ]
        svc.graph.search_hybrid.return_value = mock_result

        query = SemanticQuery(query_text="Bob", top_k=10)
        result = asyncio.run(svc.semantic_query(query))

        self.assertEqual(result.total, 1)

    def test_semantic_query_dedup_by_id(self):
        """重复 ID 的实体应去重"""
        svc = self._make_service()
        svc.graph.search_hybrid.return_value = {
            "results": [
                {"id": "e-1", "type": "Person", "properties": {"name": "Alice"}},
                {"id": "e-1", "type": "Person", "properties": {"name": "Alice Duplicate"}},
            ]
        }

        query = SemanticQuery(query_text="Alice", top_k=10)
        result = asyncio.run(svc.semantic_query(query))

        self.assertEqual(result.total, 1)

    def test_semantic_query_skip_empty_id(self):
        """空 ID 的实体应跳过"""
        svc = self._make_service()
        svc.graph.search_hybrid.return_value = {
            "results": [
                {"id": "", "type": "Person", "properties": {"name": "NoID"}},
                {"id": "e-1", "type": "Person", "properties": {"name": "Valid"}},
            ]
        }

        query = SemanticQuery(query_text="test", top_k=10)
        result = asyncio.run(svc.semantic_query(query))

        self.assertEqual(result.total, 1)
        self.assertEqual(result.results[0].object_id, "e-1")

    def test_semantic_query_top_k_limits_results(self):
        """top_k 限制返回数量"""
        svc = self._make_service()
        entities = [
            {"id": f"e-{i}", "type": "Person", "properties": {"name": f"Item{i}"}}
            for i in range(10)
        ]
        svc.graph.search_hybrid.return_value = {"results": entities}

        query = SemanticQuery(query_text="test", top_k=3)
        result = asyncio.run(svc.semantic_query(query))

        self.assertLessEqual(result.total, 3)

    def test_semantic_query_exception_returns_empty(self):
        """graph.search_hybrid 异常时返回空结果"""
        svc = self._make_service()
        svc.graph.search_hybrid.side_effect = RuntimeError("search failed")

        query = SemanticQuery(query_text="test", top_k=10)
        result = asyncio.run(svc.semantic_query(query))

        self.assertEqual(result.total, 0)
        self.assertEqual(result.results, [])

    def test_semantic_query_display_props_filter(self):
        """仅保留 name/type/status/area/affiliation 属性"""
        svc = self._make_service()
        svc.graph.search_hybrid.return_value = {
            "results": [
                {
                    "id": "e-1",
                    "type": "Person",
                    "properties": {
                        "name": "Alice",
                        "status": "active",
                        "area": "NYC",
                        "affiliation": "Acme",
                        "secret_field": "hidden",
                        "another_field": "also_hidden",
                    },
                },
            ]
        }

        query = SemanticQuery(query_text="Alice", top_k=10)
        result = asyncio.run(svc.semantic_query(query))

        props = result.results[0].properties
        self.assertIn("name", props)
        self.assertIn("status", props)
        self.assertIn("area", props)
        self.assertIn("affiliation", props)
        self.assertNotIn("secret_field", props)
        self.assertNotIn("another_field", props)


# ============================================================
# 6. get_object 测试
# ============================================================


class TestGetObject(unittest.TestCase):
    """get_object 单对象获取"""

    def _make_service(self) -> ObjectService:
        svc = ObjectService()
        svc._oms = MagicMock()
        svc._graph_manager = MagicMock()
        svc._business_storage = MagicMock()
        svc._agent_storage = MagicMock()
        svc._kb_storage = MagicMock()
        return svc

    def test_get_object_found(self):
        """query_objects 返回结果时取第一条"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}

        mock_entity = MagicMock()
        mock_entity.to_dict.return_value = {
            "id": "e-1",
            "properties": {"name": "Alice"},
        }
        svc.graph.query_entities.return_value = [mock_entity]

        result = asyncio.run(svc.get_object("e-1", object_type="Customer"))

        self.assertIsNotNone(result)
        self.assertEqual(result.object_id, "e-1")

    def test_get_object_not_found(self):
        """query_objects 无结果时返回 None"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = None

        result = asyncio.run(svc.get_object("nonexistent", object_type="Missing"))

        self.assertIsNone(result)

    def test_get_object_sets_include_links_and_actions(self):
        """get_object 自动设置 include_links=True, include_actions=True"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}

        mock_entity = MagicMock()
        mock_entity.to_dict.return_value = {
            "id": "e-1",
            "properties": {"name": "Alice"},
        }
        svc.graph.query_entities.return_value = [mock_entity]
        svc.graph._mode = "fallback"
        svc.graph.fallback_graph = None
        svc.oms.list_action_types.return_value = []

        result = asyncio.run(svc.get_object("e-1", object_type="Customer"))

        self.assertIsNotNone(result)
        # links 和 actions 已被填充（可能为空列表）
        self.assertIsInstance(result.links, list)
        self.assertIsInstance(result.available_actions, list)


# ============================================================
# 7. _query_by_type 测试
# ============================================================


class TestQueryByType(unittest.TestCase):
    """_query_by_type 内部方法"""

    def _make_service(self) -> ObjectService:
        svc = ObjectService()
        svc._oms = MagicMock()
        svc._graph_manager = MagicMock()
        svc._business_storage = MagicMock()
        svc._agent_storage = MagicMock()
        svc._kb_storage = MagicMock()
        return svc

    def test_entity_with_to_dict(self):
        """实体有 to_dict 方法时使用"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}

        mock_entity = MagicMock()
        mock_entity.to_dict.return_value = {
            "id": "e-1",
            "properties": {"name": "Alice"},
        }
        svc.graph.query_entities.return_value = [mock_entity]

        query = _make_query(object_type="Customer")
        results, total = asyncio.run(svc._query_by_type(query))

        self.assertEqual(total, 1)
        self.assertEqual(results[0].object_id, "e-1")

    def test_entity_without_to_dict(self):
        """实体无 to_dict 方法时使用 dict() 转换"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}

        entity_dict = {"id": "e-2", "properties": {"name": "Bob"}}
        svc.graph.query_entities.return_value = [entity_dict]

        query = _make_query(object_type="Customer")
        results, total = asyncio.run(svc._query_by_type(query))

        self.assertEqual(total, 1)
        self.assertEqual(results[0].object_id, "e-2")

    def test_graph_exception_returns_empty(self):
        """graph 查询异常时返回空"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}
        svc.graph.query_entities.side_effect = RuntimeError("db down")

        query = _make_query(object_type="Customer")
        results, total = asyncio.run(svc._query_by_type(query))

        self.assertEqual(total, 0)
        self.assertEqual(results, [])

    def test_none_properties_filtered_out(self):
        """properties 中值为 None 的字段应被过滤"""
        svc = self._make_service()
        svc.oms.get_object_type.return_value = {"name": "Customer"}

        mock_entity = MagicMock()
        mock_entity.to_dict.return_value = {
            "id": "e-1",
            "properties": {"name": "Alice", "email": None},
        }
        svc.graph.query_entities.return_value = [mock_entity]

        query = _make_query(object_type="Customer")
        results, total = asyncio.run(svc._query_by_type(query))

        self.assertNotIn("email", results[0].properties)
        self.assertIn("name", results[0].properties)


# ============================================================
# 8. _fetch_from_business 测试
# ============================================================


class TestFetchFromBusiness(unittest.TestCase):
    """_fetch_from_business 业务数据获取"""

    def _make_service(self) -> ObjectService:
        svc = ObjectService()
        svc._oms = MagicMock()
        svc._graph_manager = MagicMock()
        svc._business_storage = MagicMock()
        svc._agent_storage = MagicMock()
        svc._kb_storage = MagicMock()
        return svc

    def test_fetch_processes(self):
        svc = self._make_service()
        svc.business.list_processes.return_value = [
            {"process_id": "p-1", "display_name": "Proc1", "description": "desc"}
        ]
        svc.business.list_rules.return_value = []
        svc.business.list_logics.return_value = []
        svc.business.list_indicators.return_value = []

        query = _make_query()
        results = asyncio.run(svc._fetch_from_business(query))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].object_type, "BusinessProcess")
        self.assertEqual(results[0].source, "business_sqlite")

    def test_fetch_rules(self):
        svc = self._make_service()
        svc.business.list_processes.return_value = []
        svc.business.list_rules.return_value = [
            {"rule_id": "r-1", "display_name": "Rule1", "description": "desc"}
        ]
        svc.business.list_logics.return_value = []
        svc.business.list_indicators.return_value = []

        query = _make_query()
        results = asyncio.run(svc._fetch_from_business(query))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].object_type, "BusinessRule")

    def test_fetch_logics(self):
        svc = self._make_service()
        svc.business.list_processes.return_value = []
        svc.business.list_rules.return_value = []
        svc.business.list_logics.return_value = [
            {"logic_id": "l-1", "display_name": "Logic1", "description": "desc"}
        ]
        svc.business.list_indicators.return_value = []

        query = _make_query()
        results = asyncio.run(svc._fetch_from_business(query))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].object_type, "BusinessLogic")

    def test_fetch_indicators(self):
        svc = self._make_service()
        svc.business.list_processes.return_value = []
        svc.business.list_rules.return_value = []
        svc.business.list_logics.return_value = []
        svc.business.list_indicators.return_value = [
            {"indicator_id": "i-1", "display_name": "Ind1", "description": "desc"}
        ]

        query = _make_query()
        results = asyncio.run(svc._fetch_from_business(query))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].object_type, "Indicator")

    def test_fetch_with_filters(self):
        """业务数据应用 filter"""
        svc = self._make_service()
        svc.business.list_processes.return_value = [
            {"process_id": "p-1", "display_name": "Proc1", "description": "desc", "status": "inactive"},
            {"process_id": "p-2", "display_name": "Proc2", "description": "desc", "status": "active"},
        ]
        svc.business.list_rules.return_value = []
        svc.business.list_logics.return_value = []
        svc.business.list_indicators.return_value = []

        filters = [_make_filter(field="status", operator=ObjectQueryOperator.EQ, value="active")]
        query = _make_query(filters=filters)
        results = asyncio.run(svc._fetch_from_business(query))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].properties["name"], "Proc2")

    def test_fetch_exception_returns_empty(self):
        svc = self._make_service()
        svc.business.list_processes.side_effect = RuntimeError("db error")

        query = _make_query()
        results = asyncio.run(svc._fetch_from_business(query))

        self.assertEqual(results, [])


# ============================================================
# 9. _get_available_actions 测试
# ============================================================


class TestGetAvailableActions(unittest.TestCase):
    """_get_available_actions 获取可用动作"""

    def _make_service(self) -> ObjectService:
        svc = ObjectService()
        svc._oms = MagicMock()
        svc._graph_manager = MagicMock()
        svc._business_storage = MagicMock()
        svc._agent_storage = MagicMock()
        svc._kb_storage = MagicMock()
        return svc

    def test_returns_formatted_actions(self):
        svc = self._make_service()
        svc.oms.list_action_types.return_value = [
            {"action_type_id": "a-1", "name": "delete", "display_name": "Delete", "confirmation_required": True},
            {"action_type_id": "a-2", "name": "update", "display_name": "Update", "confirmation_required": False},
        ]

        result = asyncio.run(svc._get_available_actions("Customer"))

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["action_type_id"], "a-1")
        self.assertTrue(result[0]["confirmation_required"])
        self.assertFalse(result[1]["confirmation_required"])

    def test_missing_display_name_falls_back_to_name(self):
        svc = self._make_service()
        svc.oms.list_action_types.return_value = [
            {"action_type_id": "a-1", "name": "delete"},
        ]

        result = asyncio.run(svc._get_available_actions("Customer"))

        self.assertEqual(result[0]["display_name"], "delete")

    def test_missing_confirmation_required_defaults_false(self):
        svc = self._make_service()
        svc.oms.list_action_types.return_value = [
            {"action_type_id": "a-1", "name": "delete", "display_name": "Delete"},
        ]

        result = asyncio.run(svc._get_available_actions("Customer"))

        self.assertFalse(result[0]["confirmation_required"])


# ============================================================
# 10. get_object_service 单例测试
# ============================================================


class TestGetObjectServiceSingleton(unittest.TestCase):
    """get_object_service 单例模式"""

    def test_returns_same_instance(self):
        from odap.infra.object_service.object_service import (
            get_object_service,
            _object_service_instance,
        )
        # 重置单例
        import odap.infra.object_service.object_service as mod
        mod._object_service_instance = None

        svc1 = get_object_service()
        svc2 = get_object_service()
        self.assertIs(svc1, svc2)

        # 清理
        mod._object_service_instance = None


# ============================================================
# 入口
# ============================================================


if __name__ == "__main__":
    unittest.main()
