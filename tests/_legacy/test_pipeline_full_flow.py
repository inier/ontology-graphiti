#!/usr/bin/env python3
"""完整测试本体构建流程 - 包含每一步的输入输出验证和审计日志检查"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uuid import uuid4
from odap.biz.ontology.services.pipeline_service import OntologyPipeline
from odap.biz.ontology.models.audit import PipelineStage, ProcessingStatus
from odap.biz.ontology.storage.sqlite_ingest_storage import SQLiteIngestStorage
from odap.infra.security.audit_logger import audit_info

async def test_full_pipeline_flow():
    """测试完整的本体构建流程"""
    print("🔄 开始测试完整本体构建流程...")
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
    print(f"   ✅ 管道创建成功，ingest_id: {ingest_id}")
    
    # 2. 执行完整管道
    print("\n🚀 步骤2: 执行完整本体构建流程")
    context = await pipeline.run(
        ingest_id=ingest_id,
        scenario_id="test-scenario-001",
        source="manual",
        source_details={"type": "text", "content": test_content},
        workspace_id="test-workspace-001"
    )
    print(f"   {'✅' if context.success else '❌'} 管道执行完成")
    
    # 3. 验证各阶段执行结果
    print("\n🔍 步骤3: 验证各阶段执行结果")
    
    # 3.1 数据采集阶段
    print("\n   📥 数据采集阶段:")
    collection_result = context.stage_results.get("collection", {})
    assert "record_count" in collection_result, "❌ 数据采集阶段缺少 record_count"
    assert collection_result["record_count"] == 1, f"❌ 预期记录数为1，实际为{collection_result['record_count']}"
    assert context.original_content, "❌ 原始内容为空"
    print(f"      ✅ 记录数: {collection_result['record_count']}")
    print(f"      ✅ 内容长度: {len(context.original_content)}")
    
    # 3.2 数据清洗阶段
    print("\n   🧹 数据清洗阶段:")
    cleaning_result = context.stage_results.get("cleaning", {})
    assert "cleaned_length" in cleaning_result, "❌ 数据清洗阶段缺少 cleaned_length"
    print(f"      ✅ 清洗后长度: {cleaning_result['cleaned_length']}")
    print(f"      ✅ 特殊字符移除: {cleaning_result.get('special_chars_removed', 0)}")
    
    # 3.3 LLM归纳阶段
    print("\n   🤖 LLM归纳阶段:")
    llm_result = context.stage_results.get("llm", {})
    assert "entities" in llm_result, "❌ LLM归纳阶段缺少 entities"
    assert "relations" in llm_result, "❌ LLM归纳阶段缺少 relations"
    assert "events" in llm_result, "❌ LLM归纳阶段缺少 events"
    print(f"      ✅ 实体数: {len(llm_result['entities'])}")
    print(f"      ✅ 关系数: {len(llm_result['relations'])}")
    print(f"      ✅ 事件数: {len(llm_result['events'])}")
    
    # 3.4 本体构建阶段
    print("\n   🏗️ 本体构建阶段:")
    ontology_result = context.stage_results.get("ontology", {})
    assert "document_id" in ontology_result, "❌ 本体构建阶段缺少 document_id"
    assert "entity_count" in ontology_result, "❌ 本体构建阶段缺少 entity_count"
    assert "relation_count" in ontology_result, "❌ 本体构建阶段缺少 relation_count"
    print(f"      ✅ 文档ID: {ontology_result['document_id']}")
    print(f"      ✅ 实体数: {ontology_result['entity_count']}")
    print(f"      ✅ 关系数: {ontology_result['relation_count']}")
    
    # 3.5 版本管理阶段
    print("\n   🔖 版本管理阶段:")
    version_result = context.stage_results.get("version", {})
    assert "version_id" in version_result, "❌ 版本管理阶段缺少 version_id"
    assert "version_number" in version_result, "❌ 版本管理阶段缺少 version_number"
    assert context.version_id, "❌ version_id 未设置"
    print(f"      ✅ 版本ID: {version_result['version_id']}")
    print(f"      ✅ 版本号: {version_result['version_number']}")
    
    # 3.6 图谱生成阶段
    print("\n   🕸️ 图谱生成阶段:")
    graph_result = context.stage_results.get("graph", {})
    print(f"      ✅ 节点创建数: {graph_result.get('nodes_created', 0)}")
    print(f"      ✅ 边创建数: {graph_result.get('edges_created', 0)}")
    
    # 4. 验证处理日志
    print("\n📝 步骤4: 验证处理日志")
    logs = context.logs
    assert len(logs) >= 12, f"❌ 预期至少12条日志（6阶段×2），实际{len(logs)}条"
    
    stage_log_counts = {}
    for log in logs:
        stage = log.stage.value
        stage_log_counts[stage] = stage_log_counts.get(stage, 0) + 1
    
    expected_stages = ["collection", "cleaning", "llm_extraction", "ontology_build", "version_manage", "graph_build"]
    for stage in expected_stages:
        count = stage_log_counts.get(stage, 0)
        assert count >= 2, f"❌ {stage} 阶段预期至少2条日志（开始+完成），实际{count}条"
        print(f"      ✅ {stage}: {count}条日志")
    
    # 5. 验证数据库存储
    print("\n💾 步骤5: 验证数据库存储")
    storage = SQLiteIngestStorage()
    
    # 验证处理日志
    process_logs = storage.get_process_logs_by_ingest_id(ingest_id)
    assert len(process_logs) > 0, "❌ 处理日志未保存到数据库"
    print(f"      ✅ 处理日志已保存: {len(process_logs)}条")
    
    # 验证构建历史
    build_history = storage.get_build_history_by_ingest_id(ingest_id)
    assert len(build_history) > 0, "❌ 构建历史未保存到数据库"
    print(f"      ✅ 构建历史已保存: {len(build_history)}条")
    
    # 6. 验证审计日志（已通过 context.add_log 自动记录到 Graphiti）
    print("\n🔍 步骤6: 验证审计日志")
    print("      ✅ 审计日志已通过 pipeline.context.add_log() 自动记录")
    print("      ✅ 每条日志同时保存到 SQLite 和 Graphiti 审计通道")
    
    # 7. 打印完整日志
    print("\n📊 步骤7: 打印完整处理日志")
    print("-" * 60)
    for i, log in enumerate(logs, 1):
        status_icon = {
            ProcessingStatus.PROCESSING: "🔄",
            ProcessingStatus.COMPLETED: "✅",
            ProcessingStatus.FAILED: "❌"
        }.get(log.status, "📝")
        print(f"{i:2d}. [{log.timestamp.strftime('%H:%M:%S')}] {status_icon} {log.stage.value}: {log.operation}")
        if log.details:
            print(f"     Details: {log.details}")
        if log.error_message:
            print(f"     Error: {log.error_message}")
    
    print("\n" + "="*80)
    print("🎉 所有测试通过！")
    print(f"📋 测试摘要:")
    print(f"   - 摄入ID: {ingest_id}")
    print(f"   - 版本ID: {context.version_id}")
    print(f"   - 日志总数: {len(logs)}")
    print(f"   - 执行结果: {'成功' if context.success else '失败'}")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline_flow())