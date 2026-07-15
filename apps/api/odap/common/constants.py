"""通用常量定义

所有模块共享的常量、枚举和状态码定义
"""

from odap.biz.platform.workspace.models.workspace import WorkspaceType, WorkspaceStatus
from odap.biz.platform.workspace.models.isolation import IsolationLevel
from odap.biz.platform.workspace.models.import_export import ImportExportStatus
from odap.biz.platform.workspace.models.scenario import ScenarioStatus
from odap.biz.core.ontology.design.models.audit import ProcessingStatus


# 状态码常量
class HTTPStatus:
    """HTTP 状态码常量"""
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503


# 错误码常量
class ErrorCode:
    """错误码常量"""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


# 默认值常量
DEFAULT_WORKSPACE_ID = "default"
DEFAULT_SCENARIO_ID = "default"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

# 时间格式
ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"
ISO_FORMAT_WITH_TZ = "%Y-%m-%dT%H:%M:%S%z"

# 数据库相关
DB_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 分页默认值
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 1000
