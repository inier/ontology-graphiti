import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.data.data_warehouse.query_service import (
    QueryService, SimulatedWarehouse, SQLParser, QueryPlanner, ResultAggregator,
)
from odap.biz.data.data_warehouse.models import QueryRequest, QueryPlan, SortOrder


@pytest.fixture
def sample_warehouse():
    wh = SimulatedWarehouse()
    wh.load_data("units", [
        {"id": "U1", "name": "Alpha Unit", "type": "infantry", "strength": 100, "area": "A"},
        {"id": "U2", "name": "Bravo Unit", "type": "armor", "strength": 50, "area": "A"},
        {"id": "U3", "name": "Charlie Unit", "type": "infantry", "strength": 80, "area": "B"},
        {"id": "U4", "name": "Delta Unit", "type": "artillery", "strength": 30, "area": "B"},
        {"id": "U5", "name": "Echo Unit", "type": "armor", "strength": 60, "area": "C"},
    ])
    wh.load_data("locations", [
        {"id": "L1", "name": "Base Alpha", "area": "A", "terrain": "desert"},
        {"id": "L2", "name": "Base Bravo", "area": "B", "terrain": "plains"},
        {"id": "L3", "name": "Base Charlie", "area": "C", "terrain": "mountain"},
    ])
    return wh


@pytest.fixture
def query_service(sample_warehouse):
    service = QueryService()
    service.warehouse = sample_warehouse
    return service


class TestSimulatedWarehouse:
    def test_load_data(self, sample_warehouse):
        assert "units" in sample_warehouse.list_tables()
        assert "locations" in sample_warehouse.list_tables()
        assert len(sample_warehouse.get_table("units")) == 5

    def test_get_table_schema(self, sample_warehouse):
        schema = sample_warehouse.get_table_schema("units")
        assert "id" in schema
        assert "name" in schema
        assert "strength" in schema

    def test_get_nonexistent_table(self, sample_warehouse):
        assert sample_warehouse.get_table("nonexistent") == []

    def test_create_and_restore_snapshot(self, sample_warehouse):
        snapshot = sample_warehouse.create_snapshot("test_snapshot", "Test description")
        assert snapshot.name == "test_snapshot"
        assert snapshot.entity_counts["units"] == 5

        sample_warehouse.load_data("units", [{"id": "NEW", "name": "New Unit"}])
        assert len(sample_warehouse.get_table("units")) == 1

        assert sample_warehouse.restore_snapshot(snapshot.snapshot_id)
        assert len(sample_warehouse.get_table("units")) == 5

    def test_list_snapshots(self, sample_warehouse):
        sample_warehouse.create_snapshot("snap1")
        sample_warehouse.create_snapshot("snap2")
        snapshots = sample_warehouse.list_snapshots()
        assert len(snapshots) == 2


class TestSQLParser:
    def test_simple_select(self):
        parser = SQLParser()
        plan = parser.parse("SELECT * FROM units")
        assert plan.source_tables == ["units"]

    def test_where_clause(self):
        parser = SQLParser()
        plan = parser.parse("SELECT * FROM units WHERE area = 'A'")
        assert plan.source_tables == ["units"]
        assert "area" in plan.filters
        assert plan.filters["area"]["op"] == "eq"
        assert plan.filters["area"]["value"] == "A"

    def test_numeric_where(self):
        parser = SQLParser()
        plan = parser.parse("SELECT * FROM units WHERE strength > 50")
        assert "strength" in plan.filters
        assert plan.filters["strength"]["op"] == "gt"
        assert plan.filters["strength"]["value"] == 50

    def test_aggregation(self):
        parser = SQLParser()
        plan = parser.parse("SELECT COUNT(*) FROM units GROUP BY area")
        assert len(plan.aggregations) == 1
        assert plan.aggregations[0]["type"] == "count"
        assert plan.aggregations[0]["group_by"] == "area"

    def test_order_by(self):
        parser = SQLParser()
        plan = parser.parse("SELECT * FROM units ORDER BY strength DESC")
        assert plan.sort_by == "strength"
        assert plan.sort_order == SortOrder.DESC

    def test_limit_offset(self):
        parser = SQLParser()
        plan = parser.parse("SELECT * FROM units LIMIT 10 OFFSET 5")
        assert plan.limit == 10
        assert plan.offset == 5


class TestQueryService:
    def test_simple_query(self, query_service):
        result = query_service.execute(QueryRequest(query="SELECT * FROM units"))
        assert result.error is None
        assert len(result.rows) == 5
        assert "id" in result.columns

    def test_filtered_query(self, query_service):
        result = query_service.execute(QueryRequest(query="SELECT * FROM units WHERE area = 'A'"))
        assert len(result.rows) == 2
        assert all(r["area"] == "A" for r in result.rows)

    def test_numeric_filter(self, query_service):
        result = query_service.execute(QueryRequest(query="SELECT * FROM units WHERE strength > 50"))
        assert len(result.rows) == 3

    def test_aggregation_query(self, query_service):
        result = query_service.execute(QueryRequest(query="SELECT COUNT(*) FROM units GROUP BY area"))
        assert len(result.rows) == 3
        assert any("count" in r for r in result.rows)

    def test_order_by_query(self, query_service):
        result = query_service.execute(QueryRequest(query="SELECT * FROM units ORDER BY strength DESC"))
        assert result.rows[0]["strength"] == 100

    def test_limit_query(self, query_service):
        result = query_service.execute(QueryRequest(query="SELECT * FROM units LIMIT 2"))
        assert len(result.rows) == 2

    def test_nonexistent_table(self, query_service):
        result = query_service.execute(QueryRequest(query="SELECT * FROM nonexistent"))
        assert result.error is not None

    def test_simple_table_query(self, query_service):
        result = query_service.execute(QueryRequest(query="units"))
        assert result.error is None
        assert len(result.rows) == 5

    def test_query_history(self, query_service):
        query_service.execute(QueryRequest(query="SELECT * FROM units"))
        query_service.execute(QueryRequest(query="SELECT * FROM locations"))
        history = query_service.get_query_history()
        assert len(history) == 2

    def test_list_tables(self, query_service):
        tables = query_service.list_tables()
        assert "units" in tables
        assert "locations" in tables
