from typing import List, Dict, Any, Optional


class IDeductionEngine:
    async def create_scenario(self, name: str, description: str,
                              source_recommendation_id: Optional[str] = None,
                              source_analysis_id: Optional[str] = None,
                              target_object_id: str = "",
                              target_object_type: str = "") -> Dict[str, Any]:
        raise NotImplementedError

    async def load_ontology_conditions(self, scenario_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def add_execution_chain(self, scenario_id: str, name: str,
                                   description: str, steps: List[Dict[str, Any]],
                                   conditions: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError

    async def delete_chain(self, scenario_id: str, chain_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def update_chain(self, scenario_id: str, chain_id: str,
                            name: str = None, description: str = None,
                            steps: List[Dict[str, Any]] = None,
                            conditions: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError

    async def update_condition(self, scenario_id: str, condition_id: str,
                                value: Any) -> Dict[str, Any]:
        raise NotImplementedError

    async def simulate_chain(self, scenario_id: str, chain_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def simulate_all_chains(self, scenario_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def compare_chains(self, scenario_id: str,
                              chain_ids: List[str]) -> Dict[str, Any]:
        raise NotImplementedError

    async def get_scenario(self, scenario_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def list_scenarios(self, filters: Dict[str, Any] = None,
                              page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        raise NotImplementedError

    async def delete_scenario(self, scenario_id: str) -> Dict[str, Any]:
        raise NotImplementedError
