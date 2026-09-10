"""biz → infra provider 注册（组合根启动时导入即生效）。

把 biz 层的服务工厂注册到 `odap.infra.providers` 注册表，供 infra 组件依赖倒置解析。
biz→infra 是合法的下行依赖（C4 允许），故本模块方向合规。

注册的工厂均为闭包，内部惰性 import 目标 biz 模块——注册本身零开销、不触发 biz 重载；
真正的 biz 导入发生在 infra 组件首次 `resolve_provider(...)` 时（运行期，此时应用已启动）。

接线点（组合根，导入本模块即完成注册）：
    - `odap/web/app.py`        生产入口（端口 8000）
    - `odap/web/api/app.py`    本地开发入口（端口 8765）
    - `tests/conftest.py`      测试全局

Stage I · C4 Group A 烧账（ADR-081）：消除 infra.query source 适配器对 biz 的直接依赖边。
"""
from odap.infra.providers import register_provider


# ── 统一查询服务 source 适配器所需的 biz 协作者 ────────────────────────────────

def _oms_service_factory():
    """SchemaSourceImpl 默认协作者：本体 OMS 服务。"""
    from odap.biz.core.ontology.public import get_oms_service
    return get_oms_service()


def _semantic_object_retriever_factory():
    """UnstructuredSourceImpl 默认协作者：语义对象检索器。

    注意：`SemanticObjectRetriever` 定义在 `semantic_retriever/retriever.py`，而包
    `__init__.py` 未再导出该名——历史上 unstructured_source 的惰性 import 写的是包路径
    （`from ...semantic_retriever import SemanticObjectRetriever`），运行期恒 ImportError，
    被 try/except 吞成 warning（.unstructured 路径因此长期失效）。此处按真实定义路径导入，
    修正该存量缺陷，使 provider 可被真正解析。
    """
    from odap.biz.data.qa.semantic_retriever.retriever import SemanticObjectRetriever
    return SemanticObjectRetriever()


def _design_contract_factory():
    """OntologyDesignSource 协作者：设计子系统契约门面。"""
    from odap.biz.core.ontology.public import get_design_contract
    return get_design_contract()


def _action_storage_factory():
    """OntologyDesignSource.query_action_types 降级源：动作存储。"""
    from odap.biz.core.ontology.public import SQLiteActionStorage
    return SQLiteActionStorage()


def _ontology_storage_factory():
    """OntologyDesignSource.query_action_types 降级源：本体存储。"""
    from odap.biz.core.ontology.public import SQLiteOntologyStorage
    return SQLiteOntologyStorage()


def bootstrap() -> None:
    """注册全部 biz provider。幂等：重复调用以后者为准。"""
    register_provider("oms_service", _oms_service_factory)
    register_provider("semantic_object_retriever", _semantic_object_retriever_factory)
    register_provider("design_contract", _design_contract_factory)
    register_provider("action_storage", _action_storage_factory)
    register_provider("ontology_storage", _ontology_storage_factory)


# 导入即注册（组合根 `import odap.biz.providers_bootstrap` 完成接线）
bootstrap()


__all__ = ["bootstrap"]
