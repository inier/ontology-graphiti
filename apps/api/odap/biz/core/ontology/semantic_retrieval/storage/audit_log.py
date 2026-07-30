"""Semantic Retrieval 审计适配层 (spec FR-013)。

薄封装 storage_audit，固定 service="semantic_retrieval"。
规则（project_memory）：
- 审计不记录明文内容/敏感字段，仅记录统计指标（长度/计数）
- try/except 兜底，不阻断业务
- 不在此层做图谱写入（避免递归）
"""

import logging
from typing import Any, Dict, Optional

from odap.infra.security.audit_helper import storage_audit

logger = logging.getLogger("semantic_retrieval.audit")

_SERVICE = "semantic_retrieval"


def audit_retrieval(
    action: str,
    *,
    result_status: str = "success",
    result_message: str = "",
    resource: str = _SERVICE,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """记录一次检索操作审计。

    Args:
        action: 操作名（如 query / graph_search / nl_search / hybrid）
        result_status: success | failure | denied
        result_message: 结果描述（不含明文内容）
        details: 统计指标（如 query_len / rows / duration_ms），不含明文
    """
    try:
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service=_SERVICE,
        )
    except Exception as exc:
        # 审计失败不得阻断检索业务（project_memory 规则）
        logger.warning("semantic_retrieval audit failed action=%s: %s", action, exc)
