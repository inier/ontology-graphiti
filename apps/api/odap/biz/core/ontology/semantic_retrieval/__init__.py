"""Semantic Retrieval Service Bus (ADR-073, spec 008).

统一/分项/混合三层语义检索服务总线：
- 统一检索：POST /api/semantic-retrieval/query  (auto 路由)
- 分项检索：/chain /nl /mdl /graph /metric
- 混合检索：POST /api/semantic-retrieval/hybrid

定位为 Facade + 薄适配器，90% 能力复用现有资产（QueryService / USL /
DeductionEngine / PipelineService），不新建单实现接口（Constitution IV）。
"""
