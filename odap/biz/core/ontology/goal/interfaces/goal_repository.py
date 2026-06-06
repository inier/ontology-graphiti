"""GoalRepository 抽象接口 (T419)

定义 OntoFlow Goal 仓储的方法签名。实现层 (GoalRepositoryImpl) 负责
SQLite 持久化，存储层 (SQLiteGoalStorage) 仅做 dict ↔ row 转换。

调用链: routes.py -> services/ -> repository -> storage
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..models import ChangeProposal, Goal, ImpactAnalysis


class GoalRepository(ABC):
    """OntoFlow Goal 仓储抽象基类"""

    # ---------- Goal CRUD ----------

    @abstractmethod
    def save_goal(self, goal: Goal) -> Goal:
        """保存或更新 Goal (upsert)"""
        raise NotImplementedError

    @abstractmethod
    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """根据 ID 获取 Goal；不存在返回 None"""
        raise NotImplementedError

    @abstractmethod
    def list_goals(
        self,
        workspace_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页列出 Goal；可按 status / workspace_id 过滤

        返回格式: {"goals": [Goal, ...], "total": N, "page": P, "page_size": S}
        """
        raise NotImplementedError

    @abstractmethod
    def update_goal(self, goal: Goal) -> Goal:
        """更新 Goal 整体 (upsert)"""
        raise NotImplementedError

    @abstractmethod
    def delete_goal(self, goal_id: str) -> bool:
        """删除 Goal；级联删除其下的 ChangeProposal/ImpactAnalysis"""
        raise NotImplementedError

    # ---------- ChangeProposal CRUD ----------

    @abstractmethod
    def save_proposal(self, proposal: ChangeProposal) -> ChangeProposal:
        """保存或更新 ChangeProposal (upsert)"""
        raise NotImplementedError

    @abstractmethod
    def get_proposal(self, proposal_id: str) -> Optional[ChangeProposal]:
        """根据 ID 获取 ChangeProposal；不存在返回 None"""
        raise NotImplementedError

    @abstractmethod
    def list_proposals(
        self,
        goal_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[ChangeProposal]:
        """列出 ChangeProposal；可按 goal_id / status 过滤"""
        raise NotImplementedError

    @abstractmethod
    def update_proposal(self, proposal: ChangeProposal) -> ChangeProposal:
        """更新 ChangeProposal (upsert)"""
        raise NotImplementedError

    # ---------- ImpactAnalysis CRUD ----------

    @abstractmethod
    def save_impact(self, impact: ImpactAnalysis) -> ImpactAnalysis:
        """保存或更新 ImpactAnalysis (upsert)"""
        raise NotImplementedError

    @abstractmethod
    def get_impact(self, impact_id: str) -> Optional[ImpactAnalysis]:
        """根据 ID 获取 ImpactAnalysis；不存在返回 None"""
        raise NotImplementedError

    # ---------- Lineage (血缘) ----------

    @abstractmethod
    def get_goal_lineage(self, goal_id: str) -> Dict[str, Any]:
        """获取 Goal 的血缘树

        返回格式:
        {
            "goal": Goal,
            "ancestors": [祖先 Goal 列表，按层级排序],
            "children": [子 Goal 列表],
            "proposals": [该 Goal 关联的所有 ChangeProposal 列表],
        }
        """
        raise NotImplementedError


__all__ = ["GoalRepository"]
