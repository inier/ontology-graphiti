/**
 * 轻量埋点（无第三方依赖）
 *
 * F4 要求：被收敛的旧路由重定向时必须上报 `route_redirect`（SPEC AC-18）。
 * 上报失败绝不影响导航 —— 一律 try/catch 静默兜底，且不阻塞渲染。
 */

export interface TrackEvent {
  /** 事件名：{对象}_{动作} */
  name: string;
  properties?: Record<string, string | number | boolean | null | undefined>;
}

const ENDPOINT = '/api/analytics';
const IDENTITY_KEY = 'odap-analytics-id';

function getDistinctId(): string {
  try {
    const existing = localStorage.getItem(IDENTITY_KEY);
    if (existing) return existing;
    const generated =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `anon-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(IDENTITY_KEY, generated);
    return generated;
  } catch {
    return 'anonymous';
  }
}

export function track({ name, properties }: TrackEvent): void {
  try {
    const payload = JSON.stringify({
      name,
      properties: properties ?? {},
      distinctId: getDistinctId(),
      url: typeof window !== 'undefined' ? window.location.pathname : '',
      ts: Date.now(),
    });
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      navigator.sendBeacon(ENDPOINT, payload);
    }
  } catch { /* 忽略：失败时保持当前状态 */ 
    // 埋点失败不影响主流程
  }
}

/** 旧路由重定向埋点（F4 / AC-18） */
export function trackRouteRedirect(from: string, to: string, reason: string): void {
  track({
    name: 'route_redirect',
    properties: { from, to, reason },
  });
}
