from .types import StateType, TransitionGuard
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


@dataclass
class StateDefinition:
    state_id: str = field(default_factory=lambda: f"state-{uuid.uuid4().hex[:8]}")
    name: str = ""
    state_type: StateType = StateType.NORMAL
    description: str = ""
    on_enter_actions: List[str] = field(default_factory=list)
    on_exit_actions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateTransition:
    transition_id: str = field(default_factory=lambda: f"trans-{uuid.uuid4().hex[:8]}")
    name: str = ""
    from_state: str = ""
    to_state: str = ""
    trigger_action_type_id: str = ""
    guard: TransitionGuard = TransitionGuard.ALWAYS
    guard_condition: str = ""
    required_roles: List[str] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OntologyStateMachine:
    sm_id: str = field(default_factory=lambda: f"sm-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    target_object_type: str = ""
    states: List[StateDefinition] = field(default_factory=list)
    transitions: List[StateTransition] = field(default_factory=list)
    initial_state: str = ""
    current_states: Dict[str, str] = field(default_factory=dict)
    bound_action_type_ids: List[str] = field(default_factory=list)
    scenario_id: Optional[str] = None
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
