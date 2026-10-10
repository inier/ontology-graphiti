import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';

const getMock = vi.fn();
const setMock = vi.fn();

vi.mock('../services/extractorModeApi', () => ({
  extractorModeApi: {
    getExtractorMode: (...a: unknown[]) => getMock(...a),
    setExtractorMode: (...a: unknown[]) => setMock(...a),
  },
}));

import { ExtractorModeCard } from '../components/ExtractorModeCard';

const INFO = {
  status: 'ok',
  mode: null,
  effective_mode: 'query',
  default_mode: 'query',
  available_modes: ['off', 'inject', 'query'],
  descriptions: {
    off: '关闭归一化：实体原词直通',
    inject: '预加载全量注入',
    query: '按需查询（ontology_semantics）',
  },
  updated_by: 'admin-1',
  updated_at: '2026-10-09T00:00:00+00:00',
};

describe('ExtractorModeCard: 提取模式切换界面（ADR-089 C-D12 / E-17）', () => {
  beforeEach(() => {
    getMock.mockReset();
    setMock.mockReset();
    getMock.mockResolvedValue(INFO);
  });

  it('渲染当前生效 mode 与三个选项', async () => {
    render(<ExtractorModeCard />);
    await waitFor(() => expect(getMock).toHaveBeenCalled());
    expect(await screen.findByText(/当前生效/)).toBeInTheDocument();
    expect(screen.getAllByText('全量注入').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('关闭（原词直通）').length).toBeGreaterThanOrEqual(1);
  });

  it('切换选项调用 setExtractorMode', async () => {
    setMock.mockResolvedValue({ ...INFO, effective_mode: 'inject', mode: 'inject' });
    render(<ExtractorModeCard />);
    await screen.findByText(/当前生效/);
    // 第一个匹配为 Segmented 选项（描述列表在后）
    fireEvent.click(screen.getAllByText('全量注入')[0]);
    await waitFor(() => expect(setMock).toHaveBeenCalledWith('inject'));
  });
});
