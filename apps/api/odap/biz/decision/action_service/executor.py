import logging
import time
from typing import Optional, Dict, Any

from .schemas import ActionRequest, ActionRecord, ActionRequestStatus, ActionExecutionResult
from .storage.sqlite_action_storage import SQLiteActionStorage
from odap.biz.decision.interfaces.idecision_oms_service import IDecisionOMSService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 审计辅助：决策层 Action Service，service="agent_action"
# ---------------------------------------------------------------------------

def _executor_audit(
    action: str,
    *,
    resource: str,
    details: Optional[Dict[str, Any]] = None,
    result_status: str = "success",
    result_message: str = "",
    latency_ms: Optional[int] = None,
) -> None:
    """决策 action 服务审计：优先 storage_audit → 回退 log_audit → logger.warning"""
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


class ActionExecutor:
    def __init__(self):
        self._action_storage = None
        self._oms = None
        self._graph_manager = None
        self._opa_manager = None

    @property
    def action_storage(self):
        if self._action_storage is None:
            self._action_storage = SQLiteActionStorage()
        return self._action_storage

    @property
    def oms(self) -> Optional[IDecisionOMSService]:
        if self._oms is None:
            from odap.biz.core.ontology.application.oms.services import OMSService
            self._oms = OMSService.get_instance()
        return self._oms

    @property
    def graph(self):
        if self._graph_manager is None:
            from odap.infra.query import get_graph_write_proxy
            self._graph_manager = get_graph_write_proxy()
        return self._graph_manager

    @property
    def opa(self):
        if self._opa_manager is None:
            try:
                from odap.infra.opa.opa_service import OPAManagerV2
                self._opa_manager = OPAManagerV2()
            except Exception as e:
                logger.warning(f"ActionExecutor: OPAManagerV2 import failed (fail-closed): {e}")
                self._opa_manager = None
        return self._opa_manager

    async def submit_action(self, request: ActionRequest) -> ActionRecord:
        """提交 Action（execute 主入口）：start/success/failed 三维度审计"""
        start = time.perf_counter()
        action_type_id = request.action_type_id
        requested_by = getattr(request, "requested_by", "system") or "system"
        record_id = ""
        try:
            # start 审计
            try:
                _executor_audit(
                    "decision_action_submit_start",
                    resource=action_type_id,
                    details={
                        "action_type_id": action_type_id,
                        "requested_by": requested_by,
                        "params_count": len(getattr(request, "parameters", {}) or {}),
                    },
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

            action_type_def = self.oms.get_action_type(request.action_type_id)
            if not action_type_def:
                raise ValueError(f"Action type '{request.action_type_id}' not found in OMS")

            record_data = request.model_dump()
            record = self.action_storage.create_record(record_data)
            record_id = record.get("action_record_id", "")

            try:
                self.action_storage.update_status(record['action_record_id'], 'validating')
                validation = await self._validate(record, action_type_def)
                if not validation['valid']:
                    self.action_storage.update_status(
                        record['action_record_id'], 'rejected',
                        validation_result=validation
                    )
                    latency_ms = int((time.perf_counter() - start) * 1000)
                    try:
                        _executor_audit(
                            "decision_action_submit_rejected",
                            resource=record.get("action_record_id", action_type_id),
                            details={
                                "action_record_id": record.get("action_record_id", ""),
                                "action_type_id": action_type_id,
                                "errors_count": len(validation.get("errors", [])),
                            },
                            result_status="failure",
                            result_message="validation failed: "
                                           + ("; ".join(validation.get("errors", [])[:3]))[:500],
                            latency_ms=latency_ms,
                        )
                    except Exception as e:
                        logger.warning(f"audit failed: {e}")
                    return self.action_storage.get_record(record['action_record_id'])

                opa_result = await self._check_opa(record, action_type_def)
                if not opa_result.get('allow', False):
                    self.action_storage.update_status(
                        record['action_record_id'], 'rejected',
                        opa_decision=opa_result,
                        validation_result=validation,
                    )
                    latency_ms = int((time.perf_counter() - start) * 1000)
                    try:
                        _executor_audit(
                            "decision_action_submit_opa_denied",
                            resource=record.get("action_record_id", action_type_id),
                            details={
                                "action_record_id": record.get("action_record_id", ""),
                                "action_type_id": action_type_id,
                                "opa_reason": opa_result.get("reason", "")[:200],
                            },
                            result_status="denied",
                            result_message="OPA denied",
                            latency_ms=latency_ms,
                        )
                    except Exception as e:
                        logger.warning(f"audit failed: {e}")
                    return self.action_storage.get_record(record['action_record_id'])

                if action_type_def.get('confirmation_required', False):
                    self.action_storage.update_status(
                        record['action_record_id'], 'approved',
                        validation_result=validation,
                        opa_decision=opa_result,
                    )
                    latency_ms = int((time.perf_counter() - start) * 1000)
                    try:
                        _executor_audit(
                            "decision_action_submit_approved",
                            resource=record.get("action_record_id", action_type_id),
                            details={
                                "action_record_id": record.get("action_record_id", ""),
                                "action_type_id": action_type_id,
                            },
                            result_status="success",
                            result_message="confirmation_required",
                            latency_ms=latency_ms,
                        )
                    except Exception as e:
                        logger.warning(f"audit failed: {e}")
                    return self.action_storage.get_record(record['action_record_id'])

                result_record = await self._execute(record, action_type_def, validation, opa_result)
                latency_ms = int((time.perf_counter() - start) * 1000)
                try:
                    final_status = result_record.get("status") if isinstance(result_record, dict) else getattr(result_record, "status", "unknown")
                    _executor_audit(
                        "decision_action_submit_success",
                        resource=record.get("action_record_id", action_type_id),
                        details={
                            "action_record_id": record.get("action_record_id", ""),
                            "action_type_id": action_type_id,
                            "final_status": str(final_status),
                        },
                        result_status="success",
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return result_record

            except Exception as e:
                latency_ms = int((time.perf_counter() - start) * 1000)
                logger.error(f"Action execution failed: {e}")
                self.action_storage.update_status(
                    record['action_record_id'], 'failed',
                    execution_result={'error': str(e)},
                )
                try:
                    _executor_audit(
                        "decision_action_submit_failed",
                        resource=record.get("action_record_id", action_type_id),
                        details={
                            "action_record_id": record.get("action_record_id", ""),
                            "action_type_id": action_type_id,
                        },
                        result_status="failure",
                        result_message=str(e)[:500],
                        latency_ms=latency_ms,
                    )
                except Exception as e_a:
                    logger.warning(f"audit failed: {e_a}")
                return self.action_storage.get_record(record['action_record_id'])
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _executor_audit(
                    "decision_action_submit_failed",
                    resource=record_id or action_type_id,
                    details={
                        "action_record_id": record_id,
                        "action_type_id": action_type_id,
                    },
                    result_status="failure",
                    result_message=str(e)[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e_a:
                logger.warning(f"audit failed: {e_a}")
            raise

    async def approve_and_execute(self, record_id: str, approver: str = "", comment: str = "") -> ActionRecord:
        """批准并执行（execute 第二入口）：start/success/failed 审计"""
        start = time.perf_counter()
        try:
            try:
                _executor_audit(
                    "decision_action_approve_start",
                    resource=record_id,
                    details={
                        "action_record_id": record_id,
                        "approver": approver or "system",
                        "comment_len": len(comment or ""),
                    },
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

            record = self.action_storage.get_record(record_id)
            if not record:
                raise ValueError(f"Action record '{record_id}' not found")
            if record['status'] != 'approved':
                raise ValueError(f"Action record is in '{record['status']}' status, cannot execute")

            action_type_def = self.oms.get_action_type(record['action_type_id'])
            result = await self._execute(record, action_type_def or {}, record.get('validation_result'), record.get('opa_decision'))
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                final_status = result.get("status") if isinstance(result, dict) else getattr(result, "status", "unknown")
                _executor_audit(
                    "decision_action_approve_success",
                    resource=record_id,
                    details={
                        "action_record_id": record_id,
                        "approver": approver or "system",
                        "final_status": str(final_status),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return result
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _executor_audit(
                    "decision_action_approve_failed",
                    resource=record_id,
                    details={
                        "action_record_id": record_id,
                        "approver": approver or "system",
                    },
                    result_status="failure",
                    result_message=str(e)[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e_a:
                logger.warning(f"audit failed: {e_a}")
            raise

    async def _validate(self, record: Dict[str, Any], action_type_def: Dict[str, Any]) -> Dict[str, Any]:
        errors = []

        required_params = [p for p in action_type_def.get('parameters', []) if p.get('required', True)]
        provided = record.get('parameters', {})
        for param in required_params:
            pname = param.get('name', '')
            if pname not in provided or provided[pname] is None:
                errors.append(f"Missing required parameter: {pname}")

        target_type = action_type_def.get('target_object_type', '')
        if target_type and record.get('target_object_type') != target_type:
            errors.append(f"Target object type mismatch: expected '{target_type}', got '{record.get('target_object_type')}'")

        return {'valid': len(errors) == 0, 'errors': errors}

    async def _check_opa(self, record: Dict[str, Any], action_type_def: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.opa:
            return {'allow': False, 'reason': 'No OPA configured (fail-closed)'}

        opa_policy = action_type_def.get('opa_policy')
        if not opa_policy:
            return {'allow': True, 'reason': 'No OPA policy configured'}

        try:
            result = self.opa.check_permission_abac(
                user=record.get('requested_by', 'system'),
                action=record.get('action_type_id', ''),
                resource=record.get('target_object_id', ''),
                environment={'agent_id': record.get('agent_id')},
            )
            return result
        except Exception as e:
            logger.error(f"OPA check failed (fail-closed): {e}")
            return {'allow': False, 'reason': f'OPA check error (fail-closed): {e}'}

    async def _execute(
        self,
        record: Dict[str, Any],
        action_type_def: Dict[str, Any],
        validation: Optional[Dict[str, Any]],
        opa_decision: Optional[Dict[str, Any]],
    ) -> ActionRecord:
        """内部 execute + writeback_execution + feedback_loop_update 审计"""
        self.action_storage.update_status(
            record['action_record_id'], 'executing',
            validation_result=validation,
            opa_decision=opa_decision,
        )

        execute_start = time.perf_counter()
        execution_result = await self._do_execute(record, action_type_def)
        execute_latency_ms = int((time.perf_counter() - execute_start) * 1000)

        # do_execute 完成审计
        try:
            try:
                result_len = len(str(execution_result.model_dump())[:200])
            except Exception:
                result_len = 0
            _executor_audit(
                "decision_action_do_execute_done",
                resource=record.get("action_record_id", ""),
                details={
                    "action_record_id": record.get("action_record_id", ""),
                    "action_type_id": record.get("action_type_id", ""),
                    "success": bool(getattr(execution_result, "success", False)),
                    "result_len": result_len,
                },
                result_status="success" if getattr(execution_result, "success", False) else "failure",
                latency_ms=execute_latency_ms,
            )
        except Exception as e:
            logger.warning(f"audit failed: {e}")

        # writeback_execution（成功时才执行）
        writeback_result = None
        writeback_latency_ms = None
        if execution_result.success:
            wb_start = time.perf_counter()
            try:
                writeback_result = await self._do_writeback(record, action_type_def, execution_result)
                writeback_latency_ms = int((time.perf_counter() - wb_start) * 1000)
            except Exception:
                writeback_latency_ms = int((time.perf_counter() - wb_start) * 1000)
            # writeback_execution 审计
            try:
                wb_success = (
                    bool(writeback_result.get("success"))
                    if isinstance(writeback_result, dict)
                    else bool(writeback_result)
                )
                _executor_audit(
                    "decision_action_writeback_execution",
                    resource=record.get("action_record_id", ""),
                    details={
                        "action_record_id": record.get("action_record_id", ""),
                        "action_type_id": record.get("action_type_id", ""),
                        "writeback_success": wb_success,
                    },
                    result_status="success" if wb_success else "failure",
                    latency_ms=writeback_latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

        final_status = 'completed' if execution_result.success else 'failed'
        self.action_storage.update_status(
            record['action_record_id'], final_status,
            execution_result=execution_result.model_dump(),
            writeback_result=writeback_result,
        )

        updated_record = self.action_storage.get_record(record['action_record_id'])

        # feedback_loop_update（成功时 close_loop）
        fb_start = time.perf_counter()
        feedback_error = ""
        feedback_done = False
        if execution_result.success:
            try:
                from .feedback_loop import get_feedback_loop
                feedback_loop = get_feedback_loop()
                await feedback_loop.close_loop(updated_record)
                feedback_done = True
            except Exception as e:
                feedback_error = str(e)[:500]
                logger.warning(f"Feedback loop failed for {record['action_record_id']}: {e}")
            fb_latency_ms = int((time.perf_counter() - fb_start) * 1000)
            try:
                _executor_audit(
                    "decision_action_feedback_loop_update",
                    resource=record.get("action_record_id", ""),
                    details={
                        "action_record_id": record.get("action_record_id", ""),
                        "action_type_id": record.get("action_type_id", ""),
                        "feedback_done": feedback_done,
                    },
                    result_status="success" if feedback_done and not feedback_error else "failure",
                    result_message=feedback_error,
                    latency_ms=fb_latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

        return updated_record

    async def _do_execute(self, record: Dict[str, Any], action_type_def: Dict[str, Any]) -> ActionExecutionResult:
        action_name = action_type_def.get('name', record.get('action_type_id', ''))
        target_id = record.get('target_object_id', '')
        params = record.get('parameters', {})

        try:
            if action_name in ('update_status', 'update_property', 'modify'):
                prop_key = params.get('property', 'status')
                prop_val = params.get('value')
                if prop_val is not None:
                    self.graph.update_entity(target_id, {prop_key: prop_val})
                return ActionExecutionResult(
                    success=True,
                    message=f"Updated {prop_key}={prop_val} on {target_id}",
                    data={'property': prop_key, 'value': prop_val},
                )

            elif action_name in ('create', 'add'):
                entity_type = record.get('target_object_type', 'Entity')
                name = params.get('name', f"New {entity_type}")
                self.graph.add_entity(
                    entity_id=target_id,
                    entity_type=entity_type,
                    properties=params,
                )
                return ActionExecutionResult(
                    success=True,
                    message=f"Created {entity_type} '{name}'",
                    data={'entity_id': target_id},
                )

            elif action_name in ('delete', 'remove'):
                self.graph.delete_entity(target_id)
                return ActionExecutionResult(
                    success=True,
                    message=f"Deleted entity {target_id}",
                    data={'target_id': target_id, 'deleted': True},
                )

            elif action_name in ('link', 'relate'):
                target2 = params.get('target_id', '')
                link_type = params.get('link_type', 'related_to')
                self.graph.add_relationship(target_id, target2, link_type, {})
                return ActionExecutionResult(
                    success=True,
                    message=f"Created link [{link_type}] from {target_id} to {target2}",
                    data={'source': target_id, 'target': target2, 'link_type': link_type},
                )

            else:
                logger.warning(f"Unknown action type: {action_name}, attempting generic property update")
                properties_to_update = {k: v for k, v in params.items() if k not in ('entity_type', 'target_id', 'link_type')}
                if properties_to_update:
                    self.graph.update_entity(target_id, properties_to_update)
                    return ActionExecutionResult(
                        success=True,
                        message=f"Updated {target_id} via generic handler with {list(properties_to_update.keys())}",
                        data={'updated_properties': list(properties_to_update.keys())},
                    )
                return ActionExecutionResult(
                    success=False,
                    message=f"Unknown action type '{action_name}' and no properties to update",
                )

        except Exception as e:
            return ActionExecutionResult(
                success=False,
                message=f"Execution failed: {str(e)}",
            )

    async def _do_writeback(
        self,
        record: Dict[str, Any],
        action_type_def: Dict[str, Any],
        execution_result: ActionExecutionResult,
    ) -> Optional[Dict[str, Any]]:
        """writeback_execution（记录到审计）"""
        writeback_config = action_type_def.get('writeback_config')
        if not writeback_config:
            return None

        try:
            from .writeback.connectors import get_writeback_manager
            manager = get_writeback_manager()
            result = await manager.execute_writeback(
                record,
                execution_result.model_dump(),
                writeback_config,
            )
            if result:
                return {
                    'success': result.success,
                    'message': result.message,
                    'data': result.data,
                    'timestamp': result.timestamp,
                }
        except Exception as e:
            logger.warning(f"Writeback manager failed: {e}")

        wb_type = writeback_config.get('type', '')
        wb_url = writeback_config.get('url', '')

        if wb_type == 'webhook' and wb_url:
            logger.info(f"Writeback webhook to {wb_url} for action {record['action_record_id']}")
            return {'status': 'webhook_sent', 'url': wb_url}

        elif wb_type == 'graph':
            logger.info(f"Writeback to graph for action {record['action_record_id']}")
            return {'status': 'graph_updated'}

        return None


_executor_instance = None


def get_action_executor() -> ActionExecutor:
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = ActionExecutor()
    return _executor_instance
