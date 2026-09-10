"""通用模块"""

# Stage E · T1 烧账：曾从此处再导出 5 个 workspace 枚举
# (WorkspaceType / WorkspaceStatus / IsolationLevel / ImportExportStatus / ScenarioStatus)，
# 但全仓无任何消费者，且触发 common→biz 反向依赖（C1 契约 4 条 ignore 债账）。
# 已同步从 constants.py 移除上游 import，此处再导出一并删除，C1 变为完全严格。
# 需要这些枚举的消费者请直接从 odap.biz.platform.workspace.models.* 导入。
from .constants import (
    HTTPStatus,
    ErrorCode,
    DEFAULT_WORKSPACE_ID,
    DEFAULT_SCENARIO_ID,
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ISO_FORMAT,
    ISO_FORMAT_WITH_TZ,
    DB_DATE_FORMAT,
)
from .semantic_types import SemanticType, DomainCategory
from .permission_scope import PermissionScope

__all__ = [
    "HTTPStatus",
    "ErrorCode",
    "DEFAULT_WORKSPACE_ID",
    "DEFAULT_SCENARIO_ID",
    "DEFAULT_PAGE",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "ISO_FORMAT",
    "ISO_FORMAT_WITH_TZ",
    "DB_DATE_FORMAT",
    "SemanticType",
    "DomainCategory",
    "PermissionScope",
]
