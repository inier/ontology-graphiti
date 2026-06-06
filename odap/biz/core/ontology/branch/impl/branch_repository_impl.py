"""
BranchRepositoryImpl (T354)

BranchRepository ABC 的 SQLite 实现。
通过依赖注入 SQLiteBranchStorage，符合 AGENTS.md 规则 6（禁止跨层调用）。
"""
from __future__ import annotations

from typing import Any, List, Optional

from ..interfaces import BranchRepository
from ..models import Branch, Conflict, ConflictResolution, MergeRequest
from ..storage import SQLiteBranchStorage


class BranchRepositoryImpl(BranchRepository):
    """分支仓储实现（基于 SQLite）"""

    def __init__(self, storage: Optional[SQLiteBranchStorage] = None):
        self._storage = storage or SQLiteBranchStorage()

    # ---------- Branch CRUD ----------

    def save(self, branch: Branch) -> Branch:
        return self._storage.save_branch(branch)

    def get(self, branch_id: str) -> Optional[Branch]:
        return self._storage.get_branch(branch_id)

    def list(self) -> List[Branch]:
        return self._storage.list_branches()

    def list_by_ontology(self, ontology_id: str) -> List[Branch]:
        return self._storage.list_branches_by_ontology(ontology_id)

    def get_active(self, ontology_id: str) -> Optional[Branch]:
        return self._storage.get_active_branch(ontology_id)

    def delete(self, branch_id: str) -> bool:
        return self._storage.delete_branch(branch_id)

    # ---------- MergeRequest ----------

    def save_merge_request(self, mr: MergeRequest) -> MergeRequest:
        return self._storage.save_merge_request(mr)

    def get_merge_request(self, mr_id: str) -> Optional[MergeRequest]:
        return self._storage.get_merge_request(mr_id)

    def list_merge_requests(
        self,
        branch_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[MergeRequest]:
        return self._storage.list_merge_requests(branch_id=branch_id, status=status)

    # ---------- Conflict ----------

    def save_conflicts(self, mr_id: str, conflicts: List[Conflict]) -> None:
        self._storage.save_conflicts(mr_id, conflicts)

    def list_conflicts(self, mr_id: str) -> List[Conflict]:
        return self._storage.list_conflicts(mr_id)

    def update_conflict_resolution(
        self,
        conflict_id: str,
        resolution: ConflictResolution,
        resolved_value: Any,
        resolved_by: str,
    ) -> Conflict:
        return self._storage.update_conflict_resolution(
            conflict_id, resolution, resolved_value, resolved_by
        )
