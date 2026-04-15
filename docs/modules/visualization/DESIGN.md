# Visualization 可视化模块设计文档

> **优先级**: P1 | **相关 ADR**: ADR-007, ADR-015

## 1. 模块概述

### 1.1 模块定位

`visualization` 负责领域态势的可视化展示，包括地图渲染、关系图谱、时间线、图表等。

### 1.2 可视化类型

| 类型 | 用途 | 技术栈 |
|------|------|--------|
| 领域地图 | 态势概览 | ECharts + CesiumJS |
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
    BATTLEFIELD_MAP = "domain_map"
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

    async def render_domain_map(
        self,
        targets: List[Dict],
        units: List[Dict],
        options: Dict[str, Any]
    ) -> str:
        """渲染领域地图"""
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

### 3.1 领域地图

```python
# visualization/domain_map.py
import json

class DomainMapRenderer:
    """领域地图渲染器"""

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
                "map": "domain",
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

### 4.1 领域态势 HTML

```html
<!-- visualization/templates/domain_map.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Domain Situation</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts"></script>
    <style>
        #domain { width: 100%; height: 800px; }
    </style>
</head>
<body>
    <div id="domain"></div>
    <script>
        const chart = echarts.init(document.getElementById('domain'));
        chart.setOption({{ chart_config | safe }});
    </script>
</body>
</html>
```

---

## 5. 模拟推演可视化增强

### 5.1 模拟推演可视化类型

```python
class SimulationVisualizationType(str, Enum):
    """模拟推演可视化类型"""
    SCENARIO_COMPARISON = "scenario_comparison"      # 方案对比
    PARAMETER_SENSITIVITY = "parameter_sensitivity"  # 参数敏感性分析
    WHAT_IF_ANALYSIS = "what_if_analysis"           # What-if分析
    VERSION_TIMELINE = "version_timeline"           # 版本时间线
    PERFORMANCE_DASHBOARD = "performance_dashboard" # 性能看板
    REAL_TIME_SIMULATION = "real_time_simulation"   # 实时推演
```

### 5.2 方案对比可视化

```python
# visualization/simulation_comparison.py

class SimulationComparisonVisualizer:
    """
    模拟方案对比可视化器
    """
    
    def render_comparison_dashboard(
        self,
        scenarios: List[Dict[str, Any]],
        comparison_metrics: List[str]
    ) -> Dict[str, Any]:
        """
        渲染方案对比看板
        """
        # 1. 指标对比雷达图
        radar_chart = self._render_radar_comparison(scenarios, comparison_metrics)
        
        # 2. 参数差异热力图
        heatmap = self._render_parameter_heatmap(scenarios)
        
        # 3. 结果对比柱状图
        bar_chart = self._render_metric_bars(scenarios, comparison_metrics)
        
        # 4. 时间线对比
        timeline = self._render_version_timeline(scenarios)
        
        return {
            "dashboard": {
                "radar_chart": radar_chart,
                "heatmap": heatmap,
                "bar_chart": bar_chart,
                "timeline": timeline
            },
            "interactive": {
                "drilldown": True,
                "filtering": True,
                "highlighting": True
            }
        }
    
    def _render_radar_comparison(
        self,
        scenarios: List[Dict[str, Any]],
        metrics: List[str]
    ) -> Dict[str, Any]:
        """
        渲染雷达图对比
        """
        series_data = []
        
        for scenario in scenarios:
            metric_values = [
                scenario.get("metrics", {}).get(metric, 0)
                for metric in metrics
            ]
            
            series_data.append({
                "name": scenario["name"],
                "value": metric_values,
                "itemStyle": {
                    "color": self._get_scenario_color(scenario["id"])
                }
            })
        
        return {
            "type": "radar",
            "indicator": [
                {"name": metric, "max": self._get_metric_max(metric)}
                for metric in metrics
            ],
            "series": series_data
        }
    
    def _render_parameter_heatmap(
        self,
        scenarios: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        渲染参数差异热力图
        """
        # 提取所有参数
        all_params = set()
        for scenario in scenarios:
            all_params.update(scenario.get("parameters", {}).keys())
        
        # 构建参数矩阵
        data = []
        for param in sorted(all_params):
            row = []
            for scenario in scenarios:
                value = scenario.get("parameters", {}).get(param)
                row.append(self._normalize_parameter_value(value))
            data.append(row)
        
        return {
            "type": "heatmap",
            "xAxis": {"data": [s["name"] for s in scenarios]},
            "yAxis": {"data": list(sorted(all_params))},
            "data": data,
            "visualMap": {
                "min": 0,
                "max": 1,
                "calculable": True,
                "orient": "horizontal",
                "left": "center",
                "bottom": "10%"
            }
        }
```

### 5.3 实时推演可视化

```python
# visualization/realtime_simulation.py

class RealTimeSimulationVisualizer:
    """
    实时推演可视化器 - 支持WebSocket实时更新
    """
    
    def __init__(self, websocket_manager):
        self.ws_manager = websocket_manager
        self.simulation_states = {}
        
    async def start_realtime_visualization(
        self,
        simulation_id: str,
        client_ws
    ):
        """
        启动实时可视化流
        """
        # 注册客户端
        await self.ws_manager.register_client(simulation_id, client_ws)
        
        # 开始推送数据
        try:
            async for update in self._get_simulation_updates(simulation_id):
                # 生成可视化更新
                viz_update = await self._generate_visualization_update(update)
                
                # 推送到客户端
                await self.ws_manager.send_update(
                    simulation_id,
                    client_ws,
                    viz_update
                )
        finally:
            await self.ws_manager.unregister_client(simulation_id, client_ws)
    
    async def _generate_visualization_update(
        self,
        simulation_update: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成可视化更新
        """
        update_type = simulation_update.get("type")
        
        if update_type == "entity_movement":
            return await self._render_entity_movement(simulation_update)
        elif update_type == "event_occurrence":
            return await self._render_event_occurrence(simulation_update)
        elif update_type == "metric_update":
            return await self._render_metric_update(simulation_update)
        elif update_type == "state_change":
            return await self._render_state_change(simulation_update)
        else:
            return {"type": "raw", "data": simulation_update}
    
    async def _render_entity_movement(
        self,
        movement_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        渲染实体移动动画
        """
        return {
            "type": "entity_movement",
            "animation": {
                "from": movement_data["from_position"],
                "to": movement_data["to_position"],
                "duration": 1000,  # 1秒动画
                "easing": "cubicOut"
            },
            "entity": {
                "id": movement_data["entity_id"],
                "type": movement_data["entity_type"],
                "icon": self._get_entity_icon(movement_data["entity_type"])
            }
        }
    
    async def _render_metric_update(
        self,
        metric_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        渲染指标更新
        """
        return {
            "type": "metric_update",
            "metrics": [
                {
                    "name": metric["name"],
                    "value": metric["value"],
                    "trend": metric.get("trend", "stable"),
                    "threshold": metric.get("threshold"),
                    "alarm": metric.get("alarm", False)
                }
                for metric in metric_data["metrics"]
            ],
            "timestamp": metric_data["timestamp"]
        }
```

### 5.4 What-if分析可视化

```python
# visualization/what_if_analysis.py

class WhatIfAnalysisVisualizer:
    """
    What-if分析可视化器
    """
    
    def render_what_if_analysis(
        self,
        base_scenario: Dict[str, Any],
        what_if_scenarios: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        渲染What-if分析可视化
        """
        # 1. 参数变化影响图
        impact_chart = self._render_parameter_impact(
            base_scenario,
            what_if_scenarios
        )
        
        # 2. 敏感性分析图
        sensitivity_chart = self._render_sensitivity_analysis(
            base_scenario,
            what_if_scenarios
        )
        
        # 3. 趋势预测图
        trend_chart = self._render_trend_prediction(what_if_scenarios)
        
        # 4. 推荐方案图
        recommendation_chart = self._render_recommendations(
            base_scenario,
            what_if_scenarios
        )
        
        return {
            "what_if_analysis": {
                "impact_chart": impact_chart,
                "sensitivity_chart": sensitivity_chart,
                "trend_chart": trend_chart,
                "recommendation_chart": recommendation_chart
            }
        }
    
    def _render_parameter_impact(
        self,
        base_scenario: Dict[str, Any],
        what_if_scenarios: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        渲染参数变化影响图
        """
        # 计算每个参数变化的影响
        impacts = []
        
        for scenario in what_if_scenarios:
            param_changes = self._extract_parameter_changes(
                base_scenario,
                scenario
            )
            
            for param, change in param_changes.items():
                metric_change = self._calculate_metric_change(
                    base_scenario["metrics"],
                    scenario["metrics"]
                )
                
                impacts.append({
                    "parameter": param,
                    "change": change,
                    "metric_impact": metric_change,
                    "scenario_name": scenario["name"]
                })
        
        # 生成散点图
        scatter_data = [
            {
                "name": impact["scenario_name"],
                "value": [impact["change"], impact["metric_impact"]],
                "parameter": impact["parameter"]
            }
            for impact in impacts
        ]
        
        return {
            "type": "scatter",
            "title": "参数变化对指标的影响",
            "xAxis": {"name": "参数变化量"},
            "yAxis": {"name": "指标变化量"},
            "series": scatter_data,
            "visualMap": {
                "dimension": 2,
                "min": 0,
                "max": len(set(i["parameter"] for i in impacts)),
                "inRange": {"color": ["#313695", "#4575b4", "#74add1", "#abd9e9", "#fee090", "#fdae61", "#f46d43", "#d73027"]}
            }
        }
    
    def _render_sensitivity_analysis(
        self,
        base_scenario: Dict[str, Any],
        what_if_scenarios: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        渲染敏感性分析图
        """
        # 计算每个参数的敏感性系数
        sensitivity_coefficients = self._calculate_sensitivity_coefficients(
            base_scenario,
            what_if_scenarios
        )
        
        # 生成条形图
        bar_data = [
            {
                "name": param,
                "value": coefficient,
                "itemStyle": {
                    "color": self._get_sensitivity_color(coefficient)
                }
            }
            for param, coefficient in sensitivity_coefficients.items()
        ]
        
        return {
            "type": "bar",
            "title": "参数敏感性分析",
            "xAxis": {"data": list(sensitivity_coefficients.keys())},
            "yAxis": {"name": "敏感性系数"},
            "series": [{
                "data": bar_data,
                "type": "bar",
                "label": {"show": True, "position": "top"}
            }]
        }
```

### 5.5 Web界面集成

```html
<!-- visualization/templates/simulation_dashboard.html -->
<!DOCTYPE html>
<html>
<head>
    <title>模拟推演可视化看板</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts"></script>
    <script src="https://cdn.jsdelivr.net/npm/socket.io-client"></script>
    <style>
        .dashboard-container {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            grid-gap: 20px;
            padding: 20px;
        }
        .dashboard-panel {
            background: #1e1e2e;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .panel-title {
            color: #fff;
            margin-bottom: 15px;
            font-size: 16px;
            font-weight: bold;
        }
        .chart-container {
            height: 300px;
        }
        #realtime-simulation {
            grid-column: span 2;
            height: 500px;
        }
        .control-panel {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        .control-button {
            background: #3498db;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 5px;
            cursor: pointer;
        }
        .control-button:hover {
            background: #2980b9;
        }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- 实时推演面板 -->
        <div class="dashboard-panel" id="realtime-simulation">
            <div class="panel-title">实时推演可视化</div>
            <div class="control-panel">
                <button class="control-button" onclick="startSimulation()">开始推演</button>
                <button class="control-button" onclick="pauseSimulation()">暂停</button>
                <button class="control-button" onclick="resetSimulation()">重置</button>
                <select id="speedControl" onchange="changeSpeed(this.value)">
                    <option value="1">1x 速度</option>
                    <option value="2">2x 速度</option>
                    <option value="5" selected>5x 速度</option>
                    <option value="10">10x 速度</option>
                </select>
            </div>
            <div id="realtime-chart" class="chart-container"></div>
        </div>
        
        <!-- 方案对比面板 -->
        <div class="dashboard-panel">
            <div class="panel-title">方案对比分析</div>
            <div id="comparison-chart" class="chart-container"></div>
        </div>
        
        <!-- What-if分析面板 -->
        <div class="dashboard-panel">
            <div class="panel-title">What-if分析</div>
            <div id="whatif-chart" class="chart-container"></div>
        </div>
        
        <!-- 参数敏感性面板 -->
        <div class="dashboard-panel">
            <div class="panel-title">参数敏感性分析</div>
            <div id="sensitivity-chart" class="chart-container"></div>
        </div>
        
        <!-- 版本时间线面板 -->
        <div class="dashboard-panel">
            <div class="panel-title">版本演变时间线</div>
            <div id="timeline-chart" class="chart-container"></div>
        </div>
        
        <!-- 性能指标面板 -->
        <div class="dashboard-panel">
            <div class="panel-title">推演性能指标</div>
            <div id="performance-chart" class="chart-container"></div>
        </div>
    </div>
    
    <script>
        // WebSocket连接
        const socket = io('http://localhost:8000/simulation');
        const charts = {};
        
        // 初始化图表
        function initCharts() {
            charts.comparison = echarts.init(document.getElementById('comparison-chart'));
            charts.whatif = echarts.init(document.getElementById('whatif-chart'));
            charts.sensitivity = echarts.init(document.getElementById('sensitivity-chart'));
            charts.timeline = echarts.init(document.getElementById('timeline-chart'));
            charts.performance = echarts.init(document.getElementById('performance-chart'));
            charts.realtime = echarts.init(document.getElementById('realtime-chart'));
        }
        
        // WebSocket消息处理
        socket.on('simulation_update', function(data) {
            handleSimulationUpdate(data);
        });
        
        socket.on('visualization_update', function(data) {
            updateVisualization(data);
        });
        
        // 处理模拟更新
        function handleSimulationUpdate(data) {
            const updateType = data.type;
            
            switch(updateType) {
                case 'entity_movement':
                    updateEntityMovement(data);
                    break;
                case 'metric_update':
                    updateMetrics(data);
                    break;
                case 'event_occurrence':
                    logEvent(data);
                    break;
                default:
                    console.log('Unknown update type:', updateType);
            }
        }
        
        // 更新实体移动
        function updateEntityMovement(data) {
            // 在地图上显示实体移动动画
            const animation = data.animation;
            const entity = data.entity;
            
            // 更新地图上的实体位置
            updateMapEntity(entity.id, {
                position: animation.to,
                icon: entity.icon
            });
            
            // 播放移动动画
            animateEntity(entity.id, animation);
        }
        
        // 更新指标
        function updateMetrics(data) {
            // 更新性能指标图表
            charts.performance.setOption({
                series: [{
                    type: 'gauge',
                    data: data.metrics.map(m => ({
                        name: m.name,
                        value: m.value
                    }))
                }]
            });
            
            // 检查告警
            data.metrics.forEach(metric => {
                if (metric.alarm) {
                    showAlert(metric.name, metric.value);
                }
            });
        }
        
        // 模拟控制函数
        function startSimulation() {
            socket.emit('start_simulation', {
                scenario_id: getCurrentScenarioId()
            });
        }
        
        function pauseSimulation() {
            socket.emit('pause_simulation');
        }
        
        function resetSimulation() {
            socket.emit('reset_simulation');
        }
        
        function changeSpeed(speed) {
            socket.emit('change_speed', { speed: parseInt(speed) });
        }
        
        // 页面加载
        window.onload = function() {
            initCharts();
            loadInitialData();
        };
        
        function loadInitialData() {
            // 加载初始数据
            fetch('/api/simulation/initial_data')
                .then(response => response.json())
                .then(data => {
                    // 初始化各个图表
                    initComparisonChart(data.comparison);
                    initWhatIfChart(data.whatif);
                    initSensitivityChart(data.sensitivity);
                    initTimelineChart(data.timeline);
                });
        }
    </script>
</body>
</html>
```

### 5.6 模拟推演可视化配置

```yaml
# config/visualization_simulation.yaml
simulation_visualization:
  # 实时推演配置
  realtime:
    update_frequency: 100  # 更新频率(ms)
    animation_duration: 1000  # 动画时长(ms)
    max_data_points: 1000  # 最大数据点数
    
  # 方案对比配置
  comparison:
    radar_metrics:  # 雷达图展示的指标
      - "mission_success"
      - "risk_level"
      - "resource_efficiency"
      - "decision_quality"
      - "response_time"
    chart_types:  # 对比图表类型
      - "radar"
      - "bar"
      - "heatmap"
      - "scatter"
    
  # What-if分析配置
  what_if:
    sensitivity_analysis: true
    trend_prediction: true
    impact_visualization: true
    parameter_ranges:  # 参数范围
      risk_tolerance: [0, 100]
      resource_allocation: [0, 1]
      time_limit: [60, 3600]
    
  # 版本管理可视化
  versioning:
    timeline_visualization: true
    diff_visualization: true
    change_impact_analysis: true
    
  # 性能监控
  performance:
    metrics_dashboard: true
    resource_monitoring: true
    alert_visualization: true
    
  # 交互功能
  interaction:
    drilldown: true  # 下钻分析
    filtering: true  # 数据筛选
    highlighting: true  # 高亮显示
    annotation: true  # 标注功能
    export: true  # 导出功能
```

---

## 6. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
| 1.1.0 | 2026-04-12 | 新增模拟推演可视化增强，包括实时推演、方案对比、What-if分析等高级功能 |

---

**相关文档**:
- [Graphiti 客户端模块设计](../graphiti_client/DESIGN.md)
- [Ontology 本体管理层设计](../ontology/DESIGN.md)
- [Decision Recommendation 决策推荐模块设计](../decision_recommendation/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)
