"""
Domain event bus for the ontology design subsystem.

This is the **decoupling mechanism** that allows design/* to publish events
without importing from application/*. Application/* modules can subscribe
to these events from outside (in application code), keeping the dependency
direction correct: design → contract ← application.

R-P0-001 fix: Replaces the previous design→application direct imports in
pipeline_service.py with publish-subscribe via this bus.

Usage:
    # In design/* (the publisher):
    from .events import get_event_bus, EntityExtractedEvent
    bus = get_event_bus()
    bus.publish(EntityExtractedEvent(entities=[...]))

    # In application/* (the subscriber):
    from odap.biz.core.ontology.design.events import get_event_bus, EntityExtractedEvent
    bus = get_event_bus()
    bus.subscribe(EntityExtractedEvent, my_handler_function)
"""
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Type, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events. Subclass for specific events.

    Using @dataclass(frozen=True) means events are immutable, just like
    the contract views (see contract/interface.py).
    """
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass(frozen=True)
class EntityExtractedEvent(DomainEvent):
    """Published when LLM extraction produces new entity types.

    The application layer's OMS handler subscribes to this to register
    the entity types in the ontology management system.
    """
    entities: tuple = ()  # tuple of entity dicts (immutable for frozen dataclass)


@dataclass(frozen=True)
class OntologyVersionRolledBackEvent(DomainEvent):
    """Published when an ontology version is rolled back.

    Application-layer handlers (Servitization catalog, Agent cache) subscribe
    to this to mark dependent assets as needs_update.
    """
    ontology_id: str = ""
    new_version_id: str = ""


@dataclass(frozen=True)
class OntologyCreatedEvent(DomainEvent):
    """Published when a new ontology is created."""
    ontology_id: str = ""
    version_id: str = ""


@dataclass(frozen=True)
class OntologyPublishedEvent(DomainEvent):
    """Published when an ontology version is published (made active)."""
    ontology_id: str = ""
    version_id: str = ""


# ============ Event bus ============

class EventBus:
    """Thread-safe in-process event bus.

    Multiple subscribers can register for the same event type. Subscribers
    are called synchronously in registration order.

    Handlers receive the event instance and may raise; an exception in one
    handler does not prevent later handlers from being called (errors are
    logged with `logger.exception`).
    """

    def __init__(self):
        self._subscribers: Dict[Type[DomainEvent], List[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_type: Type[DomainEvent], handler: Callable) -> None:
        """Register a handler for a specific event type.

        The handler signature is: `handler(event: DomainEvent) -> None`
        """
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(handler)
            logger.debug(
                "Subscribed %s to %s (total handlers: %d)",
                getattr(handler, "__name__", repr(handler)),
                event_type.__name__,
                len(self._subscribers[event_type]),
            )

    def unsubscribe(self, event_type: Type[DomainEvent], handler: Callable) -> bool:
        """Unregister a handler. Returns True if removed."""
        with self._lock:
            if event_type not in self._subscribers:
                return False
            try:
                self._subscribers[event_type].remove(handler)
                return True
            except ValueError:
                return False

    def publish(self, event: DomainEvent) -> int:
        """Publish an event. Returns the number of handlers called.

        Handlers are called synchronously. Exceptions are logged but not
        propagated (so one bad handler doesn't break the publisher).
        """
        event_type = type(event)
        with self._lock:
            handlers = list(self._subscribers.get(event_type, []))

        if not handlers:
            return 0

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Error in event handler %s for %s",
                    getattr(handler, "__name__", repr(handler)),
                    event_type.__name__,
                )
        return len(handlers)

    def clear(self) -> None:
        """Remove all subscribers. Mainly for testing."""
        with self._lock:
            self._subscribers.clear()


# ============ Module-level singleton ============

_event_bus: Optional[EventBus] = None
_singleton_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Get the global event bus singleton (thread-safe lazy init)."""
    global _event_bus
    if _event_bus is None:
        with _singleton_lock:
            if _event_bus is None:
                _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus. For testing only."""
    global _event_bus
    with _singleton_lock:
        _event_bus = None
