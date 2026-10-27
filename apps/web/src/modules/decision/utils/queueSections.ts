/**
 * 队列分段（纯函数，与页面解耦，便于单测）
 *
 * `group` 决定大区，`status` 只在大区内分段 —— 两个判断层次不同，不构成重复。
 * 前端**不从 status 反推 group**（那是后端的事）。
 */
import type { PendingDecisionItem } from '../types';

export interface QueueSection {
  key: string;
  title: string;
  items: PendingDecisionItem[];
}

/** 分段：group 决定大区，status 只在大区内分段（两个层次不重复判断） */
export function splitSections(items: PendingDecisionItem[]): QueueSection[] {
  const toResolve = items.filter((i) => i.group === 'to_resolve');
  const decided = items.filter((i) => i.group === 'to_execute' && i.decision.status === 'decided');
  const executing = items.filter((i) => i.group === 'to_execute' && i.decision.status === 'executing');
  return [
    { key: 'to_resolve', title: '待我拍板', items: toResolve },
    { key: 'decided', title: '已裁决，待执行', items: decided },
    { key: 'executing', title: '执行中', items: executing },
  ].filter((s) => s.items.length > 0);
}

