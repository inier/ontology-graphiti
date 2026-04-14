"""Backward compatibility shim for core module.

.. deprecated::
    Import from odap.infra.graph.graph_service instead.
"""
import warnings
warnings.warn(
    "Importing from 'core' is deprecated. Use 'odap.infra.graph' or 'odap.infra.events' etc.",
    DeprecationWarning,
    stacklevel=2
)

from odap.infra.graph.graph_service import BattlefieldGraphManager
from odap.infra.events.hook_system import HookRegistry
from odap.infra.opa.opa_service import OPAManager
from odap.infra.resilience.fault_tolerance import FaultTolerance
from odap.infra.resilience.health_monitor import HealthMonitor
from odap.infra.resilience.state_persistence import StatePersistenceManager

__all__ = [
    'BattlefieldGraphManager',
    'HookRegistry',
    'OPAManager',
    'FaultTolerance',
    'HealthMonitor',
    'StatePersistenceManager',
]
