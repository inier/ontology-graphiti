/**
 * Wiki 四态块测试
 *
 * 断言的错误文案是"可诊断"的：必须出现具体 error_code 与后端 message，
 * 不允许只显示"加载失败"。
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { WikiStateBlock } from '../components/WikiStateBlock';

const BASE = {
  emptyTitle: '还没有符合条件的 Wiki 条目',
  emptyDesc: '请放宽筛选条件后再查看。',
};

describe('WikiStateBlock', () => {
  it('loading 渲染骨架并标记 aria-busy', () => {
    const { container } = render(
      <WikiStateBlock {...BASE} phase="loading" error={null}>
        <div>数据</div>
      </WikiStateBlock>,
    );
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(container.querySelectorAll('.wiki-skeleton')).toHaveLength(3);
    expect(screen.queryByText('数据')).toBeNull();
  });

  it('idle 也按 loading 处理，避免首帧闪空态', () => {
    const { container } = render(
      <WikiStateBlock {...BASE} phase="idle" error={null} skeletonCount={2}>
        <div>数据</div>
      </WikiStateBlock>,
    );
    expect(container.querySelectorAll('.wiki-skeleton')).toHaveLength(2);
  });

  it('error 展示 error_code、message、trace_id 与重试按钮', () => {
    const onRetry = vi.fn();
    render(
      <WikiStateBlock
        {...BASE}
        phase="error"
        error={{
          errorCode: 'WIKI_LIST_UPSTREAM_TIMEOUT',
          message: '条目列表上游 SQLite 查询超时（read txn 8s）',
          traceId: 'mock-list-1760700000000',
          status: 504,
        }}
        onRetry={onRetry}
      >
        <div>数据</div>
      </WikiStateBlock>,
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('WIKI_LIST_UPSTREAM_TIMEOUT')).toBeInTheDocument();
    expect(screen.getByText('条目列表上游 SQLite 查询超时（read txn 8s）')).toBeInTheDocument();
    expect(screen.getByText(/trace_id: mock-list-1760700000000/)).toBeInTheDocument();
    expect(screen.queryByText('数据')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /重试/ }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('error 带冲突对象时额外展示，便于定位是哪条冲突', () => {
    render(
      <WikiStateBlock
        {...BASE}
        phase="error"
        error={{
          errorCode: 'WIKI_VERSION_CONFLICT',
          message: '合并前版本校验失败：discard 侧已被他人更新',
          traceId: 'trace-1',
          status: 409,
          conflictingId: '01J9Z6Q2X8K3M4N5P6R7S8T9V6',
        }}
      >
        <div>数据</div>
      </WikiStateBlock>,
    );
    expect(screen.getByText(/冲突对象：01J9Z6Q2X8K3M4N5P6R7S8T9V6/)).toBeInTheDocument();
  });

  it('error 但后端没给详情时给兜底说明，不渲染空 div', () => {
    render(
      <WikiStateBlock {...BASE} phase="error" error={null}>
        <div>数据</div>
      </WikiStateBlock>,
    );
    expect(screen.getByText('后端未返回错误详情')).toBeInTheDocument();
  });

  it('isEmpty 渲染空态标题与说明，且不渲染 children', () => {
    render(
      <WikiStateBlock {...BASE} phase="ready" error={null} isEmpty>
        <div>数据</div>
      </WikiStateBlock>,
    );
    expect(screen.getByText(BASE.emptyTitle)).toBeInTheDocument();
    expect(screen.getByText(BASE.emptyDesc)).toBeInTheDocument();
    expect(screen.queryByText('数据')).toBeNull();
  });

  it('ready 且非空时原样渲染 children', () => {
    render(
      <WikiStateBlock {...BASE} phase="ready" error={null}>
        <div>数据</div>
      </WikiStateBlock>,
    );
    expect(screen.getByText('数据')).toBeInTheDocument();
  });
});
