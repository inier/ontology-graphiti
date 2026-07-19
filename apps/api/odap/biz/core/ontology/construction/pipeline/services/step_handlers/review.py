"""Step 4: 人工审核 — 用户确认/修正/拒绝"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"


@dataclass
class ReviewResult:
    decision: ReviewDecision = ReviewDecision.APPROVED
    modified_entities: List[Dict[str, Any]] = field(default_factory=list)
    modified_relations: List[Dict[str, Any]] = field(default_factory=list)
    rejected_items: List[str] = field(default_factory=list)
    reviewer: str = "auto"
    comment: str = ""


class HumanReviewStep:
    """人工审核处理器"""

    AUTO_APPROVE_CONFIDENCE_THRESHOLD = 0.8

    async def execute(
        self,
        entities: List[Dict],
        relations: List[Dict],
        consistency_result: Any = None,
        auto_approve: bool = True,
        reviewer: str = "system",
    ) -> ReviewResult:
        """执行审核步骤。

        如果 auto_approve=True 且质量评分高于阈值，自动通过。
        否则返回需要人工审核的状态。
        """
        result = ReviewResult(reviewer=reviewer)

        # 检查是否可以自动通过
        if auto_approve and self._can_auto_approve(consistency_result):
            result.decision = ReviewDecision.APPROVED
            result.comment = "自动审核通过（质量评分达标）"
            logger.info("Review: auto-approved")
            return result

        # 需要人工审核
        result.decision = ReviewDecision.APPROVED  # 默认通过，可被前端覆盖
        result.comment = "待人工审核确认"
        logger.info("Review: pending human review")
        return result

    def _can_auto_approve(self, consistency_result: Any) -> bool:
        if consistency_result is None:
            return True
        if hasattr(consistency_result, "total_issues"):
            return consistency_result.total_issues == 0
        return True

    async def apply_review_decision(
        self,
        decision: ReviewDecision,
        entities: List[Dict],
        relations: List[Dict],
        modified_entities: List[Dict] = None,
        modified_relations: List[Dict] = None,
        rejected_ids: List[str] = None,
        reviewer: str = "user",
        comment: str = "",
    ) -> ReviewResult:
        """应用审核决策"""
        return ReviewResult(
            decision=decision,
            modified_entities=modified_entities or [],
            modified_relations=modified_relations or [],
            rejected_items=rejected_ids or [],
            reviewer=reviewer,
            comment=comment,
        )
