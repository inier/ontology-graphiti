"""智能体管理 - 服务层

审计（service="agent_action"）：
- create_agent / update_agent / delete_agent：生命周期 CRUD 三维度
- deploy_agent / stop_agent：破坏性操作必记（start/success/failed）
- list_agents / get_agent：只读计数
"""

import logging
import time
from typing import Dict, Any, List, Optional

from ..storage.sqlite_agent_storage import SQLiteAgentStorage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 审计辅助：Agent 管理服务层
# ---------------------------------------------------------------------------

def _agent_audit(
    action: str,
    *,
    resource: str,
    details: Optional[Dict[str, Any]] = None,
    result_status: str = "success",
    result_message: str = "",
    latency_ms: Optional[int] = None,
) -> None:
    """Agent 管理审计：优先 storage_audit → 回退 log_audit → logger.warning"""
    _details = dict(details or {})
    if latency_ms is not None:
        _details.setdefault("latency_ms", latency_ms)
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            resource=resource,
            details=_details,
            service="agent_action",
            result_status=result_status,
            result_message=result_message,
        )
        return
    except Exception as e:
        logger.warning(f"audit failed: {e}")

    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource=resource,
            user="system",
            service="agent_action",
            details=_details,
            result_status=result_status,
            result_message=result_message,
            duration_ms=latency_ms,
        )
        return
    except Exception as e:
        logger.warning(f"audit failed (log_audit fallback): {e}")


class AgentService:
    """智能体服务，封装存储层调用"""

    def __init__(self):
        self.storage = SQLiteAgentStorage()

    # ---------- 只读操作 ----------

    def list_agents(
        self,
        role_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start = time.perf_counter()
        try:
            items = self.storage.list_agents(role_id=role_id, workspace_id=workspace_id)
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _agent_audit(
                    "agent_list_success",
                    resource=workspace_id or role_id or "all",
                    details={
                        "role_id": role_id or "",
                        "workspace_id": workspace_id or "",
                        "count": len(items),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return items
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _agent_audit(
                    "agent_list_failed",
                    resource=workspace_id or role_id or "all",
                    details={"role_id": role_id or "", "workspace_id": workspace_id or ""},
                    result_status="failure",
                    result_message=f"list_agents failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            raise

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            agent = self.storage.get_agent(agent_id)
            latency_ms = int((time.perf_counter() - start) * 1000)
            if not agent:
                try:
                    _agent_audit(
                        "agent_get_miss",
                        resource=agent_id,
                        details={"agent_id": agent_id},
                        result_status="success",
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return {"status": "error", "message": "智能体不存在"}
            try:
                _agent_audit(
                    "agent_get_hit",
                    resource=agent_id,
                    details={
                        "agent_id": agent_id,
                        "agent_name": agent.get("name", "") if isinstance(agent, dict) else getattr(agent, "name", ""),
                        "status": agent.get("status", "unknown") if isinstance(agent, dict) else getattr(agent, "status", "unknown"),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return agent
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _agent_audit(
                    "agent_get_failed",
                    resource=agent_id,
                    details={"agent_id": agent_id},
                    result_status="failure",
                    result_message=f"get_agent failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            raise

    # ---------- 生命周期 CRUD ----------

    def create_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        name = data.get("name", "unnamed_agent") or "unnamed_agent"
        try:
            try:
                _agent_audit(
                    "agent_create_start",
                    resource=name,
                    details={
                        "name": name,
                        "role_id": data.get("role_id", ""),
                        "workspace_id": data.get("workspace_id", "default"),
                        "enabled": bool(data.get("enabled", True)),
                    },
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

            result = self.storage.create_agent(data)
            latency_ms = int((time.perf_counter() - start) * 1000)
            agent_id = result.get("id", "") if isinstance(result, dict) else getattr(result, "id", name)
            try:
                _agent_audit(
                    "agent_create_success",
                    resource=agent_id,
                    details={
                        "agent_id": agent_id,
                        "name": name,
                        "role_id": data.get("role_id", ""),
                        "workspace_id": data.get("workspace_id", "default"),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return result
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _agent_audit(
                    "agent_create_failed",
                    resource=name,
                    details={
                        "name": name,
                        "role_id": data.get("role_id", ""),
                        "workspace_id": data.get("workspace_id", "default"),
                    },
                    result_status="failure",
                    result_message=f"create_agent failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            raise

    def update_agent(self, agent_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            try:
                _agent_audit(
                    "agent_update_start",
                    resource=agent_id,
                    details={
                        "agent_id": agent_id,
                        "update_fields": list(data.keys()),
                    },
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

            updated = self.storage.update_agent(agent_id, data)
            latency_ms = int((time.perf_counter() - start) * 1000)
            if not updated:
                try:
                    _agent_audit(
                        "agent_update_failed",
                        resource=agent_id,
                        details={"agent_id": agent_id},
                        result_status="failure",
                        result_message="智能体不存在",
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return {"status": "error", "message": "智能体不存在"}
            try:
                _agent_audit(
                    "agent_update_success",
                    resource=agent_id,
                    details={
                        "agent_id": agent_id,
                        "update_fields": list(data.keys()),
                        "new_name": data.get("name", ""),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return updated
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _agent_audit(
                    "agent_update_failed",
                    resource=agent_id,
                    details={"agent_id": agent_id},
                    result_status="failure",
                    result_message=f"update_agent failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            raise

    def delete_agent(self, agent_id: str) -> Dict[str, Any]:
        """删除 Agent（破坏性操作，必记 start/success/failed 三维度）"""
        start = time.perf_counter()
        try:
            try:
                _agent_audit(
                    "agent_delete_start",
                    resource=agent_id,
                    details={"agent_id": agent_id},
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

            success = self.storage.delete_agent(agent_id)
            latency_ms = int((time.perf_counter() - start) * 1000)
            if not success:
                try:
                    _agent_audit(
                        "agent_delete_failed",
                        resource=agent_id,
                        details={"agent_id": agent_id},
                        result_status="failure",
                        result_message="智能体不存在",
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return {"status": "error", "message": "智能体不存在"}
            try:
                _agent_audit(
                    "agent_delete_success",
                    resource=agent_id,
                    details={"agent_id": agent_id},
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "success", "message": "智能体删除成功"}
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _agent_audit(
                    "agent_delete_failed",
                    resource=agent_id,
                    details={"agent_id": agent_id},
                    result_status="failure",
                    result_message=f"delete_agent failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            raise

    # ---------- 破坏性操作：deploy / stop ----------

    def deploy_agent(self, agent_id: str, deploy_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """部署 Agent（破坏性操作必记 start/success/failed）"""
        start = time.perf_counter()
        deploy_config = deploy_config or {}
        try:
            try:
                _agent_audit(
                    "agent_deploy_start",
                    resource=agent_id,
                    details={
                        "agent_id": agent_id,
                        "runtime": deploy_config.get("runtime", ""),
                        "replicas": deploy_config.get("replicas", 1),
                    },
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

            # 获取 agent 信息
            agent = self.storage.get_agent(agent_id)
            if not agent:
                latency_ms = int((time.perf_counter() - start) * 1000)
                try:
                    _agent_audit(
                        "agent_deploy_failed",
                        resource=agent_id,
                        details={"agent_id": agent_id},
                        result_status="failure",
                        result_message="智能体不存在",
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return {"status": "error", "message": "智能体不存在"}

            # 尝试更新 status 为 deploying / running（实际部署逻辑由 runtime 决定）
            try:
                self.storage.update_agent(agent_id, {
                    "status": "running",
                    "deployed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                })
            except Exception:
                pass

            latency_ms = int((time.perf_counter() - start) * 1000)
            deployment_id = deploy_config.get("deployment_id") or f"deploy-{agent_id}-{int(time.time())}"
            try:
                _agent_audit(
                    "agent_deploy_success",
                    resource=agent_id,
                    details={
                        "agent_id": agent_id,
                        "deployment_id": deployment_id,
                        "runtime": deploy_config.get("runtime", "default"),
                        "replicas": deploy_config.get("replicas", 1),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {
                "status": "success",
                "agent_id": agent_id,
                "deployment_id": deployment_id,
                "message": "智能体部署成功",
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _agent_audit(
                    "agent_deploy_failed",
                    resource=agent_id,
                    details={
                        "agent_id": agent_id,
                        "runtime": deploy_config.get("runtime", ""),
                    },
                    result_status="failure",
                    result_message=f"deploy_agent failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": f"deploy_agent failed: {exc}"}

    def stop_agent(self, agent_id: str, stop_reason: str = "") -> Dict[str, Any]:
        """停止 Agent（破坏性操作必记 start/success/failed）"""
        start = time.perf_counter()
        try:
            try:
                _agent_audit(
                    "agent_stop_start",
                    resource=agent_id,
                    details={
                        "agent_id": agent_id,
                        "stop_reason_len": len(stop_reason or ""),
                    },
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

            agent = self.storage.get_agent(agent_id)
            if not agent:
                latency_ms = int((time.perf_counter() - start) * 1000)
                try:
                    _agent_audit(
                        "agent_stop_failed",
                        resource=agent_id,
                        details={"agent_id": agent_id},
                        result_status="failure",
                        result_message="智能体不存在",
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return {"status": "error", "message": "智能体不存在"}

            try:
                self.storage.update_agent(agent_id, {
                    "status": "stopped",
                    "stopped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "stop_reason": stop_reason,
                })
            except Exception:
                pass

            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _agent_audit(
                    "agent_stop_success",
                    resource=agent_id,
                    details={
                        "agent_id": agent_id,
                        "stop_reason": stop_reason[:200],
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {
                "status": "success",
                "agent_id": agent_id,
                "message": "智能体停止成功",
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _agent_audit(
                    "agent_stop_failed",
                    resource=agent_id,
                    details={"agent_id": agent_id},
                    result_status="failure",
                    result_message=f"stop_agent failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": f"stop_agent failed: {exc}"}


# 模块级单例
_agent_service_instance: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """获取智能体服务实例（单例）"""
    global _agent_service_instance
    if _agent_service_instance is None:
        _agent_service_instance = AgentService()
    return _agent_service_instance
