import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DecisionStatusTag } from './DecisionStatusTag';

describe('DecisionStatusTag —— 5 类标签 / 4 色系', () => {
  it('双参映射出「部分成功」，不显示 outcome 原文', () => {
    render(<DecisionStatusTag status="executed" outcome="partial_success" />);
    expect(screen.getByText('部分成功')).toBeInTheDocument();
    expect(screen.queryByText('partial_success')).toBeNull();
  });

  it('executed + success → 执行成功', () => {
    const { container } = render(<DecisionStatusTag status="executed" outcome="success" />);
    expect(screen.getByText('执行成功')).toBeInTheDocument();
    expect(container.querySelector('.dsi-status--success')).not.toBeNull();
  });

  it('待定两细分同属 warning 色系，只靠文案区分', () => {
    const { container, rerender } = render(<DecisionStatusTag status="pending" outcome="pending" />);
    expect(screen.getByText('待定（待裁定）')).toBeInTheDocument();
    expect(container.querySelector('.dsi-status--pending')).not.toBeNull();

    rerender(<DecisionStatusTag status="executing" outcome="pending" />);
    expect(screen.getByText('待定（待执行确认）')).toBeInTheDocument();
    expect(container.querySelector('.dsi-status--pending')).not.toBeNull();
  });

  it('已驳回用中性色而非错误色', () => {
    const { container } = render(<DecisionStatusTag status="rejected" outcome="rejected" />);
    expect(screen.getByText('已驳回')).toBeInTheDocument();
    expect(container.querySelector('.dsi-status--failure')).toBeNull();
    expect(container.querySelector('.dsi-status--rejected')).not.toBeNull();
  });

  it('状态与结果矛盾时追加提示图标，但标签仍以 status 为准', () => {
    render(<DecisionStatusTag status="executed" outcome="failure" />);
    expect(screen.getByText('执行成功')).toBeInTheDocument();
    expect(screen.getByLabelText('状态与结果字段不一致')).toBeInTheDocument();
  });

  it('历史数据标注为可见文字（不是胶囊样式）', () => {
    render(<DecisionStatusTag status="pending" outcome="pending" statusAssumed />);
    expect(screen.getByText('历史数据，流程状态未记录')).toBeInTheDocument();
  });
});
