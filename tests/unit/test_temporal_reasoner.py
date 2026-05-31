import pytest
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.data.qa.impl.temporal_reasoner import TemporalReasoner
from odap.biz.data.qa.impl.chart_renderer import ChartRenderer, ChartType, RenderMode


class TestTemporalReasonerParsing:
    def test_parse_specific_date(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("2024年3月1日的状态是什么？", None)
        assert result["time_type"] == "specific_date"
        assert result["valid_time"] is not None
        assert "2024" in result["valid_time"]

    def test_parse_specific_month(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("2024年3月的情况", None)
        assert result["time_type"] == "specific_month"
        assert result["valid_time"] is not None

    def test_parse_specific_year(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("2024年的数据", None)
        assert result["time_type"] == "specific_year"
        assert result["valid_time"] is not None

    def test_parse_last_week(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("上周的情况", None)
        assert result["time_type"] == "last_week"
        assert result["valid_time"] is not None

    def test_parse_this_week(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("这周的情况", None)
        assert result["time_type"] == "this_week"
        assert result["valid_time"] is not None

    def test_parse_last_month(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("上个月的情况", None)
        assert result["time_type"] == "last_month"
        assert result["valid_time"] is not None

    def test_parse_yesterday(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("昨天的数据", None)
        assert result["time_type"] == "yesterday"
        assert result["valid_time"] is not None

    def test_parse_now(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("当前的状态", None)
        assert result["time_type"] == "now"
        assert result["valid_time"] is not None

    def test_parse_hours_ago(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("3小时前的数据", None)
        assert result["time_type"] == "hours_ago"
        assert result["valid_time"] is not None

    def test_parse_days_ago(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("5天前的情况", None)
        assert result["time_type"] == "days_ago"
        assert result["valid_time"] is not None

    def test_parse_event_time(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("事件发生时的状态", None)
        assert result["time_type"] == "event_time"

    def test_parse_explicit_valid_time(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("某个问题", "2024-01-01T00:00:00Z")
        assert result["time_type"] == "explicit"
        assert result["valid_time"] == "2024-01-01T00:00:00Z"

    def test_parse_no_time_expression(self):
        reasoner = TemporalReasoner()
        result = reasoner._parse_temporal_question("普通问题", None)
        assert result["valid_time"] is None


class TestTemporalReasonerAnswer:
    def test_answer_no_graphiti(self):
        reasoner = TemporalReasoner(graphiti_client=None)
        result = reasoner.answer_temporal_question(
            question="2024年3月1日的状态",
            valid_time=None,
        )
        assert result["status"] == "success"
        assert "answer" in result
        assert result["entity_count"] == 0

    def test_answer_no_time_parsed(self):
        reasoner = TemporalReasoner(graphiti_client=None)
        result = reasoner.answer_temporal_question(
            question="普通问题没有时间",
            valid_time=None,
        )
        assert result["status"] == "error"
        assert "无法解析时间表达式" in result["message"]

    def test_answer_with_explicit_time(self):
        reasoner = TemporalReasoner(graphiti_client=None)
        result = reasoner.answer_temporal_question(
            question="状态是什么",
            valid_time="2024-01-01T00:00:00Z",
        )
        assert result["status"] == "success"
        assert result["valid_time"] == "2024-01-01T00:00:00Z"

    def test_generate_temporal_answer_no_entities(self):
        reasoner = TemporalReasoner(graphiti_client=None)
        answer = reasoner._generate_temporal_answer(
            question="测试问题",
            parsed={"valid_time": "2024-01-01T00:00:00Z", "time_type": "explicit", "match_text": "2024-01-01"},
            entities=[],
        )
        assert "未找到" in answer

    def test_generate_temporal_answer_with_entities(self):
        reasoner = TemporalReasoner(graphiti_client=None)
        entities = [
            {"id": "e1", "properties": {"name": "实体A", "type": "Unit", "status": "active"}},
            {"id": "e2", "properties": {"name": "实体B", "entity_type": "Location"}},
        ]
        answer = reasoner._generate_temporal_answer(
            question="测试问题",
            parsed={"valid_time": "2024-01-01T00:00:00Z", "time_type": "explicit", "match_text": "2024-01-01"},
            entities=entities,
        )
        assert "2 条相关记录" in answer
        assert "实体A" in answer


class TestChartRenderer:
    def test_render_line_chart(self):
        renderer = ChartRenderer()
        result = renderer.render(
            chart_type="line",
            data={"categories": ["A", "B", "C"], "values": [10, 20, 30]},
            title="测试折线图",
        )
        assert result["status"] == "success"
        assert result["chart_type"] == "line"
        assert result["render_mode"] == "frontend"
        assert "spec" in result
        assert result["spec"]["type"] == "line"

    def test_render_bar_chart(self):
        renderer = ChartRenderer()
        result = renderer.render(
            chart_type="bar",
            data={"categories": ["X", "Y"], "values": [5, 15]},
            title="柱状图",
        )
        assert result["status"] == "success"
        assert result["chart_type"] == "bar"
        assert result["spec"]["type"] == "bar"

    def test_render_pie_chart(self):
        renderer = ChartRenderer()
        result = renderer.render(
            chart_type="pie",
            data={"items": [{"name": "A", "value": 30}, {"name": "B", "value": 70}]},
            title="饼图",
        )
        assert result["status"] == "success"
        assert result["chart_type"] == "pie"
        assert result["spec"]["type"] == "pie"

    def test_render_scatter_chart(self):
        renderer = ChartRenderer()
        result = renderer.render(
            chart_type="scatter",
            data={"points": [[1, 2], [3, 4], [5, 6]]},
        )
        assert result["status"] == "success"
        assert result["chart_type"] == "scatter"

    def test_render_heatmap_chart(self):
        renderer = ChartRenderer()
        result = renderer.render(
            chart_type="heatmap",
            data={"matrix": [[1, 2], [3, 4]], "x_labels": ["A", "B"], "y_labels": ["X", "Y"]},
        )
        assert result["status"] == "success"
        assert result["chart_type"] == "heatmap"
        assert result["render_mode"] == "backend"

    def test_render_radar_chart(self):
        renderer = ChartRenderer()
        result = renderer.render(
            chart_type="radar",
            data={"indicators": [{"name": "A", "max": 100}, {"name": "B", "max": 100}], "values": [80, 60]},
        )
        assert result["status"] == "success"
        assert result["chart_type"] == "radar"

    def test_render_map_chart(self):
        renderer = ChartRenderer()
        result = renderer.render(
            chart_type="map",
            data={"points": [{"lat": 39.9, "lng": 116.4, "name": "Beijing"}], "center": [116.4, 39.9]},
        )
        assert result["status"] == "success"
        assert result["chart_type"] == "map"

    def test_render_network_chart(self):
        renderer = ChartRenderer()
        result = renderer.render(
            chart_type="network",
            data={"nodes": [{"id": "1", "label": "A"}], "edges": [{"source": "1", "target": "2"}]},
        )
        assert result["status"] == "success"
        assert result["chart_type"] == "network"

    def test_render_unsupported_chart(self):
        renderer = ChartRenderer()
        result = renderer.render(
            chart_type="unsupported",
            data={},
        )
        assert result["status"] == "error"
        assert "不支持" in result["message"]

    def test_render_with_explicit_mode(self):
        renderer = ChartRenderer()
        result = renderer.render(
            chart_type="line",
            data={"values": [1, 2, 3]},
            render_mode="backend",
        )
        assert result["render_mode"] == "backend"

    def test_render_line_with_series_records(self):
        renderer = ChartRenderer()
        data = {
            "values": [
                {"x": "Jan", "y": 10, "series": "A"},
                {"x": "Feb", "y": 20, "series": "A"},
                {"x": "Jan", "y": 15, "series": "B"},
            ],
        }
        result = renderer.render(
            chart_type="line",
            data=data,
            options={"x_field": "x", "y_field": "y", "series_field": "series"},
        )
        assert result["status"] == "success"
        assert len(result["spec"]["series"]) == 2

    def test_chart_type_enum(self):
        assert ChartType.LINE.value == "line"
        assert ChartType.BAR.value == "bar"
        assert ChartType.PIE.value == "pie"
        assert ChartType.SCATTER.value == "scatter"
        assert ChartType.HEATMAP.value == "heatmap"
        assert ChartType.RADAR.value == "radar"
        assert ChartType.MAP.value == "map"
        assert ChartType.NETWORK.value == "network"

    def test_render_mode_enum(self):
        assert RenderMode.FRONTEND.value == "frontend"
        assert RenderMode.BACKEND.value == "backend"
