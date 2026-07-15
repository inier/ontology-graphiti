"""
BranchRepositoryImpl (T354)

BranchRepository ABC 的 SQLite 实现。
通过依赖注入 SQLiteBranchStorage，符合 AGENTS.md 规则 6（禁止跨层调用）。
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from odap.infra.security.audit_helper import storage_audit

from ..interfaces import BranchRepository
from ..models import Branch, Conflict, ConflictResolution, MergeRequest
from ..storage import SQLiteBranchStorage

logger = logging.getLogger(__name__)

_AUDIT_SERVICE = "ontology_design"


def _audit_success(action: str, resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="success",
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


def _audit_failure(action: str, msg: str = "", resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="failure",
            result_message=(msg or "")[:200],
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


class BranchRepositoryImpl(BranchRepository):
    """分支仓储实现（基于 SQLite）"""

    def __init__(self, storage: Optional[SQLiteBranchStorage] = None):
        self._storage = storage or SQLiteBranchStorage()

    # ---------- Branch CRUD ----------

    def save(self, branch: Branch) -> Branch:
        action = "branch_repo.save_branch"
        resource = branch.id or "new"
        try:
            result = self._storage.save_branch(branch)
            _audit_success(action, resource=result.id,
                           details={"branch_id": result.id,
                                    "ontology_id_len": len(result.ontology_id or ""),
                                    "status": result.status.value})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=resource,
                           details={"branch_id": branch.id or ""})
            raise

    def get(self, branch_id: str) -> Optional[Branch]:
        action = "branch_repo.get_branch"
        try:
            result = self._storage.get_branch(branch_id)
            _audit_success(action, resource=branch_id,
                           details={"branch_id": branch_id, "found": bool(result)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=branch_id,
                           details={"branch_id": branch_id})
            raise

    def list(self) -> List[Branch]:
        action = "branch_repo.list_branches"
        try:
            result = self._storage.list_branches()
            _audit_success(action, details={"count": len(result)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            raise

    def list_by_ontology(self, ontology_id: str) -> List[Branch]:
        action = "branch_repo.list_by_ontology"
        try:
            result = self._storage.list_branches_by_ontology(ontology_id)
            _audit_success(action,
                           details={"count": len(result),
                                    "ontology_id_len": len(ontology_id or "")})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                           details={"ontology_id_len": len(ontology_id or "")})
            raise

    def get_active(self, ontology_id: str) -> Optional[Branch]:
        action = "branch_repo.get_active"
        try:
            result = self._storage.get_active_branch(ontology_id)
            _audit_success(action,
                           details={"ontology_id_len": len(ontology_id or ""),
                                    "found": bool(result)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                           details={"ontology_id_len": len(ontology_id or "")})
            raise

    def delete(self, branch_id: str) -> bool:
        action = "branch_repo.delete_branch"
        try:
            result = self._storage.delete_branch(branch_id)
            _audit_success(action, resource=branch_id,
                           details={"branch_id": branch_id, "deleted": bool(result)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=branch_id,
                           details={"branch_id": branch_id})
            raise

    # ---------- MergeRequest ----------

    def save_merge_request(self, mr: MergeRequest) -> MergeRequest:
        action = "branch_repo.save_mr"
        resource = mr.id or "new"
        try:
            result = self._storage.save_merge_request(mr)
            _audit_success(action, resource=result.id,
                           details={"mr_id": result.id,
                                    "source_branch_id": result.source_branch_id,
                                    "target_branch_id": result.target_branch_id,
                                    "status": result.status.value})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=resource,
                           details={"source_branch_id": mr.source_branch_id,
                                    "target_branch_id": mr.target_branch_id})
            raise

    def get_merge_request(self, mr_id: str) -> Optional[MergeRequest]:
        action = "branch_repo.get_mr"
        try:
            result = self._storage.get_merge_request(mr_id)
            _audit_success(action, resource=mr_id,
                           details={"mr_id": mr_id, "found": bool(result)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=mr_id,
                           details={"mr_id": mr_id})
            raise

    def list_merge_requests(
        self,
        branch_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[MergeRequest]:
        action = "branch_repo.list_mrs"
        try:
            result = self._storage.list_merge_requests(branch_id=branch_id, status=status)
            _audit_success(action,
                           details={"count": len(result),
                                    "has_branch_filter": bool(branch_id),
                                    "status_filter": status or ""})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                           details={"has_branch_filter": bool(branch_id)})
            raise

    # ---------- Conflict ----------

    def save_conflicts(self, mr_id: str, conflicts: List[Conflict]) -> None:
        action = "branch_repo.save_conflicts"
        try:
            self._storage.save_conflicts(mr_id, conflicts)
            _audit_success(action, resource=mr_id,
                           details={"mr_id": mr_id, "conflict_count": len(conflicts)})
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=mr_id,
                           details={"mr_id": mr_id, "conflict_count": len(conflicts)})
            raise

    def list_conflicts(self, mr_id: str) -> List[Conflict]:
        action = "branch_repo.list_conflicts"
        try:
            result = self._storage.list_conflicts(mr_id)
            _audit_success(action, resource=mr_id,
                           details={"mr_id": mr_id, "count": len(result)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=mr_id,
                           details={"mr_id": mr_id})
            raise

    def update_conflict_resolution(
        self,
        conflict_id: str,
        resolution: ConflictResolution,
        resolved_value: Any,
        resolved_by: str,
    ) -> Conflict:
        action = "branch_repo.update_conflict_resolution"
        try:
            result = self._storage.update_conflict_resolution(
                conflict_id, resolution, resolved_value, resolved_by
            )
            _audit_success(action, resource=conflict_id,
                           details={"conflict_id": conflict_id,
                                    "resolution": resolution.value})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=conflict_id,
                           details={"conflict_id": conflict_id})
            raise
