from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class IFunctionEngine(ABC):
    @abstractmethod
    def register_function(self, function_data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_function(self, function_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_functions(self, function_type: Optional[str] = None, target_object_type: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def execute_function(self, function_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def update_function(self, function_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def delete_function(self, function_id: str) -> bool:
        ...


class IActionContractEngine(ABC):
    @abstractmethod
    def create_contract(self, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_contract(self, contract_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_contract_by_action(self, action_type_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_contracts(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def verify_contract(self, contract_id: str, mutation_log: List[Dict[str, Any]]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def update_contract(self, contract_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def delete_contract(self, contract_id: str) -> bool:
        ...


class IStatePropagationEngine(ABC):
    @abstractmethod
    def build_propagation_graph(self, contracts: List[Dict[str, Any]]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_propagation_graph(self, graph_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def compute_impact(self, graph_id: str, action_type_id: str, target_object_type: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def record_mutation(self, mutation_data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def query_mutations(self, target_object_id: Optional[str] = None, action_type_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        ...


class IAggregateEngine(ABC):
    @abstractmethod
    def register_aggregate(self, aggregate_data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_aggregate(self, agg_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_aggregates(self, target_object_type: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def compute_aggregate(self, agg_id: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def delete_aggregate(self, agg_id: str) -> bool:
        ...


class IWorldStateManager(ABC):
    @abstractmethod
    def capture_snapshot(self, name: str, scenario_id: Optional[str] = None, is_baseline: bool = False) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_snapshots(self, scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def compare_snapshots(self, snapshot_id_a: str, snapshot_id_b: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def delete_snapshot(self, snapshot_id: str) -> bool:
        ...


class IActionTriggerEngine(ABC):
    @abstractmethod
    def register_trigger(self, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_trigger(self, trigger_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_triggers(self, target_object_type: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def delete_trigger(self, trigger_id: str) -> bool:
        ...

    @abstractmethod
    def evaluate_triggers(self, object_type: str, object_id: str, state_changes: Dict[str, Any]) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def execute_trigger(self, trigger_id: str, triggered_by: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_execution_history(self, trigger_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        ...
