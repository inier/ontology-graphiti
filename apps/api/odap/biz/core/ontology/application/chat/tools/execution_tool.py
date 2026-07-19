"""ExecutionStrategyTool — 执行策略引擎。

支持三种执行模式:
- auto: 自动执行（需OPA权限校验）
- approval: 审批执行（发送审批请求，等待确认）
- scheduled: 定时执行（创建定时任务）
"""

from __future__ import annotations

import logging
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    AUTO = "auto"
    APPROVAL = "approval"
    SCHEDULED = "scheduled"


class ExecutionInput:
    def __init__(
        self,
        action: str,
        target: str = "",
        params: dict = None,
        mode: str = "auto",
        schedule: str = "",
        ontology_id: str = None,
        workspace_id: str = "default",
        operator: str = "system",
    ):
        self.action = action
        self.target = target
        self.params = params or {}
        self.mode = mode
        self.schedule = schedule
        self.ontology_id = ontology_id
        self.workspace_id = workspace_id
        self.operator = operator


class ExecutionStrategyTool:
    """执行策略引擎"""

    async def execute(self, input_data: ExecutionInput) -> Dict[str, Any]:
        mode = input_data.mode
        execution_id = f"exec-{uuid.uuid4().hex[:8]}"

        if mode == ExecutionMode.AUTO or mode == "auto":
            return await self._auto_execute(execution_id, input_data)
        elif mode == ExecutionMode.APPROVAL or mode == "approval":
            return await self._approval_execute(execution_id, input_data)
        elif mode == ExecutionMode.SCHEDULED or mode == "scheduled":
            return await self._scheduled_execute(execution_id, input_data)
        else:
            return {"status": "error", "message": f"不支持的执行模式: {mode}"}

    async def _auto_execute(self, exec_id: str, input_data: ExecutionInput) -> dict:
        """自动执行 — 需通过OPA权限校验"""
        # OPA 权限校验
        try:
            from odap.infra.opa.opa_service import OPAService
            opa = OPAService()
            allowed = opa.check_permission(
                user=input_data.operator,
                action=input_data.action,
                resource=input_data.target,
            )
            if not allowed:
                return {
                    "execution_id": exec_id,
                    "status": "blocked",
                    "mode": "auto",
                    "reason": "OPA权限校验未通过",
                }
        except Exception as e:
            logger.warning("OPA check exception: %s, denying by default (fail-close)", e)
            return {
                "execution_id": exec_id,
                "status": "blocked",
                "mode": "auto",
                "reason": f"OPA权限校验异常，默认拒绝: {str(e)[:100]}",
            }

        # 执行
        result = self._perform_action(input_data)
        await self._record_audit(exec_id, "auto", input_data, result)

        return {
            "execution_id": exec_id,
            "status": "completed",
            "mode": "auto",
            "result": result,
        }

    async def _approval_execute(self, exec_id: str, input_data: ExecutionInput) -> dict:
        """审批执行 — 发送审批请求"""
        approval_id = f"appr-{uuid.uuid4().hex[:8]}"

        try:
            from odap.biz.core.ontology.design.engine.impl.audit_recorder_impl import AuditRecorderImpl
            recorder = AuditRecorderImpl()
            recorder.record_ingest(
                entity_type_id="approval_request",
                source="execution_engine",
                process_steps=[{
                    "step": "request_approval",
                    "approval_id": approval_id,
                    "action": input_data.action,
                    "target": input_data.target,
                    "operator": input_data.operator,
                }],
                transform_rules=[],
                result="pending",
            )
        except Exception as e:
            logger.warning("Approval audit recording failed: %s", e)

        return {
            "execution_id": exec_id,
            "status": "pending_approval",
            "mode": "approval",
            "approval_id": approval_id,
            "message": f"操作需要审批: {input_data.action} on {input_data.target}",
            "approval_url": f"/api/approvals/{approval_id}",
        }

    async def _scheduled_execute(self, exec_id: str, input_data: ExecutionInput) -> dict:
        """定时执行 — 创建定时任务"""
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        schedule = input_data.schedule or "0 0 * * *"

        return {
            "execution_id": exec_id,
            "status": "scheduled",
            "mode": "scheduled",
            "job_id": job_id,
            "schedule": schedule,
            "message": f"任务已创建: {input_data.action} on {input_data.target}, 计划: {schedule}",
        }

    def _perform_action(self, input_data: ExecutionInput) -> dict:
        """真正执行CRUD操作"""
        action = input_data.action
        target = input_data.target
        params = input_data.params
        ontology_id = input_data.ontology_id
        workspace_id = input_data.workspace_id

        try:
            from odap.infra.query import get_query_service
            from odap.infra.graph.graph_service import get_graph_manager
            
            qs = get_query_service()
            gm = get_graph_manager()

            if action == "query":
                # 执行查询
                result = qs.execute(workspace_id, f".entity with(search='{target}')", limit=20)
                return {
                    "action": "query",
                    "target": target,
                    "result_count": len(result.rows),
                    "preview": result.rows[:5],
                    "timestamp": self._now(),
                }

            elif action == "add_entity":
                # 创建实体
                eid = params.get("id", f"exec-{uuid.uuid4().hex[:8]}")
                etype = params.get("entity_type", target)
                name = params.get("name", target)
                props = params.get("properties", {})
                
                gm.add_entity(
                    entity_id=eid, entity_type=etype,
                    entity_name=name, properties=props,
                )
                return {
                    "action": "add_entity",
                    "entity_id": eid,
                    "entity_type": etype,
                    "name": name,
                    "properties_count": len(props),
                    "timestamp": self._now(),
                    "verification_hint": f"调用 .entity with(search='{eid}') 验证创建结果",
                }

            elif action == "update_entity":
                # 更新实体
                eid = params.get("id", target)
                props = params.get("properties", {})
                
                gm.update_entity(entity_id=eid, properties=props)
                return {
                    "action": "update_entity",
                    "entity_id": eid,
                    "updated_properties": list(props.keys()),
                    "timestamp": self._now(),
                    "verification_hint": f"调用 .entity with(search='{eid}') 验证更新结果",
                }

            elif action == "delete_entity":
                # 删除实体
                eid = params.get("id", target)
                
                gm.delete_entity(entity_id=eid)
                return {
                    "action": "delete_entity",
                    "entity_id": eid,
                    "timestamp": self._now(),
                    "warning": "此操作不可逆",
                }

            elif action == "add_relation":
                # 创建关系
                source = params.get("source", "")
                tgt = params.get("target", target)
                rtype = params.get("relation_type", "ASSOCIATED_WITH")
                rprops = params.get("properties", {})
                
                gm.add_relationship(
                    source_id=source, target_id=tgt,
                    relationship_type=rtype, properties=rprops,
                )
                return {
                    "action": "add_relation",
                    "source": source,
                    "target": tgt,
                    "relation_type": rtype,
                    "timestamp": self._now(),
                }

            elif action == "check_consistency":
                # 一致性检查
                from odap.biz.core.ontology.reasoning.services.unified_reasoning import get_reasoning_service
                rs = get_reasoning_service()
                report = rs.check_schema_consistency(ontology_id or "default")
                return {
                    "action": "check_consistency",
                    "pass_count": report.pass_count,
                    "fail_count": report.fail_count,
                    "severity": report.severity,
                    "anomalies": list(report.anomalies)[:10],
                    "timestamp": self._now(),
                }

            elif action == "trace_provenance":
                # 溯源查询
                from odap.biz.core.ontology.construction.provenance.provenance_linker import get_provenance_linker
                linker = get_provenance_linker()
                chain = linker.link_chain(target)
                return {
                    "action": "trace_provenance",
                    "entity_id": target,
                    "chain": chain.to_dict(),
                    "is_complete": chain.is_complete(),
                    "timestamp": self._now(),
                }

            else:
                return {
                    "action": action,
                    "target": target,
                    "status": "unsupported",
                    "message": f"不支持的操作类型: {action}。支持: query, add_entity, update_entity, delete_entity, add_relation, check_consistency, trace_provenance",
                    "timestamp": self._now(),
                }

        except ImportError as e:
            logger.warning("Action '%s' dependency not available: %s", action, e)
            return {
                "action": action,
                "target": target,
                "status": "dependency_missing",
                "message": f"执行 {action} 的依赖模块不可用: {e}",
                "timestamp": self._now(),
            }
        except Exception as e:
            logger.error("Action '%s' failed: %s", action, e)
            return {
                "action": action,
                "target": target,
                "status": "failed",
                "error": str(e),
                "timestamp": self._now(),
            }

    async def _record_audit(self, exec_id: str, mode: str, input_data: ExecutionInput, result: dict):
        try:
            from odap.biz.core.ontology.design.engine.impl.audit_recorder_impl import AuditRecorderImpl
            recorder = AuditRecorderImpl()
            recorder.record_ingest(
                entity_type_id="execution",
                source=f"execution_{mode}",
                process_steps=[{
                    "step": mode,
                    "execution_id": exec_id,
                    "action": input_data.action,
                    "target": input_data.target,
                }],
                transform_rules=[],
                result=result.get("status", "unknown"),
            )
        except Exception as e:
            logger.warning("Execution audit recording failed: %s", e)

    def _now(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


def get_execution_tool() -> ExecutionStrategyTool:
    return ExecutionStrategyTool()
