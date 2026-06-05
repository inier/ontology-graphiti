import logging
from typing import Dict, Any, List, Optional

from ..storage import SQLiteRuntimeStorage
from ..impl.function_engine import FunctionEngine
from ..impl.action_contract_engine import ActionContractEngine
from ..impl.state_propagation_engine import StatePropagationEngine
from ..impl.aggregate_engine import AggregateEngine
from ..impl.world_state_manager import WorldStateManager
from ..impl.action_trigger_engine import ActionTriggerEngine

logger = logging.getLogger("runtime_service")


class OntologyRuntimeService:
    _instance = None

    @classmethod
    def get_instance(cls) -> "OntologyRuntimeService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, storage: SQLiteRuntimeStorage = None):
        self.storage = storage or SQLiteRuntimeStorage()
        self.function_engine = FunctionEngine(self.storage)
        self.contract_engine = ActionContractEngine(self.storage)
        self.propagation_engine = StatePropagationEngine(self.storage)
        self.aggregate_engine = AggregateEngine(self.storage)
        self.world_state_manager = WorldStateManager(self.storage)
        self.trigger_engine = ActionTriggerEngine(
            storage=self.storage,
            function_engine=self.function_engine,
            propagation_engine=self.propagation_engine,
        )

    # ── Function ──

    def register_function(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.function_engine.register_function(data)
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def get_function(self, function_id: str) -> Dict[str, Any]:
        result = self.function_engine.get_function(function_id)
        if not result:
            return {"status": "error", "message": f"Function {function_id} not found"}
        return result

    def list_functions(self, function_type: Optional[str] = None, target_object_type: Optional[str] = None) -> Dict[str, Any]:
        functions = self.function_engine.list_functions(function_type=function_type, target_object_type=target_object_type)
        return {"functions": functions, "count": len(functions)}

    def execute_function(self, function_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return self.function_engine.execute_function(function_id, context)

    def update_function(self, function_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        result = self.function_engine.update_function(function_id, updates)
        if not result:
            return {"status": "error", "message": f"Function {function_id} not found"}
        return result

    def delete_function(self, function_id: str) -> Dict[str, Any]:
        if self.function_engine.delete_function(function_id):
            return {"status": "success", "message": f"Function {function_id} deleted"}
        return {"status": "error", "message": f"Function {function_id} not found"}

    # ── ActionContract ──

    def create_contract(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.contract_engine.create_contract(data)
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def get_contract(self, contract_id: str) -> Dict[str, Any]:
        result = self.contract_engine.get_contract(contract_id)
        if not result:
            return {"status": "error", "message": f"Contract {contract_id} not found"}
        return result

    def get_contract_by_action(self, action_type_id: str) -> Dict[str, Any]:
        result = self.contract_engine.get_contract_by_action(action_type_id)
        if not result:
            return {"status": "error", "message": f"No contract found for action {action_type_id}"}
        return result

    def list_contracts(self) -> Dict[str, Any]:
        contracts = self.contract_engine.list_contracts()
        return {"contracts": contracts, "count": len(contracts)}

    def verify_contract(self, contract_id: str) -> Dict[str, Any]:
        mutations = self.propagation_engine.query_mutations(limit=1000)
        return self.contract_engine.verify_contract(contract_id, mutations)

    def update_contract(self, contract_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        result = self.contract_engine.update_contract(contract_id, updates)
        if not result:
            return {"status": "error", "message": f"Contract {contract_id} not found"}
        return result

    def delete_contract(self, contract_id: str) -> Dict[str, Any]:
        if self.contract_engine.delete_contract(contract_id):
            return {"status": "success", "message": f"Contract {contract_id} deleted"}
        return {"status": "error", "message": f"Contract {contract_id} not found"}

    # ── StatePropagation ──

    def build_propagation_graph(self) -> Dict[str, Any]:
        contracts = self.contract_engine.list_contracts()
        if not contracts:
            return {"status": "error", "message": "No action contracts found. Create contracts first."}
        return self.propagation_engine.build_propagation_graph(contracts)

    def get_propagation_graph(self, graph_id: str) -> Dict[str, Any]:
        result = self.propagation_engine.get_propagation_graph(graph_id)
        if not result:
            return {"status": "error", "message": f"Propagation graph {graph_id} not found"}
        return result

    def compute_impact(self, graph_id: str, action_type_id: str, target_object_type: str) -> Dict[str, Any]:
        return self.propagation_engine.compute_impact(graph_id, action_type_id, target_object_type)

    def record_mutation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.propagation_engine.record_mutation(data)

    def query_mutations(self, target_object_id: Optional[str] = None, action_type_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        mutations = self.propagation_engine.query_mutations(target_object_id=target_object_id, action_type_id=action_type_id, limit=limit)
        return {"mutations": mutations, "count": len(mutations)}

    # ── Aggregate ──

    def register_aggregate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.aggregate_engine.register_aggregate(data)
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def get_aggregate(self, agg_id: str) -> Dict[str, Any]:
        result = self.aggregate_engine.get_aggregate(agg_id)
        if not result:
            return {"status": "error", "message": f"Aggregate {agg_id} not found"}
        return result

    def list_aggregates(self, target_object_type: Optional[str] = None) -> Dict[str, Any]:
        aggregates = self.aggregate_engine.list_aggregates(target_object_type=target_object_type)
        return {"aggregates": aggregates, "count": len(aggregates)}

    def compute_aggregate(self, agg_id: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.aggregate_engine.compute_aggregate(agg_id, data)

    def delete_aggregate(self, agg_id: str) -> Dict[str, Any]:
        if self.aggregate_engine.delete_aggregate(agg_id):
            return {"status": "success", "message": f"Aggregate {agg_id} deleted"}
        return {"status": "error", "message": f"Aggregate {agg_id} not found"}

    # ── WorldState ──

    def capture_snapshot(self, name: str, scenario_id: Optional[str] = None, is_baseline: bool = False) -> Dict[str, Any]:
        return self.world_state_manager.capture_snapshot(name, scenario_id=scenario_id, is_baseline=is_baseline)

    def get_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        result = self.world_state_manager.get_snapshot(snapshot_id)
        if not result:
            return {"status": "error", "message": f"Snapshot {snapshot_id} not found"}
        return result

    def list_snapshots(self, scenario_id: Optional[str] = None) -> Dict[str, Any]:
        snapshots = self.world_state_manager.list_snapshots(scenario_id=scenario_id)
        return {"snapshots": snapshots, "count": len(snapshots)}

    def compare_snapshots(self, snapshot_id_a: str, snapshot_id_b: str) -> Dict[str, Any]:
        return self.world_state_manager.compare_snapshots(snapshot_id_a, snapshot_id_b)

    def delete_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        if self.world_state_manager.delete_snapshot(snapshot_id):
            return {"status": "success", "message": f"Snapshot {snapshot_id} deleted"}
        return {"status": "error", "message": f"Snapshot {snapshot_id} not found"}

    # ── ActionTrigger ──

    def register_trigger(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.trigger_engine.register_trigger(data)
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def get_trigger(self, trigger_id: str) -> Dict[str, Any]:
        result = self.trigger_engine.get_trigger(trigger_id)
        if not result:
            return {"status": "error", "message": f"Trigger {trigger_id} not found"}
        return result

    def list_triggers(self, target_object_type: Optional[str] = None, is_active: Optional[bool] = None) -> Dict[str, Any]:
        triggers = self.trigger_engine.list_triggers(target_object_type=target_object_type, is_active=is_active)
        return {"triggers": triggers, "count": len(triggers)}

    def delete_trigger(self, trigger_id: str) -> Dict[str, Any]:
        if self.trigger_engine.delete_trigger(trigger_id):
            return {"status": "success", "message": f"Trigger {trigger_id} deleted"}
        return {"status": "error", "message": f"Trigger {trigger_id} not found"}

    def evaluate_triggers(self, object_type: str, object_id: str, state_changes: Dict[str, Any]) -> Dict[str, Any]:
        matched = self.trigger_engine.evaluate_triggers(object_type, object_id, state_changes)
        return {"matched_triggers": matched, "count": len(matched)}

    def execute_trigger(self, trigger_id: str, triggered_by: Dict[str, Any]) -> Dict[str, Any]:
        return self.trigger_engine.execute_trigger(trigger_id, triggered_by)

    def get_trigger_history(self, trigger_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        executions = self.trigger_engine.get_execution_history(trigger_id=trigger_id, limit=limit)
        return {"executions": executions, "count": len(executions)}
