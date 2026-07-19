"""GenBITool — 自然语言 → 图表/报表。

集成 UnifiedRetrieveEngine，支持:
- NL → 指标查询 → 图表类型推荐 → 图表配置
- 结果包含溯源信息
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GenBIInput:
    """GenBI 输入"""
    def __init__(self, query: str, chart_hint: str = "", ontology_id: str = None, workspace_id: str = "default"):
        self.query = query
        self.chart_hint = chart_hint
        self.ontology_id = ontology_id
        self.workspace_id = workspace_id


class GenBITool:
    """GenBI — 自然语言生成商业智能图表"""

    CHART_TYPES = ["bar", "line", "pie", "scatter", "area", "radar", "table", "number"]

    async def execute(self, input_data: GenBIInput) -> Dict[str, Any]:
        query = input_data.query
        chart_hint = input_data.chart_hint

        # 1. 检索指标数据
        try:
            from odap.biz.core.ontology.reasoning.services.unified_retrieve import (
                RetrieveRequest, get_retrieve_engine,
            )
            engine = get_retrieve_engine()
            result = await engine.retrieve(RetrieveRequest(
                query=query,
                workspace_id=input_data.workspace_id,
                ontology_id=input_data.ontology_id,
                include_provenance=True,
                include_metrics=True,
                top_k=10,
            ))
            data_items = result.items
        except Exception as e:
            logger.warning("GenBI retrieval failed: %s", e)
            data_items = []

        # 2. 推荐图表类型
        chart_type = chart_hint if chart_hint in self.CHART_TYPES else self._recommend_chart(query, data_items)

        # 3. 构建图表配置
        chart_config = self._build_chart_config(chart_type, data_items, query)

        # 4. 溯源信息
        provenance_items = []
        for item in data_items:
            if item.get("provenance"):
                prov = item["provenance"]
                provenance_items.append({
                    "name": item.get("name", ""),
                    "source": prov.get("source", {}).get("document_name", ""),
                    "extraction_method": prov.get("extraction", {}).get("method", ""),
                })

        return {
            "status": "success",
            "chart_type": chart_type,
            "chart_config": chart_config,
            "data_items": data_items[:5],
            "provenance": provenance_items,
            "explanation": f"为查询 '{query[:50]}...' 推荐 {chart_type} 图表",
        }

    def _recommend_chart(self, query: str, items: list) -> str:
        """增强的图表类型推荐"""
        q = query.lower()
        item_count = len(items)
        
        # 单值 → 统计卡
        if item_count <= 1:
            return "number"
        
        # 关键词匹配
        if any(kw in q for kw in ("占比", "比例", "百分比", "份额", "分布", "构成")):
            return "pie"
        if any(kw in q for kw in ("趋势", "变化", "走势", "增长", "下降", "随时间")):
            return "line"
        if any(kw in q for kw in ("对比", "比较", "排名", "排行", "vs")):
            return "bar"
        if any(kw in q for kw in ("散点", "相关", "关联")):
            return "scatter"
        if any(kw in q for kw in ("多维", "雷达", "综合")):
            return "radar"
        if any(kw in q for kw in ("列表", "表格", "清单")):
            return "table"
        
        # 默认按数据量选择
        if item_count <= 5:
            return "pie"
        elif item_count <= 15:
            return "bar"
        else:
            return "line"

    def _build_chart_config(self, chart_type: str, items: list, query: str) -> dict:
        """构建完整的 ECharts/AntV 图表配置"""
        
        labels = [item.get("name", f"item-{i}") for i, item in enumerate(items)]
        values = []
        for item in items:
            raw = item.get("raw_data", {})
            val = raw.get("value", raw.get("count", item.get("score", 0)))
            if isinstance(val, str):
                try:
                    val = float(val)
                except ValueError:
                    val = 0
            values.append(val)

        # 基础配置
        config = {
            "title": {
                "text": f"查询: {query[:40]}{'...' if len(query) > 40 else ''}",
                "subtext": f"共 {len(items)} 条结果",
                "left": "center",
            },
            "tooltip": {
                "trigger": "axis" if chart_type in ("bar", "line", "area") else "item",
            },
            "legend": {
                "orient": "vertical",
                "left": "left",
                "data": labels[:5],
            } if chart_type in ("pie",) else {},
            "series": [],
        }

        series_name = query[:20]

        if chart_type == "bar":
            config["xAxis"] = {"type": "category", "data": labels, "axisLabel": {"rotate": 30}}
            config["yAxis"] = {"type": "value"}
            config["series"] = [{
                "name": series_name, "type": "bar",
                "data": [{"name": l, "value": v} for l, v in zip(labels, values)],
                "itemStyle": {"color": "#5470c6"},
            }]

        elif chart_type == "line":
            config["xAxis"] = {"type": "category", "data": labels, "axisLabel": {"rotate": 30}}
            config["yAxis"] = {"type": "value"}
            config["series"] = [{
                "name": series_name, "type": "line",
                "data": values,
                "smooth": True,
                "lineStyle": {"color": "#91cc75"},
                "areaStyle": {"color": "rgba(145,204,117,0.2)"} if chart_type == "area" else {},
            }]

        elif chart_type == "area":
            config["xAxis"] = {"type": "category", "data": labels, "axisLabel": {"rotate": 30}}
            config["yAxis"] = {"type": "value"}
            config["series"] = [{
                "name": series_name, "type": "line",
                "data": values,
                "smooth": True,
                "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                    "colorStops": [{"offset": 0, "color": "rgba(84,112,198,0.4)"},
                                  {"offset": 1, "color": "rgba(84,112,198,0.05)"}]}},
            }]

        elif chart_type == "pie":
            config["series"] = [{
                "name": series_name, "type": "pie",
                "radius": ["40%", "70%"],
                "data": [{"name": l, "value": v} for l, v in zip(labels, values)],
                "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0,0,0,0.5)"}},
                "label": {"formatter": "{b}: {d}%"},
            }]

        elif chart_type == "scatter":
            config["xAxis"] = {"type": "value", "name": "索引"}
            config["yAxis"] = {"type": "value", "name": "数值"}
            config["series"] = [{
                "name": series_name, "type": "scatter",
                "data": [[i, v] for i, v in enumerate(values)],
                "symbolSize": 12,
            }]

        elif chart_type == "radar":
            config["radar"] = {
                "indicator": [{"name": l, "max": max(values) * 1.2 if values else 10} for l in labels[:8]]
            }
            config["series"] = [{
                "name": series_name, "type": "radar",
                "data": [{"value": values[:8], "name": series_name}],
            }]

        elif chart_type == "table":
            config["type"] = "table"
            columns = [{"title": "名称", "dataIndex": "name", "key": "name"}]
            if values:
                columns.append({"title": "数值", "dataIndex": "value", "key": "value"})
            config["columns"] = columns
            config["dataSource"] = [{"name": l, "key": str(i), "value": v} for i, (l, v) in enumerate(zip(labels, values))]

        elif chart_type == "number":
            total = sum(values)
            avg = total / len(values) if values else 0
            config["type"] = "statistic"
            config["statistics"] = {
                "total": round(total, 2),
                "average": round(avg, 2),
                "max": round(max(values), 2) if values else 0,
                "min": round(min(values), 2) if values else 0,
                "count": len(values),
            }

        # 添加溯源数据到配置
        provenance_items = []
        for item in items[:5]:
            if item.get("provenance"):
                prov = item["provenance"]
                provenance_items.append({
                    "name": item.get("name", ""),
                    "source_doc": prov.get("source", {}).get("document_name", ""),
                    "extraction_method": prov.get("extraction", {}).get("method", ""),
                    "confidence": prov.get("extraction", {}).get("confidence"),
                })
        config["_provenance"] = provenance_items

        return config


def get_genbi_tool() -> GenBITool:
    return GenBITool()
