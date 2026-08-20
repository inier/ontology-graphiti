"""语义资产统一编排 Pipeline（Semantic Asset Pipeline）。

把「结构化数据引入 / 非结构化文档抽取 / 候选归集 / 提交审核」统一为一条
端到端链路，前端一个入口即可完成语义定义全流程。

仅做确定性编排与候选归集，复用：
- UnifiedIngestFacade（结构化数据引入，链路 A）
- ExtractService（非结构化文档抽取，链路 B）
- SQLiteCandidateStorage（候选落库）
不引入任何 LLM 判断，状态流转遵循统一状态机（见 candidate_store/storage 常量）。
"""

from .services.pipeline_service import (
    SemanticAssetPipeline,
    get_semantic_asset_pipeline,
)

__all__ = ["SemanticAssetPipeline", "get_semantic_asset_pipeline"]
