"""数据管道模块。

历史上 `odap/infra/data_pipeline.py`（模块）与 `odap/infra/data_pipeline/`（包）同名共存，
Python 的包优先规则让模块被永久遮蔽：任何 `from odap.infra.data_pipeline import DataPipeline`
都会命中本包，而本包 `__init__` 当时是空的，于是 adapters/ 下 4 个适配器全部
`ModuleNotFoundError: No module named 'odap.infra.data_pipeline.data_pipeline'`。

现已把原模块收敛为包内的 `core.py`（内容未改），并在包级 re-export 原公开符号，
使 `from odap.infra.data_pipeline import DataSourceConnector` 等旧写法重新成立。
"""

from .core import (
    DataFormat,
    DataPipeline,
    DataRecord,
    DataSourceConnector,
    DataTransformer,
    DataValidator,
    FileDataSource,
    PipelineResult,
    PipelineStage,
    StageResult,
    StageStatus,
)

__all__ = [
    "DataFormat",
    "DataPipeline",
    "DataRecord",
    "DataSourceConnector",
    "DataTransformer",
    "DataValidator",
    "FileDataSource",
    "PipelineResult",
    "PipelineStage",
    "StageResult",
    "StageStatus",
]
