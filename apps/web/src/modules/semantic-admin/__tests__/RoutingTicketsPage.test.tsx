import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';

const listMock = vi.fn();
const statsMock = vi.fn();
const navigateMock = vi.fn();

vi.mock('../services/routingTicketApi', async () => {
  const actual = await vi.importActual<typeof import('../services/routingTicketApi')>(
    '../services/routingTicketApi');
  return {
    ...actual,
    routingTicketApi: {
      list: (...a: unknown[]) => listMock(...a),
      stats: (...a: unknown[]) => statsMock(...a),
    },
  };
});

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}));

import { RoutingTicketsPage } from '../pages/RoutingTicketsPage';

const TICKET = {
  id: 't-1', gap_id: 'g-1', engine: 'nl_engine', expression: '找相似武将',
  scope_key: 'ws1::d1', title: '检索引擎能力缺口：找相似武将', description: null,
  priority: 'P2', status: 'open', assignee: null,
  sla_deadline: '2026-10-12T00:00:00+00:00', sla_breached: false,
  created_by: 'alice', created_at: '2026-10-09T00:00:00+00:00',
  updated_at: '2026-10-09T00:00:00+00:00', resolved_at: null,
  resolved_by: null, resolution_note: null,
};

describe('RoutingTicketsPage: 工单列表（ADR-090 D-D14 / E-16）', () => {
  beforeEach(() => {
    listMock.mockReset();
    statsMock.mockReset();
    navigateMock.mockReset();
    listMock.mockResolvedValue({ items: [TICKET], total: 1, page: 1, page_size: 50 });
    statsMock.mockResolvedValue({
      total: 1, by_status: { open: 1 }, by_priority: { P2: 1 }, breached_count: 0,
    });
  });

  it('渲染统计卡与工单行', async () => {
    render(<RoutingTicketsPage />);
    await waitFor(() => expect(listMock).toHaveBeenCalled());
    expect(await screen.findByText('工单总数')).toBeInTheDocument();
    expect(await screen.findByText(/检索引擎能力缺口/)).toBeInTheDocument();
    expect(await screen.findByText('nl_engine')).toBeInTheDocument();
  });

  it('SLA 违约工单展示红色高亮标记', async () => {
    listMock.mockResolvedValue({
      items: [{ ...TICKET, sla_breached: true }], total: 1, page: 1, page_size: 50,
    });
    statsMock.mockResolvedValue({
      total: 1, by_status: { open: 1 }, by_priority: { P2: 1 }, breached_count: 1,
    });
    render(<RoutingTicketsPage />);
    await waitFor(() => expect(listMock).toHaveBeenCalled());
    expect((await screen.findAllByText(/已违约/)).length).toBeGreaterThanOrEqual(1);
  });
});
