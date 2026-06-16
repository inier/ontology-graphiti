"""Database Schema Extractor using SQLAlchemy Inspector.

Uses SQLAlchemy Inspector to introspect database schemas and map them
to ontology type definitions (object_types, link_types, etc.).
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Pattern keywords for inferring advanced type definitions
_ACTION_TABLE_KEYWORDS = ("log", "record", "transaction", "operation", "event", "action")
_RULE_TABLE_KEYWORDS = ("rule", "policy", "constraint", "validation")
_RULE_COLUMN_KEYWORDS = ("status", "state", "flag", "enabled", "active")
_PROCESS_TABLE_KEYWORDS = ("flow", "process", "workflow", "pipeline", "step")
_FUNCTION_TABLE_KEYWORDS = ("view", "func", "calc", "compute", "transform")
_INDICATOR_TABLE_KEYWORDS = ("metric", "indicator", "kpi", "stat", "measure", "report", "dashboard")
_INDICATOR_COLUMN_KEYWORDS = ("value", "score", "rate", "count", "amount", "total", "avg", "sum", "ratio", "percentage")
_NUMERIC_SQL_TYPES = {"INTEGER", "INT", "SMALLINT", "BIGINT", "TINYINT", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL"}


class DatabaseSchemaExtractor:
    """Extracts ontology type definitions from database schemas."""

    # SQL type to PropertyType mapping
    SQL_TYPE_MAP = {
        "VARCHAR": "string",
        "CHAR": "string",
        "TEXT": "string",
        "NVARCHAR": "string",
        "CLOB": "string",
        "INTEGER": "integer",
        "INT": "integer",
        "SMALLINT": "integer",
        "BIGINT": "integer",
        "TINYINT": "integer",
        "FLOAT": "float",
        "DOUBLE": "float",
        "DECIMAL": "float",
        "NUMERIC": "float",
        "REAL": "float",
        "BOOLEAN": "boolean",
        "BOOL": "boolean",
        "BIT": "boolean",
        "DATE": "datetime",
        "DATETIME": "datetime",
        "TIMESTAMP": "datetime",
        "TIME": "datetime",
        "JSON": "json",
        "JSONB": "json",
        "BLOB": "json",
        "BYTEA": "json",
        "VARBINARY": "json",
    }

    def __init__(self):
        self._engine = None

    def test_connection(
        self,
        db_type: str,
        host: str,
        port: int,
        database: str,
        username: str = None,
        password: str = None,
    ) -> Dict[str, Any]:
        """Test database connection.

        Returns:
            Dict with keys: status, message, table_count, schema_name
        """
        try:
            engine = self._create_engine(db_type, host, port, database, username, password)
            from sqlalchemy import inspect

            inspector = inspect(engine)
            tables = inspector.get_table_names()
            engine.dispose()
            return {
                "status": "ok",
                "message": f"连接成功，发现 {len(tables)} 张表",
                "table_count": len(tables),
                "schema_name": database,
            }
        except Exception as e:
            logger.warning(f"Database connection test failed: {e}")
            return {
                "status": "error",
                "message": f"连接失败: {str(e)}",
                "table_count": 0,
                "schema_name": "",
            }

    def extract_schema(
        self,
        db_type: str,
        host: str,
        port: int,
        database: str,
        username: str = None,
        password: str = None,
        table_filter: List[str] = None,
        use_llm_enrichment: bool = False,
    ) -> Dict[str, Any]:
        """Extract schema and map to ontology type definitions.

        Args:
            db_type: Database type (sqlite/postgresql/mysql)
            host: Database host
            port: Database port
            database: Database name or file path
            username: Database username
            password: Database password
            table_filter: Optional list of table names to include
            use_llm_enrichment: Whether to use LLM for enrichment (reserved)

        Returns:
            Dict with keys: status, object_types, link_types, action_types,
            rule_types, process_types, function_types, indicator_types, summary
        """
        try:
            engine = self._create_engine(db_type, host, port, database, username, password)
            from sqlalchemy import inspect

            inspector = inspect(engine)

            tables = inspector.get_table_names()
            if table_filter:
                tables = [t for t in tables if t in table_filter]

            # Try to get view names for function type inference
            view_names = []
            try:
                view_names = inspector.get_view_names()
            except Exception:
                # Some dialects don't support views
                pass

            object_types = []
            link_types = []
            action_types = []
            rule_types = []
            process_types = []
            function_types = []
            indicator_types = []

            # Build a lookup for table → columns (used by advanced type inference)
            table_columns_map: Dict[str, List[Dict]] = {}
            # Track which tables have been classified as advanced types
            classified_tables: set = set()

            for table_name in tables:
                # Map table to ObjectType
                columns = inspector.get_columns(table_name)
                pk_constraint = inspector.get_pk_constraint(table_name)
                fk_constraints = inspector.get_foreign_keys(table_name)

                table_columns_map[table_name] = columns

                properties = []
                pk_columns = pk_constraint.get("constrained_columns", [])

                for col in columns:
                    prop_type = self._map_sql_type(str(col.get("type", "")))
                    properties.append(
                        {
                            "name": col["name"],
                            "display_name": self._to_display_name(col["name"]),
                            "property_type": prop_type,
                            "required": not col.get("nullable", True)
                            or col["name"] in pk_columns,
                            "default": str(col.get("default")) if col.get("default") else None,
                            "description": f"Column {col['name']} ({col.get('type', '')})",
                        }
                    )

                object_type = {
                    "name": table_name,
                    "display_name": self._to_display_name(table_name),
                    "description": f"Table {table_name}",
                    "properties": properties,
                    "links": [],
                    "actions": [],
                    "primary_key": pk_columns,
                    "classification_level": "U",
                }
                object_types.append(object_type)

                # Map foreign keys to LinkTypes
                for fk in fk_constraints:
                    link_name = f"{table_name}_to_{fk['referred_table']}"
                    link_types.append(
                        {
                            "name": link_name,
                            "display_name": self._to_display_name(link_name),
                            "source_type": table_name,
                            "target_type": fk["referred_table"],
                            "cardinality": "N:1",
                            "link_type": "ASSOCIATION",
                            "description": (
                                f"FK: {table_name}"
                                f"({', '.join(fk.get('constrained_columns', []))})"
                                f" -> {fk['referred_table']}"
                                f"({', '.join(fk.get('referred_columns', []))})"
                            ),
                        }
                    )

            # ── Infer action_types from transactional/event tables ──────
            for table_name in tables:
                name_lower = table_name.lower()
                if any(kw in name_lower for kw in _ACTION_TABLE_KEYWORDS):
                    classified_tables.add(table_name)
                    cols = table_columns_map.get(table_name, [])
                    # Find FK target as the related entity
                    fk_constraints = inspector.get_foreign_keys(table_name)
                    target_type = table_name
                    if fk_constraints:
                        target_type = fk_constraints[0]["referred_table"]

                    params = []
                    for col in cols:
                        if col["name"].lower() not in ("id", "created_at", "updated_at"):
                            params.append({
                                "name": col["name"],
                                "param_type": self._map_sql_type(str(col.get("type", ""))),
                                "required": not col.get("nullable", True),
                            })

                    action_types.append({
                        "name": f"{table_name}_action",
                        "display_name": self._to_display_name(table_name) + " 动作",
                        "target_object_type": target_type,
                        "description": f"从表 {table_name} 推断的操作动作",
                        "parameters": params,
                    })

            # ── Infer rule_types from tables with status/state columns ──
            for table_name in tables:
                cols = table_columns_map.get(table_name, [])
                status_columns = [
                    c for c in cols
                    if any(kw in c["name"].lower() for kw in _RULE_COLUMN_KEYWORDS)
                ]
                name_lower = table_name.lower()
                is_rule_table = any(kw in name_lower for kw in _RULE_TABLE_KEYWORDS)

                if status_columns or is_rule_table:
                    classified_tables.add(table_name)
                    condition_schema = {}
                    for sc in status_columns:
                        condition_schema[sc["name"]] = {
                            "type": self._map_sql_type(str(sc.get("type", ""))),
                            "description": f"状态列 {sc['name']}",
                        }

                    rule_types.append({
                        "name": f"{table_name}_rule",
                        "display_name": self._to_display_name(table_name) + " 规则",
                        "description": f"从表 {table_name} 的状态/约束列推断的业务规则",
                        "condition_schema": condition_schema,
                        "consequence_schema": {},
                        "priority": "medium",
                    })

            # ── Infer process_types from workflow/flow tables ───────────
            for table_name in tables:
                name_lower = table_name.lower()
                if any(kw in name_lower for kw in _PROCESS_TABLE_KEYWORDS):
                    classified_tables.add(table_name)
                    cols = table_columns_map.get(table_name, [])
                    # Find FK targets as related object types
                    fk_constraints = inspector.get_foreign_keys(table_name)
                    related = list({fk["referred_table"] for fk in fk_constraints})

                    process_types.append({
                        "name": f"{table_name}_process",
                        "display_name": self._to_display_name(table_name) + " 流程",
                        "description": f"从表 {table_name} 推断的业务流程",
                        "related_object_types": related,
                    })

            # ── Infer function_types from views or computed tables ──────
            # Views detected via Inspector
            for view_name in view_names:
                try:
                    view_cols = inspector.get_columns(view_name)
                except Exception:
                    view_cols = []
                classified_tables.add(view_name)

                expression_schema = {}
                for col in view_cols:
                    expression_schema[col["name"]] = {
                        "type": self._map_sql_type(str(col.get("type", ""))),
                    }

                function_types.append({
                    "name": f"{view_name}_function",
                    "display_name": self._to_display_name(view_name) + " 函数",
                    "description": f"从视图 {view_name} 推断的计算函数",
                    "logic_types": ["compute"],
                    "expression_schema": expression_schema,
                    "related_object_types": [],
                })

            # Tables with computed-like names
            for table_name in tables:
                if table_name in classified_tables:
                    continue
                name_lower = table_name.lower()
                if any(kw in name_lower for kw in _FUNCTION_TABLE_KEYWORDS):
                    classified_tables.add(table_name)
                    cols = table_columns_map.get(table_name, [])
                    expression_schema = {}
                    for col in cols:
                        expression_schema[col["name"]] = {
                            "type": self._map_sql_type(str(col.get("type", ""))),
                        }

                    function_types.append({
                        "name": f"{table_name}_function",
                        "display_name": self._to_display_name(table_name) + " 函数",
                        "description": f"从表 {table_name} 推断的计算函数",
                        "logic_types": ["compute", "transform"],
                        "expression_schema": expression_schema,
                        "related_object_types": [],
                    })

            # ── Infer indicator_types from metric/indicator tables ──────
            for table_name in tables:
                name_lower = table_name.lower()
                cols = table_columns_map.get(table_name, [])

                # Check table name pattern
                is_indicator_table = any(kw in name_lower for kw in _INDICATOR_TABLE_KEYWORDS)

                # Check for numeric columns with indicator-like names
                indicator_columns = []
                for col in cols:
                    col_type_upper = str(col.get("type", "")).upper()
                    is_numeric = any(t in col_type_upper for t in _NUMERIC_SQL_TYPES)
                    col_name_lower = col["name"].lower()
                    if is_numeric and any(kw in col_name_lower for kw in _INDICATOR_COLUMN_KEYWORDS):
                        indicator_columns.append(col)

                if is_indicator_table or indicator_columns:
                    classified_tables.add(table_name)
                    formula_schema = {}
                    for ic in indicator_columns:
                        formula_schema[ic["name"]] = {
                            "type": self._map_sql_type(str(ic.get("type", ""))),
                            "description": f"指标列 {ic['name']}",
                        }

                    # Determine indicator sub-type
                    ind_type = "kpi" if is_indicator_table else "metric"

                    indicator_types.append({
                        "name": f"{table_name}_indicator",
                        "display_name": self._to_display_name(table_name) + " 指标",
                        "description": f"从表 {table_name} 推断的指标定义",
                        "indicator_type": ind_type,
                        "formula_schema": formula_schema,
                        "unit": "",
                    })

            engine.dispose()

            result = {
                "status": "ok",
                "object_types": object_types,
                "link_types": link_types,
                "action_types": action_types,
                "rule_types": rule_types,
                "process_types": process_types,
                "function_types": function_types,
                "indicator_types": indicator_types,
                "summary": {
                    "tables": len(tables),
                    "object_types": len(object_types),
                    "link_types": len(link_types),
                    "action_types": len(action_types),
                    "rule_types": len(rule_types),
                    "process_types": len(process_types),
                    "function_types": len(function_types),
                    "indicator_types": len(indicator_types),
                },
            }
            return result

        except Exception as e:
            logger.error(f"Schema extraction failed: {e}")
            return {"status": "error", "message": f"Schema extraction failed: {str(e)}"}

    def _create_engine(
        self,
        db_type: str,
        host: str,
        port: int,
        database: str,
        username: str = None,
        password: str = None,
    ):
        """Create SQLAlchemy engine based on database type."""
        from sqlalchemy import create_engine

        if db_type == "sqlite":
            url = f"sqlite:///{database}"
            return create_engine(url)
        elif db_type == "postgresql":
            url = f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"
        elif db_type == "mysql":
            url = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
        return create_engine(url, connect_args={"connect_timeout": 10})

    def _map_sql_type(self, sql_type: str) -> str:
        """Map SQL type string to PropertyType string."""
        sql_type_upper = sql_type.upper()
        for key, value in self.SQL_TYPE_MAP.items():
            if key in sql_type_upper:
                return value
        return "string"

    @staticmethod
    def _to_display_name(name: str) -> str:
        """Convert snake_case to Display Name."""
        return name.replace("_", " ").title()
