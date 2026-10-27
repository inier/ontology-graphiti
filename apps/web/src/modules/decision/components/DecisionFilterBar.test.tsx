import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DecisionFilterBar } from './DecisionFilterBar';
import type { DecisionFilters } from '../types';

const filters: DecisionFilters = { results: [], confidenceBand: 'all' };

describe('DecisionFilterBar', () => {
  it('渲染契约支持的筛选控件（时间/结果/来源/置信度/关键词）', () => {
    render(<DecisionFilterBar value={filters} onChange={vi.fn()} />);
    // RangePicker 内部会复制 aria-label（起止输入框），故用 getAllByLabelText
    expect(screen.getAllByLabelText('创建时间范围').length).toBeGreaterThan(0);
    expect(screen.getByLabelText('执行结果')).toBeInTheDocument();
    expect(screen.getByLabelText('来源入口')).toBeInTheDocument();
    expect(screen.getByLabelText('置信度区间')).toBeInTheDocument();
    expect(screen.getByLabelText('关键词')).toBeInTheDocument();
  });

  it('契约缺参数的「仅看证据不完整」不渲染，也不留灰色占位', () => {
    render(<DecisionFilterBar value={filters} onChange={vi.fn()} />);
    expect(screen.queryByText('仅看证据不完整')).toBeNull();
    expect(screen.queryByText('暂不支持')).toBeNull();
  });

  it('compact 模式收窄为时间/结果/关键词，且不出现 Agent 可见筛选器', () => {
    render(<DecisionFilterBar value={filters} onChange={vi.fn()} compact />);
    expect(screen.getByLabelText('关键词')).toBeInTheDocument();
    expect(screen.queryByLabelText('来源入口')).toBeNull();
    expect(screen.queryByLabelText('置信度区间')).toBeNull();
    expect(screen.queryByLabelText('按 Agent 过滤')).toBeNull();
  });
});
