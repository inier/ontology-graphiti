"""
战场态势可视化模块
包含：
1. 战场图谱可视化
2. 处置动态查看
3. 本体可视化查询
4. 本体属性聚合
5. 时序知识图谱支持（graphiti特性）
"""

import sys
import os
import matplotlib.pyplot as plt
import networkx as nx
import plotly.graph_objects as go
import plotly.io as pio
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.graph_manager import BattlefieldGraphManager

class BattlefieldVisualization:
    """
    战场态势可视化
    支持graphiti时序知识图谱特性
    """

    def __init__(self):
        """
        初始化可视化模块
        """
        self.graph_manager = BattlefieldGraphManager()
        self.action_history = []
        print("战场态势可视化模块初始化成功")

    def _get_fallback_graph(self):
        """
        获取回退模式的图谱
        """
        if hasattr(self.graph_manager, 'fallback_graph'):
            return self.graph_manager.fallback_graph
        return None
    
    def visualize_graph(self, output_file=None):
        """
        可视化战场图谱

        Args:
            output_file: 输出文件路径
        """
        graph = self._get_fallback_graph()
        if not graph:
            print("无法获取图谱数据")
            return
        
        color_map = {
            "Location": "#1f77b4",
            "MilitaryUnit": "#ff7f0e",
            "WeaponSystem": "#2ca02c",
            "CivilianInfrastructure": "#d62728",
            "BattleEvent": "#9467bd",
            "Mission": "#8c564b"
        }
        
        size_map = {
            "Location": 300,
            "MilitaryUnit": 200,
            "WeaponSystem": 250,
            "CivilianInfrastructure": 150,
            "BattleEvent": 100,
            "Mission": 180
        }
        
        node_colors = []
        node_sizes = []
        node_labels = {}
        
        for node_id, node_data in graph.nodes(data=True):
            node_type = node_data.get("entity_type", "Unknown")
            node_colors.append(color_map.get(node_type, "#7f7f7f"))
            node_sizes.append(size_map.get(node_type, 100))
            
            if "name" in node_data:
                node_labels[node_id] = node_data["name"]
            else:
                node_labels[node_id] = node_id
        
        pos = nx.spring_layout(graph, k=0.3, iterations=50)
        
        plt.figure(figsize=(15, 12))
        nx.draw_networkx_edges(graph, pos, edge_color="#999999", width=1.0)
        nx.draw_networkx_nodes(graph, pos, node_size=node_sizes, node_color=node_colors, alpha=0.8)
        nx.draw_networkx_labels(graph, pos, labels=node_labels, font_size=8, font_color="#333333")
        
        edge_labels = {}
        for u, v, data in graph.edges(data=True):
            edge_labels[(u, v)] = data.get("relationship", "")
        
        nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_size=6, font_color="#666666")
        
        plt.title("Battlefield Situation Graph", fontsize=16)
        plt.axis("off")
        plt.tight_layout()
        
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches="tight")
            print(f"Graph saved to: {output_file}")
        else:
            plt.show()
    
    def create_interactive_visualization(self, output_file="battlefield_visualization.html"):
        """
        创建交互式可视化
        """
        graph = self._get_fallback_graph()
        if not graph:
            print("无法获取图谱数据")
            return
        
        color_map = {
            "Location": "#1f77b4",
            "MilitaryUnit": "#ff7f0e",
            "WeaponSystem": "#2ca02c",
            "CivilianInfrastructure": "#d62728",
            "BattleEvent": "#9467bd",
            "Mission": "#8c564b"
        }
        
        pos = nx.spring_layout(graph, k=0.3, iterations=50)
        
        node_x = []
        node_y = []
        node_text = []
        node_colors = []
        node_sizes = []
        
        for node_id, node_data in graph.nodes(data=True):
            x, y = pos[node_id]
            node_x.append(x)
            node_y.append(y)
            
            node_type = node_data.get("entity_type", "Unknown")
            node_colors.append(color_map.get(node_type, "#7f7f7f"))
            
            text = f"ID: {node_id}<br>Type: {node_type}"
            for key, value in node_data.items():
                if key != "entity_type":
                    text += f"<br>{key}: {value}"
            node_text.append(text)
            
            size = 20
            if node_type == "Location":
                size = 30
            elif node_type == "MilitaryUnit":
                size = 25
            elif node_type == "WeaponSystem":
                size = 28
            node_sizes.append(size)
        
        edge_x = []
        edge_y = []
        
        for u, v, data in graph.edges(data=True):
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        
        edge_trace = go.Scatter(
            x=edge_x,
            y=edge_y,
            line=dict(width=1, color="#888"),
            hoverinfo="none",
            mode="lines"
        )
        
        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers",
            hoverinfo="text",
            marker=dict(
                showscale=False,
                colorscale="YlGnBu",
                reversescale=True,
                color=node_colors,
                size=node_sizes,
                line_width=2
            )
        )
        
        node_trace.text = node_text
        
        fig = go.Figure(data=[edge_trace, node_trace],
                     layout=go.Layout(
                        title=dict(text="Battlefield Interactive Graph", font=dict(size=16)),
                        showlegend=False,
                        hovermode="closest",
                        margin=dict(b=20,l=5,r=5,t=40),
                        annotations=[ dict(
                            text="Battlefield Visualization",
                            showarrow=False,
                            xref="paper", yref="paper",
                            x=0.005, y=-0.002 ) ],
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)))
        
        pio.write_html(fig, file=output_file, auto_open=False)
        print(f"Interactive visualization saved to: {output_file}")
    
    def visualize_battlefield_status(self, output_file=None):
        """
        可视化战场状态
        """
        stats = self.graph_manager.get_graph_statistics()
        
        entity_types = list(stats["type_count"].keys())
        counts = list(stats["type_count"].values())
        
        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
        
        plt.figure(figsize=(10, 8))
        plt.pie(counts, labels=entity_types, colors=colors, autopct='%1.1f%%', startangle=140)
        plt.axis('equal')
        plt.title('Battlefield Entity Distribution', fontsize=16)
        
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches="tight")
            print(f"Battlefield status saved to: {output_file}")
        else:
            plt.show()

    def visualize_action_dynamics(self, output_file="action_dynamics.html"):
        """
        处置动态查看
        显示所有处置操作的动态状态
        """
        graph = self._get_fallback_graph()
        if not graph:
            print("无法获取图谱数据")
            return

        actions = []
        for node_id, node_data in graph.nodes(data=True):
            if node_data.get("entity_type") == "Mission":
                actions.append({
                    "id": node_id,
                    "name": node_data.get("name", node_id),
                    "type": node_data.get("type", "Unknown"),
                    "status": node_data.get("status", "Unknown"),
                    "priority": node_data.get("priority", "Unknown")
                })

        for node_id, node_data in graph.nodes(data=True):
            if node_data.get("entity_type") == "BattleEvent":
                actions.append({
                    "id": node_id,
                    "name": node_data.get("description", node_id)[:50],
                    "type": node_data.get("type", "Unknown"),
                    "status": node_data.get("outcome", "Unknown"),
                    "priority": "-"
                })
        
        if not actions:
            actions = [{"id": "NO_ACTIONS", "name": "No actions recorded", "type": "-", "status": "-", "priority": "-"}]
        
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=["<b>Action ID</b>", "<b>Name</b>", "<b>Type</b>", "<b>Status</b>", "<b>Priority</b>"],
                fill_color="#1f77b4",
                font=dict(color="white", size=12),
                align="left"
            ),
            cells=dict(
                values=[[a["id"] for a in actions],
                       [a["name"] for a in actions],
                       [a["type"] for a in actions],
                       [a["status"] for a in actions],
                       [a["priority"] for a in actions]],
                fill_color=[["#f0f0f0"]*len(actions)],
                font=dict(size=11),
                align="left"
            )
        )])
        
        fig.update_layout(
            title=dict(text="Action Dynamics View (处置动态查看)", font=dict(size=16)),
            margin=dict(l=20, r=20, t=60, b=20)
        )
        
        pio.write_html(fig, file=output_file, auto_open=False)
        print(f"Action dynamics saved to: {output_file}")
        
        return actions

    def visualize_ontology_query(self, output_file="ontology_query.html"):
        """
        本体可视化查询界面
        支持按类型、区域、状态等条件查询实体
        """
        graph = self._get_fallback_graph()
        if not graph:
            print("无法获取图谱数据")
            return

        query_results = []
        for node_id, node_data in graph.nodes(data=True):
            entity_type = node_data.get("entity_type", "Unknown")
            area = node_data.get("area", "-")
            status = node_data.get("status", "-")
            affiliation = node_data.get("affiliation", "-")
            name = node_data.get("name", node_id)

            query_results.append({
                "id": node_id,
                "name": name,
                "type": entity_type,
                "area": area,
                "status": status,
                "affiliation": affiliation
            })
        
        query_results.sort(key=lambda x: (x["type"], x["area"]))
        
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=["<b>Entity ID</b>", "<b>Name</b>", "<b>Type</b>", "<b>Area</b>", "<b>Status</b>", "<b>Affiliation</b>"],
                fill_color="#2ca02c",
                font=dict(color="white", size=12),
                align="left"
            ),
            cells=dict(
                values=[[q["id"] for q in query_results],
                       [q["name"] for q in query_results],
                       [q["type"] for q in query_results],
                       [q["area"] for q in query_results],
                       [q["status"] for q in query_results],
                       [q["affiliation"] for q in query_results]],
                fill_color=[["#e8f5e9"]*len(query_results)],
                font=dict(size=10),
                align="left"
            )
        )])
        
        fig.update_layout(
            title=dict(text="Ontology Query Interface (本体可视化查询)", font=dict(size=16)),
            margin=dict(l=20, r=20, t=60, b=20),
            height=max(600, len(query_results) * 30 + 150)
        )
        
        pio.write_html(fig, file=output_file, auto_open=False)
        print(f"Ontology query interface saved to: {output_file}")
        
        return query_results

    def visualize_ontology_aggregation(self, output_file="ontology_aggregation.html"):
        """
        本体属性聚合页面
        聚合显示各类实体的属性统计信息
        """
        graph = self._get_fallback_graph()
        if not graph:
            print("无法获取图谱数据")
            return

        type_properties = defaultdict(lambda: defaultdict(list))

        for node_id, node_data in graph.nodes(data=True):
            entity_type = node_data.get("entity_type", "Unknown")

            for key, value in node_data.items():
                if key != "entity_type":
                    type_properties[entity_type][key].append(str(value))

        aggregation_data = []
        for entity_type, properties in type_properties.items():
            prop_stats = []
            for prop_name, values in properties.items():
                unique_values = list(set(values))
                if len(unique_values) <= 5:
                    value_summary = ", ".join(unique_values)
                else:
                    value_summary = f"{len(unique_values)} unique values"

                prop_stats.append(f"{prop_name}: {value_summary}")

            aggregation_data.append({
                "type": entity_type,
                "count": sum(1 for n, d in graph.nodes(data=True) if d.get("entity_type") == entity_type),
                "properties": len(properties),
                "property_details": prop_stats
            })

        aggregation_data.sort(key=lambda x: x["count"], reverse=True)
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=[a["type"] for a in aggregation_data],
            y=[a["count"] for a in aggregation_data],
            marker_color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"],
            text=[a["count"] for a in aggregation_data],
            textposition="auto"
        ))
        
        fig.update_layout(
            title=dict(text="Ontology Property Aggregation (本体属性聚合)", font=dict(size=16)),
            xaxis_title="Entity Type",
            yaxis_title="Count",
            margin=dict(l=40, r=40, t=60, b=100)
        )
        
        pio.write_html(fig, file=output_file, auto_open=False)
        print(f"Ontology aggregation saved to: {output_file}")
        
        detail_file = output_file.replace(".html", "_details.html")
        
        details_html = "<html><head><meta charset='utf-8'><title>Ontology Property Details</title></head><body>"
        details_html += "<h1>本体属性聚合详情 (Ontology Property Aggregation Details)</h1>"
        details_html += "<table border='1' cellpadding='5' cellspacing='0'>"
        details_html += "<tr><th>Entity Type</th><th>Count</th><th>Property Count</th><th>Property Details</th></tr>"
        
        for a in aggregation_data:
            details_html += f"<tr>"
            details_html += f"<td>{a['type']}</td>"
            details_html += f"<td>{a['count']}</td>"
            details_html += f"<td>{a['properties']}</td>"
            details_html += f"<td><ul>"
            for detail in a["property_details"]:
                details_html += f"<li>{detail}</li>"
            details_html += f"</ul></td>"
            details_html += f"</tr>"
        
        details_html += "</table></body></html>"
        
        with open(detail_file, 'w', encoding='utf-8') as f:
            f.write(details_html)
        
        print(f"Ontology aggregation details saved to: {detail_file}")
        
        return aggregation_data

    def query_ontology(self, entity_type=None, area=None, affiliation=None, status=None):
        """
        查询本体

        Args:
            entity_type: 实体类型
            area: 区域
            affiliation: 所属方
            status: 状态

        Returns:
            查询结果列表
        """
        results = []

        graph = self._get_fallback_graph()
        if not graph:
            return results

        for node_id, node_data in graph.nodes(data=True):
            if entity_type and node_data.get("entity_type") != entity_type:
                continue
            if area and node_data.get("area") != area:
                continue
            if affiliation and node_data.get("affiliation") != affiliation:
                continue
            if status and node_data.get("status") != status:
                continue

            results.append({
                "id": node_id,
                "type": node_data.get("entity_type"),
                "properties": {k: v for k, v in node_data.items() if k != "entity_type"}
            })
        
        return results

if __name__ == "__main__":
    viz = BattlefieldVisualization()
    
    viz.visualize_graph("battlefield_graph.png")
    viz.create_interactive_visualization("battlefield_visualization.html")
    viz.visualize_battlefield_status("battlefield_status.png")
    viz.visualize_action_dynamics("action_dynamics.html")
    viz.visualize_ontology_query("ontology_query.html")
    viz.visualize_ontology_aggregation("ontology_aggregation.html")
    
    print("\nAll visualizations generated successfully!")