"""
可视化引擎 - Visualization Engine
WR-16: 可视化引擎 (图谱 + 地图 + 图表)

功能：
- 图谱可视化 (Graph)
- 地图可视化 (CesiumJS 风格)
- 图表可视化 (ECharts)
- 数据转换器
- 布局算法
"""

import sys
import os
import json
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid
import math
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class VisualizationType(str, Enum):
    GRAPH = "graph"
    MAP = "map"
    CHART = "chart"
    TIMELINE = "timeline"
    HEATMAP = "heatmap"
    NETWORK = "network"


class GraphLayout(str, Enum):
    FORCE = "force"
    CIRCULAR = "circular"
    HIERARCHICAL = "hierarchical"
    GRID = "grid"
    RADIAL = "radial"


class ChartType(str, Enum):
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    GAUGE = "gauge"
    TREemap = "treemap"


@dataclass
class GraphNode:
    """图节点"""
    node_id: str
    label: str
    node_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    x: float = 0
    y: float = 0
    size: float = 10
    color: str = "#1890ff"
    icon: Optional[str] = None
    category: Optional[str] = None


@dataclass
class GraphEdge:
    """图边"""
    edge_id: str
    source: str
    target: str
    label: str = ""
    edge_type: str = "default"
    weight: float = 1.0
    color: str = "#d9d9d9"
    line_style: str = "solid"
    animated: bool = False


@dataclass
class GraphData:
    """图数据"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    categories: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MapEntity:
    """地图实体"""
    entity_id: str
    name: str
    entity_type: str
    latitude: float
    longitude: float
    altitude: float = 0
    properties: Dict[str, Any] = field(default_factory=dict)
    icon_url: Optional[str] = None
    color: str = "#1890ff"
    size: float = 10
    label_visible: bool = True


@dataclass
class MapLayer:
    """地图图层"""
    layer_id: str
    name: str
    layer_type: str
    entities: List[MapEntity] = field(default_factory=list)
    visible: bool = True
    opacity: float = 1.0


@dataclass
class MapData:
    """地图数据"""
    center_lat: float
    center_lon: float
    zoom: float = 10
    layers: List[MapLayer] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChartSeries:
    """图表系列"""
    series_id: str
    name: str
    series_type: ChartType
    data: List[Any]
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChartData:
    """图表数据"""
    chart_id: str
    title: str
    chart_type: ChartType
    x_axis: Dict[str, Any] = field(default_factory=dict)
    y_axis: Dict[str, Any] = field(default_factory=dict)
    series: List[ChartSeries] = field(default_factory=list)
    legend: Dict[str, Any] = field(default_factory=dict)
    tooltip: Dict[str, Any] = field(default_factory=dict)


class GraphLayoutEngine:
    """图布局引擎"""

    def __init__(self):
        self._layouts = {
            GraphLayout.FORCE: self._force_layout,
            GraphLayout.CIRCULAR: self._circular_layout,
            GraphLayout.HIERARCHICAL: self._hierarchical_layout,
            GraphLayout.GRID: self._grid_layout,
            GraphLayout.RADIAL: self._radial_layout,
        }

    def apply_layout(self, graph: GraphData, layout: GraphLayout,
                    width: float = 800, height: float = 600) -> GraphData:
        layout_func = self._layouts.get(layout, self._force_layout)
        return layout_func(graph, width, height)

    def _force_layout(self, graph: GraphData, width: float, height: float) -> GraphData:
        for node in graph.nodes:
            if node.x == 0 and node.y == 0:
                node.x = width / 2 + (random.random() - 0.5) * 100
                node.y = height / 2 + (random.random() - 0.5) * 100

        return graph

    def _circular_layout(self, graph: GraphData, width: float, height: float) -> GraphData:
        center_x, center_y = width / 2, height / 2
        radius = min(width, height) / 2 - 50

        n = len(graph.nodes)
        for i, node in enumerate(graph.nodes):
            angle = 2 * math.pi * i / n
            node.x = center_x + radius * math.cos(angle)
            node.y = center_y + radius * math.sin(angle)

        return graph

    def _hierarchical_layout(self, graph: GraphData, width: float, height: float) -> GraphData:
        levels: Dict[int, List[GraphNode]] = {}
        for node in graph.nodes:
            level = node.properties.get("level", 0)
            if level not in levels:
                levels[level] = []
            levels[level].append(node)

        level_height = height / (len(levels) + 1)
        for level, nodes in levels.items():
            level_width = width / (len(nodes) + 1)
            for i, node in enumerate(nodes):
                node.x = level_width * (i + 1)
                node.y = level_height * (level + 1)

        return graph

    def _grid_layout(self, graph: GraphData, width: float, height: float) -> GraphData:
        n = len(graph.nodes)
        cols = math.ceil(math.sqrt(n))
        cell_width = width / cols
        cell_height = height / (math.ceil(n / cols))

        for i, node in enumerate(graph.nodes):
            row = i // cols
            col = i % cols
            node.x = cell_width * (col + 0.5)
            node.y = cell_height * (row + 0.5)

        return graph

    def _radial_layout(self, graph: GraphData, width: float, height: float) -> GraphData:
        center_x, center_y = width / 2, height / 2

        if graph.nodes:
            graph.nodes[0].x = center_x
            graph.nodes[0].y = center_y
            graph.nodes[0].size = 20

        for i, node in enumerate(graph.nodes[1:], 1):
            angle = 2 * math.pi * i / len(graph.nodes)
            radius = min(width, height) / 3
            node.x = center_x + radius * math.cos(angle)
            node.y = center_y + radius * math.sin(angle)

        return graph


class DataConverter:
    """数据转换器"""

    @staticmethod
    def entities_to_graph(entities: List[Dict], relationships: List[Dict],
                        layout: GraphLayout = GraphLayout.FORCE) -> GraphData:
        nodes = []
        edges = []
        categories = []

        category_set = set()
        for entity in entities:
            node_type = entity.get("type", "default")
            category_set.add(node_type)

            node = GraphNode(
                node_id=entity.get("id", str(uuid.uuid4())),
                label=entity.get("name", entity.get("id", "Unknown")),
                node_type=node_type,
                properties=entity.get("properties", {}),
                size=entity.get("size", 10),
                color=entity.get("color", "#1890ff"),
                category=node_type
            )
            nodes.append(node)

        categories = [{"name": cat, "itemStyle": {"color": "#1890ff"}} for cat in category_set]

        edge_id_set = set()
        for rel in relationships:
            src = rel.get("source", rel.get("source_id", ""))
            tgt = rel.get("target", rel.get("target_id", ""))

            if src and tgt:
                edge_id = f"{src}-{tgt}"
                if edge_id not in edge_id_set:
                    edge_id_set.add(edge_id)

                    edge = GraphEdge(
                        edge_id=rel.get("id", edge_id),
                        source=src,
                        target=tgt,
                        label=rel.get("type", ""),
                        edge_type=rel.get("type", "default"),
                        weight=rel.get("weight", 1.0),
                        color=rel.get("color", "#d9d9d9"),
                        animated=rel.get("animated", False)
                    )
                    edges.append(edge)

        graph_data = GraphData(nodes=nodes, edges=edges, categories=categories)

        layout_engine = GraphLayoutEngine()
        return layout_engine.apply_layout(graph_data, layout)

    @staticmethod
    def entities_to_map(entities: List[Dict]) -> MapData:
        layers: Dict[str, List[MapEntity]] = {}

        for entity in entities:
            lat = entity.get("properties", {}).get("latitude", entity.get("latitude", 0))
            lon = entity.get("properties", {}).get("longitude", entity.get("longitude", 0))

            if lat == 0 and lon == 0:
                continue

            entity_type = entity.get("type", "default")

            if entity_type not in layers:
                layers[entity_type] = []

            map_entity = MapEntity(
                entity_id=entity.get("id", str(uuid.uuid4())),
                name=entity.get("name", entity.get("id", "Unknown")),
                entity_type=entity_type,
                latitude=lat,
                longitude=lon,
                altitude=entity.get("properties", {}).get("altitude", 0),
                properties=entity.get("properties", {}),
                icon_url=entity.get("icon_url"),
                color=entity.get("color", "#1890ff"),
                size=entity.get("size", 10)
            )
            layers[entity_type].append(map_entity)

        map_layers = [
            MapLayer(
                layer_id=layer_type,
                name=f"{layer_type} Layer",
                layer_type=layer_type,
                entities=entities
            )
            for layer_type, entities in layers.items()
        ]

        if not layers:
            return MapData(center_lat=39.9, center_lon=116.4, zoom=10, layers=map_layers)

        first_key = list(layers.keys())[0]
        first_entities = layers[first_key]
        center_lat = sum(e.latitude for e in first_entities) / max(len(first_entities), 1)
        center_lon = sum(e.longitude for e in first_entities) / max(len(first_entities), 1)

        return MapData(
            center_lat=center_lat or 39.9,
            center_lon=center_lon or 116.4,
            zoom=10,
            layers=map_layers
        )

    @staticmethod
    def statistics_to_chart(stats: Dict[str, Any], chart_type: ChartType = ChartType.BAR) -> ChartData:
        series_list = []

        for key, value in stats.items():
            if isinstance(value, dict):
                series_data = [{"name": k, "value": v} for k, v in value.items()]
            elif isinstance(value, list):
                series_data = value
            else:
                series_data = [{"name": key, "value": value}]

            series = ChartSeries(
                series_id=str(uuid.uuid4()),
                name=key,
                series_type=chart_type,
                data=series_data
            )
            series_list.append(series)

        return ChartData(
            chart_id=str(uuid.uuid4()),
            title="Statistics",
            chart_type=chart_type,
            series=series_list,
            legend={"show": True},
            tooltip={"trigger": "item"}
        )


class VisualizationEngineV2:
    """
    可视化引擎
    统一的可视化渲染引擎
    """

    def __init__(self):
        self._graph_cache: Dict[str, GraphData] = {}
        self._map_cache: Dict[str, MapData] = {}
        self._chart_cache: Dict[str, ChartData] = {}
        self._render_callbacks: List[Callable] = []
        self._lock = threading.RLock()
        self._layout_engine = GraphLayoutEngine()
        self._converter = DataConverter()

    def create_graph(self, data_id: str, entities: List[Dict],
                    relationships: List[Dict],
                    layout: GraphLayout = GraphLayout.FORCE) -> GraphData:
        with self._lock:
            graph = self._converter.entities_to_graph(entities, relationships, layout)

            width = 800
            height = 600
            graph = self._layout_engine.apply_layout(graph, layout, width, height)

            self._graph_cache[data_id] = graph
            return graph

    def update_graph_node(self, data_id: str, node_id: str, updates: Dict[str, Any]) -> bool:
        with self._lock:
            graph = self._graph_cache.get(data_id)
            if not graph:
                return False

            for node in graph.nodes:
                if node.node_id == node_id:
                    for key, value in updates.items():
                        if hasattr(node, key):
                            setattr(node, key, value)
                    return True
            return False

    def add_graph_node(self, data_id: str, node: GraphNode) -> bool:
        with self._lock:
            graph = self._graph_cache.get(data_id)
            if not graph:
                return False

            graph.nodes.append(node)
            return True

    def add_graph_edge(self, data_id: str, edge: GraphEdge) -> bool:
        with self._lock:
            graph = self._graph_cache.get(data_id)
            if not graph:
                return False

            graph.edges.append(edge)
            return True

    def create_map(self, data_id: str, entities: List[Dict]) -> MapData:
        with self._lock:
            map_data = self._converter.entities_to_map(entities)
            self._map_cache[data_id] = map_data
            return map_data

    def update_map_entity(self, data_id: str, entity_id: str, updates: Dict[str, Any]) -> bool:
        with self._lock:
            map_data = self._map_cache.get(data_id)
            if not map_data:
                return False

            for layer in map_data.layers:
                for entity in layer.entities:
                    if entity.entity_id == entity_id:
                        for key, value in updates.items():
                            if hasattr(entity, key):
                                setattr(entity, key, value)
                        return True
            return False

    def create_chart(self, data_id: str, stats: Dict[str, Any],
                   chart_type: ChartType = ChartType.BAR) -> ChartData:
        with self._lock:
            chart = self._converter.statistics_to_chart(stats, chart_type)
            chart.chart_id = data_id
            self._chart_cache[data_id] = chart
            return chart

    def get_graph(self, data_id: str) -> Optional[GraphData]:
        return self._graph_cache.get(data_id)

    def get_map(self, data_id: str) -> Optional[MapData]:
        return self._map_cache.get(data_id)

    def get_chart(self, data_id: str) -> Optional[ChartData]:
        return self._chart_cache.get(data_id)

    def to_echarts_option(self, chart: ChartData) -> Dict[str, Any]:
        series = []
        for s in chart.series:
            series.append({
                "name": s.name,
                "type": s.series_type.value,
                "data": s.data,
                **s.properties
            })

        return {
            "title": {"text": chart.title},
            "tooltip": chart.tooltip,
            "legend": chart.legend,
            "xAxis": chart.x_axis,
            "yAxis": chart.y_axis,
            "series": series
        }

    def to_graphiti_format(self, graph: GraphData) -> Dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": n.node_id,
                    "label": n.label,
                    "type": n.node_type,
                    "x": n.x,
                    "y": n.y,
                    "size": n.size,
                    "color": n.color,
                    "category": n.category
                }
                for n in graph.nodes
            ],
            "edges": [
                {
                    "id": e.edge_id,
                    "source": e.source,
                    "target": e.target,
                    "label": e.label,
                    "type": e.edge_type,
                    "weight": e.weight,
                    "color": e.color,
                    "animated": e.animated
                }
                for e in graph.edges
            ],
            "categories": graph.categories
        }

    def to_geojson(self, map_data: MapData) -> Dict[str, Any]:
        features = []

        for layer in map_data.layers:
            for entity in layer.entities:
                feature = {
                    "type": "Feature",
                    "id": entity.entity_id,
                    "geometry": {
                        "type": "Point",
                        "coordinates": [entity.longitude, entity.latitude, entity.altitude]
                    },
                    "properties": {
                        "name": entity.name,
                        "type": entity.entity_type,
                        "color": entity.color,
                        "size": entity.size,
                        **entity.properties
                    }
                }
                features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features
        }

    def clear_cache(self, data_id: str = None):
        with self._lock:
            if data_id:
                self._graph_cache.pop(data_id, None)
                self._map_cache.pop(data_id, None)
                self._chart_cache.pop(data_id, None)
            else:
                self._graph_cache.clear()
                self._map_cache.clear()
                self._chart_cache.clear()

    def register_render_callback(self, callback: Callable):
        self._render_callbacks.append(callback)

    def get_cache_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "graph_count": len(self._graph_cache),
                "map_count": len(self._map_cache),
                "chart_count": len(self._chart_cache),
                "total_nodes": sum(len(g.nodes) for g in self._graph_cache.values()),
                "total_edges": sum(len(g.edges) for g in self._graph_cache.values()),
                "total_entities": sum(sum(len(l.entities) for l in m.layers)
                                     for m in self._map_cache.values())
            }


_global_viz_engine: Optional[VisualizationEngineV2] = None


def get_visualization_engine() -> VisualizationEngineV2:
    """获取全局可视化引擎"""
    global _global_viz_engine
    if _global_viz_engine is None:
        _global_viz_engine = VisualizationEngineV2()
    return _global_viz_engine


if __name__ == "__main__":
    engine = get_visualization_engine()

    print("=" * 60)
    print("可视化引擎测试")
    print("=" * 60)

    print("\n1. 创建图可视化:")
    entities = [
        {"id": "n1", "name": "雷达站A", "type": "radar", "properties": {}},
        {"id": "n2", "name": "指挥中心", "type": "command", "properties": {}},
        {"id": "n3", "name": "雷达站B", "type": "radar", "properties": {}},
        {"id": "n4", "name": "补给站", "type": "logistics", "properties": {}},
    ]
    relationships = [
        {"source": "n1", "target": "n2", "type": "connects"},
        {"source": "n3", "target": "n2", "type": "connects"},
        {"source": "n4", "target": "n2", "type": "supplies"},
    ]

    graph = engine.create_graph("test-graph", entities, relationships, GraphLayout.FORCE)
    print(f"   节点数: {len(graph.nodes)}")
    print(f"   边数: {len(graph.edges)}")

    print("\n2. 创建地图可视化:")
    map_entities = [
        {"id": "m1", "name": "目标A", "type": "target", "latitude": 39.9, "longitude": 116.4},
        {"id": "m2", "name": "友军B", "type": "friendly", "latitude": 39.95, "longitude": 116.45},
        {"id": "m3", "name": "敌军C", "type": "enemy", "latitude": 39.85, "longitude": 116.35},
    ]
    map_data = engine.create_map("test-map", map_entities)
    print(f"   图层数: {len(map_data.layers)}")
    print(f"   中心: ({map_data.center_lat:.2f}, {map_data.center_lon:.2f})")

    print("\n3. 创建图表:")
    stats = {
        "radar_count": 5,
        "command_count": 2,
        "threat_level": {"low": 10, "medium": 5, "high": 2}
    }
    chart = engine.create_chart("test-chart", stats, ChartType.BAR)
    print(f"   图表ID: {chart.chart_id}")
    print(f"   系列数: {len(chart.series)}")

    print("\n4. 转换为 ECharts 配置:")
    echarts_option = engine.to_echarts_option(chart)
    print(f"   标题: {echarts_option.get('title', {}).get('text')}")

    print("\n5. 转换为 GeoJSON:")
    geojson = engine.to_geojson(map_data)
    print(f"   Feature 数: {len(geojson.get('features', []))}")

    print("\n6. 缓存统计:")
    stats = engine.get_cache_statistics()
    print(f"   图数量: {stats['graph_count']}")
    print(f"   地图数量: {stats['map_count']}")
    print(f"   图表数量: {stats['chart_count']}")

    print("\n" + "=" * 60)
    print("可视化引擎测试完成")
    print("=" * 60)
