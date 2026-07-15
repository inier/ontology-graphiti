import pytest
from unittest.mock import MagicMock, patch

from odap.infra.query.protocols import QuerySource, QueryResult
from odap.infra.query.parser import QueryParser, ParsedQuery
from odap.infra.query.service import QueryService
from odap.infra.query.sources.schema_source import SchemaSourceImpl
from odap.infra.query.sources.entity_source import EntitySourceImpl
from odap.infra.query.sources.topo_source import TopoSourceImpl
from odap.infra.query.sources.temporal_source import TemporalSource


class TestQueryProtocols:
    def test_query_source_enum_values(self):
        assert QuerySource.SCHEMA.value == "schema"
        assert QuerySource.ENTITY.value == "entity"
        assert QuerySource.TOPO.value == "topo"
        assert QuerySource.TEMPORAL.value == "temporal"

    def test_query_result_creation(self):
        result = QueryResult(
            source=QuerySource.ENTITY,
            rows=[{"id": "1", "name": "test"}],
            total=1,
        )
        assert result.source == QuerySource.ENTITY
        assert result.total == 1
        assert len(result.rows) == 1

    def test_query_result_with_explain(self):
        result = QueryResult(
            source=QuerySource.SCHEMA,
            rows=[],
            total=0,
            explain={"source": "schema"},
        )
        assert result.explain is not None
        assert result.explain["source"] == "schema"


class TestQueryParser:
    @pytest.fixture
    def parser(self):
        return QueryParser()

    def test_parse_schema_query(self, parser):
        parsed = parser.parse(".schema")
        assert parsed.source == QuerySource.SCHEMA

    def test_parse_entity_query(self, parser):
        parsed = parser.parse(".entity")
        assert parsed.source == QuerySource.ENTITY

    def test_parse_topo_query(self, parser):
        parsed = parser.parse(".topo")
        assert parsed.source == QuerySource.TOPO

    def test_parse_temporal_query(self, parser):
        parsed = parser.parse(".temporal")
        assert parsed.source == QuerySource.TEMPORAL

    def test_parse_default_to_entity(self, parser):
        parsed = parser.parse("unknown query")
        assert parsed.source == QuerySource.ENTITY

    def test_parse_entity_with_filters(self, parser):
        parsed = parser.parse(".entity with(name='test', status='active')")
        assert parsed.source == QuerySource.ENTITY
        assert parsed.filters.get("name") == "test"
        assert parsed.filters.get("status") == "active"

    def test_parse_topo_neighbors(self, parser):
        parsed = parser.parse(".topo neighbors(id='e1', direction='outbound', depth=2)")
        assert parsed.source == QuerySource.TOPO
        assert parsed.action == "neighbors"
        assert parsed.action_params.get("id") == "e1"
        assert parsed.action_params.get("depth") == 2

    def test_parse_topo_path(self, parser):
        parsed = parser.parse(".topo path(from='a', to='b', max_hops=3)")
        assert parsed.action == "path"
        assert parsed.action_params.get("from") == "a"
        assert parsed.action_params.get("max_depth") == 3

    def test_parse_temporal_at(self, parser):
        parsed = parser.parse(".temporal at('2024-01-01')")
        assert parsed.source == QuerySource.TEMPORAL
        assert parsed.action == "at"
        assert parsed.action_params.get("valid_time") == "2024-01-01"

    def test_parse_temporal_history(self, parser):
        parsed = parser.parse(".temporal history(id='e1')")
        assert parsed.action == "history"
        assert parsed.action_params.get("id") == "e1"

    def test_parse_limit(self, parser):
        parsed = parser.parse(".entity", limit=50)
        assert parsed.limit == 50


class TestQueryService:
    @pytest.fixture
    def mock_schema_source(self):
        source = MagicMock(spec=SchemaSourceImpl)
        source.query_object_types.return_value = [{"name": "Radar", "kind": "object_type"}]
        source.query_link_definitions.return_value = [{"name": "tracks", "kind": "link"}]
        source.query_action_types.return_value = [{"name": "Deploy", "kind": "action"}]
        return source

    @pytest.fixture
    def mock_entity_source(self):
        source = MagicMock(spec=EntitySourceImpl)
        source.query_entities.return_value = [{"id": "e1", "name": "Radar-A"}]
        source.get_entity.return_value = {"id": "e1", "name": "Radar-A"}
        source.search_entities.return_value = [{"id": "e1", "name": "Radar-A"}]
        return source

    @pytest.fixture
    def mock_topo_source(self):
        source = MagicMock(spec=TopoSourceImpl)
        source.get_neighbors.return_value = [{"id": "n1"}]
        source.get_relations.return_value = [{"id": "r1", "type": "tracks"}]
        source.traverse.return_value = {"nodes": [{"id": "a"}, {"id": "b"}], "edges": []}
        return source

    @pytest.fixture
    def mock_temporal_source(self):
        source = MagicMock(spec=TemporalSource)
        source.query.return_value = [{"id": "t1"}]
        source.query_at_time.return_value = [{"id": "t1", "valid_time": "2024-01-01"}]
        source.query_history.return_value = [{"id": "h1"}]
        source.query_range.return_value = [{"id": "r1"}]
        return source

    @pytest.fixture
    def service(self, mock_schema_source, mock_entity_source, mock_topo_source, mock_temporal_source):
        QueryService._instance = None
        svc = QueryService(
            schema_source=mock_schema_source,
            entity_source=mock_entity_source,
            topo_source=mock_topo_source,
            temporal_source=mock_temporal_source,
        )
        return svc

    def test_execute_schema_query(self, service):
        result = service.execute("default", ".schema")
        assert result.source == QuerySource.SCHEMA
        assert len(result.rows) > 0

    def test_execute_entity_query(self, service):
        result = service.execute("default", ".entity")
        assert result.source == QuerySource.ENTITY

    def test_execute_entity_search(self, service):
        result = service.execute("default", ".entity with(search='radar')")
        assert result.source == QuerySource.ENTITY

    def test_execute_entity_get_by_id(self, service):
        result = service.execute("default", ".entity with(id='e1')")
        assert result.source == QuerySource.ENTITY

    def test_execute_topo_neighbors(self, service):
        result = service.execute("default", ".topo neighbors(id='e1')")
        assert result.source == QuerySource.TOPO

    def test_execute_topo_path(self, service):
        result = service.execute("default", ".topo path(from='a', to='b')")
        assert result.source == QuerySource.TOPO

    def test_execute_temporal_history(self, service):
        result = service.execute("default", ".temporal history(id='e1')")
        assert result.source == QuerySource.TEMPORAL

    def test_execute_temporal_at(self, service):
        result = service.execute("default", ".temporal at('2024-01-01')")
        assert result.source == QuerySource.TEMPORAL

    def test_explain_query(self, service):
        result = service.explain("default", ".entity with(name='test')")
        assert result["source"] == "entity"
        assert "filters" in result

    def test_validate_valid_query(self, service):
        result = service.validate(".schema")
        assert result["valid"] is True
        assert result["source"] == "schema"

    def test_validate_invalid_query(self, service):
        result = service.validate("not a query")
        assert result["source"] == "entity"

    def test_list_sources(self, service):
        sources = service.list_sources()
        assert len(sources) >= 4
        source_names = [s["name"] for s in sources]
        assert "schema" in source_names
        assert "entity" in source_names
        assert "topo" in source_names
        assert "temporal" in source_names

    def test_agent_safe_mode(self, service):
        service.enable_agent_safe_mode(True)
        result = service.execute("default", ".schema", agent_safe=True)
        assert result.source == QuerySource.SCHEMA

    def test_register_tool_source(self, service):
        mock_handler = MagicMock()
        service.register_tool_source("custom", mock_handler)
        sources = service.list_sources()
        custom_sources = [s for s in sources if s["name"] == "custom"]
        assert len(custom_sources) == 1


class TestQueryTools:
    def test_query_tools_classes_exist(self):
        from odap.infra.query.query_tools import QUERY_TOOLS
        assert len(QUERY_TOOLS) == 4

    def test_query_schema_tool(self):
        from odap.infra.query.query_tools import QuerySchemaTool
        tool = QuerySchemaTool()
        assert tool.name == "query_schema"
        assert tool.source == QuerySource.SCHEMA

    def test_query_entity_tool(self):
        from odap.infra.query.query_tools import QueryEntityTool
        tool = QueryEntityTool()
        assert tool.name == "query_entity"
        assert tool.source == QuerySource.ENTITY

    def test_query_topo_tool(self):
        from odap.infra.query.query_tools import QueryTopoTool
        tool = QueryTopoTool()
        assert tool.name == "query_topo"
        assert tool.source == QuerySource.TOPO

    def test_query_temporal_tool(self):
        from odap.infra.query.query_tools import QueryTemporalTool
        tool = QueryTemporalTool()
        assert tool.name == "query_temporal"
        assert tool.source == QuerySource.TEMPORAL


class TestCognitionModels:
    def test_intent_result_defaults(self):
        from odap.biz.core.cognition.models.cognition_models import IntentResult, IntentType
        result = IntentResult()
        assert result.primary_intent == IntentType.QUERY
        assert result.confidence == 0.0
        assert result.entities == []
        assert result.attributes == {}
        assert result.alternative_intents == []
        assert result.role == "guest"

    def test_intent_result_with_values(self):
        from odap.biz.core.cognition.models.cognition_models import IntentResult, IntentType
        result = IntentResult(
            primary_intent=IntentType.ACTION,
            confidence=0.9,
            entities=["radar-1"],
            role="commander",
        )
        assert result.primary_intent == IntentType.ACTION
        assert result.confidence == 0.9
        assert "radar-1" in result.entities

    def test_navigation_path_defaults(self):
        from odap.biz.core.cognition.models.cognition_models import NavigationPath
        path = NavigationPath(entity_id="e1")
        assert path.entity_id == "e1"
        assert path.direction == "outbound"
        assert path.depth == 1
        assert path.path_nodes == []

    def test_explanation_defaults(self):
        from odap.biz.core.cognition.models.cognition_models import Explanation
        exp = Explanation(decision_id="d1")
        assert exp.decision_id == "d1"
        assert exp.confidence == 0.0
        assert exp.reasoning_chain == []
        assert exp.sources == []

    def test_role_view_config_defaults(self):
        from odap.biz.core.cognition.models.cognition_models import RoleViewConfig
        config = RoleViewConfig(role="commander", name="指挥官视图")
        assert config.role == "commander"
        assert config.name == "指挥官视图"
        assert config.capabilities == []

    def test_intent_type_enum(self):
        from odap.biz.core.cognition.models.cognition_models import IntentType
        assert IntentType.QUERY.value == "query"
        assert IntentType.ACTION.value == "action"
        assert IntentType.EXPLAIN.value == "explain"
        assert IntentType.RECOMMEND.value == "recommend"
        assert IntentType.NAVIGATE.value == "navigate"
        assert IntentType.COMPARE.value == "compare"
        assert IntentType.ANALYZE.value == "analyze"


class TestToolModels:
    def test_tool_definition_defaults(self):
        from odap.biz.platform.tool_registry.models.tool_models import ToolDefinition, ToolType
        td = ToolDefinition(name="test_tool")
        assert td.name == "test_tool"
        assert td.tool_type == ToolType.FUNCTION
        assert td.category == "general"
        assert td.status.value == "registered"

    def test_tool_definition_with_values(self):
        from odap.biz.platform.tool_registry.models.tool_models import ToolDefinition, ToolType
        td = ToolDefinition(
            name="my_skill",
            description="A test skill",
            tool_type=ToolType.SKILL,
            category="intelligence",
            capabilities=["query", "analyze"],
        )
        assert td.tool_type == ToolType.SKILL
        assert "query" in td.capabilities

    def test_tool_type_enum(self):
        from odap.biz.platform.tool_registry.models.tool_models import ToolType
        assert ToolType.SKILL.value == "skill"
        assert ToolType.MCP.value == "mcp"
        assert ToolType.REST.value == "rest"
        assert ToolType.FUNCTION.value == "function"

    def test_tool_invocation(self):
        from odap.biz.platform.tool_registry.models.tool_models import ToolInvocation
        inv = ToolInvocation(tool_id="t1", params={"key": "value"})
        assert inv.tool_id == "t1"
        assert inv.params["key"] == "value"

    def test_tool_invocation_result(self):
        from odap.biz.platform.tool_registry.models.tool_models import ToolInvocationResult
        result = ToolInvocationResult(
            tool_id="t1",
            tool_name="test",
            success=True,
            data={"output": "ok"},
        )
        assert result.success is True
        assert result.data["output"] == "ok"

    def test_tool_status_enum(self):
        from odap.biz.platform.tool_registry.models.tool_models import ToolStatus
        assert ToolStatus.REGISTERED.value == "registered"
        assert ToolStatus.ACTIVE.value == "active"
        assert ToolStatus.DEPRECATED.value == "deprecated"
        assert ToolStatus.DISABLED.value == "disabled"
