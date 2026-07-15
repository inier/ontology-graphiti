from ..impl.state_machine_engine import StateMachineEngine
from ..storage import SQLiteStateMachineStorage
from typing import Dict, Any, Optional


class StateMachineService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, storage=None):
        self.engine = StateMachineEngine(storage or SQLiteStateMachineStorage())

    def create_state_machine(self, name, target_object_type, states, transitions,
                             initial_state="", description="", scenario_id=None,
                             bound_action_type_ids=None):
        return self.engine.create_state_machine(
            name=name, target_object_type=target_object_type,
            states=states, transitions=transitions,
            initial_state=initial_state, description=description,
            scenario_id=scenario_id, bound_action_type_ids=bound_action_type_ids)

    def get_state_machine(self, sm_id):
        return self.engine.get_state_machine(sm_id)

    def get_state_machine_by_object_type(self, object_type):
        return self.engine.get_state_machine_by_object_type(object_type)

    def list_state_machines(self, scenario_id=None, is_active=None):
        return self.engine.list_state_machines(scenario_id, is_active)

    def delete_state_machine(self, sm_id):
        return self.engine.delete_state_machine(sm_id)

    def transition(self, sm_id, object_id, action_type_id, context=None):
        return self.engine.transition(sm_id, object_id, action_type_id, context)

    def get_object_state(self, sm_id, object_id):
        return self.engine.get_object_state(sm_id, object_id)

    def reset_object_state(self, sm_id, object_id):
        return self.engine.reset_object_state(sm_id, object_id)

    def bind_action_type(self, sm_id, action_type_id):
        return self.engine.bind_action_type(sm_id, action_type_id)


get_state_machine_service = StateMachineService.get_instance
