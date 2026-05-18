#!/usr/bin/env python3
"""测试科技事件生成器"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'odap'))

from biz.ontology.ingestion import TechEventGenerator
import asyncio


async def main():
    print("🔍 测试科技事件生成器...")
    
    try:
        generator = TechEventGenerator()
        
        print(f"生成器名称: {generator.get_generator_name()}")
        print(f"生成器描述: {generator.get_generator_description()}")
        
        docs = await generator.generate(
            parties=None,
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
            print(f"实体数量: {len(doc.entities)}")
            print(f"关系数量: {len(doc.relations)}")
            print(f"事件数量: {len(doc.events)}")
        
        print("\n✅ 测试通过！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
