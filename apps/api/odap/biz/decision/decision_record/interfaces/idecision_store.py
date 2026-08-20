"""决策存储抽象接口（ADR-076 §5.1 可替换原则）"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from odap.biz.decision.decision_record.models import (
    CausalLinkType,
    DecisionCausalLink,
    DecisionChain,
    DecisionImpact,
    DecisionOutcome,
    DecisionRecord,
)


class IDecisionStore(ABC):
    """决策图存储接口。所有查询必须携带 workspace_id/group_id 双轨过滤。"""

    @abstractmethod
    async def ensure_indices(self) -> None:
        """幂等创建索引与约束（应用启动/首次使用时调用）。"""

    @abstractmethod
    async def save_decision_node(self, record: DecisionRecord, embedder: Any = None) -> str:
        """EntityNode 三步法保存 Decision 节点 + SET 扩展属性。返回 decision_id。"""

    @abstractmethod
    async def get_decision(self, decision_id: str, workspace_id: str) -> Optional[DecisionRecord]:
        """按 ID 读取（隔离条件：decision_id AND workspace_id）。"""

    @abstractmethod
    async def create_derived_from_edges(
        self,
        decision_id: str,
        workspace_id: str,
        evidence_entity_ids: List[str],
        evidence_episode_ids: List[str],
    ) -> None:
        """建立 Decision -[:DERIVED_FROM]-> Entity/Episodic 证据边。"""

    @abstractmethod
    async def add_causal_link(self, link: DecisionCausalLink) -> None:
        """建立因果边（调用方已完成同空间校验与环检测）。"""

    @abstractmethod
    async def has_caused_by_path(
        self, from_decision_id: str, to_decision_id: str, workspace_id: str, max_hops: int = 10
    ) -> bool:
        """检测 from -[:CAUSED_BY*]-> to 是否已存在路径（用于新边环检测）。"""

    @abstractmethod
    async def create_triggered_edge(
        self, decision_id: str, workspace_id: str, action_record: Dict[str, Any]
    ) -> None:
        """建立 Decision -[:TRIGGERED]-> ActionRecord 边（ActionRecord 为轻量节点）。"""

    @abstractmethod
    async def trace_chain(self, decision_id: str, workspace_id: str, max_hops: int = 3) -> Optional[DecisionChain]:
        """因果链追溯：证据实体/Episode + CAUSED_BY 上游链 + PRECEDENT_FOR 先例。"""

    @abstractmethod
    async def find_similar_by_text(
        self, workspace_id: str, query: str, top_k: int = 5
    ) -> List[DecisionRecord]:
        """Cypher 文本扫描降级检索（向量检索不可用时）。"""

    @abstractmethod
    async def analyze_impact(
        self, decision_id: str, workspace_id: str, max_hops: int = 3
    ) -> Optional[DecisionImpact]:
        """影响分析：下游决策 + 目标对象变化 + 协同证据决策（查询而非监听）。"""

    @abstractmethod
    async def update_outcome(
        self,
        decision_id: str,
        workspace_id: str,
        outcome: DecisionOutcome,
        outcome_details: Dict[str, Any],
        feedback_summary: Optional[str] = None,
    ) -> bool:
        """结果回填。更新条件必须含 decision_id AND workspace_id。"""

    @abstractmethod
    def edge_type_values(self) -> List[str]:
        """返回支持的因果边类型（CausalLinkType 值列表）。"""


def causal_edge_types() -> List[str]:
    return [t.value for t in CausalLinkType]
