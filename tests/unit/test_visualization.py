import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.simulation.visualization.visualization_engine import (
    VisualizationEngineV2,
    GraphLayoutEngine,
    DataConverter,
    GraphLayout,
    ChartType,
    VisualizationType,
    GraphNode,
    GraphEdge,
    GraphData,
    MapEntity,
    MapLayer,
    MapData,
    ChartSeries,
    ChartData,
)


class TestGraphLayoutEngine:
    @pytest.fixture
    def engine(self):
        return GraphLayoutEngine()

    def _make_graph(self, n=3):
        nodes = [
            GraphNode(node_id=f"n{i}", label=f"Node {i}", node_type="default")
            for i in range(n)
        ]
        edges = [
            GraphEdge(edge_id=f"e{i}", source=f"n{i}", target=f"n{(i+1) % n}")
            for i in range(n)
        ]
        return GraphData(nodes=nodes, edges=edges)

    def test_force_layout(self, engine):
        graph = self._make_graph()
        result = engine.apply_layout(graph, GraphLayout.FORCE)
        assert len(result.nodes) == 3
        for node in result.nodes:
            assert node.x != 0 or node.y != 0

    def test_circular_layout(self, engine):
        graph = self._make_graph(4)
        result = engine.apply_layout(graph, GraphLayout.CIRCULAR)
        assert len(result.nodes) == 4
        for node in result.nodes:
            assert node.x != 0
            assert node.y != 0

    def test_hierarchical_layout(self, engine):
        nodes = [
            GraphNode(node_id="n0", label="Root", node_type="default", properties={"level": 0}),
            GraphNode(node_id="n1", label="Child1", node_type="default", properties={"level": 1}),
            GraphNode(node_id="n2", label="Child2", node_type="default", properties={"level": 1}),
        ]
        edges = [
            GraphEdge(edge_id="e0", source="n0", target="n1"),
            GraphEdge(edge_id="e1", source="n0", target="n2"),
        ]
        graph = GraphData(nodes=nodes, edges=edges)
        result = engine.apply_layout(graph, GraphLayout.HIERARCHICAL)
        assert len(result.nodes) == 3
        assert result.nodes[0].y < result.nodes[1].y

    def test_grid_layout(self, engine):
        graph = self._make_graph(4)
        result = engine.apply_layout(graph, GraphLayout.GRID)
        assert len(result.nodes) == 4
        positions = [(n.x, n.y) for n in result.nodes]
        assert len(set(positions)) == 4

    def test_radial_layout(self, engine):
        graph = self._make_graph(5)
        result = engine.apply_layout(graph, GraphLayout.RADIAL)
        assert len(result.nodes) == 5
        assert result.nodes[0].size == 20

    def test_unknown_layout_defaults_to_force(self, engine):
        graph = self._make_graph()
        result = engine.apply_layout(graph, "nonexistent")
        assert len(result.nodes) == 3


class TestDataConverter:
    def test_entities_to_graph(self):
        entities = [
            {"id": "e1", "name": "Entity1", "type": "person"},
            {"id": "e2", "name": "Entity2", "type": "org"},
        ]
        relationships = [
            {"source": "e1", "target": "e2", "type": "works_at"},
        ]
        result = DataConverter.entities_to_graph(entities, relationships)
        assert len(result.nodes) == 2
        assert len(result.edges) == 1
        assert result.nodes[0].node_id == "e1"
        assert result.edges[0].source == "e1"
        assert result.edges[0].target == "e2"

    def test_entities_to_graph_dedup_edges(self):
        entities = [
            {"id": "e1", "name": "Entity1", "type": "person"},
            {"id": "e2", "name": "Entity2", "type": "org"},
        ]
        relationships = [
            {"source": "e1", "target": "e2", "type": "works_at"},
            {"source": "e1", "target": "e2", "type": "manages"},
        ]
        result = DataConverter.entities_to_graph(entities, relationships)
        assert len(result.edges) == 1

    def test_entities_to_graph_with_layout(self):
        entities = [{"id": "e1", "name": "E1", "type": "t"}]
        relationships = []
        result = DataConverter.entities_to_graph(entities, relationships, GraphLayout.CIRCULAR)
        assert len(result.nodes) == 1

    def test_entities_to_map(self):
        entities = [
            {"id": "m1", "name": "Loc1", "type": "city", "latitude": 39.9, "longitude": 116.4},
            {"id": "m2", "name": "Loc2", "type": "city", "latitude": 31.2, "longitude": 121.5},
        ]
        result = DataConverter.entities_to_map(entities)
        assert len(result.layers) == 1
        assert result.zoom == 10
        assert result.center_lat != 0

    def test_entities_to_map_skip_zero_coords(self):
        entities = [
            {"id": "m1", "name": "NoCoords", "type": "virtual", "latitude": 0, "longitude": 0},
        ]
        result = DataConverter.entities_to_map(entities)
        assert len(result.layers) == 0
        assert result.center_lat == 39.9
        assert result.center_lon == 116.4

    def test_entities_to_map_nested_properties(self):
        entities = [
            {
                "id": "m1", "name": "Nested", "type": "base",
                "properties": {"latitude": 35.0, "longitude": 110.0}
            },
        ]
        result = DataConverter.entities_to_map(entities)
        assert len(result.layers) == 1

    def test_statistics_to_chart_dict_values(self):
        stats = {"threat_level": {"low": 10, "medium": 5, "high": 2}}
        result = DataConverter.statistics_to_chart(stats, ChartType.BAR)
        assert result.title == "Statistics"
        assert len(result.series) == 1
        assert result.series[0].name == "threat_level"
        assert len(result.series[0].data) == 3

    def test_statistics_to_chart_scalar_values(self):
        stats = {"radar_count": 5, "command_count": 2}
        result = DataConverter.statistics_to_chart(stats, ChartType.PIE)
        assert len(result.series) == 2
        assert result.series[0].data[0]["value"] == 5

    def test_statistics_to_chart_list_values(self):
        stats = {"data": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]}
        result = DataConverter.statistics_to_chart(stats, ChartType.LINE)
        assert len(result.series) == 1
        assert len(result.series[0].data) == 2


class TestVisualizationEngineV2:
    @pytest.fixture
    def engine(self):
        return VisualizationEngineV2()

    def test_create_graph(self, engine):
        entities = [
            {"id": "n1", "name": "Node1", "type": "t1"},
            {"id": "n2", "name": "Node2", "type": "t2"},
        ]
        relationships = [{"source": "n1", "target": "n2", "type": "rel"}]
        graph = engine.create_graph("g1", entities, relationships, GraphLayout.FORCE)
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert engine.get_graph("g1") is graph

    def test_create_graph_circular_layout(self, engine):
        entities = [
            {"id": "n1", "name": "Node1", "type": "t1"},
            {"id": "n2", "name": "Node2", "type": "t2"},
            {"id": "n3", "name": "Node3", "type": "t1"},
        ]
        relationships = [
            {"source": "n1", "target": "n2", "type": "rel"},
            {"source": "n2", "target": "n3", "type": "rel"},
        ]
        graph = engine.create_graph("g2", entities, relationships, GraphLayout.CIRCULAR)
        assert len(graph.nodes) == 3
        for node in graph.nodes:
            assert node.x != 0

    def test_update_graph_node(self, engine):
        entities = [{"id": "n1", "name": "Node1", "type": "t1"}]
        relationships = []
        engine.create_graph("g3", entities, relationships)
        result = engine.update_graph_node("g3", "n1", {"label": "Updated"})
        assert result is True
        graph = engine.get_graph("g3")
        assert graph.nodes[0].label == "Updated"

    def test_update_graph_node_nonexistent(self, engine):
        result = engine.update_graph_node("nonexistent", "n1", {"label": "X"})
        assert result is False

    def test_add_graph_node(self, engine):
        entities = [{"id": "n1", "name": "Node1", "type": "t1"}]
        engine.create_graph("g4", entities, [])
        new_node = GraphNode(node_id="n2", label="Node2", node_type="t2")
        result = engine.add_graph_node("g4", new_node)
        assert result is True
        assert len(engine.get_graph("g4").nodes) == 2

    def test_add_graph_edge(self, engine):
        entities = [
            {"id": "n1", "name": "Node1", "type": "t1"},
            {"id": "n2", "name": "Node2", "type": "t2"},
        ]
        engine.create_graph("g5", entities, [])
        new_edge = GraphEdge(edge_id="e1", source="n1", target="n2")
        result = engine.add_graph_edge("g5", new_edge)
        assert result is True
        assert len(engine.get_graph("g5").edges) == 1

    def test_create_map(self, engine):
        entities = [
            {"id": "m1", "name": "Loc1", "type": "city", "latitude": 39.9, "longitude": 116.4},
        ]
        map_data = engine.create_map("map1", entities)
        assert map_data is not None
        assert engine.get_map("map1") is map_data

    def test_update_map_entity(self, engine):
        entities = [
            {"id": "m1", "name": "Loc1", "type": "city", "latitude": 39.9, "longitude": 116.4},
        ]
        engine.create_map("map2", entities)
        result = engine.update_map_entity("map2", "m1", {"name": "Updated"})
        assert result is True

    def test_create_chart(self, engine):
        stats = {"count": 5, "level": {"low": 10, "high": 2}}
        chart = engine.create_chart("chart1", stats, ChartType.BAR)
        assert chart.chart_id == "chart1"
        assert len(chart.series) == 2
        assert engine.get_chart("chart1") is chart

    def test_to_echarts_option(self, engine):
        stats = {"count": 5}
        chart = engine.create_chart("ech1", stats, ChartType.BAR)
        option = engine.to_echarts_option(chart)
        assert option["title"]["text"] == "Statistics"
        assert len(option["series"]) == 1
        assert option["series"][0]["type"] == "bar"

    def test_to_graphiti_format(self, engine):
        entities = [{"id": "n1", "name": "N1", "type": "t"}]
        relationships = []
        graph = engine.create_graph("gf1", entities, relationships)
        result = engine.to_graphiti_format(graph)
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["id"] == "n1"
        assert "edges" in result
        assert "categories" in result

    def test_to_geojson(self, engine):
        entities = [
            {"id": "m1", "name": "Loc1", "type": "city", "latitude": 39.9, "longitude": 116.4},
        ]
        map_data = engine.create_map("geo1", entities)
        geojson = engine.to_geojson(map_data)
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) >= 1

    def test_clear_cache_specific(self, engine):
        entities = [{"id": "n1", "name": "N1", "type": "t"}]
        engine.create_graph("clear1", entities, [])
        engine.clear_cache("clear1")
        assert engine.get_graph("clear1") is None

    def test_clear_cache_all(self, engine):
        entities = [{"id": "n1", "name": "N1", "type": "t"}]
        engine.create_graph("all1", entities, [])
        engine.create_chart("all2", {"k": 1})
        engine.clear_cache()
        assert engine.get_graph("all1") is None
        assert engine.get_chart("all2") is None

    def test_cache_statistics(self, engine):
        entities = [{"id": "n1", "name": "N1", "type": "t"}]
        engine.create_graph("stat1", entities, [])
        stats = engine.get_cache_statistics()
        assert stats["graph_count"] == 1
        assert stats["total_nodes"] == 1

    def test_register_render_callback(self, engine):
        callback = MagicMock()
        engine.register_render_callback(callback)
        assert callback in engine._render_callbacks
