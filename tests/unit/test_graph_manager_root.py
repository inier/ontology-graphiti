#!/usr/bin/env python3
"""
GraphManager 单元测试
"""

import sys
import os
import unittest

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.infra.graph import GraphManager


class TestGraphManager(unittest.TestCase):
    """GraphManager 测试"""

    def setUp(self):
        """测试前准备"""
        self.graph_manager = GraphManager()

    def test_initialization(self):
        """测试 GraphManager 初始化"""
        self.assertIsNotNone(self.graph_manager)

    def test_get_statistics(self):
        """测试获取统计信息"""
        stats = self.graph_manager.get_statistics()
        self.assertIsInstance(stats, dict)
        # Neo4j 不可用时返回错误信息（生产模式），或正常统计（测试模式/fallback 模式）
        if 'status' in stats and stats.get('status') == 'error':
            # 生产模式：Neo4j 不可用，返回错误
            self.assertIn('message', stats)
        else:
            # 测试/fallback 模式：返回统计信息
            self.assertIn('mode', stats)
            self.assertIn('total_entities', stats)
            self.assertIn('entity_types', stats)

    def test_search(self):
        """测试实体搜索"""
        results = self.graph_manager.search("雷达")
        self.assertIsInstance(results, list)
        
        results = self.graph_manager.search("Location")
        self.assertIsInstance(results, list)

    def test_add_episode(self):
        """测试添加 Episode"""
        import asyncio
        
        async def test_add_episode_async():
            success = await self.graph_manager.add_episode(
                name="test_episode",
                content="Test episode content",
                source_description="Test source"
            )
            self.assertIsInstance(success, bool)
        
        asyncio.run(test_add_episode_async())

    def test_retrieve_rag_context(self):
        """测试 RAG 上下文检索"""
        context = self.graph_manager.retrieve_rag_context("B区威胁分析")
        self.assertIsInstance(context, str)


if __name__ == '__main__':
    unittest.main()
