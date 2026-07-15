"""Candidate Store — CandidateRepository 协议抽象（Protocol + ABC 双重导出）。

用途：被其他子服务（approval_workflow / quality_gate / ol_pipeline / usl_writeback）
      通过依赖注入消费，**禁止任何子服务直接 import candidate_store.storage**。

设计要点：
1. 运行时使用 `typing_extensions.Protocol` + `runtime_checkable`，
   允许不继承 ABC 的 SQLiteCandidateStorage 仍然 satisfy 类型（structural subtyping）
2. 同时提供 `CandidateRepositoryABC`（抽象基类），子类可选择性继承来强制约束
3. 仅列 cross-service 实际调用到的方法，非全量 API（全量 API 在 candidate_service）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class CandidateRepository(Protocol):
    """跨子服务最小 Candidate 仓储契约（structural subtyping）。"""

    def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 获取候选，返回扁平 dict；不存在返回 None。

        注意：类型层面这是 Protocol 签名（不需要 raise NotImplementedError），
              但运行时如果实现类未定义该方法，runtime_checkable 会在 isinstance 时给出 False。
        """

    def update_status(
        self,
        candidate_id: str,
        new_status: str,
        *,
        quality_tier: Optional[str] = None,
        total_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """更新候选状态（可选同时写质量分层/总分/元数据）。返回是否 update 成功。"""

    def list_pending_review(
        self,
        *,
        approval_level: Optional[str] = None,
        domain_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """列出待审核候选（PENDING_REVIEW / AUDITOR_PENDING / ADMIN_PENDING）。

        参数：
          approval_level: 'L1' 仅返回 schema_auditor 待审；'L2' 仅管理员待审；None 全部
          domain_id:     可选领域过滤
        返回 (候选字典列表, 总数)
        """

    def count_by_status(self, *, status: Optional[str] = None) -> Dict[str, int]:
        """按状态计数。若 status=None 返回全状态字典；否则返回 {status: N}。"""


class CandidateRepositoryABC(ABC):
    """跨子服务 Candidate 仓储 ABC（强制子类必须实现 4 个方法）。

    与 CandidateRepository Protocol 完全等价的 API 面，供使用 ABC 模式的实现类继承。
    """

    @abstractmethod
    def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def update_status(
        self,
        candidate_id: str,
        new_status: str,
        *,
        quality_tier: Optional[str] = None,
        total_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_pending_review(
        self,
        *,
        approval_level: Optional[str] = None,
        domain_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        raise NotImplementedError

    @abstractmethod
    def count_by_status(self, *, status: Optional[str] = None) -> Dict[str, int]:
        raise NotImplementedError


__all__ = ["CandidateRepository", "CandidateRepositoryABC"]
