"""Tests for DatabaseSchemaExtractor.

Covers:
- SQL type mapping (_map_sql_type)
- Display name conversion (_to_display_name)
- test_connection with real SQLite DB
- extract_schema with real SQLite DB (tables, columns, foreign keys, table_filter)
- _create_engine for different db_types
"""

import sqlite3

import pytest


# ---------------------------------------------------------------------------
# Module-level import guard: skip entire file if sqlalchemy is unavailable
# ---------------------------------------------------------------------------
try:
    from sqlalchemy import create_engine, inspect  # noqa: F401
except ImportError:
    pytest.skip("sqlalchemy not installed", allow_module_level=True)

from odap.biz.core.ontology.design.ingestion_split.db_schema_ingester import (
    DatabaseSchemaExtractor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def extractor():
    """Provide a fresh DatabaseSchemaExtractor instance."""
    return DatabaseSchemaExtractor()


@pytest.fixture
def sample_db(tmp_path):
    """Create a sample SQLite database with two tables and a foreign key."""
    db_path = str(tmp_path / "sample.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT,
            age INTEGER,
            is_active BOOLEAN DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            total REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def empty_db(tmp_path):
    """Create an empty SQLite database (no tables)."""
    db_path = str(tmp_path / "empty.db")
    conn = sqlite3.connect(db_path)
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# 1. SQL Type Mapping
# ---------------------------------------------------------------------------


class TestMapSqlType:
    """Tests for DatabaseSchemaExtractor._map_sql_type."""

    @pytest.fixture(autouse=True)
    def setup(self, extractor):
        self.ext = extractor

    # -- STRING mappings ----------------------------------------------------

    @pytest.mark.parametrize(
        "sql_type",
        ["VARCHAR", "VARCHAR(255)", "CHAR", "CHAR(10)", "TEXT", "NVARCHAR", "CLOB"],
    )
    def test_string_types(self, sql_type):
        assert self.ext._map_sql_type(sql_type) == "string"

    # -- INTEGER mappings ---------------------------------------------------

    @pytest.mark.parametrize(
        "sql_type", ["INTEGER", "INT", "SMALLINT", "BIGINT", "TINYINT"]
    )
    def test_integer_types(self, sql_type):
        assert self.ext._map_sql_type(sql_type) == "integer"

    # -- FLOAT mappings -----------------------------------------------------

    @pytest.mark.parametrize(
        "sql_type", ["FLOAT", "DOUBLE", "DECIMAL", "DECIMAL(10,2)", "NUMERIC", "REAL"]
    )
    def test_float_types(self, sql_type):
        assert self.ext._map_sql_type(sql_type) == "float"

    # -- BOOLEAN mappings ---------------------------------------------------

    @pytest.mark.parametrize("sql_type", ["BOOLEAN", "BOOL", "BIT"])
    def test_boolean_types(self, sql_type):
        assert self.ext._map_sql_type(sql_type) == "boolean"

    # -- DATETIME mappings --------------------------------------------------

    @pytest.mark.parametrize("sql_type", ["DATE", "DATETIME", "TIMESTAMP", "TIME"])
    def test_datetime_types(self, sql_type):
        assert self.ext._map_sql_type(sql_type) == "datetime"

    # -- JSON mappings ------------------------------------------------------

    @pytest.mark.parametrize("sql_type", ["JSON", "JSONB", "BLOB", "BYTEA", "VARBINARY"])
    def test_json_types(self, sql_type):
        assert self.ext._map_sql_type(sql_type) == "json"

    # -- Default fallback ---------------------------------------------------

    def test_unknown_type_defaults_to_string(self):
        assert self.ext._map_sql_type("GEOMETRY") == "string"

    def test_empty_string_defaults_to_string(self):
        assert self.ext._map_sql_type("") == "string"

    # -- Case insensitivity -------------------------------------------------

    def test_case_insensitive_mapping(self):
        assert self.ext._map_sql_type("varchar") == "string"
        assert self.ext._map_sql_type("Integer") == "integer"
        assert self.ext._map_sql_type("TIMESTAMP") == "datetime"


# ---------------------------------------------------------------------------
# 2. Display Name Conversion
# ---------------------------------------------------------------------------


class TestToDisplayName:
    """Tests for DatabaseSchemaExtractor._to_display_name."""

    @pytest.mark.parametrize(
        "input_name, expected",
        [
            ("user_account", "User Account"),
            ("order_item", "Order Item"),
            ("id", "Id"),
            ("created_at", "Created At"),
            ("is_active", "Is Active"),
            ("user_id", "User Id"),
            ("single", "Single"),
            ("", ""),
        ],
    )
    def test_snake_case_to_display_name(self, input_name, expected):
        assert DatabaseSchemaExtractor._to_display_name(input_name) == expected


# ---------------------------------------------------------------------------
# 3. Test Connection
# ---------------------------------------------------------------------------


class TestTestConnection:
    """Tests for DatabaseSchemaExtractor.test_connection."""

    def test_connection_success(self, extractor, sample_db):
        result = extractor.test_connection(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
        )
        assert result["status"] == "ok"
        assert result["table_count"] == 2
        assert result["schema_name"] == sample_db

    def test_connection_empty_db(self, extractor, empty_db):
        result = extractor.test_connection(
            db_type="sqlite",
            host="",
            port=0,
            database=empty_db,
        )
        assert result["status"] == "ok"
        assert result["table_count"] == 0

    def test_connection_failure_invalid_path(self, extractor):
        result = extractor.test_connection(
            db_type="sqlite",
            host="",
            port=0,
            database="/nonexistent/path/to/db.sqlite",
        )
        assert result["status"] == "error"
        assert result["table_count"] == 0

    def test_connection_failure_unsupported_db_type(self, extractor):
        result = extractor.test_connection(
            db_type="oracle",
            host="localhost",
            port=1521,
            database="orcl",
        )
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# 4. Extract Schema
# ---------------------------------------------------------------------------


class TestExtractSchema:
    """Tests for DatabaseSchemaExtractor.extract_schema."""

    def test_extract_schema_basic(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        assert result["status"] == "ok"
        assert len(result["object_types"]) == 2
        assert result["summary"]["tables"] == 2
        assert result["summary"]["object_types"] == 2

    def test_extract_schema_tables_map_to_object_types(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        table_names = [ot["name"] for ot in result["object_types"]]
        assert "users" in table_names
        assert "orders" in table_names

    def test_extract_schema_object_type_display_name(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        users_ot = next(ot for ot in result["object_types"] if ot["name"] == "users")
        assert users_ot["display_name"] == "Users"

    def test_extract_schema_columns_map_to_properties(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        users_ot = next(ot for ot in result["object_types"] if ot["name"] == "users")
        prop_names = [p["name"] for p in users_ot["properties"]]
        assert "id" in prop_names
        assert "username" in prop_names
        assert "email" in prop_names
        assert "age" in prop_names
        assert "is_active" in prop_names

    def test_extract_schema_property_types(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        users_ot = next(ot for ot in result["object_types"] if ot["name"] == "users")
        prop_map = {p["name"]: p["property_type"] for p in users_ot["properties"]}

        # SQLite reports types as declared; INTEGER -> integer, TEXT -> string
        assert prop_map["id"] == "integer"
        assert prop_map["username"] == "string"
        assert prop_map["age"] == "integer"

    def test_extract_schema_required_fields(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        users_ot = next(ot for ot in result["object_types"] if ot["name"] == "users")
        prop_map = {p["name"]: p["required"] for p in users_ot["properties"]}

        # username is NOT NULL, id is PK -> both required
        assert prop_map["id"] is True
        assert prop_map["username"] is True
        # email is nullable
        assert prop_map["email"] is False

    def test_extract_schema_primary_key(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        users_ot = next(ot for ot in result["object_types"] if ot["name"] == "users")
        assert users_ot["primary_key"] == ["id"]

    def test_extract_schema_foreign_keys_map_to_link_types(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        assert len(result["link_types"]) >= 1
        fk_link = result["link_types"][0]
        assert fk_link["source_type"] == "orders"
        assert fk_link["target_type"] == "users"
        assert fk_link["cardinality"] == "N:1"
        assert fk_link["link_type"] == "ASSOCIATION"

    def test_extract_schema_link_type_name(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        fk_link = result["link_types"][0]
        assert fk_link["name"] == "orders_to_users"
        assert fk_link["display_name"] == "Orders To Users"

    def test_extract_schema_link_type_description(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        fk_link = result["link_types"][0]
        assert "FK:" in fk_link["description"]
        assert "orders" in fk_link["description"]
        assert "users" in fk_link["description"]

    def test_extract_schema_with_table_filter(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            table_filter=["users"],
            use_llm_enrichment=False,
        )
        assert result["status"] == "ok"
        assert len(result["object_types"]) == 1
        assert result["object_types"][0]["name"] == "users"
        # No FK link_types when only one table is included
        assert len(result["link_types"]) == 0

    def test_extract_schema_table_filter_nonexistent_table(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            table_filter=["nonexistent"],
            use_llm_enrichment=False,
        )
        assert result["status"] == "ok"
        assert len(result["object_types"]) == 0
        assert result["summary"]["tables"] == 0

    def test_extract_schema_empty_db(self, extractor, empty_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=empty_db,
            use_llm_enrichment=False,
        )
        assert result["status"] == "ok"
        assert len(result["object_types"]) == 0
        assert result["summary"]["tables"] == 0

    def test_extract_schema_failure_invalid_path(self, extractor):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database="/nonexistent/path/db.sqlite",
            use_llm_enrichment=False,
        )
        assert result["status"] == "error"
        assert "message" in result

    def test_extract_schema_result_structure(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        # Verify all expected top-level keys exist
        expected_keys = {
            "status",
            "object_types",
            "link_types",
            "action_types",
            "rule_types",
            "process_types",
            "function_types",
            "indicator_types",
            "summary",
        }
        assert set(result.keys()) == expected_keys
        # Advanced type lists are present (may be non-empty based on schema patterns)
        assert isinstance(result["action_types"], list)
        assert isinstance(result["rule_types"], list)
        assert isinstance(result["process_types"], list)
        assert isinstance(result["function_types"], list)
        assert isinstance(result["indicator_types"], list)

    def test_extract_schema_summary_counts(self, extractor, sample_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=sample_db,
            use_llm_enrichment=False,
        )
        summary = result["summary"]
        assert summary["tables"] == 2
        assert summary["object_types"] == 2
        assert summary["link_types"] >= 1
        # Advanced type counts are present in summary
        assert "action_types" in summary
        assert "rule_types" in summary
        assert "process_types" in summary
        assert "function_types" in summary
        assert "indicator_types" in summary


# ---------------------------------------------------------------------------
# 5. Engine Creation
# ---------------------------------------------------------------------------


class TestCreateEngine:
    """Tests for DatabaseSchemaExtractor._create_engine."""

    def test_create_engine_sqlite(self, extractor, tmp_path):
        db_path = str(tmp_path / "engine_test.db")
        # Create the file so SQLite can open it
        conn = sqlite3.connect(db_path)
        conn.commit()
        conn.close()

        engine = extractor._create_engine(
            db_type="sqlite", host="", port=0, database=db_path
        )
        assert engine is not None
        assert "sqlite" in str(engine.url)
        engine.dispose()

    def test_create_engine_unsupported_type_raises(self, extractor):
        with pytest.raises(ValueError, match="Unsupported database type"):
            extractor._create_engine(
                db_type="oracle", host="localhost", port=1521, database="orcl"
            )

    def test_create_engine_mysql_url_format(self, extractor):
        """Test that MySQL engine creation attempts the correct URL format.

        This will fail because no MySQL server is running, but we verify
        the method attempts to connect with the right URL pattern.
        """
        # MySQL connection will fail without a server, but _create_engine
        # itself should construct the URL; the failure happens at connect time.
        # We just verify the method exists and doesn't raise on URL construction.
        try:
            engine = extractor._create_engine(
                db_type="mysql",
                host="localhost",
                port=3306,
                database="testdb",
                username="root",
                password="pass",
            )
            # If we get here (unlikely without a MySQL server), dispose
            engine.dispose()
        except Exception as exc:
            # Expected: connection error, not ValueError
            assert "Unsupported" not in str(exc)

    def test_create_engine_postgresql_url_format(self, extractor):
        """Test that PostgreSQL engine creation attempts the correct URL format."""
        try:
            engine = extractor._create_engine(
                db_type="postgresql",
                host="localhost",
                port=5432,
                database="testdb",
                username="postgres",
                password="pass",
            )
            engine.dispose()
        except Exception as exc:
            assert "Unsupported" not in str(exc)


# ---------------------------------------------------------------------------
# 6. Integration: multi-table with multiple foreign keys
# ---------------------------------------------------------------------------


class TestExtractSchemaComplex:
    """Integration tests with a more complex database schema."""

    @pytest.fixture
    def complex_db(self, tmp_path):
        """Create a database with 3 tables and multiple foreign keys."""
        db_path = str(tmp_path / "complex.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL,
                category_id INTEGER REFERENCES categories(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE order_items (
                id INTEGER PRIMARY KEY,
                order_id INTEGER,
                product_id INTEGER REFERENCES products(id),
                quantity INTEGER
            )
            """
        )
        conn.commit()
        conn.close()
        return db_path

    def test_extract_schema_multiple_foreign_keys(self, extractor, complex_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=complex_db,
            use_llm_enrichment=False,
        )
        assert result["status"] == "ok"
        assert len(result["object_types"]) == 3
        # products -> categories, order_items -> products
        assert len(result["link_types"]) == 2

    def test_extract_schema_table_filter_partial(self, extractor, complex_db):
        """Filter to only 2 of 3 tables."""
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=complex_db,
            table_filter=["categories", "products"],
            use_llm_enrichment=False,
        )
        assert len(result["object_types"]) == 2
        # Only products->categories FK is within the filtered set
        assert len(result["link_types"]) == 1

    def test_extract_schema_classification_level(self, extractor, complex_db):
        result = extractor.extract_schema(
            db_type="sqlite",
            host="",
            port=0,
            database=complex_db,
            use_llm_enrichment=False,
        )
        for ot in result["object_types"]:
            assert ot["classification_level"] == "U"


# ---------------------------------------------------------------------------
# 7. Advanced type inference (action, rule, process, function, indicator)
# ---------------------------------------------------------------------------


class TestAdvancedTypeInference:
    """Tests for inferring action_types, rule_types, process_types,
    function_types, and indicator_types from database schema patterns."""

    @pytest.fixture
    def pattern_db(self, tmp_path):
        """Create a database with tables matching each advanced type pattern."""
        db_path = str(tmp_path / "pattern.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE customer (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE transaction_log (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER REFERENCES customer(id),
                amount REAL,
                status TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE order_workflow (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER REFERENCES customer(id),
                state TEXT,
                enabled BOOLEAN DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE kpi_metric (
                id INTEGER PRIMARY KEY,
                value REAL,
                score INTEGER,
                rate REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE calc_transform (
                id INTEGER PRIMARY KEY,
                result REAL
            )
            """
        )
        conn.commit()
        conn.close()
        return db_path

    def test_action_type_inferred_from_log_table(self, extractor, pattern_db):
        """Tables with 'log' in name infer action_types."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        action_names = [at["name"] for at in result["action_types"]]
        assert any("transaction_log" in n for n in action_names)

    def test_action_type_has_target_object_type(self, extractor, pattern_db):
        """Inferred action_type has target_object_type from FK."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        action = next(at for at in result["action_types"] if "transaction_log" in at["name"])
        # FK points to customer table
        assert action["target_object_type"] == "customer"

    def test_action_type_has_parameters(self, extractor, pattern_db):
        """Inferred action_type includes parameters from columns."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        action = next(at for at in result["action_types"] if "transaction_log" in at["name"])
        param_names = [p["name"] for p in action["parameters"]]
        assert "amount" in param_names or "status" in param_names

    def test_rule_type_inferred_from_status_columns(self, extractor, pattern_db):
        """Tables with 'status' or 'state' columns infer rule_types."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        rule_names = [rt["name"] for rt in result["rule_types"]]
        # transaction_log has 'status', order_workflow has 'state' and 'enabled'
        assert len(rule_names) >= 2

    def test_rule_type_has_condition_schema(self, extractor, pattern_db):
        """Inferred rule_type has condition_schema with status columns."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        rule = next(
            rt for rt in result["rule_types"]
            if "transaction_log" in rt["name"]
        )
        assert "status" in rule["condition_schema"]

    def test_process_type_inferred_from_workflow_table(self, extractor, pattern_db):
        """Tables with 'workflow' in name infer process_types."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        process_names = [pt["name"] for pt in result["process_types"]]
        assert any("order_workflow" in n for n in process_names)

    def test_process_type_has_related_object_types(self, extractor, pattern_db):
        """Inferred process_type has related_object_types from FKs."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        process = next(
            pt for pt in result["process_types"]
            if "order_workflow" in pt["name"]
        )
        assert "customer" in process["related_object_types"]

    def test_function_type_inferred_from_calc_table(self, extractor, pattern_db):
        """Tables with 'calc' or 'transform' in name infer function_types."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        func_names = [ft["name"] for ft in result["function_types"]]
        assert any("calc_transform" in n for n in func_names)

    def test_function_type_has_expression_schema(self, extractor, pattern_db):
        """Inferred function_type has expression_schema with columns."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        func = next(
            ft for ft in result["function_types"]
            if "calc_transform" in ft["name"]
        )
        assert "result" in func["expression_schema"]

    def test_indicator_type_inferred_from_metric_table(self, extractor, pattern_db):
        """Tables with 'metric' or 'kpi' in name infer indicator_types."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        indicator_names = [it["name"] for it in result["indicator_types"]]
        assert any("kpi_metric" in n for n in indicator_names)

    def test_indicator_type_has_formula_schema(self, extractor, pattern_db):
        """Inferred indicator_type has formula_schema with numeric columns."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        indicator = next(
            it for it in result["indicator_types"]
            if "kpi_metric" in it["name"]
        )
        # value, score, rate are all numeric + indicator-like names
        assert "value" in indicator["formula_schema"]
        assert "score" in indicator["formula_schema"]
        assert "rate" in indicator["formula_schema"]

    def test_indicator_type_from_numeric_indicator_columns(self, extractor, tmp_path):
        """Tables with numeric columns named 'value'/'score' infer indicator_types."""
        db_path = str(tmp_path / "indicator_cols.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY,
                total_amount REAL,
                description TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=db_path,
        )
        # "total_amount" contains "total" which is in _INDICATOR_COLUMN_KEYWORDS
        # and it's REAL type (numeric)
        assert len(result["indicator_types"]) >= 1

    def test_no_advanced_types_from_plain_tables(self, extractor, tmp_path):
        """Plain tables without pattern keywords produce no advanced types."""
        db_path = str(tmp_path / "plain.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE person (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=db_path,
        )
        assert result["action_types"] == []
        assert result["rule_types"] == []
        assert result["process_types"] == []
        assert result["function_types"] == []
        assert result["indicator_types"] == []

    def test_advanced_type_display_name_format(self, extractor, pattern_db):
        """Inferred advanced types have proper display_name with suffix."""
        result = extractor.extract_schema(
            db_type="sqlite", host="", port=0, database=pattern_db,
        )
        action = next(at for at in result["action_types"] if "transaction_log" in at["name"])
        assert action["display_name"].endswith("动作")

        rule = next(rt for rt in result["rule_types"] if "transaction_log" in rt["name"])
        assert rule["display_name"].endswith("规则")

        process = next(pt for pt in result["process_types"] if "order_workflow" in pt["name"])
        assert process["display_name"].endswith("流程")

        func = next(ft for ft in result["function_types"] if "calc_transform" in ft["name"])
        assert func["display_name"].endswith("函数")

        indicator = next(it for it in result["indicator_types"] if "kpi_metric" in it["name"])
        assert indicator["display_name"].endswith("指标")
