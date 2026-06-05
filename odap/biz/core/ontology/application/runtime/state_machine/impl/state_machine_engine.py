import json
from datetime import datetime
from ..models import OntologyStateMachine, StateDefinition, StateTransition, StateType, TransitionGuard
from ..storage import SQLiteStateMachineStorage
from .expression_evaluator import safe_eval
from typing import Dict, Any, List, Optional


class StateMachineEngine:
    def __init__(self, storage=None):
        self.storage = storage or SQLiteStateMachineStorage()

    def create_state_machine(self, name, target_object_type, states, transitions,
                             initial_state="", description="", scenario_id=None,
                             bound_action_type_ids=None):
        for s in states:
            if s.get("state_type") == "initial" or s.get("state_type") == StateType.INITIAL:
                initial_state = s.get("name", s.get("state_id", ""))
                break
        if not initial_state and states:
            initial_state = states[0].get("name", states[0].get("state_id", ""))
        sm = OntologyStateMachine(
            name=name, target_object_type=target_object_type,
            states=[StateDefinition(**s) if isinstance(s, dict) else s for s in states],
            transitions=[StateTransition(**t) if isinstance(t, dict) else t for t in transitions],
            initial_state=initial_state, description=description,
            scenario_id=scenario_id,
            bound_action_type_ids=bound_action_type_ids or []
        )
        sm_data = self._sm_to_dict(sm)
        self.storage.save_state_machine(sm_data)
        return {"status": "success", "sm_id": sm.sm_id, "name": sm.name,
                "state_count": len(sm.states), "transition_count": len(sm.transitions),
                "initial_state": sm.initial_state}

    def get_state_machine(self, sm_id):
        data = self.storage.get_state_machine(sm_id)
        if not data:
            return {"status": "error", "message": "State machine not found"}
        return {"status": "success", **self._deserialize_sm(data)}

    def get_state_machine_by_object_type(self, object_type):
        data = self.storage.get_state_machine_by_object_type(object_type)
        if not data:
            return {"status": "error", "message": "No state machine for object type"}
        return {"status": "success", **self._deserialize_sm(data)}

    def list_state_machines(self, scenario_id=None, is_active=None):
        machines = self.storage.list_state_machines(scenario_id, is_active)
        return {"status": "success", "count": len(machines),
                "machines": [{"sm_id": m["sm_id"], "name": m["name"],
                              "target_object_type": m["target_object_type"],
                              "state_count": len(json.loads(m.get("states", "[]"))),
                              "initial_state": m.get("initial_state", "")} for m in machines]}

    def delete_state_machine(self, sm_id):
        result = self.storage.delete_state_machine(sm_id)
        if not result:
            return {"status": "error", "message": "State machine not found"}
        return {"status": "success", "sm_id": sm_id}

    def transition(self, sm_id, object_id, action_type_id, context=None):
        sm_data = self.storage.get_state_machine(sm_id)
        if not sm_data:
            return {"status": "error", "message": "State machine not found"}
        states = json.loads(sm_data.get("states", "[]"))
        transitions = json.loads(sm_data.get("transitions", "[]"))
        current_states = json.loads(sm_data.get("current_states", "{}"))
        current_state = current_states.get(object_id, sm_data.get("initial_state", ""))
        matching = [t for t in transitions
                    if t.get("from_state") == current_state
                    and (t.get("trigger_action_type_id") == action_type_id or not t.get("trigger_action_type_id"))]
        if not matching:
            return {"status": "error", "message": f"No valid transition from '{current_state}' for action '{action_type_id}'",
                    "current_state": current_state}
        matching.sort(key=lambda t: t.get("priority", 0), reverse=True)
        transition = matching[0]
        guard = transition.get("guard", "always")
        if guard in ("role_based", "condition_based", "manual_approval"):
            if guard == "role_based":
                required_roles = transition.get("required_roles", [])
                user_roles = (context or {}).get("roles", [])
                if not any(r in required_roles for r in user_roles):
                    return {"status": "error", "message": "Insufficient roles",
                            "required_roles": required_roles}
            elif guard == "condition_based":
                condition = transition.get("guard_condition", "")
                if condition and not self._evaluate_condition(condition, context or {}):
                    return {"status": "error", "message": "Condition not met",
                            "condition": condition}
            elif guard == "manual_approval":
                if not (context or {}).get("approved", False):
                    return {"status": "pending_approval",
                            "message": "Manual approval required",
                            "transition": transition.get("name", ""),
                            "from_state": current_state,
                            "to_state": transition.get("to_state", "")}
        new_state = transition.get("to_state", "")
        current_states[object_id] = new_state
        sm_data["current_states"] = current_states
        sm_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_state_machine(sm_data)
        side_effects = transition.get("side_effects", [])
        return {"status": "success", "object_id": object_id,
                "from_state": current_state, "to_state": new_state,
                "transition": transition.get("name", ""),
                "side_effects": side_effects}

    def get_object_state(self, sm_id, object_id):
        sm_data = self.storage.get_state_machine(sm_id)
        if not sm_data:
            return {"status": "error", "message": "State machine not found"}
        current_states = json.loads(sm_data.get("current_states", "{}"))
        current_state = current_states.get(object_id, sm_data.get("initial_state", ""))
        states = json.loads(sm_data.get("states", "[]"))
        state_info = next((s for s in states if s.get("name") == current_state or s.get("state_id") == current_state), None)
        transitions = json.loads(sm_data.get("transitions", "[]"))
        available = [t for t in transitions if t.get("from_state") == current_state]
        return {"status": "success", "object_id": object_id,
                "current_state": current_state,
                "state_info": state_info,
                "available_transitions": available}

    def reset_object_state(self, sm_id, object_id):
        sm_data = self.storage.get_state_machine(sm_id)
        if not sm_data:
            return {"status": "error", "message": "State machine not found"}
        current_states = json.loads(sm_data.get("current_states", "{}"))
        if object_id in current_states:
            del current_states[object_id]
        sm_data["current_states"] = current_states
        self.storage.save_state_machine(sm_data)
        return {"status": "success", "object_id": object_id,
                "current_state": sm_data.get("initial_state", "")}

    def bind_action_type(self, sm_id, action_type_id):
        sm_data = self.storage.get_state_machine(sm_id)
        if not sm_data:
            return {"status": "error", "message": "State machine not found"}
        bound = json.loads(sm_data.get("bound_action_type_ids", "[]"))
        if action_type_id not in bound:
            bound.append(action_type_id)
        sm_data["bound_action_type_ids"] = bound
        self.storage.save_state_machine(sm_data)
        return {"status": "success", "sm_id": sm_id,
                "bound_action_type_ids": bound}

    def _sm_to_dict(self, sm):
        return {
            "sm_id": sm.sm_id, "name": sm.name, "description": sm.description,
            "target_object_type": sm.target_object_type,
            "states": [{"state_id": s.state_id, "name": s.name,
                        "state_type": s.state_type.value if hasattr(s.state_type, "value") else s.state_type,
                        "description": s.description,
                        "on_enter_actions": s.on_enter_actions, "on_exit_actions": s.on_exit_actions}
                       for s in sm.states],
            "transitions": [{"transition_id": t.transition_id, "name": t.name,
                             "from_state": t.from_state, "to_state": t.to_state,
                             "trigger_action_type_id": t.trigger_action_type_id,
                             "guard": t.guard.value if hasattr(t.guard, "value") else t.guard,
                             "guard_condition": t.guard_condition,
                             "required_roles": t.required_roles,
                             "side_effects": t.side_effects, "priority": t.priority}
                            for t in sm.transitions],
            "initial_state": sm.initial_state,
            "current_states": sm.current_states,
            "bound_action_type_ids": sm.bound_action_type_ids,
            "scenario_id": sm.scenario_id, "is_active": sm.is_active,
            "created_at": sm.created_at, "updated_at": sm.updated_at
        }

    def _deserialize_sm(self, data):
        result = dict(data)
        for key in ("states", "transitions", "current_states", "bound_action_type_ids"):
            if key in result and isinstance(result[key], str):
                result[key] = json.loads(result[key])
        if "is_active" in result and isinstance(result["is_active"], int):
            result["is_active"] = bool(result["is_active"])
        return result

    def _evaluate_condition(self, condition, context):
        try:
            return safe_eval(condition, context)
        except Exception:
            return False
