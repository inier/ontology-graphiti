"""TypeRegistry — 统一类型定义读写入口

所有类型定义的写入必须经过 TypeRegistry，由其委托给 OntologyService 执行，
并通过 OMSSyncAdapter 自动同步到 OMS 只读缓存。

调用链: routes → TypeRegistry → OntologyService (权威源)
                                 → OMSSyncAdapter → OMS (只读缓存同步)
"""

from .type_registry import TypeRegistry, get_type_registry
from .oms_sync import OMSSyncAdapter

__all__ = ["TypeRegistry", "get_type_registry", "OMSSyncAdapter"]
