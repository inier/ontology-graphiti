"""approval_workflow.impl 包（Spec 007 Iter 1）。

子模块：
  - permissions: verify_schema_auditor Depends 钩子（Iter 1 写死，Iter 3 OPA）
"""

from .permissions import verify_schema_auditor

__all__ = ["verify_schema_auditor"]
