import logging
from typing import Dict, Any, List, Optional

from odap.biz.simulation.simulation_deduction.impl.deduction_engine_impl import DeductionEngineImpl

logger = logging.getLogger(__name__)


class DeductionService:
    def __init__(self):
        self._engine = DeductionEngineImpl()

    def create_scenario(self, name: str, description: str,
                        source_recommendation_id: Optional[str] = None,
                        source_analysis_id: Optional[str] = None,
                        target_object_id: str = "",
                        target_object_type: str = "") -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(
                        self._engine.create_scenario(
                            name, description, source_recommendation_id,
                            source_analysis_id, target_object_id, target_object_type
                        )
                    )
                ).result(timeout=30)
            return result
        except RuntimeError:
            return asyncio.run(
                self._engine.create_scenario(
                    name, description, source_recommendation_id,
                    source_analysis_id, target_object_id, target_object_type
                )
            )

    def load_ontology_conditions(self, scenario_id: str) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(self._engine.load_ontology_conditions(scenario_id))
                ).result(timeout=30)
            return result
        except RuntimeError:
            return asyncio.run(self._engine.load_ontology_conditions(scenario_id))

    def add_execution_chain(self, scenario_id: str, name: str,
                             description: str, steps: List[Dict[str, Any]],
                             conditions: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(
                        self._engine.add_execution_chain(
                            scenario_id, name, description, steps, conditions
                        )
                    )
                ).result(timeout=30)
            return result
        except RuntimeError:
            return asyncio.run(
                self._engine.add_execution_chain(
                    scenario_id, name, description, steps, conditions
                )
            )

    def delete_chain(self, scenario_id: str, chain_id: str) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(self._engine.delete_chain(scenario_id, chain_id))
                ).result(timeout=30)
            return result
        except RuntimeError:
            return asyncio.run(self._engine.delete_chain(scenario_id, chain_id))

    def update_chain(self, scenario_id: str, chain_id: str,
                      name: str = None, description: str = None,
                      steps: list = None, conditions: list = None) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(
                        self._engine.update_chain(scenario_id, chain_id, name, description, steps, conditions)
                    )
                ).result(timeout=30)
            return result
        except RuntimeError:
            return asyncio.run(
                self._engine.update_chain(scenario_id, chain_id, name, description, steps, conditions)
            )

    def update_condition(self, scenario_id: str, condition_id: str,
                          value: Any) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(self._engine.update_condition(scenario_id, condition_id, value))
                ).result(timeout=30)
            return result
        except RuntimeError:
            return asyncio.run(self._engine.update_condition(scenario_id, condition_id, value))

    def simulate_chain(self, scenario_id: str, chain_id: str) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(self._engine.simulate_chain(scenario_id, chain_id))
                ).result(timeout=60)
            return result
        except RuntimeError:
            return asyncio.run(self._engine.simulate_chain(scenario_id, chain_id))

    def simulate_all_chains(self, scenario_id: str) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(self._engine.simulate_all_chains(scenario_id))
                ).result(timeout=120)
            return result
        except RuntimeError:
            return asyncio.run(self._engine.simulate_all_chains(scenario_id))

    def compare_chains(self, scenario_id: str, chain_ids: List[str]) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(self._engine.compare_chains(scenario_id, chain_ids))
                ).result(timeout=120)
            return result
        except RuntimeError:
            return asyncio.run(self._engine.compare_chains(scenario_id, chain_ids))

    def get_scenario(self, scenario_id: str) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(self._engine.get_scenario(scenario_id))
                ).result(timeout=30)
            return result
        except RuntimeError:
            return asyncio.run(self._engine.get_scenario(scenario_id))

    def list_scenarios(self, filters: Dict[str, Any] = None,
                        page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(self._engine.list_scenarios(filters, page, page_size))
                ).result(timeout=30)
            return result
        except RuntimeError:
            return asyncio.run(self._engine.list_scenarios(filters, page, page_size))

    def delete_scenario(self, scenario_id: str) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(self._engine.delete_scenario(scenario_id))
                ).result(timeout=30)
            return result
        except RuntimeError:
            return asyncio.run(self._engine.delete_scenario(scenario_id))
