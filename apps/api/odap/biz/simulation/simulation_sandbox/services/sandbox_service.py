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

    def stop_sandbox(self, sandbox_id: str) -> Dict[str, Any]:
        """停止沙箱。

        底层 `SandboxManager.stop_sandbox` 一直存在，但 service 层与 HTTP 路由都没转发，
        导致**运行中的沙箱既不能停止、也不能销毁**（destroy 对 running 会明确拒绝），
        前端只能调 `/stop` 打到一个不存在的端点。此处补上转发。
        """
        return self._manager.stop_sandbox(sandbox_id)

    def export_results(self, sandbox_id: str, approved_by: str = "") -> Dict[str, Any]:
        return self._manager.export_results(sandbox_id, approved_by)

    def list_sandboxes(self, workspace_id: str = None) -> List[Dict[str, Any]]:
        return self._manager.list_sandboxes(workspace_id)
