"""
设计层写操作桥接 (Design Layer Write-Operation Bridge)

Application 层需要调用设计层的写操作服务（摄入、构建、管道），
这些操作无法通过只读的 OntologyDesignContract 接口完成。

本模块是唯一的"写操作桥接点"，application 层通过本模块获取
设计层的写操作服务实例，而不是直接导入 design.services.*。

规则:
- 只暴露工厂函数，不暴露内部实现类
- Application 层 MUST 通过本模块获取写操作服务
- 禁止 application 层直接 from odap.biz.core.ontology.design.services import ...
"""


def get_ingest_service():
    """获取摄入服务实例（写操作桥接）。"""
    from ..services.ingest_service import IngestService
    return IngestService()


def get_builder_service():
    """获取构建服务实例（写操作桥接）。"""
    from ..services.build_service import get_builder_service as _get
    return _get()


def get_pipeline_service():
    """获取管道服务实例（写操作桥接）。"""
    from ..services.pipeline_service import get_pipeline_service as _get
    return _get()
