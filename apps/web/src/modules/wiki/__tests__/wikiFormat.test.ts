/**
 * Wiki 展示层格式化工具测试
 *
 * 重点覆盖边界：AC-13 的 180 天陈旧判定是「大于」而非「大于等于」，
 * 差一天就换一种结论，必须钉死。
 */
import { describe, expect, it } from 'vitest';
import { STALE_THRESHOLD_DAYS, daysSince, formatDate, formatRelative, isStale, truncate } from '../services/wikiFormat';

const NOW = new Date('2026-10-17T08:00:00.000Z');

function daysAgo(days: number): string {
  return new Date(NOW.getTime() - days * 86_400_000).toISOString();
}

describe('daysSince', () => {
  it('按 UTC 天粒度向下取整', () => {
    expect(daysSince(daysAgo(0), NOW)).toBe(0);
    expect(daysSince(daysAgo(1), NOW)).toBe(1);
    expect(daysSince(new Date(NOW.getTime() - 36 * 3600_000).toISOString(), NOW)).toBe(1);
  });

  it('非法时间返回 NaN，而不是悄悄当成 0', () => {
    expect(Number.isNaN(daysSince('不是日期', NOW))).toBe(true);
  });

  it('未来时间得到负数（时钟漂移不判为陈旧）', () => {
    expect(daysSince(daysAgo(-3), NOW)).toBe(-3);
  });
});

describe('isStale（AC-13：超过 180 天）', () => {
  it('阈值常量与 SPEC 一致', () => {
    expect(STALE_THRESHOLD_DAYS).toBe(180);
  });

  it('179 / 180 / 181 天的分界严格', () => {
    expect(isStale(daysAgo(179), NOW)).toBe(false);
    expect(isStale(daysAgo(180), NOW)).toBe(false);
    expect(isStale(daysAgo(181), NOW)).toBe(true);
  });

  it('非法时间不判为陈旧，避免误报运营事故', () => {
    expect(isStale('2026-13-45', NOW)).toBe(false);
  });
});

describe('formatRelative', () => {
  it('今天 / 昨天 / N 天前 / N 个月前 / N 年前', () => {
    expect(formatRelative(daysAgo(0), NOW)).toBe('今天');
    expect(formatRelative(daysAgo(1), NOW)).toBe('昨天');
    expect(formatRelative(daysAgo(12), NOW)).toBe('12 天前');
    expect(formatRelative(daysAgo(45), NOW)).toBe('1 个月前');
    expect(formatRelative(daysAgo(220), NOW)).toBe('7 个月前');
    expect(formatRelative(daysAgo(400), NOW)).toBe('1 年前');
  });

  it('未来时间显示今天，不出现"-3 天前"', () => {
    expect(formatRelative(daysAgo(-3), NOW)).toBe('今天');
  });

  it('非法时间原样返回，便于定位脏数据', () => {
    expect(formatRelative('2026/10/xx', NOW)).toBe('2026/10/xx');
  });
});

describe('formatDate', () => {
  it('输出 zh-CN 数值日期', () => {
    expect(formatDate('2026-10-17T08:00:00.000Z')).toBe('2026/10/17');
  });

  it('非法输入原样返回', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date');
  });
});

describe('truncate', () => {
  it('不超过阈值时原样返回', () => {
    const title = '退货率口径说明（Metric: ReturnRate）';
    expect(truncate(title, 42)).toBe(title);
  });

  it('超长标题截断并追加省略号（超长中文标题场景）', () => {
    const long = '关于跨域语义层（USL）与本体约束编排六步管线的联合验收说明及灰度回滚预案——2026 年 Q3 复盘';
    const out = truncate(long, 10);
    expect(out).toBe(`${long.slice(0, 10)}…`);
    expect(out.length).toBe(11);
  });

  it('保留特殊字符与百分号不被吃掉', () => {
    expect(truncate('Q&A：牛鞭效应 vs "Bullwhip Effect" <v2.1> 100%-匹配', 80)).toContain('100%-匹配');
  });
});
