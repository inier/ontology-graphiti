/**
 * 同步窗口（E41）+ 按组取等待时长
 *
 * E41 的三条硬要求逐条对应下面的用例：
 * 1. 不得把残留态渲染成「执行中」
 * 2. 必须自带期限，超时升级为「状态可能未同步」
 * 3. 不得与执行记录矛盾
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { toSyncState, toWaitMinutes } from './displayStatus';
import type { PendingDecisionItem } from '../types';

const NOW = new Date('2026-10-24T12:00:00Z').getTime();

function minutesAgo(minutes: number): string {
  return new Date(NOW - minutes * 60_000).toISOString();
}

describe('toWaitMinutes：按 group 取字段，不可互替', () => {
  const base = {
    waited_minutes: 4560,
    decided_waited_minutes: 90,
  } as Pick<PendingDecisionItem, 'waited_minutes' | 'decided_waited_minutes'>;

  it('to_resolve 用 waited_minutes（自 createdAt）', () => {
    expect(toWaitMinutes({ ...base, group: 'to_resolve' })).toBe(4560);
  });

  it('to_execute 用 decided_waited_minutes（自 resolution.at），不拿 waited_minutes 顶替', () => {
    expect(toWaitMinutes({ ...base, group: 'to_execute' })).toBe(90);
  });

  it('to_execute 且 decided_waited_minutes 缺失 → null（「未知」），不回落到 waited_minutes', () => {
    expect(
      toWaitMinutes({ group: 'to_execute', waited_minutes: 4560, decided_waited_minutes: null }),
    ).toBeNull();
  });
});

describe('toSyncState', () => {
  it('非 executing 状态与本机制无关，返回 null', () => {
    expect(toSyncState({ status: 'pending', updatedAt: minutesAgo(99), now: NOW })).toBeNull();
    expect(toSyncState({ status: 'executed', updatedAt: minutesAgo(99), now: NOW })).toBeNull();
    expect(toSyncState({ status: 'failed', updatedAt: minutesAgo(99), now: NOW })).toBeNull();
  });

  it('期限内 → 「状态同步中」，且**不是**「执行中」', () => {
    const sync = toSyncState({ status: 'executing', updatedAt: minutesAgo(3), now: NOW });
    expect(sync?.kind).toBe('syncing');
    expect(sync?.label).toBe('状态同步中');
    expect(sync?.label).not.toBe('执行中');
    // 文案要含可核对信息（等了多久 + 期限）
    expect(sync?.detail).toContain('3 分钟');
    expect(sync?.detail).toContain('10 分钟');
  });

  it('超过期限（用 updated_at 计时）→ 「状态可能未同步」，不是「同步中」也不是「执行中」', () => {
    const sync = toSyncState({ status: 'executing', updatedAt: minutesAgo(45), now: NOW });
    expect(sync?.kind).toBe('stale');
    expect(sync?.label).toBe('状态可能未同步');
    expect(sync?.detail).toContain('45 分钟');
    expect(sync?.detail).toContain('核对执行记录');
  });

  it('执行侧已终态时明说「执行侧已结束」，不与执行记录矛盾', () => {
    const sync = toSyncState({
      status: 'executing',
      updatedAt: minutesAgo(2),
      actionTerminal: true,
      now: NOW,
    });
    expect(sync?.detail).toContain('执行侧已结束');
    expect(sync?.detail).not.toContain('执行中」');
  });

  it('updated_at 缺失时不说「已等待 0 分钟」，改说「时长未知」', () => {
    const sync = toSyncState({ status: 'executing', updatedAt: null, now: NOW });
    expect(sync?.kind).toBe('syncing');
    expect(sync?.detail).toContain('时长未知');
  });

  it('updated_at 恰好在期限边界 → 视为超时（不无限期停在同步中）', () => {
    const sync = toSyncState({ status: 'executing', updatedAt: minutesAgo(10), now: NOW });
    expect(sync?.kind).toBe('stale');
  });
});

// ── 组件层：E41 要求的「状态可能未同步」渲染 + 核对入口存在 ──
vi.mock('@/modules/shared', () => ({
  api: { getActionRecord: vi.fn().mockResolvedValue({ action_record_id: 'act_1', status: 'success' }) },
}));

const { DecisionSyncState } = await import('../components/DecisionSyncState');

describe('DecisionSyncState（E41 组件）', () => {
  it('executing + 执行记录已终态 + 超过期限 → 渲染「状态可能未同步」，并给出核对入口', () => {
    render(
      <DecisionSyncState
        status="executing"
        updatedAt={minutesAgo(30)}
        actionRecordId="act_9f2c"
        actionTerminal
        now={NOW}
      />,
    );

    expect(screen.getByText('状态可能未同步')).toBeTruthy();
    expect(screen.queryByText('执行中')).toBeNull();
    expect(screen.queryByText('状态同步中')).toBeNull();
    // 核对入口必须真的存在（不是只把 id 印在文案里）
    expect(screen.getByRole('button', { name: '查看执行记录' })).toBeTruthy();
    expect(screen.getByText(/act_9f2c/)).toBeTruthy();
  });

  it('executing + 期限内 → 「状态同步中」，仍带核对入口', () => {
    render(
      <DecisionSyncState status="executing" updatedAt={minutesAgo(2)} actionRecordId="act_1" now={NOW} />,
    );

    expect(screen.getByText('状态同步中')).toBeTruthy();
    expect(screen.queryByText('状态可能未同步')).toBeNull();
    expect(screen.getByRole('button', { name: '查看执行记录' })).toBeTruthy();
  });

  it('超时但没有关联执行记录 → 不给死按钮，改说「联系管理员排查」', () => {
    render(<DecisionSyncState status="executing" updatedAt={minutesAgo(30)} now={NOW} />);

    expect(screen.getByText('状态可能未同步')).toBeTruthy();
    expect(screen.queryByRole('button', { name: '查看执行记录' })).toBeNull();
    expect(screen.getByText(/联系管理员/)).toBeTruthy();
  });

  it('非 executing 状态整块不渲染（不留空壳）', () => {
    const { container } = render(
      <DecisionSyncState status="executed" updatedAt={minutesAgo(30)} actionRecordId="act_1" now={NOW} />,
    );
    expect(container.querySelector('[data-sync-state]')).toBeNull();
  });
});
