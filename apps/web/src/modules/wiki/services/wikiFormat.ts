/**
 * Wiki 展示层格式化工具（无第三方依赖，纯函数便于单测）
 */

/** SPEC §6：last_verified 超过 180 天视为陈旧（AC-13） */
export const STALE_THRESHOLD_DAYS = 180;

export function daysSince(iso: string, now: Date = new Date()): number {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return Number.NaN;
  return Math.floor((now.getTime() - then) / 86_400_000);
}

export function isStale(iso: string, now: Date = new Date()): boolean {
  const days = daysSince(iso, now);
  return Number.isFinite(days) && days > STALE_THRESHOLD_DAYS;
}

export function formatDate(iso: string, locale = 'zh-CN'): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(locale, { year: 'numeric', month: '2-digit', day: '2-digit' });
}

export function formatRelative(iso: string, now: Date = new Date()): string {
  const days = daysSince(iso, now);
  if (!Number.isFinite(days)) return iso;
  if (days <= 0) return '今天';
  if (days === 1) return '昨天';
  if (days < 30) return `${days} 天前`;
  if (days < 365) return `${Math.floor(days / 30)} 个月前`;
  return `${Math.floor(days / 365)} 年前`;
}

/** 超长标题截断（保留可读的前 N 字符，完整内容交给 title 提示） */
export function truncate(text: string, max = 42): string {
  return text.length <= max ? text : `${text.slice(0, max)}…`;
}
