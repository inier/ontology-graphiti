import logging
import math
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ChartType(str, Enum):
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    RADAR = "radar"
    MAP = "map"
    NETWORK = "network"


class RenderMode(str, Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"


class ChartRenderer:
    FRONTEND_TYPES = {
        ChartType.LINE, ChartType.BAR, ChartType.PIE,
        ChartType.SCATTER, ChartType.RADAR, ChartType.MAP,
        ChartType.NETWORK,
    }
    BACKEND_TYPES = {ChartType.HEATMAP}

    def render(
        self,
        chart_type: str,
        data: Dict[str, Any],
        title: str = "",
        render_mode: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            ct = ChartType(chart_type)
        except ValueError:
            return {
                "status": "error",
                "message": f"不支持的图表类型: {chart_type}",
                "supported_types": [t.value for t in ChartType],
            }

        mode = self._determine_render_mode(ct, render_mode)

        spec = self._generate_spec(ct, data, title, options or {})

        return {
            "status": "success",
            "chart_type": ct.value,
            "render_mode": mode.value,
            "title": title,
            "spec": spec,
        }

    def _determine_render_mode(self, chart_type: ChartType, render_mode: Optional[str]) -> RenderMode:
        if render_mode:
            try:
                return RenderMode(render_mode)
            except ValueError:
                pass
        if chart_type in self.BACKEND_TYPES:
            return RenderMode.BACKEND
        return RenderMode.FRONTEND

    def _generate_spec(
        self,
        chart_type: ChartType,
        data: Dict[str, Any],
        title: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        generators = {
            ChartType.LINE: self._spec_line,
            ChartType.BAR: self._spec_bar,
            ChartType.PIE: self._spec_pie,
            ChartType.SCATTER: self._spec_scatter,
            ChartType.HEATMAP: self._spec_heatmap,
            ChartType.RADAR: self._spec_radar,
            ChartType.MAP: self._spec_map,
            ChartType.NETWORK: self._spec_network,
        }
        generator = generators.get(chart_type)
        if generator:
            return generator(data, title, options)
        return {}

    def _spec_line(self, data: Dict[str, Any], title: str, options: Dict[str, Any]) -> Dict[str, Any]:
        x_field = options.get("x_field", "x")
        y_field = options.get("y_field", "y")
        series_field = options.get("series_field")

        series_data = data.get("series", [])
        if not series_data and "values" in data:
            values = data["values"]
            if isinstance(values, list) and values and isinstance(values[0], (int, float)):
                series_data = [{"data": values}]
            elif isinstance(values, list) and values and isinstance(values[0], dict):
                series_data = self._extract_series(values, x_field, y_field, series_field)

        return {
            "type": "line",
            "title": {"text": title},
            "xAxis": {"type": "category", "data": data.get("categories", [])},
            "yAxis": {"type": "value"},
            "series": series_data if series_data else [{"type": "line", "data": data.get("values", [])}],
            "tooltip": {"trigger": "axis"},
            "legend": {"show": len(series_data) > 1},
        }

    def _spec_bar(self, data: Dict[str, Any], title: str, options: Dict[str, Any]) -> Dict[str, Any]:
        categories = data.get("categories", [])
        values = data.get("values", [])
        series_data = data.get("series", [])

        if not series_data and values:
            series_data = [{"type": "bar", "data": values}]

        return {
            "type": "bar",
            "title": {"text": title},
            "xAxis": {"type": "category", "data": categories},
            "yAxis": {"type": "value"},
            "series": series_data if series_data else [{"type": "bar", "data": []}],
            "tooltip": {"trigger": "axis"},
        }

    def _spec_pie(self, data: Dict[str, Any], title: str, options: Dict[str, Any]) -> Dict[str, Any]:
        items = data.get("items", [])
        if not items and "values" in data:
            categories = data.get("categories", [])
            values = data.get("values", [])
            items = [{"name": c, "value": v} for c, v in zip(categories, values)]

        return {
            "type": "pie",
            "title": {"text": title},
            "series": [{
                "type": "pie",
                "radius": options.get("radius", "60%"),
                "data": items,
                "label": {"show": True},
            }],
            "tooltip": {"trigger": "item"},
        }

    def _spec_scatter(self, data: Dict[str, Any], title: str, options: Dict[str, Any]) -> Dict[str, Any]:
        points = data.get("points", [])
        if not points and "values" in data:
            values = data.get("values", [])
            points = [[i, v] for i, v in enumerate(values)]

        return {
            "type": "scatter",
            "title": {"text": title},
            "xAxis": {"type": "value"},
            "yAxis": {"type": "value"},
            "series": [{"type": "scatter", "data": points, "symbolSize": options.get("symbolSize", 8)}],
            "tooltip": {"trigger": "item"},
        }

    def _spec_heatmap(self, data: Dict[str, Any], title: str, options: Dict[str, Any]) -> Dict[str, Any]:
        matrix = data.get("matrix", [])
        x_labels = data.get("x_labels", [])
        y_labels = data.get("y_labels", [])

        flat_data = []
        for y_idx, row in enumerate(matrix):
            for x_idx, val in enumerate(row):
                flat_data.append([x_idx, y_idx, val])

        return {
            "type": "heatmap",
            "title": {"text": title},
            "xAxis": {"type": "category", "data": x_labels},
            "yAxis": {"type": "category", "data": y_labels},
            "visualMap": {
                "min": data.get("min_val", 0),
                "max": data.get("max_val", 100),
                "calculable": True,
                "orient": "horizontal",
                "left": "center",
                "bottom": 0,
            },
            "series": [{"type": "heatmap", "data": flat_data, "emphasis": {"itemStyle": {"shadowBlur": 10}}}],
        }

    def _spec_radar(self, data: Dict[str, Any], title: str, options: Dict[str, Any]) -> Dict[str, Any]:
        indicators = data.get("indicators", [])
        values = data.get("values", [])

        if not indicators and "categories" in data:
            categories = data["categories"]
            max_val = data.get("max_val", 100)
            indicators = [{"name": c, "max": max_val} for c in categories]

        series_data = []
        if values:
            if isinstance(values[0], list):
                for i, v in enumerate(values):
                    series_data.append({"value": v, "name": f"Series {i + 1}"})
            else:
                series_data.append({"value": values, "name": title or "Data"})

        return {
            "type": "radar",
            "title": {"text": title},
            "radar": {"indicator": indicators},
            "series": [{"type": "radar", "data": series_data}],
        }

    def _spec_map(self, data: Dict[str, Any], title: str, options: Dict[str, Any]) -> Dict[str, Any]:
        points = data.get("points", [])
        center = data.get("center", [116.4, 39.9])
        zoom = data.get("zoom", 5)

        return {
            "type": "map",
            "title": {"text": title},
            "center": center,
            "zoom": zoom,
            "points": points,
            "mapStyle": options.get("mapStyle", "standard"),
        }

    def _spec_network(self, data: Dict[str, Any], title: str, options: Dict[str, Any]) -> Dict[str, Any]:
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        if not nodes and "entities" in data:
            nodes = [
                {
                    "id": e.get("id", str(i)),
                    "label": e.get("name", e.get("id", f"node_{i}")),
                    "type": e.get("type", e.get("entity_type", "default")),
                }
                for i, e in enumerate(data["entities"])
            ]

        if not edges and "relations" in data:
            edges = [
                {
                    "source": r.get("source", r.get("source_id", "")),
                    "target": r.get("target", r.get("target_id", "")),
                    "label": r.get("type", r.get("relation_type", "")),
                }
                for r in data["relations"]
            ]

        return {
            "type": "network",
            "title": {"text": title},
            "nodes": nodes,
            "edges": edges,
            "layout": options.get("layout", "force"),
            "nodeSize": options.get("nodeSize", 20),
        }

    def _extract_series(
        self,
        records: List[Dict[str, Any]],
        x_field: str,
        y_field: str,
        series_field: Optional[str],
    ) -> List[Dict[str, Any]]:
        if not series_field:
            data_points = [[r.get(x_field, i), r.get(y_field, 0)] for i, r in enumerate(records)]
            return [{"type": "line", "data": data_points}]

        series_map: Dict[str, List] = {}
        for r in records:
            sname = str(r.get(series_field, "default"))
            if sname not in series_map:
                series_map[sname] = []
            series_map[sname].append([r.get(x_field, 0), r.get(y_field, 0)])

        return [
            {"type": "line", "name": name, "data": points}
            for name, points in series_map.items()
        ]
