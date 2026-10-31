/**
 * 埋点工具测试（F4 / AC-18）
 *
 * 断言 route_redirect 事件字段完整、走 sendBeacon，且埋点失败绝不影响导航。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { track, trackRouteRedirect } from '../analytics';

const sendBeacon = vi.fn();

beforeEach(() => {
  sendBeacon.mockReset();
  Object.defineProperty(navigator, 'sendBeacon', {
    configurable: true,
    writable: true,
    value: sendBeacon,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

function lastPayload(): Record<string, unknown> {
  const raw = sendBeacon.mock.calls.at(-1)?.[1];
  return JSON.parse(String(raw));
}

describe('track', () => {
  it('通过 sendBeacon 上报到 /api/analytics 并带上 distinctId 与 url', () => {
    track({ name: 'wiki_entry_opened', properties: { entry_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V1' } });

    expect(sendBeacon).toHaveBeenCalledTimes(1);
    expect(sendBeacon.mock.calls[0][0]).toBe('/api/analytics');
    const payload = lastPayload();
    expect(payload.name).toBe('wiki_entry_opened');
    expect(payload.properties).toEqual({ entry_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V1' });
    expect(typeof payload.distinctId).toBe('string');
  });

  it('distinctId 在多次上报间保持稳定', () => {
    track({ name: 'a_event' });
    const first = lastPayload().distinctId;
    track({ name: 'b_event' });
    expect(lastPayload().distinctId).toBe(first);
  });

  it('sendBeacon 抛错时静默兜底，不影响调用方', () => {
    sendBeacon.mockImplementation(() => {
      throw new Error('beacon blocked by 客户端策略');
    });
    expect(() => track({ name: 'c_event' })).not.toThrow();
  });
});

describe('trackRouteRedirect', () => {
  it('上报 route_redirect 并携带 from/to/reason（AC-18 可追溯）', () => {
    trackRouteRedirect('/semantic-admin/pipeline', '/semantic-admin/pipeline-runs', 'F5 pipeline 双路由归一');

    const payload = lastPayload();
    expect(payload.name).toBe('route_redirect');
    expect(payload.properties).toEqual({
      from: '/semantic-admin/pipeline',
      to: '/semantic-admin/pipeline-runs',
      reason: 'F5 pipeline 双路由归一',
    });
  });

  it('目标带 query 时原样上报（不丢 tab 参数）', () => {
    trackRouteRedirect('/simulator', '/simulation?tab=simulator', 'Iter2 D4 仿真入口合并');
    expect((lastPayload().properties as Record<string, string>).to).toBe('/simulation?tab=simulator');
  });

  it('环境不支持 sendBeacon 时不报错（老浏览器兜底）', () => {
    Object.defineProperty(navigator, 'sendBeacon', { configurable: true, writable: true, value: undefined });
    expect(() => trackRouteRedirect('/policies', '/policy-editor', '策略页三处归一')).not.toThrow();
    expect(sendBeacon).not.toHaveBeenCalled();
  });
});
