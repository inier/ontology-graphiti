"""
Agent 决策引擎

.. deprecated::
    本模块已弃用。决策功能已统一到 OpenHarness v2 的 QueryEngine
    （LLM function calling 自动选择工具）和 GraphitiAgentLoop._fallback_decide()
    （关键词匹配降级）。请勿在新代码中使用 DecisionEngine。

    预计移除版本: v2.0

提供智能的决策逻辑：
1. 意图识别
2. 工具推荐
3. 参数提取
4. 多轮对话管理
"""

import re
import warnings
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Intent:
    """用户意图"""
    action: str  # 动作类型
    target: str  # 目标对象
    filters: Dict[str, Any]  # 过滤条件
    confidence: float  # 置信度


class DecisionEngine:
    """
    决策引擎
    
    基于规则 + 模式匹配的决策系统。
    """

    # 意图模式定义
    INTENT_PATTERNS = {
        "query": {
            "patterns": [
                r"查询|查找|搜索|列出|显示|获取",
                r"query|search|find|list|show|get",
            ],
            "tools": ["query_entities", "search_graph", "get_entity_details"],
        },
        "analyze": {
            "patterns": [
                r"分析|统计|汇总|报告|总结",
                r"analyze|statistics|summary|report",
            ],
            "tools": ["analyze_graph", "create_workspace_summary"],
        },
        "create": {
            "patterns": [
                r"创建|新建|添加|插入",
                r"create|new|add|insert",
            ],
            "tools": [],  # 需要具体实现
        },
        "update": {
            "patterns": [
                r"更新|修改|编辑|更改",
                r"update|modify|edit|change",
            ],
            "tools": [],  # 需要具体实现
        },
        "delete": {
            "patterns": [
                r"删除|移除|清除",
                r"delete|remove|clear",
            ],
            "tools": [],  # 需要具体实现
        },
    }

    # 实体类型映射
    ENTITY_TYPE_MAP = {
        "武器": "WeaponSystem",
        "装备": "WeaponSystem",
        "实体": "Entity",
        "组织": "Organization",
        "人员": "Person",
        "地点": "Location",
        "事件": "Event",
    }

    # 区域映射
    AREA_MAP = {
        "东部": "东部战区",
        "西部": "西部战区",
        "南部": "南部战区",
        "北部": "北部战区",
        "中部": "中部战区",
    }

    # 工作空间关键词映射
    WORKSPACE_KEYWORDS = [
        "工作空间", "workspace", "空间"
    ]

    def __init__(self, tools_catalog: Dict[str, Any]):
        warnings.warn(
            "DecisionEngine 已弃用，决策功能已统一到 OpenHarness v2 QueryEngine "
            "和 GraphitiAgentLoop._fallback_decide()。请勿在新代码中使用。"
            "预计移除版本: v2.0",
            DeprecationWarning,
            stacklevel=2,
        )
        self.tools_catalog = tools_catalog

    def recognize_intent(self, user_input: str) -> Intent:
        """
        识别用户意图
        
        Args:
            user_input: 用户输入
            
        Returns:
            识别的意图
        """
        user_input_lower = user_input.lower()
        
        # 检查是否涉及工作空间
        is_workspace_query = any(keyword in user_input for keyword in self.WORKSPACE_KEYWORDS)
        
        # 匹配意图
        for action, config in self.INTENT_PATTERNS.items():
            for pattern in config["patterns"]:
                if re.search(pattern, user_input_lower):
                    # 提取目标
                    target = self._extract_target(user_input)
                    
                    # 如果是工作空间相关查询，设置目标为 workspace
                    if is_workspace_query:
                        target = "workspace"
                    
                    # 提取过滤条件
                    filters = self._extract_filters(user_input)
                    
                    return Intent(
                        action=action,
                        target=target,
                        filters=filters,
                        confidence=0.8,
                    )
        
        # 默认意图
        return Intent(
            action="query",
            target="workspace" if is_workspace_query else "",
            filters={},
            confidence=0.5,
        )

    def recommend_tools(self, intent: Intent) -> List[Tuple[str, float]]:
        """
        推荐工具
        
        Args:
            intent: 用户意图
            
        Returns:
            工具推荐列表（带置信度）
        """
        recommendations = []
        
        # 如果是工作空间相关查询，优先推荐工作空间工具
        if intent.target == "workspace":
            workspace_tools = ["list_workspaces", "get_workspace_info", "create_workspace_summary"]
            for tool_name in workspace_tools:
                if tool_name in self.tools_catalog:
                    recommendations.append((tool_name, 0.9))
        
        # 获取意图对应的工具
        intent_config = self.INTENT_PATTERNS.get(intent.action, {})
        candidate_tools = intent_config.get("tools", [])
        
        for tool_name in candidate_tools:
            if tool_name in self.tools_catalog:
                # 计算匹配度
                score = self._calculate_tool_score(tool_name, intent)
                recommendations.append((tool_name, score))
        
        # 按置信度排序
        recommendations.sort(key=lambda x: x[1], reverse=True)
        
        return recommendations

    def extract_parameters(self, tool_name: str, user_input: str) -> Dict[str, Any]:
        """
        提取工具参数
        
        Args:
            tool_name: 工具名称
            user_input: 用户输入
            
        Returns:
            提取的参数
        """
        params = {}
        
        if tool_name in ["list_workspaces", "create_workspace_summary"]:
            # 工作空间工具不需要特殊参数
            pass
        
        elif tool_name == "get_workspace_info":
            # 尝试提取工作空间ID
            ws_match = re.search(r'工作空间[是为]?\s*([\w-]+)', user_input)
            if ws_match:
                params["workspace_id"] = ws_match.group(1)
        
        elif tool_name == "query_entities":
            # 提取实体类型
            for keyword, entity_type in self.ENTITY_TYPE_MAP.items():
                if keyword in user_input:
                    params["entity_type"] = entity_type
                    break
            
            # 提取区域
            for keyword, area in self.AREA_MAP.items():
                if keyword in user_input:
                    params["area"] = area
                    break
            
            # 提取限制
            limit_match = re.search(r'(\d+)个', user_input)
            if limit_match:
                params["limit"] = int(limit_match.group(1))
        
        elif tool_name == "search_graph":
            # 提取关键词
            params["keyword"] = user_input
            
            # 提取搜索类型
            if "关系" in user_input or "relation" in user_input.lower():
                params["search_type"] = "relation"
            elif "实体" in user_input or "entity" in user_input.lower():
                params["search_type"] = "entity"
            else:
                params["search_type"] = "all"
        
        elif tool_name == "get_entity_details":
            # 尝试提取实体ID
            id_match = re.search(r'ID[是为]?\s*([\w-]+)', user_input)
            if id_match:
                params["entity_id"] = id_match.group(1)
        
        elif tool_name == "create_workspace_summary":
            # 检查是否指定了工作空间
            ws_match = re.search(r'工作空间[是为]?\s*([\w-]+)', user_input)
            if ws_match:
                params["workspace_id"] = ws_match.group(1)
        
        return params

    def _extract_target(self, user_input: str) -> str:
        """提取目标对象"""
        # 尝试匹配实体类型
        for keyword, entity_type in self.ENTITY_TYPE_MAP.items():
            if keyword in user_input:
                return entity_type
        
        return ""

    def _extract_filters(self, user_input: str) -> Dict[str, Any]:
        """提取过滤条件"""
        filters = {}
        
        # 提取区域
        for keyword, area in self.AREA_MAP.items():
            if keyword in user_input:
                filters["area"] = area
                break
        
        # 提取数量限制
        limit_match = re.search(r'(\d+)个', user_input)
        if limit_match:
            filters["limit"] = int(limit_match.group(1))
        
        return filters

    def _calculate_tool_score(self, tool_name: str, intent: Intent) -> float:
        """计算工具匹配分数"""
        score = 0.5  # 基础分
        
        # 意图匹配
        if intent.action in ["query", "search"]:
            if tool_name in ["query_entities", "search_graph"]:
                score += 0.3
        elif intent.action == "analyze":
            if tool_name in ["analyze_graph", "create_workspace_summary"]:
                score += 0.3
        
        # 目标匹配
        if intent.target:
            tool_info = self.tools_catalog.get(tool_name, {})
            description = tool_info.get("description", "")
            if intent.target.lower() in description.lower():
                score += 0.2
        
        return min(score, 1.0)

    def decide(self, user_input: str) -> Tuple[str, Dict[str, Any], str]:
        """
        决策主函数
        
        Args:
            user_input: 用户输入
            
        Returns:
            (工具名称, 参数, 思考过程)
        """
        # 1. 识别意图
        intent = self.recognize_intent(user_input)
        
        # 2. 推荐工具
        recommendations = self.recommend_tools(intent)
        
        if not recommendations:
            return "end_mission", {}, "无法识别合适的工具"
        
        # 3. 选择最佳工具
        best_tool, confidence = recommendations[0]
        
        # 4. 提取参数
        params = self.extract_parameters(best_tool, user_input)
        
        # 5. 生成思考过程
        thought = (
            f"识别意图: {intent.action} (置信度: {intent.confidence:.2f})\n"
            f"推荐工具: {best_tool} (匹配度: {confidence:.2f})\n"
            f"提取参数: {params}"
        )
        
        return best_tool, params, thought


# 便捷函数
def create_decision_engine(tools_catalog: Dict[str, Any]) -> DecisionEngine:
    """创建决策引擎

    .. deprecated::
        DecisionEngine 已弃用。请使用 GraphitiAgentLoop 代替。
    """
    warnings.warn(
        "create_decision_engine() 已弃用，请使用 GraphitiAgentLoop 代替。"
        "预计移除版本: v2.0",
        DeprecationWarning,
        stacklevel=2,
    )
    return DecisionEngine(tools_catalog)
