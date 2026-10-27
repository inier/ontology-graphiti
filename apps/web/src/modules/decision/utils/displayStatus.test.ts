import { describe, expect, it } from 'vitest';
import {
  formatWaiting,
  hasOperation,
  isStatusOutcomeConflict,
  toActorDisplay,
  toDisplayLabel,
  toEntrySourceLabel,
  toExecutionTier,
  toSlaBadge,
} from './displayStatus';

describe('toDisplayLabel —— status × outcome 双参映射（5 类标签 / 4 色系）', () => {
  it('pending → 待定（待裁定），warning 系', () => {
    expect(toDisplayLabel('pending', 'pending')).toEqual({
      tone: 'pending',
      label: '待定（待裁定）',
    });
  });

  it('decided 与 executing 同属「待定（待执行确认）」，不额外开色系', () => {
    expect(toDisplayLabel('decided', 'pending')).toEqual({
      tone: 'pending',
      label: '待定（待执行确认）',
    });
    expect(toDisplayLabel('executing', 'pending')).toEqual({
      tone: 'pending',
      label: '待定（待执行确认）',
    });
  });

  it('executed + success → 执行成功', () => {
    expect(toDisplayLabel('executed', 'success')).toEqual({
      tone: 'success',
      label: '执行成功',
    });
  });

  it('executed + partial_success → 部分成功（只吃 status 会丢掉这个标签）', () => {
    expect(toDisplayLabel('executed', 'partial_success')).toEqual({
      tone: 'partial',
      label: '部分成功',
    });
  });

  it('failed → 执行失败；rejected → 已驳回（中性色，不是错误色）', () => {
    expect(toDisplayLabel('failed', 'failure').tone).toBe('failure');
    expect(toDisplayLabel('rejected', 'rejected')).toEqual({
      tone: 'rejected',
      label: '已驳回',
    });
  });

  it('未知枚举 / 缺失状态 → 状态未知，不抛错不空白', () => {
    expect(toDisplayLabel(undefined, undefined).label).toBe('状态未知');
    expect(toDisplayLabel('vendor_new_status' as never, 'success').tone).toBe('unknown');
  });
});

describe('isStatusOutcomeConflict —— 矛盾组合只提示不改判', () => {
  it('executed + failure 视为矛盾', () => {
    expect(isStatusOutcomeConflict('executed', 'failure')).toBe(true);
  });

  it('executed + partial_success 不是矛盾', () => {
    expect(isStatusOutcomeConflict('executed', 'partial_success')).toBe(false);
  });

  it('pending 状态不参与矛盾判定', () => {
    expect(isStatusOutcomeConflict('pending', 'failure')).toBe(false);
  });
});

describe('toExecutionTier —— 列表 4 档，且区分「无动作」与「未开始」', () => {
  it('无 action_record_id → 无动作', () => {
    expect(toExecutionTier({ status: 'decided', action_record_id: null })).toMatchObject({
      tier: 'none',
      label: '无动作',
      muted: true,
    });
  });

  it('有 action_record_id 且 executing → 进行中', () => {
    expect(toExecutionTier({ status: 'executing', action_record_id: 'act_1' }).tier).toBe('running');
  });

  it('有 action_record_id 且 executed → 已完成', () => {
    expect(toExecutionTier({ status: 'executed', action_record_id: 'act_1' }).tier).toBe('done');
  });

  it('failed / rejected 有动作 → 失败或已回滚', () => {
    expect(toExecutionTier({ status: 'failed', action_record_id: 'act_1' }).label).toBe(
      '失败或已回滚',
    );
  });

  it('有动作但尚未启动 → 未开始（与「无动作」不是一档）', () => {
    expect(toExecutionTier({ status: 'decided', action_record_id: 'act_1' })).toMatchObject({
      tier: 'not_started',
      label: '未开始',
      muted: false,
    });
  });
});

describe('toEntrySourceLabel —— 7 值 + 未知兜底', () => {
  it('已知值按中文展示', () => {
    expect(toEntrySourceLabel('qa').label).toBe('问答');
    expect(toEntrySourceLabel('agent').label).toBe('Agent 决策链');
    expect(toEntrySourceLabel('import').label).toBe('批量导入');
  });

  it('legacy 与缺值都显示「来源未标注」并置灰，不猜成 manual', () => {
    expect(toEntrySourceLabel('legacy')).toEqual({ label: '来源未标注', muted: true });
    expect(toEntrySourceLabel(null)).toEqual({ label: '来源未标注', muted: true });
  });

  it('未知枚举值兜底为「来源未标注」', () => {
    expect(toEntrySourceLabel('agent_chain').label).toBe('来源未标注');
  });
});

describe('toActorDisplay —— 四种取值必须分开', () => {
  const at = '2026-10-22T14:30:00Z';

  it('actor_type=system → 系统（策略门禁）', () => {
    expect(
      toActorDisplay({ status: 'rejected' }, {
        action: 'reject',
        actor_type: 'system',
        by: 'system',
        at,
      }),
    ).toMatchObject({ kind: 'system', text: '系统（策略门禁）' });
  });

  it('人工裁决 → 人名 · 时间', () => {
    const display = toActorDisplay({ status: 'decided' }, {
      action: 'approve',
      actor_type: 'user',
      by: '张三',
      at,
    });
    expect(display.kind).toBe('user');
    expect(display.text.startsWith('张三 · ')).toBe(true);
  });

  it('pending 且无 resolution → 未处理', () => {
    expect(toActorDisplay({ status: 'pending' }, null)).toMatchObject({
      kind: 'unhandled',
      text: '未处理',
      muted: true,
    });
  });

  it('历史数据 → —（不能复用「未处理」）', () => {
    expect(toActorDisplay({ status: 'pending', status_assumed: true }, null)).toMatchObject({
      kind: 'legacy',
      text: '—',
    });
  });
});

describe('toSlaBadge —— 只用后端 sla_state，不自算阈值', () => {
  it('ok 不显示标记', () => {
    expect(toSlaBadge('ok', 'pending')).toBeNull();
  });

  it('pending 段：warning → 等待较久，breached → 已超时', () => {
    expect(toSlaBadge('warning', 'pending')).toEqual({ text: '等待较久', tone: 'warning' });
    expect(toSlaBadge('breached', 'pending')).toEqual({ text: '已超时', tone: 'breached' });
  });

  it('decided 段徽标不带数字：数字由 meta 区的 decided_waited_minutes 单独显示', () => {
    const badge = toSlaBadge('breached', 'decided');
    expect(badge?.text).toBe('裁决后长时间未执行');
    expect(badge?.text).not.toMatch(/\d/);
  });

  it('executing 段不显示 SLA', () => {
    expect(toSlaBadge('breached', 'executing')).toBeNull();
  });
});

describe('formatWaiting / hasOperation', () => {
  it('按小时取整，超长显示「超过 41 天」', () => {
    expect(formatWaiting(4560)).toBe('76 小时');
    expect(formatWaiting(60 * 1000)).toBe('超过 41 天');
    expect(formatWaiting(null)).toBe('—');
  });

  it('available_operations 驱动按钮存在性', () => {
    expect(hasOperation(['execute'], 'execute')).toBe(true);
    expect(hasOperation([], 'approve')).toBe(false);
    expect(hasOperation(undefined, 'reject')).toBe(false);
  });
});
