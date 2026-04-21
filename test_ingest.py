#!/usr/bin/env python3
"""测试数据摄入服务"""

from odap.biz.ontology.services.ingest_service import IngestService

# 测试创建服务实例
try:
    service = IngestService()
    print("✅ 成功创建 IngestService 实例")
    
    # 测试获取摄入历史
    history = service.get_ingest_history()
    print(f"✅ 成功获取摄入历史，共 {len(history)} 条记录")
    
    # 测试生成随机事件
    import asyncio
    async def test_random_events():
        ingest_id = await service.generate_random_events(['red', 'blue'], count=1)
        print(f"✅ 成功生成随机事件，ingest_id: {ingest_id}")
        
        # 测试获取摄入状态
        status = service.get_ingest_status(ingest_id)
        print(f"✅ 成功获取摄入状态: {status.get('status')}")
    
    asyncio.run(test_random_events())
    
    print("\n🎉 所有测试通过！")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()