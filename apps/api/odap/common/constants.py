"""通用常量定义

所有模块共享的常量、枚举和状态码定义
"""

# 注意（Stage A.1）：此处曾顶层导入 odap.biz.core.ontology.common.types.ProcessingStatus，
# 会级联触发 biz/core/__init__.py（import * + core.agent）与整个 ontology 包，
# 使 core.ontology 成为全应用加载期依赖。经全仓核实无任何代码从 odap.common 消费
# ProcessingStatus，故移除该死再导出。ProcessingStatus 的权威定义仍在
# odap.biz.core.ontology.common.types（及 design.models.audit），需要者请直接从那里导入，
# 或走门面 odap.biz.core.ontology.public。

# 注意（Stage E · T1 烧账）：此处曾顶层导入 5 个 workspace 枚举
# (WorkspaceType / WorkspaceStatus / IsolationLevel / ImportExportStatus / ScenarioStatus)
# 从 odap.biz.platform.workspace.models.*，仅为供 common/__init__.py 再导出。
# 但文件内部从未引用它们，且全仓 grep 显示 odap.common 无任何消费者
# （apps/api + tests 均 0 命中），是纯死再导出。这 4 条边正是 C1 契约
# "common is a leaf" 的 4 条 ignore 债账来源。删除后 C1 变为完全严格
# （ignore_imports 清零），common 真正成为叶子层。需要这些枚举的消费者
# 应直接从 odap.biz.platform.workspace.models.* 导入。


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
