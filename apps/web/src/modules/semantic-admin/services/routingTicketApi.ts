/**
 * 路由工单 API（ADR-090 子项目 D D-D14）——tool 层缺口的完整工程债工作流。
 *
 * 覆盖 7 端点：list / stats / detail / events / assign / transition / comment。
 */
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const BASE = `${API_BASE}/api/semantic-admin/routing-tickets`;

export type TicketStatus =
  | 'open' | 'assigned' | 'in_progress' | 'resolved' | 'rejected' | 'closed';
export type TicketPriority = 'P0' | 'P1' | 'P2' | 'P3';

export interface RoutingTicket {
  id: string;
  gap_id: string | null;
  engine: string;
  expression: string;
  scope_key: string;
  title: string;
  description: string | null;
  priority: TicketPriority;
  status: TicketStatus;
  assignee: string | null;
  sla_deadline: string | null;
  sla_breached: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_note: string | null;
}

export interface TicketEvent {
  id: string;
  ticket_id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  actor: string;
  note: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface TicketStats {
  total: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  breached_count: number;
}

/** 合法状态机转换（前端用于禁用非法按钮，与后端 TICKET_TRANSITIONS 对齐）。 */
export const TICKET_TRANSITIONS: Record<TicketStatus, TicketStatus[]> = {
  open: ['assigned', 'rejected'],
  assigned: ['in_progress', 'open', 'rejected'],
  in_progress: ['resolved', 'rejected', 'assigned'],
  resolved: ['closed', 'in_progress'],
  rejected: [],
  closed: [],
};

export const PRIORITY_SLA_HOURS: Record<TicketPriority, number> = {
  P0: 4, P1: 24, P2: 72, P3: 168,
};

export const routingTicketApi = {
  list: (params: {
    status?: string; priority?: string; assignee?: string; engine?: string;
    page?: number; page_size?: number;
  } = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null)
        .map(([k, v]) => [k, String(v)]),
    ).toString();
    return fetchJson<{ items: RoutingTicket[]; total: number;
                       page: number; page_size: number }>(`${BASE}/?${qs}`);
  },
  stats: () => fetchJson<TicketStats>(`${BASE}/stats`),
  get: (id: string) => fetchJson<RoutingTicket>(`${BASE}/${id}`),
  events: (id: string) =>
    fetchJson<{ ticket_id: string; events: TicketEvent[] }>(`${BASE}/${id}/events`),
  assign: (id: string, body: { assignee: string; priority?: TicketPriority }) =>
    fetchJson<{ status: string; ticket: RoutingTicket }>(`${BASE}/${id}/assign`,
      { method: 'POST', body: JSON.stringify(body) }),
  transition: (id: string, body: { to_status: TicketStatus; note?: string }) =>
    fetchJson<{ status: string; ticket: RoutingTicket }>(`${BASE}/${id}/transition`,
      { method: 'POST', body: JSON.stringify(body) }),
  comment: (id: string, note: string) =>
    fetchJson<{ status: string; ticket_id: string }>(`${BASE}/${id}/comment`,
      { method: 'POST', body: JSON.stringify({ note }) }),
};
