"""routing_tickets 领域模型包。"""
from .ticket import (
    TicketStatus, TicketPriority, TICKET_TRANSITIONS, TERMINAL_STATUSES,
    PRIORITY_SLA_HOURS, DEFAULT_PRIORITY, compute_sla_deadline, is_breached,
    new_ticket_id,
)

__all__ = [
    "TicketStatus", "TicketPriority", "TICKET_TRANSITIONS",
    "TERMINAL_STATUSES", "PRIORITY_SLA_HOURS", "DEFAULT_PRIORITY",
    "compute_sla_deadline", "is_breached", "new_ticket_id",
]
