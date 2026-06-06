"""
BranchRepository 抽象基类 (T351)

定义分支 + 合并请求 + 冲突的持久化契约。实现方必须遵守。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from ..models import Branch, Conflict, ConflictResolution, MergeRequest


class BranchRepository(ABC):
    """分支 / 合并请求 / 冲突仓储抽象基类"""

    # ---------- Branch CRUD ----------

    @abstractmethod
    def save(self, branch: Branch) -> Branch:
        """保存 (upsert) 分支"""
        raise NotImplementedError

    @abstractmethod
    def get(self, branch_id: str) -> Optional[Branch]:
        """按 ID 获取分支"""
        raise NotImplementedError

    @abstractmethod
    def list(self) -> List[Branch]:
        """列出所有分支"""
        raise NotImplementedError

    @abstractmethod
    def list_by_ontology(self, ontology_id: str) -> List[Branch]:
        """列出指定本体的所有分支"""
        raise NotImplementedError

    @abstractmethod
    def get_active(self, ontology_id: str) -> Optional[Branch]:
        """获取指定本体的活跃分支（仅 1 个）"""
        raise NotImplementedError

    @abstractmethod
    def delete(self, branch_id: str) -> bool:
        """删除分支（级联删 MR 与冲突）"""
        raise NotImplementedError

    # ---------- MergeRequest ----------

    @abstractmethod
    def save_merge_request(self, mr: MergeRequest) -> MergeRequest:
        """保存 (upsert) 合并请求"""
        raise NotImplementedError

    @abstractmethod
    def get_merge_request(self, mr_id: str) -> Optional[MergeRequest]:
        """按 ID 获取合并请求"""
        raise NotImplementedError

    @abstractmethod
    def list_merge_requests(
        self,
        branch_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[MergeRequest]:
        """列出合并请求（可按 branch_id 或 status 过滤）"""
        raise NotImplementedError

    # ---------- Conflict ----------

    @abstractmethod
    def save_conflicts(self, mr_id: str, conflicts: List[Conflict]) -> None:
        """批量保存冲突（同 MR 的旧冲突会被替换）"""
        raise NotImplementedError

    @abstractmethod
    def list_conflicts(self, mr_id: str) -> List[Conflict]:
        """列出 MR 的所有冲突"""
        raise NotImplementedError

    @abstractmethod
    def update_conflict_resolution(
        self,
        conflict_id: str,
        resolution: ConflictResolution,
        resolved_value: Any,
        resolved_by: str,
    ) -> Conflict:
        """更新冲突的解决状态"""
        raise NotImplementedError
