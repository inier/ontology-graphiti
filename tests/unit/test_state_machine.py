import pytest
import os
import json
from datetime import datetime


def _make_sm_storage(tmp_path):
    from odap.biz.core.ontology.runtime.state_machine.storage.sqlite_state_machine_storage import SQLiteStateMachineStorage
    db_path = str(tmp_path / "test_sm.db")
    return SQLiteStateMachineStorage(db_path=db_path)


def _make_sm_data(**overrides):
    defaults = {
        "sm_id": "sm-test-001",
        "name": "TestStateMachine",
        "description": "A test state machine",
        "target_object_type": "Unit",
        "states": [
            {"state_id": "s1", "name": "idle", "state_type": "initial"},
            {"state_id": "s2", "name": "active", "state_type": "normal"},
            {"state_id": "s3", "name": "completed", "state_type": "final"},
        ],
        "transitions": [
            {"transition_id": "tr1", "name": "activate", "from_state": "idle", "to_state": "active",
             "trigger_action_type_id": "action-activate", "guard": "always", "priority": 0},
            {"transition_id": "tr2", "name": "complete", "from_state": "active", "to_state": "completed",
             "trigger_action_type_id": "action-complete", "guard": "always", "priority": 0},
        ],
        "initial_state": "idle",
        "current_states": {},
        "bound_action_type_ids": [],
        "scenario_id": "sc-1",
        "is_active": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    defaults.update(overrides)
    return defaults


class TestSQLiteStateMachineStorage:
    def test_init_db(self, tmp_path):
        storage = _make_sm_storage(tmp_path)
        assert os.path.exists(storage.db_path)

    def test_state_machine_crud(self, tmp_path):
        storage = _make_sm_storage(tmp_path)
        sm_data = _make_sm_data()
        saved = storage.save_state_machine(sm_data)
        assert saved["sm_id"] == "sm-test-001"

        fetched = storage.get_state_machine("sm-test-001")
        assert fetched is not None
        assert fetched["name"] == "TestStateMachine"
        assert fetched["target_object_type"] == "Unit"

        assert storage.get_state_machine("nonexistent") is None

        result = storage.delete_state_machine("sm-test-001")
        assert result is True

        result = storage.delete_state_machine("sm-test-001")
        assert result is False

    def test_get_by_object_type(self, tmp_path):
        storage = _make_sm_storage(tmp_path)
        sm_data = _make_sm_data()
        storage.save_state_machine(sm_data)

        fetched = storage.get_state_machine_by_object_type("Unit")
        assert fetched is not None
        assert fetched["sm_id"] == "sm-test-001"

        assert storage.get_state_machine_by_object_type("NonExistent") is None

    def test_list_state_machines(self, tmp_path):
        storage = _make_sm_storage(tmp_path)
        storage.save_state_machine(_make_sm_data(sm_id="sm-1", scenario_id="sc-1"))
        storage.save_state_machine(_make_sm_data(sm_id="sm-2", scenario_id="sc-2"))

        all_sms = storage.list_state_machines()
        assert len(all_sms) == 2

        sc1_sms = storage.list_state_machines(scenario_id="sc-1")
        assert len(sc1_sms) == 1

        active_sms = storage.list_state_machines(is_active=True)
        assert len(active_sms) == 2

    def test_json_field_serialization(self, tmp_path):
        storage = _make_sm_storage(tmp_path)
        sm_data = _make_sm_data(
            states=[{"name": "s1"}],
            transitions=[{"name": "t1"}],
            current_states={"obj-1": "active"},
            bound_action_type_ids=["action-1"]
        )
        storage.save_state_machine(sm_data)
        fetched = storage.get_state_machine("sm-test-001")
        states = json.loads(fetched["states"])
        assert len(states) == 1
        assert states[0]["name"] == "s1"
        current = json.loads(fetched["current_states"])
        assert current["obj-1"] == "active"


class TestStateMachineEngine:
    def _make_engine(self, tmp_path):
        from odap.biz.core.ontology.runtime.state_machine.impl.state_machine_engine import StateMachineEngine
        from odap.biz.core.ontology.runtime.state_machine.storage.sqlite_state_machine_storage import SQLiteStateMachineStorage
        storage = SQLiteStateMachineStorage(db_path=str(tmp_path / "test_engine.db"))
        return StateMachineEngine(storage=storage)

    def test_create_state_machine(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine.create_state_machine(
            name="UnitSM",
            target_object_type="Unit",
            states=[
                {"name": "idle", "state_type": "initial"},
                {"name": "active", "state_type": "normal"},
            ],
            transitions=[
                {"name": "activate", "from_state": "idle", "to_state": "active",
                 "trigger_action_type_id": "act-1", "guard": "always"},
            ]
        )
        assert result["status"] == "success"
        assert result["state_count"] == 2
        assert result["initial_state"] == "idle"

    def test_create_auto_detect_initial(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine.create_state_machine(
            name="AutoSM",
            target_object_type="Item",
            states=[
                {"name": "draft", "state_type": "initial"},
                {"name": "published", "state_type": "normal"},
            ],
            transitions=[]
        )
        assert result["initial_state"] == "draft"

    def test_get_state_machine(self, tmp_path):
        engine = self._make_engine(tmp_path)
        created = engine.create_state_machine(
            name="GetSM",
            target_object_type="Unit",
            states=[{"name": "idle", "state_type": "initial"}],
            transitions=[]
        )
        sm_id = created["sm_id"]

        result = engine.get_state_machine(sm_id)
        assert result["status"] == "success"
        assert result["name"] == "GetSM"

        result = engine.get_state_machine("nonexistent")
        assert result["status"] == "error"

    def test_get_by_object_type(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.create_state_machine(
            name="TypeSM",
            target_object_type="Weapon",
            states=[{"name": "idle", "state_type": "initial"}],
            transitions=[]
        )
        result = engine.get_state_machine_by_object_type("Weapon")
        assert result["status"] == "success"

        result = engine.get_state_machine_by_object_type("NonExistent")
        assert result["status"] == "error"

    def test_list_state_machines(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.create_state_machine(
            name="SM1", target_object_type="T1",
            states=[{"name": "idle", "state_type": "initial"}], transitions=[]
        )
        engine.create_state_machine(
            name="SM2", target_object_type="T2",
            states=[{"name": "idle", "state_type": "initial"}], transitions=[]
        )
        result = engine.list_state_machines()
        assert result["status"] == "success"
        assert result["count"] == 2

    def test_delete_state_machine(self, tmp_path):
        engine = self._make_engine(tmp_path)
        created = engine.create_state_machine(
            name="DelSM", target_object_type="Unit",
            states=[{"name": "idle", "state_type": "initial"}], transitions=[]
        )
        result = engine.delete_state_machine(created["sm_id"])
        assert result["status"] == "success"

        result = engine.delete_state_machine("nonexistent")
        assert result["status"] == "error"

    def test_transition_success(self, tmp_path):
        engine = self._make_engine(tmp_path)
        created = engine.create_state_machine(
            name="TransSM", target_object_type="Unit",
            states=[
                {"name": "idle", "state_type": "initial"},
                {"name": "active", "state_type": "normal"},
            ],
            transitions=[
                {"name": "activate", "from_state": "idle", "to_state": "active",
                 "trigger_action_type_id": "act-1", "guard": "always"},
            ]
        )
        sm_id = created["sm_id"]
        result = engine.transition(sm_id, "obj-1", "act-1")
        assert result["status"] == "success"
        assert result["from_state"] == "idle"
        assert result["to_state"] == "active"

    def test_transition_no_match(self, tmp_path):
        engine = self._make_engine(tmp_path)
        created = engine.create_state_machine(
            name="NoMatchSM", target_object_type="Unit",
            states=[{"name": "idle", "state_type": "initial"}],
            transitions=[]
        )
        result = engine.transition(created["sm_id"], "obj-1", "act-x")
        assert result["status"] == "error"

    def test_transition_role_guard(self, tmp_path):
        engine = self._make_engine(tmp_path)
        created = engine.create_state_machine(
            name="RoleSM", target_object_type="Unit",
            states=[
                {"name": "idle", "state_type": "initial"},
                {"name": "active", "state_type": "normal"},
            ],
            transitions=[
                {"name": "activate", "from_state": "idle", "to_state": "active",
                 "trigger_action_type_id": "act-1", "guard": "role_based",
                 "required_roles": ["admin"]},
            ]
        )
        sm_id = created["sm_id"]

        result = engine.transition(sm_id, "obj-1", "act-1", context={"roles": ["user"]})
        assert result["status"] == "error"
        assert "Insufficient" in result["message"]

        result = engine.transition(sm_id, "obj-1", "act-1", context={"roles": ["admin"]})
        assert result["status"] == "success"

    def test_transition_condition_guard(self, tmp_path):
        engine = self._make_engine(tmp_path)
        created = engine.create_state_machine(
            name="CondSM", target_object_type="Unit",
            states=[
                {"name": "idle", "state_type": "initial"},
                {"name": "active", "state_type": "normal"},
            ],
            transitions=[
                {"name": "activate", "from_state": "idle", "to_state": "active",
                 "trigger_action_type_id": "act-1", "guard": "condition_based",
                 "guard_condition": "power > 50"},
            ]
        )
        sm_id = created["sm_id"]

        result = engine.transition(sm_id, "obj-1", "act-1", context={"power": 30})
        assert result["status"] == "error"

        result = engine.transition(sm_id, "obj-1", "act-1", context={"power": 80})
        assert result["status"] == "success"

    def test_transition_manual_approval(self, tmp_path):
        engine = self._make_engine(tmp_path)
        created = engine.create_state_machine(
            name="ApprovalSM", target_object_type="Unit",
            states=[
                {"name": "pending", "state_type": "initial"},
                {"name": "approved", "state_type": "normal"},
            ],
            transitions=[
                {"name": "approve", "from_state": "pending", "to_state": "approved",
                 "trigger_action_type_id": "act-approve", "guard": "manual_approval"},
            ]
        )
        sm_id = created["sm_id"]

        result = engine.transition(sm_id, "obj-1", "act-approve")
        assert result["status"] == "pending_approval"

        result = engine.transition(sm_id, "obj-1", "act-approve", context={"approved": True})
        assert result["status"] == "success"

    def test_get_object_state(self, tmp_path):
        engine = self._make_engine(tmp_path)
        created = engine.create_state_machine(
            name="StateSM", target_object_type="Unit",
            states=[
                {"name": "idle", "state_type": "initial"},
                {"name": "active", "state_type": "normal"},
            ],
            transitions=[
                {"name": "activate", "from_state": "idle", "to_state": "active",
                 "trigger_action_type_id": "act-1", "guard": "always"},
            ]
        )
        sm_id = created["sm_id"]

        result = engine.get_object_state(sm_id, "obj-1")
        assert result["status"] == "success"
        assert result["current_state"] == "idle"
        assert len(result["available_transitions"]) == 1

        engine.transition(sm_id, "obj-1", "act-1")
        result = engine.get_object_state(sm_id, "obj-1")
        assert result["current_state"] == "active"

    def test_reset_object_state(self, tmp_path):
        engine = self._make_engine(tmp_path)
        created = engine.create_state_machine(
            name="ResetSM", target_object_type="Unit",
            states=[
                {"name": "idle", "state_type": "initial"},
                {"name": "active", "state_type": "normal"},
            ],
            transitions=[
                {"name": "activate", "from_state": "idle", "to_state": "active",
                 "trigger_action_type_id": "act-1", "guard": "always"},
            ]
        )
        sm_id = created["sm_id"]
        engine.transition(sm_id, "obj-1", "act-1")

        result = engine.reset_object_state(sm_id, "obj-1")
        assert result["status"] == "success"
        assert result["current_state"] == "idle"

    def test_bind_action_type(self, tmp_path):
        engine = self._make_engine(tmp_path)
        created = engine.create_state_machine(
            name="BindSM", target_object_type="Unit",
            states=[{"name": "idle", "state_type": "initial"}],
            transitions=[]
        )
        sm_id = created["sm_id"]

        result = engine.bind_action_type(sm_id, "action-type-1")
        assert result["status"] == "success"
        assert "action-type-1" in result["bound_action_type_ids"]

        result = engine.bind_action_type(sm_id, "action-type-1")
        assert result["status"] == "success"
        assert result["bound_action_type_ids"].count("action-type-1") == 1

    def test_transition_priority(self, tmp_path):
        engine = self._make_engine(tmp_path)
        created = engine.create_state_machine(
            name="PrioritySM", target_object_type="Unit",
            states=[
                {"name": "idle", "state_type": "initial"},
                {"name": "active", "state_type": "normal"},
                {"name": "error", "state_type": "error"},
            ],
            transitions=[
                {"name": "activate", "from_state": "idle", "to_state": "active",
                 "trigger_action_type_id": "act-1", "guard": "always", "priority": 0},
                {"name": "fail", "from_state": "idle", "to_state": "error",
                 "trigger_action_type_id": "act-1", "guard": "always", "priority": 10},
            ]
        )
        sm_id = created["sm_id"]
        result = engine.transition(sm_id, "obj-1", "act-1")
        assert result["status"] == "success"
        assert result["to_state"] == "error"


class TestStateMachineModels:
    def test_state_type_enum(self):
        from odap.biz.core.ontology.runtime.state_machine.models import StateType
        assert StateType.INITIAL.value == "initial"
        assert StateType("normal") == StateType.NORMAL

    def test_transition_guard_enum(self):
        from odap.biz.core.ontology.runtime.state_machine.models import TransitionGuard
        assert TransitionGuard.ALWAYS.value == "always"
        assert TransitionGuard("role_based") == TransitionGuard.ROLE_BASED

    def test_state_definition_defaults(self):
        from odap.biz.core.ontology.runtime.state_machine.models import StateDefinition
        sd = StateDefinition()
        assert sd.state_id.startswith("state-")
        assert sd.on_enter_actions == []
        assert sd.on_exit_actions == []

    def test_state_transition_defaults(self):
        from odap.biz.core.ontology.runtime.state_machine.models import StateTransition
        st = StateTransition()
        assert st.transition_id.startswith("trans-")
        assert st.required_roles == []
        assert st.side_effects == []

    def test_ontology_state_machine_defaults(self):
        from odap.biz.core.ontology.runtime.state_machine.models import OntologyStateMachine
        sm = OntologyStateMachine()
        assert sm.sm_id.startswith("sm-")
        assert sm.states == []
        assert sm.is_active is True


class TestStateMachineService:
    def _make_service(self, tmp_path):
        from odap.biz.core.ontology.runtime.state_machine.services import StateMachineService
        from odap.biz.core.ontology.runtime.state_machine.storage.sqlite_state_machine_storage import SQLiteStateMachineStorage
        StateMachineService._instance = None
        storage = SQLiteStateMachineStorage(db_path=str(tmp_path / "test_svc.db"))
        return StateMachineService(storage=storage)

    def test_create_and_get(self, tmp_path):
        svc = self._make_service(tmp_path)
        result = svc.create_state_machine(
            name="SvcSM", target_object_type="Unit",
            states=[{"name": "idle", "state_type": "initial"}],
            transitions=[]
        )
        assert result["status"] == "success"

        fetched = svc.get_state_machine(result["sm_id"])
        assert fetched["status"] == "success"

    def test_transition_via_service(self, tmp_path):
        svc = self._make_service(tmp_path)
        created = svc.create_state_machine(
            name="SvcTransSM", target_object_type="Unit",
            states=[
                {"name": "idle", "state_type": "initial"},
                {"name": "active", "state_type": "normal"},
            ],
            transitions=[
                {"name": "activate", "from_state": "idle", "to_state": "active",
                 "trigger_action_type_id": "act-1", "guard": "always"},
            ]
        )
        result = svc.transition(created["sm_id"], "obj-1", "act-1")
        assert result["status"] == "success"

    def test_service_returns_error_dict(self, tmp_path):
        svc = self._make_service(tmp_path)
        result = svc.get_state_machine("nonexistent")
        assert result["status"] == "error"
        assert "message" in result
