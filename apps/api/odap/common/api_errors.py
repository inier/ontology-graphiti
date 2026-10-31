"""统一 API 错误契约 —— common 叶子层（仅标准库）。

SPEC-v2 §5 错误契约（全局统一，AC-56）：

    { "error_code": string, "message": string, "detail": object|null, "trace_id": string }

约束：
- `error_code` 必须具体可调试（如 `WIKI_OWNER_REQUIRED`）；
- **禁止** `"处理失败"` / `"操作异常"` 之类模糊文案；
- `detail` 承载机器可读的补充信息（如冲突条目 id、期望版本号）。

本模块只做「错误定义」，不依赖 fastapi —— 使 biz service 可以抛业务错误而不感知 HTTP
（分层铁律：service 不 import req/res）。HTTP 状态码映射由
`odap.infra.middleware.api_error_handler` 统一完成。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ApiError(Exception):
    """带 error_code 的业务错误（由全局处理器翻译为 JSON 响应）。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 400,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not error_code:
            raise ValueError("ApiError.error_code 不能为空")
        super().__init__(f"{error_code}: {message}")
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.detail = detail

    def to_payload(self, trace_id: str) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "detail": self.detail,
            "trace_id": trace_id,
        }


# ── Wiki 条目（F1，AC-01~AC-08）───────────────────────────────────────────────
WIKI_OWNER_REQUIRED = "WIKI_OWNER_REQUIRED"
WIKI_TITLE_REQUIRED = "WIKI_TITLE_REQUIRED"
WIKI_CONTENT_REQUIRED = "WIKI_CONTENT_REQUIRED"
WIKI_ENTRY_NOT_FOUND = "WIKI_ENTRY_NOT_FOUND"
WIKI_VERSION_CONFLICT = "WIKI_VERSION_CONFLICT"
WIKI_DUPLICATE_CONTENT = "WIKI_DUPLICATE_CONTENT"
WIKI_INVALID_STATUS_TRANSITION = "WIKI_INVALID_STATUS_TRANSITION"
WIKI_CITATION_INVALID = "WIKI_CITATION_INVALID"
WIKI_EXPORT_FORBIDDEN = "WIKI_EXPORT_FORBIDDEN"
WIKI_IMPORT_SOURCE_NOT_FOUND = "WIKI_IMPORT_SOURCE_NOT_FOUND"
WIKI_IMPORT_PATH_INVALID = "WIKI_IMPORT_PATH_INVALID"

# ── 文档治理（F2，AC-09~AC-14）────────────────────────────────────────────────
DOC_NOT_FOUND = "DOC_NOT_FOUND"
DOC_SUPERSEDE_SELF = "DOC_SUPERSEDE_SELF"
DOC_SUPERSEDE_CYCLE = "DOC_SUPERSEDE_CYCLE"
DOC_SUPERSEDE_TARGET_INVALID = "DOC_SUPERSEDE_TARGET_INVALID"

# ── 本体约束编排（F6/F8，AC-24~AC-38）────────────────────────────────────────
QA_QUERY_REQUIRED = "QA_QUERY_REQUIRED"
QA_TRACE_NOT_FOUND = "QA_TRACE_NOT_FOUND"
QA_PROVENANCE_INCOMPLETE = "QA_PROVENANCE_INCOMPLETE"
GUARD_FAIL_CLOSED = "GUARD_FAIL_CLOSED"
TBOX_UNMAPPED_SLOT = "TBOX_UNMAPPED_SLOT"
OUTPUT_CONTRACT_VIOLATION = "OUTPUT_CONTRACT_VIOLATION"

# ── F9 Action / HITL（AC-40~AC-42）───────────────────────────────────────────
ACTION_NOT_FOUND = "ACTION_NOT_FOUND"
ACTION_HITL_REQUIRED = "ACTION_HITL_REQUIRED"
ACTION_HITL_NOT_APPLICABLE = "ACTION_HITL_NOT_APPLICABLE"
ACTION_ALREADY_SETTLED = "ACTION_ALREADY_SETTLED"
ACTION_REJECTED = "ACTION_REJECTED"
ACTION_EXECUTION_FAILED = "ACTION_EXECUTION_FAILED"
ACTION_EXECUTION_NOT_IMPLEMENTED = "ACTION_EXECUTION_NOT_IMPLEMENTED"
APPROVAL_DENIED = "APPROVAL_DENIED"
APPROVAL_SERVICE_UNAVAILABLE = "APPROVAL_SERVICE_UNAVAILABLE"

# ── 通用 ──────────────────────────────────────────────────────────────────────
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
UNAUTHORIZED = "UNAUTHORIZED"
INTERNAL_ERROR = "INTERNAL_ERROR"


__all__ = [
    "ApiError",
    "WIKI_OWNER_REQUIRED",
    "WIKI_TITLE_REQUIRED",
    "WIKI_CONTENT_REQUIRED",
    "WIKI_ENTRY_NOT_FOUND",
    "WIKI_VERSION_CONFLICT",
    "WIKI_DUPLICATE_CONTENT",
    "WIKI_INVALID_STATUS_TRANSITION",
    "WIKI_CITATION_INVALID",
    "WIKI_EXPORT_FORBIDDEN",
    "WIKI_IMPORT_SOURCE_NOT_FOUND",
    "WIKI_IMPORT_PATH_INVALID",
    "DOC_NOT_FOUND",
    "DOC_SUPERSEDE_SELF",
    "DOC_SUPERSEDE_CYCLE",
    "DOC_SUPERSEDE_TARGET_INVALID",
    "QA_QUERY_REQUIRED",
    "QA_TRACE_NOT_FOUND",
    "QA_PROVENANCE_INCOMPLETE",
    "GUARD_FAIL_CLOSED",
    "TBOX_UNMAPPED_SLOT",
    "OUTPUT_CONTRACT_VIOLATION",
    "ACTION_NOT_FOUND",
    "ACTION_HITL_REQUIRED",
    "ACTION_HITL_NOT_APPLICABLE",
    "ACTION_ALREADY_SETTLED",
    "ACTION_REJECTED",
    "ACTION_EXECUTION_FAILED",
    "ACTION_EXECUTION_NOT_IMPLEMENTED",
    "APPROVAL_DENIED",
    "APPROVAL_SERVICE_UNAVAILABLE",
    "NOT_IMPLEMENTED",
    "UNAUTHORIZED",
    "INTERNAL_ERROR",
]
