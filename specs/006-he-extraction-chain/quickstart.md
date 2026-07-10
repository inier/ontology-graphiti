# Quickstart: Hyper-Extract 启用 + 抽取校验完整链路

**Date**: 2026-07-11
**Feature**: 006-he-extraction-chain

## 1. 重建 Docker 镜像（安装 HE）

```bash
# 在项目根目录执行
python bootstep.py rebuild main
```

## 2. 验证 HE 安装

```bash
# 验证 HE 包导入
podman exec graphiti-dev-app python -c "from hyperextract import Template; print(len(Template.list()))"
# 预期输出: 35 (或 30+)

# 验证关键依赖
podman exec graphiti-dev-app python -c "import faiss, langchain, ontomem, ontosight; print('all deps OK')"
# 预期输出: all deps OK

# 验证 HEAdapter
podman exec graphiti-dev-app python -c "from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter; a = HEAdapter(); print(a.is_available())"
# 预期输出: True
```

## 3. 端到端抽取示例

```python
# 在容器内执行
from odap.biz.core.ontology.extraction.services.extraction_service import ExtractionService

service = ExtractionService()

# NL 抽取
result = await service.extract_from_nl(
    ontology_id="your-ontology-id",
    text="客户在电商平台下单购买商品，系统自动创建订单并触发发货流程。订单包含多个商品项，每个商品有名称、价格和数量。客户可以选择支付方式，支付成功后订单状态更新为已付款。发货后物流系统跟踪配送状态。",
    method="graph_rag",
)

print(f"Session ID: {result['session_id']}")
print(f"Template used: {result['template_used']}")
print(f"Conflicts: {len(result['conflicts'])}")

# 检查校验报告
session = service.get_session(result['session_id'])
validation = session.get('result_data', {}).get('validation_report', {})
print(f"Overall status: {validation.get('summary', {}).get('overall_status')}")
print(f"Needs review: {validation.get('confidence', {}).get('needs_review', [])}")
```

## 4. 模板沉淀复用验证

```python
# 第一次抽取（触发自定义模板生成并沉淀）
result1 = await service.extract_from_nl(ontology_id="ont-1", text="...")

# 第二次抽取同一本体（应复用沉淀模板）
result2 = await service.extract_from_nl(ontology_id="ont-1", text="...")

# 验证 usage_count 递增
from odap.biz.data.hyper_extract.storage.sqlite_template_storage import SqliteTemplateStorage
storage = SqliteTemplateStorage()
settled = storage.get_by_ontology("ont-1")
print(f"Usage count: {settled['usage_count']}")  # 预期: 2
```

## 5. 单元测试

```bash
# 运行全部单元测试
pytest tests/unit/test_he_adapter.py tests/unit/test_template_engine.py tests/unit/test_validation_engine.py tests/unit/test_sqlite_template_storage.py tests/unit/test_ontology_mapper.py tests/unit/test_extract_service.py -v

# 运行集成测试（需 Neo4j + OPENAI_API_KEY）
pytest tests/integration/test_he_real_extraction.py tests/integration/test_template_settle_reuse.py tests/integration/test_dual_channel_write.py -v -m integration
```

## 6. 验证无 fallback 标记

```bash
# 确认抽取结果中无 schema_level_fallback
podman exec graphiti-dev-app python -c "
from odap.biz.core.ontology.extraction.services.extraction_service import ExtractionService
import asyncio
svc = ExtractionService()
r = asyncio.run(svc.extract_from_nl(ontology_id='test', text='测试文本'))
assert r.get('template_used') != 'schema_level_fallback', 'HE 未启用！'
print('HE 正常启用，无 fallback')
"
```
