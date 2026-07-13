"""审批工作流（Spec 007 Iter 1 骨架，Iter 2 完善）。

Iter 1 已落地：
  - impl/permissions.py::verify_schema_auditor  ——  FastAPI Depends 钩子，
    用于写路径强制 admin 或 schema_auditor（Iter 3 切换 OPA 驱动）。
"""

from __future__ import annotations

from .impl.permissions import verify_schema_auditor

__all__ = ["verify_schema_auditor"]
