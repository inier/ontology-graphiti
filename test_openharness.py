#!/usr/bin/env python3
"""测试OpenHarness导入"""

import sys
sys.path.insert(0, '/Users/caec/workspace/ontology/graphiti')

try:
    # 测试直接导入
    try:
        from openharness_ai.tools.tool import Tool
        from openharness_ai.core.harness import Harness, Observation
        print("✓ 从 openharness_ai 导入成功")
    except ImportError:
        from openharness.tools.tool import Tool
        from openharness.core.harness import Harness, Observation
        print("✓ 从 openharness 导入成功")
    
    # 测试适配器导入
    from odap.infra.openharness import create_harness
    harness = create_harness()
    if harness:
        print(f"✓ Harness 创建成功，可用工具: {len(harness.list_available_tools())}")
    else:
        print("⚠ Harness 创建失败，使用 fallback 模式")
        
    print("\n测试完成！")
    
except Exception as e:
    print(f"✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()