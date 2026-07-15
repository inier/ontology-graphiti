"""
设计子系统契约层 (Design Subsystem Contract Layer)

本体设计子系统和本体应用子系统之间只能通过这个契约层通信。
所有跨边界访问 MUST 通过本模块的接口，禁止直接导入 design 子模块。

The Design and Application subsystems communicate ONLY through this contract layer.
All cross-boundary access MUST go through this module. Direct imports of
`odap.biz.core.ontology.design.*` from application code are FORBIDDEN.

Usage from application:
    from odap.biz.core.ontology.design.contract import (
        get_design_contract,
        OntologyDesignContract,
    )

    contract = get_design_contract()
    entities = contract.list_entity_types(workspace_id="ws-001")
"""
from .interface import (
    OntologyDesignContract,
    EntityTypeView,
    RelationTypeView,
    PropertyView,
    OntologyVersionView,
    OntologyDocumentView,
    ContractError,
    ContractNotFoundError,
    ContractValidationError,
)
from .facade import DesignContractFacade, get_design_contract
from .bridge import get_ingest_service, get_builder_service, get_pipeline_service

__all__ = [
    "OntologyDesignContract",
    "EntityTypeView",
    "RelationTypeView",
    "PropertyView",
    "OntologyVersionView",
    "OntologyDocumentView",
    "ContractError",
    "ContractNotFoundError",
    "ContractValidationError",
    "DesignContractFacade",
    "get_design_contract",
    "get_ingest_service",
    "get_builder_service",
    "get_pipeline_service",
]
