#!/usr/bin/env python3
"""测试所有随机事件生成器"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'odap'))

from biz.ontology.ingestion import RandomEventGeneratorFactory
import asyncio


async def test_generator(generator_type: str):
    """测试单个生成器"""
    print(f"\n{'='*60}")
    print(f"测试生成器: {generator_type}")
    print(f"{'='*60}")
    
    try:
        generator = RandomEventGeneratorFactory.get_generator(generator_type)
        
        print(f"生成器名称: {generator.get_generator_name()}")
        print(f"生成器描述: {generator.get_generator_description()}")
        
        # 生成事件
        docs = await generator.generate(
            parties=["red", "blue"],  # 仅军事类使用
            scenario_context=None,
            count=1,
            scenario_id=None
        )
        
        print(f"\n✅ 成功生成 {len(docs)} 个事件文档")
        
        for i, doc in enumerate(docs, 1):
            print(f"\n--- 事件 #{i} ---")
            print(f"文档ID: {doc.doc_id}")
            print(f"文档类型: {doc.doc_type}")
            print(f"标题: {doc.meta.title}")
            print(f"描述: {doc.meta.description}")
            print(f"标签: {doc.meta.tags}")
            
            print(f"\n实体数量: {len(doc.entities)}")
            for entity in doc.entities[:3]:  # 只显示前3个
                print(f"  - {entity.name} ({entity.entity_type})")
            
            print(f"\n关系数量: {len(doc.relations)}")
            for rel in doc.relations[:3]:  # 只显示前3个
                print(f"  - {rel.source_entity} {rel.relation_type} {rel.target_entity}")
            
            print(f"\n事件数量: {len(doc.events)}")
            for event in doc.events[:2]:  # 只显示前2个
                print(f"  - {event.event_type}: {event.description}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 生成器 {generator_type} 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("🔍 开始测试所有随机事件生成器...")
    
    # 测试所有可用的生成器
    generator_types = ["military", "business", "tech", "healthcare"]
    
    results = {}
    for gen_type in generator_types:
        results[gen_type] = await test_generator(gen_type)
    
    # 总结
    print(f"\n{'='*60}")
    print("测试总结:")
    print(f"{'='*60}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for gen_type, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        generator = RandomEventGeneratorFactory.get_generator(gen_type)
        print(f"  {status}: {generator.get_generator_name()} ({gen_type})")
    
    print(f"\n总测试: {total}, 通过: {passed}, 失败: {total - passed}")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
