import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..interfaces import IActionTriggerEngine
from ..storage import SQLiteRuntimeStorage
from ..models import ActionTrigger, TriggerCondition, TriggerExecution, ActionContext, TriggerType

logger = logging.getLogger("action_trigger_engine")


class ActionTriggerEngine(IActionTriggerEngine):
    def __init__(self, storage: SQLiteRuntimeStorage = None, function_engine=None, propagation_engine=None):
        self.storage = storage or SQLiteRuntimeStorage()
        self.function_engine = function_engine
        self.propagation_engine = propagation_engine

    def register_trigger(self, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        conditions_data = trigger_data.get("conditions", [])
        if isinstance(conditions_data, list):
            conditions = [TriggerCondition(**c) if isinstance(c, dict) else c for c in conditions_data]
        else:
            conditions = []
        trigger = ActionTrigger(**{k: v for k, v in trigger_data.items() if k != "conditions"})
        trigger.conditions = conditions
        if not trigger.name:
            raise ValueError("trigger name is required")
        if not trigger.action_type_id and not trigger.action_name:
            raise ValueError("action_type_id or action_name is required")
        result = self.storage.save_trigger(trigger.model_dump())
        return result

    def get_trigger(self, trigger_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_trigger(trigger_id)

    def list_triggers(self, target_object_type: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        return self.storage.list_triggers(target_object_type=target_object_type, is_active=is_active)

    def delete_trigger(self, trigger_id: str) -> bool:
        return self.storage.delete_trigger(trigger_id)

    def evaluate_triggers(self, object_type: str, object_id: str, state_changes: Dict[str, Any]) -> List[Dict[str, Any]]:
        all_triggers = self.storage.list_triggers(is_active=True)
        matched = []
        for trigger_data in all_triggers:
            conditions = trigger_data.get("conditions", [])
            if not conditions:
                continue
            all_conditions_met = True
            for cond in conditions:
                if not cond.get("is_active", True):
                    continue
                cond_object_type = cond.get("object_type", "")
                if cond_object_type and cond_object_type != object_type:
                    all_conditions_met = False
                    break
                prop_name = cond.get("property_name", "")
                if prop_name not in state_changes:
                    all_conditions_met = False
                    break
                current_value = state_changes[prop_name]
                if not self._check_condition(cond, current_value):
                    all_conditions_met = False
                    break
            if all_conditions_met:
                if self._is_cooled_down(trigger_data):
                    matched.append(trigger_data)
        propagated = self._propagate_along_relations(object_type, object_id, state_changes, matched)
        matched.extend(propagated)
        matched.sort(key=lambda t: t.get("priority", 0), reverse=True)
        return matched

    def execute_trigger(self, trigger_id: str, triggered_by: Dict[str, Any]) -> Dict[str, Any]:
        trigger_data = self.storage.get_trigger(trigger_id)
        if not trigger_data:
            return {"status": "error", "message": f"Trigger {trigger_id} not found"}
        if not trigger_data.get("is_active", True):
            return {"status": "error", "message": f"Trigger {trigger_id} is not active"}
        execution = TriggerExecution(
            trigger_id=trigger_id,
            action_type_id=trigger_data.get("action_type_id", ""),
            action_name=trigger_data.get("action_name", ""),
            triggered_by=triggered_by,
            target_object_id=trigger_data.get("target_object_id") or "",
            target_object_type=trigger_data.get("target_object_type", ""),
            parameters=trigger_data.get("parameters", {}),
            status="running",
        )
        self.storage.save_execution(execution.model_dump())
        try:
            context = self._build_action_context(trigger_data, triggered_by)
            exec_result = None
            if self.function_engine:
                action_type_id = trigger_data.get("action_type_id", "")
                functions = self.function_engine.list_functions(target_object_type=trigger_data.get("target_object_type", ""))
                for func in functions:
                    if func.get("bound_action_contract", "").startswith(action_type_id.split("-")[0] if "-" in action_type_id else action_type_id):
                        exec_result = self.function_engine.execute_function(func["function_id"], context.model_dump())
                        break
            execution.status = "completed"
            execution.result = exec_result or {"status": "success", "message": "trigger executed, no bound function found"}
            execution.completed_at = datetime.now().isoformat()
        except Exception as e:
            logger.error(f"Trigger execution failed: {trigger_id} - {e}")
            execution.status = "failed"
            execution.error = str(e)
            execution.completed_at = datetime.now().isoformat()
        self.storage.save_execution(execution.model_dump())
        trigger_data["last_fired_at"] = datetime.now().isoformat()
        trigger_data["fire_count"] = trigger_data.get("fire_count", 0) + 1
        self.storage.save_trigger(trigger_data)
        return execution.model_dump()

    def get_execution_history(self, trigger_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self.storage.query_executions(trigger_id=trigger_id, limit=limit)

    def _check_condition(self, condition: Dict[str, Any], current_value: Any) -> bool:
        operator = condition.get("operator", "eq")
        threshold = condition.get("threshold_value")
        try:
            if operator == "gt":
                return current_value > threshold
            elif operator == "lt":
                return current_value < threshold
            elif operator == "eq":
                return current_value == threshold
            elif operator == "neq":
                return current_value != threshold
            elif operator == "contains":
                return threshold in current_value if current_value is not None else False
            elif operator == "in":
                return current_value in threshold if threshold is not None else False
            elif operator == "between":
                threshold_max = condition.get("threshold_max")
                if threshold is not None and threshold_max is not None:
                    return threshold <= current_value <= threshold_max
                return False
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
        except (TypeError, ValueError):
            return False

    def _build_action_context(self, trigger_data: Dict[str, Any], triggered_by: Dict[str, Any]) -> ActionContext:
        context = ActionContext(
            action_type_id=trigger_data.get("action_type_id", ""),
            action_name=trigger_data.get("action_name", ""),
            target_object=triggered_by,
            parameters=trigger_data.get("parameters", {}),
            scenario_id=triggered_by.get("scenario_id"),
            workspace_id=triggered_by.get("workspace_id"),
        )
        return context

    def _propagate_along_relations(self, object_type: str, object_id: str, state_changes: Dict[str, Any], already_matched: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        propagated = []
        if not self.propagation_engine:
            return propagated
        already_ids = {t.get("trigger_id") for t in already_matched}
        graphs = self.storage.list_propagation_graphs() if hasattr(self.storage, "list_propagation_graphs") else []
        if not graphs:
            return propagated
        for graph_data in graphs:
            edges = graph_data.get("edges", [])
            for edge in edges:
                if edge.get("source_type") == object_type:
                    target_type = edge.get("target_type", "")
                    target_prop = edge.get("target_property")
                    if target_prop and target_prop in state_changes:
                        related_triggers = self.storage.list_triggers(target_object_type=target_type, is_active=True)
                        for rt in related_triggers:
                            if rt.get("trigger_id") not in already_ids:
                                conditions = rt.get("conditions", [])
                                for cond in conditions:
                                    if cond.get("trigger_type") == TriggerType.RELATION_PROPAGATED.value:
                                        propagated.append(rt)
                                        already_ids.add(rt.get("trigger_id"))
                                        break
        return propagated

    def _is_cooled_down(self, trigger_data: Dict[str, Any]) -> bool:
        cooldown = trigger_data.get("cooldown_seconds", 0)
        if cooldown <= 0:
            return True
        last_fired = trigger_data.get("last_fired_at")
        if not last_fired:
            return True
        try:
            last_dt = datetime.fromisoformat(last_fired)
            now_dt = datetime.now()
            elapsed = (now_dt - last_dt).total_seconds()
            return elapsed >= cooldown
        except (ValueError, TypeError):
            return True
