#!/usr/bin/env python3
"""
工具模块单元测试
"""

import sys
import os
import unittest

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.tools import SKILL_CATALOG, register_skill
from odap.tools.operations import operations
from odap.tools.intelligence import intelligence


class TestTools(unittest.TestCase):
    """工具模块测试"""

    def setUp(self):
        """测试前准备"""
        pass

    def test_skill_registration(self):
        """测试技能注册"""
        # 验证技能注册表不为空
        self.assertTrue(len(SKILL_CATALOG) > 0)
        
        # 验证关键技能存在
        expected_skills = [
            'engage_target',
            'command_unit',
            'search_sensor',
            'analyze_domain'
        ]
        
        for skill in expected_skills:
            self.assertIn(skill, SKILL_CATALOG)
            self.assertIn('description', SKILL_CATALOG[skill])
            self.assertIn('handler', SKILL_CATALOG[skill])
            self.assertIn('category', SKILL_CATALOG[skill])

    def test_skill_execution(self):
        """测试技能执行"""
        # 测试 search_sensor 技能
        if 'search_sensor' in SKILL_CATALOG:
            handler = SKILL_CATALOG['search_sensor']['handler']
            result = handler(area="B")
            self.assertIsInstance(result, list)
        
        # 测试 analyze_domain 技能
        if 'analyze_domain' in SKILL_CATALOG:
            handler = SKILL_CATALOG['analyze_domain']['handler']
            result = handler()
            self.assertIsInstance(result, dict)
            self.assertIn('total_entities', result)
            self.assertIn('entity_types', result)
            self.assertIn('domain_status', result)
            self.assertIn('recommendations', result)

    def test_operations_module_import(self):
        """测试 operations 模块导入"""
        try:
            from odap.tools.operations import operations
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"导入 operations 模块失败: {e}")

    def test_intelligence_module_import(self):
        """测试 intelligence 模块导入"""
        try:
            from odap.tools.intelligence import intelligence
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"导入 intelligence 模块失败: {e}")


if __name__ == '__main__':
    unittest.main()
