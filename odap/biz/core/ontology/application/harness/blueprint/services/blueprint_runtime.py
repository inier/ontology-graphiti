from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeExecutionState(str, Enum):
    WAITING = "waiting"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NodeExecution:
    node_id: str
    node_type: str
    state: NodeExecutionState = NodeExecutionState.WAITING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class BlueprintExecution:
    execution_id: str
    blueprint_id: str
    blueprint_name: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    node_executions: Dict[str, NodeExecution] = field(default_factory=dict)
    execution_order: List[str] = field(default_factory=list)
    current_step: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class BlueprintRuntimeEngine:
    _instance: Optional["BlueprintRuntimeEngine"] = None

    @classmethod
    def get_instance(cls, blueprint_service=None):
        if cls._instance is None:
            cls._instance = cls(blueprint_service)
        return cls._instance

    def __init__(self, blueprint_service=None):
        self._blueprint_service = blueprint_service
        self._executions: Dict[str, BlueprintExecution] = {}
        self._node_handlers: Dict[str, callable] = {}

    def register_node_handler(self, node_type: str, handler: callable):
        self._node_handlers[node_type] = handler

    def start_execution(self, execution_id: str, blueprint_id: str,
                        metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        blueprint = self._load_blueprint(blueprint_id)
        if not blueprint:
            return {"status": "error", "message": "Blueprint not found"}
        nodes = blueprint.get("nodes", [])
        edges = blueprint.get("edges", [])
        if not nodes:
            return {"status": "error", "message": "Blueprint has no nodes"}
        execution_order = self._compute_execution_order(nodes, edges)
        node_executions = {}
        for node in nodes:
            node_executions[node.get("node_id", "")] = NodeExecution(
                node_id=node.get("node_id", ""),
                node_type=node.get("node_type", "")
            )
        execution = BlueprintExecution(
            execution_id=execution_id, blueprint_id=blueprint_id,
            blueprint_name=blueprint.get("name", ""),
            node_executions=node_executions,
            execution_order=execution_order,
            metadata=metadata or {}
        )
        self._executions[execution_id] = execution
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.now().isoformat()
        self._advance_execution(execution_id)
        return {
            "status": "success", "execution_id": execution_id,
            "blueprint_id": blueprint_id, "execution_status": execution.status,
            "execution_order": execution_order
        }

    def pause_execution(self, execution_id: str) -> Dict[str, Any]:
        if execution_id not in self._executions:
            return {"status": "error", "message": "Execution not found"}
        execution = self._executions[execution_id]
        if execution.status != ExecutionStatus.RUNNING:
            return {"status": "error", "message": f"Cannot pause execution in {execution.status} state"}
        execution.status = ExecutionStatus.PAUSED
        return {"status": "success", "execution_id": execution_id, "execution_status": execution.status}

    def resume_execution(self, execution_id: str) -> Dict[str, Any]:
        if execution_id not in self._executions:
            return {"status": "error", "message": "Execution not found"}
        execution = self._executions[execution_id]
        if execution.status != ExecutionStatus.PAUSED:
            return {"status": "error", "message": f"Cannot resume execution in {execution.status} state"}
        execution.status = ExecutionStatus.RUNNING
        self._advance_execution(execution_id)
        return {"status": "success", "execution_id": execution_id, "execution_status": execution.status}

    def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        if execution_id not in self._executions:
            return {"status": "error", "message": "Execution not found"}
        execution = self._executions[execution_id]
        execution.status = ExecutionStatus.CANCELLED
        execution.completed_at = datetime.now().isoformat()
        return {"status": "success", "execution_id": execution_id, "execution_status": execution.status}

    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        if execution_id not in self._executions:
            return {"status": "error", "message": "Execution not found"}
        e = self._executions[execution_id]
        return {
            "status": "success", "execution_id": e.execution_id,
            "blueprint_id": e.blueprint_id, "blueprint_name": e.blueprint_name,
            "execution_status": e.status, "current_step": e.current_step,
            "total_steps": len(e.execution_order), "started_at": e.started_at,
            "completed_at": e.completed_at, "error": e.error,
            "node_states": {
                nid: {"state": ne.state, "output": ne.output, "error": ne.error}
                for nid, ne in e.node_executions.items()
            }
        }

    def list_executions(self, blueprint_id: Optional[str] = None,
                        status: Optional[str] = None) -> Dict[str, Any]:
        executions = list(self._executions.values())
        if blueprint_id:
            executions = [e for e in executions if e.blueprint_id == blueprint_id]
        if status:
            executions = [e for e in executions if e.status == status]
        return {
            "status": "success", "count": len(executions),
            "executions": [
                {
                    "execution_id": e.execution_id, "blueprint_id": e.blueprint_id,
                    "blueprint_name": e.blueprint_name, "status": e.status,
                    "started_at": e.started_at, "completed_at": e.completed_at
                }
                for e in executions
            ]
        }

    def _load_blueprint(self, blueprint_id: str) -> Optional[Dict[str, Any]]:
        if not self._blueprint_service:
            return None
        try:
            result = self._blueprint_service.get_blueprint(blueprint_id)
            if result.get("status") == "success":
                return result
        except Exception:
            pass
        return None

    def _compute_execution_order(self, nodes: List[Dict], edges: List[Dict]) -> List[str]:
        in_degree: Dict[str, int] = {}
        adj: Dict[str, List[str]] = {}
        for node in nodes:
            nid = node.get("node_id", "")
            in_degree[nid] = 0
            adj[nid] = []
        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            if source in adj and target in in_degree:
                adj[source].append(target)
                in_degree[target] += 1
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order = []
        while queue:
            node_id = queue.pop(0)
            order.append(node_id)
            for neighbor in adj.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        for node in nodes:
            nid = node.get("node_id", "")
            if nid not in order:
                order.append(nid)
        return order

    def _advance_execution(self, execution_id: str):
        execution = self._executions[execution_id]
        if execution.status != ExecutionStatus.RUNNING:
            return
        while execution.current_step < len(execution.execution_order):
            node_id = execution.execution_order[execution.current_step]
            node_exec = execution.node_executions.get(node_id)
            if not node_exec:
                execution.current_step += 1
                continue
            node_exec.state = NodeExecutionState.RUNNING
            node_exec.started_at = datetime.now().isoformat()
            handler = self._node_handlers.get(node_exec.node_type)
            if handler:
                try:
                    result = handler(node_id, node_exec.node_type, execution)
                    node_exec.output = result if isinstance(result, dict) else {"result": result}
                    node_exec.state = NodeExecutionState.COMPLETED
                    node_exec.completed_at = datetime.now().isoformat()
                except Exception as e:
                    node_exec.state = NodeExecutionState.FAILED
                    node_exec.error = str(e)
                    execution.status = ExecutionStatus.FAILED
                    execution.error = f"Node {node_id} failed: {str(e)}"
                    execution.completed_at = datetime.now().isoformat()
                    return
            else:
                node_exec.output = {"simulated": True}
                node_exec.state = NodeExecutionState.COMPLETED
                node_exec.completed_at = datetime.now().isoformat()
            execution.current_step += 1
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = datetime.now().isoformat()
