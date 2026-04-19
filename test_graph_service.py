#!/usr/bin/env python3
"""
测试 GraphService 新功能
"""

import sys
import os
from datetime import datetime, timezone

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from odap.infra.graph.graph_service import GraphManager


def test_temporal_query():
    """测试双时态查询"""
    print("\n=== 测试双时态查询 ===")
    graph_manager = GraphManager()
    
    # 测试双时态查询
    result = graph_manager.query_temporal()
    print(f"双时态查询结果数量: {len(result)}")
    if result:
        print(f"第一个结果: {result[0]}")


def test_hybrid_search():
    """测试混合检索"""
    print("\n=== 测试混合检索 ===")
    graph_manager = GraphManager()
    
    # 测试混合检索
    query = "军事基地"
    result = graph_manager.search_hybrid(query, top_k=5)
    print(f"混合检索结果数量: {len(result)}")
    for i, item in enumerate(result):
        print(f"{i+1}. {item['id']} - 得分: {item.get('score', 'N/A')}")


def test_batch_episodes():
    """测试批量添加 Episode"""
    print("\n=== 测试批量添加 Episode ===")
    graph_manager = GraphManager()
    
    # 准备测试数据
    episodes = [
        {
            "name": "测试实体1",
            "content": "这是测试实体1的内容",
            "source_description": "测试数据",
            "reference_time": datetime.now(timezone.utc)
        },
        {
            "name": "测试实体2",
            "content": "这是测试实体2的内容",
            "source_description": "测试数据",
            "reference_time": datetime.now(timezone.utc)
        }
    ]
    
    # 测试批量添加
    result = graph_manager.add_episodes_batch(episodes)
    print(f"批量添加结果: {result}")


def test_performance_metrics():
    """测试性能监控"""
    print("\n=== 测试性能监控 ===")
    graph_manager = GraphManager()
    
    # 执行一些查询以生成性能数据
    for i in range(5):
        graph_manager.query_entities()
    
    # 获取性能指标
    metrics = graph_manager.get_performance_metrics()
    print("性能监控指标:")
    print(f"平均查询时间: {metrics['query_times']['average']:.4f} 秒")
    print(f"最大查询时间: {metrics['query_times']['max']:.4f} 秒")
    print(f"最小查询时间: {metrics['query_times']['min']:.4f} 秒")
    print(f"缓存命中率: {metrics['cache']['hit_rate']:.2f}")
    print(f"连接池大小: {metrics['connection_pool']['current_size']}/{metrics['connection_pool']['max_size']}")
    print(f"断路器状态: {'打开' if metrics['circuit_breaker']['is_open'] else '关闭'}")


def test_connection_pool():
    """测试连接池"""
    print("\n=== 测试连接池 ===")
    graph_manager = GraphManager()
    
    # 获取性能指标中的连接池信息
    metrics = graph_manager.get_performance_metrics()
    print(f"初始连接池大小: {metrics['connection_pool']['current_size']}")
    
    # 执行多次查询，测试连接池使用
    for i in range(10):
        graph_manager.query_entities()
    
    # 再次获取连接池信息
    metrics = graph_manager.get_performance_metrics()
    print(f"执行查询后连接池大小: {metrics['connection_pool']['current_size']}")


if __name__ == "__main__":
    print("开始测试 GraphService 新功能...")
    
    try:
        test_temporal_query()
        test_hybrid_search()
        test_batch_episodes()
        test_performance_metrics()
        test_connection_pool()
        print("\n测试完成!")
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
