"""权限作用域枚举 — 跨层共享类型。

原定义于 biz.platform.roles.api.schemas，但 infra.opa.opa_service 也需使用。
infra 不得向上依赖 biz（C4 契约），故下沉到 common 叶子层。
biz.platform.roles.api.schemas 保留向后兼容再导出。

Stage H · C4 Tier3 烧账（ADR-080）。
"""

from enum import Enum


class PermissionScope(str, Enum):
    """权限作用域。"""

    SYSTEM = "system"
    PROJECT = "project"
    RESOURCE = "resource"
    DATA = "data"


__all__ = ["PermissionScope"]
