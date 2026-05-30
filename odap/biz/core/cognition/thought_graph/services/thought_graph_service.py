from typing import Dict, Any, List, Optional

from ..storage import ThoughtGraphStorage
from ..models.types import ThoughtType, ReasoningMethod, ThoughtNode, ReasoningChain


class ThoughtGraphService:
    _instance = None

    @classmethod
    def get_instance(cls, storage=None):
        if cls._instance is None:
            cls._instance = cls(storage)
        return cls._instance

    def __init__(self, storage=None):
        self.storage = storage or ThoughtGraphStorage()

    def add_thought(self, thought_type, content, premises=None, conclusion="",
                    confidence=0.5, reasoning_method="heuristic",
                    source_entity_ids=None, source_scenario_id=None,
                    agent_id=None, metadata=None):
        thought = ThoughtNode(
            thought_type=ThoughtType(thought_type) if isinstance(thought_type, str) else thought_type,
            content=content,
            premises=premises or [],
            conclusion=conclusion,
            confidence=confidence,
            reasoning_method=ReasoningMethod(reasoning_method) if isinstance(reasoning_method, str) else reasoning_method,
            source_entity_ids=source_entity_ids or [],
            source_scenario_id=source_scenario_id,
            agent_id=agent_id,
            metadata=metadata or {}
        )
        saved = self.storage.save_thought(thought)
        return {"status": "success", "thought_id": saved.thought_id,
                "thought_type": saved.thought_type.value, "content": saved.content,
                "confidence": saved.confidence}

    def get_thought(self, thought_id):
        thought = self.storage.get_thought(thought_id)
        if not thought:
            return {"status": "error", "message": "Thought not found"}
        return {"status": "success", "thought_id": thought.thought_id,
                "thought_type": thought.thought_type.value, "content": thought.content,
                "premises": thought.premises, "conclusion": thought.conclusion,
                "confidence": thought.confidence,
                "reasoning_method": thought.reasoning_method.value,
                "source_entity_ids": thought.source_entity_ids,
                "source_scenario_id": thought.source_scenario_id,
                "agent_id": thought.agent_id, "metadata": thought.metadata,
                "created_at": thought.created_at}

    def list_thoughts(self, thought_type=None, scenario_id=None, agent_id=None, limit=100):
        thoughts = self.storage.list_thoughts(thought_type, scenario_id, agent_id, limit)
        return {"status": "success", "count": len(thoughts),
                "thoughts": [{"thought_id": t.thought_id, "thought_type": t.thought_type.value,
                              "content": t.content[:100], "confidence": t.confidence,
                              "created_at": t.created_at} for t in thoughts]}

    def delete_thought(self, thought_id):
        result = self.storage.delete_thought(thought_id)
        if not result:
            return {"status": "error", "message": "Thought not found"}
        return {"status": "success", "thought_id": thought_id}

    def create_reasoning_chain(self, name, description="", thought_ids=None,
                               chain_type="sequential", scenario_id=None, metadata=None):
        chain = ReasoningChain(
            name=name, description=description,
            thought_ids=thought_ids or [],
            chain_type=chain_type, scenario_id=scenario_id,
            metadata=metadata or {}
        )
        saved = self.storage.save_chain(chain)
        for i in range(len(saved.thought_ids) - 1):
            self.storage.add_thought_edge(saved.thought_ids[i], saved.thought_ids[i+1],
                                          edge_type="leads_to")
        return {"status": "success", "chain_id": saved.chain_id, "name": saved.name,
                "thought_count": len(saved.thought_ids)}

    def get_chain(self, chain_id):
        chain = self.storage.get_chain(chain_id)
        if not chain:
            return {"status": "error", "message": "Chain not found"}
        thoughts = []
        for tid in chain.thought_ids:
            t = self.storage.get_thought(tid)
            if t:
                thoughts.append({"thought_id": t.thought_id, "thought_type": t.thought_type.value,
                                 "content": t.content, "confidence": t.confidence})
        return {"status": "success", "chain_id": chain.chain_id, "name": chain.name,
                "description": chain.description, "chain_type": chain.chain_type,
                "thoughts": thoughts, "scenario_id": chain.scenario_id,
                "created_at": chain.created_at}

    def list_chains(self, scenario_id=None, limit=100):
        chains = self.storage.list_chains(scenario_id, limit)
        return {"status": "success", "count": len(chains),
                "chains": [{"chain_id": c.chain_id, "name": c.name,
                            "thought_count": len(c.thought_ids),
                            "created_at": c.created_at} for c in chains]}

    def delete_chain(self, chain_id):
        result = self.storage.delete_chain(chain_id)
        if not result:
            return {"status": "error", "message": "Chain not found"}
        return {"status": "success", "chain_id": chain_id}

    def link_thoughts(self, source_id, target_id, edge_type="leads_to", weight=1.0):
        edge = self.storage.add_thought_edge(source_id, target_id, edge_type, weight)
        return {"status": "success", **edge}

    def get_thought_graph(self, thought_id, depth=2):
        visited = set()
        nodes = []
        edges = []
        queue = [(thought_id, 0)]
        while queue:
            current_id, current_depth = queue.pop(0)
            if current_id in visited or current_depth > depth:
                continue
            visited.add(current_id)
            thought = self.storage.get_thought(current_id)
            if not thought:
                continue
            nodes.append({"thought_id": thought.thought_id,
                          "thought_type": thought.thought_type.value,
                          "content": thought.content[:80], "confidence": thought.confidence})
            if current_depth < depth:
                thought_edges = self.storage.get_thought_edges(current_id)
                for e in thought_edges:
                    edges.append({"source": e["source_thought_id"],
                                  "target": e["target_thought_id"],
                                  "edge_type": e["edge_type"], "weight": e["weight"]})
                    neighbor = e["target_thought_id"] if e["source_thought_id"] == current_id else e["source_thought_id"]
                    if neighbor not in visited:
                        queue.append((neighbor, current_depth + 1))
        return {"status": "success", "nodes": nodes, "edges": edges}

    def sync_to_graphiti(self, thought_id, graph_manager=None):
        thought = self.storage.get_thought(thought_id)
        if not thought:
            return {"status": "error", "message": "Thought not found"}
        if graph_manager is None:
            from odap.infra.graph import GraphManager
            graph_manager = GraphManager.get_instance()
        try:
            graph_manager.add_entity(
                entity_id=thought.thought_id,
                entity_type="Thought",
                properties={
                    "thought_type": thought.thought_type.value,
                    "content": thought.content,
                    "confidence": thought.confidence,
                    "reasoning_method": thought.reasoning_method.value,
                    "premises": thought.premises,
                    "conclusion": thought.conclusion,
                    "source_entity_ids": thought.source_entity_ids,
                    "scenario_id": thought.source_scenario_id or "",
                    "agent_id": thought.agent_id or ""
                }
            )
            return {"status": "success", "thought_id": thought_id, "synced": True}
        except Exception as e:
            return {"status": "error", "message": str(e)}
