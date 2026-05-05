#!/usr/bin/env python3
"""调试科技事件生成器"""

import sys
import os
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'odap'))

from biz.ontology.ingestion import TechEventGenerator
import asyncio


async def test():
    print("=== 测试 TechEventGenerator ===")
    
    try:
        generator = TechEventGenerator()
        print("✅ 生成器实例化成功")
        
        print("正在调用 generate() 方法...")
        docs = await generator.generate(
            parties=None,
            scenario_context=None,
            count=1,
            scenario_id=None
        )
        
        print(f"✅ 生成了 {len(docs)} 个文档")
        
        for i, doc in enumerate(docs):
            print(f"\n文档 {i+1}:")
            print(f"  doc_id: {doc.doc_id}")
            print(f"  title: {doc.meta.title}")
            print(f"  description: {doc.meta.description}")
            print(f"  entities: {len(doc.entities)}")
            print(f"  events: {len(doc.events)}")
            
            if doc.events:
                ev = doc.events[0]
                print(f"  事件 0:")
                print(f"    event_id: {ev.event_id}")
                print(f"    event_type: {ev.event_type}")
                print(f"    description: {ev.description}")
        
        print("\n=== 完整测试通过！===")
        return True
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n完整堆栈:")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
