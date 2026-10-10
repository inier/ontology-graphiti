import { describe, it, expect, vi, beforeEach } from 'vitest';
import { routingTicketApi, PRIORITY_SLA_HOURS, TICKET_TRANSITIONS }
  from '../services/routingTicketApi';

const mockFetch = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: (...args: unknown[]) => mockFetch(...args),
}));

describe('routingTicketApi.ts: 7 端点 URL 与 body', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({ items: [], total: 0 });
  });

  it('list: GET /api/semantic-admin/routing-tickets/ 且含 status/priority', async () => {
    await routingTicketApi.list({ status: 'open', priority: 'P1', page: 1 });
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('/api/semantic-admin/routing-tickets/');
    expect(url).toContain('status=open');
    expect(url).toContain('priority=P1');
  });

  it('stats: GET .../stats', async () => {
    await routingTicketApi.stats();
    expect(mockFetch.mock.calls[0][0]).toContain(
      '/api/semantic-admin/routing-tickets/stats');
  });

  it('get: GET .../{id}', async () => {
    await routingTicketApi.get('t-1');
    expect(mockFetch.mock.calls[0][0]).toContain(
      '/api/semantic-admin/routing-tickets/t-1');
  });

  it('events: GET .../{id}/events', async () => {
    await routingTicketApi.events('t-2');
    expect(mockFetch.mock.calls[0][0]).toContain(
      '/api/semantic-admin/routing-tickets/t-2/events');
  });

  it('assign: POST .../{id}/assign 且 body 含 assignee/priority', async () => {
    await routingTicketApi.assign('t-3', { assignee: 'bob', priority: 'P0' });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain('/routing-tickets/t-3/assign');
    expect((opts as RequestInit).method).toBe('POST');
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.assignee).toBe('bob');
    expect(body.priority).toBe('P0');
  });

  it('transition: POST .../{id}/transition 且 body 含 to_status', async () => {
    await routingTicketApi.transition('t-4', { to_status: 'in_progress', note: '开始' });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain('/routing-tickets/t-4/transition');
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.to_status).toBe('in_progress');
  });

  it('comment: POST .../{id}/comment 且 body 含 note', async () => {
    await routingTicketApi.comment('t-5', '需要换引擎');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain('/routing-tickets/t-5/comment');
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.note).toBe('需要换引擎');
  });

  it('SLA 常量与状态机与后端契约一致（P0=4h；open→assigned|rejected）', () => {
    expect(PRIORITY_SLA_HOURS.P0).toBe(4);
    expect(PRIORITY_SLA_HOURS.P2).toBe(72);
    expect(TICKET_TRANSITIONS.open).toEqual(['assigned', 'rejected']);
    expect(TICKET_TRANSITIONS.closed).toEqual([]);
  });
});
