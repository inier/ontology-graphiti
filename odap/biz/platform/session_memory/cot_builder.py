import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CoTNodeType(str, Enum):
    INTENT = "intent"
    ENTITY_LINK = "entity_link"
    CONTEXT_FETCH = "context_fetch"
    RAG_AUGMENT = "rag_augment"
    LLM_INFER = "llm_infer"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DECISION = "decision"
    SYNTHESIS = "synthesis"


class CoTTiming(BaseModel):
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class CoTNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    type: CoTNodeType
    label: str
    detail: str = ""
    status: str = "pending"
    parent_id: Optional[str] = None
    children_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timing: Optional[CoTTiming] = None


class CoTTree(BaseModel):
    root_id: str = ""
    nodes: Dict[str, CoTNode] = Field(default_factory=dict)
    current_focus_id: Optional[str] = None
    version: int = 1


class CoTBuilder:
    def __init__(self):
        self._tree = CoTTree()
        self._id_counter = 0

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"cot_{self._id_counter}"

    def start(self, user_query: str) -> CoTNode:
        root = CoTNode(
            id=self._next_id(),
            type=CoTNodeType.INTENT,
            label=f"用户问题: {user_query[:50]}{'...' if len(user_query) > 50 else ''}",
            detail=user_query,
            status="done",
        )
        self._tree.root_id = root.id
        self._tree.nodes[root.id] = root
        self._tree.current_focus_id = root.id
        return root

    def add_child(self, parent: CoTNode, node_type: CoTNodeType,
                  label: str, detail: str = "") -> CoTNode:
        node = CoTNode(
            id=self._next_id(),
            type=node_type,
            label=label,
            detail=detail,
            parent_id=parent.id,
        )
        parent.children_ids.append(node.id)
        self._tree.nodes[node.id] = node
        self._tree.current_focus_id = node.id
        return node

    def update_status(self, node_id: str, status: str,
                      detail: str = "", timing: Optional[CoTTiming] = None):
        if node_id not in self._tree.nodes:
            logger.warning(f"CoTBuilder: node {node_id} not found")
            return
        node = self._tree.nodes[node_id]
        node.status = status
        if detail:
            node.detail = detail
        if timing:
            node.timing = timing

    def start_timing(self, node_id: str):
        if node_id in self._tree.nodes:
            self._tree.nodes[node_id].timing = CoTTiming(
                started_at=datetime.now(timezone.utc)
            )

    def finish_timing(self, node_id: str):
        if node_id not in self._tree.nodes:
            return
        node = self._tree.nodes[node_id]
        if node.timing and node.timing.started_at:
            node.timing.finished_at = datetime.now(timezone.utc)
            delta = node.timing.finished_at - node.timing.started_at
            node.timing.duration_ms = int(delta.total_seconds() * 1000)

    def get_tree(self) -> CoTTree:
        return self._tree

    def get_node(self, node_id: str) -> Optional[CoTNode]:
        return self._tree.nodes.get(node_id)

    def get_path_to_root(self, node_id: str) -> List[CoTNode]:
        path = []
        current = self._tree.nodes.get(node_id)
        while current:
            path.append(current)
            if current.parent_id:
                current = self._tree.nodes.get(current.parent_id)
            else:
                break
        return path

    def to_serializable(self) -> dict:
        return {
            "rootId": self._tree.root_id,
            "nodes": {
                nid: self._serialize_node(n)
                for nid, n in self._tree.nodes.items()
            },
            "currentFocusId": self._tree.current_focus_id,
            "version": self._tree.version,
        }

    def _serialize_node(self, node: CoTNode) -> dict:
        return {
            "id": node.id,
            "type": node.type.value,
            "label": node.label,
            "detail": node.detail,
            "status": node.status,
            "parentId": node.parent_id,
            "childrenIds": node.children_ids,
            "metadata": node.metadata,
            "timing": node.timing.model_dump() if node.timing else None,
        }
