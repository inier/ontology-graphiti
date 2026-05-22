import json
import os
import re
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from collections import defaultdict

from .models import (
    QueryRequest, QueryResult, QueryPlan, DataSnapshot,
    AggregationType, SortOrder,
)

logger = logging.getLogger(__name__)


class SimulatedWarehouse:
    def __init__(self, data_dir: Optional[str] = None):
        self._tables: Dict[str, List[Dict[str, Any]]] = {}
        self._snapshots: Dict[str, DataSnapshot] = {}
        self._data_dir = data_dir
        if data_dir:
            self._load_from_directory(data_dir)

    def _load_from_directory(self, data_dir: str):
        if not os.path.exists(data_dir):
            logger.warning(f"Data directory not found: {data_dir}")
            return
        for filename in os.listdir(data_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(data_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        for table_name, records in data.items():
                            if isinstance(records, list):
                                self._tables[table_name] = records
                                logger.info(f"Loaded table '{table_name}': {len(records)} records")
                    elif isinstance(data, list):
                        table_name = os.path.splitext(filename)[0]
                        self._tables[table_name] = data
                        logger.info(f"Loaded table '{table_name}': {len(data)} records")
                except Exception as e:
                    logger.warning(f"Failed to load {filename}: {e}")

    def load_data(self, table_name: str, records: List[Dict[str, Any]]):
        self._tables[table_name] = records
        logger.info(f"Loaded table '{table_name}': {len(records)} records")

    def get_table(self, table_name: str) -> List[Dict[str, Any]]:
        return self._tables.get(table_name, [])

    def list_tables(self) -> List[str]:
        return list(self._tables.keys())

    def get_table_schema(self, table_name: str) -> Dict[str, str]:
        records = self._tables.get(table_name, [])
        if not records:
            return {}
        schema = {}
        for key, value in records[0].items():
            schema[key] = type(value).__name__
        return schema

    def create_snapshot(self, name: str, description: str = "") -> DataSnapshot:
        snapshot = DataSnapshot(
            name=name,
            description=description,
            data={k: list(v) for k, v in self._tables.items()},
            entity_counts={k: len(v) for k, v in self._tables.items()},
        )
        self._snapshots[snapshot.snapshot_id] = snapshot
        logger.info(f"Created snapshot '{name}': {snapshot.snapshot_id}")
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[DataSnapshot]:
        return self._snapshots.get(snapshot_id)

    def list_snapshots(self) -> List[Dict[str, Any]]:
        return [
            {
                "snapshot_id": s.snapshot_id,
                "name": s.name,
                "description": s.description,
                "created_at": s.created_at.isoformat(),
                "entity_counts": s.entity_counts,
            }
            for s in self._snapshots.values()
        ]

    def restore_snapshot(self, snapshot_id: str) -> bool:
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            return False
        self._tables = {k: list(v) for k, v in snapshot.data.items()}
        logger.info(f"Restored snapshot: {snapshot_id}")
        return True


class SQLParser:
    TOKEN_PATTERNS = [
        ('SELECT', r'\bSELECT\b'),
        ('FROM', r'\bFROM\b'),
        ('WHERE', r'\bWHERE\b'),
        ('GROUP', r'\bGROUP\b'),
        ('BY', r'\bBY\b'),
        ('ORDER', r'\bORDER\b'),
        ('LIMIT', r'\bLIMIT\b'),
        ('OFFSET', r'\bOFFSET\b'),
        ('AND', r'\bAND\b'),
        ('OR', r'\bOR\b'),
        ('COUNT', r'\bCOUNT\b'),
        ('SUM', r'\bSUM\b'),
        ('AVG', r'\bAVG\b'),
        ('MIN', r'\bMIN\b'),
        ('MAX', r'\bMAX\b'),
        ('DISTINCT', r'\bDISTINCT\b'),
        ('ASC', r'\bASC\b'),
        ('DESC', r'\bDESC\b'),
        ('STAR', r'\*'),
        ('COMMA', r','),
        ('EQ', r'='),
        ('NEQ', r'!=|<>'),
        ('GT', r'>'),
        ('LT', r'<'),
        ('GTE', r'>='),
        ('LTE', r'<='),
        ('STRING', r"'[^']*'"),
        ('NUMBER', r'\d+\.?\d*'),
        ('IDENTIFIER', r'[a-zA-Z_][a-zA-Z0-9_]*'),
        ('DOT', r'\.'),
        ('LPAREN', r'\('),
        ('RPAREN', r'\)'),
        ('WS', r'\s+'),
    ]

    def parse(self, sql: str) -> QueryPlan:
        sql_upper = sql.strip().rstrip(';')
        plan = QueryPlan()

        from_match = re.search(r'\bFROM\s+(\w+)', sql_upper, re.IGNORECASE)
        if from_match:
            plan.source_tables = [from_match.group(1).lower()]

        where_match = re.search(r'\bWHERE\s+(.+?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|$)', sql_upper, re.IGNORECASE)
        if where_match:
            plan.filters = self._parse_where(where_match.group(1).strip())

        agg_match = re.search(r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(\w+|\*)\s*\)', sql_upper, re.IGNORECASE)
        if agg_match:
            plan.aggregations = [{
                "type": agg_match.group(1).lower(),
                "field": agg_match.group(2) if agg_match.group(2) != '*' else None,
            }]

        group_match = re.search(r'\bGROUP\s+BY\s+(\w+)', sql_upper, re.IGNORECASE)
        if group_match:
            if not plan.aggregations:
                plan.aggregations = [{"type": "count", "field": None}]
            plan.aggregations[0]["group_by"] = group_match.group(1).lower()

        order_match = re.search(r'\bORDER\s+BY\s+(\w+)(?:\s+(ASC|DESC))?', sql_upper, re.IGNORECASE)
        if order_match:
            plan.sort_by = order_match.group(1).lower()
            if order_match.group(2):
                plan.sort_order = SortOrder(order_match.group(2).lower())

        limit_match = re.search(r'\bLIMIT\s+(\d+)', sql_upper, re.IGNORECASE)
        if limit_match:
            plan.limit = int(limit_match.group(1))

        offset_match = re.search(r'\bOFFSET\s+(\d+)', sql_upper, re.IGNORECASE)
        if offset_match:
            plan.offset = int(offset_match.group(1))

        return plan

    def _parse_where(self, where_clause: str) -> Dict[str, Any]:
        filters = {}
        conditions = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)
        for cond in conditions:
            for op_str, op_name in [('!=', 'neq'), ('>=', 'gte'), ('<=', 'lte'), ('>', 'gt'), ('<', 'lt'), ('=', 'eq')]:
                if op_str in cond:
                    parts = cond.split(op_str, 1)
                    if len(parts) == 2:
                        field = parts[0].strip().lower()
                        value = parts[1].strip().strip("'\"")
                        try:
                            value = float(value) if '.' in value else int(value)
                        except (ValueError, TypeError):
                            pass
                        filters[field] = {"op": op_name, "value": value}
                    break
        return filters


class QueryPlanner:
    def plan(self, request: QueryRequest) -> QueryPlan:
        sql = request.query.strip()
        if sql.upper().startswith('SELECT'):
            parser = SQLParser()
            plan = parser.parse(sql)
        else:
            plan = QueryPlan(source_tables=[], filters={})
            parts = sql.split()
            if parts:
                plan.source_tables = [parts[0].lower()]
                if len(parts) > 1:
                    plan.filters = self._parse_simple_filter(' '.join(parts[1:]))

        if request.limit and request.limit != 100:
            plan.limit = request.limit
        if request.offset:
            plan.offset = request.offset
        return plan

    def _parse_simple_filter(self, filter_str: str) -> Dict[str, Any]:
        filters = {}
        conditions = re.split(r'\s+AND\s+', filter_str, flags=re.IGNORECASE)
        for cond in conditions:
            match = re.match(r'(\w+)\s*(=|!=|>|<|>=|<=)\s*(.+)', cond.strip())
            if match:
                field = match.group(1).lower()
                op_map = {'=': 'eq', '!=': 'neq', '>': 'gt', '<': 'lt', '>=': 'gte', '<=': 'lte'}
                value = match.group(3).strip().strip("'\"")
                try:
                    value = float(value) if '.' in value else int(value)
                except (ValueError, TypeError):
                    pass
                filters[field] = {"op": op_map.get(match.group(2), 'eq'), "value": value}
        return filters


class ResultAggregator:
    def execute(self, warehouse: SimulatedWarehouse, plan: QueryPlan) -> QueryResult:
        start = time.time()

        if not plan.source_tables:
            return QueryResult(error="No source table specified", execution_time_ms=0)

        table_name = plan.source_tables[0]
        records = warehouse.get_table(table_name)

        if records is None or (len(records) == 0 and table_name not in warehouse.list_tables()):
            return QueryResult(
                error=f"Table '{table_name}' not found. Available: {warehouse.list_tables()}",
                execution_time_ms=(time.time() - start) * 1000,
            )

        filtered = self._apply_filters(records, plan.filters)

        if plan.aggregations:
            result_rows = self._apply_aggregation(filtered, plan.aggregations)
        else:
            result_rows = filtered

        if plan.sort_by:
            result_rows = self._apply_sort(result_rows, plan.sort_by, plan.sort_order)

        total_count = len(result_rows)
        result_rows = result_rows[plan.offset:plan.offset + plan.limit]

        columns = list(result_rows[0].keys()) if result_rows else []

        return QueryResult(
            columns=columns,
            rows=result_rows,
            total_count=total_count,
            execution_time_ms=(time.time() - start) * 1000,
            plan=plan,
        )

    def _apply_filters(self, records: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        if not filters:
            return records

        result = []
        for record in records:
            match = True
            for field, condition in filters.items():
                if field not in record:
                    match = False
                    break
                value = record[field]
                op = condition.get("op", "eq")
                target = condition.get("value")

                if op == "eq" and value != target:
                    match = False
                elif op == "neq" and value == target:
                    match = False
                elif op == "gt" and not (value > target):
                    match = False
                elif op == "lt" and not (value < target):
                    match = False
                elif op == "gte" and not (value >= target):
                    match = False
                elif op == "lte" and not (value <= target):
                    match = False

                if not match:
                    break

            if match:
                result.append(record)
        return result

    def _apply_aggregation(self, records: List[Dict], aggregations: List[Dict]) -> List[Dict]:
        if not aggregations:
            return records

        agg = aggregations[0]
        agg_type = agg.get("type", "count")
        field = agg.get("field")
        group_by = agg.get("group_by")

        if group_by:
            groups = defaultdict(list)
            for r in records:
                key = r.get(group_by, "unknown")
                groups[key].append(r)

            result = []
            for key, group_records in groups.items():
                row = {group_by: key}
                row[self._agg_column_name(agg_type, field)] = self._compute_agg(group_records, agg_type, field)
                result.append(row)
            return result
        else:
            value = self._compute_agg(records, agg_type, field)
            return [{self._agg_column_name(agg_type, field): value}]

    def _compute_agg(self, records: List[Dict], agg_type: str, field: Optional[str]) -> Any:
        if agg_type == "count":
            return len(records)
        if not field:
            return None

        values = [r.get(field) for r in records if field in r and isinstance(r[field], (int, float))]
        if not values:
            return None

        if agg_type == "sum":
            return sum(values)
        elif agg_type == "avg":
            return sum(values) / len(values)
        elif agg_type == "min":
            return min(values)
        elif agg_type == "max":
            return max(values)
        elif agg_type == "distinct":
            return len(set(values))
        return None

    def _agg_column_name(self, agg_type: str, field: Optional[str]) -> str:
        if field:
            return f"{agg_type}_{field}"
        return agg_type

    def _apply_sort(self, records: List[Dict], sort_by: str, order: SortOrder) -> List[Dict]:
        reverse = order == SortOrder.DESC
        return sorted(records, key=lambda r: r.get(sort_by, ''), reverse=reverse)


class QueryService:
    def __init__(self, data_dir: Optional[str] = None):
        self.warehouse = SimulatedWarehouse(data_dir=data_dir)
        self.planner = QueryPlanner()
        self.aggregator = ResultAggregator()
        self._query_history: List[Dict] = []

    def execute(self, request: QueryRequest) -> QueryResult:
        plan = self.planner.plan(request)
        result = self.aggregator.execute(self.warehouse, plan)

        self._query_history.append({
            "query_id": result.query_id,
            "query": request.query,
            "workspace_id": request.workspace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_time_ms": result.execution_time_ms,
            "total_count": result.total_count,
        })

        return result

    def load_data(self, table_name: str, records: List[Dict[str, Any]]):
        self.warehouse.load_data(table_name, records)

    def list_tables(self) -> List[str]:
        return self.warehouse.list_tables()

    def get_table_schema(self, table_name: str) -> Dict[str, str]:
        return self.warehouse.get_table_schema(table_name)

    def create_snapshot(self, name: str, description: str = "") -> DataSnapshot:
        return self.warehouse.create_snapshot(name, description)

    def list_snapshots(self) -> List[Dict[str, Any]]:
        return self.warehouse.list_snapshots()

    def restore_snapshot(self, snapshot_id: str) -> bool:
        return self.warehouse.restore_snapshot(snapshot_id)

    def get_query_history(self, limit: int = 50) -> List[Dict]:
        return self._query_history[-limit:]
