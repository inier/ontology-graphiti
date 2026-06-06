"""实现模块"""
from .validator import (
    InheritanceValidator,
    ValidationResult,
    validate_inheritance_chain,
    validate_mixin_conflicts,
)
from .resolver import (
    InheritanceResolver,
    TypePropertyProvider,
    DictTypePropertyProvider,
    SOURCE_SELF,
    SOURCE_PARENT,
    SOURCE_MIXIN,
    resolve_property_chain,
    resolve_all_properties,
)
from .inheritance_repository_impl import InheritanceRepositoryImpl
from ..models.resolved_property import ResolvedProperty

__all__ = [
    "InheritanceValidator",
    "ValidationResult",
    "validate_inheritance_chain",
    "validate_mixin_conflicts",
    "InheritanceResolver",
    "ResolvedProperty",
    "TypePropertyProvider",
    "DictTypePropertyProvider",
    "SOURCE_SELF",
    "SOURCE_PARENT",
    "SOURCE_MIXIN",
    "resolve_property_chain",
    "resolve_all_properties",
    "InheritanceRepositoryImpl",
]
