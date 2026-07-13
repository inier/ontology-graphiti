"""USL Manager - 6 大领域模型聚合导出。"""

from __future__ import annotations

from .usl_domain import UslDomain
from .usl_term import SemanticType, UslTerm
from .usl_hierarchy import HierarchyRel, UslHierarchy
from .usl_property_spec import DataType, UslPropertySpec
from .usl_disjoint_pair import UslDisjointPair
from .usl_cardinality import UslCardinality

__all__ = [
    # Domain
    "UslDomain",
    # Term
    "SemanticType",
    "UslTerm",
    # Hierarchy
    "HierarchyRel",
    "UslHierarchy",
    # Property Spec
    "DataType",
    "UslPropertySpec",
    # Disjoint Pair
    "UslDisjointPair",
    # Cardinality
    "UslCardinality",
]
