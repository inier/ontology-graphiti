#!/usr/bin/env python3
"""
集成测试
"""

import sys
import os
import unittest

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 手动导入技能模块以确保技能被注册
try:
    from odap.tools.operations import operations
    from odap.tools.intelligence import intelligence
    from odap.tools.analysis import analysis
    from odap.tools.recommendation import recommendation
    from odap.tools.task_management import task_management
    from odap.tools.policy import policy
    from odap.tools.computation import computation
    from odap.tools.planning import planning
except ImportError as e:
    print(f"技能模块导入失败: {e}")

from odap.tools import SKILL_CATALOG
from odap.infra.graph import GraphManager
from odap.biz.agent.orchestrator import SelfCorrectingOrchestrator


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def setUp(self):
        """测试前准备"""
        self.graph_manager = GraphManager()

    def test_system_initialization(self):
        """测试系统初始化"""
        # 测试技能注册
        self.assertTrue(len(SKILL_CATALOG) > 0)
        
        # 测试 GraphManager 初始化
        stats = self.graph_manager.get_statistics()
        self.assertIsInstance(stats, dict)
        self.assertIn('mode', stats)
        self.assertIn('total_entities', stats)

    def test_orchestrator_execution(self):
        """测试编排器执行"""
        # 测试飞行员角色的情报查询
        pilot = SelfCorrectingOrchestrator(user_role="pilot")
        result = pilot.run("帮我看看 B 区有没有雷达")
        self.assertIsInstance(result, list)
        
        # 测试情报分析员角色的态势分析
        analyst = SelfCorrectingOrchestrator(user_role="intelligence_analyst")
        result = analyst.run("分析当前领域态势")
        self.assertIsInstance(result, dict)
        self.assertIn('total_entities', result)
        self.assertIn('entity_types', result)
        self.assertIn('domain_status', result)
        self.assertIn('recommendations', result)

    def test_skill_integration(self):
        """测试技能集成"""
        # 测试 search_radar 技能
        if 'search_radar' in SKILL_CATALOG:
            handler = SKILL_CATALOG['search_radar']['handler']
            result = handler(area="B")
            self.assertIsInstance(result, list)
        
        # 测试 analyze_domain 技能
        if 'analyze_domain' in SKILL_CATALOG:
            handler = SKILL_CATALOG['analyze_domain']['handler']
            result = handler()
            self.assertIsInstance(result, dict)

    def test_graph_manager_integration(self):
        """测试 GraphManager 集成"""
        # 测试实体搜索
        results = self.graph_manager.search("雷达")
        self.assertIsInstance(results, list)
        
        # 测试统计信息
        stats = self.graph_manager.get_statistics()
        self.assertIsInstance(stats, dict)


if __name__ == '__main__':
    unittest.main()
