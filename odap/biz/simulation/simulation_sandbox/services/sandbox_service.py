import logging
from typing import Dict, Any, List

from ..impl.sandbox_manager import get_sandbox_manager

logger = logging.getLogger(__name__)


class SandboxService:
    def __init__(self):
        self._manager = get_sandbox_manager()

    def create_sandbox(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return self._manager.create_sandbox(config)

    async def run_simulation(self, sandbox_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return await self._manager.run_simulation(sandbox_id, params)

    def get_sandbox_status(self, sandbox_id: str) -> Dict[str, Any]:
        return self._manager.get_sandbox_status(sandbox_id)

    def get_sandbox_results(self, sandbox_id: str) -> Dict[str, Any]:
        return self._manager.get_sandbox_results(sandbox_id)

    def destroy_sandbox(self, sandbox_id: str) -> Dict[str, Any]:
        return self._manager.destroy_sandbox(sandbox_id)

    def export_results(self, sandbox_id: str, approved_by: str = "") -> Dict[str, Any]:
        return self._manager.export_results(sandbox_id, approved_by)

    def list_sandboxes(self, workspace_id: str = None) -> List[Dict[str, Any]]:
        return self._manager.list_sandboxes(workspace_id)
