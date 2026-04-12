# Visualization 可视化模块设计文档

## 1. 模块概述

### 1.1 模块定位

`visualization` 负责战场态势的可视化展示，包括地图渲染、关系图谱、时间线、图表等。

### 1.2 可视化类型

| 类型 | 用途 | 技术栈 |
|------|------|--------|
| 战场地图 | 态势概览 | ECharts + CesiumJS |
| 关系图谱 | 知识图谱展示 | AntV G6 |
| 时间线 | 时序事件展示 | ECharts |
| 态势图表 | 数据统计 | Plotly + Matplotlib |

---

## 2. 接口设计

### 2.1 可视化服务

```python
# visualization/visualizer.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

class VisualizationType(str, Enum):
    """可视化类型"""
    BATTLEFIELD_MAP = "battlefield_map"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    TIMELINE = "timeline"
    BAR_CHART = "bar_chart"
    LINE_CHART = "line_chart"
    HEATMAP = "heatmap"

class VisualizerService:
    """可视化服务"""

    async def render(
        self,
        viz_type: VisualizationType,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """渲染可视化"""
        pass

    async def render_battlefield_map(
        self,
        targets: List[Dict],
        units: List[Dict],
        options: Dict[str, Any]
    ) -> str:
        """渲染战场地图"""
        pass

    async def render_knowledge_graph(
        self,
        entities: List[Dict],
        relations: List[Dict]
    ) -> str:
        """渲染知识图谱"""
        pass

    async def render_timeline(
        self,
        events: List[Dict],
        time_range: tuple[datetime, datetime]
    ) -> str:
        """渲染时间线"""
        pass
```

---

## 3. 核心实现

### 3.1 战场地图

```python
# visualization/battlefield_map.py
import json

class BattlefieldMapRenderer:
    """战场地图渲染器"""

    def render(
        self,
        targets: List[Dict],
        units: List[Dict],
        options: Dict[str, Any]
    ) -> str:
        """生成 ECharts 配置"""

        # 目标标记
        target_series = {
            "name": "Targets",
            "type": "scatter",
            "coordinateSystem": "geo",
            "symbolSize": lambda params: self._get_symbol_size(params),
            "itemStyle": {
                "color": lambda params: self._get_target_color(params)
            },
            "data": [
                {
                    "name": t["name"],
                    "value": [t["location"]["lon"], t["location"]["lat"], t["threat_level"]]
                }
                for t in targets
            ],
            "label": {
                "show": options.get("show_labels", True),
                "formatter": "{b}"
            }
        }

        # 友军单元
        friendly_series = {
            "name": "Friendly Units",
            "type": "scatter",
            "symbol": "path://M...",
            "data": [self._unit_to_point(u) for u in units if u.get("affiliation") == "friendly"]
        }

        # 敌军单元
        hostile_series = {
            "name": "Hostile Units",
            "type": "scatter",
            "data": [self._unit_to_point(u) for u in units if u.get("affiliation") == "hostile"]
        }

        return {
            "geo": {
                "map": "battlefield",
                " roam": True,
                "itemStyle": {"areaColor": "#1a1a2e"}
            },
            "series": [target_series, friendly_series, hostile_series]
        }

    def _get_symbol_size(self, params):
        threat_sizes = {"critical": 30, "high": 24, "medium": 18, "low": 12}
        return threat_sizes.get(params.value[2], 15)

    def _get_target_color(self, params):
        threat_colors = {
            "critical": "#ff0000",
            "high": "#ff6600",
            "medium": "#ffcc00",
            "low": "#00cc00"
        }
        return threat_colors.get(params.value[2], "#888888")
```

### 3.2 知识图谱

```python
# visualization/knowledge_graph.py

class KnowledgeGraphRenderer:
    """知识图谱渲染器"""

    def render(
        self,
        entities: List[Dict],
        relations: List[Dict]
    ) -> Dict[str, Any]:
        """生成 AntV G6 配置"""

        nodes = [
            {
                "id": e["id"],
                "label": e["name"],
                "type": e["category"],
                "style": self._get_node_style(e)
            }
            for e in entities
        ]

        edges = [
            {
                "source": r["source_id"],
                "target": r["target_id"],
                "label": r["relation_type"],
                "style": self._get_edge_style(r)
            }
            for r in relations
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "layout": {
                "type": "force",
                "preventOverlap": True,
                "nodeSpacing": 50
            }
        }

    def _get_node_style(self, entity):
        category_styles = {
            "target": {"fill": "#ff6b6b", "stroke": "#c92a2a"},
            "unit": {"fill": "#51cf66", "stroke": "#2b8a3e"},
            "intelligence": {"fill": "#339af0", "stroke": "#1864ab"},
            "strike_order": {"fill": "#fcc419", "stroke": "#e67700"}
        }
        return category_styles.get(entity.get("category"), {})

    def _get_edge_style(self, relation):
        relation_styles = {
            "ATTACKED_BY": {"stroke": "#ff0000", "lineDash": [5, 5]},
            "DETECTED_AT": {"stroke": "#339af0"},
            "EVIDENCE_FOR": {"stroke": "#fcc419", "lineDash": [2, 2]}
        }
        return relation_styles.get(relation.get("relation_type"), {})
```

---

## 4. HTML 模板

### 4.1 战场态势 HTML

```html
<!-- visualization/templates/battlefield_map.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Battlefield Situation</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts"></script>
    <style>
        #battlefield { width: 100%; height: 800px; }
    </style>
</head>
<body>
    <div id="battlefield"></div>
    <script>
        const chart = echarts.init(document.getElementById('battlefield'));
        chart.setOption({{ chart_config | safe }});
    </script>
</body>
</html>
```

---

## 5. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
