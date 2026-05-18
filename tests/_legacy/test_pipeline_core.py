#!/usr/bin/env python3
"""测试本体构建管道核心功能 - 专注于数据摄入到本体构建的核心流程"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uuid import uuid4
from odap.biz.ontology.services.pipeline_service import OntologyPipeline
from odap.biz.ontology.models.audit import PipelineStage, ProcessingStatus

async def test_pipeline_core():
    """测试管道核心功能"""
    print("🔄 开始测试本体构建管道核心功能...")
    print("="*80)
    
    # 测试数据
    test_content = """
    2024年3月15日，红方部队在A地区部署了3个作战单位，
    蓝方部队在B地区部署了2个作战单位。
    红方指挥官张三与蓝方指挥官李四进行了无线电通信。
    随后红方发起了进攻行动。
    """
    
    # 1. 创建管道实例
    print("\n📦 步骤1: 创建本体构建管道")
    pipeline = OntologyPipeline()
    ingest_id = str(uuid4())
    print(f"   ✅ 管道创建成功，ingest_id: {ingest_id[:8]}...")
    
    # 2. 执行管道（只执行前4个阶段，跳过需要外部依赖的阶段）
    print("\n🚀 步骤2: 执行管道核心阶段（数据采集→清洗→LLM归纳→本体构建）")
    
    # 创建上下文并手动执行前4个阶段
    from odap.biz.ontology.services.pipeline_service import PipelineContext
    
    context = PipelineContext(
        ingest_id=ingest_id,
        scenario_id="test-scenario-001",
        source="manual",
        source_details={"type": "text", "content": test_content},
        workspace_id="test-workspace-001",
        original_content=test_content
    )
    
    # 手动执行各个阶段
    stages_to_run = [
        PipelineStage.COLLECTION,
        PipelineStage.CLEANING,
        PipelineStage.LLM_EXTRACTION,
        PipelineStage.ONTOLOGY_BUILD,
    ]
    
    for stage in stages_to_run:
        print(f"\n   执行阶段: {stage.value}")
        handler = pipeline.handlers[stage]
        try:
            success = await handler.execute(context)
            if success:
                print(f"      ✅ {stage.value} 执行成功")
            else:
                print(f"      ❌ {stage.value} 执行失败: {context.error}")
                break
        except Exception as e:
            print(f"      ❌ {stage.value} 执行异常: {e}")
            break
    
    # 3. 验证执行结果
    print("\n🔍 步骤3: 验证各阶段执行结果")
    
    # 检查数据采集
    if "collection" in context.stage_results:
        collection = context.stage_results["collection"]
        print(f"\n   📥 数据采集: ✅ 记录数={collection.get('record_count', 0)}")
    
    # 检查数据清洗
    if "cleaning" in context.stage_results:
        cleaning = context.stage_results["cleaning"]
        print(f"   🧹 数据清洗: ✅ 清洗后长度={cleaning.get('cleaned_length', 0)}")
    
    # 检查LLM归纳
    if "llm" in context.stage_results:
        llm = context.stage_results["llm"]
        print(f"   🤖 LLM归纳: ✅ 实体={len(llm.get('entities', []))} 关系={len(llm.get('relations', []))}")
    
    # 检查本体构建
    if "ontology" in context.stage_results:
        ontology = context.stage_results["ontology"]
        print(f"   🏗️ 本体构建: ✅ 文档ID={ontology.get('document_id')}")
    
    # 4. 验证日志记录
    print("\n📝 步骤4: 验证处理日志")
    print(f"   ✅ 日志总数: {len(context.logs)}")
    
    stage_counts = {}
    for log in context.logs:
        stage = log.stage.value
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
    
    for stage, count in stage_counts.items():
        status = "✅" if count >= 2 else "⚠️"
        print(f"   {status} {stage}: {count}条日志")
    
    # 5. 打印日志详情
    print("\n📊 步骤5: 日志详情")
    print("-" * 60)
    for i, log in enumerate(context.logs, 1):
        status_icon = {
            ProcessingStatus.PROCESSING: "🔄",
            ProcessingStatus.COMPLETED: "✅",
            ProcessingStatus.FAILED: "❌"
        }.get(log.status, "📝")
        print(f"{i:2d}. [{log.timestamp.strftime('%H:%M:%S')}] {status_icon} {log.stage.value}: {log.operation}")
    
    print("\n" + "="*80)
    print("🎉 核心功能测试完成！")
    print(f"📋 测试摘要:")
    print(f"   - 摄入ID: {ingest_id[:8]}...")
    print(f"   - 执行阶段: {len(stages_to_run)} 个")
    print(f"   - 日志总数: {len(context.logs)}")

if __name__ == "__main__":
    asyncio.run(test_pipeline_core())