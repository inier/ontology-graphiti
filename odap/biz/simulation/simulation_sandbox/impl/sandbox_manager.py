import asyncio
import logging
import uuid
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SandboxStatus(str):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DESTROYED = "destroyed"


class SandboxManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._sandboxes: Dict[str, Dict[str, Any]] = {}
        self._results: Dict[str, Dict[str, Any]] = {}
        self._storage = None
        try:
            from ..storage import SQLiteSandboxStorage
            self._storage = SQLiteSandboxStorage()
        except Exception as e:
            logger.warning(f"SQLiteSandboxStorage initialization failed: {e}")
        self._initialized = True

    def _persist_sandbox(self, sandbox: Dict[str, Any]):
        if self._storage is None:
            return
        try:
            persist_data = {k: v for k, v in sandbox.items() if k != "process_handle"}
            self._storage.save_sandbox(persist_data)
        except Exception as e:
            logger.warning(f"Failed to persist sandbox: {e}")

    def _persist_result(self, sandbox_id: str, result: Dict[str, Any]):
        if self._storage is None:
            return
        try:
            self._storage.save_result(sandbox_id, result)
        except Exception as e:
            logger.warning(f"Failed to persist result: {e}")

    def create_sandbox(self, config: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_id = f"sandbox_{uuid.uuid4().hex[:12]}"
        max_memory_mb = config.get("max_memory_mb", 512)
        max_time_seconds = config.get("max_time_seconds", 300)
        workspace_id = config.get("workspace_id", "default")
        scenario_id = config.get("scenario_id", "")

        sandbox = {
            "sandbox_id": sandbox_id,
            "status": SandboxStatus.CREATED,
            "config": {
                "max_memory_mb": max_memory_mb,
                "max_time_seconds": max_time_seconds,
                "workspace_id": workspace_id,
                "scenario_id": scenario_id,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
            "process_handle": None,
            "isolation_level": "process",
        }

        try:
            sandbox["process_handle"] = self._create_isolated_process(sandbox_id, config)
        except Exception as e:
            logger.warning(f"OpenHarness sandbox creation failed, using in-process isolation: {e}")
            sandbox["isolation_level"] = "in_process"

        self._sandboxes[sandbox_id] = sandbox
        self._persist_sandbox(sandbox)
        logger.info(f"Created sandbox {sandbox_id} with isolation level {sandbox['isolation_level']}")
        return {
            "sandbox_id": sandbox_id,
            "status": sandbox["status"],
            "isolation_level": sandbox["isolation_level"],
            "created_at": sandbox["created_at"],
        }

    def _create_isolated_process(self, sandbox_id: str, config: Dict[str, Any]) -> Optional[str]:
        try:
            from openharness.sandbox.session import SandboxSession
            session = SandboxSession(
                sandbox_id=sandbox_id,
                max_memory_mb=config.get("max_memory_mb", 512),
                max_time_seconds=config.get("max_time_seconds", 300),
            )
            return session
        except ImportError:
            raise RuntimeError("OpenHarness sandbox not available")
        except Exception as e:
            raise RuntimeError(f"Sandbox session creation failed: {e}")

    async def run_simulation(self, sandbox_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            if self._storage:
                stored = self._storage.get_sandbox(sandbox_id)
                if stored:
                    self._sandboxes[sandbox_id] = stored
                    sandbox = stored
        if not sandbox:
            return {"status": "error", "message": f"Sandbox {sandbox_id} not found"}
        if sandbox["status"] not in (SandboxStatus.CREATED, SandboxStatus.COMPLETED, SandboxStatus.FAILED, SandboxStatus.TIMEOUT):
            return {"status": "error", "message": f"Sandbox {sandbox_id} is in {sandbox['status']} state, cannot run"}

        sandbox["status"] = SandboxStatus.RUNNING
        sandbox["started_at"] = datetime.now(timezone.utc).isoformat()
        max_time = sandbox["config"]["max_time_seconds"]
        start_time = time.time()

        try:
            result = await asyncio.wait_for(
                self._execute_simulation(sandbox_id, params),
                timeout=max_time,
            )
            sandbox["status"] = SandboxStatus.COMPLETED
            sandbox["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._results[sandbox_id] = result
            self._persist_sandbox(sandbox)
            self._persist_result(sandbox_id, result)
            return result
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            sandbox["status"] = SandboxStatus.TIMEOUT
            sandbox["completed_at"] = datetime.now(timezone.utc).isoformat()
            partial_result = {
                "status": "timeout",
                "sandbox_id": sandbox_id,
                "elapsed_seconds": round(elapsed, 2),
                "message": f"Simulation exceeded time limit of {max_time}s",
                "partial_results": self._results.get(sandbox_id, {}),
            }
            self._results[sandbox_id] = partial_result
            self._persist_sandbox(sandbox)
            self._persist_result(sandbox_id, partial_result)
            return partial_result
        except Exception as e:
            sandbox["status"] = SandboxStatus.FAILED
            sandbox["completed_at"] = datetime.now(timezone.utc).isoformat()
            error_result = {
                "status": "error",
                "sandbox_id": sandbox_id,
                "message": str(e),
            }
            self._results[sandbox_id] = error_result
            self._persist_sandbox(sandbox)
            self._persist_result(sandbox_id, error_result)
            return error_result

    async def _execute_simulation(self, sandbox_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        from ..sandbox import get_simulation_sandbox

        action_type_id = params.get("action_type_id", "")
        target_object_id = params.get("target_object_id", "")
        target_object_type = params.get("target_object_type", "")
        parameters = params.get("parameters", {})
        variant_parameters = params.get("variant_parameters", [])

        from ..schemas import WhatIfScenario
        scenario = WhatIfScenario(
            scenario_id=f"sim_{sandbox_id}",
            action_type_id=action_type_id,
            target_object_id=target_object_id,
            target_object_type=target_object_type,
            parameters=parameters,
            variant_parameters=variant_parameters,
        )

        sim_sandbox = get_simulation_sandbox()
        result = await sim_sandbox.simulate(scenario)

        return {
            "status": "completed",
            "sandbox_id": sandbox_id,
            "scenario_id": result.scenario_id,
            "baseline_metrics": result.baseline_metrics,
            "projected_metrics": result.projected_metrics,
            "metric_changes": [mc.model_dump() for mc in result.metric_changes],
            "risk_assessment": result.risk_assessment,
            "recommendation": result.recommendation,
            "confidence": result.confidence,
            "valid_time": params.get("valid_time", datetime.now(timezone.utc).isoformat()),
            "transaction_time": datetime.now(timezone.utc).isoformat(),
        }

    def get_sandbox_status(self, sandbox_id: str) -> Dict[str, Any]:
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox and self._storage:
            stored = self._storage.get_sandbox(sandbox_id)
            if stored:
                self._sandboxes[sandbox_id] = stored
                sandbox = stored
        if not sandbox:
            return {"status": "error", "message": f"Sandbox {sandbox_id} not found"}
        return {
            "sandbox_id": sandbox_id,
            "status": sandbox["status"],
            "isolation_level": sandbox["isolation_level"],
            "created_at": sandbox["created_at"],
            "started_at": sandbox["started_at"],
            "completed_at": sandbox["completed_at"],
            "config": sandbox["config"],
        }

    def get_sandbox_results(self, sandbox_id: str) -> Dict[str, Any]:
        if sandbox_id not in self._sandboxes:
            if self._storage:
                stored = self._storage.get_sandbox(sandbox_id)
                if stored:
                    self._sandboxes[sandbox_id] = stored
                else:
                    return {"status": "error", "message": f"Sandbox {sandbox_id} not found"}
            else:
                return {"status": "error", "message": f"Sandbox {sandbox_id} not found"}
        results = self._results.get(sandbox_id)
        if not results and self._storage:
            stored_result = self._storage.get_result(sandbox_id)
            if stored_result:
                self._results[sandbox_id] = stored_result
                results = stored_result
        if not results:
            return {"status": "pending", "message": "No results yet"}
        return results

    def destroy_sandbox(self, sandbox_id: str) -> Dict[str, Any]:
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            if self._storage:
                stored = self._storage.get_sandbox(sandbox_id)
                if stored:
                    sandbox = stored
                    self._sandboxes[sandbox_id] = stored
            if not sandbox:
                return {"status": "error", "message": f"Sandbox {sandbox_id} not found"}
        if sandbox["status"] == SandboxStatus.RUNNING:
            return {"status": "error", "message": f"Sandbox {sandbox_id} is running, cannot destroy"}

        if sandbox.get("process_handle") and sandbox.get("isolation_level") == "process":
            try:
                sandbox["process_handle"].close()
            except Exception:
                pass

        sandbox["status"] = SandboxStatus.DESTROYED
        self._sandboxes.pop(sandbox_id, None)
        self._results.pop(sandbox_id, None)
        if self._storage:
            try:
                self._storage.delete_sandbox(sandbox_id)
            except Exception as e:
                logger.warning(f"Failed to delete sandbox from storage: {e}")
        logger.info(f"Destroyed sandbox {sandbox_id}")
        return {"status": "ok", "sandbox_id": sandbox_id}

    def export_results(self, sandbox_id: str, approved_by: str = "") -> Dict[str, Any]:
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox and self._storage:
            stored = self._storage.get_sandbox(sandbox_id)
            if stored:
                self._sandboxes[sandbox_id] = stored
                sandbox = stored
        if not sandbox:
            return {"status": "error", "message": f"Sandbox {sandbox_id} not found"}
        if sandbox["status"] != SandboxStatus.COMPLETED:
            return {"status": "error", "message": "Only completed sandbox results can be exported"}

        results = self._results.get(sandbox_id)
        if not results and self._storage:
            stored_result = self._storage.get_result(sandbox_id)
            if stored_result:
                self._results[sandbox_id] = stored_result
                results = stored_result
        if not results:
            results = {}

        export_data = {
            "sandbox_id": sandbox_id,
            "workspace_id": sandbox["config"].get("workspace_id", "default"),
            "scenario_id": sandbox["config"].get("scenario_id", ""),
            "results": results,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": approved_by,
        }

        try:
            from odap.biz.simulation.simulation_deduction.storage.sqlite_deduction_storage import SQLiteDeductionStorage
            storage = SQLiteDeductionStorage()
            storage.save_scenario({
                "scenario_id": f"exported_{sandbox_id}",
                "name": f"Exported from sandbox {sandbox_id}",
                "description": f"Results exported from sandbox {sandbox_id}",
                "target_object_id": results.get("baseline_metrics", {}).get("target_id", ""),
                "target_object_type": results.get("baseline_metrics", {}).get("target_type", ""),
                "status": "exported",
                "tags": ["sandbox_export"],
                "created_at": export_data["exported_at"],
                "updated_at": export_data["exported_at"],
            })
        except Exception as e:
            logger.warning(f"Export to production storage failed: {e}")

        return export_data

    def list_sandboxes(self, workspace_id: str = None) -> List[Dict[str, Any]]:
        memory_ids = set(self._sandboxes.keys())
        if self._storage:
            try:
                stored_list = self._storage.list_sandboxes()
                for s in stored_list:
                    sid = s.get("sandbox_id")
                    if sid and sid not in memory_ids:
                        self._sandboxes[sid] = s
                        memory_ids.add(sid)
            except Exception as e:
                logger.warning(f"Failed to load sandboxes from storage: {e}")

        results = []
        for sid, sandbox in self._sandboxes.items():
            if workspace_id and sandbox.get("config", {}).get("workspace_id") != workspace_id:
                continue
            results.append({
                "sandbox_id": sid,
                "status": sandbox["status"],
                "created_at": sandbox["created_at"],
                "workspace_id": sandbox.get("config", {}).get("workspace_id", ""),
            })
        return results


def get_sandbox_manager() -> SandboxManager:
    return SandboxManager()
