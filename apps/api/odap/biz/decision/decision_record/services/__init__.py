"""Decision Record 服务层导出"""

from odap.biz.decision.decision_record.services.decision_service import (
    DecisionService,
    get_decision_service,
)

__all__ = ["DecisionService", "get_decision_service"]
